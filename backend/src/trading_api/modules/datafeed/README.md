# Datafeed Module

**Status**: ✅ Production Ready  
**Last Updated**: January 31, 2026  
**Related Files**: `backend/src/trading_api/modules/datafeed/`

---

## Overview

BFF (Backend-For-Frontend) module for market data operations. Provides REST API and WebSocket streaming for bars (OHLC), quotes, symbol search, and resolution.

**Key Responsibilities**:

- Translate frontend API requests to provider subscriptions
- Route WebSocket topics (`bars`, `quotes`) to appropriate `DatafeedCapability` provider methods
- Handle error classification (recoverable vs non-recoverable, including TWS API error routing)
- Delegate all business logic to the datafeed provider

---

## Architecture

### Module Structure

```
modules/datafeed/
├── __init__.py           # DatafeedModule class
├── service.py            # DatafeedService (BFF layer, provider delegation)
├── api/v1.py             # REST endpoints (config, search, bars, quotes)
├── ws/v1/__init__.py     # WebSocket routers (bars, quotes)
├── specs_generated/      # OpenAPI/AsyncAPI specs (auto-generated)
├── client_generated/     # Python client (auto-generated)
└── tests/                # Module tests
```

### Service Layer Pattern

The `DatafeedService` follows the **WsRouteService** pattern (mirrors `BrokerService` exactly):

```python
class DatafeedService(WsRouteService):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="datafeed")]

    @property
    def datafeed_provider(self) -> DatafeedCapability:
        # Cached O(1) lookup - type-safe provider access
        provider = self.get_capability_provider("datafeed")
        return provider
```

**[DECISION]**: DatafeedService is a thin BFF layer - all business logic lives in the `DatafeedCapability` provider (e.g., `TWSDatafeedProvider`).

**[PATTERN]**: Simple Topic Controller - Service subscribes to the provider once per symbol per topic. Symbol mutualization (deduplication) is handled at the provider/tracker level (`QuoteTracker` manages subscription reference counting internally).

**Datastore Access**: Service inherits `datastore` property from `ServiceInterface`. Used to initialize `BarRepository(self.datastore)` for bar storage with per-table RWLock concurrency.

### Repository Layer

The module includes a `BarRepository` for OHLC bar storage using `DatastoreInterface`:

```python
class BarRepository:
    def __init__(self, datastore: DatastoreInterface) -> None:
        self._datastore = datastore
        self._table_classes: dict[str, type[Bar]] = {}  # Cache dynamic subclasses

    def _get_bar_table(self, symbol: str, resolution: Resolution) -> TableInterface[Bar]:
        # Creates separate table per symbol/resolution: bars_{symbol}_{resolution}
        table_name = f"bars_{symbol.lower()}_{resolution.value.lower()}"
        if table_name not in self._table_classes:
            self._table_classes[table_name] = type(table_name, (Bar,), {"__tablename__": table_name})
        return self._datastore.table(self._table_classes[table_name])

    async def store_bars(self, symbol: str, resolution: Resolution, bars: list[Bar]) -> int:
        table = self._get_bar_table(symbol, resolution)
        # Store bars keyed by timestamp (ms)
        ...
```

**Key Points:**

- Creates dynamic `TableInterface` per symbol/resolution combination
- Table naming convention: `bars_{symbol}_{resolution}` (e.g., `bars_aapl_1d`)
- Bars keyed by timestamp (upsert semantics via `table.set()`)
- Supports cleanup via `drop_if_empty()` using `datastore.drop_table()`

### Cache Management Layer

The `BarCacheManager` provides intelligent cache metadata tracking for historical bars:

```python
from trading_api.datastores import InMemoryDatastore
from trading_api.modules.datafeed.bar_cache_manager import BarCacheManager
from trading_api.models.market import TimeRange
from trading_api.shared.config import Settings

# Initialize via async factory (required pattern)
datastore = InMemoryDatastore()
settings = Settings()  # Uses BAR_CACHE_PENDING_TTL_MS config
manager = await BarCacheManager.create(datastore=datastore, settings=settings)

# Track in-flight request (async)
await manager.add_pending(symbol="AAPL", resolution=resolution, time_range=TimeRange(start=start, end=end))

# After successful fetch, mark as covered
await manager.mark_covered(symbol="AAPL", resolution=resolution, time_range=TimeRange(start=start, end=end), storage_type=StorageType.MEMORY, bar_count=100)

# Find gaps for subsequent requests
missing = await manager.find_missing_ranges("AAPL", resolution, query_start, query_end)
# Returns: [TimeRange(start=gap_start, end=gap_end), ...]
```

**Instantiation**: Direct `__init__` is forbidden (raises `TradingApiException`). Use `BarCacheManager.create()` factory which handles index creation and settings injection.

**Key Features**:

| Feature              | Description                                                                          |
| -------------------- | ------------------------------------------------------------------------------------ |
| **Gap Detection**    | Boundary-based algorithm finds uncached time ranges                                  |
| **Pending Tracking** | Prevents duplicate in-flight requests (TTL via `settings.BAR_CACHE_PENDING_TTL_MS`)  |
| **Range Merging**    | Adjacent/overlapping covered ranges auto-merge                                       |
| **Storage Tracking** | `CoveredRange.storage_type` indicates cache tier (MEMORY, DATABASE, DATALAKE)        |
| **Thread Safety**    | Datastore provides per-table locking for concurrent access (no external lock needed) |
| **Atomic Transitions** | `mark_covered()` uses database transactions to atomically delete pending + insert covered |

**`mark_covered()` Atomicity**: This method atomically removes the pending range and creates the covered range in a single transaction:

```python
async def mark_covered(self, symbol, resolution, time_range, storage_type, bar_count):
    # Uses database transaction for atomic delete+insert
    async with self._session_factory() as session:
        await self.pending_table.delete(req_range_key, session=session)
        await self.covered_table.set(req_range_key, covered, session=session)
        await session.commit()  # Both operations committed atomically
```

**Requirement**: `BarCacheManager.__init__` validates that the datastore has `has_transactions=True`. This ensures the atomic delete+insert pattern cannot leave partial state (pending deleted but covered not created).

**Models** (from `trading_api.models.market.bar_cache`):

| Model          | Purpose                                                                   |
| -------------- | ------------------------------------------------------------------------- |
| `TimeRange`    | Base range with `start`/`end` int milliseconds                            |
| `PendingRange` | In-flight request with `expires_at` timestamp, auto-computed `lookup_key` |
| `CoveredRange` | Cached data with `storage_type` indicator, auto-computed `lookup_key`     |

**Note**: `PendingRange` and `CoveredRange` have a `lookup_key` field (computed via `model_post_init()` as `{symbol}_{resolution}`) enabling indexed datastore lookups.

### Provider Delegation

```
┌─────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│  DatafeedApi    │───▶│  DatafeedService   │───▶│  DatafeedCapability │
│  (REST)         │    │  (BFF Layer)       │    │  (Provider)         │
└─────────────────┘    └────────────────────┘    └─────────────────────┘
                              │
┌─────────────────┐           │
│ DatafeedWsRouters│──────────┘
│  (WebSocket)    │
└─────────────────┘
```

---

## API Endpoints

All endpoints require authentication via JWT in HttpOnly cookie.

| Method | Path                                | Operation ID    | Description                   |
| ------ | ----------------------------------- | --------------- | ----------------------------- |
| GET    | `/api/datafeed/v1/config`           | `getConfig`     | Get datafeed configuration    |
| GET    | `/api/datafeed/v1/search`           | `searchSymbols` | Search symbols by pattern     |
| GET    | `/api/datafeed/v1/resolve/{symbol}` | `resolveSymbol` | Resolve symbol information    |
| GET    | `/api/datafeed/v1/bars`             | `getBars`       | Get historical OHLC bars      |
| POST   | `/api/datafeed/v1/quotes`           | `getQuotes`     | Get real-time quotes snapshot |

### Historical Bars Endpoint

Returns OHLC bars for specified symbol, resolution, and time range.

**Request Parameters:**

- `symbol` (required): Ticker symbol (e.g., "NASDAQ:AAPL")
- `resolution` (required): Bar size ("1", "5", "15", "60", "D", "W", "M")
- `from` (required): Start timestamp (Unix seconds)
- `to` (required): End timestamp (Unix seconds)
- `countBack` (optional): Max bars to return

**Response**: List of `Bar` objects with OHLC data

**Empty Response Handling:**

The provider logs a warning when no bars are returned:

```python
bars = await self.datafeed_provider.get_historical_bars(...)
if not bars:
    logger.warning(
        f"No bars returned for {ticker} {duration} ending {end_datetime_str}"
    )
```

**Rationale**: Distinguishes between provider errors (exceptions thrown) and legitimate "no data" scenarios (empty list returned). Common causes of empty responses:

- Symbol not available for requested time range
- Market closed during entire period
- Insufficient historical data for new listings
- Invalid resolution for asset type (e.g., "1" minute bars for illiquid symbols)

**Response**: Empty list `[]` is returned to frontend (not an error). TradingView charting library handles empty datasets gracefully.

### Configuration Endpoint

Returns datafeed capabilities for TradingView charting library integration:

```python
class DatafeedConfiguration:
    supported_resolutions: list[str]  # ["1", "5", "15", "60", "D", "W", "M"]
    exchanges_list: list[dict]
    symbols_types: list[dict]
    currency_codes: list[str]
```

---

## WebSocket Topics

Real-time streaming via WebSocket with topic-based routing.

| Topic    | Request Model                  | Response Model | Description                       |
| -------- | ------------------------------ | -------------- | --------------------------------- |
| `bars`   | `BarsSubscriptionRequest`      | `Bar`          | Real-time OHLC bar updates        |
| `quotes` | `QuoteDataSubscriptionRequest` | `QuoteData`    | Real-time quote updates (bid/ask) |

### Topic Format

Topics use the format `{topic_type}:{json_params}`:

```
bars:{"resolution":"1D","symbol":"AAPL"}
quotes:{"symbols":["AAPL","GOOGL"],"fast_symbols":["MSFT"]}
```

### Topic Lifecycle

**Direct Provider Callback Pattern (Simplified - January 19, 2026)**

**Bars Subscription - Direct Domain Model Callback:**

```python
# In DatafeedService.create_topic()
if topic_type == "bars":
    # Direct delegation - provider returns Bar domain model via BarsTracker
    subscription_id = await self.datafeed_provider.subscribe_realtime_bars(
        ticker_name=request.symbol,
        resolution=request.resolution,
        callback=topic_update,  # ← Receives Bar domain model directly
        on_error=on_sub_error,
    )
    self._topic_to_subs[topic] = [subscription_id]
```

**Architectural Fix (January 19, 2026):**

- **Before**: Intermediate callback wrapper converted raw TWS dict to Bar
- **After**: Provider delegates to `BarsTracker` which converts TWS BarData → Bar domain model
- **Impact**: Eliminated 10 lines of redundant conversion logic from datafeed_provider.py
- **Benefit**: Single conversion point for all bars (historical + real-time)

**Quotes Subscription - Topic-Level Subscriptions:**

```python
# In DatafeedService.create_topic()
elif topic_type == "quotes":
    all_symbols = list(set(request.symbols + request.fast_symbols))
    subscription_ids = self._topic_to_subs.setdefault(topic, [])

    for symbol in all_symbols:
        subscription_id = await self.datafeed_provider.subscribe_market_data(
            ticker_name=symbol,
            callback=topic_update,  # Same callback for all symbols in this topic
            on_error=on_sub_error,
        )
        subscription_ids.append(subscription_id)
```

**Key Points:**

- **Simple Topic Controller**: Service creates one provider subscription per symbol per topic (no service-level deduplication)
- **Provider-Level Mutualization**: If multiple topics request the same symbol, the provider (`TWSDatafeedProvider` + `QuoteTracker`) handles subscription reference counting and shares the underlying TWS subscription
- **Topic Cleanup**: When `remove_topic()` is called, all subscription IDs for that topic are unsubscribed
- **Error Handling**: Provider errors are classified as recoverable/non-recoverable at the service level via `_is_error_recoverable()`

**Debug Logging:**

```bash
export DEBUG_TWS_DATAFEED=true  # Enables verbose topic lifecycle logs
```

**Quote Callback Wrapper** - Multiplexes provider updates to all subscribed topics:

```python
def quote_cb_wapper(self, symbol: str):
    """Wrap provider callbacks to fan out to all topics subscribed to this symbol."""
    async def callback_wrapper(data: QuoteData) -> None:
        await asyncio.gather(
            *[cb(data) for cb, _ in self._quote_callbacks.get(symbol, {}).values()]
        )
    return callback_wrapper, on_provider_error
```

**Cleanup** - Unsubscribes from provider only when last topic for a symbol is removed:

```python
def remove_topic(self, topic: str):
    if topic_type == "quotes":
        for symbol in all_symbols:
            symbol_callbacks = self._quote_callbacks.get(symbol, {})
            symbol_callbacks.pop(topic, None)
            if not symbol_callbacks:  # Last topic for this symbol
                self._quote_callbacks.pop(symbol, None)
                subscription_id = self._quote_symbol_to_sub_id.pop(symbol, None)
                if subscription_id:
                    self.datafeed_provider.unsubscribe_market_data(subscription_id)
```

---

## Error Handling

### Recoverable vs Non-Recoverable Errors

The service classifies errors to determine WebSocket connection behavior:

```python
_RECOVERABLE_ERROR_CODES: frozenset[str] = frozenset({
    "PROVIDER_DATAFEED_TIMEOUT",
    "PROVIDER_DATAFEED_CONNECTION_LOST",
    "PROVIDER_DATAFEED_RATE_LIMIT",
    "PROVIDER_DATAFEED_DATA_GAP",
})

def _is_error_recoverable(self, exc: TradingApiException) -> bool:
    """TWS-aware error classification."""
    code = exc.code

    # Check explicit recoverable codes
    if code in _RECOVERABLE_ERROR_CODES:
        return True

    # TWS API error codes: PROVIDER_TWS_API_{CATEGORY}_{CODE}[_NON_RECOVERABLE]
    if code.startswith("PROVIDER_TWS_API_"):
        if code.endswith("_NON_RECOVERABLE"):
            return False
        return True  # Other TWS errors are recoverable by default

    return False  # Default: non-recoverable
```

**[DECISION]**: TWS errors use suffix-based classification for flexibility. Errors ending in `_NON_RECOVERABLE` close the connection; others allow retry.

### Error Flow

1. Provider raises `ProviderException` or `TradingApiException`
2. `DatafeedService.on_provider_error()` wraps with recoverable/retry_after_ms
3. For recoverable: `SubscriptionError` sent, connection stays open, retry after 5 seconds
4. For non-recoverable: `SubscriptionError` sent, connection closes

### Quote-Specific Error Handling

Quote errors are multiplexed to all topics subscribed to the affected symbol:

```python
async def on_provider_error(exc: TradingApiException) -> None:
    recoverable = self._is_error_recoverable(exc)
    if not recoverable:
        # Clean up all topics for this symbol
        self._quote_symbol_to_sub_id.pop(symbol, None)
        for topic in self._quote_callbacks.get(symbol, {}).keys():
            self._topic_to_subs.pop(topic, None)

    # Fan out error to all affected topics
    retry_after_ms = _DEFAULT_RETRY_AFTER_MS if recoverable else None
    await asyncio.gather(
        *[err(exc, recoverable, retry_after_ms)
          for _, err in self._quote_callbacks.get(symbol, {}).values()]
    )
```

---

## Symbol Resolution

### Search Flow

```python
async def search_symbols(self, user_input: str, exchange: str = "",
                         symbol_type: str = "", max_results: int = 50):
    # 1. Delegate to provider for raw search
    provider_results = await self.datafeed_provider.search_symbols(
        pattern=user_input if user_input.strip() else "*",
        timeout=10.0,
    )

    # 2. Apply business logic filters
    if exchange:
        filtered = [r for r in filtered if r.exchange.lower() == exchange.lower()]
    if symbol_type:
        filtered = [r for r in filtered if r.type.lower() == symbol_type.lower()]

    return filtered[:max_results]
```

### Ticker Resolution

```python
async def resolve_ticker(self, ticker: str) -> Optional[SymbolInfo]:
    """Resolve full symbol info for TradingView charting."""
    return await self.datafeed_provider.get_symbol_info(
        ticker_name=ticker,
        timeout=5.0,
    )
```

---

## Testing

### Running Tests

```bash
# Module tests only
cd backend && poetry run pytest src/trading_api/modules/datafeed/tests/ -v

# With coverage
cd backend && poetry run pytest src/trading_api/modules/datafeed/tests/ --cov=src/trading_api/modules/datafeed
```

### Test Files

- `test_api.py` - REST API endpoint tests
- `test_bar_cache_manager.py` - BarCacheManager unit tests (24 tests covering pending/covered ranges, gap detection, cleanup)

### Mocking the Datafeed Provider

```python
@pytest.fixture
def mock_datafeed_provider():
    """Mock DatafeedCapability for unit tests."""
    provider = AsyncMock(spec=DatafeedCapability)
    provider.get_historical_bars.return_value = [mock_bar]
    provider.search_symbols.return_value = [mock_symbol]
    return provider
```

### WebSocket Testing

```python
async def test_bars_subscription(datafeed_ws_client):
    """Test bars topic subscription."""
    async with datafeed_ws_client.websocket_connect("/ws/datafeed/v1/bars") as ws:
        await ws.send_json({
            "action": "subscribe",
            "topic": 'bars:{"resolution":"1D","symbol":"AAPL"}'
        })
        response = await ws.receive_json()
        assert response["type"] == "subscribed"
```

---

## Models

Key Pydantic models used by this module (defined in `trading_api/models/`):

| Model                          | Purpose                                    |
| ------------------------------ | ------------------------------------------ |
| `Bar`                          | OHLC bar data                              |
| `BarsSubscriptionRequest`      | Bars subscription parameters               |
| `QuoteData`                    | Quote with bid/ask/last                    |
| `QuoteDataSubscriptionRequest` | Quote subscription parameters              |
| `SymbolInfo`                   | Full symbol information for TradingView    |
| `SearchSymbolResultItem`       | Symbol search result                       |
| `DatafeedConfiguration`        | Datafeed capabilities/config               |
| `GetBarsResponse`              | Historical bars response wrapper           |
| `Resolution`                   | Type-safe TradingView resolution enum      |
| `TimeRange`                    | Base range with start/end int milliseconds |
| `PendingRange`                 | In-flight request with TTL expiration      |
| `CoveredRange`                 | Cached range with storage type indicator   |

### SymbolInfo Fields (TradingView LibrarySymbolInfo)

| Priority | Fields                                                      | Notes                            |
| -------- | ----------------------------------------------------------- | -------------------------------- |
| Core     | `name`, `ticker`, `type`, `exchange`, `session`, `timezone` | Required TradingView fields      |
| P0       | `currency_code`, `original_currency_code`                   | Currency handling for trading    |
| P1       | `expired`, `expiration_date`                                | Derivatives support (FUT/OPT)    |
| P1       | `industry`, `sector`                                        | Categorization for search/filter |
| P2       | `con_id`, `has_weekly_and_monthly`, `delay`                 | TWS-specific metadata            |

### DatafeedConfiguration Fields

| Field                   | Type         | Description                                     |
| ----------------------- | ------------ | ----------------------------------------------- |
| `supported_resolutions` | `list[str]`  | Available bar resolutions ("1", "5", "D", etc.) |
| `exchanges`             | `list[dict]` | Available exchanges for symbol filtering        |
| `symbols_types`         | `list[dict]` | Available symbol types (stock, forex, etc.)     |
| `currency_codes`        | `list[str]`  | Supported currencies for price conversion (20+) |

---

## TradingView Integration

This module powers the TradingView charting library datafeed:

1. **Config** → `getConfig()` provides supported resolutions and exchanges
2. **Symbol Search** → `searchSymbols()` powers the symbol search UI
3. **Symbol Resolution** → `resolveSymbol()` provides full symbol info for charts
4. **Historical Data** → `getBars()` provides OHLC history for chart rendering
5. **Real-Time Updates** → WebSocket `bars` topic provides live bar updates
6. **Quotes** → WebSocket `quotes` topic provides live bid/ask updates

---

## Related Documentation

- **[TWS Provider](../../providers/tws/README.md)** - TWSDatafeedProvider implementation
- **[Provider System](../../../../docs/PROVIDER-SYSTEM.md)** - DatafeedCapability interface
- **[Backend WebSockets](../../../../docs/BACKEND_WEBSOCKETS.md)** - WsRouteService pattern
- **[Error Management](../../../../docs/ERROR-MANAGEMENT.md)** - Exception hierarchy
- **[Modular Backend Architecture](../../../../docs/MODULAR_BACKEND_ARCHITECTURE.md)** - Module lifecycle
