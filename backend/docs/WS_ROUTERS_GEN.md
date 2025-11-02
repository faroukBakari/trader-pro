# WebSocket Router Generation Guide

**Version**: 1.0.0  
**Date**: November 2, 2025  
**Status**: ✅ Current Implementation Reference

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Module Compliance Checklist](#module-compliance-checklist)
4. [TypeAlias Declaration Patterns](#typealias-declaration-patterns)
5. [Common Issues & Solutions](#common-issues--solutions)
6. [Generation Flow Deep Dive](#generation-flow-deep-dive)
7. [Quality Checks](#quality-checks)
8. [Related Documentation](#related-documentation)

---

## Overview

### What is WS Router Generation?

WebSocket routers in this codebase are **automatically generated** from TypeAlias declarations. Instead of writing repetitive boilerplate for each WebSocket endpoint, you:

1. Declare a `TypeAlias` mapping request/data types to `WsRouter`
2. The system generates the concrete router class at module initialization
3. Import and use the generated router in your module

### Key Benefits

- ✅ **Type-safe**: Compile-time type checking with TypeAlias
- ✅ **DRY**: No repetitive router boilerplate
- ✅ **Automatic**: Generation happens during module initialization
- ✅ **Validated**: Quality checks ensure generated code passes all linters/formatters
- ✅ **Module-scoped**: Each module owns its generated routers (`ws_generated/`)

### Architecture Context

```
modules/{module}/
├── ws.py                    # TypeAlias declarations + WsRouters class
├── ws_generated/            # Auto-generated (created at module init)
│   ├── __init__.py          # Exports all routers
│   ├── barwsrouter.py       # Generated router classes
│   └── quotewsrouter.py
└── service.py               # Implements WsRouteService protocol
```

**Generator Location**: `shared/ws/module_router_generator.py`  
**Template**: `shared/ws/generic_route.py`

---

## How It Works

### Step 1: Developer Writes TypeAlias

In your module's `ws.py` file:

```python
# modules/datafeed/ws.py
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter

if TYPE_CHECKING:
    # TypeAlias for code generation
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteSubscriptionRequest, Quote]
```

**Key Pattern**:

- Use `if TYPE_CHECKING:` block for TypeAlias declarations
- Pattern: `RouterName: TypeAlias = WsRouter[RequestType, DataType]`
- Both single-line and multi-line declarations supported

### Step 2: Automatic Generation at Module Init

When your `WsRouters` class is instantiated:

```python
class DatafeedWsRouters(list[WsRouteInterface]):
    def __init__(self, datafeed_service: WsRouteService):
        # 1. Detect module name automatically
        module_name = os.path.basename(os.path.dirname(__file__))

        # 2. Generate routers (creates ws_generated/ directory)
        try:
            generated = generate_module_routers(module_name)
            if generated:
                logger.info(f"Generated WS routers for module '{module_name}'")
        except RuntimeError as e:
            logger.error(f"WebSocket router generation failed for module '{module_name}'!")
            raise

        # 3. Import generated routers
        if not TYPE_CHECKING:
            from .ws_generated import BarWsRouter, QuoteWsRouter

        # 4. Instantiate and register
        bar_router = BarWsRouter(route="bars", service=datafeed_service)
        super().__init__([bar_router, ...])
```

**Critical**: Generation happens BEFORE the import statement, ensuring files exist when needed.

### Step 3: Generated Output

The generator creates:

```python
# modules/datafeed/ws_generated/barwsrouter.py
from trading_api.models import BarsSubscriptionRequest, Bar
from typing import Any
from trading_api.shared.ws.router_interface import WsRouteInterface, WsRouteService

class BarWsRouter(WsRouteInterface):
    def __init__(
        self,
        *,
        route: str,
        service: WsRouteService,
        tags: list[str] | None = None,
    ):
        self._route = route
        self._service = service
        self._tags = tags or []
        # ... full implementation
```

---

## Module Compliance Checklist

When creating a new module with WebSocket support:

### ✅ Required Files

- [ ] `modules/{module}/ws.py` - Contains TypeAlias declarations
- [ ] `modules/{module}/service.py` - Implements `WsRouteService` protocol
- [ ] Service has `broadcast()` method for push notifications

### ✅ TypeAlias Declaration Format

```python
if TYPE_CHECKING:
    # ✅ CORRECT: Single-line
    RouterName: TypeAlias = WsRouter[RequestType, DataType]

    # ✅ CORRECT: Multi-line
    RouterName: TypeAlias = WsRouter[
        RequestType,
        DataType
    ]

    # ❌ WRONG: Missing TypeAlias
    RouterName = WsRouter[RequestType, DataType]

    # ❌ WRONG: Not in TYPE_CHECKING block
    RouterName: TypeAlias = WsRouter[RequestType, DataType]
```

### ✅ WsRouters Class Pattern

```python
from trading_api.shared.ws.module_router_generator import generate_module_routers

class ModuleWsRouters(list[WsRouteInterface]):
    def __init__(self, module_service: WsRouteService):
        # 1. Generate routers
        module_name = os.path.basename(os.path.dirname(__file__))
        generated = generate_module_routers(module_name)

        # 2. Import (after generation!)
        if not TYPE_CHECKING:
            from .ws_generated import RouterName

        # 3. Instantiate
        router = RouterName(route="endpoint", service=module_service)
        super().__init__([router])
```

### ✅ Service Protocol Compliance

Your service MUST implement:

```python
class WsRouteService(Protocol):
    """Service protocol for WebSocket routers."""

    async def broadcast(
        self,
        message: Any,
        route: str | None = None,
    ) -> None:
        """Broadcast message to subscribed clients."""
        ...
```

---

## TypeAlias Declaration Patterns

### Pattern 1: Simple Router

```python
if TYPE_CHECKING:
    OrderWsRouter: TypeAlias = WsRouter[OrderSubscriptionRequest, PlacedOrder]
```

**Generated File**: `orderwsrouter.py`  
**Generated Class**: `OrderWsRouter`

### Pattern 2: Multi-line for Readability

```python
if TYPE_CHECKING:
    BrokerConnectionWsRouter: TypeAlias = WsRouter[
        BrokerConnectionSubscriptionRequest,
        BrokerConnectionStatus
    ]
```

**Generated File**: `brokerconnectionwsrouter.py`  
**Generated Class**: `BrokerConnectionWsRouter`

### Pattern 3: Multiple Routers in One Module

```python
if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteSubscriptionRequest, Quote]
    TradeWsRouter: TypeAlias = WsRouter[TradeSubscriptionRequest, Trade]
```

All routers generated in the same `ws_generated/` directory.

### Naming Conventions

- **Router Class Name**: `{Purpose}WsRouter` (e.g., `OrderWsRouter`, `BarWsRouter`)
- **Generated File**: Lowercase class name (e.g., `orderwsrouter.py`)
- **Route Name**: Lowercase, hyphenated (e.g., `"orders"`, `"broker-connection"`)

---

## Common Issues & Solutions

### Issue 1: ModuleNotFoundError on Import

**Symptom**:

```python
ModuleNotFoundError: No module named 'trading_api.modules.datafeed.ws_generated'
```

**Cause**: Generation failed or wasn't triggered before import

**Solutions**:

1. Check TypeAlias declarations are inside `if TYPE_CHECKING:` block
2. Verify `generate_module_routers()` is called BEFORE the import
3. Check logs for generation errors
4. Ensure `ws.py` exists in the module directory

**Debug**:

```bash
# Check if ws_generated exists
ls -la backend/src/trading_api/modules/datafeed/ws_generated/

# Manually trigger generation
cd backend
poetry run python -c "from trading_api.shared.ws.module_router_generator import generate_module_routers; generate_module_routers('datafeed', silent=False)"
```

### Issue 2: AttributeError on Router Class

**Symptom**:

```python
AttributeError: module 'trading_api.modules.datafeed.ws_generated' has no attribute 'BarWsRouter'
```

**Cause**:

- TypeAlias name doesn't match import
- Generation created different class name
- Old cached files

**Solutions**:

1. Verify TypeAlias name matches import: `BarWsRouter: TypeAlias = ...`
2. Clear Python cache: `find . -name "__pycache__" -type d -exec rm -rf {} +`
3. Re-run generation: `make generate modules=datafeed`

### Issue 3: Generation Fails with RuntimeError

**Symptom**:

```
RuntimeError: Black formatting failed for module 'datafeed'!
```

**Cause**: Generated code doesn't pass quality checks

**Solutions**:

1. Check TypeAlias uses valid types (must be importable from `trading_api.models`)
2. Verify request/data types are correctly formatted
3. Review the error output for specific linting issues

**Debug**:

```bash
# Run generation with verbose output
poetry run python -c "
from trading_api.shared.ws.module_router_generator import generate_module_routers
generate_module_routers('datafeed', silent=False, skip_quality_checks=True)
"

# Then manually check generated files
poetry run black src/trading_api/modules/datafeed/ws_generated/
poetry run mypy src/trading_api/modules/datafeed/ws_generated/
```

### Issue 4: Service Protocol Violations

**Symptom**:

```python
TypeError: Can't instantiate abstract class with abstract methods broadcast
```

**Cause**: Service doesn't implement `WsRouteService` protocol

**Solution**: Implement the required `broadcast()` method:

```python
class DatafeedService:
    async def broadcast(
        self,
        message: Any,
        route: str | None = None,
    ) -> None:
        """Broadcast message to WebSocket clients."""
        if self._ws_adapter:
            await self._ws_adapter.broadcast(message, route=route)
```

### Issue 5: Stale Generated Files

**Symptom**: Changes to TypeAlias don't reflect in generated routers

**Cause**: Old generated files cached

**Solutions**:

1. Delete `ws_generated/` directory: `rm -rf modules/{module}/ws_generated/`
2. Clear Python cache: `find . -name "__pycache__" -type d -exec rm -rf {} +`
3. Re-run generation: Module initialization will regenerate

**Prevention**: Generator automatically cleans old files on regeneration.

---

## Generation Flow Deep Dive

### Automatic Generation (During Module Init)

```
Module Initialization
├─ 1. DatafeedWsRouters.__init__() called
│  ├─ 2. Detect module name from __file__
│  ├─ 3. Call generate_module_routers('datafeed')
│  │  ├─ 4. Check if ws.py exists
│  │  ├─ 5. Parse TypeAlias declarations (regex)
│  │  ├─ 6. Load template (generic_route.py)
│  │  ├─ 7. Generate concrete classes
│  │  ├─ 8. Generate __init__.py
│  │  ├─ 9. Run quality checks (Black, Ruff, Mypy, etc.)
│  │  └─ 10. Verify imports work
│  └─ 11. Import from ws_generated
└─ 12. Instantiate routers with service
```

### Manual Generation (Optional)

For debugging or pre-generation:

```bash
# Generate for specific module
cd backend
poetry run python -c "
from trading_api.shared.ws.module_router_generator import generate_module_routers
generate_module_routers('datafeed', silent=False)
"

# Or use Makefile (deprecated, but still works)
make generate modules=datafeed
```

### Generator Implementation Details

**File**: `shared/ws/module_router_generator.py`

**Key Functions**:

1. `parse_router_specs_from_file()`: Regex-based TypeAlias extraction

   - Pattern: `(\w+): TypeAlias = WsRouter\[(\w+), (\w+)\]`
   - Supports multi-line declarations
   - Returns `RouterSpec` named tuples

2. `generate_router_code()`: Template substitution

   - Replaces `_TRequest` with actual request type
   - Replaces `_TData` with actual data type
   - Removes generic type parameters
   - Adds model imports

3. `generate_init_file()`: Creates `__init__.py`

   - Imports all generated routers
   - Exports via `__all__`

4. `run_quality_checks_for_module()`: 7-step validation

   - Black → Ruff format → Ruff fix → Flake8 → Ruff check → Mypy → Isort

5. `verify_router_imports()`: Lightweight verification
   - Checks routers can be imported
   - Does NOT instantiate (avoids circular deps)

---

## Quality Checks

Generated code passes through 7 quality checks:

### 1. Black - Code Formatting

```bash
poetry run black src/trading_api/modules/{module}/ws_generated/
```

### 2. Ruff Format - Additional Formatting

```bash
poetry run ruff format src/trading_api/modules/{module}/ws_generated/
```

### 3. Ruff Auto-fix - Linting with Fixes

```bash
poetry run ruff check src/trading_api/modules/{module}/ws_generated/ --fix
```

### 4. Flake8 - Style Guide Enforcement

```bash
poetry run flake8 src/trading_api/modules/{module}/ws_generated/
```

### 5. Ruff Check - Linting Validation

```bash
poetry run ruff check src/trading_api/modules/{module}/ws_generated/
```

### 6. Mypy - Type Checking

```bash
poetry run mypy src/trading_api/modules/{module}/ws_generated/
```

### 7. Isort - Import Sorting

```bash
poetry run isort src/trading_api/modules/{module}/ws_generated/
```

**All checks must pass** for generation to succeed. If any check fails, the generator:

1. Outputs detailed error message with command and output
2. Deletes the `ws_generated/` directory (clean failure)
3. Raises `RuntimeError` with module context

---

## Related Documentation

### Core Documentation

- `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md` - Module system architecture
- `shared/ws/router_interface.py` - `WsRouteInterface` and `WsRouteService` protocols
- `shared/ws/generic_route.py` - Template for generated routers
- `shared/module_interface.py` - Module Protocol definition

### Implementation Examples

- `modules/datafeed/ws.py` - Datafeed WebSocket routers (2 routers)
- `modules/broker/ws.py` - Broker WebSocket routers (5 routers)
- `modules/datafeed/service.py` - Service implementing WsRouteService
- `modules/broker/service.py` - Service implementing WsRouteService

### Historical Context

- `backend/docs/outdated/SYSTEMATIC_WS_ROUTER_GEN.md` - Complete migration history
- `backend/docs/outdated/MODULE_SCOPED_WS_APP.md` - Module-scoped design evolution
- `backend/docs/outdated/MODULAR_BACKEND_IMPL.md` - Full modular migration plan

### Related Methodologies

- `WEBSOCKET-METHODOLOGY.md` - WebSocket implementation methodology
- `API-METHODOLOGY.md` - REST API design patterns
- `ARCHITECTURE.md` - Overall system architecture

---

## Quick Reference Card

### Creating a New WebSocket Router

1. **Add TypeAlias in `ws.py`**:

   ```python
   if TYPE_CHECKING:
       MyRouter: TypeAlias = WsRouter[MyRequest, MyData]
   ```

2. **Ensure models exist**:

   ```python
   # In models/
   class MyRequest(BaseModel): ...
   class MyData(BaseModel): ...
   ```

3. **Import in WsRouters class**:

   ```python
   if not TYPE_CHECKING:
       from .ws_generated import MyRouter
   ```

4. **Instantiate**:

   ```python
   router = MyRouter(route="my-route", service=service)
   ```

5. **Test**: Module initialization will auto-generate

### Troubleshooting Commands

```bash
# Check if ws_generated exists
ls -la src/trading_api/modules/{module}/ws_generated/

# Manual generation (debug)
poetry run python -c "from trading_api.shared.ws.module_router_generator import generate_module_routers; generate_module_routers('{module}', silent=False)"

# Clear all caches
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "ws_generated" -type d -exec rm -rf {} +

# Verify service protocol
poetry run mypy modules/{module}/service.py

# Check generated code quality
poetry run black modules/{module}/ws_generated/
poetry run mypy modules/{module}/ws_generated/
```

---

**Last Updated**: November 2, 2025  
**Maintainer**: Backend Team  
**Status**: ✅ Production-ready, actively used
