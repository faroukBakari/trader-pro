# TWS Provider

**Status:** Production-Ready (Datafeed + Broker Capabilities)  
**Architecture:** Three-Layer Streaming Pattern  
**Last Updated:** January 16, 2026

---

## Quick Reference

| Layer                       | File                                  | Responsibility                                                                                                                                                                          |
| --------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **3 - TWSDatafeedProvider** | `datafeed_provider.py`                | DatafeedCapability impl, domain conversion                                                                                                                                              |
| **3 - TWSBrokerProvider**   | `broker_provider.py`                  | BrokerCapability impl, order/position management                                                                                                                                        |
| **2 - TWSClient**           | `tws_connection.py`                   | AsyncIO facade, stream management, owns IBSocket                                                                                                                                        |
| **1 - IBSocket**            | `tws_connection.py`                   | Raw TCP, daemon thread, business key registry                                                                                                                                           |
| **Wiring Interfaces**       | `wiring_interfaces.py`                | Abstract interfaces for component composition (IbSocketWiringInterface, QuoteTrackerCBWiringInterface, BarsTrackerCBWiringInterface)                                                    |
| **CachedContract**          | `cached_contract.py`                  | Contract caching (description → full details)                                                                                                                                           |
| **ContractTracker**         | `contract_tracker.py`                 | Contract persistence with SQLite + lazy loading                                                                                                                                         |
| **QuoteTracker**            | `quote_tracker.py`                    | Quote subscription management with interface-based wiring, centralized snapshot/stream hooks, refcount logic                                                                            |
| **BarsTracker**             | `bars_tracker.py`                     | Bar data management with interface-based wiring, timezone-aware conversion, snapshot/stream patterns                                                                                    |
| **OrderTracker**            | `order_tracker.py`                    | Order state tracking with interface-based wiring, TWS protocol internalization (placeOrder/cancelOrder), status mapping, OCA reconciliation, parent-child dispatch, lazy initialization |
| **PositionTracker**         | `position_tracker.py`                 | Position state tracking with interface-based wiring, lazy initialization, snapshot/stream patterns                                                                                      |
| **AccountTracker**          | `account_tracker.py`                  | Account state tracking with interface-based wiring, TWS protocol internalization (**req_account_summary/**req_pnl), snapshot/stream patterns, lazy initialization                       |
| **ExecutionTracker**        | `execution_tracker.py`                | Execution tracking with interface-based wiring, commission joining, two-phase dispatch pattern, lazy initialization                                                                     |
| **Mappers**                 | `tws_mappers.py`                      | TWS ↔ domain model conversion, ticker parsing                                                                                                                                           |
| **Models**                  | `tws_models.py`                       | `StreamData`, `AssetConfig`, error classification                                                                                                                                       |
| **Config**                  | `models/providers/tws/tws_configs.py` | `TWS_*` env vars, Pydantic settings                                                                                                                                                     |

**Tests:** `providers/tws/tests/test_{client,ibsocket,mappers,models,datafeed_provider,broker_provider,cached_contract,contract_tracker,quote_tracker,config}.py`

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
TWSClient (Layer 2) ─── owns IBSocket, async facade, Tracker orchestration
        │ CachedContract cache, coordinates tracker components
        ▼
IBSocket (Layer 1) ─── daemon thread _reader_task(), wiring interface implementation
        │ callback routing to wired trackers
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
quote_tracker.subscribe(ticker, callback)        tickPrice(reqId, price)
        │ (wire_quote_tracker binds)            │
        │                                quote_tracker.update(tws_key, tick_data)
        │                                        │
callback(data) ◄──────────────────────── loop.call_soon_threadsafe(...)
```

**Key Patterns:**

- **Lazy Connection**: `TWSClient.ibsocket` connects on first access
- **Lazy Tracker Initialization**: `TWSClient.position_tracker` property creates tracker on first access
- **Business Key System**: External API uses business keys (e.g., `datafeed:Quote:SMART:AAPL:...`)

**Dependency Inversion Pattern (January 2026):**

Components now communicate via abstract interfaces instead of callback injection:

- **IbSocketWiringInterface**: Socket abstraction providing `next_req_id` property and `send_message()` method
- **QuoteTrackerCBWiringInterface**: QuoteTracker callback contract defining `update()` and `raise_error()` methods
- **BarsTrackerCBWiringInterface**: BarsTracker callback contract defining `update()`, `flag_complete()`, and `raise_error()` methods
- **Benefits**: Cleaner testing (mock interfaces), single source of truth for TWS protocol logic, reduced coupling

**Before (Hook Injection):**

```python
quote_tracker = QuoteTracker(
    quote_request_hook=lambda c: ibsocket._reqQuote(c),
    quote_cancel_hook=lambda rid: ibsocket._cancelQuote(rid),
    timeout=10
)
```

**After (Interface Composition):**

```python
# IBSocket implements IbSocketWiringInterface
# QuoteTracker/BarsTracker implement their respective CB interfaces
quote_tracker = QuoteTracker(ibsocket=self.ibsocket, timeout=10)
bars_tracker = BarsTracker(ibsocket=self.ibsocket, timeout=30)
```

See: `wiring_interfaces.py` for interface definitions, section 2.7 for QuoteTracker details, section 2.8 for BarsTracker details

**Quote Subscription Pattern:**

- **Centralized Hooks**: `QuoteTracker` owns `_snapshot_hooks` and `_stream_hooks` (not per-`TrackedQuote`)
- **Reference Counting**: Tracker manages subscription refcount - unsubscribe only when last consumer disconnects
- **Symbol Deduplication**: Multiple topics requesting same symbol share underlying TWS subscription

**Connection Lifecycle Logging:**

IBSocket creation and recreation is logged to track connection state:

```python
# In TWSClient.__init__ or lazy connection logic
logger.warning(f"Creating new IBSocket with client_id={client_id}")
# OR
logger.warning(f"Recreating IBSocket with client_id={client_id}")
```

**Warning Level Rationale**: Connection creation is an important lifecycle event that should be visible in production logs without DEBUG level verbosity. Helps diagnose:

- Unexpected reconnections (network issues, TWS restarts)
- Multiple socket instances (misconfigured client IDs)
- Connection churn patterns (frequent disconnect/reconnect cycles)

**Lifecycle Events:**

| Event              | Log Level | Message                                     |
| ------------------ | --------- | ------------------------------------------- |
| Socket creation    | WARNING   | "Creating new IBSocket with client_id={id}" |
| Socket recreation  | WARNING   | "Recreating IBSocket with client_id={id}"   |
| Connection success | INFO      | "Connected to TWS/Gateway at {host}:{port}" |
| Disconnection      | WARNING   | "Disconnected from TWS (reason: {reason})"  |

**Client ID Context**: Logs include `client_id` to distinguish between datafeed (client_id=1) and broker (client_id=2) connections.

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

---

## 2.3 Wiring Interfaces (Dependency Inversion)

**File:** `wiring_interfaces.py`

Abstract interfaces enabling component composition via dependency inversion principle.

### IbSocketWiringInterface

Socket abstraction for TWS communication:

```python
class IbSocketWiringInterface(ABC):
    """Socket wiring contract for tracker components."""

    @property
    @abstractmethod
    def next_req_id(self) -> int:
        """Allocate and return next TWS request ID (thread-safe)."""
        pass

    @abstractmethod
    def send_message(self, msgId: int, values: list[object]) -> None:
        """Send TWS protocol message (thread-safe).

        Args:
            msgId: TWS message identifier (e.g., OUT.REQ_MKT_DATA)
            values: Message field values per TWS protocol spec
        """
        pass

    @abstractmethod
    def wire_quote_tracker(self, tracker: "QuoteTrackerCBWiringInterface") -> None:
        """Wire QuoteTracker for callback routing."""
        pass

    @abstractmethod
    def wire_bars_tracker(self, tracker: "BarsTrackerCBWiringInterface") -> None:
        """Wire BarsTracker for callback routing."""
        pass

    @abstractmethod
    def wire_contract_tracker(self, tracker: "ContractTrackerCBWiringInterface") -> None:
        """Wire ContractTracker for callback routing."""
        pass
```

**Implementors:**

- `IBSocket` in `tws_connection.py` (production)
- `mock_ibsocket` fixture in tests (testing)

**Usage Example:**

```python
# Allocate request ID
req_id = self.ibsocket.next_req_id

# Build TWS message
fields = [2, req_id, contract.conId, contract.symbol, ...]

# Send to TWS
self.ibsocket.send_message(OUT.REQ_MKT_DATA, fields)
```

### QuoteTrackerCBWiringInterface

Tracker callback contract for quote updates:

```python
class QuoteTrackerCBWiringInterface(ABC):
    """Quote tracker callback contract."""

    @abstractmethod
    def update(self, req_id: int, updates: dict[str, int | float | str]) -> None:
        """Dispatch quote field updates to registered hooks (thread-safe).

        Called from reader thread (TWS callbacks).
        """
        pass

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        """Dispatch subscription-level errors to hooks (thread-safe).

        Returns: True if error handlers found, False otherwise
        """
        pass
```

**Implementors:**

- `QuoteTracker` in `quote_tracker.py`

### BarsTrackerCBWiringInterface

Tracker callback contract for bar data updates:

```python
class BarsTrackerCBWiringInterface(ABC):
    """Bars tracker callback contract."""

    @abstractmethod
    def update(self, req_id: int, bar: "BarData") -> None:
        """Dispatch bar update to registered hooks (thread-safe).

        Called from reader thread (historicalData, historicalDataUpdate callbacks).
        """
        pass

    @abstractmethod
    def flag_complete(self, req_id: int, start: str, end: str) -> None:
        """Signal historical data request completion (thread-safe).

        Called from reader thread (historicalDataEnd callback).
        """
        pass

    @abstractmethod
    def raise_error(self, req_id: int, exception: "ProviderException") -> bool:
        """Dispatch subscription-level errors to hooks (thread-safe).

        Returns: True if error handlers found, False otherwise
        """
        pass
```

**Implementors:**

- `BarsTracker` in `bars_tracker.py`

### ContractTrackerCBWiringInterface

Tracker callback contract for contract data updates:

```python
class ContractTrackerCBWiringInterface(ABC):
    """Contract tracker callback contract."""

    @abstractmethod
    def update_descriptions(
        self, req_id: int, descriptions: list["ContractDescription"]
    ) -> None:
        """Dispatch contract descriptions from symbolSamples callback (thread-safe).

        Called from reader thread (TWS callbacks).
        """
        pass

    @abstractmethod
    def update_details(self, req_id: int, details: "ContractDetails") -> None:
        """Dispatch contract details from contractDetails callback (thread-safe).

        Called from reader thread (TWS callbacks).
        """
        pass

    @abstractmethod
    def flag_details_complete(self, req_id: int) -> None:
        """Mark contract details request complete (thread-safe).

        Called from reader thread (contractDetailsEnd callback).
        """
        pass

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        """Dispatch contract request errors to hooks (thread-safe).

        Returns: True if error handlers found, False otherwise
        """
        pass
```

**Implementors:**

- `ContractTracker` in `contract_tracker.py`

**Bidirectional Wiring:**

```python
# ContractTracker constructor
def __init__(self, ibsocket: IbSocketWiringInterface, db_path: str | None = None):
    self.ibsocket = ibsocket
    self.ibsocket.wire_contract_tracker(self)  # ← Register for callbacks
    # ...

# IBSocket stores reference
def wire_contract_tracker(self, tracker: ContractTrackerCBWiringInterface):
    self._contract_tracker = tracker

# IBSocket callbacks route to tracker
def symbolSamples(self, reqId: int, descriptions: list[ContractDescription]):
    if self._contract_tracker:
        self._contract_tracker.update_descriptions(reqId, descriptions)

def contractDetails(self, reqId: int, details: ContractDetails):
    if self._contract_tracker:
        self._contract_tracker.update_details(reqId, details)

def contractDetailsEnd(self, reqId: int):
    if self._contract_tracker:
        self._contract_tracker.flag_details_complete(reqId)
```

**Comparison with Other Trackers:**

| Aspect              | QuoteTracker                     | BarsTracker                         | ContractTracker                                     |
| ------------------- | -------------------------------- | ----------------------------------- | --------------------------------------------------- |
| Wiring Method       | `wire_quote_tracker(tracker)`    | `wire_bars_tracker(tracker)`        | `wire_contract_tracker(tracker)`                    |
| Update Callback     | `update(req_id, updates)`        | `update(req_id, bar_data)`          | `update_descriptions()` / `update_details()`        |
| Completion Callback | _(none - continuous streaming)_  | `flag_complete(req_id, start, end)` | `flag_details_complete(req_id)`                     |
| Error Callback      | `raise_error(req_id, exception)` | `raise_error(req_id, exception)`    | `raise_error(req_id, exception)`                    |
| Request Messages    | `OUT.REQ_MKT_DATA`               | `OUT.REQ_HISTORICAL_DATA`           | `OUT.REQ_MATCHING_SYMBOLS`, `OUT.REQ_CONTRACT_DATA` |
| Cancel Messages     | `OUT.CANCEL_MKT_DATA`            | `OUT.CANCEL_HISTORICAL_DATA`        | _(none - one-shot requests)_                        |

**Rationale:**

This pattern enables:

1. **Single Source of Truth**: TWS protocol logic lives in tracker, not duplicated in IBSocket
2. **Cleaner Testing**: Mock interfaces instead of complex hook injection
3. **Reduced Coupling**: Components depend on abstractions, not concrete implementations
4. **Future Extensibility**: Other trackers (OrderTracker, PositionTracker) can adopt same pattern

### PositionTrackerCBWiringInterface

Tracker callback contract for position updates:

```python
class PositionTrackerCBWiringInterface(ABC):
    """Position tracker callback contract."""

    @abstractmethod
    def upsert_position(
        self,
        account: str,
        contract: Contract,
        position: Decimal,
        avgCost: float,
    ) -> None:
        """Dispatch position update to registered hooks (thread-safe).

        Called from reader thread (position callback).
        """
        pass

    @abstractmethod
    def mark_snapshot_complete(self) -> None:
        """Signal position snapshot completion (thread-safe).

        Called from reader thread (positionEnd callback).
        """
        pass

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None:
        """Dispatch position request errors to hooks (thread-safe).

        Called from reader thread when position request fails.
        """
        pass
```

**Implementors:**

- `PositionTracker` in `position_tracker.py`

**Bidirectional Wiring:**

```python
# PositionTracker constructor
def __init__(self, ibsocket: IbSocketWiringInterface):
    self.ibsocket = ibsocket
    self.ibsocket.wire_position_tracker(self)  # ← Register for callbacks
    # ...

# IBSocket stores reference
def wire_position_tracker(self, tracker: PositionTrackerCBWiringInterface):
    self._position_tracker = tracker

# IBSocket callbacks route to tracker
def position(self, account: str, contract: Contract, position: Decimal, avgCost: float):
    if self._position_tracker:
        self._position_tracker.ensure_snapshot_requested()  # Auto-request
        self._position_tracker.upsert_position(account, contract, position, avgCost)

def positionEnd(self):
    if self._position_tracker:
        self._position_tracker.mark_snapshot_complete()
```

**Comparison with Other Trackers:**

| Aspect              | QuoteTracker                     | BarsTracker                         | ContractTracker                  | PositionTracker                        |
| ------------------- | -------------------------------- | ----------------------------------- | -------------------------------- | -------------------------------------- |
| Wiring Method       | `wire_quote_tracker(tracker)`    | `wire_bars_tracker(tracker)`        | `wire_contract_tracker(tracker)` | `wire_position_tracker(tracker)`       |
| Update Callback     | `update(req_id, updates)`        | `update(req_id, bar_data)`          | `update_descriptions()` / `...`  | `upsert_position(account, ...)`        |
| Completion Callback | _(none - continuous streaming)_  | `flag_complete(req_id, start, end)` | `flag_details_complete(req_id)`  | `mark_snapshot_complete()`             |
| Error Callback      | `raise_error(req_id, exception)` | `raise_error(req_id, exception)`    | `raise_error(req_id, exception)` | `raise_error(exception)` (no req_id)   |
| Request Messages    | `OUT.REQ_MKT_DATA`               | `OUT.REQ_HISTORICAL_DATA`           | `OUT.REQ_MATCHING_SYMBOLS`       | `OUT.REQ_POSITIONS`                    |
| Cancel Messages     | `OUT.CANCEL_MKT_DATA`            | `OUT.CANCEL_HISTORICAL_DATA`        | _(none - one-shot requests)_     | `OUT.CANCEL_POSITIONS`                 |
| Error Routing       | By req_id                        | By req_id                           | By req_id                        | By nature (global subscription errors) |

**Unique Aspects of PositionTracker:**

1. **No Request ID**: Position subscription is global (single stream per account), no per-request tracking
2. **Auto-Request**: `ensure_snapshot_requested()` sends `OUT.REQ_POSITIONS` on first callback
3. **Error Routing by Nature**: Position errors (codes 200, 321, 322) routed via `TWSErrorNature.POSITION` classification
4. **Lazy Initialization**: `TWSClient.position_tracker` property creates tracker on first access (not owned by IBSocket)

**See:** Section 2.7 for QuoteTracker implementation, Section 2.8 for BarsTracker implementation, Section 2.9 for PositionTracker implementation, Section 2.10 for ExecutionTracker implementation

### ExecutionTrackerCBWiringInterface

Tracker callback contract for execution updates with commission joining:

```python
class ExecutionTrackerCBWiringInterface(ABC):
    """Execution tracker callback contract with two-phase dispatch."""

    @abstractmethod
    def upsert_execution(
        self,
        req_id: int,
        contract: Contract,
        execution: Execution,
    ) -> None:
        """Dispatch execution update to registered hooks (thread-safe).

        Called from reader thread (execDetails callback).
        First phase of two-phase dispatch - execution data without commission.
        """
        pass

    @abstractmethod
    def update_commission(
        self,
        exec_id: str,
        commission_report: CommissionAndFeesReport,
    ) -> None:
        """Update existing execution with commission data (thread-safe).

        Called from reader thread (commissionAndFeesReport callback).
        Second phase of two-phase dispatch - joins commission with execution.
        """
        pass

    @abstractmethod
    def mark_snapshot_complete(self, req_id: int) -> None:
        """Signal execution snapshot completion (thread-safe).

        Called from reader thread (execDetailsEnd callback).
        """
        pass

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> None:
        """Dispatch execution request errors to hooks (thread-safe).

        Called from reader thread when execution request fails.
        """
        pass
```

**Implementors:**

- `ExecutionTracker` in `execution_tracker.py`

**Bidirectional Wiring:**

```python
# ExecutionTracker constructor
def __init__(self, ibsocket: IbSocketWiringInterface):
    self.ibsocket = ibsocket
    self.ibsocket.wire_execution_tracker(self)  # ← Register for callbacks
    # ...

# IBSocket stores reference
def wire_execution_tracker(self, tracker: ExecutionTrackerCBWiringInterface):
    self.__execution_tracker = tracker

# IBSocket callbacks route to tracker
def execDetails(self, reqId: int, contract: Contract, execution: Execution):
    if self.__execution_tracker:
        self.__execution_tracker.upsert_execution(reqId, contract, execution)

def commissionAndFeesReport(self, commissionReport: CommissionAndFeesReport):
    if self.__execution_tracker:
        self.__execution_tracker.update_commission(
            commissionReport.execId, commissionReport
        )

def execDetailsEnd(self, reqId: int):
    if self.__execution_tracker:
        self.__execution_tracker.mark_snapshot_complete(reqId)
```

**Comparison - PositionTracker vs ExecutionTracker:**

| Aspect              | PositionTracker                       | ExecutionTracker                           |
| ------------------- | ------------------------------------- | ------------------------------------------ |
| Wiring Method       | `wire_position_tracker(tracker)`      | `wire_execution_tracker(tracker)`          |
| Update Callback     | `upsert_position(account, ...)`       | `upsert_execution(req_id, contract, exec)` |
| Join Callback       | _(none)_                              | `update_commission(exec_id, report)`       |
| Completion Callback | `mark_snapshot_complete()`            | `mark_snapshot_complete(req_id)`           |
| Error Callback      | `raise_error(exception)` (no req_id)  | `raise_error(req_id, exception)`           |
| Request Messages    | `OUT.REQ_POSITIONS`                   | `OUT.REQ_EXECUTIONS + PROTOBUF_MSG_ID`     |
| Cancel Messages     | `OUT.CANCEL_POSITIONS`                | _(none - snapshot only)_                   |
| Dispatch Pattern    | Single-phase                          | Two-phase (exec → commission join)         |
| Lazy Initialization | `TWSClient.position_tracker` property | `TWSClient.execution_tracker` property     |

**Unique Aspects of ExecutionTracker:**

1. **Two-Phase Dispatch**: Executions arrive via `execDetails`, commissions via `commissionAndFeesReport` with join by `exec_id`
2. **Protobuf Request**: Uses `send_protobuf()` for `OUT.REQ_EXECUTIONS` (vs `send_message()` for positions)
3. **Request ID Tracking**: Execution requests use req_id for completion/error correlation
4. **Commission Joining**: `update_commission()` enriches existing `TrackedExecution` and re-dispatches to hooks

### OrderTrackerCBWiringInterface

Tracker callback contract for order updates:

```python
class OrderTrackerCBWiringInterface(ABC):
    """Order tracker callback contract."""

    @abstractmethod
    def upsert_order(
        self,
        orderId: int,
        contract: Contract,
        order: Order,
        orderState: OrderState,
    ) -> None:
        """Create or replace TrackedOrder from openOrder callback (thread-safe).

        Called from reader thread (TWS callbacks).
        """
        pass

    @abstractmethod
    def update_status(
        self,
        orderId: int,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ) -> None:
        """Update TrackedOrder from orderStatus callback (thread-safe).

        Called from reader thread (TWS callbacks).
        Mutates stored Order and OrderState objects directly.
        """
        pass

    @abstractmethod
    def mark_snapshot_complete(self) -> None:
        """Signal order snapshot completion (thread-safe).

        Called from reader thread (openOrderEnd callback).
        """
        pass

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None:
        """Dispatch order request errors to hooks (thread-safe).

        Called from reader thread when order request fails.
        No req_id - errors dispatched to all hooks (global subscription).
        """
        pass
```

**Implementors:**

- `OrderTracker` in `order_tracker.py`

**Bidirectional Wiring:**

```python
# OrderTracker constructor
def __init__(self, ibsocket: IbSocketWiringInterface):
    self.ibsocket = ibsocket
    self.next_order_id: int = self.ibsocket.wire_order_tracker(self)  # ← Returns next_order_id!
    # ...

# IBSocket stores reference and returns next_order_id
def wire_order_tracker(self, tracker: OrderTrackerCBWiringInterface) -> int | None:
    self.__order_tracker = tracker
    return self.__next_order_id  # Unique: returns order ID for initialization

# IBSocket callbacks route to tracker
def openOrder(
    self, orderId: int, contract: Contract, order: Order, orderState: OrderState
):
    if self.__order_tracker:
        self.__order_tracker.upsert_order(orderId, contract, order, orderState)

def orderStatus(
    self,
    orderId: int,
    status: str,
    filled: Decimal,
    remaining: Decimal,
    avgFillPrice: float,
    permId: int,
    parentId: int,
    lastFillPrice: float,
    clientId: int,
    whyHeld: str,
    mktCapPrice: float,
):
    if self.__order_tracker:
        self.__order_tracker.update_status(
            orderId, status, filled, remaining, avgFillPrice, permId,
            parentId, lastFillPrice, clientId, whyHeld, mktCapPrice
        )

def openOrderEnd(self):
    if self.__order_tracker:
        self.__order_tracker.mark_snapshot_complete()

def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str):
    # ... (other error routing)
    nature = classify_error(errorCode, errorString)
    if nature == TWSErrorNature.ORDER:
        if self.__order_tracker:
            exception = ProviderException(
                error_code=f"TWS_{errorCode}",
                message=errorString,
                category="tws_error"
            )
            self.__order_tracker.raise_error(exception)
```

**Comparison - OrderTracker vs ExecutionTracker vs PositionTracker:**

| Aspect              | OrderTracker                           | ExecutionTracker                           | PositionTracker                       |
| ------------------- | -------------------------------------- | ------------------------------------------ | ------------------------------------- |
| Wiring Method       | `wire_order_tracker(tracker)`          | `wire_execution_tracker(tracker)`          | `wire_position_tracker(tracker)`      |
| **Wiring Returns**  | **next_order_id (int \| None)**        | _(void)_                                   | _(void)_                              |
| Update Callback     | `upsert_order(orderId, contract, ...)` | `upsert_execution(req_id, contract, exec)` | `upsert_position(account, ...)`       |
| Join Callback       | _(none)_                               | `update_commission(exec_id, report)`       | _(none)_                              |
| Status Callback     | `update_status(orderId, status, ...)`  | _(none)_                                   | _(none)_                              |
| Completion Callback | `mark_snapshot_complete()`             | `mark_snapshot_complete(req_id)`           | `mark_snapshot_complete()`            |
| Error Callback      | `raise_error(exception)` (no req_id)   | `raise_error(req_id, exception)`           | `raise_error(exception)` (no req_id)  |
| Request Messages    | `OUT.REQ_OPEN_ORDERS`                  | `OUT.REQ_EXECUTIONS + PROTOBUF_MSG_ID`     | `OUT.REQ_POSITIONS`                   |
| Place Messages      | `OUT.PLACE_ORDER + PROTOBUF_MSG_ID`    | _(none)_                                   | _(none)_                              |
| Cancel Messages     | `OUT.CANCEL_ORDER + PROTOBUF_MSG_ID`   | _(none - snapshot only)_                   | `OUT.CANCEL_POSITIONS`                |
| Dispatch Pattern    | Single-phase                           | Two-phase (exec → commission join)         | Single-phase                          |
| Lazy Initialization | `TWSClient.order_tracker` property     | `TWSClient.execution_tracker` property     | `TWSClient.position_tracker` property |

**Unique Aspects of OrderTracker:**

1. **next_order_id Return**: `wire_order_tracker()` returns `int | None` for order ID initialization (unique among all trackers)
2. **TWS Protocol Internalization**: OrderTracker sends `OUT.PLACE_ORDER` and `OUT.CANCEL_ORDER` via `send_protobuf()`
3. **Status Updates**: Separate `update_status()` callback mutates existing TrackedOrder (vs ExecutionTracker's commission join)
4. **No Request ID**: Order subscription is global, errors dispatched to all hooks (like PositionTracker)
5. **Internal Submission Logic**: Private `__submit_order()` handles reconciliation, no-op detection, immutable field guards

### AccountTrackerCBWiringInterface

Tracker callback contract for account updates:

```python
class AccountTrackerCBWiringInterface(ABC):
    """Account tracker callback contract."""

    @abstractmethod
    def upsert_account(self, account: str) -> None:
        """Create or update TrackedAccount from managedAccounts callback (thread-safe).

        Called from reader thread (TWS callbacks).
        """
        pass

    @abstractmethod
    def update_account(self, account: str, tag: str, value: str, currency: str) -> None:
        """Update TrackedAccount field from accountSummary callback (thread-safe).

        Called from reader thread (TWS callbacks).
        Maps TWS tag names to TrackedAccount fields.
        """
        pass

    @abstractmethod
    def update_pnl(
        self, reqId: int, daily: float, unrealized: float, realized: float
    ) -> None:
        """Update TrackedAccount P&L from pnl callback (thread-safe).

        Called from reader thread (TWS callbacks).
        Real-time P&L updates from reqPnL subscription.
        """
        pass

    @abstractmethod
    def update_account_time(self, timestamp: str) -> None:
        """Update last_update_time on all tracked accounts (thread-safe).

        Called from reader thread (updateAccountTime callback).
        """
        pass

    @abstractmethod
    def mark_summary_complete(self) -> None:
        """Signal account summary completion (thread-safe).

        Called from reader thread (accountSummaryEnd callback).
        """
        pass

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None:
        """Dispatch account request errors to hooks (thread-safe).

        Called from reader thread when account request fails.
        """
        pass
```

**Implementors:**

- `AccountTracker` in `account_tracker.py`

**Bidirectional Wiring:**

```python
# AccountTracker constructor
def __init__(self, ibsocket: IbSocketWiringInterface):
    self.ibsocket = ibsocket
    account_list = self.ibsocket.wire_account_tracker(self)  # ← Returns accounts list!
    for account in account_list.split(","):
        self.upsert_account(account)
    # ...

# IBSocket stores reference and returns accounts list
def wire_account_tracker(self, tracker: AccountTrackerCBWiringInterface) -> str:
    self.__account_tracker = tracker
    assert (
        self.__accounts_list is not None
    ), "Accounts list should be set as part of the socket connection setup."
    return self.__accounts_list  # Unique: returns accounts list from managedAccounts

# IBSocket callbacks route to tracker
def managedAccounts(self, accountsList: str):
    # Store accounts list for wiring, route to tracker if wired
    assert (
        self.__account_tracker is not None or self.__accounts_list is None
    ), "Unexpected managedAccounts callback: account tracker already wired."
    self.__accounts_list = accountsList
    if self.__account_tracker is not None:
        accounts = accountsList.split(",")
        for account in accounts:
            self.__account_tracker.upsert_account(account)

def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
    if self.__account_tracker is not None:
        self.__account_tracker.update_account(account, tag, value, currency)

def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
    if self.__account_tracker is not None:
        self.__account_tracker.update_pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)

def updateAccountTime(self, timestamp: str):
    if self.__account_tracker is not None:
        self.__account_tracker.update_account_time(timestamp)

def accountSummaryEnd(self, reqId: int):
    if self.__account_tracker is not None:
        self.__account_tracker.mark_summary_complete()
```

**Comparison - AccountTracker vs OrderTracker vs PositionTracker:**

| Aspect              | AccountTracker                        | OrderTracker                           | PositionTracker                       |
| ------------------- | ------------------------------------- | -------------------------------------- | ------------------------------------- |
| Wiring Method       | `wire_account_tracker(tracker)`       | `wire_order_tracker(tracker)`          | `wire_position_tracker(tracker)`      |
| **Wiring Returns**  | **accounts list (str)**               | **next_order_id (int \| None)**        | _(void)_                              |
| Update Callback     | `update_account(account, tag, ...)`   | `upsert_order(orderId, contract, ...)` | `upsert_position(account, ...)`       |
| P&L Callback        | `update_pnl(reqId, daily, unr, real)` | _(none)_                               | _(none)_                              |
| Time Callback       | `update_account_time(timestamp)`      | _(none)_                               | _(none)_                              |
| Completion Callback | `mark_summary_complete()`             | `mark_snapshot_complete()`             | `mark_snapshot_complete()`            |
| Error Callback      | `raise_error(exception)` (no req_id)  | `raise_error(exception)` (no req_id)   | `raise_error(exception)` (no req_id)  |
| Request Messages    | `OUT.REQ_ACCOUNT_SUMMARY`             | `OUT.REQ_OPEN_ORDERS`                  | `OUT.REQ_POSITIONS`                   |
| Subscribe Messages  | `OUT.REQ_ACCT_DATA`, `OUT.REQ_PNL`    | _(none)_                               | _(none)_                              |
| Dispatch Pattern    | Multiple specialized callbacks        | Single-phase                           | Single-phase                          |
| Lazy Initialization | `TWSClient.account_tracker` property  | `TWSClient.order_tracker` property     | `TWSClient.position_tracker` property |

**Unique Aspects of AccountTracker:**

1. **Accounts List Return**: `wire_account_tracker()` returns `str` (comma-separated accounts from `managedAccounts`)
2. **Multiple Update Callbacks**: Separate callbacks for account values, P&L, and timestamp (vs single update callback)
3. **TWS Protocol Internalization**: Private `__req_account_summary()`, `__req_account_updates()`, `__req_pnl()` methods send TWS messages
4. **No Request ID for Identification**: Uses account ID instead of request ID for tracking
5. **Multi-Source Data**: Combines `accountSummary`, `pnl`, and `updateAccountTime` callbacks

---

## 2.5 Contract Caching & Persistence

**Files:** `cached_contract.py`, `contract_tracker.py`

Contract data is cached in a two-tier architecture:

1. **Descriptions** (SQLite + memory): `ContractDescription` data from `reqMatchingSymbols` - immutable instrument identity
2. **Details** (memory only): Full `ContractDetails` from `reqContractDetails` - session-dependent (tradingHours, etc.)

### ContractTracker

**File:** `contract_tracker.py`

The `ContractTracker` manages contract caching with SQLite persistence following the dependency inversion pattern established by QuoteTracker/BarsTracker.

**Constructor:**

```python
class ContractTracker(ContractTrackerCBWiringInterface):
    def __init__(
        self,
        ibsocket: IbSocketWiringInterface,
        db_path: str | None = None
    ):
        """Initialize ContractTracker with wired IBSocket.

        Args:
            ibsocket: Socket interface for TWS communication
            db_path: SQLite database path (defaults to .local/DB/sqlite/contracts.db)
        """
        self.ibsocket = ibsocket
        self.ibsocket.wire_contract_tracker(self)  # Bidirectional wiring

        # Internal state
        self._cached_contracts: dict[str, CachedContract] = {}  # ticker → contract
        self._descriptions: dict[int, CachedContract] = {}  # req_id → results
        self._details: dict[int, list[CachedContract]] = {}  # req_id → results
        self._sqlite = SQLiteContractCache(db_path or DEFAULT_CACHE_PATH)
```

**Method Naming Convention:**

Internal helper methods follow clear naming patterns:

| Method                     | Purpose                                         | Called By            |
| -------------------------- | ----------------------------------------------- | -------------------- |
| `_fetch_and_cache()`       | Fetch details from TWS and cache to memory      | `get_details()`      |
| `_search_cache()`          | Multi-tier cache search with exchange filtering | `get_descriptions()` |
| `_send_descriptions_req()` | Build and send OUT.REQ_MATCHING_SYMBOLS         | `get_descriptions()` |
| `_send_details_req()`      | Build and send OUT.REQ_CONTRACT_DATA            | `get_details()`      |

**Rationale**: `_fetch_and_cache()` clarifies "fetch from TWS + cache result" semantics vs. previous `_load_and_cache_details()` which suggested loading from cache. `_search_cache()` emphasizes search/filtering behavior vs. previous `_load_cached_descriptions()` which suggested simple retrieval.

**Public Async API:**

```python
# High-level async methods for TWSClient
async def get_descriptions(
    self, pattern: str, timeout: float = 10.0
) -> list[CachedContract]:
    """Search for contracts by symbol pattern with optimized cache lookup.

    Search Strategy:
    1. Exact match: Check memory cache for exact pattern match (O(1) dict lookup)
    2. Exchange filtering: If pattern contains ":", split into exchange:symbol and filter by exchange
    3. Symbol search: Check memory cache for symbol substring matches
    4. SQLite fallback: Query persistent cache
    5. TWS API: Request from TWS if not cached

    Lazy loading: memory → SQLite → TWS API
    Deduplication: Reuses pending requests for same pattern

    Args:
        pattern: Symbol search pattern. Supports:
            - Simple symbol: "AAPL", "AA" (matches any ticker containing substring)
            - Exchange-qualified: "NASDAQ:AAPL", "NYSE:AA" (filters by exchange)
        timeout: Request timeout in seconds

    Returns:
        List of matching CachedContracts (sorted by ticker name)

    Examples:
        # Exact match optimization
        await get_descriptions("NASDAQ:AAPL")  # O(1) if cached

        # Exchange filtering
        await get_descriptions("NYSE:AA")  # Returns only NYSE matches

        # Symbol search
        await get_descriptions("AA")  # Returns all tickers with "AA" substring
    """

async def get_details(
    self, contract: Contract, timeout: float = 10.0
) -> CachedContract:
    """Get full contract details (singular result).

    Fetches primary exchange + SMART + OVERNIGHT if available.
    Returns first/best match.

    Args:
        contract: Contract to look up
        timeout: Request timeout in seconds

    Returns:
        Single CachedContract with full details
    """
```

**Cache Search Optimization:**

The `_search_cache()` method implements a three-tier search strategy:

```python
def _search_cache(self, pattern: str) -> list[CachedContract]:
    """Multi-tier cache search with exchange filtering.

    Tier 1: Exact Match (O(1))
        - Check self._cached_contracts.get(pattern)
        - Early return if found (e.g., "NASDAQ:AAPL" exactly cached)

    Tier 2: Exchange Filtering
        - If pattern contains ":", split into exchange:symbol
        - Filter cached contracts by exchange field
        - Search within exchange-filtered subset using symbol substring

    Tier 3: Symbol Search
        - If no ":", search all cached contracts
        - Match using `symbol in cached.ticker` substring logic

    Returns:
        Sorted list of matching CachedContracts
    """
```

**Performance Impact:**

- **Before**: All searches iterated entire cache with `startswith(prefix)` matching
- **After**: Exact matches skip iteration (common case when full ticker provided from UI)
- **Exchange Filtering**: Reduces search space when exchange specified (e.g., "NYSE:AA" only searches NYSE contracts)

**Search Pattern Examples:**

| Pattern         | Tier   | Behavior                                       |
| --------------- | ------ | ---------------------------------------------- |
| `"NASDAQ:AAPL"` | Tier 1 | Exact match → O(1) dict lookup                 |
| `"NYSE:AA"`     | Tier 2 | Filter by NYSE exchange → substring "AA"       |
| `"AA"`          | Tier 3 | Search all cached contracts for "AA" substring |

**Rationale**: Most contract resolutions use full ticker names from UI (TradingView symbol selection), making exact match optimization the common path. Exchange filtering enables precise contract disambiguation when multiple exchanges available.

**Internal TWS Protocol Methods:**

```python
# TWS message construction (called by public API)
def _send_descriptions_req(self, pattern: str) -> int:
    """Build and send OUT.REQ_MATCHING_SYMBOLS message.

    Handles deduplication by pattern.
    Returns: Request ID for tracking
    """

def _send_details_req(self, contract: Contract) -> int:
    """Build and send OUT.REQ_CONTRACT_DATA message.

    Handles deduplication by contract identity.
    Returns: Request ID for tracking
    """
```

**IBSocket Callback Routing** (implements `ContractTrackerCBWiringInterface`):

```python
# Called from IBSocket reader thread
def update_descriptions(
    self, req_id: int, descriptions: list[ContractDescription]
) -> None:
    """Route symbolSamples callback data.

    Filters invalid contracts (conId <= 0), caches to SQLite + memory,
    resolves pending Futures.
    """

def update_details(self, req_id: int, details: ContractDetails) -> None:
    """Route contractDetails callback data.

    Accumulates details for multi-result queries.
    No auto-caching - waits for flag_details_complete().
    """

def flag_details_complete(self, req_id: int) -> None:
    """Route contractDetailsEnd callback.

    Resolves pending Future with accumulated results.
    """

def raise_error(self, req_id: int, exception: ProviderException) -> bool:
    """Route error callback.

    Rejects pending Futures with exception.
    """
```

**Architecture Diagram:**

```
TWSClient.reqMatchingSymbols(pattern)
        │
tracker.get_descriptions(pattern, timeout)
        │
        ├─► 1. Check memory cache (dedup by pattern)
        │
        ├─► 2. Check SQLite cache
        │
        ├─► 3. Create Future for async wait
        │
        └─► 4. Send _send_descriptions_req() → OUT.REQ_MATCHING_SYMBOLS
                                │
                                ▼
                    IBSocket.symbolSamples() callback
                                │
                    tracker.update_descriptions(req_id, descriptions)
                                │
                    ├─► Filter invalid (conId <= 0)
                    ├─► Cache to SQLite + memory
                    └─► Resolve Future → return to TWSClient
```

**Session Management:**

```python
def reset(self) -> None:
    """Clear all memory caches (SQLite preserved)."""

def clear_details_cache(self) -> None:
    """Clear session-dependent details only."""
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
# Environment variable (defaults to .local/DB/sqlite/contracts.db)
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
# TWSClient - Simplified delegation pattern
async def reqMatchingSymbols(
    self, pattern: str, timeout: float = 10.0
) -> list[CachedContract]:
    """Delegate to ContractTracker."""
    return await self.contract_tracker.get_descriptions(pattern, timeout)

async def reqContractDetails(
    self, contract: Contract, timeout: float = 10.0
) -> CachedContract:
    """Delegate to ContractTracker. Returns single best match.

    ContractTracker handles:
    - Multi-exchange resolution (primary + SMART + OVERNIGHT)
    - SQLite persistence for descriptions
    - Memory caching for details
    - Deduplication

    Returns:
        Single CachedContract (not list) with full details
    """
    results = await self.contract_tracker.get_details(contract, timeout)
    return results[0]  # First/best match

# TWSClient.reqTickerDetails() - Convenience wrapper
async def reqTickerDetails(self, ticker: str, **kwargs) -> CachedContract:
    """Get single CachedContract for ticker (uses parse_ticker internally)."""
    symbol, primaryExchange, sec_type, _ = parse_ticker(ticker)
    # ... builds Contract and delegates to reqContractDetails()
    return await self.reqContractDetails(contract, **kwargs)
```

**Return Type Change:**

⚠️ **Breaking Change**: `reqContractDetails()` now returns `CachedContract` (singular) instead of `list[CachedContract]`.

**Rationale:** Callers almost always used `next(iter(results))` pattern. Simplifying to singular return reduces boilerplate. Multi-result access available via `contract_tracker.get_details()` if needed.

**Removed Internal Methods:**

The following methods were internalized in ContractTracker:

- `_reqContractDetails(contract)` - Now `ContractTracker._send_details_req()`
- `_get_cached_details(con_id)` - Replaced by `get_details()` async API

**IBSocket Callback Routing:**

- `symbolSamples()` callback → `contract_tracker.update_descriptions()`
- `contractDetails()` callback → `contract_tracker.update_details()`
- `contractDetailsEnd()` callback → `contract_tracker.flag_details_complete()`

---

## 2.6 Account Tracking

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
    """Convert TrackedAccount to AccountMetainfo for account list.

    Includes equity data for initial display (before WebSocket streams).

    Returns:
        Domain AccountMetainfo model with optional equity fields
    """
    equity_data = self.equity_data()
    return AccountMetainfo(
        id=self.id,
        name=self.id,  # TWS doesn't provide separate display name
        currency=self.currency or "USD",
        currencySign=self.currency_sign or "$",
        equity=equity_data.equity if equity_data.equity != 0.0 else None,
        balance=equity_data.balance if equity_data.balance != 0.0 else None,
        unrealizedPL=equity_data.unrealizedPL
        if equity_data.unrealizedPL != 0.0
        else None,
        realizedPL=equity_data.realizedPL
        if equity_data.realizedPL != 0.0
        else None,
    )
```

**Note:** All equity metrics in TrackedAccount are stored as `Decimal | None` - use helper methods (`equity_data()`, `metainfo()`) for safe float access with 0.0 fallback.

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

**AccountTracker Architecture (Interface-Based):**

```python
class AccountTracker(AccountTrackerCBWiringInterface):
    """Manages account state for IBSocket. Thread-safe via asyncio dispatch.

    Follows the wiring pattern used by other trackers:
    - TWSClient owns the tracker instance
    - IBSocket receives wired interface for callbacks
    - Request methods are owned by the tracker

    Thread Ownership:
        - Envelope (hooks registration, reset): main thread
        - Content (accounts dict): reader thread writes, main thread reads
        - Dispatch (callbacks): reader thread schedules, main thread executes
    """
    def __init__(self, ibsocket: IbSocketWiringInterface):
        self.ibsocket = ibsocket
        self._account_summary_requested = threading.Event()
        self._account_summary_complete = threading.Event()
        self._accounts: dict[str, TrackedAccount] = {}
        self._snapshot_hooks: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future]] = {}
        self._stream_hooks: dict[str, tuple[loop, callback, on_error]] = {}

        # Wire to IBSocket (returns comma-separated accounts list)
        account_list = ibsocket.wire_account_tracker(self)
        for account in account_list.split(","):
            self.upsert_account(account)
```

**Internal Request Methods (TWS Protocol Internalization):**

```python
# Private methods send TWS messages directly
def __req_account_summary(self) -> None:
    """Send account summary request to TWS."""
    if not self._account_summary_requested.is_set():
        VERSION = 1
        reqId = self.ibsocket.next_req_id
        self.ibsocket.send_message(
            OUT.REQ_ACCOUNT_SUMMARY,
            [VERSION, reqId, "All", ",".join(TWS_TAG_TO_FIELD.keys())],
        )
        self._account_summary_requested.set()

def __req_account_updates(self, subscribe: bool, acctCode: str) -> None:
    """Subscribe/unsubscribe to account updates."""
    VERSION = 2
    self.ibsocket.send_message(OUT.REQ_ACCT_DATA, [VERSION, subscribe, acctCode])

def __req_pnl(self, reqId: int, account: str, modelCode: str = "") -> None:
    """Subscribe to real-time P&L updates."""
    self.ibsocket.send_message(OUT.REQ_PNL, [reqId, account, modelCode])

def __req_account_subscriptions(self, account: str) -> int:
    """Subscribe to account updates with P&L.

    Combines __req_account_updates and __req_pnl for comprehensive account tracking.
    """
    self.__req_account_updates(True, account)
    reqId = self.ibsocket.next_req_id
    self.__req_pnl(reqId, account)
    return reqId
```

**Usage Patterns:**

```python
# Snapshot: Get all accounts (wait for summary if needed)
accounts = await account_tracker.reqAccountSummary(timeout=5.0)

# Stream: Register callback for continuous updates
key = account_tracker.create_stream_hook(
    callback=async def on_update(tracked: TrackedAccount): ...,
    on_error=async def on_error(exc: ProviderException): ...,
)
account_tracker.remove_stream_hook(key)  # Cleanup
```

**Note:** `create_stream_hook()` signature changed - removed `loop` parameter (auto-detected via `asyncio.get_event_loop()`).

**Public API Changes:**
**Callback Methods (AccountTrackerCBWiringInterface):**

```python
# Called from reader thread (IBSocket callbacks)
def upsert_account(self, account: str) -> None:
    """Create or update TrackedAccount from managedAccounts callback.

    Automatically subscribes to P&L updates for this account.
    """
    if account in self._accounts:
        return  # Already exists

    tracked = self._accounts.setdefault(account, TrackedAccount(id=account))
    # Subscribe to P&L updates for this account
    tracked.pnl_req_id = self.__req_account_subscriptions(tracked.id)
    self.__notify_hooks(tracked.id)

def update_account(self, account: str, tag: str, value: str, currency: str) -> None:
    """Update TrackedAccount field from accountSummary callback.

    Maps TWS tag names (e.g., "NetLiquidation") to TrackedAccount fields.
    """
    # ... field mapping logic
    self.__notify_hooks(tracked.id)

def update_pnl(self, reqId: int, daily: float, unrealized: float, realized: float) -> None:
    """Update TrackedAccount P&L from pnl callback.

    Real-time P&L updates from reqPnL subscription.
    """
    # ... update P&L fields
    self.__notify_hooks(tracked.id)

def update_account_time(self, timestamp: str) -> None:
    """Update last_update_time on all tracked accounts."""
    for tracked in self._accounts.values():
        tracked.last_update_time = timestamp

def mark_summary_complete(self) -> None:
    """Mark snapshot as complete. Called from accountSummaryEnd callback."""
    self._account_summary_complete.set()
    # ... resolve snapshot hooks

def raise_error(self, exception: ProviderException) -> None:
    """Dispatch error to all hooks."""
    # ... dispatch to error callbacks
```

**IBSocket Integration (via Wiring):**

See [AccountTrackerCBWiringInterface section](#accounttrackercbwiringinterface) for complete wiring code examples showing:

- `managedAccounts()` callback routing
- `accountSummary()` callback routing
- `pnl()` callback routing
- `updateAccountTime()` callback routing
- `accountSummaryEnd()` callback routing """Called for each tag in reqAccountSummary() response."""
  self.account_tracker.update_account(account, tag, value, currency)

def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
"""Real-time P&L updates from reqPnL()."""
self.account_tracker.update_pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)

````

### TWSBrokerProvider Integration

**Get Account Metadata:**

```python
async def get_account_info(self) -> AccountMetainfo:
    """Get account metadata from TWS."""
    account_list = await self._tws_client.reqAccountSummary()
    tracked_account = next(iter(account_list), None)
    assert tracked_account is not None, "Account summary returned no data"
    return tracked_account.metainfo()
````

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

## 2.7 Quote Tracking

**File:** `quote_tracker.py`

The `QuoteTracker` manages real-time market data subscriptions with centralized hook management:

```python
class QuoteTracker(QuoteTrackerCBWiringInterface):
    # Constructor (interface-based composition)
    def __init__(self, ibsocket: IbSocketWiringInterface, timeout: float = 10):
        """Initialize with socket interface instead of hook functions."""
        self.ibsocket = ibsocket
        self.timeout = timeout
        # ... state initialization

**Initialization Flow (Bidirectional Wiring):**

```

1. Constructor receives ibsocket: IbSocketWiringInterface parameter
   │
2. Immediately calls ibsocket.wire_quote_tracker(self)
   │
   ├─► IBSocket stores reference: self.\_\_quote_tracker = tracker_interface
   │
3. All tick callbacks now route through stored reference:
   │
   ├─► tickPrice() → self.**quote_tracker.update(reqId, {"bid": price})
   ├─► tickSize() → self.**quote_tracker.update(reqId, {"bid_size": size})
   ├─► tickString() → self.**quote_tracker.update(reqId, {"rt_volume": value})
   └─► error() → self.**quote_tracker.raise_error(reqId, exception)

```

**Thread Safety:** IBSocket's private `__quote_tracker` attribute prevents external mutation. Only IBSocket reader thread can invoke the stored interface methods.

**See:** `quote_tracker.py` lines 514-517 for initialization, `tws_connection.py` IBSocket class for `wire_quote_tracker()` implementation and tick callback routing.

    # Internal State
    _quotes: dict[str, TrackedQuote]              # ticker_name → TrackedQuote
    _snapshot_hooks: dict[str, list[...]]         # tws_key → [(loop, Future)]
    _stream_hooks: dict[str, list[...]]           # tws_key → [(loop, callback, on_error)]
    _lock: threading.Lock

    # Internal TWS Protocol Methods (encapsulated)
    def _quote_request_hook(self, contract: Contract) -> int:
        """Build and send REQ_MKT_DATA message via ibsocket interface.

        Encapsulates TWS market data request protocol:
        - Allocates reqId from ibsocket.next_req_id
        - Determines genericTickList from asset type
        - Constructs TWS message fields
        - Sends via ibsocket.send_message()

        Returns: TWS reqId for subscription tracking
        """

    def _quote_cancel_hook(self, req_id: int) -> None:
        """Build and send CANCEL_MKT_DATA message via ibsocket interface."""

    # Snapshot Pattern (one-time fetch)
    async def request(self, ticker_name: str, timeout: float = 10) -> Quote:
        """Request quote snapshot, reuses existing subscription if available."""

    # Stream Pattern (continuous updates)
    def subscribe(self, ticker_name: str, callback: Callable, on_error: Callable) -> str:
        """Subscribe to quote stream, returns subscription_id for cleanup."""

    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from stream, uses reference counting."""

    # Update Dispatch (called from reader thread)
    def update(self, tws_key: str, tick_data: dict[str, Any]) -> None:
        """Dispatch tick updates to registered hooks (thread-safe)."""
```

**Observability & Timing:**

QuoteTracker includes enhanced logging for production debugging:

**Periodic Logging:**

```python
class TrackedQuote:
    __slots__ = [
        ...,
        "__log_timer",  # Timer for periodic "TrackedQuote is live" logging
    ]

    def update(self, tick_data: dict[str, Any]) -> None:
        """Update quote fields and dispatch to hooks.

        Logs "TrackedQuote is live" message every 5 seconds to verify
        subscription health in production. Timing tracked via __log_timer.
        """
```

**Staleness Detection:**

The `is_ready` property warns when quotes are stale:

```python
@property
def is_ready(self) -> bool:
    """Check if quote has received at least one update.

    Logs warning if last_update timestamp exists but is stale
    (updated > 30 seconds ago). Warning includes timing information
    for debugging delayed updates.

    Returns:
        True if quote has valid data, False if never updated
    """
```

**Debounce Cancel Timing:**

```python
# Stream subscription debounce settings
DEBOUNCE_CANCEL_DELAY = 3.0  # Wait 3 seconds before canceling TWS subscription

# Rationale: Increased from 1.0s to reduce premature cancellations
# when frontend temporarily disconnects/reconnects (e.g., tab switches).
# Prevents unnecessary TWS reqMktData churn.
```

**Logging Strategy:**

| Event                    | Log Level | Frequency    | Purpose                                 |
| ------------------------ | --------- | ------------ | --------------------------------------- |
| Quote is live            | DEBUG     | Every 5s     | Verify subscription health              |
| Quote staleness          | WARNING   | Per access   | Alert to delayed/missing updates        |
| Subscription start       | INFO      | Once         | Track subscription lifecycle            |
| Subscription cancel      | INFO      | Once         | Track cleanup operations                |
| Unknown req_id (removed) | ~~ERROR~~ | ~~Per tick~~ | ~~Removed - handled at IBSocket level~~ |

**Rationale**: Periodic logging enables passive monitoring in production logs without needing active debugging. Staleness warnings surface quote quality issues. Debounce timing reduces TWS API churn during normal frontend reconnection patterns.

**Interface Implementation:**

- **Implements**: `QuoteTrackerCBWiringInterface` for callback contract (`update()`, `raise_error()`)
- **Depends On**: `IbSocketWiringInterface` for socket communication (injected via constructor)
- **TWS Protocol Ownership**: `_quote_request_hook()` and `_quote_cancel_hook()` internalize TWS message construction
  - Previously: TWSClient hook functions built messages
  - Now: QuoteTracker owns complete market data request lifecycle
- **Thread Safety**: Added `with self.tracker_lock:` around hook lookups in `update()` and `raise_error()` methods

**Constructor Change:**

**OLD (callback injection):**

```python
QuoteTracker(
    quote_request_hook: Callable[[Contract], int],
    quote_cancel_hook: Callable[[int], None],
    timeout: float
)
```

**NEW (interface composition):**

```python
QuoteTracker(
    ibsocket: IbSocketWiringInterface,
    timeout: float
)
```

**Wiring in TWSClient:**

```python
class TWSClient:
    @property
    def quote_tracker(self) -> QuoteTracker:
        if not hasattr(self, "_quote_tracker"):
            self._quote_tracker = QuoteTracker(self.ibsocket, self._timeout)
        return self._quote_tracker
```

**Architecture:**

- **Centralized Hooks**: Unlike other trackers, hooks are stored centrally in `_snapshot_hooks` and `_stream_hooks`, not per-`TrackedQuote`
- **Reference Counting**: Each subscription increments a refcount; `unsubscribe()` decrements and only cancels TWS subscription when count reaches zero
- **Symbol Deduplication**: Multiple topics requesting the same symbol share the underlying TWS subscription

**Threading Model:**

- **Main Thread**: `request()`, `subscribe()`, `unsubscribe()` called from async service methods
- **Reader Thread**: `update()` called from TWS tick callbacks (`tickPrice`, `tickString`, etc.)
- **Dispatch**: Hooks dispatched to main thread via `asyncio.loop.call_soon_threadsafe()`

**Debug Logging:**

```bash
export DEBUG_TWS_DATAFEED=true  # Enables verbose quote tracking logs
```

**Reference:**

- **Tests**: `providers/tws/tests/test_quote_tracker.py` (28 test methods with `mock_ibsocket` fixture)
- **Usage**: Used by `TWSDatafeedProvider.subscribe_market_data()`
- **Testing Pattern**: Mock `IbSocketWiringInterface` with PropertyMock for auto-incrementing req_id behavior (see BACKEND_TESTING.md)

See: `quote_tracker.py` lines 1-115 for implementation, `wiring_interfaces.py` for interface contracts

---

## 2.8 Bar Data Management (BarsTracker)

**File:** `bars_tracker.py`

The `BarsTracker` manages historical and real-time bar data with timezone-aware conversion, snapshot/stream patterns, and dependency inversion for testability:

```python
class BarsTracker(BarsTrackerCBWiringInterface):
    """Manages bar data requests using interface-based wiring pattern.

    Implements BarsTrackerCBWiringInterface for IBSocket callback routing.
    Depends on IbSocketWiringInterface for TWS socket communication.
    """
    def __init__(self, ibsocket: IbSocketWiringInterface, timeout: float = 11.0):
        self._ibsocket = ibsocket
        self._timeout = timeout
        ibsocket.wire_bars_tracker(self)  # Bidirectional wiring
        # ... state initialization
```

**Initialization Flow (Bidirectional Wiring):**

```
1. Constructor receives ibsocket: IbSocketWiringInterface parameter
   │
2. Immediately calls ibsocket.wire_bars_tracker(self)
   │
   ├─► IBSocket stores reference: self.__bars_tracker = tracker_interface
   │
3. All historical data callbacks now route through stored reference:
   │
   ├─► historicalData()       → self.__bars_tracker.update(reqId, bar)
   ├─► historicalDataUpdate() → self.__bars_tracker.update(reqId, bar)
   ├─► historicalDataEnd()    → self.__bars_tracker.flag_complete(reqId, start, end)
   └─► error() (bar-related)  → self.__bars_tracker.raise_error(reqId, exception)
```

**Thread Safety:** IBSocket's private `__bars_tracker` attribute prevents external mutation. Only IBSocket reader thread can invoke the stored interface methods.

**See:** `bars_tracker.py` for initialization, `tws_connection.py` IBSocket class for `wire_bars_tracker()` implementation and historical data callback routing.

```python
    # Internal State
    _bars_requests: dict[int, BarsRequest]        # reqId → BarsRequest
    _stream_hooks: dict[int, StreamHook]          # reqId → (loop, callback, on_error)
    _lock: threading.Lock

    # Internal TWS Protocol Methods (encapsulated)
    def _bars_request_hook(
        self, contract: Contract, bar_size: str, end_date_time: str, duration_str: str
    ) -> int:
        """Build and send REQ_HISTORICAL_DATA message via ibsocket interface.

        Encapsulates TWS historical data request protocol:
        - Allocates reqId from ibsocket.next_req_id
        - Builds ~25-field message (contract details, bar params, format options)
        - Sends via ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, fields)

        Returns: TWS reqId for request tracking
        """

    def _bars_cancel_hook(self, req_id: int) -> None:
        """Build and send CANCEL_HISTORICAL_DATA message via ibsocket interface."""

    # Snapshot Pattern (historical bars)
    async def request(
        self,
        contract: Contract,
        bar_size: str,
        duration: str,
        end_datetime: str,
        what_to_show: str,
        use_rth: int,
        timeout: float = 10
    ) -> list[Bar]:
        """Request historical bars snapshot with timezone-aware conversion."""

    # Stream Pattern (real-time bars)
    def subscribe(
        self,
        req_id: int,
        callback: Callable[[Bar], Awaitable[None]],
        on_error: Callable[[ProviderException], Awaitable[None]]
    ) -> None:
        """Subscribe to real-time bar updates."""

    # BarsTrackerCBWiringInterface implementation (called from reader thread)
    def update(self, req_id: int, bar: ibapi.common.BarData) -> None:
        """Convert TWS bar to domain Bar and dispatch to hooks (thread-safe)."""

    def flag_complete(self, req_id: int, start: str, end: str) -> None:
        """Mark historical request complete, resolve snapshot Future."""

    def raise_error(self, req_id: int, error: ProviderException) -> bool:
        """Forward error to request/stream hooks. Returns True if handled."""
```

**Interface Implementation:**

- **Implements**: `BarsTrackerCBWiringInterface` for callback contract (`update()`, `flag_complete()`, `raise_error()`)
- **Depends On**: `IbSocketWiringInterface` for socket communication (injected via constructor)
- **TWS Protocol Ownership**: `_bars_request_hook()` and `_bars_cancel_hook()` internalize TWS message construction
  - Previously: TWSClient hook functions built messages
  - Now: BarsTracker owns complete historical data request lifecycle
- **Thread Safety**: Uses `with self._lock:` around hook lookups in callback methods

**Constructor Change:**

**OLD (callback injection):**

```python
BarsTracker(
    bars_request_hook: Callable[[Contract, str, str, str], int],
    bars_cancel_hook: Callable[[int], None],
    timeout: float
)
```

**NEW (interface composition):**

```python
BarsTracker(
    ibsocket: IbSocketWiringInterface,
    timeout: float
)
```

**Wiring in TWSClient:**

```python
class TWSClient:
    @property
    def bars_tracker(self) -> BarsTracker:
        """Lazy-initialized BarsTracker for historical/streaming bar data."""
        if self.__bars_tracker is None:
            self.__bars_tracker = BarsTracker(self.ibsocket, self._timeout)
        return self.__bars_tracker
```

### Unified Bar Subscription Pattern

**[ARCHITECTURE FIX - January 19, 2026]**: All bar subscriptions (both historical and real-time) now route through BarsTracker for centralized registration. This fixes the "Received bar update for unknown req_id" warning.

**Call Flow:**

```
TWSClient.reqBarDataStream()
        │
        ├──> bars_tracker.subscribe()    # ← Centralized registration
        │           │
        │           └──> _bars_request_hook() → ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, ...)
        │
IBSocket.historicalData() callback
        │
        └──> self.__bars_tracker.update(reqId, bar)  # ← Routes to registered hooks
```

**Key Benefits:**

- ✅ Single subscription pathway for all bar data (historical + real-time)
- ✅ Eliminates "unknown req_id" warnings
- ✅ Consistent callback routing through BarsTracker
- ✅ Simplified architecture (no parallel pathways)
- ✅ Testability via interface mocking

**Architecture:**

- **SmartTwsBar**: Timezone-aware wrapper for `ibapi.common.BarData`
  - Converts TWS datetime strings (`"20231215 09:30:00 US/Eastern"`) to UTC timestamps
  - Provides `to_domain()` → `Bar` (Pydantic model with `time: int` milliseconds, `volume: int`)
- **BarsRequest**: Lifecycle tracking for single historical data request
  - `upsert()`: Accumulates bars by timestamp (replaces duplicates)
  - `flag_request_complete()`: Resolves snapshot Future with sorted bars
- **Callback Routing**: `IBSocket.historicalData()` → `self.__bars_tracker.update(reqId, bar)` via wiring interface

**Threading Model:**

- **Main Thread**: `request()` creates Future, awaits completion with timeout
- **Reader Thread**: `update()` called from TWS callbacks (`historicalData`, `historicalDataUpdate`)
- **Dispatch**: Hooks dispatched to main thread via `asyncio.loop.call_soon_threadsafe()`

**Domain Conversion:**

```python
from bars_tracker import SmartTwsBar
from trading_api.models.bars import Bar

# TWS BarData → SmartTwsBar → Bar
tws_bar = ibapi.common.BarData()  # date="20231215 09:30:00 US/Eastern"
smart_bar = SmartTwsBar(bar=tws_bar)
domain_bar = smart_bar.to_domain()

# domain_bar.time → 1702641000000 (int milliseconds UTC)
# domain_bar.volume → 1000000 (int, not float/Decimal)
# domain_bar.count → Optional[int] (None for historical, set for real-time)
```

**Test Patterns:**

- **Snapshot Testing**: Mock `bars_tracker.request()` with `AsyncMock(return_value=[bar1, bar2])`
  - Use `Bar` objects with `time: int` (milliseconds), `volume: int`
  - Example: `Bar(time=1702641000000, open=150.0, high=151.0, low=149.5, close=150.5, volume=1000000)`
- **IBSocket Integration Testing**: Wire mock `BarsTrackerCBWiringInterface` via `wire_bars_tracker()`
  - Verify `historicalData()` → `mock_bars_tracker.update(reqId, bar)`
  - Verify `historicalDataEnd()` → `mock_bars_tracker.flag_complete(reqId, start, end)`
  - No async patterns in IBSocket tests (synchronous callback verification)
- **BarsTracker Unit Testing**: Mock `IbSocketWiringInterface` with `PropertyMock(side_effect=...)` for `next_req_id`
  - Same pattern as QuoteTracker tests in `test_quote_tracker.py`

**IBSocket Integration:**

```python
# IBSocket implements wiring interface
class IBSocket(EWrapper, IbSocketWiringInterface):
    def __init__(self) -> None:
        self.__bars_tracker: BarsTrackerCBWiringInterface | None = None
        # ... other initialization

    def wire_bars_tracker(self, tracker: BarsTrackerCBWiringInterface) -> None:
        """Wire BarsTracker for callback routing (bidirectional wiring)."""
        self.__bars_tracker = tracker

    # historicalData callback routes to wired BarsTracker
    def historicalData(self, reqId: int, bar: BarData) -> None:
        if self.__bars_tracker:
            self.__bars_tracker.update(reqId, bar)

    # historicalDataEnd callback completes request
    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        if self.__bars_tracker:
            self.__bars_tracker.flag_complete(reqId, start, end)
```

**Reference:**

- **Tests**: `providers/tws/tests/test_ibsocket.py` (callback routing with wired mock), `test_datafeed_provider.py` (Bar objects)
- **Interfaces**: `wiring_interfaces.py` (`BarsTrackerCBWiringInterface`, `IbSocketWiringInterface`)
- **Usage**: Used by `TWSClient.bars_tracker` property and `TWSDatafeedProvider.get_historical_bars()`

---

## 2.9 Crypto-Specific Handling

**[CRYPTO SUPPORT - January 19, 2026]**: Special handling for cryptocurrency assets (CRYPTO secType).

### Broker Provider - Leverage

**File:** `broker_provider.py`

Crypto assets return fixed leverage (no margin trading):

```python
# In get_leverage_info()
if contract.secType == "CRYPTO":
    return LeverageInfo(
        leverage=1.0,  # No leverage for crypto
        margin_rate=None,
        buy_rate=None,
        sell_rate=None,
    )
```

**Rationale**: IBKR does not support margin trading for cryptocurrencies. All crypto positions must be fully funded.

### Order Mappers - Cash Quantity

**File:** `tws_mappers.py`

Crypto orders use cash quantity instead of share quantity:

```python
# In prebuild_tws_order()
if contract.secType == "CRYPTO":
    order.cashQty = preorder.qty  # Cash amount (USD, EUR, etc.)
    order.tif = "IOC"             # Immediate-Or-Cancel
else:
    order.totalQuantity = preorder.qty  # Share quantity
```

**TWS API Specifics:**

| Field           | Stock Orders     | Crypto Orders                |
| --------------- | ---------------- | ---------------------------- |
| `totalQuantity` | Share count      | _(not used)_                 |
| `cashQty`       | _(not used)_     | Cash amount (e.g., 1000 USD) |
| `tif`           | DAY/GTC/IOC      | IOC (Immediate-Or-Cancel)    |
| `orderType`     | LMT/MKT/STP/etc. | LMT/MKT only                 |

**Example:**

- Stock: `totalQuantity=100` shares at `lmtPrice=150.00` → Total: $15,000
- Crypto: `cashQty=15000` USD → Buys equivalent BTC at market price

---

## 2.10 ExecutionTracker: Interface-Based Wiring

**Purpose:** Track trade executions with commission enrichment via two-phase dispatch, using the dependency inversion pattern.

**Key Classes:**

- `TrackedExecution` - Dataclass wrapping Contract, Execution, and optional commission
- `ExecutionTracker` - Manages execution state with snapshot/stream hooks, implements `ExecutionTrackerCBWiringInterface`

**Architecture:**

```
┌─────────────────────┐              ┌─────────────────────────────────────┐
│     TWSClient       │─────────────▶│       ExecutionTracker              │
│  (owns via lazy     │   property   │ (implements ExecutionTrackerCB      │
│   __execution_      │              │  WiringInterface)                   │
│   tracker field)    │              └───────────────┬─────────────────────┘
└─────────────────────┘                              │
                                         constructor │ calls wire_execution_tracker(self)
                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              IBSocket                                       │
│  wire_execution_tracker(tracker) ─► stores __execution_tracker reference    │
│                                                                             │
│  Callbacks route to tracker:                                                │
│    execDetails()         ─► __execution_tracker.upsert_execution()          │
│    commissionAndFeesReport() ─► __execution_tracker.update_commission()     │
│    execDetailsEnd()      ─► __execution_tracker.mark_snapshot_complete()    │
│    error() [EXEC nature] ─► __execution_tracker.raise_error()               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Commission Joining Workflow:**

```
┌────────────────┐  (commission=None)
│ execDetails    │
│ callback       │
└───────┬────────┘
        │
        ▼
┌────────────────────┐         ┌─────────────────────┐
│ upsert_execution() │────────▶│ Dispatch to streams │  (immediate)
└────────────────────┘         └─────────────────────┘
        │                               ▲
        │                               │
┌───────▼────────┐                      │
│ Store tracked  │                      │
│ execution      │                      │
└────────────────┘                      │
                                        │
┌──────────────────────┐         ┌──────┴──────────────────┐
│ commissionAndFees    │────────▶│ Re-dispatch with    │  (~50-200ms later)
│ Report callback      │         │ enriched commission │
└──────────────────────┘         └─────────────────────────┘
```

**Why Two-Phase Dispatch?**

- **Fast Fill Notifications:** Frontend receives execution ~2ms after fill
- **Complete Data:** Commission arrives ~50-200ms later, triggers update
- **No Blocking:** Don't wait for commission before notifying subscribers

**Thread Safety:**

- **Reader Thread:** `upsert_execution()`, `update_commission()`, `mark_snapshot_complete()` - called via IBSocket callbacks
- **Main Thread:** `all_executions()`, `create_stream_hook()`, `reset()` - called via TWSClient
- **No Locks Needed:** Reader thread writes to dict, main thread reads via asyncio dispatch

**Constructor & Wiring:**

```python
class ExecutionTracker(ExecutionTrackerCBWiringInterface):
    def __init__(self, ibsocket: IbSocketWiringInterface):
        self.ibsocket = ibsocket
        self.ibsocket.wire_execution_tracker(self)  # Register for callbacks
        self._executions: dict[str, TrackedExecution] = {}
        self._snapshot_hooks: dict[int, asyncio.Future[list[TrackedExecution]]] = {}
        self._stream_hooks: dict[str, tuple[asyncio.AbstractEventLoop, ...]] = {}
        self._snapshot_requested = False
        self._snapshot_req_id: int | None = None

    def ensure_snapshot_requested(self) -> None:
        """Send REQ_EXECUTIONS if not already requested (auto-request pattern)."""
        if not self._snapshot_requested:
            self._snapshot_requested = True
            self._snapshot_req_id = self.ibsocket.next_req_id
            self.ibsocket.send_protobuf(OUT.REQ_EXECUTIONS + PROTOBUF_MSG_ID, ...)
```

**Lazy Initialization (TWSClient):**

```python
class TWSClient:
    def __init__(self, ...):
        self.__execution_tracker: ExecutionTracker | None = None

    @property
    def execution_tracker(self) -> ExecutionTracker:
        """Lazy-initialized ExecutionTracker for execution tracking."""
        if self.__execution_tracker is None:
            self.__execution_tracker = ExecutionTracker(self.ibsocket)
        return self.__execution_tracker
```

**Execution Model Update:**

`TrackedExecution.to_domain()` now populates the `id` field for TradingView Account Manager deduplication:

```python
def to_domain(self) -> Execution:
    """Convert to domain Execution model."""
    return Execution(
        id=self.exec_id,  # TWS exec_id maps to domain id
        symbol=self.symbol,
        price=self.execution.price,
        # ... other fields
    )
```

**Rationale:** TradingView custom Account Manager pages require unique `id` field for row deduplication. Since TWS may fire two updates per execution (fill → commission enrichment), the `id` ensures the second update modifies the existing row instead of creating a duplicate.

**Timezone-Aware Time Parsing:**

TWS execution times now support IANA timezones (e.g., `"20260120 07:10:09 US/Eastern"`):

```python
def _parse_tws_execution_time(time_str: str) -> int:
    """Parse TWS execution time to unix milliseconds (UTC).

    TWS format: "YYYYMMDD HH:MM:SS TZ" where TZ is IANA timezone.
    Legacy formats: "YYYYMMDD-HH:MM:SS" or "YYYYMMDD HH:MM:SS" (no TZ).
    """
    parts = time_str.replace("-", " ").split(" ")
    dt = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y%m%d %H:%M:%S")

    # Apply timezone if provided (e.g., "US/Eastern"), else assume UTC
    if len(parts) >= 3:
        tz = ZoneInfo(" ".join(parts[2:]))  # Handle multi-word TZ
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.replace(tzinfo=timezone.utc)

    return int(dt.timestamp() * 1000)  # Convert to UTC milliseconds
```

**Exception Handling:** Falls back to current UTC time on `ValueError`, `KeyError`, or `IndexError` (malformed time strings).

**API:**

```python
class ExecutionTracker:
    # Reader thread (IBSocket callbacks)
    def upsert_execution(self, contract: Contract, execution: TWSExecution) -> None:
        """Store execution and dispatch immediately (commission may be None)."""

    def update_commission(self, exec_id: str, commission: float) -> None:
        """Enrich execution with commission and re-dispatch."""

    def mark_snapshot_complete(self) -> None:
        """Resolve all snapshot hooks with current executions."""

    # Main thread (TWSClient/BrokerProvider)
    async def all_executions(self, filter_symbol: str = "", timeout: float | None = None) -> list[TrackedExecution]:
        """Get all executions, waiting for snapshot if needed."""

    def create_stream_hook(self, loop, callback, on_error) -> str:
        """Register callback for execution updates (called twice per execution)."""

    def remove_stream_hook(self, key: str) -> None:
        """Unregister execution callback."""
```

**TWSBrokerProvider Integration:**

```python
class TWSBrokerProvider:
    async def get_executions(self, symbol: str | None = None) -> list[DomainExecution]:
        """Get executions with optional symbol filter."""
        # Uses TWSClient.execution_tracker (lazy init, auto-request)
        tracked = await self._tws_client.reqExecutions()
        if symbol:
            tracked = [t for t in tracked if t.symbol == f"EXCHANGE:{symbol}"]
        return [t.to_domain() for t in tracked]

    async def get_all_executions(self) -> list[DomainExecution]:
        """Get ALL execution history (no symbol filter)."""
        return await self.get_executions("")  # Empty string = all symbols

    async def subscribe_executions(self, callback, on_error, symbol: str | None = None) -> str:
        """Subscribe to execution stream (with commission enrichment)."""
        async def on_execution_update(tracked: TrackedExecution) -> None:
            # Filter by symbol if specified
            if symbol and tracked.symbol != f"EXCHANGE:{symbol}":
                return
            # Convert to domain and dispatch
            await callback(tracked.to_domain())

        # Uses TWSClient.reqExecutionsStream (lazy init, auto-request via tracker)
        return self._tws_client.reqExecutionsStream(on_execution_update, on_error)
```

**Testing Patterns:**

```python
# Mock execution_tracker in IBSocket
class TestBrokerProvider:
    def test_subscribe_executions_dispatches_twice(self, mock_socket):
        """Verify two-phase dispatch: execDetails → commissionAndFeesReport."""
        tracker = mock_socket.execution_tracker
        contract = Contract()
        execution = TWSExecution()
        execution.execId = "001"

        # Track dispatches
        dispatches = []
        tracker.create_stream_hook(
            loop=asyncio.get_running_loop(),
            callback=lambda t: dispatches.append(t),
            on_error=lambda e: None,
        )

        # Phase 1: execDetails (commission=None)
        tracker.upsert_execution(contract, execution)
        assert len(dispatches) == 1
        assert dispatches[0].commission is None

        # Phase 2: commissionAndFeesReport (commission enriched)
        tracker.update_commission("001", 1.50)
        assert len(dispatches) == 2
        assert dispatches[1].commission == 1.50
```

**Known Behavior:**

- Commission may arrive before execution (rare, gracefully handled)
- Re-dispatch uses same hook keys (subscribers receive both notifications)
- Snapshot includes all executions up to `execDetailsEnd` callback
- Symbol filtering happens at provider layer (not tracker)

---

## 2.11 OrderTracker

**[DEPENDENCY INVERSION - January 24, 2026]**: Interface-based wiring enables testable order state tracking without tight coupling to IBSocket.

**File:** `order_tracker.py`

```
┌─────────────────────────────────────────────────────────────────────┐
│                             OrderTracker                            │
│                                                                     │
│  Implements OrderTrackerCBWiringInterface for TWS callbacks:       │
│  - upsert_order(orderId, contract, order, orderState)              │
│  - update_status(orderId, status, filled, remaining, ...)          │
│  - mark_snapshot_complete()                                         │
│  - raise_error(exception)                                           │
│                                                                     │
│  Uses IbSocketWiringInterface for TWS protocol:                    │
│  - wire_order_tracker(self) → returns next_order_id                │
│  - send_protobuf(OUT.PLACE_ORDER + PROTOBUF_MSG_ID, order_proto)   │
│  - send_protobuf(OUT.CANCEL_ORDER + PROTOBUF_MSG_ID, order_id)     │
│  - send_message(OUT.REQ_OPEN_ORDERS)                               │
│                                                                     │
│  Internal Logic:                                                    │
│  - __submit_order(): Reconciliation, no-op detection, guards       │
│  - TrackedOrder: Bidirectional parent/child refs, BracketContext   │
│  - __placeOrder(): TWS protocol internalization                    │
│  - __cancelOrder(): TWS protocol internalization                   │
│  - __ensure_snapshot_requested(): Auto-request on first hook       │
└─────────────────────────────────────────────────────────────────────┘
              ▲                                   │
              │ implements                        │ uses
              │ OrderTrackerCBWiringInterface     │ IbSocketWiringInterface
              │                                   ▼
┌─────────────┴──────────────────────────────────────────────────────┐
│                             IBSocket                               │
│                                                                    │
│  - Stores __order_tracker: OrderTrackerCBWiringInterface           │
│  - wire_order_tracker(tracker) → returns next_order_id             │
│  - openOrder() → __order_tracker.upsert_order()                    │
│  - orderStatus() → __order_tracker.update_status()                 │
│  - openOrderEnd() → __order_tracker.mark_snapshot_complete()       │
│  - error() → __order_tracker.raise_error() (if ORDER error)        │
└────────────────────────────────────────────────────────────────────┘
```

### Wiring Interfaces (Dependency Inversion)

OrderTracker implements `OrderTrackerCBWiringInterface` (callback contract) and uses `IbSocketWiringInterface` (protocol contract):

```python
# Constructor: Bidirectional wiring
def __init__(self, ibsocket: IbSocketWiringInterface):
    """Initialize OrderTracker with ibsocket wiring (dependency injection).

    Args:
        ibsocket: Wiring interface for TWS protocol operations and callbacks.
    """
    self.ibsocket = ibsocket
    # Unique: wire_order_tracker() returns next_order_id for initialization
    self.next_order_id: int = self.ibsocket.wire_order_tracker(self)
    # ... (other initialization)

# Callback Implementation (OrderTrackerCBWiringInterface)
def upsert_order(
    self, orderId: int, contract: Contract, order: Order, orderState: OrderState
) -> None:
    """Create or replace TrackedOrder from openOrder callback (thread-safe).

    Called from IBSocket.openOrder() in reader thread.
    """
    # ... (update __orders dict, dispatch to hooks)

def update_status(
    self, orderId: int, status: str, filled: Decimal, remaining: Decimal, ...
) -> None:
    """Update TrackedOrder from orderStatus callback (thread-safe).

    Mutates stored Order and OrderState objects directly.
    """
    # ... (update Order/OrderState, dispatch to hooks)

def mark_snapshot_complete(self) -> None:
    """Signal order snapshot completion (thread-safe)."""
    # ... (dispatch snapshot_complete to hooks)

def raise_error(self, exception: ProviderException) -> None:
    """Dispatch order request errors to hooks (thread-safe)."""
    # ... (dispatch error to hooks, no req_id correlation)
```

### TWS Protocol Internalization

OrderTracker sends TWS protocol messages directly (no callback injection):

```python
def __placeOrder(
    self,
    orderId: int,
    contract: Contract,
    order: Order,
    tracked: TrackedOrder,
) -> None:
    """Send PLACE_ORDER protobuf message to TWS (internal)."""
    ORDER_PROTO = protobuf.OrderProto()
    ORDER_PROTO.orderId = orderId
    ORDER_PROTO.contract.CopyFrom(protobuf.ContractProto(...))
    ORDER_PROTO.order.CopyFrom(protobuf.OrderProto(...))

    # PLACE_ORDER message (TWS API v10.25+)
    self.ibsocket.send_protobuf(
        OUT.PLACE_ORDER + PROTOBUF_MSG_ID,
        ORDER_PROTO.SerializeToString(),
    )

def __cancelOrder(self, orderId: int) -> None:
    """Send CANCEL_ORDER protobuf message to TWS (internal)."""
    CANCEL_PROTO = protobuf.CancelOrderProto()
    CANCEL_PROTO.orderId = orderId
    CANCEL_PROTO.manualCancelOrderTime = ""  # Empty = immediate

    # CANCEL_ORDER message (TWS API v10.25+)
    self.ibsocket.send_protobuf(
        OUT.CANCEL_ORDER + PROTOBUF_MSG_ID,
        CANCEL_PROTO.SerializeToString(),
    )

def __ensure_snapshot_requested(self) -> None:
    """Send REQ_OPEN_ORDERS if not already requested (auto-request pattern)."""
    if not self._snapshot_requested:
        self._snapshot_requested = True
        self.ibsocket.send_message(OUT.REQ_OPEN_ORDERS)
```

**Rationale:** By internalizing TWS protocol operations, OrderTracker decouples from IBSocket callback injection (no `place_order_fn` / `cancel_order_fn` parameters). Interface-based wiring provides compile-time safety without tight coupling.

### Lazy Initialization (TWSClient)

OrderTracker is created on-demand when first accessed:

```python
class TWSClient:
    def __init__(self, ...):
        self.__order_tracker: OrderTracker | None = None

    @property
    def order_tracker(self) -> OrderTracker:
        """Lazy-initialized OrderTracker for order state tracking."""
        if self.__order_tracker is None:
            self.__order_tracker = OrderTracker(self.ibsocket)
        return self.__order_tracker
```

**Rationale:** OrderTracker subscribes to global order callbacks (`openOrder`, `orderStatus`) via wiring. Lazy initialization avoids activating order tracking for clients that don't need it (e.g., datafeed-only clients).

### Order Submission Logic (\_\_submit_order)

Private method handles order placement with reconciliation, no-op detection, and immutable field guards:

```python
def __submit_order(
    self,
    preorder: PreOrder,
    existing_tracked: TrackedOrder | None,
) -> PlacedOrder:
    """Submit order with reconciliation, no-op detection, and guards (private).

    Args:
        preorder: Frontend order request (domain model).
        existing_tracked: Existing TrackedOrder for modifications, or None for new orders.

    Returns:
        PlacedOrder (domain model) converted from TrackedOrder.

    Raises:
        ProviderException: If immutable field changed (qty/price for OCA parent).
    """
    # 1. Build TWS Contract and Order from PreOrder
    contract, order = prebuild_tws_order(preorder)

    # 2. Reconciliation: Use existing order_id for modifications
    if existing_tracked:
        order_id = existing_tracked.orderId
        # Guard: Check immutable fields (qty/price for OCA parent)
        if existing_tracked.in_oca_group and not existing_tracked.is_oca_child:
            if order.totalQuantity != existing_tracked.order.totalQuantity:
                raise ProviderException("Cannot modify qty of OCA parent")
            if order.lmtPrice != existing_tracked.order.lmtPrice:
                raise ProviderException("Cannot modify price of OCA parent")
    else:
        order_id = self.next_order_id
        self.next_order_id += 1

    # 3. No-op detection: Skip placeOrder if identical (same contract + order + state)
    if existing_tracked and existing_tracked.matches(contract, order):
        return existing_tracked.to_domain()  # Return existing PlacedOrder

    # 4. Create TrackedOrder (stores contract/order/state)
    tracked = TrackedOrder(order_id, contract, order, orderState=OrderState())

    # 5. Send PLACE_ORDER protobuf to TWS
    self.__placeOrder(order_id, contract, order, tracked)

    # 6. Store in __orders dict and dispatch to hooks
    self.__orders[order_id] = tracked
    self._dispatch_snapshot(tracked)

    # 7. Convert to domain model
    return tracked.to_domain()
```

**Key Features:**

- **Reconciliation**: Existing order modifications reuse `order_id` (vs new orders increment `next_order_id`)
- **No-Op Detection**: Identical modifications skip `placeOrder` (avoids redundant TWS messages)
- **Immutable Field Guards**: OCA parent orders cannot change `totalQuantity` or `lmtPrice` (TWS constraint)
- **Private Method**: Not part of public API — TWSBrokerProvider calls `place_order()` wrapper

### Domain Conversion (TrackedOrder.to_domain)

Converts TWS `TrackedOrder` to domain `PlacedOrder` with BracketContext preservation:

```python
class TrackedOrder:
    def to_domain(self) -> PlacedOrder:
        """Convert to domain PlacedOrder model."""
        # BracketContext: Preserved from original PreOrder (for UI display)
        bracket_context = self.bracket_context.to_dict() if self.bracket_context else None

        return PlacedOrder(
            id=str(self.orderId),
            symbol=self.symbol,
            status=self.status,
            side=_map_side(self.order.action),
            type=_map_order_type(self.order),
            qty=self.order.totalQuantity,
            filledQty=self.filledQty,
            remainingQty=self.remainingQty,
            limitPrice=self.order.lmtPrice,
            avgPrice=self.avgFillPrice,
            time=self.time,
            account=self.account,
            exchange=self.contract.exchange,
            permId=self.permId,
            parentId=self.parentId,
            clientId=self.clientId,
            # BracketContext: Nullable dict with stopLoss/takeProfit IDs
            bracket_context=bracket_context,
        )

@dataclass
class BracketContext:
    """Parent-child order references for bracket orders (UI metadata).

    Moved from tws_mappers.py to order_tracker.py (domain ownership).
    """
    parent_id: int | None = None
    stop_loss_id: int | None = None
    take_profit_id: int | None = None

    def to_dict(self) -> dict[str, int]:
        """Convert to dict for domain model (filters None values)."""
        return {
            k: v for k, v in asdict(self).items() if v is not None
        }
```

**Rationale:**

- `BracketContext` moved from `tws_mappers.py` to `order_tracker.py` (domain ownership — bracket logic is order tracking concern, not mapping concern)
- `to_domain()` converts TWS types to domain types (e.g., `Order.action` → `OrderSide`)
- `bracket_context` field preserves parent/child relationships for UI display (TradingView Account Manager)

### Thread Safety

All public methods and callbacks are thread-safe:

```python
# RLock for re-entrant safety (callbacks may trigger other callbacks)
self._lock = threading.RLock()

def upsert_order(self, ...) -> None:
    with self._lock:
        # ... (update __orders dict)

def update_status(self, ...) -> None:
    with self._lock:
        # ... (mutate Order/OrderState)

def mark_snapshot_complete(self) -> None:
    with self._lock:
        # ... (dispatch snapshot_complete)

def place_order(self, preorder: PreOrder) -> PlacedOrder:
    with self._lock:
        return self.__submit_order(preorder, existing_tracked=None)
```

**Rationale:** TWS callbacks fire from reader thread, but `place_order()` called from request thread. RLock prevents race conditions during concurrent access.

### API Summary

**Public Methods (TWSClient/TWSBrokerProvider):**

```python
def place_order(self, preorder: PreOrder) -> PlacedOrder:
    """Place new order or modify existing order (thread-safe)."""
    # ... (calls __submit_order with reconciliation)

def cancel_order(self, order_id: str) -> None:
    """Cancel order by ID (thread-safe)."""
    # ... (calls __cancelOrder)

def subscribe_orders(
    self,
    on_order: OrderCallback,
    on_error: ErrorCallback,
    on_snapshot_complete: SnapshotCompleteCallback | None = None,
) -> None:
    """Subscribe to order updates (thread-safe).

    Hooks receive all orders (global subscription, no req_id).
    Auto-requests snapshot on first hook (lazy pattern).
    """
    # ... (register hooks, call __ensure_snapshot_requested)

def unsubscribe_orders(self, on_order: OrderCallback) -> None:
    """Unsubscribe from order updates (thread-safe)."""
    # ... (remove hooks)
```

**Internal Methods (Private):**

```python
def __submit_order(self, preorder: PreOrder, existing_tracked: TrackedOrder | None) -> PlacedOrder:
    """Submit order with reconciliation, no-op detection, and guards."""

def __placeOrder(self, orderId: int, contract: Contract, order: Order, tracked: TrackedOrder) -> None:
    """Send PLACE_ORDER protobuf to TWS."""

def __cancelOrder(self, orderId: int) -> None:
    """Send CANCEL_ORDER protobuf to TWS."""

def __ensure_snapshot_requested(self) -> None:
    """Send REQ_OPEN_ORDERS if not already requested."""
```

**Reference:**

- **Tests**: `providers/tws/tests/test_order_tracker.py` (unit tests), `test_ibsocket.py` (callback routing), `test_client.py` (delegation)
- **Interfaces**: `wiring_interfaces.py` (`OrderTrackerCBWiringInterface`, `IbSocketWiringInterface`)
- **Usage**: Used by `TWSClient.order_tracker` property and `TWSBrokerProvider.place_order()`, `cancel_order()`, `subscribe_orders()`

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
    async def get_executions(self, symbol: str | None = None) -> list[Execution]  # Get all executions with optional symbol filter. Uses ExecutionTracker.all_executions() for snapshot, domain conversion via TrackedExecution.to_domain().

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
        symbol: str | None,
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

- **Current Implementation**: `TWSBrokerProvider` has real TWS integration for order operations via `_submit_order()` which uses `TWSClient.placeOrderGroup()` and `reqTickerDetails()`. Order streaming (`subscribe_orders()`) is fully TWS-backed via `OrderTracker`. Execution tracking (`get_executions()`, `subscribe_executions()`) is TWS-backed via `ExecutionTracker` with commission joining pattern. Some features (positions, equity streaming) still use in-memory state.
- **Order Streaming**: `subscribe_orders()` delegates to `TWSClient.reqOrdersStream()` which registers callbacks via `OrderTracker.create_stream_hook()`. Initial snapshot is triggered via `reqOpenOrders()` on subscription. Domain conversion uses `tracked_order_to_placed_order()`.
- **Execution Streaming**: `subscribe_executions()` delegates to `ExecutionTracker.create_stream_hook()` with two-phase dispatch (immediate on execDetails, re-dispatch on commissionAndFeesReport). Snapshot triggered via `reqExecutions(ExecutionFilter())`. Optional symbol filtering at provider layer (TrackedExecution.symbol format: "EXCHANGE:SYMBOL").
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
        │       └── reqTickerDetails(ticker) → CachedContract
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
    details = await self._tws_client.reqTickerDetails(ticker)
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

## 2.9 Position Tracking

**Files:** `position_tracker.py`, `wiring_interfaces.py`, `tws_models.py`

PositionTracker manages position state following the interface-based wiring pattern with unique characteristics:

### Architecture

**Simpler than Other Trackers:**

- No request ID tracking (global position subscription per account)
- No per-position waiting hooks (snapshot/stream only)
- No fills history (positions are net aggregates)
- Auto-request pattern: sends `OUT.REQ_POSITIONS` on first callback

**Thread Ownership:**

```
Main Thread (AsyncIO)                    Daemon Thread
─────────────────────                    ─────────────
TWSClient.position_tracker property      IBSocket.position(account, contract, ...)
        │ (lazy initialization)                  │
        │                                position_tracker.ensure_snapshot_requested()
        │                                        │
        │                                position_tracker.upsert_position(...)
        │                                        │
callback(tracked_pos) ◄──────────────── loop.call_soon_threadsafe(...)
```

**Key Differences from Quote/Bars/ContractTracker:**

1. **Lazy Ownership**: Created by `TWSClient.position_tracker` property, not owned by IBSocket
2. **Error Routing by Nature**: Errors routed via `TWSErrorNature.POSITION` (codes 200, 321, 322)
3. **Auto-Request**: `ensure_snapshot_requested()` sends request on first callback (no explicit caller)
4. **No Request ID**: Global subscription, errors dispatched to all hooks

### Wiring Pattern

**Constructor:**

```python
class PositionTracker(PositionTrackerCBWiringInterface):
    def __init__(self, ibsocket: IbSocketWiringInterface) -> None:
        ibsocket.wire_position_tracker(self)  # Bidirectional wiring
        self.ibsocket = ibsocket
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
        self._positions: dict[str, TrackedPosition] = {}  # position_key → TrackedPosition
        self._snapshot_hooks: dict[str, tuple[loop, future]] = {}
        self._stream_hooks: dict[str, tuple[loop, callback, error_callback]] = {}
```

**Callback Methods (thread-safe, called from reader thread):**

```python
def ensure_snapshot_requested(self) -> None:
    """Send reqPositions() if not already requested."""
    if not self._snapshot_requested.is_set():
        VERSION = 1
        self.ibsocket.send_message(OUT.REQ_POSITIONS, [VERSION])
        self._snapshot_requested.set()

def upsert_position(
    self, account: str, contract: Contract, position: Decimal, avgCost: float
) -> None:
    """Create or replace TrackedPosition from position callback."""
    tracked = TrackedPosition(account, contract, position, avgCost)
    self._positions[tracked.position_key] = tracked
    # Dispatch to stream hooks via call_soon_threadsafe(...)

def mark_snapshot_complete(self) -> None:
    """Signal snapshot completion, resolve pending futures."""
    self._snapshot_complete.set()
    # Resolve snapshot hooks with all_positions()

def raise_error(self, exception: ProviderException) -> None:
    """Dispatch error to all hooks (no req_id)."""
    # Reject snapshot futures, dispatch to stream error callbacks
```

**IBSocket Callback Routing:**

```python
class IBSocket:
    def wire_position_tracker(self, tracker: PositionTrackerCBWiringInterface):
        self._position_tracker = tracker

    def position(
        self, account: str, contract: Contract, position: Decimal, avgCost: float
    ):
        if self._position_tracker:
            self._position_tracker.ensure_snapshot_requested()  # Auto-request
            self._position_tracker.upsert_position(account, contract, position, avgCost)

    def positionEnd(self):
        if self._position_tracker:
            self._position_tracker.mark_snapshot_complete()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str):
        # ... (other error routing)
        nature = classify_error(errorCode, errorString)
        if nature == TWSErrorNature.POSITION:
            if self._position_tracker:
                exception = ProviderException(
                    error_code=f"TWS_{errorCode}",
                    message=errorString,
                    category="tws_error"
                )
                self._position_tracker.raise_error(exception)
```

### Error Classification

**File:** `tws_models.py`

Position-specific errors routed via nature classification:

```python
_POSITION_NATURE_CODES: frozenset[int] = frozenset(
    [
        200,  # No security definition found
        321,  # Server error when validating request
        322,  # Unable to connect as client id is already in use
    ]
)

class TWSErrorNature(str, Enum):
    POSITION = "position"  # Global position subscription errors
    # ... (other natures)

def classify_error(error_code: int, error_string: str) -> TWSErrorNature:
    if error_code in _POSITION_NATURE_CODES:
        return TWSErrorNature.POSITION
    # ... (other classifications)
```

**Rationale:** Position subscription is global (no reqId), errors must be dispatched to all hooks.

### TWSClient Integration (Lazy Property)

**File:** `tws_connection.py`

```python
class TWSClient:
    def __init__(self, ...):
        self._ibsocket: IBSocket | None = None
        self._position_tracker: PositionTracker | None = None

    @property
    def position_tracker(self) -> PositionTracker:
        """Lazy-initialized position tracker.

        Creates tracker on first access and wires with IBSocket.
        """
        if self._position_tracker is None:
            self._position_tracker = PositionTracker(ibsocket=self.ibsocket)
        return self._position_tracker
```

**Usage in TWSBrokerProvider:**

```python
class TWSBrokerProvider:
    async def get_positions(self) -> list[Position]:
        tracked = await self._tws_client.position_tracker.all_positions()
        return [t.to_domain() for t in tracked]

    async def subscribe_positions(
        self, callback: Callable[[Position], Coroutine[Any, Any, None]]
    ) -> str:
        return await self._tws_client.position_tracker.create_stream_hook(
            callback=lambda t: callback(t.to_domain())
        )
```

### Testing Patterns

**Mock Interface Approach:**

```python
import pytest
from unittest.mock import Mock, PropertyMock
from trading_api.providers.tws.position_tracker import PositionTracker
from trading_api.providers.tws.wiring_interfaces import IbSocketWiringInterface

@pytest.fixture
def mock_ibsocket():
    """Mock IbSocketWiringInterface for PositionTracker tests."""
    mock = Mock(spec=IbSocketWiringInterface)
    type(mock).next_req_id = PropertyMock(side_effect=range(1000, 10000))
    return mock

def test_position_tracker_wiring(mock_ibsocket):
    """PositionTracker wires itself during __init__."""
    tracker = PositionTracker(ibsocket=mock_ibsocket)
    mock_ibsocket.wire_position_tracker.assert_called_once_with(tracker)
    assert tracker.ibsocket is mock_ibsocket

def test_ensure_snapshot_requested(mock_ibsocket):
    """ensure_snapshot_requested() sends OUT.REQ_POSITIONS."""
    from ibapi.message import OUT
    tracker = PositionTracker(ibsocket=mock_ibsocket)
    tracker.ensure_snapshot_requested()
    mock_ibsocket.send_message.assert_called_once()
    call_args = mock_ibsocket.send_message.call_args
    assert call_args[0][0] == OUT.REQ_POSITIONS  # msgId
    assert call_args[0][1] == [1]  # VERSION = 1
```

**Error Routing Test:**

```python
def test_error_routing_by_nature(mock_ibsocket):
    """Position errors routed via nature classification (no req_id)."""
    from trading_api.providers.tws.tws_models import TWSErrorNature, classify_error
    from trading_api.models.exceptions import ProviderException

    # Verify error code 200 classified as POSITION nature
    assert classify_error(200, "No security definition") == TWSErrorNature.POSITION

    # Mock error dispatch
    tracker = PositionTracker(ibsocket=mock_ibsocket)
    exception = ProviderException(
        error_code="TWS_200", message="No security definition", category="tws_error"
    )
    tracker.raise_error(exception)
    # Verify error dispatched to hooks (no req_id parameter)
```

**See:** `providers/tws/tests/test_position_tracker.py` for complete test suite

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
```

**Note:** StreamData is used by individual Tracker components (QuoteTracker, BarsTracker) for internal accumulation. IBSocket no longer maintains centralized `_stream_data` or `_business_to_tws_key` dictionaries - each Tracker manages its own internal state.

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

**Note:** This section documents legacy patterns from pre-January 2026 architecture. Current implementation uses Tracker pattern with wiring interfaces (see sections 2.3-2.11).

### Current Architecture (January 2026+)

All data requests now use dedicated Tracker components:

- **ContractTracker**: Symbol search and contract details (see section 2.5)
- **QuoteTracker**: Quote snapshots and streaming (see section 2.7)
- **BarsTracker**: Historical and real-time bars (see section 2.8)
- **OrderTracker**: Order state tracking with interface-based wiring, TWS protocol internalization (placeOrder/cancelOrder), reconciliation, no-op detection, immutable field guards, lazy initialization (see section 2.11)
- **PositionTracker**: Position tracking (see section 2.9)
- **AccountTracker**: Account data (see section 2.10)
- **ExecutionTracker**: Trade executions (see section 2.10)

See specific tracker sections for current implementation patterns.

---

    )

    # 3. Issue request if new (reqId is None if reusing existing)
    if reqId is not None:
        request_fn(reqId)

    # 4. Await and transform result
    return transform_fn(await coroutine)

````

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
````

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

    cached = await self._tws_client.reqTickerDetails(ticker_name)
    contract = cached[0].contract
    return self._tws_client.reqBarDataStream(contract, bar_size, bar_callback, on_error=on_error)
```

### Cancellation

```python
# TWSClient
def cancelDataSubscription(self, stream_key: str) -> None:
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

### OCA Group Submission (Bracket Orders)

Used by: `edit_position_brackets()`, `placeOrderGroup()` with brackets

OCA groups use a **transmit strategy** that adapts based on whether a parent order exists:

```python
# TWSClient.placeOcaGroup() - Bracket order submission with reconciliation
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

    # Without parent linkage, the IB transmit chain doesn't work:
    # transmit=False orders stay held indefinitely as standalone.
    # All orders must transmit independently; OCA handles cancellation.
    if not parent_id:
        transmit_all = True

    # Assign OCA attributes to all orders
    for order in children:
        order.ocaGroup = signed_oca_group
        order.ocaType = oca_type

    # Chain pattern: staged (transmit=False) only when parent_id links the chain;
    # otherwise all orders transmit independently.
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
- **Transmit Strategy**: Two modes depending on `parent_id`:
  - `parent_id > 0` (via `placeOrderGroup`): Uses chain pattern (`transmit=False` → `True` on last child). The IB transmit chain fires atomically because all children share a `parentId`.
  - `parent_id = 0` (via `edit_position_brackets`): All orders transmit independently (`transmit_all=True`). Without `parentId` linkage, `transmit=False` orders would be held indefinitely as standalone.
- **OCA Enforcement**: When one order fills, TWS automatically cancels the remaining orders in the group

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

**Error Code 162 Reclassification (January 2026):**

Error code 162 ("Historical data request pacing violation") was previously included in an internal `_NOT_FOUND_CODES` set in `tws_models.py`, treating it as informational. This classification has been **removed**.

**Change Summary:**

- **Before**: Error 162 treated as "no data" → returned empty list
- **After**: Error 162 treated as error → raises `ProviderException` with `PACING` classification

**Rationale**: Error 162 indicates rate limiting by TWS API, not "no data available". Treating it as informational masked underlying pacing issues. Now correctly classified as `PACING` error (recoverable), triggering proper error handling:

- Exception propagates to caller
- Error callbacks invoked for subscriptions
- Retry logic can be applied at provider level with backoff

**Impact**: Code previously swallowing error 162 will now receive `ProviderException`. Consumers should implement appropriate retry/backoff logic for rate-limited requests.

**Current Classification**: Error 162 is now handled by `classify_error()` as:

- **Nature**: `REQUEST` (req_id-based error)
- **Category**: `PACING` (rate limiting)
- **Recoverable**: `True` (can retry with backoff)

**Non-Recoverable Error Convention:**

Error details ending with `_NON_RECOVERABLE` trigger cleanup of associated data structures:

```python
# In _log_handled_error():
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
        └─► nature == REQUEST/SYSTEM → _log_handled_error(...)
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

`_log_handled_error()` routes errors based on business key and request state:

### Error Routing Pattern

Errors are routed through tracker-specific error handlers:

```python
def _log_handled_error(self, category, detail, tws_key, message, timestamp=None):
    # Extract capability from error context
    capability = "shared"  # Default for orphan errors

    error = ProviderException(
        code=f"PROVIDER_TWS_{category}_{detail.upper()}",
        message=f"[{tws_key}] {message}",
        provider="tws",
        capability=capability,
        timestamp=timestamp,
    )

    # 1. Try routing to QuoteTracker via wired interface
    # 2. Try routing to BarsTracker via wired interface
    # 3. Try routing to OrderTracker
    # 4. Fallback: log as orphan error
```

**Thread-Safe Cleanup:** Trackers handle cleanup via their `raise_error()` methods which schedule cleanup in the event loop.

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
