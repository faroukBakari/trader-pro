# Broker Service Architecture

**Status**: Implemented
**Last Updated**: October 27, 2025
**Related Files**:

- `backend/src/trading_api/core/broker_service.py`
- `backend/src/trading_api/models/broker/`

---

## Overview

The `BrokerService` implements a **realistic trading broker simulation** with automatic order execution, position management, and equity tracking. It follows an **event-driven architecture** using a single execution simulator loop that triggers cascading updates across all business objects.

**Key Design Principles:**

- ✅ Single background task for all executions (no task proliferation)
- ✅ Callback-based broadcasting (no queue overhead)
- ✅ Subscription-driven lifecycle (starts/stops automatically)
- ✅ Immutable execution cascade (deterministic update order)

---

## Architecture Components

### 1. Core Data Structures

```python
class BrokerService(WsRouteService):
    # Business State (In-Memory)
    _orders: Dict[str, PlacedOrder]           # order_id → PlacedOrder
    _positions: Dict[str, Position]           # symbol → Position
    _executions: List[Execution]              # Chronological execution history
    _equity: EquityData                       # Current equity/balance/P&L

    # WebSocket Infrastructure
    _update_callbacks: Dict[str, Callable]    # topic_type → broadcast_callback
    _execution_simulator_task: Optional[Task] # Single background task

    # Configuration
    _execution_delay: float | None            # Delay between executions
```

**Design Rationale:**

- **In-memory storage**: Fast, simple, suitable for demo/development
- **Dict-based lookups**: O(1) access for orders and positions
- **Single task**: Prevents race conditions and task explosion
- **Callback registry**: Direct invocation, no queue overhead

---

## Execution Simulator Architecture

### Overview

The execution simulator is the **heart of the broker service**. It's a single background task that:

1. Picks random WORKING orders at random intervals (1-2 seconds)
2. Simulates execution and creates an `Execution` object
3. Triggers a cascade of updates across orders, equity, and positions
4. Broadcasts updates to WebSocket subscribers via callbacks

### Lifecycle Management

```python
async def create_topic(topic: str, callback: Callable) -> None:
    """
    Register callback for topic type.
    Start execution simulator if this is the first subscription.
    """
    topic_type, params = topic.split(":", 1)

    # Register callback (one per topic type for now)
    if topic_type not in self._update_callbacks:
        self._update_callbacks[topic_type] = callback

    # Start simulator if not running and we have subscribers
    if self._execution_simulator_task is None and len(self._update_callbacks) > 0:
        self._execution_simulator_task = asyncio.create_task(
            self._execution_simulator()
        )

def remove_topic(topic: str) -> None:
    """
    Unregister callback for topic type.
    Stop execution simulator if no more subscribers.
    """
    topic_type, _ = topic.split(":", 1)

    # Remove callback
    if topic_type in self._update_callbacks:
        del self._update_callbacks[topic_type]

    # Stop simulator if no more subscribers
    if len(self._update_callbacks) == 0 and self._execution_simulator_task:
        self._execution_simulator_task.cancel()
        self._execution_simulator_task = None
```

**Key Features:**

- ✅ **Automatic startup**: First subscription starts the simulator
- ✅ **Automatic shutdown**: Last unsubscription stops the simulator
- ✅ **Resource efficient**: No background work when no clients connected
- ✅ **Single task guarantee**: Only one simulator task runs at a time

---

### Execution Simulator Loop

```python
async def _execution_simulator(self) -> None:
    """
    Single background task that simulates random order executions.

    Flow:
        1. Sleep random interval (1-2 seconds)
        2. Find all WORKING orders
        3. Pick a random order
        4. Call _simulate_execution() → triggers cascade
        5. Repeat
    """
    while True:
        try:
            # Random delay between executions (realistic trading)
            delay = self._execution_delay or random.uniform(1, 2)
            await asyncio.sleep(delay)

            # Find all executable orders
            working_orders = [
                order_id
                for order_id, order in self._orders.items()
                if order.status == OrderStatus.WORKING
            ]

            if working_orders:
                # Pick random order to execute
                order_id = random.choice(working_orders)
                await self._simulate_execution(order_id)

        except asyncio.CancelledError:
            logger.info("Execution simulator cancelled")
            break
        except Exception as e:
            logger.error(f"Error in execution simulator: {e}", exc_info=True)
            # Continue running despite errors
```

**Design Decisions:**

- **Random intervals**: Realistic trading simulation (configurable for testing)
- **Random selection**: Unbiased execution across all pending orders
- **Error resilience**: Continues running despite individual execution failures
- **Cancellation support**: Clean shutdown via `asyncio.CancelledError`

---

## Execution Cascade

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Execution Simulator (1-2 second intervals)                     │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  _simulate_execution() │
                    └────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 1. Execution    │───▶│ 2. Order Update │───▶│ 3. Equity Update│
│    Created      │    │    (FILLED)     │    │    (_update_    │
└─────────────────┘    └─────────────────┘    │     equity)     │
         │                       │             └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ broadcast(      │    │ broadcast(      │    │ broadcast(      │
│ "executions")   │    │ "orders")       │    │ "equity")       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │ 4. Position     │
                                               │    Update       │
                                               │    (_update_    │
                                               │     position)   │
                                               └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │ broadcast(      │
                                               │ "positions")    │
                                               └─────────────────┘
```

### Cascade Implementation

```python
async def _simulate_execution(self, order_id: str) -> None:
    """
    Simulate execution and trigger update cascade.

    Cascade Order (IMMUTABLE):
        1. Create execution → broadcast
        2. Update order status → broadcast
        3. Update equity → broadcast
        4. Update position → broadcast
    """
    # Small delay for realism
    await asyncio.sleep(0.2)

    order = self._orders.get(order_id)
    if not order or order.status != OrderStatus.WORKING:
        return

    # Get execution price (market, limit, or stop)
    execution_price = self._get_execution_price(order)

    # 1. CREATE EXECUTION
    execution = Execution(
        symbol=order.symbol,
        price=execution_price,
        qty=order.qty,
        side=order.side,
        time=int(time.time() * 1000),
    )
    self._executions.append(execution)

    # Broadcast execution update
    if "executions" in self._update_callbacks:
        self._update_callbacks["executions"](execution)

    # 2. UPDATE ORDER STATUS
    order.status = OrderStatus.FILLED
    order.filledQty = order.qty
    order.avgPrice = execution_price
    order.updateTime = execution.time

    # Broadcast order update
    if "orders" in self._update_callbacks:
        self._update_callbacks["orders"](order)

    # 3. TRIGGER EQUITY UPDATE (cascades to position)
    self._update_equity(execution)
```

**Critical Design Points:**

- ✅ **Deterministic order**: Always executes in the same sequence
- ✅ **Immediate broadcasting**: No queuing delays
- ✅ **Conditional callbacks**: Only broadcast if subscribers exist
- ✅ **Cascade trigger**: `_update_equity()` internally calls `_update_position()`

---

### Equity Update Logic

```python
def _update_equity(self, execution: Execution) -> None:
    """
    Update equity after execution and broadcast changes.

    Logic:
        - Calculate execution value (side * qty * price)
        - Update position P&L (unrealized/realized)
        - Update balance and equity
        - Broadcast equity update
        - Trigger position update cascade
    """
    execution_value = execution.side * execution.qty * execution.price

    position = self._positions.get(execution.symbol)
    if position is not None and position.qty != 0:
        # Existing position - calculate P&L
        position_value = position.side * position.avgPrice * position.qty
        new_position_size = abs(position.side * position.qty) + (
            execution.side * execution.qty
        )
        new_position_value = execution_value + position_value
        new_position_side = (0 <= new_position_value) and Side.BUY or Side.SELL

        if position.side == execution.side:
            # Adding to position - update unrealized P&L
            new_avg_price = new_position_value / new_position_size
            unrealized_pnl = (
                (execution.price - new_avg_price) * new_position_side * new_position_size
            )
            self.unrealizedPL[execution.symbol] = unrealized_pnl
            self.accounting.unrealizedPL = sum(self.unrealizedPL.values())
            self.accounting.equity = self.accounting.balance + self.accounting.unrealizedPL

        if position.side != execution.side:
            # Closing position - realize P&L
            pnl = (execution.price - position.avgPrice) * execution.side * execution.qty
            self.accounting.balance += pnl
            self.accounting.realizedPL += pnl

    # Broadcast equity update
    if "equity" in self._update_callbacks:
        self._update_callbacks["equity"](self.accounting)

    # Trigger position update cascade
    self._update_position(execution)
```

**P&L Calculation:**

- **Unrealized P&L**: When adding to existing position (same side)
- **Realized P&L**: When reducing/closing position (opposite side)
- **Balance**: Starting capital + realized P&L
- **Equity**: Balance + unrealized P&L

---

### Position Update Logic

```python
def _update_position(self, execution: Execution) -> None:
    """
    Update position from execution and broadcast changes.

    Cases:
        1. New position: Create and broadcast
        2. Adding to position: Update avg price and broadcast
        3. Closing position: Set qty=0, broadcast, then delete
    """
    existing = self._positions.get(execution.symbol)

    if existing:
        # Update existing position
        total_cost = existing.avgPrice * existing.qty * existing.side
        total_cost += execution.price * execution.qty * execution.side
        total_qty = existing.qty * existing.side + execution.qty * execution.side

        if total_qty != 0:
            # Position still open - update
            total_side = Side.BUY if total_qty > 0 else Side.SELL
            existing.side = total_side
            existing.qty = abs(total_qty)
            existing.avgPrice = total_cost / total_qty

            if "positions" in self._update_callbacks:
                self._update_callbacks["positions"](existing)
        else:
            # Position closed - broadcast with qty=0 then delete
            existing.qty = 0
            if "positions" in self._update_callbacks:
                self._update_callbacks["positions"](existing)

            del self._positions[execution.symbol]
    else:
        # New position
        new_position = Position(
            id=execution.symbol,
            symbol=execution.symbol,
            qty=execution.qty,
            side=execution.side,
            avgPrice=execution.price,
        )
        self._positions[execution.symbol] = new_position

        if "positions" in self._update_callbacks:
            self._update_callbacks["positions"](new_position)
```

**Important:**

- ⚠️ **qty=0 broadcast**: TradingView requires position update with `qty=0` to confirm closure (within 10 seconds)
- ✅ **Average price calculation**: Weighted average when adding to position
- ✅ **Side flip detection**: Position can flip from BUY to SELL

---

## Price Determination

### Order Execution Price Logic

```python
def _get_execution_price(self, order: PlacedOrder) -> float:
    """
    Determine execution price based on order type and available data.

    Priority:
        1. Market orders: limitPrice > seenPrice > 100.0 (fallback)
        2. Limit orders: limitPrice (required)
        3. Stop orders: stopPrice (required)

    Future: Integrate datafeed service for real market prices
    """
    if order.type == OrderType.MARKET:
        # TODO: Inject datafeed service for current market price
        return order.limitPrice if order.limitPrice is not None else 100.0
    elif order.type == OrderType.LIMIT and order.limitPrice is not None:
        return order.limitPrice
    elif order.type == OrderType.STOP and order.stopPrice is not None:
        return order.stopPrice
    else:
        return 100.0  # Fallback
```

### Order Placement Price Logic

```python
async def place_order(self, order: PreOrder) -> PlaceOrderResult:
    """
    Determine limit price from multiple sources (priority order).

    Priority:
        1. order.limitPrice (explicit)
        2. order.seenPrice (price at order creation)
        3. order.currentQuotes.ask/bid (current market)
    """
    limit_price = order.limitPrice
    if limit_price is None:
        limit_price = order.seenPrice
    if limit_price is None and order.currentQuotes is not None:
        limit_price = (
            order.currentQuotes.ask
            if order.side == Side.BUY
            else order.currentQuotes.bid
        )

    placed_order = PlacedOrder(
        # ... other fields
        limitPrice=limit_price,
    )
```

**Design Notes:**

- `seenPrice`: TradingView sends this but it's not in official type definitions (requires type assertion)
- `currentQuotes`: New model (`CurrentQuotes`) with ask/bid prices
- Future enhancement: Integrate with datafeed service for real-time market prices

---

## WebSocket Integration

### Callback Registration

```python
async def create_topic(self, topic: str, topic_update: Callable) -> None:
    """
    Register callback for topic type.

    Topic format: "topic_type:{json_params}"
    Example: "orders:{\"accountId\":\"DEMO-ACCOUNT\"}"

    Note: accountId param currently ignored (single account support)
    """
    if ":" not in topic:
        raise ValueError(f"Invalid topic format: {topic}")

    topic_type, _ = topic.split(":", 1)

    # Register callback (single callback per type for now)
    if topic_type not in self._update_callbacks:
        logger.info(f"Registering callback for topic type: {topic_type}")
        self._update_callbacks[topic_type] = topic_update

        # Send initial connection status if broker-connection topic
        if topic_type == "broker-connection":
            status = BrokerConnectionStatus(
                status=1,  # Connected
                message="Connected to demo broker",
                disconnectType=None,
                timestamp=int(time.time() * 1000),
            )
            topic_update(status)

    # Start execution simulator if not running
    if self._execution_simulator_task is None and len(self._update_callbacks) > 0:
        self._execution_simulator_task = asyncio.create_task(
            self._execution_simulator()
        )
```

**Current Limitations:**

- Single callback per topic type (no per-subscription filtering)
- AccountId parameter ignored (single account support)
- Future: Multi-account support with per-account filtering

---

### Broadcasting Updates

```python
# Direct callback invocation (no queues)
if "orders" in self._update_callbacks:
    logger.info(f"Broadcasting order update: {order.id}")
    self._update_callbacks["orders"](order)

if "positions" in self._update_callbacks:
    logger.info(f"Broadcasting position update: {position.symbol}")
    self._update_callbacks["positions"](position)

if "executions" in self._update_callbacks:
    logger.info(f"Broadcasting execution: {execution.symbol}")
    self._update_callbacks["executions"](execution)

if "equity" in self._update_callbacks:
    logger.info(f"Broadcasting equity update: {self.accounting}")
    self._update_callbacks["equity"](self.accounting)
```

**Advantages of Callback Pattern:**

- ✅ **Zero latency**: Direct function call, no queue overhead
- ✅ **Deterministic ordering**: Updates always in cascade order
- ✅ **Memory efficient**: No queue buffering
- ✅ **Simple debugging**: Stack trace shows full execution path

---

## Testing Strategies

### Configurable Execution Delay

```python
# Production: Random 1-2 second intervals
service = BrokerService()

# Fast testing: 100ms intervals
service = BrokerService(execution_delay=0.1)

# Manual testing: Disable automatic execution
service = BrokerService(execution_delay=None)

# Custom testing: 5 second intervals
service = BrokerService(execution_delay=5.0)
```

### Testing Execution Cascade

```python
async def test_execution_cascade():
    """Test that execution triggers all updates in correct order"""
    service = BrokerService(execution_delay=None)  # Manual control

    # Track callback invocations
    callbacks = {
        "executions": [],
        "orders": [],
        "equity": [],
        "positions": [],
    }

    # Register test callbacks
    for topic_type in callbacks.keys():
        await service.create_topic(
            f"{topic_type}:{{\"accountId\":\"TEST\"}}",
            lambda data, t=topic_type: callbacks[t].append(data)
        )

    # Place order
    order = PreOrder(
        symbol="AAPL",
        type=OrderType.MARKET,
        side=Side.BUY,
        qty=10,
        limitPrice=150.0,
    )
    result = await service.place_order(order)

    # Manually trigger execution
    await service._simulate_execution(result.orderId)

    # Verify cascade order
    assert len(callbacks["executions"]) == 1
    assert len(callbacks["orders"]) == 1
    assert len(callbacks["equity"]) == 1
    assert len(callbacks["positions"]) == 1

    # Verify data consistency
    execution = callbacks["executions"][0]
    order = callbacks["orders"][0]
    assert order.status == OrderStatus.FILLED
    assert order.filledQty == execution.qty
```

### Testing Lifecycle Management

```python
async def test_simulator_lifecycle():
    """Test automatic start/stop of execution simulator"""
    service = BrokerService(execution_delay=0.1)

    # Initially no simulator
    assert service._execution_simulator_task is None

    # First subscription starts simulator
    await service.create_topic(
        "orders:{\"accountId\":\"TEST\"}",
        lambda data: None
    )
    assert service._execution_simulator_task is not None
    assert not service._execution_simulator_task.done()

    # Remove subscription stops simulator
    service.remove_topic("orders:{\"accountId\":\"TEST\"}")
    await asyncio.sleep(0.1)  # Allow cancellation
    assert service._execution_simulator_task is None
```

---

## Design Evolution

### Previous Architecture (Removed)

**Queue-Based Event Pipes:**

```python
# Old pattern (removed in commit 30877b6)
self._orders_queue: asyncio.Queue[PlacedOrder] = asyncio.Queue()
self._positions_queue: asyncio.Queue[Position] = asyncio.Queue()
self._executions_queue: asyncio.Queue[Execution] = asyncio.Queue()

async def executions_updates(self) -> Execution:
    update = await self._executions_queue.get()  # Blocking
    return update
```

**Problems:**

- ❌ Complex lifecycle management (who creates/destroys queues?)
- ❌ Memory overhead (queue buffering)
- ❌ Consumer management (who reads from queues?)
- ❌ Ordering guarantees unclear
- ❌ Error handling complicated

### Current Architecture (Callback-Based)

**Direct Callbacks:**

```python
self._update_callbacks: Dict[str, Callable] = {}

if "executions" in self._update_callbacks:
    self._update_callbacks["executions"](execution)  # Direct call
```

**Benefits:**

- ✅ Simple lifecycle (register/unregister)
- ✅ Zero memory overhead
- ✅ Clear ownership (service owns callbacks)
- ✅ Deterministic ordering (cascade sequence)
- ✅ Simple error handling (exceptions propagate)

---

## Future Enhancements

### Multi-Account Support

```python
class BrokerService:
    def __init__(self):
        # Multi-account storage
        self._accounts: Dict[str, BrokerAccount] = {}

    async def create_topic(self, topic: str, callback: Callable) -> None:
        topic_type, params_json = topic.split(":", 1)
        params = json.loads(params_json)
        account_id = params.get("accountId", "DEMO-ACCOUNT")

        # Get or create account
        if account_id not in self._accounts:
            self._accounts[account_id] = BrokerAccount(account_id)

        # Register callback with account context
        self._accounts[account_id].register_callback(topic_type, callback)
```

### Datafeed Integration

```python
class BrokerService:
    def __init__(self, datafeed_service: DatafeedService):
        self.datafeed = datafeed_service

    def _get_execution_price(self, order: PlacedOrder) -> float:
        if order.type == OrderType.MARKET:
            # Get real market price from datafeed
            quotes = await self.datafeed.get_quotes([order.symbol])
            return quotes[0].ask if order.side == Side.BUY else quotes[0].bid
        # ... rest of logic
```

### Advanced Order Types

- **Stop-Loss Monitoring**: Check prices on each tick
- **Take-Profit Monitoring**: Automatic position closure
- **Trailing Stops**: Dynamic stop adjustment
- **Partial Fills**: Split large orders across multiple executions

### Risk Management

- **Margin Calculation**: Real-time margin requirements
- **Position Limits**: Max position size per symbol
- **Daily Loss Limits**: Stop trading on excessive losses
- **Order Validation**: Pre-trade risk checks

---

## Related Documentation

- **[WEBSOCKET-METHODOLOGY.md](../WEBSOCKET-METHODOLOGY.md)** - TDD workflow for WebSocket features
- **[API-METHODOLOGY.md](../API-METHODOLOGY.md)** - TDD workflow for REST API features
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - Overall system architecture

---

## Troubleshooting

### Simulator Not Starting

**Symptom:** Orders placed but never execute

**Diagnosis:**

```python
# Check if simulator is running
assert service._execution_simulator_task is not None
assert not service._execution_simulator_task.done()

# Check if callbacks registered
assert len(service._update_callbacks) > 0
```

**Fix:** Ensure at least one WebSocket subscription exists

### No Updates Received

**Symptom:** Executions happen but no WebSocket updates

**Diagnosis:**

```python
# Check callback registration
print(service._update_callbacks.keys())  # Should include topic types

# Enable debug logging
logger.setLevel(logging.DEBUG)
```

**Fix:** Verify topic format matches exactly (case-sensitive)

### Memory Leak

**Symptom:** Memory usage grows over time

**Diagnosis:**

```python
# Check execution history
print(len(service._executions))  # Should not grow unbounded
```

**Fix:** Implement execution history pruning (keep last N executions)

---

**Last Updated**: October 27, 2025
**Maintained by**: Development Team
