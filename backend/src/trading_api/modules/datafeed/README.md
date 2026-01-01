# Datafeed Module

**Status**: ✅ Production Ready  
**Last Updated**: January 1, 2026  
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

```python
# In DatafeedService
def create_topic(self, topic: str, topic_update: Callback, topic_error: Callback, user_id: str):
    """Parse topic, create provider subscription, track subscription IDs."""
    topic_type, params_json = topic.split(":", 1)

    if topic_type == "bars":
        subscription_id = self.datafeed_provider.subscribe_realtime_bars(
            ticker_name=request.symbol,
            resolution=request.resolution,
            callback=topic_update,
            on_error=on_provider_error,
        )
        self._topic_to_subs[topic] = [subscription_id]

    elif topic_type == "quotes":
        # Multiple subscriptions for quotes (one per symbol)
        for symbol in all_symbols:
            subscription_id = self.datafeed_provider.subscribe_market_data(
                ticker_name=symbol,
                callback=topic_update,
                on_error=on_provider_error,
            )
            self._topic_to_subs.setdefault(topic, []).append(subscription_id)

def remove_topic(self, topic: str):
    """Cleanup provider subscriptions on topic removal."""
    subscription_ids = self._topic_to_subs.pop(topic, [])
    for subscription_id in subscription_ids:
        if topic_type == "bars":
            self.datafeed_provider.unsubscribe_realtime_bars(subscription_id)
        elif topic_type == "quotes":
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

| Model                          | Purpose                                 |
| ------------------------------ | --------------------------------------- |
| `Bar`                          | OHLC bar data                           |
| `BarsSubscriptionRequest`      | Bars subscription parameters            |
| `QuoteData`                    | Quote with bid/ask/last                 |
| `QuoteDataSubscriptionRequest` | Quote subscription parameters           |
| `SymbolInfo`                   | Full symbol information for TradingView |
| `SearchSymbolResultItem`       | Symbol search result                    |
| `DatafeedConfiguration`        | Datafeed capabilities/config            |
| `GetBarsResponse`              | Historical bars response wrapper        |
| `Resolution`                   | Type-safe TradingView resolution enum   |

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

---

**Last Updated**: January 1, 2026
