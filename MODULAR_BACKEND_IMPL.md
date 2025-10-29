# Modular Backend Implementation Plan

**Status**: In Progress - Phase 0 | **Created**: 2025-10-28 | **Updated**: 2025-10-29

## 🚀 Implementation Progress

> **⚠️ CRITICAL**: Update this section at the end of EVERY individual task completion.
>
> - Move completed task from "In Progress" to "Completed" with date and commit hash
> - Update task counters (X/20 tasks)
> - Move next task to "In Progress"
> - Commit the updated MODULAR_BACKEND_IMPL.md with task changes

### ✅ Completed (3/20 tasks)

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

### 🔄 In Progress (0/20 tasks)

**Phase 0 Complete! ✅**

All test files have been successfully migrated to use fixtures and are fully decoupled from main.py globals. The modular backend refactoring foundation is ready.

**Next Steps:**

- Phase 1: Create infrastructure (Module Protocol, Registry, Factory)
- Phase 2: Implement module classes (DatafeedModule, BrokerModule)

### 📋 Pending (17/20 tasks)

**Phase 0 (Complete):**

✅ All Phase 0 tasks completed

**Phase 1 (Infrastructure):**

- [ ] Task 5: Create `shared/module_interface.py`
- [ ] Task 6: Create `shared/module_registry.py`
- [ ] Task 7: Create `app_factory.py`
- [ ] Task 8: Create modules directory structure

**Phase 2 (Module Classes):**

- [ ] Task 9: Create DatafeedModule class
- [ ] Task 10: Create BrokerModule class

**Phase 3 (Move Shared):**

- [ ] Task 11: Move plugins to shared/plugins/
- [ ] Task 12: Move ws infrastructure to shared/ws/
- [ ] Task 13: Move api (health, versions) to shared/api/

**Phase 4-5 (Move Modules):**

- [ ] Task 14: Move datafeed module files
- [ ] Task 15: Move broker module files

**Phase 6 (Switch to Factory):**

- [ ] Task 16: Update fixtures to use factory
- [ ] Task 17: Move tests to module directories

**Phase 7-9 (Finalize):**

- [ ] Task 18: Finalize and validate main.py
- [ ] Task 19: Update build system and CI
- [ ] Task 20: Full verification and documentation

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
4. **🟡 WebSocket Router Generation** (P1) - Update paths to `shared/ws/generated/`

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
│   ├── ws/                 # router_interface, generic_route, generated/
│   ├── api/                # health, versions
│   └── tests/
└── modules/                 # Pluggable modules
    ├── datafeed/
    │   ├── __init__.py     # DatafeedModule
    │   ├── api.py, ws.py, service.py
    │   └── tests/
    └── broker/
        ├── __init__.py     # BrokerModule
        ├── api.py, ws.py, service.py
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

| Decision               | Choice                      | Rationale                             |
| ---------------------- | --------------------------- | ------------------------------------- |
| Test Migration         | Gradual (fixtures first)    | Lower risk, parallel work             |
| WS Router Generation   | Keep current approach       | Proven stable, simple path update     |
| Broadcast Tasks        | Centralized (FastWSAdapter) | Simpler, current pattern works        |
| Backward Compatibility | Re-exports during migration | Less disruptive, gradual adoption     |
| Service Lifecycle      | Lazy loading                | Resource efficient, true independence |
| CI Parallelization     | Immediate                   | 3x faster CI, natural fit             |

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

### Phase 3: Move Shared Infrastructure

- Move `plugins/` → `shared/plugins/`
- Move `ws/router_interface.py`, `ws/generic_route.py`, `ws/generated/` → `shared/ws/`
- Move `api/health.py`, `api/versions.py` → `shared/api/`
- Add re-exports at old locations for backward compatibility

### Phase 4-5: Move Module Files

- Move `core/datafeed_service.py` → `modules/datafeed/service.py`
- Move `api/datafeed.py` → `modules/datafeed/api.py`
- Move `ws/datafeed.py` → `modules/datafeed/ws.py`
- Repeat for broker module
- Update imports to use `models.*`

### Phase 6: Switch Fixtures to Factory

**Prerequisite**: Phase 0 completed (all tests use fixtures from `conftest.py`)

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

### Phase 7: Finalize main.py

**Implementation**: Main.py already updated in Phase 1-5, just validate:

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

### Phase 8: Build System

- Add Makefile targets: `test-shared`, `test-datafeed`, `test-broker`, `test-integration`
- Update WS generation script paths
- Update CI workflow for parallel testing

### Phase 9: Verification

- Run full test suite: `make test`
- Verify module isolation: `make test-datafeed`, `make test-broker`
- Test deployments: datafeed-only, broker-only, full-stack
- Validate client generation (should be identical)
- Update documentation
- Remove old directories after validation

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

### Revised Timeline (with Phase 0)

- **Week 1**: Phase 0 (fixtures) + Phase 1 (infrastructure)
- **Week 2**: Phase 2-3 (module classes + shared migration)
- **Week 3**: Phase 4-5 (move module files)
- **Week 4**: Phase 6-7 (switch fixtures to factory, finalize main.py)
- **Week 5**: Phase 8-9 (build system + verification)

**Total Duration**: 5 weeks (safer approach with continuous testing)

**Alternative (Big Bang)**: 3 weeks with tests broken during Phases 1-5 (higher risk)

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
