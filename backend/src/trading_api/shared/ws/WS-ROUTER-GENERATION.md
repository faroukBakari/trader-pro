````markdown
# WebSocket Router Code Generation

## Overview

This project uses code generation for both backend routers and frontend clients to ensure type safety and consistency across the stack.

### Backend: Router Generation

The backend uses a code generation approach to create concrete (non-generic) WebSocket router classes from a generic template. This provides better IDE support, type checking, and eliminates generic type parameters at runtime.

**Generation Modes:**

- **Automatic**: Routers generate per-module during app startup (⚠️ requires pre-generation on first run)
- **Manual**: Run `make generate-ws-routers` for specific workflows (CI/CD, debugging, fresh setup)

### Frontend: Client Generation

The frontend automatically generates TypeScript types and client factories from the AsyncAPI specification. See `frontend/WS-CLIENT-AUTO-GENERATION.md` for details.

---

## Automatic Generation (App Startup)

**Status**: ✅ Fully Functional - No Pre-Generation Required

WebSocket routers are automatically generated per module when the app starts. Generation happens in each module's `ws.py` file when the router factory class is instantiated, **before** importing from `ws_generated`.

### How It Works

```python
# modules/datafeed/ws.py - Router factory pattern
class DatafeedWsRouters(list[WsRouteInterface]):
    def __init__(self, datafeed_service: WsRouteService):
        # STEP 1: Generate routers (creates ws_generated/ directory)
        module_name = os.path.basename(os.path.dirname(__file__))
        generated = generate_module_routers(module_name)

        # STEP 2: Import from generated directory (now exists!)
        from .ws_generated import BarWsRouter, QuoteWsRouter

        # STEP 3: Instantiate routers with service
        bar_router = BarWsRouter(route="bars", service=datafeed_service)
        super().__init__([bar_router, ...])
```

**Detection:** Automatically scans for `modules/{module}/ws.py` files
**Output:** Generates to `modules/{module}/ws_generated/`
**Quality:** Runs all formatters and linters (Black, Ruff, Flake8, Mypy, Isort)
**Fail-fast:** Clear module-specific errors if generation fails

### Timeline

```
create_app() execution:
├─ 1. registry.auto_discover()                  ← Discovers modules
├─ 2. registry.set_enabled_modules()
├─ 3. For each enabled module:
│  ├─ 3a. module.get_ws_routers()              ← Instantiates router factory
│  │  ├─ DatafeedWsRouters.__init__()          ← Calls generate_module_routers()
│  │  │  ├─ generate_module_routers()          ← Creates ws_generated/
│  │  │  └─ from .ws_generated import ...      ← Import succeeds!
│  │  └─ Instantiate routers
│  └─ ws_app.include_router()
└─ 4. Start lifespan
```

### Benefits of Automatic Generation

- ✅ **Zero setup**: No pre-generation required, works on fresh clone
- ✅ **Always up-to-date**: Routers regenerate on every app startup
- ✅ **Module-scoped**: Clear errors identify which module failed
- ✅ **Quality assured**: All checks run automatically
- ✅ **Developer-friendly**: Edit TypeAlias → restart app → done---

## Manual Generation (make generate-ws-routers)

**When to use manual generation:**

- First-time setup (before first app run)
- CI/CD workflows (pre-build step)
- Debugging generation issues
- When you want to see generation output

### Command

```bash
cd backend
make generate-ws-routers

# What it does:
# 1. Scans modules/*/ws.py files for TypeAlias patterns
# 2. Auto-discovers all router specifications
# 3. Generates concrete classes in modules/{module}/ws_generated/
# 4. Runs all formatters (Black, isort, Ruff)
# 5. Runs all linters (Flake8, Ruff)
# 6. Runs type checker (mypy)
# 7. Verifies imports work correctly
```

**No manual configuration needed** - just add TypeAlias declarations to your module's `ws.py`!

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

Create a new file (or add to existing modular file) with TypeAlias declaration:

```python
# backend/src/trading_api/modules/trading/ws.py (new module for trading operations)
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models.market import Trade, TradeSubscriptionRequest
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.router_interface import WsRouteInterface

if TYPE_CHECKING:
    # TypeAlias for type checkers - generator will auto-discover this!
    TradeWsRouter: TypeAlias = WsRouter[TradeSubscriptionRequest, Trade]
else:
    # At runtime: use generated concrete class from module-local ws_generated
    from .ws_generated import TradeWsRouter

# Create router instance
trade_router = TradeWsRouter(route="trades", tags=["trading"])
trades_topic_builder = trade_router.topic_builder

# Export routers list (used by module __init__.py)
ws_routers: list[WsRouteInterface] = [trade_router]
```

**Note**: You can group related routes in the same module's `ws.py` file:

- `modules/datafeed/ws.py` - Market data routes (bars, quotes) → exports `ws_routers = [bar_router, quote_router]`
- `modules/trading/ws.py` - Trading routes (trades, orders) → exports `ws_routers = [trade_router, order_router]`
- `modules/account/ws.py` - Account routes (positions, balance) → exports `ws_routers = [position_router, balance_router]`

The generator scans **all** `modules/*/ws.py` files automatically!

**Note**: You can group related routes in the same module's `ws.py` file:

- `modules/datafeed/ws.py` - Market data routes (bars, quotes)
- `modules/trading/ws.py` - Trading routes (trades, orders)
- `modules/account/ws.py` - Account routes (positions, balance)

The generator scans **all** `modules/*/ws.py` files automatically!

### Step 4: Start the App (Automatic Generation)

**No manual generation needed!** Just start the app:

```bash
cd backend
make dev
```

**What happens automatically:**

1. App starts and discovers modules
2. When `DatafeedWsRouters` class is instantiated:
   - Calls `generate_module_routers("datafeed")`
   - Creates `modules/datafeed/ws_generated/` directory
   - Generates `BarWsRouter` and `QuoteWsRouter` concrete classes
   - Runs all quality checks (Black, Ruff, Flake8, Mypy, Isort)
   - Imports generated classes
3. Router factory instantiates routers with service
4. App includes routers in WebSocket application

**Optional**: You can also pre-generate manually for debugging:

```bash
cd backend
make generate-ws-routers  # Manual generation (optional)
```

### Step 5: Export Routers via Module Protocol

Modules expose routers via the `Module Protocol`'s `get_ws_routers()` method:

```python
# backend/src/trading_api/modules/trading/__init__.py
from typing import List
from trading_api.shared.ws.router_interface import WsRouteInterface
from .ws import ws_routers  # Import module's router list

class TradingModule:
    def __init__(self):
        self._service = None
        self._enabled = True

    # ... other Module Protocol methods ...

    def get_ws_routers(self) -> List[WsRouteInterface]:
        """Return all WebSocket routers for this module"""
        # Pass service instance to router factory
        from .ws import TradeWsRouter
        return [TradeWsRouter(route="trades", tags=["trading"], service=self.service)]
```

**Pattern**: Each module's `__init__.py` implements `get_ws_routers()` to provide routers with injected service.

### Step 6: Module Registration (Automatic)

**Note**: In the modular architecture, routers are registered automatically via the Module Protocol.

The application factory (`app_factory.py`) handles registration:

```python
# backend/src/trading_api/app_factory.py (excerpt)
from trading_api.shared.module_registry import registry
from trading_api.modules.trading import TradingModule  # Import new module

def create_app(enabled_modules: list[str] | None = None):
    # Register all modules
    registry.register(DatafeedModule())
    registry.register(BrokerModule())
    registry.register(TradingModule())  # 👈 Register new module

    # ... filter enabled modules if specified ...

    # Include all enabled modules' WebSocket routers
    for module in registry.get_enabled_modules():
        for ws_router in module.get_ws_routers():
            ws_app.include_router(ws_router)

    return api_app, ws_app
```

**Benefits**:

- ✅ Automatic router registration for all enabled modules
- ✅ Service injection handled by module (lazy-loaded)
- ✅ Clean separation: modules manage their own routers
- ✅ Type-safe: `get_ws_routers()` returns `list[WsRouteInterface]`

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
# Service implementation (e.g., market data service)
from trading_api.ws.router_interface import WsRouteService

class MarketDataService(WsRouteService):
    def __init__(self):
        self._topic_generators: dict[str, asyncio.Task] = {}

    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start data generation for topic"""
        if topic not in self._topic_generators:
            self._topic_generators[topic] = asyncio.create_task(
                self._trade_generator(topic, topic_update)
            )

    def remove_topic(self, topic: str) -> None:
        """Stop data generation for topic"""
        task = self._topic_generators.get(topic)
        if task:
            task.cancel()
        self._topic_generators.pop(topic, None)

    async def _trade_generator(self, topic: str, topic_update: Callable) -> None:
        """Generate trades and call topic_update callback"""
        while True:
            trade = await self.get_next_trade()
            # Call callback to enqueue update
            topic_update(trade)
            await asyncio.sleep(0.1)
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
backend/src/trading_api/
├── shared/
│   ├── ws/
│   │   ├── __init__.py
│   │   ├── generic_route.py       # Generic template (pre-defined operations)
│   │   ├── router_interface.py    # Base interface and topic builder logic
│   │   └── WS-ROUTER-GENERATION.md # This file
│   └── ...
├── modules/
│   ├── datafeed/              # Market data module
│   │   ├── __init__.py            # DatafeedModule (Module Protocol)
│   │   ├── ws.py                  # Market data routers (bars, quotes)
│   │   └── ws_generated/          # Auto-generated concrete classes
│   │       ├── __init__.py        # Generated exports (auto-updated)
│   │       ├── barwsrouter.py     # Generated from datafeed/ws.py
│   │       └── quotewsrouter.py   # Generated from datafeed/ws.py
│   ├── broker/                # Trading module
│   │   ├── __init__.py            # BrokerModule (Module Protocol)
│   │   ├── ws.py                  # Trading routers (orders, positions, etc.)
│   │   └── ws_generated/          # Auto-generated concrete classes
│   │       ├── __init__.py
│   │       ├── orderwsrouter.py
│   │       ├── positionwsrouter.py
│   │       └── ...
│   └── trading/               # Additional module (when you add it)
│       ├── __init__.py            # TradingModule (Module Protocol)
│       ├── ws.py                  # Trading routers (trades, orders)
│       └── ws_generated/          # Auto-generated concrete classes
│           ├── __init__.py
│           └── tradewsrouter.py   # Generated from trading/ws.py
├── app_factory.py             # Application factory (registers modules)
└── main.py                    # Minimal entrypoint
```

**File Organization Pattern:**

- Each module (`modules/{module}/`) has its own `ws.py` with TypeAlias declarations
- Generator scans all `modules/*/ws.py` files automatically
- Routers generated into module-specific `ws_generated/` directories
- Modules expose routers via `get_ws_routers()` method (Module Protocol)
- Application factory automatically registers all enabled modules' routers
- `shared/ws/` contains infrastructure (generic template, router interface)

**File Organization Pattern:**

- Group related routes by module in separate directories
- Each module's `ws.py` can contain multiple TypeAlias declarations
- Generator automatically finds all TypeAlias declarations across all modules
- `ws_generated/` directories are auto-managed (cleared and regenerated each time)

## How It Works

### 1. Template (generic_route.py) - Pre-Defined Operations

The `generic_route.py` file contains a generic `WsRouter` class with:

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

Developers declare routers using `TypeAlias` with `TYPE_CHECKING` guard in their module's `ws.py`:

```python
# backend/src/trading_api/modules/datafeed/ws.py
if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
else:
    from .ws_generated import BarWsRouter, QuoteWsRouter
```

### 3. Module Router Generator (shared/ws/module_router_generator.py)

The module-scoped generator **automatically scans** `modules/*/ws.py` files for TypeAlias patterns:

1. **Scans** all `modules/*/ws.py` files (not `shared/ws/` - that's infrastructure)
2. **Finds** regex pattern: `BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]`
3. **Extracts** class name, request type, and data type
4. **Generates** concrete class by:
   - Removing `Generic[__TRequest, __TData]`
   - Replacing `__TRequest` → `BarsSubscriptionRequest`
   - Replacing `__TData` → `Bar`
   - Keeping all pre-defined operations from template
5. **Outputs** to `modules/{module}/ws_generated/barwsrouter.py`
6. **Runs quality checks** - Black, Ruff, Flake8, Mypy, Isort

**No manual configuration needed!** Just write the TypeAlias in your module's `ws.py` and:

- **Automatic**: Routers generate during app startup (per module)
- **Manual**: Run `make generate-ws-routers` for specific needs

### 3. Automatic Generation During App Startup

Generation happens automatically per module when the app starts:

1. **Module loading** - App factory loads each enabled module
2. **Detection** - Checks if `modules/{module}/ws.py` exists
3. **Generation** - Calls `generate_module_routers(module_name)`
4. **Quality checks** - Runs all formatters and linters
5. **Fail-fast** - Clear module-specific errors if generation fails
6. **Import verification** - Module imports from `ws_generated/`

This ensures generated code passes **all** pre-commit hook checks and is always up-to-date.

See `backend/SYSTEMATIC_WS_ROUTER_GEN.md` for complete implementation details.

## Usage Patterns

### Pattern 1: TYPE_CHECKING Guard (Recommended)

This pattern provides the best of both worlds: type checking during development and concrete classes at runtime.

```python
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models import Bar, BarsSubscriptionRequest
from trading_api.shared.ws.generic_route import WsRouter

if TYPE_CHECKING:
    # For type checkers (mypy, IDE): use generic version
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
else:
    # At runtime: use generated concrete class (from module-local ws_generated)
    from .ws_generated import BarWsRouter

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
from .ws_generated import BarWsRouter

router = BarWsRouter(route="bars", tags=["datafeed"])
bars_topic_builder = router.topic_builder
```

**When to use:**

- ✅ Simple route definitions
- ✅ When type inference is sufficient
- ✅ No complex type manipulation needed

## Pre-Defined Operations (From generic_route.py)

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
- Used to identify router in WsRouter factory registration

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
# 1. Scans modules/*/ws.py files for TypeAlias patterns
# 2. Auto-discovers all router specifications across all modules
# 3. Generates concrete classes in modules/{module}/ws_generated/
# 4. Runs all formatters (Black, isort, Ruff)
# 5. Runs all linters (Flake8, Ruff)
# 6. Runs type checker (mypy)
# 7. Verifies imports work correctly
```

**No manual configuration needed** - just add TypeAlias declarations to your module's `ws.py`!

### Verify Generation

```bash
# Check generated files (module-specific)
ls -la backend/src/trading_api/modules/datafeed/ws_generated/
ls -la backend/src/trading_api/modules/broker/ws_generated/

# Test imports
cd backend
poetry run python -c "from trading_api.modules.datafeed.ws_generated import BarWsRouter; print('OK')"

# Run tests
make test
```

### Clean Generated Files

```bash
# Remove all generated routers (will be regenerated on next make generate-ws-routers)
rm -rf backend/src/trading_api/modules/*/ws_generated/*.py

# Or clean specific module
rm -rf backend/src/trading_api/modules/datafeed/ws_generated/*.py
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

- Single source of truth (generic_route.py)
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
# In your module's service implementation
# Example: backend/src/trading_api/modules/datafeed/service.py
from trading_api.shared.ws.router_interface import WsRouteService
from typing import Callable

class MarketDataService(WsRouteService):
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start generating trade data for topic"""
        # Parse topic to get symbol
        # topic format: "trades:{\"symbol\":\"AAPL\"}"
        self._topic_generators[topic] = asyncio.create_task(
            self._trade_generator(topic, topic_update)
        )

    async def _trade_generator(self, topic: str, topic_update: Callable) -> None:
        """Called when new trade arrives - broadcasts via callback"""
        while True:
            trade = await self.get_next_trade()
            # Call callback to enqueue update to router's updates_queue
            topic_update(trade)
            await asyncio.sleep(0.1)
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
2. Add TypeAlias declaration in modules/{module}/ws.py (backend)
   ↓
3. Generate router: make generate-ws-routers (backend)
   → Auto-discovers TypeAlias
   → Generates concrete class with pre-defined operations
   → Outputs to modules/{module}/ws_generated/
   ↓
4. Module implements get_ws_routers() method (Module Protocol)
   ↓
5. Register module in app_factory.py (registry.register(YourModule()))
   ↓
6. Start backend (generates AsyncAPI spec)
   ↓
7. Frontend auto-generates TypeScript types
   ↓
8. Use type-safe WebSocket client in frontend
```

**Key Difference**: No manual operation implementation or router registration needed - Module Protocol handles it!

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

### Issue: Import errors on app startup

**Symptom**: `ImportError: cannot import name 'YourWsRouter' from 'trading_api.modules.{module}.ws_generated'`

**Possible Causes:**

1. **Generation failed silently**: Check app startup logs for generation errors
2. **Invalid TypeAlias syntax**: Verify TypeAlias declaration in `ws.py`
3. **Quality checks failed**: Review error output for linting/formatting issues

**Solution**: Check logs and fix any errors reported during generation:

```bash
cd backend
# View detailed generation output
make dev

# Or manually generate to see errors
make generate-ws-routers
```

---

### Issue: Import errors after changing models

**Symptom**: Type errors or import errors after updating Pydantic models

**Solution**: Routers auto-regenerate on next `make dev`. If using a running dev server, restart it:

```bash
cd backend
make kill-dev  # Stop current server
make dev       # Restart (triggers regeneration)
```

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

trades_ws_routers: list[WsRouteInterface] = [
    TradeWsRouter(
        topic_builder=trades_topic_builder,
        subscribe_request_handler=subscribe_trades_handler,
        unsubscribe_request_handler=unsubscribe_trades_handler,
    ),
]

# backend/src/trading_api/ws/__init__.py
from .datafeed import datafeed_ws_routers
from .trades import trades_ws_routers  # Add this

ws_routers: list[WsRouteInterface] = [
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

2. **Verify message type**: Must match router route name in update message

```python
# Router updates_queue receives SubscriptionUpdate with topic
# FastWSAdapter broadcasts as: Message(type=f"{router.route}.update", ...)
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

1. **Batch updates in generator**: Produce updates efficiently

```python
import asyncio

class MarketDataService(WsRouteService):
    async def _trade_generator(self, topic: str, topic_update: Callable) -> None:
        """Batch process trades for efficiency"""
        batch: list[Trade] = []

        while True:
            trade = await self.get_next_trade()
            batch.append(trade)

            # Flush batch every 100ms or when full
            if len(batch) >= 10:
                for t in batch:
                    topic_update(t)
                batch.clear()

            await asyncio.sleep(0.01)
```

2. **Rate limiting**: Limit update frequency per topic in generator

3. **Reference counting**: WsRouter automatically manages topic lifecycle
   - First subscriber: calls `service.create_topic()` → starts generator
   - Last unsubscribe: calls `service.remove_topic()` → stops generator
   - No subscribers = no CPU/memory usage for that topic

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
