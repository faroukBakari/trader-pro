# Module Independence Guide

**Status**: ✅ Production Ready  
**Last Updated**: January 24, 2026  
**Version**: 1.0.0

> **🔴 This document contains NON-NEGOTIABLE architectural rules**. Violating these principles causes scaling failures, data corruption, and maintenance nightmares.

---

## Table of Contents

- [Overview](#overview)
- [The Five Core Rules](#the-five-core-rules)
- [Rule 1: Module as Microservice](#rule-1-module-as-microservice)
- [Rule 2: Statelessness](#rule-2-statelessness)
- [Rule 3: Data Ownership](#rule-3-data-ownership)
- [Rule 4: No Inter-Module Coupling](#rule-4-no-inter-module-coupling)
- [Rule 5: Orchestration Pattern](#rule-5-orchestration-pattern)
- [Anti-Pattern Gallery](#anti-pattern-gallery)
- [Code Review Checklist](#code-review-checklist)
- [Refactoring Guide](#refactoring-guide)
- [FAQ](#faq)

---

## Overview

The Trading Pro backend uses a **modular monorepo architecture** where each module functions as an independent microservice. This guide documents the non-negotiable rules that maintain this independence.

**Why Module Independence Matters**:

| Without Independence                | With Independence               |
| ----------------------------------- | ------------------------------- |
| Modules cannot scale independently  | Each module scales horizontally |
| One module crash cascades to others | Fault isolation per module      |
| Deploy entire system for one change | Deploy single module            |
| Complex circular dependencies       | Clear ownership boundaries      |
| Shared state causes race conditions | Stateless, predictable behavior |

---

## The Five Core Rules

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THE FIVE CORE RULES                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   1. MODULE AS MICROSERVICE                                             │
│      Each module runs independently in its own container                │
│                                                                          │
│   2. STATELESSNESS                                                      │
│      No in-memory business state; use Repository pattern                │
│                                                                          │
│   3. DATA OWNERSHIP                                                     │
│      Repositories strictly owned by their module; no cross-module DB    │
│                                                                          │
│   4. NO INTER-MODULE COUPLING                                           │
│      Modules never call other modules' APIs directly                    │
│                                                                          │
│   5. ORCHESTRATION PATTERN                                              │
│      UI/Gateway aggregates data; modules receive complete requests      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Rule 1: Module as Microservice

**Principle**: Each module must be capable of running in complete isolation within its own container.

### What This Means

```python
# Each module is a complete, self-contained unit
modules/
├── broker/           # Can run alone: docker run --module broker
│   ├── __init__.py   # BrokerModule
│   ├── service.py    # BrokerService
│   ├── api/v1.py     # REST endpoints
│   ├── ws/v1/        # WebSocket endpoints
│   └── repository.py # Data access (module-owned)
│
├── datafeed/         # Can run alone: docker run --module datafeed
│   └── ...
│
└── auth/             # Can run alone: docker run --module auth
    └── ...
```

### ✅ Correct Implementation

```python
# modules/broker/__init__.py
class BrokerModule(Module):
    """Broker module - completely self-contained."""

    @classmethod
    def module_dir(cls) -> Path:
        return Path(__file__).parent

    # No dependencies on other modules!
    # All required functionality is within this module
```

### ❌ Violation Example

```python
# modules/broker/__init__.py
from trading_api.modules.datafeed import DatafeedService  # ❌ VIOLATION!

class BrokerModule(Module):
    def __init__(self):
        # Importing from another module creates coupling
        self.datafeed = DatafeedService()  # ❌ NEVER DO THIS
```

### Verification

```bash
# Test module runs in isolation
ENABLED_MODULES=broker make dev
curl http://localhost:8000/api/v1/broker/health  # Should work!

# If this fails, the module has hidden dependencies
```

---

## Rule 2: Statelessness

**Principle**: Modules must remain stateless to support horizontal scaling. Use the Repository pattern for persistent data.

### What "Stateless" Means

- **No class-level mutable state** that persists across requests
- **No global variables** storing business data
- **No in-memory caches** with business-critical information
- **Request-scoped only**: Each request is independent

### ✅ Correct: Stateless Service

```python
class BrokerService(ServiceInterface):
    def __init__(self, module_dir: Path, *, providers: list | None = None):
        super().__init__(module_dir, providers=providers)
        # Repository handles persistence - external to this instance
        self._order_repo = OrderRepository(database_url=os.environ["DATABASE_URL"])

    async def place_order(self, order: PreOrder) -> PlacedOrder:
        # Every request is independent
        # Data persisted externally via repository
        placed = await self._order_repo.create(order)
        return placed

    async def get_orders(self, user_id: str) -> list[PlacedOrder]:
        # No local state - always fetch from repository
        return await self._order_repo.find_by_user(user_id)
```

### ❌ Violation: Stateful Service

```python
class BrokerService(ServiceInterface):
    def __init__(self, module_dir: Path):
        super().__init__(module_dir)
        self._orders: dict[str, PlacedOrder] = {}  # ❌ IN-MEMORY STATE!
        self._order_count = 0  # ❌ MUTABLE CLASS STATE!

    async def place_order(self, order: PreOrder) -> PlacedOrder:
        self._order_count += 1  # ❌ Lost on restart!
        placed = PlacedOrder(id=str(self._order_count), **order.dict())
        self._orders[placed.id] = placed  # ❌ Not shared across instances!
        return placed
```

**Why This Fails**:

```
Instance 1: _orders = {"1": order1, "2": order2}
Instance 2: _orders = {"1": order3}  # Different data!
Instance 3: _orders = {}  # Empty after restart!

Load balancer routes requests randomly → inconsistent results
```

### Allowed Patterns

| ✅ Allowed                      | ❌ Prohibited                       |
| ------------------------------- | ----------------------------------- |
| Repository access (external DB) | In-memory business data             |
| Read-only configuration         | Mutable global/class state          |
| Request-scoped variables        | Singleton caches with business data |
| Provider capabilities           | Session storage in memory           |
| Immutable constants             | Order counters, ID generators       |

---

## Rule 3: Data Ownership

**Principle**: Repositories are strictly owned by their specific modules. Cross-module database access is prohibited.

### Ownership Boundaries

```
BROKER MODULE                      DATAFEED MODULE
┌─────────────────────┐            ┌─────────────────────┐
│ BrokerService       │            │ DatafeedService     │
│   ↓                 │            │   ↓                 │
│ OrderRepository  ───┼──── ❌ ────┼─► BarRepository     │
│ PositionRepository  │   NEVER    │ QuoteRepository     │
│ ExecutionRepository │   CROSS    │ SymbolRepository    │
└─────────────────────┘            └─────────────────────┘
         ↓                                  ↓
┌─────────────────────┐            ┌─────────────────────┐
│ broker_database     │            │ datafeed_database   │
│ - orders table      │            │ - bars table        │
│ - positions table   │            │ - quotes table      │
│ - executions table  │            │ - symbols table     │
└─────────────────────┘            └─────────────────────┘
```

### ✅ Correct: Module-Owned Repository

```python
# modules/broker/repository.py
class OrderRepository:
    """Order repository - OWNED by broker module."""

    def __init__(self, database_url: str):
        # Connects to broker-specific database
        self._db = create_engine(database_url)

    async def create(self, order: PreOrder) -> PlacedOrder:
        # Only broker module uses this repository
        ...

# modules/broker/service.py
class BrokerService(ServiceInterface):
    def __init__(self, module_dir: Path):
        super().__init__(module_dir)
        # Repository owned by this module
        self._order_repo = OrderRepository(os.environ["BROKER_DATABASE_URL"])
```

### ❌ Violation: Cross-Module Repository Access

```python
# modules/datafeed/service.py
from trading_api.modules.broker.repository import OrderRepository  # ❌ VIOLATION!

class DatafeedService(ServiceInterface):
    def __init__(self, module_dir: Path):
        super().__init__(module_dir)
        # Accessing broker's repository from datafeed module
        self._order_repo = OrderRepository(...)  # ❌ DATA OWNERSHIP VIOLATION!

    async def get_quote_with_orders(self, symbol: str):
        quote = await self._quote_repo.get(symbol)
        orders = await self._order_repo.find_by_symbol(symbol)  # ❌ WRONG!
        return {...}
```

### Scaling Context

Repositories ARE shared across instances of the SAME module:

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Broker #1   │   │ Broker #2   │   │ Broker #3   │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   broker_database   │  ✅ Shared across broker instances
              │   (PostgreSQL)      │
              └─────────────────────┘
```

But NEVER across different modules:

```
┌─────────────┐                      ┌─────────────┐
│   Broker    │                      │  Datafeed   │
└──────┬──────┘                      └──────┬──────┘
       │                                    │
       ▼                                    ▼
┌─────────────────┐              ┌─────────────────┐
│ broker_database │   ❌ NEVER   │datafeed_database│
└─────────────────┘   SHARE DB   └─────────────────┘
```

---

## Rule 4: No Inter-Module Coupling

**Principle**: While modules can technically communicate via API/WS clients, this is strongly discouraged to prevent tight coupling.

### The "Spaghetti Effect"

```
❌ SPAGHETTI (Avoid):

  Broker ──────► Datafeed
    │               │
    │               ▼
    └──────────► Auth ◄──── Datafeed
                  │
                  ▼
               Broker (circular!)
```

```
✅ ORCHESTRATED (Correct):

              UI / Gateway
                   │
       ┌───────────┼───────────┐
       │           │           │
       ▼           ▼           ▼
    Broker     Datafeed      Auth
  (autonomous) (autonomous) (autonomous)
```

### ✅ Correct: Autonomous Route

```python
# modules/broker/api/v1.py
class BrokerApi(APIRouterInterface):

    @self.post("/orders")
    async def place_order(self, order: PreOrderComplete):
        """Place order with all required data in request."""
        # All data provided in request - no external calls needed
        # currentPrice, buyingPower, etc. already in order object
        return await self._service.place_order(order)
```

### ❌ Violation: Module Calling Another Module

```python
# modules/broker/api/v1.py
from trading_api.modules.datafeed.client import DatafeedClient  # ❌ COUPLING!

class BrokerApi(APIRouterInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._datafeed = DatafeedClient()  # ❌ INTER-MODULE DEPENDENCY!

    @self.post("/orders")
    async def place_order(self, order: PreOrder):
        # Calling another module from within a route handler
        quote = await self._datafeed.get_quote(order.symbol)  # ❌ VIOLATION!
        return await self._service.place_order(order, quote)
```

### Why This Matters

| Problem               | Consequence                           |
| --------------------- | ------------------------------------- |
| Circular dependencies | Cannot determine startup order        |
| Cascading failures    | Datafeed down → Broker down           |
| Version coupling      | Datafeed API change breaks Broker     |
| Testing complexity    | Must mock entire datafeed module      |
| Deployment coupling   | Cannot deploy broker without datafeed |

---

## Rule 5: Orchestration Pattern

**Principle**: When a module needs data from another module, the UI/Gateway aggregates it and sends a self-sufficient request.

### The Correct Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION FLOW                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   1. UI needs to place order with current price validation              │
│                                                                          │
│      ┌────────────────────┐                                              │
│      │   UI (Orchestrator)│                                              │
│      └──────────┬─────────┘                                              │
│                 │                                                        │
│   2. Fetch required data from each module                               │
│                 │                                                        │
│      ┌──────────┴──────────┐                                            │
│      │                     │                                            │
│      ▼                     ▼                                            │
│   ┌──────────┐       ┌──────────┐                                       │
│   │ Datafeed │       │  Broker  │                                       │
│   │ GET /quote       │ GET /account                                     │
│   └────┬─────┘       └────┬─────┘                                       │
│        │                  │                                              │
│   { price: 150 }    { buyingPower: 10000 }                              │
│        │                  │                                              │
│        └────────┬─────────┘                                              │
│                 │                                                        │
│   3. UI constructs self-sufficient request                              │
│                 │                                                        │
│                 ▼                                                        │
│      ┌──────────────────────────┐                                       │
│      │ PlaceOrderRequest {      │                                       │
│      │   symbol: "AAPL",        │                                       │
│      │   qty: 10,               │                                       │
│      │   currentPrice: 150,     │ ◄── From Datafeed                    │
│      │   buyingPower: 10000     │ ◄── From Broker (account)            │
│      │ }                        │                                       │
│      └────────────┬─────────────┘                                       │
│                   │                                                      │
│   4. Send complete request to target module                             │
│                   │                                                      │
│                   ▼                                                      │
│      ┌──────────────────────────┐                                       │
│      │  Broker Module           │                                       │
│      │  POST /orders            │                                       │
│      │  (has all data needed -  │                                       │
│      │   validates internally)  │                                       │
│      └──────────────────────────┘                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Frontend Implementation Example

```typescript
// Frontend orchestrates the data aggregation
async function placeOrder(orderParams: OrderParams): Promise<PlacedOrder> {
  // 1. Fetch required data from each module
  const [quote, account] = await Promise.all([
    datafeedService.getQuote(orderParams.symbol),
    brokerService.getAccount(),
  ]);

  // 2. Construct self-sufficient request
  const completeOrder: PlaceOrderRequest = {
    ...orderParams,
    currentPrice: quote.last, // From datafeed
    buyingPower: account.buyingPower, // From broker
    timestamp: Date.now(),
  };

  // 3. Send to broker module (autonomous - no further calls needed)
  return await brokerService.placeOrder(completeOrder);
}
```

### Backend Receives Complete Request

```python
# modules/broker/api/v1.py
class BrokerApi(APIRouterInterface):

    @self.post("/orders")
    async def place_order(self, order: PlaceOrderRequest):
        """
        Receives self-sufficient request with all required data.
        No need to call other modules.
        """
        # Validate using data provided in request
        if order.qty * order.currentPrice > order.buyingPower:
            raise HTTPException(400, "Insufficient buying power")

        # Process order - all data available
        return await self._service.place_order(order)
```

---

## Anti-Pattern Gallery

### Anti-Pattern 1: Shared Repository

```python
# ❌ WRONG: Repository used by multiple modules
# shared/repositories/order_repository.py
class SharedOrderRepository:
    """Used by both broker and reporting modules"""  # ❌ VIOLATION!
```

**Fix**: Each module owns its data. Reporting module should receive data via API or events.

### Anti-Pattern 2: Service-to-Service Call

```python
# ❌ WRONG: Broker service calling datafeed service
class BrokerService:
    def __init__(self):
        self._datafeed = DatafeedService()  # ❌ COUPLING!

    async def validate_order(self, order):
        quote = await self._datafeed.get_quote(order.symbol)  # ❌
```

**Fix**: Move quote fetching to UI; include quote data in request.

### Anti-Pattern 3: In-Memory State

```python
# ❌ WRONG: Business state in memory
class BrokerService:
    _instance = None  # ❌ Singleton
    _orders = {}      # ❌ In-memory state

    @classmethod
    def get_instance(cls):  # ❌ Singleton pattern for stateful service
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

**Fix**: Use Repository pattern with external persistence.

### Anti-Pattern 4: Cross-Module Import

```python
# ❌ WRONG: Importing from another module
# modules/broker/service.py
from trading_api.modules.datafeed.models import Quote  # ❌ IMPORT VIOLATION!
from trading_api.modules.auth.service import AuthService  # ❌ COUPLING!
```

**Fix**: Use shared models from `trading_api.models/` or Provider capabilities.

### Anti-Pattern 5: Shared Database Connection

```python
# ❌ WRONG: Single database for all modules
DATABASE_URL = "postgresql://localhost/trading_db"

# modules/broker/repository.py
class OrderRepo:
    db = get_shared_db()  # ❌ Shared connection!

# modules/datafeed/repository.py
class BarRepo:
    db = get_shared_db()  # ❌ Same shared connection!
```

**Fix**: Each module gets its own database URL and connection pool.

---

## Code Review Checklist

Use this checklist when reviewing code changes:

### Module Independence

- [ ] No imports from other `modules/*` packages
- [ ] Module can start with `ENABLED_MODULES=<module>` alone
- [ ] No references to other module services or repositories
- [ ] No shared singleton instances across modules

### Statelessness

- [ ] No class-level mutable state in services
- [ ] No global variables storing business data
- [ ] Repository pattern used for persistence
- [ ] Request-scoped variables only

### Data Ownership

- [ ] Repository belongs to single module
- [ ] No cross-module database queries
- [ ] Module uses own DATABASE_URL environment variable
- [ ] No shared database tables across modules

### API Autonomy

- [ ] Routes don't call other module APIs internally
- [ ] Request contains all data needed for processing
- [ ] No HTTP/WS clients to other modules in route handlers
- [ ] Validation uses request data, not external fetches

### Orchestration

- [ ] Complex flows orchestrated by UI/Gateway
- [ ] Request models include all required context
- [ ] No "fetch then process" patterns in modules

---

## Refactoring Guide

### Converting Coupled Code to Autonomous

**Before** (Coupled):

```python
class BrokerApi:
    @self.post("/orders")
    async def place_order(self, order: SimpleOrder):
        # Calling datafeed module - COUPLED!
        quote = await self._datafeed_client.get_quote(order.symbol)
        validated = order.with_price(quote.last)
        return await self._service.place_order(validated)
```

**After** (Autonomous):

1. Update request model to include required data:

```python
# models/broker/orders.py
class PlaceOrderRequest(BaseModel):
    symbol: str
    qty: int
    side: Side
    order_type: OrderType
    current_price: float  # Added: provided by orchestrator
    buying_power: float   # Added: provided by orchestrator
```

2. Update route to use self-sufficient request:

```python
class BrokerApi:
    @self.post("/orders")
    async def place_order(self, order: PlaceOrderRequest):
        # All data in request - AUTONOMOUS!
        return await self._service.place_order(order)
```

3. Update frontend to orchestrate:

```typescript
async function placeOrder(params: OrderParams) {
  const [quote, account] = await Promise.all([
    datafeedApi.getQuote(params.symbol),
    brokerApi.getAccount(),
  ]);

  return brokerApi.placeOrder({
    ...params,
    currentPrice: quote.last,
    buyingPower: account.buyingPower,
  });
}
```

---

## FAQ

### Q: What if I need to validate data owned by another module?

**A**: The orchestrator (UI/Gateway) fetches the data and includes it in the request. The module validates against the provided data.

### Q: Can modules share read-only reference data?

**A**: Use shared models in `trading_api/models/`. For data that changes, each module maintains its own copy or the orchestrator provides it.

### Q: How do I handle background jobs that need multi-module data?

**A**: Use an event-driven architecture with message queues. Each module publishes events; interested modules subscribe and maintain their own state.

### Q: What about authentication across modules?

**A**: Authentication is handled by middleware in `shared/middleware/auth.py` which validates JWT tokens. The middleware doesn't call the auth module - it uses public key validation only.

### Q: How do I test a module that "needs" data from another?

**A**: Your module should accept all required data in its request. In tests, you provide complete test data. No need to mock other modules.

---

## Related Documentation

- [MODULAR_BACKEND_ARCHITECTURE.md](./MODULAR_BACKEND_ARCHITECTURE.md) - Core architecture
- [PROVIDER-SYSTEM.md](./PROVIDER-SYSTEM.md) - External integration patterns
- [BACKEND_TESTING.md](./BACKEND_TESTING.md) - Testing module isolation
- [BACKEND_MANAGER_GUIDE.md](./BACKEND_MANAGER_GUIDE.md) - Multi-process deployment
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - System-wide architecture

---

## Summary

**The Five Rules - Memorize These**:

1. **Module as Microservice**: Each module runs independently in its own container
2. **Statelessness**: No in-memory business state; use Repository pattern
3. **Data Ownership**: Repositories owned by their module; no cross-module DB access
4. **No Inter-Module Coupling**: Modules never call other modules' APIs
5. **Orchestration Pattern**: UI/Gateway aggregates data; modules receive complete requests

**Enforcement**:

```bash
# Verify import boundaries
make test-boundaries

# Test module isolation
ENABLED_MODULES=broker make dev
```

**When in doubt**: If your design requires one module to know about another module's internals, the design is wrong. Refactor to use the orchestration pattern.
