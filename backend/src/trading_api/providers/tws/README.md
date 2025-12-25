# TWS Provider

**Status:** Production-Ready (Datafeed + Broker Capabilities)  
**Architecture:** Three-Layer Streaming Pattern  
**Last Updated:** December 25, 2025

---

## Quick Reference

| Layer                       | File                                  | Responsibility                                    |
| --------------------------- | ------------------------------------- | ------------------------------------------------- |
| **3 - TWSDatafeedProvider** | `datafeed_provider.py`                | DatafeedCapability impl, domain conversion        |
| **3 - TWSBrokerProvider**   | `broker_provider.py`                  | BrokerCapability impl, order/position management  |
| **2 - TWSClient**           | `tws_connection.py`                   | AsyncIO facade, stream management, owns IBSocket  |
| **1 - IBSocket**            | `tws_connection.py`                   | Raw TCP, daemon thread, ticker slot registry      |
| **Mappers**                 | `tws_mappers.py`                      | TWS ↔ domain model conversion, ticker parsing     |
| **Models**                  | `tws_models.py`                       | `TWSCapability`, `AssetConfig`, tick/msg mappings |
| **Config**                  | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic settings               |

**Tests:** `providers/tws/tests/test_{client,mappers,provider,broker_provider}.py`

---

## Capabilities Overview

### Datafeed Capability

- Real-time market data streaming
- Historical OHLCV bars
- Symbol search and metadata
- Quote snapshots

### Broker Capability

- Order placement, modification, cancellation
- Position management (get, close)
- Account info and equity data
- Order/position streaming subscriptions

---

## 1. Architecture

### System Flow

```
DatafeedService (provider-agnostic)
        │ requires capability="datafeed"
        ▼
TWSDatafeedProvider (Layer 3) ─── implements DatafeedCapability
        │ domain ↔ TWS conversion, stream key management
        ▼
TWSClient (Layer 2) ─── owns IBSocket, async facade
        │ asyncio.Future bridge, stream subscription API
        ▼
IBSocket (Layer 1) ─── daemon thread _reader_loop(), _active_streams registry
        │ ticker slots, stream hooks, stream key ↔ reqId mapping
        ▼
TWS/IB Gateway (localhost:7497)
```

### Threading Model

```
Main Thread (AsyncIO)                    Daemon Thread
─────────────────────                    ─────────────
TWSDatafeedProvider.subscribe_market_data()      IBSocket._reader_loop()
        │                                        │
TWSClient.reqMktDataStream()             Decoder.interpret()
        │                                        │
register_stream(reqId, callback)         tickPrice(reqId, price)
        │                                        │
        │                                _stream_data[reqId]["bid"] = price
        │                                        │
callback(data) ◄──────────────────────── _notify_stream(reqId, ["bid"])
                                                 │
                    loop.call_soon_threadsafe(callback, stream_data, fields)
```

**Key Patterns:**

- **Lazy Connection**: `TWSClient.ibsocket` connects on first access
- **Future Bridge**: `asyncio.Future` + `call_soon_threadsafe()` for one-shot requests
- **Stream Slots**: `_stream_data[reqId]` dict accumulates real-time data
- **Stream Hooks**: `_stream_hooks[reqId]` holds (loop, callback, on_error) for continuous updates
- **Active Streams**: `IBSocket._active_streams[stream_key] → reqId` maps stream keys to request IDs
- **Stream Key Lookup**: `ibsocket.stream_req_id(key)` checks for existing subscription

---

## 2. Ticker Naming Convention

**Composite Ticker Format:**

```
{symbol}:{exchange}:{secType}-{conId}[@{bar_size}]
```

**Examples:**

- `"AAPL:NASDAQ:STK-12345"` - Stock ticker
- `"AAPL:NASDAQ:STK-12345@5 mins"` - Stream key with bar size

**Functions:**

```python
# Build stream key from contract
from tws_mappers import ticker_name, parse_ticker, build_contract

# ticker_name(contract) → "AAPL:NASDAQ:STK-12345"
# ticker_name(contract, "5 mins") → "AAPL:NASDAQ:STK-12345@5 mins"

# parse_ticker("AAPL:NASDAQ:STK-12345") → ("AAPL", "NASDAQ", "STK", 12345, None)
# parse_ticker("AAPL:NASDAQ:STK-12345@5 mins") → ("AAPL", "NASDAQ", "STK", 12345, "5 mins")

# build_contract("AAPL:NASDAQ:STK-12345") → Contract(symbol="AAPL", ...)
```

**Usage:**

- Subscription tracking: `TWSClient._active_streams[stream_key] = reqId`
- Ticker slot caching: Reuse existing stream for same contract
- Unsubscription: Cancel by stream key, not reqId

---

## 3. Asset Configuration

**File:** `tws_models.py`

Per-asset-type configuration for TWS API parameters:

```python
from tws_models import get_asset_config, AssetTypeConfig

@dataclass
class AssetTypeConfig:
    what_to_show_hist: str      # For historical data ("TRADES", "MIDPOINT", etc.)
    what_to_show_live: str      # For live streaming ("TRADES", "MIDPOINT", etc.)
    generic_tick_list: tuple[str, ...]  # Additional tick types to request

config = get_asset_config("STK")  # Returns AssetTypeConfig for stocks
config.what_to_show_hist  # "TRADES"
config.what_to_show_live  # "TRADES"
config.generic_tick_list_str  # "165,225,232,233,236,..."
```

**Supported Asset Types:**
| secType | what_to_show | Notes |
|---------|--------------|-------|
| STK | TRADES | Stocks - full support |
| OPT | TRADES | Options - includes Greeks ticks |
| FUT | TRADES | Futures |
| CRYPTO | AGGTRADES | Crypto - aggregated trades |
| CASH | MIDPOINT | Forex - no TRADES support |
| IND | TRADES | Index |
| BOND | TRADES | Bonds - includes bond factor |

---

## 4. DatafeedCapability Interface

```python
class DatafeedCapability(Protocol):
    # One-shot requests (return data)
    async def search_symbols(self, pattern: str, **kwargs) -> list[SearchSymbolResultItem]
    async def get_symbol_info(self, ticker_name: str, **kwargs) -> SymbolInfo
    async def get_historical_bars(self, ticker_name: str, start_time: datetime, end_time: datetime,
                                   resolution: Resolution, **kwargs) -> list[Bar]
    async def get_quotes_snapshot(self, ticker_names: list[str], **kwargs) -> list[QuoteData]

    # Subscription methods (return stream keys)
    def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs,
    ) -> str

    def subscribe_market_data(
        self,
        ticker_names: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs,
    ) -> list[str]

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None
    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None
```

**Interface Tags:**

- `[CONTINUOUS]`: Callback invoked continuously until unsubscribe
- `[THREAD-SAFE]`: Callback may be invoked from provider thread
- `[ERROR-HANDLING]`: If `on_error` is provided, transient errors call it instead of raising

**Key Changes from Previous Version:**

- `ticker` → `ticker_name` parameter rename for consistency
- `tickers` → `ticker_names` parameter rename
- Added `on_error` callback for subscription-level error notifications

---

## 4.1 BrokerCapability Interface

```python
class BrokerCapability(Protocol):
    # Order Management (async)
    async def place_order(self, order: PreOrder) -> PlaceOrderResult
    async def modify_order(self, order_id: str, order: PreOrder) -> None
    async def cancel_order(self, order_id: str) -> None
    async def get_orders(self) -> list[PlacedOrder]
    async def preview_order(self, order: PreOrder) -> OrderPreviewResult

    # Position Management (async)
    async def get_positions(self) -> list[Position]
    async def close_position(self, position_id: str, amount: float | None = None) -> None
    async def edit_position_brackets(self, position_id: str, brackets: Brackets) -> None

    # Account Data (async)
    async def get_account_info(self) -> AccountMetainfo
    async def get_equity(self) -> EquityData
    async def get_executions(self, symbol: str) -> list[Execution]

    # Leverage (NOT SUPPORTED by TWS - raises ProviderException)
    async def preview_leverage(self, params: LeverageSetParams) -> LeveragePreviewResult
    async def get_leverage_info(self, params: LeverageInfoParams) -> LeverageInfo
    async def set_leverage(self, params: LeverageSetParams) -> LeverageSetResult

    # Streaming Subscriptions (return subscription IDs)
    def subscribe_orders(
        self,
        callback: Callable[[PlacedOrder], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str

    def subscribe_positions(
        self,
        callback: Callable[[Position], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str

    def subscribe_executions(
        self,
        symbol: str,
        callback: Callable[[Execution], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str

    def subscribe_equity(
        self,
        callback: Callable[[EquityData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str

    def unsubscribe(self, subscription_id: str) -> None
```

**TWS-Specific Notes:**

- **Leverage Methods**: IBKR uses account-level margin, not per-symbol leverage. These methods raise `ProviderException` with code `PROVIDER_BROKER_LEVERAGE_NOT_SUPPORTED`.
- **Order Preview**: Returns estimated values since TWS doesn't have native preview API.
- **Bracket Orders**: `edit_position_brackets()` not yet implemented (complex linked orders).
- **Equity Streaming**: TWS doesn't push account changes; polling via `get_equity()` is required.
- **Client ID**: Broker uses `client_id=2` (default), separate from datafeed's `client_id=1`.

**Configuration:**

| Env Variable            | Type | Default     | Description                        |
| ----------------------- | ---- | ----------- | ---------------------------------- |
| `TWS_BROKER_ENABLED`    | bool | `True`      | Enable broker provider             |
| `TWS_BROKER_HOST`       | str  | `127.0.0.1` | Gateway host                       |
| `TWS_BROKER_PORT`       | int  | `7497`      | Gateway port                       |
| `TWS_BROKER_CLIENT_ID`  | int  | `2`         | Client ID (separate from datafeed) |
| `TWS_BROKER_ACCOUNT_ID` | str  | `""`        | Account ID for orders              |

---

## 5. Domain Models

**File:** `models/market.py` — Used by Service and Provider

| Model                    | Key Fields                                          | Purpose         |
| ------------------------ | --------------------------------------------------- | --------------- |
| `Bar`                    | `time`, `open`, `high`, `low`, `close`, `volume`    | OHLCV data      |
| `SearchSymbolResultItem` | `symbol`, `exchange`, `type`, `ticker`              | Search results  |
| `SymbolInfo`             | `name`, `type`, `session`, `timezone`, `pricescale` | Symbol metadata |
| `QuoteData`              | `n`, `s`, `v` (QuoteValues embedded)                | Tick data       |
| `Resolution`             | `MIN_1`, `MIN_5`, `HOUR_1`, `DAY_1`, etc.           | Resolution enum |

**File:** `models/broker/` — Broker domain models

| Model             | Key Fields                                        | Purpose          |
| ----------------- | ------------------------------------------------- | ---------------- |
| `PreOrder`        | `symbol`, `side`, `type`, `qty`, `limitPrice`     | Order request    |
| `PlacedOrder`     | `id`, `symbol`, `status`, `filledQty`, `avgPrice` | Order status     |
| `Position`        | `id`, `symbol`, `qty`, `side`, `avgPrice`         | Open position    |
| `EquityData`      | `equity`, `balance`, `unrealizedPL`, `realizedPL` | Account equity   |
| `AccountMetainfo` | `id`, `name`                                      | Account metadata |
| `Execution`       | `id`, `symbol`, `qty`, `price`, `time`            | Trade execution  |

**TWS Types** (used ONLY in TWSDatafeedProvider/TWSClient/TWSBrokerProvider):

- `Contract`, `ContractDetails`, `ContractDescription` — from `ibapi.contract`
- `BarData` — from `ibapi.common`
- `Order`, `OrderState` — from `ibapi.order`, `ibapi.order_state`

---

## 6. Domain Mappers

**File:** `tws_mappers.py`

### Datafeed Mappers

| Function                                  | Description                                      |
| ----------------------------------------- | ------------------------------------------------ |
| `contract_description_to_search_result()` | `ContractDescription` → `SearchSymbolResultItem` |
| `contract_details_to_symbol_info()`       | `ContractDetails` → `SymbolInfo`                 |
| `tws_bar_to_domain_bar()`                 | `BarData` → `Bar` (historical)                   |
| `tws_ticks_to_bar()`                      | `dict[str, Any]` → `Bar` (real-time)             |
| `tws_ticks_to_quote_data()`               | `dict[str, Any]` → `QuoteData`                   |
| `ticker_name()`                           | `Contract` → stream key string                   |
| `parse_ticker()`                          | stream key → (symbol, exchange, secType, conId)  |
| `build_contract()`                        | ticker string → `Contract`                       |
| `map_resolution_to_tws_bar_size()`        | `Resolution` → TWS bar size string               |

### Broker Mappers

| Function                                | Description                            |
| --------------------------------------- | -------------------------------------- |
| `preorder_to_tws()`                     | `PreOrder` → `(Contract, Order)` tuple |
| `tws_order_to_placed_order()`           | order data dict → `PlacedOrder`        |
| `tws_position_to_domain()`              | position data dict → `Position`        |
| `tws_account_summary_to_equity()`       | summary dict → `EquityData`            |
| `tws_account_summary_to_account_info()` | summary dict → `AccountMetainfo`       |
| `calculate_tws_duration()`              | time range → TWS duration string       |

**secType Mapping:**

```python
SEC_TYPE_MAP = {"STK": "stock", "OPT": "option", "FUT": "futures",
                "CASH": "forex", "IND": "index", "CRYPTO": "crypto", ...}
```

---

## 7. Ticker Slot Pattern (Real-time Data)

**Replaces the old `TwsRTData` dataclass.**

Ticker slots are `dict[str, Any]` managed by IBSocket:

```python
# IBSocket internal state
_reader_tickers: dict[int, dict[str, Any]] = {}   # reqId → ticker data
_reader_streams: dict[int, tuple[loop, callback]] = {}  # reqId → notification callback
_active_streams: dict[str, int] = {}  # stream_key → reqId (for duplicate detection)

# Ticker slot structure (example)
ticker_slot = {
    "ticker_name": "AAPL:NASDAQ:STK-12345",
    # Price fields
    "bid": 150.25,
    "ask": 150.30,
    "last": 150.27,
    # Bar fields (for historicalDataUpdate)
    "bar_date": "20251207 10:30:00",
    "bar_open": 150.00,
    "bar_high": 150.50,
    "bar_low": 149.90,
    "bar_close": 150.27,
    "bar_volume": 1000,
    # Metadata
    "market_data_type": 1,
    "min_tick": 0.01,
    # Error tracking (set by _handle_request_error)
    "last_exception": None,  # ProviderException | None
}
```

**Field Mapping:** `TICK_TYPE_TO_FIELD` in `tws_models.py` maps TWS tick types to slot fields:

```python
TICK_TYPE_TO_FIELD = {
    "BID": "bid",
    "ASK": "ask",
    "LAST": "last",
    "VOLUME": "volume",
    ...
}
```

**Notification Pattern:**

```python
# In IBSocket callback (daemon thread)
def tickPrice(self, reqId: int, tickType: int, price: float, attrib) -> None:
    ticker = self._reader_tickers.get(reqId)
    if ticker is None:
        return

    field_name = TICK_TYPE_TO_FIELD.get(get_tick_type_name(tickType))
    current_value = ticker.get(field_name)

    # Only notify on actual change
    if current_value is None or not math.isclose(current_value, price, abs_tol=1e-3):
        ticker[field_name] = price
        self._notify_stream(reqId, [field_name])  # Notifies main thread
```

---

## 8. Configuration

**File:** `models/providers/tws/tws_configs.py` — Pydantic BaseSettings with `TWS_` prefix

| Env Variable             | Type  | Default     | Description            |
| ------------------------ | ----- | ----------- | ---------------------- |
| `TWS_ENABLED`            | bool  | `True`      | Enable provider        |
| `TWS_HOST`               | str   | `127.0.0.1` | Gateway host           |
| `TWS_PORT`               | int   | `7497`      | Gateway port           |
| `TWS_CLIENT_ID`          | int   | `1`         | Client ID (1-32)       |
| `TWS_CONNECTION_TIMEOUT` | float | `10.0`      | Connect timeout (sec)  |
| `TWS_MARKET_DATA_TYPE`   | int   | `1`         | 1=real-time, 3=delayed |

**Port Reference:**
| Port | Environment | App |
|------|-------------|-----|
| 7497 | Paper | TWS |
| 7496 | Live | TWS |
| 4002 | Paper | IB Gateway |
| 4001 | Live | IB Gateway |

---

## 9. Implementation Patterns

### One-Shot Request (Future-based)

Used by: `search_symbols()`, `get_historical_bars()`, `get_quotes_snapshot()`

```python
# TWSClient
async def reqMatchingSymbols(self, pattern: str) -> list[ContractDescription]:
    reqId = self.next_req_id
    coroutine = self.ibsocket.create_future(
        reqId, timeout=self._timeout, capability="shared"  # capability for error routing
    )
    self.ibsocket.send_message(OUT.REQ_MATCHING_SYMBOLS, [reqId, pattern])
    return await coroutine

# IBSocket (daemon thread) - decorated with @error_handler
@error_handler(capability="shared")
def symbolSamples(self, reqId: int, contractDescriptions: list) -> None:
    accumulator = self._reader_accumulators.get(reqId)
    if isinstance(accumulator, list):
        accumulator.extend(contractDescriptions)
        self._resolve_future(reqId)  # Resolves Future with accumulated data
```

### Streaming Subscription (Ticker Slot + Callback)

Used by: `subscribe_realtime_bars()`, `subscribe_market_data()`

```python
# TWSClient
def reqBarDataStream(self, contract: Contract, bar_size: str, callback) -> str:
    stream_key = ticker_name(contract, bar_size)

    # Check existing subscription via IBSocket registry
    existing_req_id = self.ibsocket.stream_req_id(stream_key)
    if existing_req_id is not None:
        # Reuse existing stream, update callback
        self.ibsocket.update_stream(existing_req_id, callback)
        return stream_key

    reqId = self.next_req_id
    self.ibsocket.register_stream(reqId, stream_key, callback)  # Registers reqId ↔ stream_key

    # Send REQ_HISTORICAL_DATA with keepUpToDate=1
    self.ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, [..., keepUpToDate=1, ...])
    return stream_key

# TWSDatafeedProvider
def subscribe_realtime_bars(self, ticker: str, resolution: Resolution, callback) -> str:
    bar_size = map_resolution_to_tws_bar_size(resolution)

    async def bar_callback(rt_data: dict, fields: list[str] | None) -> None:
        if fields is None or any(f.startswith("bar_") for f in fields):
            await callback(tws_ticks_to_bar(rt_data))

    contract = build_contract(ticker)
    return self._tws_client.reqBarDataStream(contract, bar_size, bar_callback)
```

### Cancellation

```python
# TWSClient
def cancelBarDataStream(self, stream_key: str) -> None:
    reqId = self.ibsocket._pop_stream_req_id(stream_key)  # Removes from _active_streams
    if reqId is not None:
        self.ibsocket.send_message(OUT.CANCEL_HISTORICAL_DATA, [1, reqId])
        self.ibsocket.unregister_stream(reqId)
```

---

## 10. Thread Safety Rules

### ✅ DO

- Use `threading.Lock` for socket writes (`IBSocket.send_message`)
- Use `loop.call_soon_threadsafe()` for cross-thread callback dispatch
- Use `threading.Event` for ready signaling (not `asyncio.Event`)
- Update ticker slots in daemon thread, notify via `call_soon_threadsafe`
- Keep domain conversion in main thread (mappers called from callbacks)

### ❌ DON'T

- Never await/async in EWrapper callbacks (daemon thread)
- Never share mutable state between threads without sync
- Never use `asyncio.Event.set()` from daemon thread
- Never call mappers directly in daemon thread

---

## 11. Error Handling

TWS errors are converted to `ProviderException` and routed through centralized error handling.

> **Full Reference:** See [ERROR-MANAGEMENT.md](../../../docs/ERROR-MANAGEMENT.md) for complete exception hierarchy.

### Error Source Categories

`TWSErrorCategory` in `tws_connection.py` defines error code prefixes by source:

| Category   | Code Prefix               | Description                              |
| ---------- | ------------------------- | ---------------------------------------- |
| `CONN`     | `PROVIDER_TWS_CONN_*`     | Socket/connection errors                 |
| `API`      | `PROVIDER_TWS_API_*`      | TWS API errors (from `error()` callback) |
| `CALLBACK` | `PROVIDER_TWS_CALLBACK_*` | Callback processing errors               |

### TWS Error Classification

`classify_error()` in `tws_models.py` classifies TWS error codes by meaning and recoverability:

```python
from tws_models import classify_error, TWSErrorClassification

category, is_recoverable = classify_error(error_code)
# Returns: (TWSErrorClassification.*, bool)
```

**Classification Categories:**

| Category       | Example Codes  | Recoverable | Description                        |
| -------------- | -------------- | ----------- | ---------------------------------- |
| `INFO`         | 2104, 2106     | ✓           | Status notifications (not errors)  |
| `CONNECTION`   | 502, 504, 1100 | ✓           | Connection state changes           |
| `PACING`       | 100, 420       | ✓           | Rate limiting (throttle and retry) |
| `DUPLICATE`    | 102, 103, 326  | ✓           | ID conflicts (use different ID)    |
| `SUBSCRIPTION` | 354, 10090     | ✗           | Market data permission issues      |
| `VALIDATION`   | 200, 201, 203  | ✗           | Invalid request/contract           |
| `FATAL`        | 503, 505-509   | ✗           | Protocol/system errors             |
| `WARNING`      | 2xxx range     | ✓           | Non-critical warnings              |
| `SYSTEM`       | 1xxx range     | ✓           | System state messages              |
| `ERROR`        | (default)      | ✗           | Unclassified errors                |

**Non-Recoverable Error Convention:**

Error details ending with `_NON_RECOVERABLE` trigger cleanup of associated data structures:

```python
# In _handle_request_error():
detail = f"{category}_{code}" if recoverable else f"{category}_{code}_NON_RECOVERABLE"
# Example: "VALIDATION_200_NON_RECOVERABLE"
```

### Stream Error Callbacks

Subscription methods accept optional `on_error` callback for streaming errors:

```python
def subscribe_realtime_bars(
    self,
    ticker_name: str,
    resolution: Resolution,
    callback: Callable[[Bar], Awaitable[None]],
    on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,  # NEW
    **kwargs: Any,
) -> str:
    ...
```

**Error Flow:**

```
TWS error() callback
        │
classify_error(code)  →  (category, is_recoverable)
        │
_handle_request_error()
        │
        ├─► Future exists → reject with ProviderException
        │
        └─► Stream exists + on_error → invoke on_error callback
                │
                └─► Non-recoverable → cleanup _stream_data, _stream_hooks
```

### Error Handler Decorator

All IBSocket callbacks use `@error_handler(capability)` to catch exceptions:

```python
@error_handler(capability="datafeed")
def tickPrice(self, reqId: int, tickType: int, price: float, attrib) -> None:
    # Exceptions auto-wrapped as ProviderException
    # Routes to _handle_request_error() on failure
    ...
```

### Centralized Error Routing

`_handle_request_error()` routes errors based on request state:

```python
def _handle_request_error(self, category, detail, reqId, message, ...):
    # Determine recoverability from detail suffix
    is_non_recoverable = detail.endswith("_NON_RECOVERABLE")

    error = ProviderException(
        code=f"PROVIDER_TWS_{category}_{detail.upper()}",
        message=f"[reqId={reqId}] {message}",
        provider="tws",
        capability=self._reqId_to_capability.pop(reqId, capability_fallback),
    )

    # 1. Future exists → reject future with error
    # 2. Stream exists + on_error → invoke error callback via call_soon_threadsafe
    # 3. Neither → log as orphan error
    # 4. Non-recoverable → cleanup via call_soon_threadsafe (safe from daemon thread)
```

**Thread-Safe Cleanup:** Non-recoverable errors trigger cleanup via `loop.call_soon_threadsafe()`
to safely remove stream entries from the daemon thread:

```python
# Daemon thread schedules cleanup in event loop
self._loop.call_soon_threadsafe(self._pop_stream_req_id, stream_key)
```

### Capability Tracking

Request IDs are mapped to capabilities for proper error routing:

```python
# On create_future() or register_stream()
self._reqId_to_capability[reqId] = capability  # "datafeed", "broker", "shared"

# On resolve/reject/unregister (or non-recoverable error)
self._reqId_to_capability.pop(reqId, None)
```

### Common TWS Error Codes

| Code      | Category     | Recoverable | Meaning                              |
| --------- | ------------ | ----------- | ------------------------------------ |
| 100       | PACING       | ✓           | Max rate exceeded (50/sec)           |
| 162       | PACING       | ✓           | Historical data pacing               |
| 200       | VALIDATION   | ✗           | No security definition found         |
| 354       | SUBSCRIPTION | ✗           | Not subscribed to market data        |
| 502       | CONNECTION   | ✓           | Couldn't connect to TWS              |
| 504       | CONNECTION   | ✓           | Not connected                        |
| 1100      | CONNECTION   | ✓           | Connectivity lost                    |
| 2104/2106 | INFO         | ✓           | Farm connected (status notification) |

---

## 12. Testing

### Test Strategy

| Layer               | Mock                  | Focus                              |
| ------------------- | --------------------- | ---------------------------------- |
| TWSDatafeedProvider | `AsyncMock` TWSClient | Domain conversion, stream keys     |
| TWSClient           | Mock `IBSocket`       | Stream management, lazy connection |
| Integration         | Mock TWS Gateway      | End-to-end flow                    |

### Mock Pattern for Async Methods

```python
# For async methods like reqQuoteSnapshot
mock_client = AsyncMock()
mock_client.reqQuoteSnapshot.return_value = {"ticker_name": "AAPL:NASDAQ:STK-12345"}

# For sync methods that return stream keys
mock_client = Mock()
mock_client.reqBarDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345@5 mins")

# Mock IBSocket for TWSClient tests
mock_ibsocket = Mock()
mock_ibsocket.stream_req_id = Mock(return_value=None)  # No existing subscription
mock_ibsocket._pop_stream_req_id = Mock(return_value=123)  # Return reqId for cleanup
```

### Run Tests

```bash
cd backend
poetry run pytest src/trading_api/providers/tws/tests/ -v
```

---

## 13. Installation

**Requirements:** Python 3.11+, protobuf 5.29.3

```bash
cd backend
poetry add ./external_packages/tws/source/pythonclient
poetry add protobuf==5.29.3
make validate-tws
```

**Type Stubs:** `.pyi` files in `external_packages/tws/source/pythonclient/ibapi/` provide Pylance/Pyright support.

---

## Cross-References

| Topic                | Document                                       |
| -------------------- | ---------------------------------------------- |
| Provider System      | `backend/docs/PROVIDER-SYSTEM.md`              |
| Error Management     | `backend/docs/ERROR-MANAGEMENT.md`             |
| TWS API Reference    | `backend/external_packages/tws/docs/README.md` |
| DatafeedService      | `modules/datafeed/service.py`                  |
| Backend Testing      | `backend/docs/BACKEND_TESTING.md`              |
| Modular Architecture | `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md` |
