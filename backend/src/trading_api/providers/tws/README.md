# TWS Datafeed Provider

**Status:** Production-Ready (Core Capabilities)  
**Architecture:** Three-Layer Composition Pattern  
**Last Updated:** November 30, 2025

---

## Quick Reference

| Layer               | File                                  | Responsibility                               |
| ------------------- | ------------------------------------- | -------------------------------------------- |
| **3 - TWSProvider** | `__init__.py`                         | DatafeedCapability impl, domain conversion   |
| **2 - TWSClient**   | `tws_connection.py`                   | AsyncIO facade, owns TWSCallback + IBSocket  |
| **2 - TWSCallback** | `tws_connection.py`                   | EWrapper callbacks, Future/callback registry |
| **1 - IBSocket**    | `tws_connection.py`                   | Raw TCP, daemon thread reader loop           |
| **Mappers**         | `tws_mappers.py`                      | TWS ↔ domain model conversion                |
| **RT Data**         | `tws_rt_data.py`                      | `TwsRTData` dataclass for tick accumulation  |
| **Config**          | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic settings          |

**Tests:** `providers/tws/tests/test_{callback,client,config,mappers,provider}.py`

---

## 1. Architecture

### System Flow

```
DatafeedService (provider-agnostic)
        │ requires capability="datafeed"
        ▼
TWSProvider (Layer 3) ─── implements DatafeedCapability
        │ domain ↔ TWS conversion
        ▼
TWSClient (Layer 2) ─── owns TWSCallback (EWrapper)
        │ asyncio.Future + loop.call_soon_threadsafe()
        ▼
IBSocket (Layer 1) ─── daemon thread _reader_loop()
        │ TCP socket
        ▼
TWS/IB Gateway (localhost:7497)
```

### Threading Model

```
Main Thread (AsyncIO)              Daemon Thread
─────────────────────              ─────────────
TWSProvider.search_symbols()       IBSocket._reader_loop()
        │                                  │
TWSClient.reqMatchingSymbols()     Decoder.interpret()
        │                                  │
await future ◄──────────────────── TWSCallback.symbolSamples()
                                           │
              loop.call_soon_threadsafe(future.set_result, data)
```

**Key Patterns:**

- **Lazy Connection**: `TWSClient.ibsocket` connects on first access
- **Future Bridge**: `asyncio.Future` + `call_soon_threadsafe()` for thread-safe resolution
- **Accumulator**: Streaming data collected before Future resolution
- **Composition**: TWSClient owns TWSCallback (no EWrapper inheritance)

---

## 2. DatafeedCapability Interface

```python
class DatafeedCapability(Protocol):
    async def search_symbols(self, pattern: str, **kwargs) -> list[SearchSymbolResultItem]
    async def get_symbol_info(self, symbol: str, exchange: str | None = None, **kwargs) -> SymbolInfo
    async def get_historical_bars(self, symbol: str, start_time: datetime, end_time: datetime,
                                   resolution: TimeFrame, exchange: str | None = None, **kwargs) -> list[Bar]
    async def get_quotes_snapshot(self, symbols: list[str], exchange: str | None = None, **kwargs) -> list[QuoteData]

    # Subscription methods (real-time streaming)
    def subscribe_realtime_bars(self, symbol: str, callback: Callable[[Bar], Awaitable[None]],
                                 exchange: str | None = None, **kwargs) -> int
    def subscribe_market_data(self, symbols: list[str], callback: Callable[[QuoteData], Awaitable[None]],
                               exchange: str | None = None, **kwargs) -> list[int]
    def unsubscribe_realtime_bars(self, subscription_id: int) -> None
    def unsubscribe_market_data(self, subscription_ids: list[int]) -> None
```

---

## 3. Domain Models

**File:** `models/market.py` — Used by Service and Provider

| Model                    | Key Fields                                            | Purpose         |
| ------------------------ | ----------------------------------------------------- | --------------- |
| `Bar`                    | `time`, `open`, `high`, `low`, `close`, `volume`      | OHLCV data      |
| `SearchSymbolResultItem` | `symbol`, `exchange`, `type`, `ticker`                | Search results  |
| `SymbolInfo`             | `name`, `type`, `session`, `timezone`, `pricescale`   | Symbol metadata |
| `QuoteData`              | `symbol`, `bid`, `ask`, `last`, `volume`, `timestamp` | Tick data       |
| `TimeFrame`              | `SEC_5`, `MIN_1`, `HOUR_1`, `DAY_1`, etc.             | Resolution enum |

**TWS Types** (used ONLY in TWSProvider):

- `Contract`, `ContractDetails`, `ContractDescription` — from `ibapi.contract`
- `BarData` — from `ibapi.common`

---

## 4. Domain Mappers

**File:** `tws_mappers.py`

| Function                                  | TWS → Domain                                     |
| ----------------------------------------- | ------------------------------------------------ |
| `contract_description_to_search_result()` | `ContractDescription` → `SearchSymbolResultItem` |
| `contract_details_to_symbol_info()`       | `ContractDetails` → `SymbolInfo`                 |
| `tws_bar_to_domain_bar()`                 | `BarData` → `Bar`                                |
| `tws_rt_bar_to_domain_bar()`              | Real-time bar params → `Bar`                     |
| `tws_ticks_to_quote_data()`               | `TwsRTData` → `QuoteData`                        |

**secType Mapping:**

```python
SEC_TYPE_MAP = {"STK": "stock", "OPT": "option", "FUT": "futures",
                "CASH": "forex", "IND": "index", "CRYPTO": "crypto", ...}
```

### TwsRTData (Real-time Data Accumulator)

**File:** `tws_rt_data.py`

Dataclass for accumulating tick data from multiple TWS callbacks:

```python
@dataclass
class TwsRTData:
    # Price ticks
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None

    # Size ticks
    bid_size: int | None = None
    ask_size: int | None = None
    last_size: int | None = None
    volume: int | None = None

    # Real-time bar fields
    bar_time: int | None = None
    bar_open: float | None = None
    bar_high: float | None = None
    bar_low: float | None = None
    bar_close: float | None = None
    bar_volume: int | None = None

    # Exchange info
    min_tick: float | None = None
    bbo_exchange: str | None = None
    market_data_type: int | None = None

    # Extended data (unknown tick types)
    extended: dict[str, Any] = field(default_factory=dict)
```

---

## 5. Configuration

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

## 6. Implementation Patterns

### Request/Response (Single Callback)

Used by: `search_symbols()` — complete data in one callback

```python
# TWSClient
async def reqMatchingSymbols(self, pattern: str) -> list[ContractDescription]:
    req_id = self._get_next_req_id()
    future = self._cb_wrapper.create_future_coroutine(req_id)
    self.ibsocket.send_message(REQ_MATCHING_SYMBOLS, [req_id, pattern])
    return await future

# TWSCallback
def symbolSamples(self, reqId: int, contractDescriptions: list) -> None:
    self._resolve_future(reqId, contractDescriptions)  # Single resolution
```

### Accumulator (Multiple Callbacks)

Used by: `get_historical_bars()` — streaming data collected before resolution

```python
# TWSClient
async def reqHistoricalData(self, ...) -> list[BarData]:
    req_id = self._get_next_req_id()
    self._cb_wrapper.init_accumulator(req_id)  # Initialize accumulator
    future = self._cb_wrapper.create_future_coroutine(req_id)
    self.ibsocket.send_message(REQ_HISTORICAL_DATA, [...])
    return await future

# TWSCallback
def historicalData(self, reqId: int, bar: BarData) -> None:
    self._accumulators[reqId].append(bar)  # Accumulate

def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
    bars = self._accumulators.pop(reqId, [])
    self._resolve_future(reqId, bars)  # Resolve with all bars
```

### Subscription (Continuous)

Used by: `subscribe_realtime_bars()`, `subscribe_market_data()` — real-time streaming

```python
# TWSProvider
def subscribe_realtime_bars(self, symbol: str, callback: Callable[[Bar], Awaitable[None]], ...) -> int:
    contract = self._build_contract(symbol)

    async def mapped_callback(*args):
        await callback(tws_rt_bar_to_domain_bar(*args))

    return self._tws_client.reqRealTimeBars(contract, mapped_callback)

# TWSClient
def reqRealTimeBars(self, contract: Contract, callback: Callable[[TwsRTData], Awaitable[None]], ...) -> int:
    reqId = self.next_req_id
    self._cb_wrapper.register_callback(reqId, callback)
    self.ibsocket.send_message(OUT.REQ_REAL_TIME_BARS, [...])
    return reqId  # Return for unsubscribe

# TWSCallback
def realtimeBar(self, reqId: int, time: int, open_: float, high: float, low: float,
                close: float, volume: Decimal, wap: Decimal, count: int) -> None:
    rt_data = self._get_rt_data(reqId)
    rt_data.bar_time = time
    rt_data.bar_open = open_
    # ... populate other fields
    self._notify_callback(reqId, rt_data)  # Calls registered async callback
```

---

## 7. Thread Safety Rules

### ✅ DO

- Use `threading.Lock` for socket writes (`IBSocket.send_message`)
- Use `loop.call_soon_threadsafe()` for cross-thread Future resolution
- Use `threading.Event` for ready signaling (not `asyncio.Event`)
- Keep domain conversion in main thread

### ❌ DON'T

- Never await/async in EWrapper callbacks (daemon thread)
- Never share mutable state between threads without sync
- Never use `asyncio.Event.set()` from daemon thread

---

## 8. Error Handling

**TWSError Dataclass:**

```python
@dataclass
class TWSError:
    req_id: int
    error_code: int
    error_string: str
    is_warning: bool  # 2100-2199 are warnings
```

**Common Error Codes:**
| Code | Meaning | Action |
|------|---------|--------|
| 162 | Historical data pacing | Wait and retry |
| 200 | No security found | Invalid symbol |
| 354 | Not subscribed | Missing market data subscription |
| 504 | Not connected | Reconnect |
| 2104/2106 | Farm connected | Informational (warning) |

---

## 9. Testing

### Test Strategy

| Layer       | Mock             | Focus                           |
| ----------- | ---------------- | ------------------------------- |
| TWSProvider | Mock `TWSClient` | Domain conversion               |
| TWSClient   | Mock `IBSocket`  | Lazy connection, delegation     |
| TWSCallback | Mock loop        | Future resolution, accumulators |
| Integration | Mock TWS Gateway | End-to-end flow                 |

### Run Tests

```bash
cd backend
poetry run pytest src/trading_api/providers/tws/tests/ -v
```

---

## 10. Installation

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
| TWS API Reference    | `backend/external_packages/tws/docs/README.md` |
| DatafeedService      | `modules/datafeed/service.py`                  |
| Backend Testing      | `backend/docs/BACKEND_TESTING.md`              |
| Modular Architecture | `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md` |
