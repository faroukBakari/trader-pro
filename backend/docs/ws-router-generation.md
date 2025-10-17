````markdown
# WebSocket Router Code Generation

## Overview

This project uses code generation for both backend routers and frontend clients to ensure type safety and consistency across the stack.

### Backend: Router Generation

The backend uses a code generation approach to create concrete (non-generic) WebSocket router classes from a generic template. This provides better IDE support, type checking, and eliminates generic type parameters at runtime.

### Frontend: Client Generation

The frontend automatically generates TypeScript types and client factories from the AsyncAPI specification. See `frontend/WS-CLIENT-AUTO-GENERATION.md` for details.

## Backend Architecture

```
backend/src/trading_api/ws/
├── generic.py              # Generic template (source of truth)
├── datafeed.py            # Usage with TYPE_CHECKING guard
└── generated/             # Auto-generated concrete classes
    ├── __init__.py        # Generated exports
    └── barwsrouter.py     # Generated BarWsRouter class
```

## How It Works

### 1. Template (generic.py)

The `generic.py` file contains a generic `WsRouter` class with type parameters:

- `__TRequest`: The subscription request model type
- `__TData`: The data payload type

```python
class WsRouter(OperationRouter, Generic[__TRequest, __TData]):
    # ... implementation
```

### 2. Generator Script (scripts/generate_ws_router.py)

The Python generator performs simple string substitutions:

1. Skips `TypeVar()` declaration lines
2. Replaces `from typing import Generic, TypeVar` with concrete imports
3. Replaces class definition to remove `Generic[__TRequest, __TData]`
4. Substitutes `__TRequest` → concrete request type (e.g., `BarsSubscriptionRequest`)
5. Substitutes `__TData` → concrete data type (e.g., `Bar`)

**Router Specifications:**

```python
ROUTER_SPECS = [
    RouterSpec(
        class_name="BarWsRouter",
        request_type="BarsSubscriptionRequest",
        data_type="Bar",
    ),
]
```

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

## Usage

### Generate Routers

```bash
# From backend directory
make generate-ws-routers
```

### Using Generated Routers

```python
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models import Bar, BarsSubscriptionRequest
from .generic import WsRouter

if TYPE_CHECKING:
    # For type checkers: use generic version
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
else:
    # At runtime: use generated concrete class
    from .generated import BarWsRouter

# Instantiate with parameters
router = BarWsRouter(route="bars", tags=["datafeed"])
bars_topic_builder = router.topic_builder
```

## Adding New Routers

1. **Update specifications** in `scripts/generate_ws_router.py`:

```python
ROUTER_SPECS = [
    RouterSpec(
        class_name="BarWsRouter",
        request_type="BarsSubscriptionRequest",
        data_type="Bar",
    ),
    RouterSpec(
        class_name="QuoteWsRouter",
        request_type="QuotesSubscriptionRequest",
        data_type="Quote",
    ),
]
```

2. **Regenerate**:

```bash
make generate-ws-routers
```

3. **Import and use**:

```python
from .generated import QuoteWsRouter

router = QuoteWsRouter(route="quotes", tags=["datafeed"])
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
    npm run client:generate
```

## Full-Stack Generation Flow

When adding a new WebSocket route:

1. **Define Models** (backend)

   ```python
   # trading_api/models/quotes.py
   class QuoteDataSubscriptionRequest(BaseModel):
       symbols: list[str] = []
       fast_symbols: list[str] = []

   class QuoteData(BaseModel):
       s: str
       n: str
       v: QuoteValues | dict
   ```

2. **Update Router Specs** (backend)

   ```python
   # scripts/generate_ws_router.py
   ROUTER_SPECS = [
       RouterSpec("BarWsRouter", "BarsSubscriptionRequest", "Bar"),
       RouterSpec("QuoteWsRouter", "QuoteDataSubscriptionRequest", "QuoteData"),
   ]
   ```

3. **Generate Backend Router** (backend)

   ```bash
   cd backend && make generate-ws-routers
   ```

4. **Use Generated Router** (backend)

   ```python
   # trading_api/ws/quotes.py
   from .generated import QuoteWsRouter

   router = QuoteWsRouter(route="quotes", tags=["datafeed"])
   ```

5. **Generate Frontend Types** (frontend)

   ```bash
   cd frontend && npm run client:generate
   ```

6. **Use Generated Types** (frontend)

   ```typescript
   // Auto-generated types available!
   import { WebSocketClientBase } from "@/plugins/wsClientBase";
   import type {
     QuoteData,
     QuoteDataSubscriptionRequest,
   } from "@/clients/ws-types-generated";

   const client = new WebSocketClientBase<
     QuoteDataSubscriptionRequest,
     QuoteData
   >("quotes");
   await client.subscribe({ symbols: ["AAPL"] }, (data: QuoteData) => {
     console.log(data);
   });
   ```

**Result**: Fully type-safe WebSocket communication from backend Python → AsyncAPI → Frontend TypeScript!

## Troubleshooting

### Import errors after generation

Run the generation script again - it includes auto-fixing:

```bash
make generate-ws-routers
```

### Type checking fails

Ensure all model types are exported from `trading_api.models`:

```python
# In trading_api/models/__init__.py
from .market.bars import Bar, BarsSubscriptionRequest

__all__ = ["Bar", "BarsSubscriptionRequest", ...]
```

### Linter issues

The wrapper script auto-fixes most issues. If manual fixes are needed:

```bash
cd backend
poetry run ruff check src/trading_api/ws/generated/ --fix
poetry run ruff format src/trading_api/ws/generated/
```
````
