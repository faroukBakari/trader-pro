# TWS Provider

**Status:** Production-Ready (Datafeed + Broker Capabilities)  
**Architecture:** Three-Layer Streaming Pattern  
**Last Updated:** January 11, 2026

---

## Quick Reference

| Layer                       | File                                  | Responsibility                                                                  |
| --------------------------- | ------------------------------------- | ------------------------------------------------------------------------------- |
| **3 - TWSDatafeedProvider** | `datafeed_provider.py`                | DatafeedCapability impl, domain conversion                                      |
| **3 - TWSBrokerProvider**   | `broker_provider.py`                  | BrokerCapability impl, order/position management                                |
| **2 - TWSClient**           | `tws_connection.py`                   | AsyncIO facade, stream management, owns IBSocket                                |
| **1 - IBSocket**            | `tws_connection.py`                   | Raw TCP, daemon thread, business key registry                                   |
| **CachedContract**          | `cached_contract.py`                  | Contract caching (description → full details)                                   |
| **ContractTracker**         | `contract_tracker.py`                 | Contract persistence with SQLite + lazy loading                                 |
| **OrderTracker**            | `order_tracker.py`                    | Order state tracking, status mapping, OCA reconciliation, parent-child dispatch |
| **PositionTracker**         | `position_tracker.py`                 | Position state tracking, thread-safe snapshot/stream pattern                    |
| **AccountTracker**          | `account_tracker.py`                  | Account metrics tracking (equity, balance, P&L), reqAccountSummary/reqPnL       |
| **Mappers**                 | `tws_mappers.py`                      | TWS ↔ domain model conversion, ticker parsing                                   |
| **Models**                  | `tws_models.py`                       | `StreamData`, `AssetConfig`, error classification                               |
| **Config**                  | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic settings                                             |

**Tests:** `providers/tws/tests/test_{client,ibsocket,mappers,models,datafeed_provider,broker_provider,cached_contract,contract_tracker,config}.py`

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

**Ticker Format:**

```
{exchange}:{symbol}[@{bar_size}]
```

**Examples:**

- `"NASDAQ:AAPL"` - Stock ticker
- `"NASDAQ:AAPL@5 mins"` - Stream key with bar size

**Functions:**

```python
from tws_mappers import ticker_name, parse_ticker, infer_sec_type

# ticker_name(contract) → "NASDAQ:AAPL"
# ticker_name(contract, "5 mins") → "NASDAQ:AAPL@5 mins"

# parse_ticker("NASDAQ:AAPL") → ("AAPL", "NASDAQ", "STK", "")
# parse_ticker("NASDAQ:AAPL@5 mins") → ("AAPL", "NASDAQ", "STK", "5 mins")
# Returns: (symbol, exchange, secType, bar_size) - secType is inferred

# infer_sec_type("NASDAQ", "AAPL") → "STK"
# infer_sec_type("IDEALPRO", "EURUSD") → "CASH"
```

**Usage:**

- Business key generation: `f"datafeed:Quote:{contract.exchange}:{ticker_name(contract)}"`
- Contract caching: `IBSocket.contract_tracker` manages `CachedContract` with SQLite persistence
- Unsubscription: Cancel by business key (maps internally to TWS reqId)

---

## 2.1 Security Type Inference

The `infer_sec_type()` function dynamically determines security type from exchange and symbol:

```python
from tws_mappers import infer_sec_type, FOREX_CURRENCIES

# FOREX_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"}

infer_sec_type("NASDAQ", "AAPL")      # → "STK" (default)
infer_sec_type("IDEALPRO", "EURUSD")  # → "CASH" (forex exchange)
infer_sec_type("PAXOS", "BTCUSD")     # → "CRYPTO" (crypto exchange)
infer_sec_type("CME", "ES1!")         # → "CONTFUT" (continuous future)
```

**Detection Rules:**

| Condition                              | Returns   | Example                     |
| -------------------------------------- | --------- | --------------------------- |
| `symbol.endswith("1!")`                | `CONTFUT` | `ES1!` → Continuous futures |
| `exchange in ("IDEALPRO", "FX")`       | `CASH`    | Forex exchanges             |
| `exchange in ("PAXOS", "ZEROHASH")`    | `CRYPTO`  | Crypto exchanges            |
| 6-char symbol with forex prefix        | `CASH`    | `EURUSD`                    |
| `symbol[-3:] in ("USD", "EUR", "GBP")` | `CRYPTO`  | `BTCUSD`                    |
| Default                                | `STK`     | Stocks                      |

---

## 2.2 Business Key Convention

**Business keys** are the external API for identifying requests and subscriptions. Internal TWS request IDs (`reqId`) are hidden from callers.

**Format:**

```
{capability}:{operation}:{params}
```

**Examples:**

| Business Key                                                       | Purpose                                |
| ------------------------------------------------------------------ | -------------------------------------- |
| `shared:reqMatchingSymbols:AAPL`                                   | Symbol search request                  |
| `shared:reqContractDetails:ANY:NASDAQ:AAPL`                        | Contract details lookup                |
| `datafeed:Quote:SMART:NASDAQ:AAPL`                                 | Quote stream/snapshot                  |
| `datafeed:reqBarDataStream:SMART:NASDAQ:AAPL@5 mins`               | Real-time bar subscription             |
| `datafeed:reqHistoricalData:SMART:1 D:20251231:NASDAQ:AAPL@5 mins` | Historical bars request                |
| `broker:orders`                                                    | Order subscription (future)            |
| `broker:account:DEMO-ACCOUNT`                                      | Account equity/balance stream (future) |

**Internal Mapping:**

```python
# IBSocket internal mapping
_business_to_tws_key: dict[str, str] = {
    "datafeed:Quote:SMART:NASDAQ:AAPL": "req_42",
    "broker:orders": "order_subscription",
}
```

**Benefits:**

- Callers don't need to track reqIds
- Deduplication: Same business key reuses existing request
- Cleanup: `remove_stream(business_key)` handles all internal state

---

## 2.3 Contract Caching & Persistence

**Files:** `cached_contract.py`, `contract_tracker.py`

Contract data is cached in a two-tier architecture:

1. **Descriptions** (SQLite + memory): `ContractDescription` data from `reqMatchingSymbols` - immutable instrument identity
2. **Details** (memory only): Full `ContractDetails` from `reqContractDetails` - session-dependent (tradingHours, etc.)

### ContractTracker

**File:** `contract_tracker.py`

The `ContractTracker` manages contract caching with SQLite persistence following the Tracker pattern:

```python
class ContractTracker:
    _descriptions: dict[int, CachedContract]  # con_id → CachedContract (memory + SQLite)
    _details: dict[int, CachedContract]       # con_id → CachedContract (memory only)
    _sqlite: SQLiteContractCache              # Internal SQLite cache (hidden)

    # Lookup Methods (main thread)
    def get_by_con_id(self, con_id: int) -> CachedContract | None
    def get_by_ticker(self, ticker: str) -> CachedContract | None
    def get_by_symbol_prefix(self, prefix: str) -> list[CachedContract]
    def get_full_details(self, con_id: int) -> CachedContract | None  # details only

    # Upsert Methods (reader thread via callbacks)
    def upsert_descriptions(self, descriptions: list[ContractDescription]) -> list[CachedContract]
    def upsert_details(self, details: ContractDetails, overnight_hours: str | None) -> CachedContract

    # Session Management
    def clear_details_cache(self) -> None  # Clear session-dependent details
    def reset(self) -> None                # Clear all memory caches (SQLite preserved)
```

**Lazy Loading Flow:**

```
reqMatchingSymbols("AAPL")
        │
ContractTracker.get_by_symbol_prefix("AAPL")
        │
        ├─► 1. Check _descriptions (memory)
        │
        ├─► 2. Check SQLite (load into memory)
        │
        └─► 3. Cache miss → API call → symbolSamples() callback
                                            │
                                 ContractTracker.upsert_descriptions()
                                            │
                                 Persists to SQLite + memory
```

**SQLite Schema:**

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE contract_descriptions (
    con_id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    sec_type TEXT NOT NULL,
    primary_exchange TEXT NOT NULL,
    currency TEXT NOT NULL,
    derivative_sec_types TEXT,
    description TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, sec_type, primary_exchange)
);

CREATE INDEX idx_symbol ON contract_descriptions(symbol);
CREATE INDEX idx_symbol_prefix ON contract_descriptions(symbol COLLATE NOCASE);
```

**Configuration:**

```bash
# Environment variable (defaults to .cache/contracts.db)
export TWS_CONTRACT_CACHE_PATH=/path/to/contracts.db
```

### CachedContract

```python
@dataclass
class CachedContract(ContractDetails):
    derivativeSecTypes: list[str]       # From ContractDescription
    has_full_details: bool              # True if from reqContractDetails
    _ticker: str                        # Cached ticker_name string
    overnight_hours: str | None = None  # Darkpool trading hours (from OVERNIGHT exchange)

    # Factory methods
    @staticmethod
    def from_contract_details(details: ContractDetails, overnight_hours: str | None = None) -> CachedContract
    @staticmethod
    def from_contract_description(desc: ContractDescription) -> CachedContract

    # Helpers
    def matches(self, ticker: str) -> bool  # Check if ticker matches this contract
    def update_from_details(details: ContractDetails, overnight_hours: str | None = None) -> None

    # Session-aware contract builders
    def build_best_contract(self) -> Contract      # SMART or OVERNIGHT based on session
    def build_smart_contract(self) -> Contract | None   # Contract with SMART exchange
    def build_darkpool_contract(self) -> Contract | None  # Contract with OVERNIGHT exchange

    # Session status checks
    def is_session_closed(self, *, reference_time=None) -> bool   # Regular session closed?
    def is_darkpool_closed(self, *, reference_time=None) -> bool  # Overnight session closed?
```

**Session-Aware Methods:**

| Method                      | Returns            | Description                                                       |
| --------------------------- | ------------------ | ----------------------------------------------------------------- |
| `build_best_contract()`     | `Contract`         | Returns OVERNIGHT if session closed and darkpool open, else SMART |
| `build_smart_contract()`    | `Contract \| None` | Contract with exchange="SMART" if available in validExchanges     |
| `build_darkpool_contract()` | `Contract \| None` | Contract with exchange="OVERNIGHT" if available (Blue Ocean ATS)  |
| `is_session_closed()`       | `bool`             | True if regular trading hours closed (parses `tradingHours`)      |
| `is_darkpool_closed()`      | `bool`             | True if `overnight_hours` is None or darkpool session closed      |

**TWSClient Contract Resolution:**

```python
# TWSClient.reqContractDetails() - Multi-exchange resolution flow
async def reqContractDetails(self, contract: Contract) -> list[CachedContract]:
    # 1. Check ContractTracker by conId
    #    → Return immediately if has_full_details=True

    # 2. Fetch primary details via _reqContractDetails()

    # 3. If SMART available in validExchanges:
    #    → Fetch SMART contract details

    # 4. If OVERNIGHT available in validExchanges:
    #    → Fetch OVERNIGHT contract details
    #    → Extract overnight_hours = darkpool.tradingHours

    # 5. Cache all details via ContractTracker.upsert_details()

# TWSClient.req_ticker_details() - Simplified public API
async def req_ticker_details(self, ticker: str, **kwargs) -> CachedContract:
    """Get single CachedContract for ticker (uses parse_ticker internally)."""
    symbol, primaryExchange, sec_type, _ = parse_ticker(ticker)
    # ... builds Contract and delegates to reqContractDetails()
    return next(iter(details_list))  # Returns first/best match
```

**Internal Methods:**

- `_reqContractDetails(contract)` - Low-level TWS request (no caching logic)
- `_get_cached_details(con_id)` - Cache lookup via ContractTracker

**Cache Population:**

- `symbolSamples()` callback: Calls `ContractTracker.upsert_descriptions()` (SQLite + memory)
- `reqContractDetails()`: Calls `ContractTracker.upsert_details()` (memory only, session-dependent)

---

## 2.4 Account Tracking

**File:** `account_tracker.py`

The `AccountTracker` class manages TWS account state (equity, balance, P&L metrics) with thread-safe snapshot/stream pattern similar to `OrderTracker` and `PositionTracker`.

### TrackedAccount Dataclass

Stores raw TWS account data from callbacks without transformation. All values are optional - populated incrementally as updates arrive.

```python
@dataclass
class TrackedAccount:
    """Wraps raw TWS account data.

    Thread Safety:
        - Created/updated by reader thread
        - Passed by reference to main thread callbacks (no copies)
        - Main thread consumers should not mutate these objects
    """
    id: str
    pnl_req_id: int | None = None  # Request ID for P&L subscription

    # Core Equity Metrics
    net_liquidation: Decimal | None = None      # Total account value
    total_cash_value: Decimal | None = None     # Cash + futures P&L
    equity_with_loan_value: Decimal | None = None
    gross_position_value: Decimal | None = None
    buying_power: Decimal | None = None

    # Margin & Risk
    available_funds: Decimal | None = None
    excess_liquidity: Decimal | None = None
    cushion: Decimal | None = None
    init_margin_req: Decimal | None = None
    maint_margin_req: Decimal | None = None
    leverage: Decimal | None = None

    # P&L (from reqPnL - real-time updates)
    daily_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None

    # Account Info
    currency: str | None = None
    account_type: str | None = None
    day_trades_remaining: int | None = None
    account_ready: bool = True
    last_update_time: str | None = None
```

**Field Mapping (`TWS_TAG_TO_FIELD`):**

TWS sends PascalCase tag names (e.g., `"NetLiquidation"`) which are mapped to snake_case Python fields:

| TWS Tag           | Python Field       | Description                       |
| ----------------- | ------------------ | --------------------------------- |
| `NetLiquidation`  | `net_liquidation`  | Total account value               |
| `TotalCashValue`  | `total_cash_value` | Cash + futures P&L                |
| `BuyingPower`     | `buying_power`     | Max marginable stocks purchasable |
| `AvailableFunds`  | `available_funds`  | Available for trading             |
| `ExcessLiquidity` | `excess_liquidity` | Excess over margin requirements   |
| `InitMarginReq`   | `init_margin_req`  | Initial margin requirement        |
| `MaintMarginReq`  | `maint_margin_req` | Maintenance margin requirement    |
| `Leverage`        | `leverage`         | GrossPositionValue / NetLiq       |
| `DailyPnL`        | `daily_pnl`        | Real-time daily P&L               |
| `UnrealizedPnL`   | `unrealized_pnl`   | Real-time unrealized P&L          |
| `RealizedPnL`     | `realized_pnl`     | Real-time realized P&L            |
| `Currency`        | `currency`         | Base account currency             |

### Data Sources

Account data comes from three TWS API methods:

| Method                | Callback               | Purpose                                    | Update Frequency      |
| --------------------- | ---------------------- | ------------------------------------------ | --------------------- |
| `reqAccountSummary()` | `accountSummary()`     | Batch fetch of all account metrics         | On-demand (snapshot)  |
| `reqAccountUpdates()` | `updateAccountValue()` | Incremental account metric updates         | ~3 minutes (periodic) |
| `reqPnL()`            | `pnl()`                | Real-time P&L streaming (daily, unr, real) | Real-time             |

**Subscription Lifecycle:**

```python
# IBSocket methods
def reqAccountSubscriptions(self, account: str) -> int:
    """Subscribe to account updates with P&L.

    Combines _reqAccountUpdates(True, account) + _reqPnL(reqId, account)
    Returns: P&L request ID for tracking
    """
    self._reqAccountUpdates(True, account)
    reqId = self.next_req_id
    self._reqPnL(reqId, account)
    return reqId

def cancelAccountSubscriptions(self, reqId: int) -> None:
    """Cancel P&L subscription."""
    self._cancelPnL(reqId)
```

### Domain Conversion Methods

**`TrackedAccount.equity_data()` → `EquityData`:**

```python
def equity_data(self) -> EquityData:
    """Convert to domain EquityData for WebSocket streaming.

    Field Mappings:
        - equity = net_liquidation (total account value)
        - balance = total_cash_value (cash + futures P&L)
        - unrealizedPL = unrealized_pnl (from reqPnL)
        - realizedPL = realized_pnl (from reqPnL)

    Falls back to 0.0 for unset values (using isUnset() helper).
    """
```

**`TrackedAccount.metainfo()` → `AccountMetainfo`:**

```python
def metainfo(self) -> AccountMetainfo:
    """Convert to AccountMetainfo for account list.

    Returns:
        AccountMetainfo with id, name, currency, currencySign
    """
    return AccountMetainfo(
        id=self.id,
        name=self.id,  # TWS doesn't provide separate display name
        currency=self.currency or "USD",
        currencySign=self.currency_sign or "$",
    )
```

**Currency Support:**

```python
CURRENCY_SIGNS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CHF": "CHF", "CAD": "C$", "AUD": "A$",
}

@property
def currency_sign(self) -> str | None:
    """Get currency sign based on currency code."""
    return CURRENCY_SIGNS.get(self.currency) if self.currency else None
```

### Snapshot/Stream Pattern

**AccountTracker Architecture:**

```python
class AccountTracker:
    """Manages account state for IBSocket. Thread-safe via asyncio dispatch.

    Thread Ownership:
        - Envelope (hooks registration, reset): main thread
        - Content (accounts dict): reader thread writes, main thread reads
        - Dispatch (callbacks): reader thread schedules, main thread executes
    """
    def __init__(
        self,
        account_sub_cb: Callable[[str], int],
        account_unsub_cb: Callable[[int], None],
    ):
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
        self._accounts: dict[str, TrackedAccount] = {}
        self._snapshot_hooks: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future]] = {}
        self._stream_hooks: dict[str, tuple[loop, callback, on_error]] = {}
        self.summary_req_id: int | None = None
```

**Usage Patterns:**

```python
# Snapshot: Get all accounts (wait for summary if needed)
accounts = await account_tracker.all_accounts(timeout=5.0)

# Stream: Register callback for continuous updates
key = account_tracker.create_stream_hook(
    loop=asyncio.get_running_loop(),
    callback=async def on_update(tracked: TrackedAccount): ...,
    on_error=async def on_error(exc: ProviderException): ...,
)
account_tracker.remove_stream_hook(key)  # Cleanup
```

**IBSocket Integration:**

```python
# Reader thread callbacks
def managedAccounts(self, accountsList: str) -> None:
    """Called on connection - creates TrackedAccount for each account."""
    self._reader_accounts = accountsList.split(",")
    for account in self._reader_accounts:
        self.account_tracker.upsert_account(account)

def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
    """Called for each tag in reqAccountSummary() response."""
    self.account_tracker.update_account(account, tag, value, currency)

def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
    """Real-time P&L updates from reqPnL()."""
    self.account_tracker.update_pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)
```

### TWSBrokerProvider Integration

**Get Account Metadata:**

```python
async def get_account_info(self) -> AccountMetainfo:
    """Get account metadata from TWS."""
    account_list = await self._tws_client.reqAccountSummary()
    tracked_account = next(iter(account_list), None)
    assert tracked_account is not None, "Account summary returned no data"
    return tracked_account.metainfo()
```

**Get Equity Data:**

```python
async def get_equity(self) -> EquityData:
    """Get current equity data from TWS."""
    account_list = await self._tws_client.reqAccountSummary()
    tracked_account = next(iter(account_list), None)
    assert tracked_account is not None, "Account summary returned no data"
    return tracked_account.equity_data()
```

### Shared Utilities

**`isUnset()` Helper:**

Checks if TWS values are unset/placeholder (used throughout account and order tracking):

```python
def isUnset(value: Any) -> bool:
    """Check if a TWS value is considered 'unset' (default/placeholder)."""
    if value is None:
        return True
    if isinstance(value, (int, float)) and value == UNSET_DOUBLE:
        return True
    if isinstance(value, Decimal) and value == UNSET_DECIMAL:
        return True
    if isinstance(value, str) and value == "":
        return True
    return False
```

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
    async def get_account_info(self) -> AccountMetainfo  # Get account metadata from TWS via reqAccountSummary(). Returns first account from managed accounts list with ID, name, currency, and currency sign.
    async def get_equity(self) -> EquityData  # Get current equity data from TWS via reqAccountSummary(). Returns real-time balance, equity, and P&L values from TrackedAccount. Uses net_liquidation for equity, total_cash_value for balance, and real-time P&L from reqPnL() subscription.
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

- **Current Implementation**: `TWSBrokerProvider` has real TWS integration for order operations via `_submit_order()` which uses `TWSClient.placeOrderGroup()` and `req_ticker_details()`. Order streaming (`subscribe_orders()`) is fully TWS-backed via `OrderTracker`. Some features (positions, executions, equity streaming) still use in-memory state.
- **Order Streaming**: `subscribe_orders()` delegates to `TWSClient.reqOrdersStream()` which registers callbacks via `OrderTracker.create_stream_hook()`. Initial snapshot is triggered via `reqOpenOrders()` on subscription. Domain conversion uses `tracked_order_to_placed_order()`.
- **Session-Aware Routing**: Orders are routed via `_resolve_trading_contract()` which uses `CachedContract.build_best_contract()` to select SMART or OVERNIGHT exchange based on market hours.
- **Leverage Methods**: IBKR uses account-level margin, not per-symbol leverage. `preview_leverage()` and `set_leverage()` raise `ProviderException` (code: `PROVIDER_BROKER_LEVERAGE_NOT_SUPPORTED`). `get_leverage_info()` computes implied leverage via WhatIf margin simulation.
- **Inter-Module Price Fetch**: `_get_symbol_price()` uses `DatafeedClient` (inter-module HTTP) instead of direct TWS calls to maintain capability isolation. The client is instantiated once per provider with `InterModuleClients(caller_id="tws-broker-provider")` and requests are automatically HMAC-signed. See [AUTHENTICATION.md](../../../../docs/AUTHENTICATION.md#inter-module-hmac-authentication).
- **Order Preview**: Uses TWS `whatIf` mode for real margin/commission data (see section below).
- **Bracket Orders**: `edit_position_brackets()` implemented using OCA (One-Cancels-All) groups. Creates stop loss (STP/TRAIL) and take profit (LMT) orders linked so when one fills, TWS cancels the others.
- **Equity Streaming**: TWS doesn't push account changes; polling via `get_equity()` is required.
- **Client ID**: Broker uses `client_id=2` (default), separate from datafeed's `client_id=1`.

### Order Preview (whatIf Mode)

The `preview_order()` method uses TWS's native `whatIf` mode to obtain real margin requirements and commission estimates without actually placing the order.

**Implementation Flow:**

```
preview_order(PreOrder)
        │
        ├── 1. _resolve_trading_contract(symbol)
        │       └── req_ticker_details(ticker) → CachedContract
        │       └── cached.build_best_contract() → Contract (SMART or OVERNIGHT)
        │
        ├── 2. preorder_to_tws(order)  →  TWS Order (entry only, no brackets)
        │
        ├── 3. order.whatIf = True  ← Enable preview mode
        │
        ├── 4. TWSClient.placeWhatifOrder(contract, order)
        │       └── Returns TrackedOrder with OrderState containing:
        │           - initMarginChange (additional margin required)
        │           - maintMarginChange (maintenance margin)
        │           - commissionAndFees / min/max estimates
        │           - warningText (TWS warnings)
        │
        └── 5. order_state_to_preview_result()  →  OrderPreviewResult
```

**Session-Aware Contract Resolution:**

The `_resolve_trading_contract()` method provides automatic darkpool routing:

```python
async def _resolve_trading_contract(self, ticker: str) -> Contract:
    """Resolve contract for current trading session.

    Uses SMART by default. If regular session closed AND darkpool
    available, opportunistically routes to OVERNIGHT exchange (Blue Ocean ATS).
    """
    details = await self._tws_client.req_ticker_details(ticker)
    return details.build_best_contract()  # SMART or OVERNIGHT
```

**Key Design Decisions:**

1. **Entry Order Only**: Only the entry order is previewed. Bracket orders (stop loss, take profit) are exit orders that release margin, not consume it, so their preview is not needed.

2. **LMT Order Type for Accuracy**: Uses `orderType="LMT"` with current market price instead of `"MKT"`. Limit orders provide more accurate margin calculations because TWS can compute exact execution price, whereas market orders have variable execution prices. Price is fetched via `_get_symbol_price()` using inter-module DatafeedClient. Falls back to 100.0 if price unavailable. Same pattern used in `get_leverage_info()` (see implementation at lines 630-680).

3. **Error Propagation**: TWS errors propagate directly to the caller (BFF layer). The provider does not swallow errors with fallback responses—the BFF decides error handling strategy. This aligns with the "let it throw" philosophy in [ERROR-MANAGEMENT.md](../../../docs/ERROR-MANAGEMENT.md).

4. **Reuses Existing Methods**: Uses the existing `placeOrder()` method with `whatIf=True` flag rather than a dedicated preview method (DRY principle).

5. **Contract Not Found Fallback**: If the contract cannot be resolved (e.g., invalid ticker), a fallback preview with estimated values is returned. This is distinct from TWS connection errors which propagate.

**OrderState Fields Used:**

| TWS Field              | Domain Field            | Description                         |
| ---------------------- | ----------------------- | ----------------------------------- |
| `initMarginChange`     | Initial Margin Required | Additional margin needed for order  |
| `maintMarginChange`    | Maintenance Margin      | Post-order maintenance requirement  |
| `equityWithLoanChange` | Equity Impact           | Change in equity with loan value    |
| `initMarginAfter`      | Initial Margin (After)  | Total initial margin after order    |
| `commissionAndFees`    | Commission              | Exact commission (if known)         |
| `minCommissionAndFees` | Commission (Est.) min   | Min estimate when exact unknown     |
| `maxCommissionAndFees` | Commission (Est.) max   | Max estimate when exact unknown     |
| `warningText`          | warnings[]              | TWS-provided warning messages       |
| `rejectReason`         | errors[]                | Rejection reason (preview failures) |

**Example Response:**

```python
OrderPreviewResult(
    sections=[
        OrderPreviewSection(header="Order Details", rows=[...]),
        OrderPreviewSection(header="Margin Requirements", rows=[
            OrderPreviewSectionRow(title="Initial Margin Required", value="$5,000.00 USD"),
            OrderPreviewSectionRow(title="Maintenance Margin", value="$2,500.00 USD"),
        ]),
        OrderPreviewSection(header="Commission & Fees", rows=[
            OrderPreviewSectionRow(title="Commission", value="$1.50 USD"),
        ]),
    ],
    confirmId="abc123-...",
    warnings=["Market orders execute immediately at current market price"],
    errors=None,
)
```

**Mapper:** `order_state_to_preview_result()` in `tws_mappers.py` handles the OrderState → OrderPreviewResult conversion.

### Position Data Freshness

Position operations require **live position data** to avoid stale cache issues. The `_get_position_by_id()` helper ensures operations work with current state:

**Implementation Pattern:**

```python
async def _get_position_by_id(self, position_id: str) -> Position | None:
    """Get position by ID with fresh data."""
    positions = await self.get_positions()
    return next((p for p in positions if p.id == position_id), None)

async def close_position(self, position_id: str, amount: float | None = None) -> None:
    """Close position (full or partial)."""
    position = await self._get_position_by_id(position_id)  # ← Fresh lookup
    if not position:
        raise ProviderException(
            code="PROVIDER_BROKER_POSITION_NOT_FOUND",
            message=f"Position {position_id} not found",
            provider="tws",
            capability="broker",
        )
    # ... continue with fresh position data
```

**Usage:**

- `close_position()`: Validates current position quantity before closing
- `attach_brackets_to_position()`: Ensures bracket orders reference current position state

**Why Fresh Data?**

Position state can change between WebSocket updates and API calls (fills, partial closes, etc.). Using cached `self._positions` risks:

- Operating on stale quantity values
- Closing non-existent positions
- Bracket orders for wrong position size

**Trade-off:** Small performance cost (one async call) for guaranteed correctness.

### Order Modification Constraints

**[CRITICAL]** TWS only allows modification of specific order fields. Attempting to change other fields results in rejection.

**Modifiable Fields Only:**

| Field           | Type    | Notes                              |
| --------------- | ------- | ---------------------------------- |
| `lmtPrice`      | double  | For LMT, STP LMT, TRAIL orders     |
| `auxPrice`      | double  | Stop/trailing price for STP, TRAIL |
| `totalQuantity` | decimal | Can increase or decrease           |
| `tif`           | string  | **Only DAY → IOC** is recommended  |

**Implementation in `TWSClient._submit_order()`:**

Return type: `tuple[int, bool]` — `(order_id, place_flag)` where `place_flag=False` when no fields actually changed (skips TWS API call).

The method supports three resolution paths:

1. **Explicit Order ID** (`order_id > 0`): Modify existing order by ID
2. **OCA Reconciliation** (`order.ocaGroup` set): Find existing order via `OrderTracker.find_tracked_order(order)` - checks orderId first, then OCA group+type+action matching
3. **New Order** (neither above): Create new order with next available ID

When modifying (paths 1 or 2), the method:

1. Retrieves existing order via `OrderTracker.find_tracked_order(order)`
2. **Asserts immutable fields unchanged**: `contract.conId`, `contract.exchange`, `parentId`
3. Clones original via `TrackedOrder.clone_order()` for thread safety
4. Copies ONLY allowed fields from new order to clone **if values differ**
5. **No-op detection**: If no fields changed, returns `(order_id, False)` without calling TWS
6. **Forces transmit=True** for existing orders (overrides staged orders)
7. Submits clone only when `place_flag=True`

```python
# In tws_connection.py - _submit_order() -> tuple[int, bool]
order_id = order.orderId
place_flag = True

# Resolution: Explicit ID, OCA reconciliation, or new order
tracked: TrackedOrder | None = self.ibsocket.order_tracker.find_tracked_order(
    order,
)

if tracked:
    order_ori = tracked.clone_order()  # Deep copy for thread safety
    order_id = tracked.orderId

    # Immutable field guards
    assert tracked.contract.conId == contract.conId, "Cannot change contract"
    # ... asserts for exchange, parentId

    place_flag = False
    # Only copy allowed fields IF values differ
    if order.lmtPrice != UNSET_DOUBLE and order_ori.lmtPrice != order.lmtPrice:
        order_ori.lmtPrice = order.lmtPrice
        place_flag = True
    # ... similar for auxPrice, totalQuantity, tif

    order = order_ori
    order.transmit = True  # Always transmit existing orders
else:
    order_id = self.ibsocket.order_tracker.next_order_id
    order.parentId = parent_id
    order.orderId = order_id
    order.transmit = transmit

if place_flag:
    self.ibsocket.placeOrder(order_id, contract, order)
return order_id, place_flag
```

**`TrackedOrder.clone_order()` Method:**

Deep copies the Order object to avoid shared mutable state between threads:

- Shallow copies primitive fields via `__dict__.update()`
- Recreates nested objects (`SoftDollarTier`, `OrderComboLeg`)
- Uses `deepcopy()` for complex hierarchies (`conditions`)

**`TrackedOrder` Properties:**

| Property        | Type                                     | Description                                                                |
| --------------- | ---------------------------------------- | -------------------------------------------------------------------------- |
| `domain_status` | `OrderStatus`                            | Converts TWS status to domain enum (handles transitional states)           |
| `is_active`     | `bool`                                   | True if order is working/submitted (not filled/canceled)                   |
| `oca_group`     | `str \| None`                            | OCA group without timestamp suffix (e.g., `"brackets_100"`)                |
| `brackets_info` | `tuple[str \| None, ParentType \| None]` | Parses OCA to extract `(parent_id, parent_type)` for bracket orders        |
| `parent_filled` | `bool`                                   | True if parent order filled (converts order brackets to position brackets) |
| `clone_order()` | `Order`                                  | Deep copies Order for thread-safe modifications                            |

**Reference:** See [02-API-REFERENCE-CONTRACTS-ORDERS.md](../../external_packages/tws/docs/02-API-REFERENCE-CONTRACTS-ORDERS.md#32-order-modification) for official IB guidance.

**Order Status Mapping:**

| TWS Status      | Domain Status | Notes                                        |
| --------------- | ------------- | -------------------------------------------- |
| `PendingSubmit` | PLACING (4)   | Order sent, awaiting exchange acknowledgment |
| `PendingCancel` | PLACING (4)   | Cancel sent, awaiting confirmation           |
| `ApiPending`    | PLACING (4)   | Not yet sent to IB server                    |
| `PreSubmitted`  | WORKING (6)   | Simulated order held by IB, will execute     |
| `Submitted`     | WORKING (6)   | Active at exchange                           |
| `ApiCancelled`  | CANCELED (1)  | Cancelled via API                            |
| `Cancelled`     | CANCELED (1)  | Cancelled                                    |
| `Filled`        | FILLED (2)    | Order fully executed                         |
| `Inactive`      | INACTIVE (3)  | Error or held state                          |

> **Note:** `PreSubmitted` maps to WORKING because simulated orders (e.g., stop orders held by IB until trigger) are effectively active and should display as working in the UI.

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
    order_list: list[Order],
    oca_group: str,
    oca_type: int = 1,
    parent_id: int = 0,
    timeout: float | None = None,
) -> list[TrackedOrder]
```

**Parameters:**

| Parameter    | Type            | Description                                               |
| ------------ | --------------- | --------------------------------------------------------- |
| `contract`   | `Contract`      | The contract for all orders                               |
| `order_list` | `list[Order]`   | List of Order objects (e.g., stop loss + take profit)     |
| `oca_group`  | `str`           | Unique OCA group identifier (e.g., `bracket_pos123`)      |
| `oca_type`   | `int`           | OCA behavior type (default: 1)                            |
| `parent_id`  | `int`           | Parent order ID for bracket children (default: 0)         |
| `timeout`    | `float \| None` | Timeout for order confirmations (default: client timeout) |

**OCA Type Options:**

| Type | Name              | Description                                                 |
| ---- | ----------------- | ----------------------------------------------------------- |
| 1    | CANCEL_WITH_BLOCK | Cancel all remaining with overfill protection (recommended) |
| 2    | REDUCE_WITH_BLOCK | Proportionally reduce remaining with block                  |
| 3    | REDUCE_NO_BLOCK   | Proportionally reduce without block                         |

**Usage in `edit_position_brackets()`:**

```python
# Generate deterministic OCA group for position brackets
oca_group = f"brackets_{position_id}"  # e.g., "brackets_AAPL:NASDAQ:STK"

# Place bracket orders atomically via OCA group
tracked_orders = await self._tws_client.placeOcaGroup(
    contract, bracket_orders, oca_group, oca_type=1
)
```

### OCA Group Naming Convention

The codebase uses deterministic OCA naming with timestamps to enable bracket relationship reconstruction and prevent conflicts:

| Pattern                           | Example                              | `TrackedOrder.brackets_info` Returns       |
| --------------------------------- | ------------------------------------ | ------------------------------------------ |
| `brackets_{order_id}` (numeric)   | `brackets_100@1736726400000`         | `("100", ParentType.ORDER)`                |
| `brackets_{position_id}` (string) | `brackets_AAPL:NASDAQ:STK@timestamp` | `("AAPL:NASDAQ:STK", ParentType.POSITION)` |
| Other patterns                    | `some_other_oca`                     | `(None, None)`                             |

**Timestamp Suffix:** OCA groups are suffixed with `@{unix_timestamp_ms}` to ensure uniqueness across sessions. The base pattern (before `@`) is used for matching/reconciliation.

**Usage:** `get_orders()` uses `TrackedOrder.brackets_info` property to reconstruct bracket relationships from TWS open orders.

---

### Order Retrieval with Bracket Grouping

`get_orders()` returns enriched `PlacedOrder` objects with bracket relationships populated for TradingView UI display.

**Processing Flow:**

```
get_orders()
      │
      ├── 1. reqOpenOrders()  →  list[TrackedOrder]
      │       └── Filters out whatIf orders and non-transmitted orders
      │
      ├── 2. _group_orders_by_bracket(orders)
      │       ├── parents_map: standalone/parent orders
      │       ├── order_children: {"parent_id": [child orders]}  (parentId > 0 or OCA numeric)
      │       └── position_children: {"symbol": [child orders]}  (OCA symbol string)
      │       └── Uses TrackedOrder.brackets_info property for OCA parsing
      │
      ├── 3. For each parent with children:
      │       └── _build_bracket_context_from_children(children)
      │           └── Extract stopLoss/takeProfit from LMT/STP/TRAIL orders
      │
      └── 4. _group_and_map_tws_orders(orders, contracts_map)
              ├── Parent orders enriched with stopLoss/takeProfit
              ├── Child orders linked with parentId/parentType
              └── Uses TrackedOrder.parent_filled for position bracket detection
```

**Detection Priority:**

1. `tracked.parent_filled == True` → Child of POSITION bracket (parent filled, now protecting position)
2. `order.parentId > 0` → Child of ORDER bracket (TWS native linking)
3. `tracked.brackets_info` returns `ParentType.ORDER` → Child of ORDER bracket (via OCA)
4. `tracked.brackets_info` returns `ParentType.POSITION` → Child of POSITION bracket (via OCA)
5. Otherwise → Standalone or parent order

**Result Structure:**

```python
# Parent order (enriched with bracket prices from children)
PlacedOrder(
    id="100",
    symbol="AAPL",
    stopLoss=145.0,      # From STP child order
    takeProfit=160.0,    # From LMT child order
    parentId=None,
    parentType=None,
)

# Order bracket child
PlacedOrder(
    id="101",
    symbol="AAPL",
    parentId="100",
    parentType=ParentType.ORDER,
)

# Position bracket child (no parent order exists)
PlacedOrder(
    id="200",
    symbol="AAPL",
    parentId="AAPL:NASDAQ:STK",
    parentType=ParentType.POSITION,
)
```

**Helper Functions in `broker_provider.py`:**

| Function                                 | Description                                                          |
| ---------------------------------------- | -------------------------------------------------------------------- |
| `_group_orders_by_bracket()`             | Partitions orders into parents, order_children, position_children    |
| `_build_bracket_context_from_children()` | Extracts stopLoss/takeProfit/trailingStopPips from child order types |
| `_group_and_map_tws_orders()`            | Orchestrates grouping and mapping with bracket enrichment            |

---

## 5. Domain Models

**File:** `models/market.py` — Used by Service and Provider

| Model                    | Key Fields                                                                                                                                                    | Purpose         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `Bar`                    | `time`, `open`, `high`, `low`, `close`, `volume`                                                                                                              | OHLCV data      |
| `SearchSymbolResultItem` | `symbol`, `exchange`, `type`, `ticker`                                                                                                                        | Search results  |
| `SymbolInfo`             | Core: `name`, `type`, `session`, `timezone`, `pricescale`; P0: `currency_code`; P1: `expired`, `expiration_date`, `industry`, `sector`; P2: `con_id`, `delay` | Symbol metadata |
| `QuoteData`              | `n`, `s`, `v` (QuoteValues embedded)                                                                                                                          | Tick data       |
| `Resolution`             | `MIN_1`, `MIN_5`, `HOUR_1`, `DAY_1`, etc.                                                                                                                     | Resolution enum |

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

| Function                                  | Description                                                                      |
| ----------------------------------------- | -------------------------------------------------------------------------------- |
| `contract_description_to_search_result()` | `ContractDescription` → `SearchSymbolResultItem`                                 |
| `contract_details_to_symbol_info()`       | `ContractDetails` → `SymbolInfo`                                                 |
| `tws_bar_to_domain_bar()`                 | `BarData` → `Bar` (historical)                                                   |
| `tws_ticks_to_bar()`                      | `dict[str, Any]` → `Bar` (real-time)                                             |
| `tws_ticks_to_quote_data()`               | `dict[str, Any]` → `QuoteData`                                                   |
| `ticker_name()`                           | `Contract` → stream key string (`{exchange}:{symbol}[@{bar_size}]`)              |
| `parse_ticker()`                          | stream key → `tuple[symbol, exchange, bar_size \| None]`                         |
| `infer_sec_type()`                        | `(exchange, symbol)` → `str` (security type: STK, CASH, CRYPTO)                  |
| `build_smart_contract()`                  | ticker string → `Contract` with `exchange="SMART"`, secType inferred dynamically |
| `build_darkpool_contract()`               | ticker string → `Contract` with `exchange="OVERNIGHT"` for Blue Ocean ATS        |
| `map_resolution_to_tws_bar_size()`        | `Resolution` → TWS bar size string                                               |

**`contract_details_to_symbol_info()` Field Mappings:**

| SymbolInfo Field         | TWS Source                              | Notes                                            |
| ------------------------ | --------------------------------------- | ------------------------------------------------ |
| `currency_code`          | `contract.currency`                     | P0: Trading currency (USD, EUR, etc.)            |
| `original_currency_code` | `contract.currency`                     | P0: Original currency for conversion             |
| `expired`                | `lastTradeDateOrContractMonth` (parsed) | P1: True if expiration < now                     |
| `expiration_date`        | `lastTradeDateOrContractMonth` (parsed) | P1: Timestamp in ms (`_parse_expiration_date()`) |
| `industry`               | `ContractDetails.industry`              | P1: Industry classification                      |
| `sector`                 | `ContractDetails.category`              | P1: Sector/category                              |
| `con_id`                 | `contract.conId`                        | P2: IB unique contract ID                        |

### Broker Mappers

| Function                                | Description                                                                                                                                                                                                                    |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `brackets_to_tws()`                     | `Brackets` → `(Order \| None, Order \| None)` — stop_loss, take_profit. Shared by `preorder_to_tws()` and `edit_position_brackets()`. Infers stop type from `trailingStopPips` presence.                                       |
| `preorder_to_tws()`                     | `PreOrder` → `(Order, Order \| None, Order \| None)` — parent, stop_loss, take_profit. Delegates bracket creation to `brackets_to_tws()`. Child orders created without OCA linking (managed by `TWSClient.placeOrderGroup()`). |
| `tracked_order_to_placed_order()`       | `TrackedOrder` → `PlacedOrder`. Accepts optional `BracketContext` to enrich parent orders with bracket prices. Uses `TrackedOrder.domain_status`, `brackets_info`, `parent_filled` properties.                                 |
| `isUnset()`                             | Checks if TWS value equals `UNSET_DOUBLE`, `UNSET_DECIMAL`, `None`, or `""` — used for safe float conversions in mapper functions.                                                                                             |
| `tws_position_to_domain()`              | position data dict → `Position`                                                                                                                                                                                                |
| `tws_account_summary_to_equity()`       | summary dict → `EquityData`                                                                                                                                                                                                    |
| `tws_account_summary_to_account_info()` | summary dict → `AccountMetainfo`                                                                                                                                                                                               |
| `calculate_tws_duration()`              | time range → TWS duration string                                                                                                                                                                                               |
| `order_state_to_preview_result()`       | `OrderState` + `PreOrder` → `OrderPreviewResult` — converts TWS whatIf response to domain preview with margin, commission, and warnings sections.                                                                              |

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
    "business_key": "datafeed:Quote:SMART:NASDAQ:AAPL",
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
async def subscribe_realtime_bars(self, ticker_name: str, resolution: Resolution, callback, on_error) -> str:
    bar_size = map_resolution_to_tws_bar_size(resolution)

    async def bar_callback(rt_data: dict[str, Any], fields: list[str] | None) -> None:
        await callback(tws_ticks_to_bar(rt_data))

    cached = await self._tws_client.req_ticker_details(ticker_name)
    contract = cached[0].contract
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

OCA groups use the **transmit chain pattern** for atomic submission with automatic reconciliation:

```python
# TWSClient.placeOcaGroup() - Atomic bracket order submission with reconciliation
async def placeOcaGroup(self, contract, children, oca_group, oca_type=1, parent_id=0, timeout=None):
    if not oca_group.startswith("brackets_"):
        raise ValueError("oca_group must start with 'brackets_'")

    # Check for existing OCA group and determine transmit strategy
    transmit_all = False
    signed_oca_group = self.ibsocket.order_tracker.find_oca_group(oca_group)
    if signed_oca_group:
        transmit_all = True  # Existing group - transmit all orders immediately
    else:
        signed_oca_group = f"{oca_group}@{int(time.time() * 1000)}"

    # Assign OCA attributes to all orders
    for order in children:
        order.ocaGroup = signed_oca_group
        order.ocaType = oca_type

    # Transmit chain: staged (transmit=False) for new groups, immediate for updates
    # _submit_order() checks OrderTracker.find_tracked_order() for existing orders
    submit_results = [
        self._submit_order(
            contract, order, parent_id=parent_id, transmit=transmit_all
        )
        for order in children[:-1]
    ]
    submit_results.append(
        self._submit_order(contract, children[-1], parent_id=parent_id, transmit=True)
    )

    # Await all order confirmations with timeout
    return await asyncio.gather(*[
        self.ibsocket.order_tracker.order_update(oid, timeout=timeout)
        for (oid, _) in submit_results
    ])
```

**Key Points:**

- **Timestamp Uniqueness**: Appends `@{unix_ms}` to OCA group if new, reuses existing if found via `find_oca_group()`
- **Reconciliation**: `_submit_order()` checks `OrderTracker.find_tracked_order()` to detect existing orders by orderId first, then OCA group+type+action
- **Modification Detection**: If existing order found, modifies it instead of creating duplicate
- **Transmit Strategy**: New OCA groups use chain pattern (`transmit=False` → `True`); existing groups transmit all immediately (`transmit_all=True`)
- **Atomic Submission**: TWS processes all orders as a unit, preventing partial fills
- **OCA Enforcement**: When one fills, others are automatically canceled by TWS

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
mock_client.reqQuoteSnapshot.return_value = {"ticker_name": "NASDAQ:AAPL"}

# For sync methods that return stream keys
mock_client = Mock()
mock_client.reqBarDataStream = Mock(return_value="NASDAQ:AAPL@5 mins")

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
