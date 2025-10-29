# Modular Backend Implementation Plan

**Status**: In Progress - Phase 3 | **Created**: 2025-10-28 | **Updated**: 2025-10-29

## 🚀 Implementation Progress

> **⚠️ CRITICAL**: Update this section at the end of EVERY individual task completion.
>
> - Move completed task from "In Progress" to "Completed" with date and commit hash
> - Update task counters (X/20 tasks)
> - Move next task to "In Progress"
> - Commit the updated MODULAR_BACKEND_IMPL.md with task changes

### ✅ Completed (15/21 tasks)

1. **Pre-Migration Validation** ✅ - Completed 2025-10-29

   - All 48 baseline tests passing
   - Coverage baseline captured: 74%
   - OpenAPI/AsyncAPI spec export verified
   - Frontend client generation verified
   - Baseline tag created: `pre-modular-baseline`
   - Current state: 43 Python files, 5 test files

2. **Phase 0: Create Fixtures** ✅ - Completed 2025-10-29

   - Created `backend/tests/conftest.py` with parallel fixtures
   - Fixtures: `app`, `client`, `async_client`, `datafeed_only_app`, `broker_only_app`
   - All 48 tests still pass with conftest.py
   - Committed: 6c16a67

3. **Phase 0: Update Test Files** ✅ - Completed 2025-10-29

   - Updated `test_api_health.py` to use `async_client` fixture
   - Updated `test_api_versioning.py` to use `async_client` fixture
   - Updated `test_api_broker.py` to use `async_client` fixture
   - Updated `test_ws_broker.py` to use `client` fixture
   - Updated `test_ws_datafeed.py` to use `client` fixture
   - All 48 tests pass with fixtures (48 passed in 0.37s)
   - All test files now decoupled from main.py globals
   - Committed: 49c5eb5

4. **Phase 1: Create Module Protocol** ✅ - Completed 2025-10-29

   - Created `shared/module_interface.py` with Module Protocol
   - Defined properties: `name`, `enabled`, `_enabled`
   - Defined methods: `get_api_routers()`, `get_ws_routers()`, `configure_app()`
   - All 48 tests pass (48 passed in 0.28s)
   - Type checking passes (mypy: no issues found in 50 source files)

5. **Phase 1: Create Module Registry** ✅ - Completed 2025-10-29

   - Created `shared/module_registry.py` with ModuleRegistry class
   - Methods: `register()`, `get_enabled_modules()`, `get_all_modules()`, `get_module()`, `clear()`
   - All 48 tests pass (48 passed in 0.28s)
   - Type checking passes (mypy: no issues found in 50 source files)

6. **Phase 1: Create Application Factory** ✅ - Completed 2025-10-29

   - Created `app_factory.py` with `create_app()` function
   - Supports `enabled_modules` parameter for selective loading
   - Includes lifespan management, spec generation, CORS middleware
   - All 48 tests pass (48 passed in 0.28s)
   - Type checking passes (mypy: no issues found in 50 source files)

7. **Phase 1: Create Modules Directory** ✅ - Completed 2025-10-29

   - Created `modules/__init__.py`
   - Created `modules/datafeed/__init__.py`
   - Created `modules/broker/__init__.py`
   - All placeholders ready for Phase 2 implementations
   - All 48 tests pass (48 passed in 0.28s)
   - Type checking passes (mypy: no issues found in 50 source files)

8. **Phase 1: Validate Infrastructure** ✅ - Completed 2025-10-29

   - All 48 tests pass (48 passed in 0.28s)
   - Type checking passes (mypy: no issues found in 50 source files)
   - Linting passes (black, isort, flake8 all green)
   - No regressions introduced
   - Committed: bef3726

9. **Phase 2: Create DatafeedModule** ✅ - Completed 2025-10-29

   - Created `modules/datafeed/__init__.py` with DatafeedModule class
   - Implements Module Protocol with lazy-loaded service
   - Methods: `get_api_routers()`, `get_ws_routers()`, `configure_app()`
   - All 48 tests pass (48 passed in 0.31s)
   - Type checking passes (mypy: no issues found in 50 source files)
   - Committed: d60aebd

10. **Phase 2: Create BrokerModule** ✅ - Completed 2025-10-29

    - Created `modules/broker/__init__.py` with BrokerModule class
    - Implements Module Protocol with lazy-loaded service
    - Methods: `get_api_routers()`, `get_ws_routers()`, `configure_app()`
    - All 48 tests pass (48 passed in 0.30s)
    - Type checking passes (mypy: no issues found in 50 source files)
    - Committed: d60aebd

11. **Phase 3: Move Plugins to shared/plugins/** ✅ - Completed 2025-10-29

    - Moved `plugins/fastws_adapter.py` → `shared/plugins/fastws_adapter.py`
    - Created backward compatibility re-export in `plugins/__init__.py`
    - Added deprecation notice for old import path
    - All existing imports continue to work
    - No test changes required
    - Committed: 112cf77

12. **Phase 3: Refactor WS Router Generation** ✅ - Completed 2025-10-29

    - Updated `ws/generic_route.py` to import from `shared/ws/router_interface`
    - Updated `scripts/generate_ws_router.py` to support both legacy and modular architectures
    - Added `find_module_ws_files()` to scan `modules/*/ws.py` files
    - Added `generate_for_module()` to generate into `modules/{module}/ws_generated/`
    - Updated `scripts/generate-ws-routers.sh` to format all generated directories (legacy + modular)
    - Updated `scripts/verify_ws_routers.py` to verify both architectures
    - Fallback to legacy `ws/generated/` when no module ws.py files found
    - All 48 tests pass (48 passed in 0.37s)
    - Generation tested and working in legacy mode
    - Committed: 112cf77

13. **Phase 3: Move API Infrastructure to shared/api/** ✅ - Completed 2025-10-29

    - Created `shared/api/__init__.py` directory structure
    - Moved `api/health.py` → `shared/api/health.py`
    - Moved `api/versions.py` → `shared/api/versions.py`
    - Updated `api/__init__.py` with backward compatibility re-exports and deprecation notice
    - Updated `shared/__init__.py` to export `HealthApi` and `VersionApi`
    - Updated `app_factory.py` to import and include shared API routers
    - Deleted old `api/health.py` and `api/versions.py` files
    - All 48 tests pass (48 passed in 0.30s)
    - Type checking passes (mypy: no issues found in 56 source files)
    - Linting passes (black, isort, flake8 all green)
    - Committed: 112cf77

14. **Phase 3: Move Datafeed Module Files** ✅ - Completed 2025-10-29

    - Moved `core/datafeed_service.py` → `modules/datafeed/service.py`
    - Moved `api/datafeed.py` → `modules/datafeed/api.py`
    - Moved `ws/datafeed.py` → `modules/datafeed/ws.py`
    - Updated imports to use `trading_api.shared.ws.router_interface`
    - Updated `modules/datafeed/__init__.py` to import from local files
    - Added backward compatibility re-exports in `core/__init__.py`, `api/__init__.py`, `ws/__init__.py`
    - Generated WebSocket routers into `modules/datafeed/ws_generated/` (2 routers)
    - All 48 tests pass (48 passed in 0.32s)
    - Type checking passes (mypy: no issues found in 59 source files)
    - Linting passes (black, isort, flake8 all green)
    - Committed: f8bbf4f

15. **Phase 3: Move Broker Module Files** ✅ - Completed 2025-10-29
    - Moved `core/broker_service.py` → `modules/broker/service.py`
    - Moved `api/broker.py` → `modules/broker/api.py`
    - Moved `ws/broker.py` → `modules/broker/ws.py`
    - Updated imports to use `trading_api.shared.ws.router_interface`
    - Updated `modules/broker/__init__.py` to import from local files
    - Updated backward compatibility re-exports in `core/__init__.py`, `api/__init__.py`, `ws/__init__.py`
    - Generated WebSocket routers into `modules/broker/ws_generated/` (5 routers)
    - Deleted old broker files from `core/`, `api/`, `ws/`
    - All 48 tests pass (48 passed in 0.32s)
    - Type checking passes (mypy: no issues found in 65 source files)
    - Linting passes (black, isort, flake8 all green)
    - Committed: f8bbf4f

### 🔄 In Progress (0/20 tasks)

**Phase 3: Move Shared and Module Infrastructure** - Complete

**Next Steps:**

- Start Task 16: Clean up legacy source files and folders

### 📋 Pending (6/21 tasks)

**Phase 0 (Complete):**

✅ All Phase 0 tasks completed

**Phase 1 (Complete):**

✅ All Phase 1 tasks completed

**Phase 2 (Complete):**

✅ All Phase 2 tasks completed

**Phase 3 (Move Shared and Module Infrastructure):**

- [x] Task 11: Move plugins to shared/plugins/ ✅ **COMPLETED** (Committed: 112cf77)
- [x] Task 12: Refactor WS router generation for modular architecture ✅ **COMPLETED** (Committed: 112cf77)
- [x] Task 13: Move api (health, versions) to shared/api/ ✅ **COMPLETED** (Committed: 112cf77)
- [x] Task 14: Move datafeed module files (service, api, ws) ✅ **COMPLETED** (Committed: f8bbf4f)
- [x] Task 15: Move broker module files (service, api, ws) ✅ **COMPLETED** (Committed: f8bbf4f)
- [ ] Task 16: Clean up legacy source files and folders
- [ ] Task 17: Verify WS router generation for modules
- [ ] Task 18: Test OpenAPI spec generation with module configurations
- [ ] Task 19: Test AsyncAPI spec generation with module configurations

**Phase 4 (Switch to Factory):**

- [ ] Task 20: Update fixtures to use factory and move tests to module directories

**Phase 5-7 (Finalize):**

- [ ] Task 21: Finalize and validate main.py, update build system and CI, full verification and documentation

---

## Impact Summary

| Aspect                 | Current                      | Target                  | Impact      |
| ---------------------- | ---------------------------- | ----------------------- | ----------- |
| Architecture           | Monolithic, global state     | Modular, factory-based  | 🔴 MAJOR    |
| Service Instantiation  | Global at import             | Lazy-loaded per module  | 🔴 MAJOR    |
| Tests                  | 100% depend on globals       | Factory-based fixtures  | 🔴 CRITICAL |
| Module Independence    | ❌ Tightly coupled           | ✅ Full isolation       | 🟢 POSITIVE |
| Deployment Flexibility | ❌ All modules always loaded | ✅ Configuration-driven | 🟢 POSITIVE |
| Test Parallelization   | ❌ Sequential, shared state  | ✅ Parallel, isolated   | 🟢 POSITIVE |
| Client Generation      | ✅ Works                     | ✅ Works (no change)    | ✅ NONE     |

## Critical Blocking Issues

1. **🔴 Global Service Instances** (P0) - `datafeed_service = DatafeedService()` in main.py → Move to factory
2. **🔴 Test Coupling to Globals** (P0) - All 48 tests import from main → Rewrite with fixtures
3. **🔴 Spec Export Script Compatibility** (P0) - `scripts/export_openapi_spec.py` imports `apiApp` from main.py → Must maintain export
4. **🟡 WebSocket Router Generation** (P1) - Refactor generation mechanism for module-specific output directories

## Objectives

- Modular architecture with pluggable datafeed/broker modules
- Application Factory Pattern for dynamic composition
- Protocol-based interfaces for type-safe contracts
- Independent testing and optional module loading
- Centralized models, backward compatible migration
- Support future microservice extraction

## Target Structure

```
backend/src/trading_api/
├── main.py                  # Minimal - calls create_app()
├── app_factory.py           # Application factory
├── models/                  # Centralized models
│   ├── broker/             # ... orders, positions, executions, etc.
│   └── market/             # ... bars, quotes, instruments, etc.
├── shared/                  # Always loaded
│   ├── module_interface.py
│   ├── module_registry.py
│   ├── plugins/fastws_adapter.py
│   ├── ws/                 # router_interface, generic_route (NO generated/)
│   ├── api/                # health, versions
│   └── tests/
└── modules/                 # Pluggable modules
    ├── datafeed/
    │   ├── __init__.py     # DatafeedModule
    │   ├── api.py          # DatafeedApi
    │   ├── ws.py           # DatafeedWsRouters + TypeAlias declarations
    │   ├── service.py      # DatafeedService
    │   ├── ws_generated/   # Generated WS routers (BarWsRouter, QuoteWsRouter)
    │   └── tests/
    └── broker/
        ├── __init__.py     # BrokerModule
        ├── api.py          # BrokerApi
        ├── ws.py           # BrokerWsRouters + TypeAlias declarations
        ├── service.py      # BrokerService
        ├── ws_generated/   # Generated WS routers (OrderWsRouter, etc.)
        └── tests/
```

## Module Architecture

### Module Protocol

```python
# shared/module_interface.py
class Module(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def enabled(self) -> bool: ...
    def get_api_routers(self) -> List[APIRouter]: ...
    def get_ws_routers(self) -> List: ...
    def configure_app(self, api_app, ws_app) -> None: ...
```

### Module Implementation Pattern

```python
# modules/datafeed/__init__.py (sample)
class DatafeedModule:
    def __init__(self):
        self._service = None
        self._enabled = True

    @property
    def name(self) -> str:
        return "datafeed"

    @property
    def service(self):
        if self._service is None:
            self._service = DatafeedService()  # Lazy load
        return self._service

    def get_api_routers(self) -> List[APIRouter]:
        return [DatafeedApi(service=self.service, ...)]
    # ... (similar pattern for broker)
```

### Application Factory

```python
# app_factory.py (sample)
def create_app(enabled_modules: List[str] | None = None) -> tuple[FastAPI, FastWSAdapter]:
    registry.register(DatafeedModule())
    registry.register(BrokerModule())

    # Filter if specified
    if enabled_modules:
        for m in registry._modules.values():
            m._enabled = m.name in enabled_modules

    api_app, ws_app = FastAPI(...), FastWSAdapter(...)

    # Include shared routers
    api_app.include_router(HealthApi(...), ...)
    api_app.include_router(VersionApi(...), ...)

    # Load enabled modules
    for module in registry.get_enabled_modules():
        for router in module.get_api_routers():
            api_app.include_router(router, ...)
        for ws_router in module.get_ws_routers():
            ws_app.include_router(ws_router)
    # ...
    return api_app, ws_app
```

### Updated main.py

```python
# main.py
import os
from typing import Annotated
from fastapi import Depends
from external_packages.fastws import Client
from trading_api.app_factory import create_app

enabled_modules = os.getenv("ENABLED_MODULES", "all")
if enabled_modules != "all":
    enabled_modules = [m.strip() for m in enabled_modules.split(",")]
else:
    enabled_modules = None

apiApp, wsApp = create_app(enabled_modules=enabled_modules)

@apiApp.websocket("/api/v1/ws")
async def websocket_endpoint(client: Annotated[Client, Depends(wsApp.manage)]):
    await wsApp.serve(client)

# CRITICAL: Maintain backward compatibility for spec export scripts
# scripts/export_openapi_spec.py and scripts/export_asyncapi_spec.py
# import apiApp directly from main.py
app = apiApp  # ✅ REQUIRED - DO NOT REMOVE
```

## Dependency Rules

```
✅ modules/*  → models/*, shared/*
✅ shared/*   → models/*
✅ models/*   → (nothing - pure data)

❌ modules/broker → modules/datafeed
❌ shared/*       → modules/*
```

### Enforcing Import Boundaries (Pattern-Based)

**Problem**: Cross-module imports break isolation and create tight coupling

**Solution**: Automated pattern-based validation (no hardcoded module names)

**Generic Rules** (apply to any module under `modules/`):

```python
# Pattern matching rules - survives module renames/additions/removals
GENERIC_RULES = {
    "modules/*": {
        "allowed": ["trading_api.models.*", "trading_api.shared.*"],
        "forbidden": ["trading_api.modules.*"],  # Block ALL cross-module imports
    },
    "shared/*": {
        "allowed": ["trading_api.models.*"],
        "forbidden": ["trading_api.modules.*"],
    },
    "models/*": {
        "allowed": [],  # Pure data - no trading_api imports
        "forbidden": ["trading_api.*"],
    },
}
```

**How it works**:

1. **Test scans all `.py` files** in `src/trading_api/` using AST parsing
2. **Extracts imports** from each file (handles `import X` and `from X import Y`)
3. **Matches file path** against patterns (`modules/*` matches any `modules/broker/`, `modules/datafeed/`, etc.)
4. **Validates imports** against allowed/forbidden patterns using glob-style matching
5. **Reports violations** with exact file path and forbidden import

**Example Violation Detection**:

```python
# File: modules/broker/service.py
from trading_api.modules.datafeed import DatafeedService  # ❌ VIOLATION

# Test output:
# ❌ modules/broker/service.py: Forbidden import 'trading_api.modules.datafeed'
#    (modules/* cannot import trading_api.modules.*)
```

**Validation**:

- Run `make test-boundaries` (AST-based import scanner)
- Integrated into `make test` (runs on every test suite execution)
- CI/CD gate (blocks PRs with violations)

**Benefits**:

- ✅ Zero configuration per module (generic patterns apply automatically)
- ✅ New modules inherit rules (add `modules/new_module/` → rules apply)
- ✅ Rename-safe (no hardcoded "broker" or "datafeed" strings)
- ✅ Fast execution (~1-2 seconds for entire codebase)
- ✅ Clear error messages with file paths

## Key Design Principles

1. **Application Factory** - Dynamic module composition via `create_app()`
2. **Protocol-Based** - Type-safe contracts without inheritance
3. **Lazy Loading** - Services created only when module enabled
4. **Module Registry** - Centralized management, auto-discovery ready
5. **Centralized Models** - Single source at root, supports microservices
6. **Shared Kernel** - Health/Versioning always available
7. **Tests Co-located** - Module ownership, isolated testing
8. **TDD Throughout** - Each phase validated with tests

## Key Decisions

| Decision               | Choice                      | Rationale                                     |
| ---------------------- | --------------------------- | --------------------------------------------- |
| Test Migration         | Gradual (fixtures first)    | Lower risk, parallel work                     |
| WS Router Generation   | Module-specific generation  | Clear ownership, module isolation, co-located |
| Broadcast Tasks        | Centralized (FastWSAdapter) | Simpler, current pattern works                |
| Backward Compatibility | Re-exports during migration | Less disruptive, gradual adoption             |
| Service Lifecycle      | Lazy loading                | Resource efficient, true independence         |
| CI Parallelization     | Immediate                   | 3x faster CI, natural fit                     |

## Export Script Compatibility

**CRITICAL**: The offline spec export scripts depend on importing `apiApp` from `main.py`:

```python
# scripts/export_openapi_spec.py
from trading_api.main import apiApp  # ← Breaks if main.py doesn't export apiApp

# scripts/export_asyncapi_spec.py
from trading_api.main import apiApp  # ← Also depends on this export
```

**Required Solution**: Maintain backward-compatible exports in main.py:

```python
# main.py (final lines)
apiApp, wsApp = create_app(enabled_modules=enabled_modules)

@apiApp.websocket("/api/v1/ws")
async def websocket_endpoint(...):
    await wsApp.serve(client)

# CRITICAL: DO NOT REMOVE - Required for spec export scripts
app = apiApp  # ✅ Enables: from trading_api.main import apiApp (or app)
```

**Impact**: Without this export, offline spec generation breaks, which breaks:

- `make export-openapi-spec` (backend)
- `make export-asyncapi-spec` (backend)
- Frontend client generation pipeline
- CI/CD spec validation

---

## Migration Phases

### Phase 0: Preparation (Parallel Fixtures Strategy)

**Objective**: Create test fixtures that work with BOTH current global-based main.py AND future factory-based approach

**Why Phase 0**: Enables gradual migration without breaking tests during Phases 1-5

**Implementation**:

```python
# backend/tests/conftest.py (NEW FILE)
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Phase 0: Wrap current globals (works immediately)
def _get_current_app():
    """Get app from current main.py globals"""
    from trading_api.main import apiApp
    return apiApp

# Phase 6: Switch to factory (just update this function)
# def _get_current_app():
#     from trading_api.app_factory import create_app
#     api_app, _ = create_app(enabled_modules=None)
#     return api_app

@pytest.fixture
def app():
    """Full application with all modules"""
    return _get_current_app()

@pytest.fixture
def client(app):
    """Sync test client for WebSocket tests"""
    return TestClient(app)

@pytest.fixture
async def async_client(app):
    """Async test client for API tests"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# Module-specific fixtures (placeholders for Phase 6)
@pytest.fixture
def datafeed_only_app():
    """Datafeed module only (Phase 6: use create_app(['datafeed']))"""
    return _get_current_app()  # Phase 0: returns full app

@pytest.fixture
def broker_only_app():
    """Broker module only (Phase 6: use create_app(['broker']))"""
    return _get_current_app()  # Phase 0: returns full app
```

**Migration Path**:

1. Create `tests/conftest.py` with fixtures wrapping current globals
2. Update ALL test files to use fixtures instead of direct imports:

   ```python
   # OLD (breaks in Phase 1-5):
   from trading_api.main import apiApp
   async with AsyncClient(app=apiApp, ...) as client:

   # NEW (works in Phase 0-9):
   async def test_something(async_client):  # ← Use fixture
       response = await async_client.get("/api/v1/health")
   ```

3. Validate ALL 48 tests pass with fixtures (before starting Phase 1)
4. Proceed with Phases 1-5 (tests continue passing via fixtures)
5. In Phase 6, update `_get_current_app()` to use factory (no test changes needed)

**Validation**:

```bash
# After Phase 0 implementation
cd backend
make test  # All 48 tests should pass with fixtures
make test-cov  # Coverage should match baseline
```

**Benefits**:

- ✅ Tests never break during migration (Phases 1-5)
- ✅ Gradual, low-risk approach
- ✅ Enables parallel work on infrastructure while tests stay green
- ✅ Single point of change in Phase 6 (fixtures, not individual tests)

---

### Phase 1: Infrastructure

- Create `shared/module_interface.py` (Module Protocol)
- Create `shared/module_registry.py` (ModuleRegistry)
- Create `app_factory.py` (create_app function)
- Create `modules/` directory structure

### Phase 2: Module Classes

- Create `modules/datafeed/__init__.py` (DatafeedModule)
- Create `modules/broker/__init__.py` (BrokerModule)
- Implement Module Protocol with lazy service property

### Phase 3: Move Shared and Module Infrastructure

**Task 11: Move Plugins**

- Move `plugins/` → `shared/plugins/`
- Add re-exports at old locations for backward compatibility

**Task 12: Refactor WebSocket Router Generation**

**Why refactor**: WS routers are currently generated into a centralized `ws/generated/` directory. In the modular architecture, each module should own its generated routers for true isolation.

**Current mechanism**:

1. TypeAlias declarations in `ws/datafeed.py` and `ws/broker.py`
2. Generator scans `ws/*.py` files for TypeAlias patterns
3. Generates concrete routers into `ws/generated/`
4. Modules import from `ws.generated`

**Target mechanism**:

1. TypeAlias declarations in `modules/datafeed/ws.py` and `modules/broker/ws.py`
2. Generator scans `modules/*/ws.py` files for TypeAlias patterns
3. Generates concrete routers into `modules/{module_name}/ws_generated/`
4. Modules import from `.ws_generated` (local import)

**Implementation steps**:

1. **Move template and interface to shared** (infrastructure only):

   ```bash
   mkdir -p src/trading_api/shared/ws
   mv src/trading_api/ws/router_interface.py src/trading_api/shared/ws/
   mv src/trading_api/ws/generic_route.py src/trading_api/shared/ws/
   ```

2. **Update generator script** (`scripts/generate_ws_router.py`):

   - Change scanner to find `modules/*/ws.py` files instead of `ws/*.py`
   - Update output path logic: `modules/{module_name}/ws_generated/` instead of `ws/generated/`
   - Generate module-specific `__init__.py` in each `ws_generated/` directory

   ```python
   # Key changes in generate_ws_router.py:

   def find_module_ws_files(base_dir: Path) -> list[tuple[str, Path]]:
       """Find all ws.py files in modules/ directory."""
       modules_dir = base_dir / "src/trading_api/modules"
       ws_files = []
       for module_dir in modules_dir.iterdir():
           if module_dir.is_dir():
               ws_file = module_dir / "ws.py"
               if ws_file.exists():
                   ws_files.append((module_dir.name, ws_file))
       return ws_files

   def generate_for_module(module_name: str, ws_file: Path, template: str, base_dir: Path):
       """Generate routers for a specific module."""
       router_specs = parse_router_specs_from_file(ws_file)
       output_dir = base_dir / f"src/trading_api/modules/{module_name}/ws_generated"
       # Clear and regenerate...
   ```

3. **Update wrapper script** (`scripts/generate-ws-routers.sh`):

   - Apply formatters/linters to all `modules/*/ws_generated/` directories

   ```bash
   GENERATED_DIRS="$BACKEND_DIR/src/trading_api/modules/*/ws_generated"
   for dir in $GENERATED_DIRS; do
       if [ -d "$dir" ]; then
           poetry run black "$dir"
           poetry run ruff format "$dir"
           # ... etc
       fi
   done
   ```

4. **Update verification script** (`scripts/verify_ws_routers.py`):

   - Update import paths to check module-specific generated routers
   - Verify each module's `ws_generated/` directory independently

5. **Delete centralized generated directory**:

   ```bash
   rm -rf src/trading_api/ws/generated/
   ```

6. **Regenerate all routers** with new module-specific structure:

   ```bash
   make generate-ws-routers
   ```

7. **Update module ws.py imports** (will be done in Phase 4-5):

   ```python
   # modules/datafeed/ws.py (after migration)
   from typing import TYPE_CHECKING, TypeAlias

   if TYPE_CHECKING:
       BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
   else:
       from .ws_generated import BarWsRouter  # Local import (not from shared)
   ```

**Validation**:

```bash
# Verify generated routers exist in module directories
ls -la src/trading_api/modules/datafeed/ws_generated/
ls -la src/trading_api/modules/broker/ws_generated/

# Verify no centralized generated directory
test ! -d src/trading_api/ws/generated/ && echo "✓ Centralized generated/ removed"

# Run generation and verify all quality checks pass
make generate-ws-routers

# All tests should still pass
make test
```

**Task 13: Move API Infrastructure**

- Move `api/health.py`, `api/versions.py` → `shared/api/`
- Add re-exports at old locations for backward compatibility

**Task 14: Move Datafeed Module Files**

- Move `core/datafeed_service.py` → `modules/datafeed/service.py`
- Move `api/datafeed.py` → `modules/datafeed/api.py`
- Move `ws/datafeed.py` → `modules/datafeed/ws.py`
- Update imports in `modules/datafeed/ws.py` to use `.ws_generated` (local import)
- Update imports to use `models.*`
- Update `modules/datafeed/__init__.py` to import from new locations
- All tests should still pass

**Task 15: Move Broker Module Files**

- Move `core/broker_service.py` → `modules/broker/service.py`
- Move `api/broker.py` → `modules/broker/api.py`
- Move `ws/broker.py` → `modules/broker/ws.py`
- Update imports in `modules/broker/ws.py` to use `.ws_generated` (local import)
- Update imports to use `models.*`
- Update `modules/broker/__init__.py` to import from new locations
- All tests should still pass

**Task 16: Clean Up Legacy Source Files and Folders**

**Objective**: Remove all legacy source files and backward compatibility re-exports now that all module files have been migrated.

**Implementation**:

1. **Remove legacy core/ files and directory**:

   ```bash
   cd backend/src/trading_api

   # Verify backward compatibility re-exports are in place
   grep -q "from ..modules.datafeed.service import DatafeedService" core/__init__.py
   grep -q "from ..modules.broker.service import BrokerService" core/__init__.py

   # Remove the core/ directory (only __init__.py with re-exports remains)
   rm -rf core/
   ```

2. **Remove legacy api/ files (keep **init**.py with re-exports)**:

   ```bash
   # The api/__init__.py contains backward compatibility re-exports
   # We'll keep it temporarily but verify it only has re-exports

   # Verify no other files exist in api/ except __init__.py
   ls -la api/  # Should only show __init__.py
   ```

3. **Remove legacy ws/ files (keep **init**.py with re-exports)**:

   ```bash
   # The ws/__init__.py contains backward compatibility re-exports
   # Verify no other files exist in ws/ except __init__.py

   ls -la ws/  # Should only show __init__.py and no generated/ directory

   # Verify centralized ws/generated/ directory was removed
   test ! -d ws/generated/ && echo "✓ Centralized ws/generated/ removed"
   ```

4. **Remove legacy plugins/ directory**:

   ```bash
   # Verify backward compatibility re-export exists
   grep -q "from trading_api.shared.plugins.fastws_adapter import FastWSAdapter" plugins/__init__.py

   # Remove the plugins/ directory
   rm -rf plugins/
   ```

5. **Update imports in main.py to remove backward compatibility layer**:

   ```python
   # Before (using backward compatibility re-exports):
   from trading_api.core import BrokerService, DatafeedService
   from trading_api.api import BrokerApi, DatafeedApi

   # After (direct imports from modules):
   # main.py uses app_factory, which imports directly from modules
   # No changes needed to main.py at this stage
   ```

6. **Verify directory structure**:
   ```bash
   # Expected structure after cleanup:
   tree -L 2 src/trading_api/
   # Should show:
   # ├── shared/          (plugins/, api/, ws/)
   # ├── modules/         (datafeed/, broker/)
   # ├── models/          (broker/, market/, etc.)
   # ├── app_factory.py
   # ├── main.py
   # ├── api/             (REMOVED - only __init__.py with re-exports gone)
   # ├── core/            (REMOVED completely)
   # ├── ws/              (REMOVED - only __init__.py with re-exports gone)
   # └── plugins/         (REMOVED completely)
   ```

**Validation**:

```bash
# Run all tests - should still pass with direct module imports
make test  # All 48 tests pass

# Verify type checking passes
make lint-check  # mypy should pass

# Verify no legacy imports remain in codebase
grep -r "from trading_api.core import" src/trading_api/ && echo "❌ Legacy core imports found" || echo "✓ No legacy core imports"
grep -r "from trading_api.api import" src/trading_api/ && echo "❌ Legacy api imports found" || echo "✓ No legacy api imports"
grep -r "from trading_api.ws import" src/trading_api/ && echo "❌ Legacy ws imports found" || echo "✓ No legacy ws imports"
grep -r "from trading_api.plugins import" src/trading_api/ && echo "❌ Legacy plugins imports found" || echo "✓ No legacy plugins imports"
```

**Expected Outcome**:

- All legacy directories removed (`core/`, `plugins/`)
- Only minimal backward compatibility re-exports remain in `api/__init__.py` and `ws/__init__.py` (to be removed in Task 19)
- All tests passing (48/48)
- Type checking clean
- No legacy imports in source code

**Commit Message**:

```
chore: Phase 3 Task 16 - Remove legacy source files and directories

- Remove core/ directory (services moved to modules/)
- Remove plugins/ directory (moved to shared/plugins/)
- Verify api/ and ws/ contain only backward compatibility re-exports
- Verify ws/generated/ centralized directory removed
- All tests passing (48/48)
- Type checking clean
```

**Task 17: Verify WS Router Generation for Modules**

- Run `make generate-ws-routers` to generate module-specific routers
- Verify `modules/datafeed/ws_generated/` contains all datafeed routers
- Verify `modules/broker/ws_generated/` contains all broker routers
- Verify no centralized `ws/generated/` directory exists
- All tests should still pass (48 passed)
- Type checking should pass (mypy)
- Linting should pass (black, isort, flake8)

**Validation**:

```bash
# Verify module structure
ls -la src/trading_api/modules/datafeed/
ls -la src/trading_api/modules/broker/

# Verify generated routers
ls -la src/trading_api/modules/datafeed/ws_generated/
ls -la src/trading_api/modules/broker/ws_generated/

# Verify centralized generated directory removed
test ! -d src/trading_api/ws/generated/ && echo "✓ Centralized generated/ removed"

# Run all quality checks
make test           # All 48 tests pass
make lint-check     # All linters pass
make type-check     # mypy passes

# Verify WS router generation works
make generate-ws-routers
```

**Task 18: Test OpenAPI Spec Generation with Module Configurations**

**Objective**: Verify OpenAPI spec generation works correctly with different module configurations (all modules, datafeed-only, broker-only)

**Implementation**:

1. **Scenario 1: Full Stack (All Modules)**

   ```bash
   # Generate spec with all modules enabled
   cd backend
   ENABLED_MODULES=all make export-openapi-spec

   # Verify spec contains both datafeed and broker endpoints
   grep -q "/api/v1/datafeed/config" openapi.json && echo "✓ Datafeed endpoints present"
   grep -q "/api/v1/broker/orders" openapi.json && echo "✓ Broker endpoints present"
   grep -q "/api/v1/health" openapi.json && echo "✓ Shared endpoints present"
   ```

2. **Scenario 2: Datafeed-Only**

   ```bash
   # Generate spec with datafeed module only
   ENABLED_MODULES=datafeed make export-openapi-spec
   mv openapi.json openapi-datafeed.json

   # Verify spec contains only datafeed and shared endpoints
   grep -q "/api/v1/datafeed/config" openapi-datafeed.json && echo "✓ Datafeed endpoints present"
   ! grep -q "/api/v1/broker/orders" openapi-datafeed.json && echo "✓ Broker endpoints absent"
   grep -q "/api/v1/health" openapi-datafeed.json && echo "✓ Shared endpoints present"
   ```

3. **Scenario 3: Broker-Only**

   ```bash
   # Generate spec with broker module only
   ENABLED_MODULES=broker make export-openapi-spec
   mv openapi.json openapi-broker.json

   # Verify spec contains only broker and shared endpoints
   ! grep -q "/api/v1/datafeed/config" openapi-broker.json && echo "✓ Datafeed endpoints absent"
   grep -q "/api/v1/broker/orders" openapi-broker.json && echo "✓ Broker endpoints present"
   grep -q "/api/v1/health" openapi-broker.json && echo "✓ Shared endpoints present"
   ```

**Validation**:

```bash
# All scenarios should produce valid OpenAPI specs
python -c "import json; json.load(open('openapi.json'))" && echo "✓ Full spec valid JSON"
python -c "import json; json.load(open('openapi-datafeed.json'))" && echo "✓ Datafeed spec valid JSON"
python -c "import json; json.load(open('openapi-broker.json'))" && echo "✓ Broker spec valid JSON"

# Verify frontend client generation works with full spec
cd ../frontend
make generate-openapi-client
make type-check  # Should pass

# Cleanup
cd ../backend
rm -f openapi-datafeed.json openapi-broker.json
```

**Expected Outcome**: OpenAPI specs correctly reflect enabled modules, shared endpoints always present, module-specific endpoints only when enabled.

---

**Task 19: Test AsyncAPI Spec Generation with Module Configurations**

**Objective**: Verify AsyncAPI spec generation works correctly with different module configurations (all modules, datafeed-only, broker-only)

**Implementation**:

1. **Scenario 1: Full Stack (All Modules)**

   ```bash
   # Generate spec with all modules enabled
   cd backend
   ENABLED_MODULES=all make export-asyncapi-spec

   # Verify spec contains both datafeed and broker WS channels
   grep -q '"bars"' asyncapi.json && echo "✓ Datafeed bars channel present"
   grep -q '"quotes"' asyncapi.json && echo "✓ Datafeed quotes channel present"
   grep -q '"orders"' asyncapi.json && echo "✓ Broker orders channel present"
   grep -q '"positions"' asyncapi.json && echo "✓ Broker positions channel present"
   grep -q '"executions"' asyncapi.json && echo "✓ Broker executions channel present"
   ```

2. **Scenario 2: Datafeed-Only**

   ```bash
   # Generate spec with datafeed module only
   ENABLED_MODULES=datafeed make export-asyncapi-spec
   mv asyncapi.json asyncapi-datafeed.json

   # Verify spec contains only datafeed WS channels
   grep -q '"bars"' asyncapi-datafeed.json && echo "✓ Datafeed bars channel present"
   grep -q '"quotes"' asyncapi-datafeed.json && echo "✓ Datafeed quotes channel present"
   ! grep -q '"orders"' asyncapi-datafeed.json && echo "✓ Broker orders channel absent"
   ! grep -q '"positions"' asyncapi-datafeed.json && echo "✓ Broker positions channel absent"
   ! grep -q '"executions"' asyncapi-datafeed.json && echo "✓ Broker executions channel absent"
   ```

3. **Scenario 3: Broker-Only**

   ```bash
   # Generate spec with broker module only
   ENABLED_MODULES=broker make export-asyncapi-spec
   mv asyncapi.json asyncapi-broker.json

   # Verify spec contains only broker WS channels
   ! grep -q '"bars"' asyncapi-broker.json && echo "✓ Datafeed bars channel absent"
   ! grep -q '"quotes"' asyncapi-broker.json && echo "✓ Datafeed quotes channel absent"
   grep -q '"orders"' asyncapi-broker.json && echo "✓ Broker orders channel present"
   grep -q '"positions"' asyncapi-broker.json && echo "✓ Broker positions channel present"
   grep -q '"executions"' asyncapi-broker.json && echo "✓ Broker executions channel present"
   ```

**Validation**:

```bash
# All scenarios should produce valid AsyncAPI specs
python -c "import json; json.load(open('asyncapi.json'))" && echo "✓ Full spec valid JSON"
python -c "import json; json.load(open('asyncapi-datafeed.json'))" && echo "✓ Datafeed spec valid JSON"
python -c "import json; json.load(open('asyncapi-broker.json'))" && echo "✓ Broker spec valid JSON"

# Verify frontend WS types generation works with full spec
cd ../frontend
make generate-asyncapi-types
make type-check  # Should pass

# Cleanup
cd ../backend
rm -f asyncapi-datafeed.json asyncapi-broker.json
```

**Expected Outcome**: AsyncAPI specs correctly reflect enabled modules, WS channels only included when their module is enabled.

---

### WebSocket Router Generation (Modular Architecture)

**Overview**: After Phase 3 Task 12, the WS router generation mechanism will be refactored to support module-specific output directories.

**New Structure**:

```
modules/
├── datafeed/
│   ├── ws.py              # TypeAlias declarations + DatafeedWsRouters class
│   └── ws_generated/      # Auto-generated (BarWsRouter, QuoteWsRouter)
│       ├── __init__.py
│       ├── barwsrouter.py
│       └── quotewsrouter.py
└── broker/
    ├── ws.py              # TypeAlias declarations + BrokerWsRouters class
    └── ws_generated/      # Auto-generated (OrderWsRouter, etc.)
        ├── __init__.py
        ├── orderwsrouter.py
        ├── positionwsrouter.py
        └── ...

shared/
└── ws/
    ├── router_interface.py  # WsRouterInterface, WsRouteService (shared)
    └── generic_route.py     # WsRouter template (shared)
```

**How it works**:

1. Developer writes TypeAlias in `modules/{module}/ws.py`:

   ```python
   if TYPE_CHECKING:
       BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
   else:
       from .ws_generated import BarWsRouter
   ```

2. Run `make generate-ws-routers`:

   - Scans all `modules/*/ws.py` files
   - Finds TypeAlias patterns using regex
   - Reads `shared/ws/generic_route.py` as template
   - Generates concrete classes into `modules/{module}/ws_generated/`
   - Applies all formatters and linters

3. Module uses local imports:
   ```python
   class DatafeedWsRouters(list[WsRouterInterface]):
       def __init__(self, datafeed_service: WsRouteService):
           from .ws_generated import BarWsRouter, QuoteWsRouter  # Local!
           bar_router = BarWsRouter(route="bars", service=datafeed_service)
           super().__init__([bar_router, quote_router])
   ```

**Benefits**:

- ✅ **Module ownership** - Each module owns its generated routers
- ✅ **Clear isolation** - No centralized `shared/ws/generated/` directory
- ✅ **Co-location** - Generated code lives with module that uses it
- ✅ **Same workflow** - Developers still write TypeAlias and run `make generate-ws-routers`
- ✅ **Independent testing** - Can regenerate one module without affecting others

**Makefile commands** (unchanged from current):

```bash
make generate-ws-routers  # Generates all module routers
```

---

### Phase 4: Switch Fixtures to Factory and Reorganize Tests

**Task 20: Update Fixtures and Move Tests**

**Prerequisite**: Phase 3 completed (all module files moved, spec generation tested)

**Implementation**:

1. **Update fixture to use factory** (single line change):

   ```python
   # backend/tests/conftest.py
   def _get_current_app():
       # OLD: from trading_api.main import apiApp; return apiApp
       # NEW:
       from trading_api.app_factory import create_app
       api_app, _ = create_app(enabled_modules=None)  # All modules
       return api_app
   ```

2. **Add module-specific fixtures**:

   ```python
   @pytest.fixture
   def datafeed_only_app():
       from trading_api.app_factory import create_app
       api_app, _ = create_app(enabled_modules=["datafeed"])
       return api_app

   @pytest.fixture
   def broker_only_app():
       from trading_api.app_factory import create_app
       api_app, _ = create_app(enabled_modules=["broker"])
       return api_app
   ```

3. **Move tests to module directories**:

   - Move shared tests: `test_api_health.py`, `test_api_versioning.py` → `shared/tests/`
   - Move module tests: `test_api_broker.py`, `test_ws_broker.py` → `modules/broker/tests/`
   - Move datafeed tests → `modules/datafeed/tests/`
   - Create `tests/integration/` with new integration tests

4. **Validate**:
   ```bash
   make test  # All 48 tests should still pass
   make test-datafeed  # Datafeed module tests only
   make test-broker  # Broker module tests only
   ```

**Risk**: 🟢 LOW (if Phase 0 completed correctly, this is a single function change)

---

### Phase 5: Finalize and Validate

**Task 21: Finalize main.py, Update Build System, and Full Verification**

**Part 1: Finalize main.py**

Main.py already updated in Phase 1-3, just validate:

```python
# main.py structure after Phases 1-5:
import os
from typing import Annotated
from fastapi import Depends
from external_packages.fastws import Client
from trading_api.app_factory import create_app

enabled_modules = os.getenv("ENABLED_MODULES", "all")
if enabled_modules != "all":
    enabled_modules = [m.strip() for m in enabled_modules.split(",")]
else:
    enabled_modules = None

apiApp, wsApp = create_app(enabled_modules=enabled_modules)

@apiApp.websocket("/api/v1/ws")
async def websocket_endpoint(client: Annotated[Client, Depends(wsApp.manage)]):
    await wsApp.serve(client)

app = apiApp  # ✅ CRITICAL: Required for spec export scripts
```

**Validation**:

```bash
make export-openapi-spec  # Should work (uses app export)
make export-asyncapi-spec  # Should work
python -c "from trading_api.main import apiApp; print('✓')"  # Should print ✓
```

**Part 2: Update Build System**

- Add Makefile targets: `test-shared`, `test-datafeed`, `test-broker`, `test-integration`
- Update WS generation script paths
- Update CI workflow for parallel testing

**Part 3: Full Verification**

- Run full test suite: `make test`
- Verify module isolation: `make test-datafeed`, `make test-broker`
- Test deployments: datafeed-only, broker-only, full-stack
- Validate client generation (should be identical)
- Remove old directories after validation

---

### Phase 6: Documentation Updates

**Task 22: Update All Documentation to Reflect Modular Architecture**

**Objective**: Update all project documentation to reflect the new modular architecture, remove references to legacy structure, and document the new patterns.

**Implementation**:

1. **Update ARCHITECTURE.md**:

   - Document the modular architecture with modules/, shared/, and models/ structure
   - Add dependency rules and import boundaries
   - Document the Module Protocol pattern
   - Add diagrams showing the new dependency graph
   - Remove references to legacy core/, api/, ws/ structure
   - Document the application factory pattern
   - Add examples of module-specific deployments

2. **Update backend/README.md**:

   - Update directory structure documentation
   - Document new development workflow with modules
   - Update testing commands (test-shared, test-datafeed, test-broker)
   - Document ENABLED_MODULES environment variable
   - Add examples of running specific modules
   - Update WebSocket router generation documentation

3. **Update docs/DEVELOPMENT.md**:

   - Document how to add new modules
   - Explain the Module Protocol implementation
   - Document lazy loading pattern
   - Add troubleshooting section for common module issues
   - Document module isolation testing

4. **Update docs/TESTING.md**:

   - Document the new fixture-based testing approach
   - Explain module-specific test fixtures (datafeed_only_app, broker_only_app)
   - Document how to test individual modules
   - Update test organization (shared/tests/, modules/\*/tests/)
   - Document parallel test execution in CI

5. **Create modules/README.md**:

   - Explain the modular architecture philosophy
   - Document how to create a new module
   - List all available modules with descriptions
   - Document module dependencies and boundaries
   - Provide template for new module creation

6. **Update WEBSOCKET-METHODOLOGY.md**:

   - Document new module-specific ws_generated/ directories
   - Update WebSocket router generation workflow
   - Remove references to centralized ws/generated/
   - Document TypeAlias pattern in modules/\*/ws.py
   - Add examples from datafeed and broker modules

7. **Update API-METHODOLOGY.md**:

   - Document module-based API organization
   - Explain shared vs. module-specific APIs
   - Document how modules register API routers
   - Update versioning strategy for modular APIs

8. **Update docs/CLIENT-GENERATION.md**:

   - Confirm that client generation is unchanged
   - Document that specs are generated from composed application
   - Add note about module-specific spec generation (optional)
   - Document ENABLED_MODULES impact on generated specs

9. **Update .github/CI-TROUBLESHOOTING.md** (if exists):

   - Document new parallel test jobs
   - Add troubleshooting for module-specific test failures
   - Document how to run module-specific CI checks locally

10. **Update frontend documentation** (BROKER-TERMINAL-SERVICE.md, etc.):

    - Confirm no changes to frontend integration
    - Document that backend modular architecture is transparent to frontend
    - Note that WebSocket and API contracts remain unchanged

11. **Create MIGRATION-GUIDE.md** (new):

    - Document the migration from monolithic to modular architecture
    - List all breaking changes (if any)
    - Provide migration path for external integrations
    - Document backward compatibility period and deprecation timeline
    - Include before/after import examples

12. **Update MODULAR_BACKEND_IMPL.md**:
    - Mark all tasks as completed
    - Update status to "Complete"
    - Add final verification checklist
    - Document lessons learned
    - Archive as historical record

**Validation**:

```bash
# Verify all documentation files are updated
grep -r "core/broker_service" docs/ && echo "❌ Legacy references found" || echo "✓ No legacy core/ references"
grep -r "api/broker" docs/ && echo "❌ Legacy references found" || echo "✓ No legacy api/ references"
grep -r "ws/generated" docs/ && echo "❌ Legacy references found" || echo "✓ No legacy ws/generated references"

# Verify new patterns are documented
grep -r "modules/" docs/ && echo "✓ Modular architecture documented"
grep -r "Module Protocol" docs/ && echo "✓ Module Protocol documented"
grep -r "ENABLED_MODULES" docs/ && echo "✓ Module selection documented"

# Verify documentation builds/renders correctly (if using doc generators)
make docs  # If applicable
```

**Expected Outcome**:

- All documentation updated to reflect modular architecture
- No references to legacy structure (core/, api/, ws/, plugins/)
- Clear guidance for developers on working with modules
- Migration guide for external teams
- Updated diagrams and examples throughout

**Commit Message**:

```
docs: Phase 6 Task 22 - Update all documentation for modular architecture

- Update ARCHITECTURE.md with modular structure and dependency rules
- Update backend/README.md with new directory structure
- Update DEVELOPMENT.md, TESTING.md with module patterns
- Create modules/README.md with module creation guide
- Update WebSocket and API methodology docs
- Create MIGRATION-GUIDE.md for external teams
- Remove all legacy structure references
- Add module-specific deployment examples
```

---

## Testing Strategy

### Module Isolation

```bash
make test-shared      # Shared infrastructure only
make test-datafeed    # Datafeed module only (no broker loaded)
make test-broker      # Broker module only (no datafeed loaded)
make test-integration # Full stack with all modules
```

### Test Fixtures Pattern

```python
# backend/tests/conftest.py (sample)
@pytest.fixture
def datafeed_only_app():
    api_app, ws_app = create_app(enabled_modules=["datafeed"])
    return api_app

@pytest.fixture
def datafeed_client(datafeed_only_app):
    return TestClient(datafeed_only_app)
# ... (similar for broker, full_app)
```

### CI Parallel Execution

```yaml
# Parallel jobs
jobs:
  test-shared: # ~2 min
  test-datafeed: # ~3 min
  test-broker: # ~4 min
  test-integration: # ~5 min (runs after others)
# Total: ~7 min (vs. 15 min sequential)
```

## Deployment Configurations

### Development

```bash
make dev                                    # All modules
ENABLED_MODULES=datafeed make dev           # Datafeed only
ENABLED_MODULES=broker make dev             # Broker only
ENABLED_MODULES=datafeed,broker make dev    # Specific modules
```

### Production (Docker Compose sample)

```yaml
services:
  trading-api-full:
    environment:
      - ENABLED_MODULES=all

  trading-api-datafeed:
    environment:
      - ENABLED_MODULES=datafeed

  trading-api-broker:
    environment:
      - ENABLED_MODULES=broker
```

## Future Enhancements

- **Microservice Extraction** - Structure enables easy separation with minimal changes
- **Config-Based Loading** - YAML config instead of env vars for module configuration
- **Auto-Discovery** - Plugin system with `pkgutil.iter_modules()` for dynamic module loading
- **Third-Party Modules** - External plugins implementing Module Protocol

---

## Client Generation Impact

### Zero Breaking Changes Guarantee

**Impact:** ✅ **NONE** - Client generation remains completely unchanged

**Why:** Specs are generated from the **composed application** (`main.py`), not individual modules:

```python
# main.py still exposes unified APIs
from trading_api.modules.datafeed import DatafeedApi, DatafeedService
from trading_api.modules.broker import BrokerApi, BrokerService

apiApp = FastAPI(...)
apiApp.include_router(DatafeedApi(...))  # Composed into single API
apiApp.include_router(BrokerApi(...))

# Spec export unchanged
apiApp.openapi()   # ✅ Generates same OpenAPI spec
wsApp.asyncapi()   # ✅ Generates same AsyncAPI spec
```

### Frontend Compatibility

| Component          | Before Refactoring                  | After Refactoring                   | Impact  |
| ------------------ | ----------------------------------- | ----------------------------------- | ------- |
| OpenAPI Spec       | `apiApp.openapi()`                  | `apiApp.openapi()`                  | ✅ None |
| AsyncAPI Spec      | `wsApp.asyncapi()`                  | `wsApp.asyncapi()`                  | ✅ None |
| Generated Client   | `@/clients/trader-client-generated` | `@/clients/trader-client-generated` | ✅ None |
| Generated WS Types | `@/clients/ws-types-generated`      | `@/clients/ws-types-generated`      | ✅ None |
| Type Imports       | Same paths                          | Same paths                          | ✅ None |
| Mappers            | `@/plugins/mappers.ts`              | `@/plugins/mappers.ts`              | ✅ None |

**Principle:** Frontend sees a **unified API contract**, never internal module boundaries

### Validation Steps

Post-refactoring verification checklist:

```bash
# 1. Generate specs (should be identical)
make export-openapi-offline
diff backend/openapi.json backend/openapi.json.backup

# 2. Generate clients
cd frontend && make generate-openapi-client
cd frontend && make generate-asyncapi-types

# 3. Verify no breaking changes
make type-check  # Should pass without changes
make test        # All tests should pass
```

---

## Current vs. Target Dependency Graphs

### Current Dependency Graph (As-Is Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main.py (Entry Point)                        │
│  - Global service instances: datafeed_service, broker_service        │
│  - Global router lists: api_routers, ws_routers                      │
│  - Composes everything at module import time                         │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌──────────────┐      ┌──────────────┐
    │   api/       │      │   ws/        │
    │ (REST APIs)  │      │ (WebSocket)  │
    └──────┬───────┘      └──────┬───────┘
           │                     │
           │    ┌────────────────┘
           │    │
           ▼    ▼
    ┌─────────────────┐
    │   core/         │
    │ (Services)      │
    │ - BrokerService │
    │ - DatafeedSvc   │
    └────────┬────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │   ws/router_interface.py     │
    │ (WsRouteService Protocol)    │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │   models/                    │
    │ - broker/                    │
    │ - market/                    │
    │ - common.py                  │
    │ - health.py                  │
    │ - versioning.py              │
    └──────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                   plugins/fastws_adapter.py                    │
│  - Imports: ws.router_interface (WsRouterInterface)           │
│  - Orchestrates broadcast tasks for all routers               │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                    ws/generated/ (Auto-Gen)                    │
│  - BarWsRouter, QuoteWsRouter                                 │
│  - OrderWsRouter, PositionWsRouter, ExecutionWsRouter         │
│  - EquityWsRouter, BrokerConnectionWsRouter                   │
│  - Generated from TypeAlias declarations in broker.py         │
└───────────────────────────────────────────────────────────────┘

Import Dependency Flow (Current):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

main.py
  ├─> api/__init__.py
  │     ├─> api/broker.py
  │     │     ├─> core.BrokerService
  │     │     └─> models.broker.*
  │     ├─> api/datafeed.py
  │     │     ├─> core.DatafeedService
  │     │     └─> models.market.*
  │     ├─> api/health.py
  │     │     └─> models.health, models.versioning
  │     └─> api/versions.py
  │           └─> models.versioning
  │
  ├─> core/__init__.py
  │     ├─> core/broker_service.py
  │     │     ├─> models.broker.*
  │     │     └─> ws.router_interface (WsRouteService)
  │     └─> core/datafeed_service.py
  │           ├─> models.market.*
  │           └─> ws.router_interface (WsRouteService)
  │
  ├─> ws/__init__.py
  │     ├─> ws/broker.py
  │     │     ├─> models.broker.*
  │     │     ├─> ws.generic_route (WsRouter)
  │     │     ├─> ws.router_interface
  │     │     └─> ws.generated.* (imports generated routers)
  │     └─> ws/datafeed.py
  │           ├─> models.market.*
  │           ├─> ws.generic_route (WsRouter)
  │           ├─> ws.router_interface
  │           └─> ws.generated.* (imports generated routers)
  │
  ├─> plugins/fastws_adapter.py
  │     └─> ws.router_interface (WsRouterInterface)
  │
  └─> models/__init__.py
        └─> models.{broker,market,common,health,versioning}

Key Issues:
  ⚠️  Global service instances created at import time
  ⚠️  All modules loaded unconditionally (no lazy loading)
  ⚠️  Tests import from main.py (tight coupling to globals)
  ⚠️  No module boundaries - everything cross-imports
```

---

### Target Dependency Graph (Modular Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        main.py (Minimal Root)                        │
│  - Parses ENABLED_MODULES env var                                   │
│  - Calls create_app(enabled_modules)                                │
│  - Registers WebSocket endpoint                                     │
│  - NO service instances, NO global state                            │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  app_factory.py        │
          │  create_app(modules)   │
          │  - Registers modules   │
          │  - Filters enabled     │
          │  - Composes FastAPI    │
          └────────┬───────────────┘
                   │
        ┌──────────┴──────────────────────────┐
        │                                     │
        ▼                                     ▼
┌───────────────────┐              ┌─────────────────────┐
│ shared/           │              │ modules/            │
│ (Always Loaded)   │              │ (Lazy Loaded)       │
├───────────────────┤              ├─────────────────────┤
│ module_interface  │◄─────────────│ datafeed/           │
│ module_registry   │              │   __init__.py       │
│                   │              │   api.py            │
│ api/              │              │   ws.py             │
│   health.py       │              │   service.py        │
│   versions.py     │              │   tests/            │
│                   │              │                     │
│ ws/               │              │ broker/             │
│   router_interface│              │   __init__.py       │
│   generic_route   │              │   api.py            │
│   generated/      │              │   ws.py             │
│                   │              │   service.py        │
│ plugins/          │              │   tests/            │
│   fastws_adapter  │              │                     │
└───────────────────┘              └─────────────────────┘
        │                                     │
        │                                     │
        └─────────────┬───────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  models/              │
          │  (Root Level - Shared)│
          ├───────────────────────┤
          │  broker/              │
          │    orders.py          │
          │    positions.py       │
          │    executions.py      │
          │    account.py         │
          │    ...                │
          │                       │
          │  market/              │
          │    bars.py            │
          │    quotes.py          │
          │    instruments.py     │
          │    ...                │
          │                       │
          │  common.py            │
          │  health.py            │
          │  versioning.py        │
          └───────────────────────┘

Import Dependency Flow (Target):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

main.py
  └─> app_factory.create_app()
        │
        ├─> shared.module_registry
        │     └─> shared.module_interface (Module Protocol)
        │
        ├─> modules.datafeed.DatafeedModule
        │     ├─> modules.datafeed.api (DatafeedApi)
        │     │     └─> models.market.*
        │     ├─> modules.datafeed.ws (DatafeedWsRouters)
        │     │     ├─> models.market.*
        │     │     └─> shared.ws.generic_route
        │     └─> modules.datafeed.service (DatafeedService)
        │           ├─> models.market.*
        │           └─> shared.ws.router_interface
        │
        ├─> modules.broker.BrokerModule
        │     ├─> modules.broker.api (BrokerApi)
        │     │     └─> models.broker.*
        │     ├─> modules.broker.ws (BrokerWsRouters)
        │     │     ├─> models.broker.*
        │     │     └─> shared.ws.generic_route
        │     └─> modules.broker.service (BrokerService)
        │           ├─> models.broker.*
        │           └─> shared.ws.router_interface
        │
        ├─> shared.api.health (HealthApi)
        │     └─> models.health, models.versioning
        │
        ├─> shared.api.versions (VersionApi)
        │     └─> models.versioning
        │
        └─> shared.plugins.fastws_adapter (FastWSAdapter)
              └─> shared.ws.router_interface

Strict Import Rules:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ modules/*     → CAN import from → models/*, shared/*
  ✅ shared/*      → CAN import from → models/*
  ✅ models/*      → CAN import from → (nothing, pure data)

  ❌ modules/broker     → CANNOT import → modules/datafeed
  ❌ modules/datafeed   → CANNOT import → modules/broker
  ❌ shared/*           → CANNOT import → modules/*
  ❌ models/*           → CANNOT import → (anything)

Benefits:
  ✅ No circular dependencies
  ✅ Modules completely isolated from each other
  ✅ Shared infrastructure independent of modules
  ✅ Models remain the single source of truth
  ✅ Clear ownership and responsibility boundaries
```

## Validation Checklist

### Phase Completion

- [ ] Infrastructure created (Protocol, Registry, Factory)
- [ ] Module classes implement Protocol
- [ ] Files moved with re-exports
- [ ] Tests reorganized with fixtures
- [ ] main.py refactored (no globals)
- [ ] Makefile targets added
- [ ] All tests pass: `make test`

### Module Isolation

```bash
# Datafeed-only deployment
ENABLED_MODULES=datafeed make dev
curl http://localhost:8000/api/v1/datafeed/config  # ✅ Should work
curl http://localhost:8000/api/v1/broker/orders     # ❌ Should 404

# Broker-only deployment
ENABLED_MODULES=broker make dev
curl http://localhost:8000/api/v1/broker/orders      # ✅ Should work
curl http://localhost:8000/api/v1/datafeed/config    # ❌ Should 404
```

### Client Generation

```bash
cp backend/openapi.json backend/openapi.json.backup
make dev && make export-openapi-spec
diff backend/openapi.json backend/openapi.json.backup  # Should be identical
cd frontend && make generate-openapi-client && make type-check  # Should pass
```

## Pre-Migration Validation

**MANDATORY**: Complete this checklist before starting Phase 0:

```bash
# 1. Baseline - All tests passing
cd backend
make test  # Must show: 48 passed

# 2. Capture coverage baseline
make test-cov > baseline-coverage.txt
cat baseline-coverage.txt  # Review coverage percentages

# 3. Verify spec export works
make export-openapi-spec
make export-asyncapi-spec
ls -lh openapi.json asyncapi.json  # Files should exist

# 4. Verify frontend client generation works
cd ../frontend
make generate-openapi-client
make generate-asyncapi-types
make type-check  # Must pass without errors

# 5. Create baseline tag
cd ..
git add -A
git commit -m "chore: baseline before modular backend refactoring"
git tag pre-modular-baseline
git push origin pre-modular-baseline

# 6. Document current state
cd backend
find src/trading_api -name '*.py' | wc -l  # Count Python files
find tests -name 'test_*.py' -exec grep -l '^def test_' {} \; | wc -l  # Count test files
```

**Checklist**:

- [ ] All 48 tests pass
- [ ] Coverage baseline captured
- [ ] Spec export scripts work
- [ ] Frontend clients generate and type-check
- [ ] Baseline tag created and pushed
- [ ] Current state documented

**If ANY item fails**: Fix before proceeding. The migration assumes a working baseline.

---

## Summary

### Effort Estimate

- **Total Tests**: 48 functions (validated) → 12 hours (~1.5 days) to migrate to fixtures
- **Files to Move**: ~15 files
- **New Test Structure**: 3 module test directories + 1 integration directory
- **CI Improvement**: 3x faster (estimated ~20min → ~7min with parallel execution)
- **Risk**: 🟡 MODERATE with Phase 0 (fixtures-first), 🔴 HIGH without Phase 0

### Revised Timeline (with Consolidated Phases)

- **Week 1**: Phase 0 (fixtures) + Phase 1 (infrastructure)
- **Week 2**: Phase 2 (module classes)
- **Week 3**: Phase 3 (move shared + move module files + verify ws generation + test spec generation)
- **Week 4**: Phase 4 (switch fixtures to factory + reorganize tests)
- **Week 5**: Phase 5 (finalize main.py + build system + verification)

**Total Duration**: 5 weeks (safer approach with continuous testing)

**Total Tasks**: 21 tasks

- Phase 0: 2 tasks (fixtures infrastructure)
- Phase 1: 4 tasks (core infrastructure)
- Phase 2: 2 tasks (module classes)
- Phase 3: 7 tasks (move files + cleanup legacy + verify generation + test specs)
- Phase 4: 1 task (switch to factory)
- Phase 5: 1 task (finalize + verify)

**Key Additions**: Task 16 removes all legacy source files and folders. Tasks 18-19 ensure spec generation works correctly with modular architecture across all deployment configurations (full, datafeed-only, broker-only).

### First Steps

```bash
# 1. Complete pre-migration validation (see checklist above)
# Ensure baseline tag exists: git tag | grep pre-modular-baseline

# 2. Create feature branch
git checkout -b feature/modular-backend

# 3. Start Phase 0 (Parallel Fixtures)
cd backend

# Create conftest.py with fixtures
cat > tests/conftest.py << 'EOF'
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

def _get_current_app():
    """Get app from current main.py globals (Phase 0)"""
    from trading_api.main import apiApp
    return apiApp

@pytest.fixture
def app():
    return _get_current_app()

@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
async def async_client(app):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
EOF

# 4. Update first test file to use fixtures (example)
# Then update remaining 47 tests similarly

# 5. Validate Phase 0 complete
make test  # Must show: 48 passed (same as baseline)
make test-cov  # Coverage should match baseline

# 6. Commit Phase 0
git add tests/conftest.py tests/*.py
git commit -m "feat: Phase 0 - Add parallel fixtures for gradual migration"

# 7. Proceed to Phase 1 (infrastructure)
mkdir -p src/trading_api/{shared,modules/{broker,datafeed}}
# Create module_interface.py, module_registry.py, app_factory.py
```

---

**Status**: ✅ Validated & Ready for Implementation | **Last Updated**: 2025-10-29
**Validation**: Baseline tests = 48 (not 63), spec export compatibility confirmed, Phase 0 strategy added
