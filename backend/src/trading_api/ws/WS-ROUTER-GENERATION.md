````markdown
# WebSocket Router Code Generation

## Overview

This project uses code generation for both backend routers and frontend clients to ensure type safety and consistency across the stack.

### Backend: Router Generation

The backend uses a code generation approach to create concrete (non-generic) WebSocket router classes from a generic template. This provides better IDE support, type checking, and eliminates generic type parameters at runtime.

### Frontend: Client Generation

The frontend automatically generates TypeScript types and client factories from the AsyncAPI specification. See `frontend/WS-CLIENT-AUTO-GENERATION.md` for details.

---

## Quick Start: Adding a New WebSocket Route

**Complete example: Adding a "Trades" WebSocket route in 5 minutes**

### Step 1: Define Your Models

Create Pydantic models for your WebSocket messages:

```python
# backend/src/trading_api/models/market/trades.py
from pydantic import BaseModel

class TradeSubscriptionRequest(BaseModel):
    """Request to subscribe to trade updates"""
    symbols: list[str]  # Symbols to subscribe to

class Trade(BaseModel):
    """Individual trade data"""
    symbol: str
    price: float
    quantity: float
    time: int  # Unix timestamp in milliseconds
    side: str  # "buy" or "sell"
```

### Step 2: Export Models

Add exports to make models discoverable:

```python
# backend/src/trading_api/models/market/__init__.py
from .trades import Trade, TradeSubscriptionRequest

__all__ = [
    # ... existing exports
    "Trade",
    "TradeSubscriptionRequest",
]
```

### Step 3: Create Router File with TypeAlias

Create a new file (or add to existing topical file) with TypeAlias declaration:

```python
# backend/src/trading_api/ws/trading.py (new file for trading operations)
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models.market import Trade, TradeSubscriptionRequest
from .generic import WsRouter
from .router_interface import WsRouterInterface

if TYPE_CHECKING:
    # TypeAlias for type checkers - generator will auto-discover this!
    TradeWsRouter: TypeAlias = WsRouter[TradeSubscriptionRequest, Trade]
else:
    # At runtime: use generated concrete class
    from .generated import TradeWsRouter

# Create router instance
trade_router = TradeWsRouter(route="trades", tags=["trading"])
trades_topic_builder = trade_router.topic_builder

# Export routers list (used by ws/__init__.py)
ws_routers: list[WsRouterInterface] = [trade_router]
```

**Note**: You can group related routes in the same file:

- `datafeed.py` - Market data routes (bars, quotes) → exports `ws_routers = [bar_router, quote_router]`
- `trading.py` - Trading routes (trades, orders) → exports `ws_routers = [trade_router, order_router]`
- `account.py` - Account routes (positions, balance) → exports `ws_routers = [position_router, balance_router]`

The generator scans **all** `.py` files in `ws/` directory automatically!

**Note**: You can group related routes in the same file:

- `datafeed.py` - Market data routes (bars, quotes)
- `trading.py` - Trading routes (trades, orders)
- `account.py` - Account routes (positions, balance)

The generator scans **all** `.py` files in `ws/` directory automatically!

### Step 4: Generate the Router

Run the code generator (it auto-discovers your TypeAlias):

```bash
cd backend
make generate-ws-routers
```

**What happens:**

1. Generator scans all `.py` files in `ws/` directory
2. Finds `TradeWsRouter: TypeAlias = WsRouter[TradeSubscriptionRequest, Trade]`
3. Creates `backend/src/trading_api/ws/generated/tradewsrouter.py` with:
   - Concrete `TradeWsRouter` class (no generics)
   - Pre-defined `subscribe`, `unsubscribe`, `update` operations from `generic.py`
   - Full type safety and all quality checks passed

### Step 5: Update ws/**init**.py to Export Routers

Consolidate all routers in the main ws module:

```python
# backend/src/trading_api/ws/__init__.py
from .datafeed import ws_routers as datafeed_ws_routers
from .trading import ws_routers as trading_ws_routers  # 👈 Add new import
from .router_interface import WsRouterInterface

ws_routers: list[WsRouterInterface] = [
    *datafeed_ws_routers,
    *trading_ws_routers,  # 👈 Include trading routers
]

__all__ = ["ws_routers"]
```

**Pattern**: Each topical file (`datafeed.py`, `trading.py`, etc.) exports its own `ws_routers` list, and `__init__.py` consolidates them all into a single list.

### Step 6: Register All Routers in Main AppRegister all WebSocket routers at once:

```python
# backend/src/trading_api/main.py
from .ws import ws_routers  # 👈 Single import from ws module

# ... existing code ...

# Include all WebSocket routers (consolidated list)
for ws_router in ws_routers:
    wsApp.include_router(ws_router)
```

**Benefits**:

- ✅ Single import statement in `main.py`
- ✅ Easy to add new topical files (just update `ws/__init__.py`)
- ✅ Clear separation: each topic file manages its own routers
- ✅ Type-safe: `ws_routers` is typed as `list[WsRouterInterface]`

**File Organization**:

- `datafeed.py` exports `ws_routers = [bar_router, quote_router]`
- `trading.py` exports `ws_routers = [trade_router, order_router]`
- `account.py` exports `ws_routers = [position_router, balance_router]`
- `ws/__init__.py` consolidates: `ws_routers = [*datafeed_ws_routers, *trading_ws_routers, *account_ws_routers]`

**File Organization:**

- `datafeed.py` - Groups market data routes (bars, quotes)
- `trading.py` - Groups trading routes (trades, orders, executions)
- `account.py` - Groups account routes (positions, balance, leverage)

Each file can have multiple routers! The generator finds all TypeAlias declarations automatically.

### Step 7: Verify and Test

```bash
# Start backend to generate AsyncAPI spec
make dev

# Frontend will auto-generate TypeScript types from AsyncAPI
cd ../frontend
make generate-asyncapi-types
```

### Step 8: Use in Frontend

The frontend now has fully typed WebSocket client:

```typescript
// frontend/src/somewhere.ts
import { WsAdapter } from "@/plugins/wsAdapter";
import type {
  Trade,
  TradeSubscriptionRequest,
} from "@/clients/ws-types-generated";

const wsAdapter = new WsAdapter();

// Subscribe to trades (fully type-safe!)
await wsAdapter.trades.subscribe(
  "trades-listener",
  { symbols: ["AAPL", "GOOGL"] },
  (trade: Trade) => {
    console.log("New trade:", trade.symbol, trade.price, trade.quantity);
  }
);
```

### Broadcasting Updates from Backend

```python
# Somewhere in your backend code (e.g., market data service)
from trading_api.main import wsApp
from trading_api.ws.trades import trades_topic_builder

async def broadcast_trade(trade: Trade):
    """Broadcast trade update to subscribers"""
    topic = trades_topic_builder(trade.symbol, {})
    await wsApp.publish(
        topic=topic,
        data=trade,
        message_type="trades.update"
    )
```

**That's it!** 🎉 You now have:

- ✅ Type-safe WebSocket router (backend)
- ✅ Fully typed TypeScript client (frontend)
- ✅ AsyncAPI documentation (auto-generated)
- ✅ Subscribe/unsubscribe operations
- ✅ Server broadcast capability

---

## Backend Architecture

```
backend/src/trading_api/ws/
├── __init__.py            # 👈 Consolidates all ws_routers (main export)
├── generic.py              # Generic template (pre-defined operations)
├── router_interface.py     # Base interface and topic builder logic
├── datafeed.py            # Market data routers (bars, quotes)
├── trading.py             # Trading routers (trades, orders) - add as needed
├── account.py             # Account routers (positions, balance) - add as needed
└── generated/             # Auto-generated concrete classes
    ├── __init__.py        # Generated exports (auto-updated)
    ├── barwsrouter.py     # Generated from datafeed.py
    ├── quotewsrouter.py   # Generated from datafeed.py
    └── tradewsrouter.py   # Generated from trading.py (when you add it)
```

**File Organization Pattern:**

- Group related routes by topic in separate files
- Each file exports its own `ws_routers: list[WsRouterInterface]`
- `ws/__init__.py` consolidates all into single `ws_routers` list
- `main.py` imports and registers: `from .ws import ws_routers`
- Generator automatically finds all TypeAlias declarations across all files
- `generated/` directory is auto-managed (cleared and regenerated each time)

**File Organization Pattern:**

- Group related routes by topic in separate files
- Each file can contain multiple TypeAlias declarations
- Generator automatically finds all TypeAlias declarations across all files
- `generated/` directory is auto-managed (cleared and regenerated each time)

## How It Works

### 1. Template (generic.py) - Pre-Defined Operations

The `generic.py` file contains a generic `WsRouter` class with:

- Type parameters: `__TRequest` and `__TData`
- **Pre-defined operations** (subscribe, unsubscribe, update) already implemented!
- Topic builder logic for routing messages

```python
class WsRouter(OperationRouter, Generic[__TRequest, __TData]):
    def __init__(self, *, route: str = "", tags: list[str | Enum] | None = None):
        super().__init__(prefix=f"{route}.", tags=tags)
        self.route = route

        @self.send("subscribe", reply="subscribe.response")
        async def send_subscribe(payload: __TRequest, client: Client):
            # Implementation already here!
            topic = self.topic_builder(payload)
            client.subscribe(topic)
            return SubscriptionResponse(status="ok", message="Subscribed", topic=topic)

        # unsubscribe and update operations also pre-defined...
```

**Key Point**: You don't write operation handlers - they're generated from the template!

### 2. Auto-Discovery Pattern

Developers declare routers using `TypeAlias` with `TYPE_CHECKING` guard:

```python
# backend/src/trading_api/ws/datafeed.py
if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
else:
    from .generated import BarWsRouter, QuoteWsRouter
```

### 3. Generator Script (scripts/generate_ws_router.py)

The generator **automatically scans** `ws/` directory for TypeAlias patterns:

1. **Scans** all `.py` files (except `__init__.py`, `generic.py`, `router_interface.py`)
2. **Finds** regex pattern: `BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]`
3. **Extracts** class name, request type, and data type
4. **Generates** concrete class by:
   - Removing `Generic[__TRequest, __TData]`
   - Replacing `__TRequest` → `BarsSubscriptionRequest`
   - Replacing `__TData` → `Bar`
   - Keeping all pre-defined operations from template
5. **Outputs** to `ws/generated/barwsrouter.py`

**No manual configuration needed!** Just write the TypeAlias and run `make generate-ws-routers`.

### 3. Wrapper Script (scripts/generate-ws-routers.sh)

The bash wrapper orchestrates the complete workflow with all pre-commit tools:

1. **Generate code** - Runs Python generator
2. **Black formatting** - Formats with `poetry run black`
3. **Import sorting (isort)** - Sorts imports with `poetry run isort`
4. **Ruff formatting** - Additional formatting with `poetry run ruff format`
5. **Auto-fix linter issues** - Applies `poetry run ruff check --fix`
6. **Flake8 linting** - Validates with `poetry run flake8`
7. **Ruff linting** - Final validation with `poetry run ruff check`
8. **Type checking** - Validates with `poetry run mypy`
9. **Import verification** - Tests that generated code imports and works correctly

This ensures generated code passes **all** pre-commit hook checks.

## Usage Patterns

### Pattern 1: TYPE_CHECKING Guard (Recommended)

This pattern provides the best of both worlds: type checking during development and concrete classes at runtime.

```python
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models import Bar, BarsSubscriptionRequest
from .generic import WsRouter

if TYPE_CHECKING:
    # For type checkers (mypy, IDE): use generic version
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
else:
    # At runtime: use generated concrete class (better performance)
    from .generated import BarWsRouter

# Instantiate with parameters
router = BarWsRouter(route="bars", tags=["datafeed"])

# Export topic builder for use in broadcasting
bars_topic_builder = router.topic_builder
```

**Why this pattern?**

- ✅ Type checkers see `WsRouter[BarsSubscriptionRequest, Bar]` with full generic support
- ✅ Runtime uses concrete `BarWsRouter` class (no generic overhead)
- ✅ Best IDE autocomplete and type inference
- ✅ Optimal performance

### Pattern 2: Direct Import (Simpler)

For simpler use cases where you don't need the generic type hints:

```python
from .generated import BarWsRouter

router = BarWsRouter(route="bars", tags=["datafeed"])
bars_topic_builder = router.topic_builder
```

**When to use:**

- ✅ Simple route definitions
- ✅ When type inference is sufficient
- ✅ No complex type manipulation needed

## Pre-Defined Operations (From generic.py)

**Important**: The generated routers come with operations already implemented! You don't write these handlers.

### Built-In Operations

All generated routers automatically include:

#### 1. **Subscribe Operation** (`{route}.subscribe`)

- Handles client subscription requests
- Builds topic using `topic_builder(payload)`
- Subscribes client to topic
- Returns `SubscriptionResponse` with topic

#### 2. **Unsubscribe Operation** (`{route}.unsubscribe`)

- Handles client unsubscription requests
- Builds topic using `topic_builder(payload)`
- Unsubscribes client from topic
- Returns `SubscriptionResponse`

#### 3. **Update Operation** (`{route}.update`)

- Receive-only operation for AsyncAPI documentation
- Defines the data structure for server broadcasts
- Used when calling `wsApp.publish()`

### What You DO Configure

You only configure:

1. **Router instantiation**: `router = BarWsRouter(route="bars", tags=["datafeed"])`
2. **Topic builder access**: `bars_topic_builder = router.topic_builder`
3. **Registration**: `wsApp.include_router(router)`

That's it! The subscribe/unsubscribe/update logic is already there.### Topic Builder Patterns

```python
# Simple topic: channel:symbol
def simple_topic_builder(symbol: str, params: dict) -> str:
    return f"trades:{symbol}"

# Multi-parameter topic: channel:symbol:param
def bars_topic_builder(symbol: str, params: dict) -> str:
    resolution = params.get('resolution', '1')
    return f"bars:{symbol}:{resolution}"

# Complex topic with multiple params
def orderbook_topic_builder(symbol: str, params: dict) -> str:
    depth = params.get('depth', 10)
    level = params.get('level', 1)
    return f"orderbook:{symbol}:{depth}:{level}"
```

## Command Reference

### Generate Routers

```bash
# From backend directory
make generate-ws-routers

# What it does:
# 1. Scans ws/*.py files for TypeAlias patterns
# 2. Auto-discovers all router specifications
# 3. Generates concrete classes in ws/generated/
# 4. Runs all formatters (Black, isort, Ruff)
# 5. Runs all linters (Flake8, Ruff)
# 6. Runs type checker (mypy)
# 7. Verifies imports work correctly
```

**No manual configuration needed** - just add TypeAlias declarations to your files!

### Verify Generation

```bash
# Check generated files
ls -la backend/src/trading_api/ws/generated/

# Test imports
cd backend
poetry run python -c "from trading_api.ws.generated import BarWsRouter; print('OK')"

# Run tests
make test
```

### Clean Generated Files

```bash
# Remove generated routers (will be regenerated on next make generate-ws-routers)
rm -rf backend/src/trading_api/ws/generated/*.py
```

## Benefits

### ✅ Type Safety

- Eliminates generic parameters
- Full type inference in IDEs
- Better autocomplete support

### ✅ Performance

- No generic overhead at runtime
- Concrete types enable optimizations

### ✅ Maintainability

- Single source of truth (generic.py)
- Automated generation ensures consistency
- All quality checks automated

### ✅ Developer Experience

- Clear error messages
- Better IDE navigation
- Simplified debugging

## Quality Checks

All generated code passes the same checks as the pre-commit hooks:

- ✅ Black formatting
- ✅ Import sorting (isort, compatible with black profile)
- ✅ Ruff formatting
- ✅ Ruff linting
- ✅ Flake8 linting
- ✅ Type checking (mypy)
- ✅ Import verification tests

**Result**: Generated code is commit-ready and will pass all pre-commit hook checks.

## File Naming Convention

- **Class name**: `<Name>WsRouter` (e.g., `BarWsRouter`)
- **Module name**: `<name>.py` (lowercase, derived from class name, e.g., `barwsrouter.py`)
- **Router instance**: `router` (exported from generated module)
- **Topic builder**: `<name>_topic_builder` (e.g., `bars_topic_builder`)

## CI/CD Integration

Add to pre-commit hooks or CI pipeline:

```yaml
# Backend router generation
- name: Generate WebSocket routers (backend)
  run: |
    cd backend
    make generate-ws-routers

- name: Verify no uncommitted changes
  run: git diff --exit-code backend/src/trading_api/ws/generated/

# Frontend type generation (in production build)
- name: Generate WebSocket types (frontend)
  run: |
    cd frontend
    make generate-openapi-client && make generate-asyncapi-types
```

## Advanced Topics

### Custom Topic Builders

Topic builders determine how to route messages to specific clients. Customize them for your use case:

```python
# Single parameter
def quotes_topic_builder(symbol: str, params: dict) -> str:
    return f"quotes:{symbol}"

# Multiple parameters
def orderbook_topic_builder(symbol: str, params: dict) -> str:
    depth = params.get('depth', 10)
    return f"orderbook:{symbol}:{depth}"

# Wildcard subscriptions
def news_topic_builder(symbol: str, params: dict) -> str:
    category = params.get('category', 'all')
    return f"news:{category}:{symbol}" if symbol != "*" else f"news:{category}:*"
```

### Broadcasting from Services

```python
# In your service/background task
from trading_api.main import wsApp
from trading_api.ws.trades import trades_topic_builder

class MarketDataService:
    async def on_new_trade(self, trade: Trade):
        """Called when new trade arrives from exchange"""
        # Build topic
        topic = trades_topic_builder(trade.symbol, {})

        # Broadcast to all subscribers of this topic
        await wsApp.publish(
            topic=topic,
            data=trade,
            message_type="trades.update"
        )
```

### Conditional Broadcasting

Only broadcast if there are subscribers:

```python
from trading_api.main import wsApp

async def broadcast_if_subscribed(symbol: str, data: Trade):
    """Only broadcast if someone is listening"""
    topic = trades_topic_builder(symbol, {})

    # Check if topic has subscribers
    if wsApp.has_subscribers(topic):
        await wsApp.publish(topic=topic, data=data, message_type="trades.update")
    else:
        # Skip unnecessary work
        pass
```

### Multi-Symbol Subscriptions

Handle subscriptions to multiple symbols efficiently:

```python
@router.send("subscribe", reply="subscribe.response")
async def subscribe(
    payload: MultiSymbolRequest,  # Has symbols: list[str]
    client: Client,
) -> SubscriptionResponse:
    """Subscribe to multiple symbols at once"""
    topics = []

    for symbol in payload.symbols:
        topic = topic_builder(symbol, payload.params)
        client.subscribe(topic)
        topics.append(topic)

    return SubscriptionResponse(
        status="ok",
        symbol=payload.symbols[0],
        message=f"Subscribed to {len(topics)} symbols",
        topic=topics[0]  # Return first topic
    )
```

### Error Handling

```python
from fastapi import WebSocketException, status

@router.send("subscribe", reply="subscribe.response")
async def subscribe(
    payload: SubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    """Subscribe with validation and error handling"""

    # Validate symbol
    if not payload.symbol or len(payload.symbol) > 20:
        return SubscriptionResponse(
            status="error",
            symbol=payload.symbol,
            message="Invalid symbol",
            topic=""
        )

    # Check if symbol exists (example validation)
    if not await symbol_exists(payload.symbol):
        return SubscriptionResponse(
            status="error",
            symbol=payload.symbol,
            message=f"Symbol {payload.symbol} not found",
            topic=""
        )

    # Subscribe
    topic = topic_builder(payload.symbol, payload.params)
    client.subscribe(topic)

    return SubscriptionResponse(
        status="ok",
        symbol=payload.symbol,
        message=f"Subscribed to {payload.symbol}",
        topic=topic
    )
```

## Full-Stack Integration

### Backend → Frontend Flow

```
1. Define Pydantic models (backend)
   ↓
2. Add TypeAlias declaration in ws/{topic}.py (backend)
   ↓
3. Generate router: make generate-ws-routers (backend)
   → Auto-discovers TypeAlias
   → Generates concrete class with pre-defined operations
   ↓
4. Export router in ws_routers list in topical file
   ↓
5. Update ws/__init__.py to include new topical file
   ↓
6. Register all routers in main.py (from .ws import ws_routers)
   ↓
7. Start backend (generates AsyncAPI spec)
   ↓
8. Frontend auto-generates TypeScript types
   ↓
9. Use type-safe WebSocket client in frontend
```

**Key Difference**: No manual operation implementation needed - they're in the template!

### Frontend Usage After Generation

```typescript
// frontend/src/services/dataService.ts
import { WsAdapter } from "@/plugins/wsAdapter";

export class DataService {
  private wsAdapter = new WsAdapter();

  async subscribeTrades(symbols: string[], onTrade: (trade: Trade) => void) {
    // Fully type-safe!
    await this.wsAdapter.trades.subscribe(
      "trades-service",
      { symbols },
      onTrade
    );
  }

  async unsubscribeTrades() {
    await this.wsAdapter.trades.unsubscribe("trades-service");
  }
}
```

**Result**: Fully type-safe WebSocket communication from backend Python → AsyncAPI → Frontend TypeScript!

## Troubleshooting

### Issue: Import errors after generation

**Symptom**: `ImportError: cannot import name 'YourWsRouter' from 'trading_api.ws.generated'`

**Solution**: Regenerate routers with auto-fixing:

```bash
cd backend
make generate-ws-routers
```

**Root cause**: Models may have changed, or generation was interrupted.

---

### Issue: Type checking fails

**Symptom**: `mypy` reports `error: Name 'YourDataType' is not defined`

**Solution**: Ensure all model types are exported from `trading_api.models`:

```python
# In trading_api/models/__init__.py
from .market.trades import Trade, TradeSubscriptionRequest

__all__ = [
    # ... existing exports
    "Trade",
    "TradeSubscriptionRequest",
]
```

**Verify exports**:

```bash
cd backend
poetry run python -c "from trading_api.models import Trade; print('OK')"
```

---

### Issue: Generated router has linting errors

**Symptom**: Pre-commit hooks fail on generated files

**Solution**: The wrapper script auto-fixes most issues. If manual fixes are needed:

```bash
cd backend
poetry run ruff check src/trading_api/ws/generated/ --fix
poetry run ruff format src/trading_api/ws/generated/
```

**Prevention**: Run `make generate-ws-routers` instead of calling the Python script directly.

---

### Issue: Frontend types not generated

**Symptom**: TypeScript can't find `TradeSubscriptionRequest` in `@/clients/ws-types-generated`

**Solution**: Regenerate frontend types after backend changes:

```bash
# Start backend first (generates AsyncAPI spec)
cd backend
make dev

# Then regenerate frontend types
cd frontend
make generate-asyncapi-types
```

**Verify AsyncAPI spec exists**:

```bash
curl http://localhost:8000/api/v1/ws/asyncapi.json
```

---

### Issue: Router not registered in app

**Symptom**: WebSocket endpoint returns "No matching type" error

**Solution**: Ensure router is exported in `ws/__init__.py` and registered in `main.py`:

```python
# backend/src/trading_api/ws/trades.py
from .generated.tradewsrouter import TradeWsRouter

trades_ws_routers: list[WsRouterInterface] = [
    TradeWsRouter(
        topic_builder=trades_topic_builder,
        subscribe_request_handler=subscribe_trades_handler,
        unsubscribe_request_handler=unsubscribe_trades_handler,
    ),
]

# backend/src/trading_api/ws/__init__.py
from .datafeed import datafeed_ws_routers
from .trades import trades_ws_routers  # Add this

ws_routers: list[WsRouterInterface] = [
    *datafeed_ws_routers,
    *trades_ws_routers,  # Add this
]
```

**Verify registration**:

```bash
# Check AsyncAPI docs - your operations should be listed
open http://localhost:8000/api/v1/ws/asyncapi
```

---

### Issue: Messages not reaching clients

**Symptom**: Clients subscribe successfully but receive no updates

**Checklist**:

1. **Verify topic matches**: Client subscribes to `trades:AAPL`, broadcaster sends to `trades:AAPL`

```python
# Check topic format
print(f"Broadcasting to: {trades_topic_builder('AAPL', {})}")
```

2. **Verify message type**: Must match operation name

```python
# Correct
await wsApp.publish(topic=topic, data=trade, message_type="trades.update")

# Wrong
await wsApp.publish(topic=topic, data=trade, message_type="trade.update")  # Missing 's'
```

3. **Check client subscription**: Verify in browser DevTools Network tab

4. **Enable debug logging**:

```python
import logging
logging.getLogger("trading_api.ws").setLevel(logging.DEBUG)
```

---

### Issue: Performance degradation with many subscriptions

**Symptom**: Slow response times with 100+ active subscriptions

**Solutions**:

1. **Batch broadcasting**: Send updates in groups

```python
import asyncio

async def broadcast_batch(updates: list[Trade]):
    tasks = [
        wsApp.publish(
            topic=trades_topic_builder(trade.symbol, {}),
            data=trade,
            message_type="trades.update"
        )
        for trade in updates
    ]
    await asyncio.gather(*tasks)
```

2. **Rate limiting**: Limit broadcast frequency per topic

3. **Selective broadcasting**: Check for subscribers before broadcasting

```python
if wsApp.has_subscribers(topic):
    await wsApp.publish(...)
```

---

### Issue: Need to reset all generated routers

**Symptom**: Want to start fresh after major changes

**Solution**:

```bash
cd backend

# Remove all generated files
rm -rf src/trading_api/ws/generated/*.py

# Regenerate everything
make generate-ws-routers

# Verify
make test
```

---

### Getting Help

If you encounter issues not covered here:

1. Check existing routers (e.g., `ws/datafeed.py`) for working examples
2. Verify AsyncAPI spec: http://localhost:8000/api/v1/ws/asyncapi
3. Run with debug logging: `UVICORN_LOG_LEVEL=debug make dev`
4. Review `backend/examples/FASTWS-INTEGRATION.md` for patterns
5. Check backend logs for WebSocket errors
````
