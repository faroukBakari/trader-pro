# TWS Datafeed Provider

**Status:** Production-Ready (Core Capabilities)  
**Architecture:** Three-Layer Composition Pattern

---

## Quick Reference

| Layer               | File                                  | Responsibility                             |
| ------------------- | ------------------------------------- | ------------------------------------------ |
| **3 - TWSProvider** | `__init__.py`                         | DatafeedCapability impl, domain conversion |
| **2 - TWSClient**   | `tws_connection.py`                   | AsyncIO facade, owns TWSCallback           |
| **2 - TWSCallback** | `tws_connection.py`                   | EWrapper callbacks, Future registry        |
| **1 - IBSocket**    | `tws_connection.py`                   | Raw TCP, daemon thread reader loop         |
| **Mappers**         | `tws_mappers.py`                      | TWS ↔ domain model conversion              |
| **Config**          | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic validation      |

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
    async def search_symbols(self, pattern: str, timeout: float = 5.0) -> list[SearchSymbolResultItem]
    async def get_symbol_info(self, symbol: str, exchange: str | None = None) -> SymbolInfo
    async def get_historical_bars(self, symbol: str, start: datetime, end: datetime,
                                   timeframe: TimeFrame, exchange: str | None = None) -> list[Bar]
    async def get_quotes_snapshot(self, symbols: list[str]) -> list[QuoteData]
    # Subscriptions (not yet implemented)
    def subscribe_realtime_bars(self, symbol: str, callback: Callable[[Bar], None]) -> int
    def subscribe_market_data(self, symbol: str, callback: Callable[[QuoteData], None]) -> int
    def unsubscribe_realtime_bars(self, subscription_id: int) -> None
    def unsubscribe_market_data(self, subscription_id: int) -> None
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
| `tws_ticks_to_quote_data()`               | Accumulated ticks → `QuoteData`                  |

**secType Mapping:**

```python
SEC_TYPE_MAP = {"STK": "stock", "OPT": "option", "FUT": "futures",
                "CASH": "forex", "IND": "index", "CRYPTO": "crypto"}
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

Used by: `subscribe_realtime_bars()` — indefinite streaming (NOT YET IMPLEMENTED)

```python
def subscribe_realtime_bars(self, symbol: str, callback: Callable[[Bar], None]) -> int:
    req_id = self._get_next_req_id()
    self._subscription_callbacks[req_id] = lambda bar: callback(tws_bar_to_domain_bar(bar))
    self.ibsocket.send_message(REQ_REAL_TIME_BARS, [...])
    return req_id  # Return for unsubscribe
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

| Topic               | Document                                       |
| ------------------- | ---------------------------------------------- |
| Provider System     | `backend/docs/PROVIDER-SYSTEM.md`              |
| TWS API Reference   | `backend/external_packages/tws/docs/README.md` |
| DatafeedService     | `modules/datafeed/service.py`                  |
| Implementation Plan | `docs/tmp/plan_tws_datafeed_provider.md`       |
| Backend Testing     | `backend/docs/BACKEND_TESTING.md`              |
