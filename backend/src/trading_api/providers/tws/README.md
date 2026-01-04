# TWS Provider

**Status:** Production-Ready (Datafeed + Broker Capabilities)  
**Architecture:** Three-Layer Streaming Pattern  
**Last Updated:** January 4, 2026

---

## Quick Reference

| Layer                       | File                                  | Responsibility                                    |
| --------------------------- | ------------------------------------- | ------------------------------------------------- |
| **3 - TWSDatafeedProvider** | `datafeed_provider.py`                | DatafeedCapability impl, domain conversion        |
| **3 - TWSBrokerProvider**   | `broker_provider.py`                  | BrokerCapability impl, order/position management  |
| **2 - TWSClient**           | `tws_connection.py`                   | AsyncIO facade, stream management, owns IBSocket  |
| **1 - IBSocket**            | `tws_connection.py`                   | Raw TCP, daemon thread, business key registry     |
| **CachedContract**          | `cached_contract.py`                  | Contract caching (description → full details)     |
| **OrderTracker**            | `order_tracker.py`                    | Order state tracking for broker callbacks         |
| **Mappers**                 | `tws_mappers.py`                      | TWS ↔ domain model conversion, ticker parsing     |
| **Models**                  | `tws_models.py`                       | `StreamData`, `AssetConfig`, error classification |
| **Config**                  | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic settings               |

**Tests:** `providers/tws/tests/test_{client,ibsocket,mappers,models,datafeed_provider,broker_provider,cached_contract,config}.py`

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
DatafeedService / BrokerService (provider-agnostic)
        │ requires capability="datafeed" / "broker"
        ▼
TWSDatafeedProvider / TWSBrokerProvider (Layer 3) ─── implements Capability
        │ domain ↔ TWS conversion, business key generation
        ▼
TWSClient (Layer 2) ─── owns IBSocket, async facade, contract caching
        │ create_snapshot() / create_stream() API, CachedContract cache
        ▼
IBSocket (Layer 1) ─── daemon thread _reader_task(), business key registry
        │ StreamData accumulation, snapshot/stream hooks, TWS key mapping
        ▼
TWS/IB Gateway (localhost:7497)
```

### Threading Model

```
Main Thread (AsyncIO)                    Daemon Thread
─────────────────────                    ─────────────
TWSDatafeedProvider.subscribe_market_data()      IBSocket._reader_task()
        │                                        │
TWSClient.reqMktDataStream()             Decoder.interpret()
        │                                        │
ibsocket.create_stream(business_key)     tickPrice(reqId, price)
        │                                        │
        │                                _update_stream_data(tws_key, {"bid": price})
        │                                        │
callback(data) ◄──────────────────────── _notify_stream(tws_key, stream)
                                                 │
                    loop.call_soon_threadsafe(callback, stream[-1], updated_fields)
```

**Key Patterns:**

- **Lazy Connection**: `TWSClient.ibsocket` connects on first access
- **Business Key System**: External API uses business keys (e.g., `datafeed:Quote:SMART:AAPL:...`)
- **TWS Key Mapping**: `_business_to_tws_key[business_key] → tws_key` (e.g., `req_123`)
- **StreamData Accumulation**: `_stream_data[tws_key]` holds `StreamData` dataclass (list of dicts + metadata)
- **Snapshot Hooks**: `_snapshot_hooks[tws_key]` holds list of (loop, Future) for one-shot requests
- **Stream Hooks**: `_stream_hooks[tws_key]` holds list of (loop, callback, on_error) for continuous updates
- **Deduplication**: `create_snapshot()`/`create_stream()` return `None` reqId if reusing existing request

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

- Business key generation: `f"datafeed:Quote:{contract.exchange}:{ticker_name(contract)}"`
- Contract caching: `TWSClient.__contracts_cache[conId]` stores `CachedContract`
- Unsubscription: Cancel by business key (maps internally to TWS reqId)

---

## 2.1 Business Key Convention

**Business keys** are the external API for identifying requests and subscriptions. Internal TWS request IDs (`reqId`) are hidden from callers.

**Format:**

```
{capability}:{operation}:{params}
```

**Examples:**

| Business Key                                                     | Purpose                     |
| ---------------------------------------------------------------- | --------------------------- |
| `shared:reqMatchingSymbols:AAPL`                                 | Symbol search request       |
| `shared:reqContractDetails:AAPL:NASDAQ:STK-12345`                | Contract details lookup     |
| `datafeed:Quote:SMART:AAPL:NASDAQ:STK-12345`                     | Quote stream/snapshot       |
| `datafeed:reqBarDataStream:SMART:AAPL:NASDAQ:STK-12345@5 mins`   | Real-time bar subscription  |
| `datafeed:reqHistoricalData:SMART:1 D:20251231:AAPL:...:@5 mins` | Historical bars request     |
| `broker:orders`                                                  | Order subscription (future) |

**Internal Mapping:**

```python
# IBSocket internal mapping
_business_to_tws_key: dict[str, str] = {
    "datafeed:Quote:SMART:AAPL:NASDAQ:STK-12345": "req_42",
    "broker:orders": "order_subscription",
}
```

**Benefits:**

- Callers don't need to track reqIds
- Deduplication: Same business key reuses existing request
- Cleanup: `remove_stream(business_key)` handles all internal state

---

## 2.2 Contract Caching

**File:** `cached_contract.py`

The `CachedContract` class provides a unified cache for contract data:

```python
@dataclass
class CachedContract(ContractDetails):
    derivativeSecTypes: list[str]  # From ContractDescription
    has_full_details: bool         # True if from reqContractDetails
    _ticker: str                   # Cached ticker_name string

    # Factory methods
    @staticmethod
    def from_contract_details(details: ContractDetails) -> CachedContract
    @staticmethod
    def from_contract_description(desc: ContractDescription) -> CachedContract

    # Helpers
    def matches(self, ticker: str) -> bool  # Check if ticker matches this contract
    def update_from_details(details: ContractDetails) -> None  # Upgrade partial to full
```

**TWSClient caching strategy:**

```python
# TWSClient - Internal cache lookup helper
def _get_cached_contracts(
    self,
    ticker: str,
    preferred_exchanges: list[str] | None = None,
    require_full_details: bool = False,
) -> list[CachedContract]:
    """Get cached contracts with optional exchange filtering."""
    cached = [
        con for con in self.__contracts_cache.values()
        if con.matches(ticker)
        and (not require_full_details or con.has_full_details)
    ]
    # Exchange filtering with fallback to unfiltered if no match
    if cached and preferred_exchanges and preferred_exchanges != [""]:
        filtered = [c for c in cached if c.contract.exchange in preferred_exchanges]
        return filtered or cached
    return cached

# TWSClient - Public method uses the helper
__contracts_cache: dict[int, CachedContract] = {}  # conId → CachedContract

def get_qualified_contracts(self, ticker: str, preferred_exchanges: list[str]) -> list[Contract]:
    cached = self._get_cached_contracts(ticker, preferred_exchanges)
    if cached:
        return [c.contract for c in cached]
    return [build_contract(ticker)]  # Fallback to unqualified
```

**Cache population:**

- `reqMatchingSymbols()`: Populates cache from `ContractDescription` (partial)
- `reqContractDetails()`: Upgrades cache entries to full `ContractDetails`

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
class DatafeedCapability(ABC):
    # One-shot requests (return data)
    async def search_symbols(self, pattern: str, **kwargs) -> list[SearchSymbolResultItem]
    async def get_symbol_info(self, ticker_name: str, **kwargs) -> SymbolInfo
    async def get_historical_bars(self, ticker_name: str, start_time: datetime, end_time: datetime,
                                   resolution: Resolution, **kwargs) -> list[Bar]
    async def get_quotes_snapshot(self, ticker_names: list[str], **kwargs) -> list[QuoteData]

    # Subscription methods (return business keys as subscription IDs)
    def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Coroutine[Any, Any, None]],
        on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],
        **kwargs,
    ) -> str

    def subscribe_market_data(
        self,
        ticker_name: str,  # Single symbol (changed from list)
        callback: Callable[[QuoteData], Coroutine[Any, Any, None]],
        on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],
        **kwargs,
    ) -> str  # Single subscription ID (changed from list)

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None
    def unsubscribe_market_data(self, subscription_id: str) -> None  # Single ID (changed from list)
```

**Interface Tags:**

- `[CONTINUOUS]`: Callback invoked continuously until unsubscribe
- `[THREAD-SAFE]`: Callback may be invoked from provider thread
- `[ERROR-HANDLING]`: `on_error` callback required for subscription-level error notifications

**Key Changes from Previous Version:**

- `subscribe_market_data()` now takes single `ticker_name: str`, returns single `str` (was list)
- `unsubscribe_market_data()` now takes single `subscription_id: str` (was list)
- `on_error` callback is now **required** (was optional)
- Callback type uses `Coroutine[Any, Any, None]` for async compatibility

---

## 4.1 BrokerCapability Interface

```python
class BrokerCapability(ABC):
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

- **Current Implementation**: `TWSBrokerProvider` is currently a **FakeBroker stub** with in-memory state for development/testing. Real TWS order integration is in progress (see `order_tracker.py`).
- **Leverage Methods**: IBKR uses account-level margin, not per-symbol leverage. These methods raise `ProviderException` with code `PROVIDER_BROKER_LEVERAGE_NOT_SUPPORTED`.
- **Order Preview**: Returns estimated values since TWS doesn't have native preview API.
- **Bracket Orders**: `edit_position_brackets()` implemented using OCA (One-Cancels-All) groups. Creates stop loss (STP/TRAIL) and take profit (LMT) orders linked so when one fills, TWS cancels the others.
- **Equity Streaming**: TWS doesn't push account changes; polling via `get_equity()` is required.
- **Client ID**: Broker uses `client_id=2` (default), separate from datafeed's `client_id=1`.

**Real TWS Broker Integration (In Progress):**

- `OrderTracker` class in `order_tracker.py` handles TWS order callbacks
- `TrackedOrder` stores raw TWS objects (Contract, Order, OrderState)
- `OrderFill` captures each `orderStatus` callback for fill history

**Configuration:**

| Env Variable            | Type | Default     | Description                        |
| ----------------------- | ---- | ----------- | ---------------------------------- |
| `TWS_BROKER_ENABLED`    | bool | `True`      | Enable broker provider             |
| `TWS_BROKER_HOST`       | str  | `127.0.0.1` | Gateway host                       |
| `TWS_BROKER_PORT`       | int  | `7497`      | Gateway port                       |
| `TWS_BROKER_CLIENT_ID`  | int  | `2`         | Client ID (separate from datafeed) |
| `TWS_BROKER_ACCOUNT_ID` | str  | `""`        | Account ID for orders              |

### OCA Group Pattern

**OCA (One-Cancels-All)** groups link multiple orders so when one fills, TWS automatically cancels the rest. Used for position brackets where no parent order exists.

**`TWSClient.placeOcaGroup()` Method:**

```python
async def placeOcaGroup(
    self,
    contract: Contract,
    children: list[Order],
    oca_group: str,
    oca_type: int = 1,
    parent_id: int = 0,
    timeout: float | None = None,
) -> list[TrackedOrder]
```

**Parameters:**

| Parameter   | Type                 | Description                                            |
| ----------- | -------------------- | ------------------------------------------------------ |
| `contract`  | `Contract`           | The contract for all orders                            |
| `children`  | `list[Order]`        | List of Order objects (e.g., stop loss + take profit)  |
| `oca_group` | `str`                | Unique OCA group identifier (e.g., `bracket_pos123`)   |
| `oca_type`  | `int`                | OCA behavior type (default: 1)                         |
| `parent_id` | `int`                | Parent order ID for bracket children (default: 0)      |
| `timeout`   | `float \| None`      | Timeout for order confirmations (default: client timeout) |

**OCA Type Options:**

| Type | Name              | Description                                                 |
| ---- | ----------------- | ----------------------------------------------------------- |
| 1    | CANCEL_WITH_BLOCK | Cancel all remaining with overfill protection (recommended) |
| 2    | REDUCE_WITH_BLOCK | Proportionally reduce remaining with block                  |
| 3    | REDUCE_NO_BLOCK   | Proportionally reduce without block                         |

**Usage in `edit_position_brackets()`:**

```python
# Generate deterministic OCA group for position brackets
oca_group = f"bracket_{position_id}"

# Place bracket orders atomically via OCA group
tracked_orders = await self._tws_client.placeOcaGroup(
    contract, bracket_orders, oca_group, oca_type=1
)
```

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

| Function                                | Description                                                                                                                                                                                                          |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `preorder_to_tws()`                     | `PreOrder` → `(Order, Order \| None, Order \| None)` — parent, stop_loss, take_profit. Generates UUID-based `ocaGroup` (e.g., `bracket_<uuid8>`) when brackets present. Supports `trailStopPrice` for trailing stops. |
| `tws_order_to_placed_order()`           | order data dict → `PlacedOrder`                                                                                                                                                                                      |
| `tws_position_to_domain()`              | position data dict → `Position`                                                                                                                                                                                      |
| `tws_account_summary_to_equity()`       | summary dict → `EquityData`                                                                                                                                                                                          |
| `tws_account_summary_to_account_info()` | summary dict → `AccountMetainfo`                                                                                                                                                                                     |
| `calculate_tws_duration()`              | time range → TWS duration string                                                                                                                                                                                     |

**secType Mapping:**

```python
SEC_TYPE_MAP = {"STK": "stock", "OPT": "option", "FUT": "futures",
                "CASH": "forex", "IND": "index", "CRYPTO": "crypto", ...}
```

---

## 7. Stream Data Pattern (Real-time Data)

**Replaces the old ticker slot dict with typed `StreamData` dataclass.**

Stream data is managed by IBSocket using typed `StreamData` instances:

```python
# StreamData dataclass (tws_models.py)
@dataclass
class StreamData(list[dict[str, Any]]):
    business_key: str                    # External identifier (e.g., "datafeed:Quote:...")
    snapshot_complete: bool = False      # Triggers future resolution when True
    index_key: str | None = None         # Optional key for indexed lookups
    updated_fields: list[str] = field(default_factory=list)  # Changed fields for selective notification
    last_updated: int = 0                # Unix timestamp (ms) of last update
    last_dispatched: int = 0             # Unix timestamp (ms) of last callback dispatch

# IBSocket internal state
_stream_data: dict[str, StreamData] = {}           # tws_key → StreamData
_business_to_tws_key: dict[str, str] = {}          # business_key → tws_key (e.g., "req_123")
_snapshot_hooks: dict[str, list[tuple[loop, Future]]] = {}  # tws_key → pending futures
_stream_hooks: dict[str, list[tuple[loop, callback, on_error]]] = {}  # tws_key → stream callbacks
```

**StreamData inherits from `list[dict[str, Any]]`** - each dict is one data item (tick, bar, etc.):

```python
# Example: Quote stream data
stream[-1] = {
    "business_key": "datafeed:Quote:SMART:AAPL:NASDAQ:STK-12345",
    "bid": 150.25,
    "ask": 150.30,
    "last": 150.27,
    "market_data_type": 1,
    "min_tick": 0.01,
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

**Update Methods (called from daemon thread):**

```python
# _update_stream_data: Updates last item in stream (for tick updates)
def _update_stream_data(self, tws_key: str, updates: dict[str, Any], *, tolerance: float = 1e-3) -> None:
    stream = self._stream_data.get(tws_key)
    if not stream:
        stream.append({})
    last_slot = stream[-1]
    # Update fields, track changed fields, notify if any changed
    ...
    self._notify_stream(tws_key, stream)

# _append_stream_data: Adds new item to stream (for accumulation patterns)
def _append_stream_data(self, tws_key: str, data: dict[str, Any]) -> None:
    ...

# _extend_stream_data: Adds multiple items (for batch responses)
def _extend_stream_data(self, tws_key: str, data: list[dict[str, Any]]) -> None:
    ...

# _flag_snapshot_complete: Triggers future resolution
def _flag_snapshot_complete(self, tws_key: str) -> None:
    stream.snapshot_complete = True
    self._notify_stream(tws_key, stream)
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

### One-Shot Request (Snapshot Pattern)

Used by: `search_symbols()`, `get_historical_bars()`, `get_quotes_snapshot()`

```python
# TWSClient
async def reqMatchingSymbols(self, pattern: str, timeout: float | None = None) -> list[ContractDescription]:
    business_key = f"shared:reqMatchingSymbols:{pattern}"

    # Check cache first
    data = self.ibsocket.get_cached_data(business_key)
    if data is not None:
        return [item["contractDescriptions"] for item in data]

    # Create snapshot request
    reqId, coroutine = self.ibsocket.create_snapshot(
        business_key,
        timeout=timeout or self._timeout,
    )

    # Only send request if new (reqId is None if reusing existing)
    if reqId is not None:
        self.ibsocket.reqMatchingSymbols(reqId, pattern)

    data = await coroutine
    return [item["contractDescriptions"] for item in data]

# IBSocket callback (daemon thread)
def symbolSamples(self, reqId: int, contractDescriptions: list[ContractDescription]) -> None:
    tws_key = f"req_{reqId}"
    self._extend_stream_data(
        tws_key, [{"contractDescriptions": cd} for cd in contractDescriptions]
    )
    self._flag_snapshot_complete(tws_key)  # Resolves pending futures
```

### Generic Snapshot Executor

TWSClient provides `_exec_snapshot()` to reduce boilerplate in snapshot methods:

```python
# TWSClient._exec_snapshot() - Generic cache-check → request → await pattern
async def _exec_snapshot(
    self,
    business_key: str,
    request_fn: Callable[[int], None],  # Called with reqId to issue TWS request
    transform_fn: Callable[[list[dict[str, Any]]], T],  # Transforms raw data to return type
    timeout: float | None = None,
) -> T:
    # 1. Check cache first
    cached = self.ibsocket.get_cached_data(business_key)
    if cached is not None:
        return transform_fn(cached)

    # 2. Create snapshot request
    reqId, coroutine = self.ibsocket.create_snapshot(
        business_key, timeout=timeout or self._timeout
    )

    # 3. Issue request if new (reqId is None if reusing existing)
    if reqId is not None:
        request_fn(reqId)

    # 4. Await and transform result
    return transform_fn(await coroutine)
```

**Example Usage (reqQuoteSnapshot):**

```python
async def reqQuoteSnapshot(self, contract: Contract) -> dict[str, Any]:
    business_key = f"datafeed:Quote:{contract.exchange}:{ticker_name(contract)}"

    def transform(data: list[dict[str, Any]]) -> dict[str, Any]:
        assert data, "No data received"
        return next(iter(data))

    return await self._exec_snapshot(
        business_key,
        lambda rid: self.ibsocket.reqQuote(rid, contract),
        transform,
    )
```

### Streaming Subscription (Stream Pattern)

Used by: `subscribe_realtime_bars()`, `subscribe_market_data()`

```python
# TWSClient
def reqBarDataStream(
    self,
    contract: Contract,
    bar_size: str,
    callback: Callable[[dict, list[str]], Coroutine],
    on_error: Callable[[ProviderException], Coroutine],
) -> str:
    business_key = f"datafeed:reqBarDataStream:{contract.exchange}:{ticker_name(contract, bar_size)}"

    # Create stream - returns None reqId if reusing existing
    reqId = self.ibsocket.create_stream(business_key, callback, on_error)

    if reqId is not None:
        self.ibsocket.reqBars(reqId, contract, end_date_time="", ...)

    return business_key  # Return business key as subscription ID

# TWSDatafeedProvider
def subscribe_realtime_bars(self, ticker_name: str, resolution: Resolution, callback, on_error) -> str:
    bar_size = map_resolution_to_tws_bar_size(resolution)

    async def bar_callback(rt_data: dict[str, Any], fields: list[str] | None) -> None:
        await callback(tws_ticks_to_bar(rt_data))

    contract = next(iter(self._tws_client.get_qualified_contracts(ticker_name, ...)))
    return self._tws_client.reqBarDataStream(contract, bar_size, bar_callback, on_error=on_error)
```

### Cancellation

```python
# TWSClient
def cancel_data_stream(self, stream_key: str) -> None:
    self.ibsocket.remove_stream(stream_key)  # Triggers cleanup hook → sends cancel message

# IBSocket.remove_stream() cleanup
def remove_stream(self, business_key: str) -> None:
    tws_key = self._business_to_tws_key.get(business_key)
    self._stream_hooks.pop(tws_key, None)
    # Cleanup hook sends TWS cancel message via call_soon_threadsafe
    cleanup = self._cleanup_hooks.pop(tws_key, None)
    if cleanup:
        loop, cleanup_func = cleanup
        loop.call_soon_threadsafe(cleanup_func)
```

### OCA Group Submission (Atomic Bracket Orders)

Used by: `edit_position_brackets()`, `placeOrderGroup()` with brackets

OCA groups use the **transmit chain pattern** for atomic submission:

```python
# TWSClient.placeOcaGroup() - Atomic bracket order submission
async def placeOcaGroup(self, contract, children, oca_group, oca_type=1, parent_id=0, timeout=None):
    # Assign OCA attributes to all orders
    for order in children:
        order.ocaGroup = oca_group
        order.ocaType = oca_type

    # Transmit chain: all orders except last staged with transmit=False
    order_ids = [
        self._submit_order(contract, order, parent_id=parent_id, transmit=False)
        for order in children[:-1]
    ]
    order_ids.append(
        self._submit_order(contract, children[-1], parent_id=parent_id, transmit=True)
    )

    # Await all order confirmations with timeout
    return await asyncio.gather(*[
        self.ibsocket.order_tracker.order_update(oid, timeout=timeout)
        for oid in order_ids
    ])
```

**Key Points:**

- All orders except last have `transmit=False` (staged but not sent)
- Last order `transmit=True` triggers atomic submission of entire group
- TWS processes all orders as a unit, preventing partial fills
- OCA group ensures when one fills, others are automatically canceled

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

`classify_error()` in `tws_models.py` classifies TWS error codes by nature, meaning, and recoverability:

```python
from tws_models import classify_error, TWSErrorClassification, TWSErrorNature

nature, category, is_recoverable = classify_error(error_code)
# Returns: (TWSErrorNature.*, TWSErrorClassification.*, bool)
```

**Error Nature** (what does the error ID represent?):

| Nature    | Value      | Description                                |
| --------- | ---------- | ------------------------------------------ |
| `ORDER`   | `"order"`  | ID is an order ID (use for order routing)  |
| `REQUEST` | `"req"`    | ID is a request ID (use for data requests) |
| `SYSTEM`  | `"system"` | System-wide error (no specific ID)         |

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

Subscription methods require `on_error` callback for streaming errors:

```python
def subscribe_realtime_bars(
    self,
    ticker_name: str,
    resolution: Resolution,
    callback: Callable[[Bar], Coroutine[Any, Any, None]],
    on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],  # Required
    **kwargs: Any,
) -> str:
    ...
```

**Error Flow:**

```
TWS error() callback
        │
classify_error(code)  →  (nature, category, is_recoverable)
        │
        ├─► nature == ORDER → _handle_order_error(id, category, detail, message)
        │           │
        │           └─► Look up order by order_id, invoke error callback
        │
        └─► nature == REQUEST/SYSTEM → _handle_request_error(...)
                │
                ├─► Look up business_key from tws_key
                │   capability = business_key.split(":")[0]  # "datafeed", "broker", "shared"
                │
                ├─► Snapshot hooks exist → reject future with ProviderException
                │
                └─► Stream hooks exist → invoke on_error callbacks
                        │
                        └─► Non-recoverable → call remove_stream(business_key)
```

### Centralized Error Routing

`_handle_request_error()` routes errors based on business key and request state:

```python
def _handle_request_error(self, category, detail, tws_key, message, timestamp=None):
    # Look up business_key and extract capability
    business_key = next(
        (bk for bk, tk in self._business_to_tws_key.items() if tk == tws_key),
        "NOT_FOUND"
    )
    capability = business_key.split(":", 1)[0] or "shared"

    error = ProviderException(
        code=f"PROVIDER_TWS_{category}_{detail.upper()}",
        message=f"[{tws_key}] {message}",
        provider="tws",
        capability=capability,
        timestamp=timestamp,
    )

    # 1. Snapshot hooks → reject futures + schedule cleanup
    # 2. Stream hooks → invoke on_error callbacks
    # 3. Non-recoverable (_NON_RECOVERABLE suffix) → call remove_stream()
    # 4. Neither → log as orphan error
```

**Thread-Safe Cleanup:** Non-recoverable errors trigger cleanup via `loop.call_soon_threadsafe()`:

```python
# Daemon thread schedules cleanup in event loop
for stream_loop, _, on_error in stream_hooks:
    stream_loop.call_soon_threadsafe(self.remove_stream, business_key)
    break  # Only need to remove once
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
