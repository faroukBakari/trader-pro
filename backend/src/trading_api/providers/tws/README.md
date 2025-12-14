# TWS Datafeed Provider

**Status:** Production-Ready (Core Capabilities)  
**Architecture:** Three-Layer Streaming Pattern  
**Last Updated:** December 14, 2025

---

## Quick Reference

| Layer               | File                                  | Responsibility                                    |
| ------------------- | ------------------------------------- | ------------------------------------------------- |
| **3 - TWSProvider** | `__init__.py`                         | DatafeedCapability impl, domain conversion        |
| **2 - TWSClient**   | `tws_connection.py`                   | AsyncIO facade, stream management, owns IBSocket  |
| **1 - IBSocket**    | `tws_connection.py`                   | Raw TCP, daemon thread, ticker slot registry      |
| **Mappers**         | `tws_mappers.py`                      | TWS ↔ domain model conversion, ticker parsing     |
| **Models**          | `tws_models.py`                       | `TWSCapability`, `AssetConfig`, tick/msg mappings |
| **Config**          | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic settings               |

**Tests:** `providers/tws/tests/test_{client,mappers,provider}.py`

---

## 1. Architecture

### System Flow

```
DatafeedService (provider-agnostic)
        │ requires capability="datafeed"
        ▼
TWSProvider (Layer 3) ─── implements DatafeedCapability
        │ domain ↔ TWS conversion, stream key management
        ▼
TWSClient (Layer 2) ─── owns IBSocket, manages _active_streams
        │ asyncio.Future + ticker slot registry
        ▼
IBSocket (Layer 1) ─── daemon thread _reader_loop()
        │ _reader_tickers (slot registry), _reader_streams (callbacks)
        ▼
TWS/IB Gateway (localhost:7497)
```

### Threading Model

```
Main Thread (AsyncIO)                    Daemon Thread
─────────────────────                    ─────────────
TWSProvider.subscribe_market_data()      IBSocket._reader_loop()
        │                                        │
TWSClient.reqMktDataStream()             Decoder.interpret()
        │                                        │
register_stream(reqId, callback)         tickPrice(reqId, price)
        │                                        │
        │                                _reader_tickers[reqId]["bid"] = price
        │                                        │
callback(data) ◄──────────────────────── _notify_stream(reqId, ["bid"])
                                                 │
                    loop.call_soon_threadsafe(callback, ticker_data, fields)
```

**Key Patterns:**

- **Lazy Connection**: `TWSClient.ibsocket` connects on first access
- **Future Bridge**: `asyncio.Future` + `call_soon_threadsafe()` for one-shot requests
- **Ticker Slots**: `_reader_tickers[reqId]` dict accumulates real-time data
- **Stream Registry**: `_reader_streams[reqId]` holds (loop, callback) for continuous updates
- **Stream Keys**: `"AAPL:NASDAQ:STK-12345@5 mins"` identifies unique subscriptions

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
    async def get_symbol_info(self, ticker: str, **kwargs) -> SymbolInfo
    async def get_historical_bars(self, ticker: str, start_time: datetime, end_time: datetime,
                                   resolution: Resolution, **kwargs) -> list[Bar]
    async def get_quotes_snapshot(self, tickers: list[str], **kwargs) -> list[QuoteData]

    # Subscription methods (return stream keys)
    def subscribe_realtime_bars(self, ticker: str, resolution: Resolution,
                                 callback: Callable[[Bar], Awaitable[None]], **kwargs) -> str
    def subscribe_market_data(self, tickers: list[str],
                               callback: Callable[[QuoteData], Awaitable[None]], **kwargs) -> list[str]
    def unsubscribe_realtime_bars(self, subscription_id: str) -> None
    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None
```

**Key Changes from Previous Version:**

- `ticker` parameter replaces `symbol` + `exchange`
- `Resolution` enum replaces `TimeFrame`
- Subscription IDs are `str` (stream keys) not `int` (reqIds)

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

**TWS Types** (used ONLY in TWSProvider/TWSClient):

- `Contract`, `ContractDetails`, `ContractDescription` — from `ibapi.contract`
- `BarData` — from `ibapi.common`

---

## 6. Domain Mappers

**File:** `tws_mappers.py`

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
| `calculate_tws_duration()`                | time range → TWS duration string                 |

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

    if stream_key in self._active_streams:
        # Reuse existing stream, update callback
        self.ibsocket.update_stream(self._active_streams[stream_key], callback)
        return stream_key

    reqId = self.next_req_id
    self._active_streams[stream_key] = reqId
    self.ibsocket.register_stream(reqId, ticker_name(contract, bar_size), callback)

    # Send REQ_HISTORICAL_DATA with keepUpToDate=1
    self.ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, [..., keepUpToDate=1, ...])
    return stream_key

# TWSProvider
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
    reqId = self._active_streams.pop(stream_key, None)
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

### Error Categories

`TWSErrorCategory` in `tws_connection.py` defines error code prefixes:

| Category   | Code Prefix               | Description                              |
| ---------- | ------------------------- | ---------------------------------------- |
| `CONN`     | `PROVIDER_TWS_CONN_*`     | Socket/connection errors                 |
| `API`      | `PROVIDER_TWS_API_*`      | TWS API errors (from `error()` callback) |
| `CALLBACK` | `PROVIDER_TWS_CALLBACK_*` | Callback processing errors               |

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
    error = ProviderException(
        code=f"PROVIDER_TWS_{category}_{detail}",
        message=f"[reqId={reqId}] {message}",
        provider="tws",
        capability=self._reqId_to_capability.get(reqId, "shared"),
    )

    # 1. Ticker stream exists → store in last_exception + notify
    # 2. Future exists → reject future with error
    # 3. Neither → log as orphan error
```

### Capability Tracking

Request IDs are mapped to capabilities for proper error routing:

```python
# On create_future() or register_stream()
self._reqId_to_capability[reqId] = capability  # "datafeed", "broker", "shared"

# On resolve/reject/unregister
self._reqId_to_capability.pop(reqId, None)
```

### Common TWS Error Codes

| Code      | Meaning                | Mapped Exception Code            |
| --------- | ---------------------- | -------------------------------- |
| 162       | Historical data pacing | `PROVIDER_TWS_API_TWS_CODE_162`  |
| 200       | No security found      | `PROVIDER_TWS_API_TWS_CODE_200`  |
| 354       | Not subscribed         | `PROVIDER_TWS_API_TWS_CODE_354`  |
| 504       | Not connected          | `PROVIDER_TWS_API_TWS_CODE_504`  |
| 2104/2106 | Farm connected         | Logged as warning (system error) |

---

## 12. Testing

### Test Strategy

| Layer       | Mock                  | Focus                              |
| ----------- | --------------------- | ---------------------------------- |
| TWSProvider | `AsyncMock` TWSClient | Domain conversion, stream keys     |
| TWSClient   | Mock `IBSocket`       | Stream management, lazy connection |
| Integration | Mock TWS Gateway      | End-to-end flow                    |

### Mock Pattern for Async Methods

```python
# For async methods like reqQuoteSnapshot
mock_client = AsyncMock()
mock_client.reqQuoteSnapshot.return_value = {"ticker_name": "AAPL:NASDAQ:STK-12345"}

# For sync methods that return stream keys
mock_client = Mock()
mock_client.reqBarDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345@5 mins")
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
