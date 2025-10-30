# API Spec Refactoring - Per-Module Specs

**Status**: In Progress  
**Started**: October 30, 2025  
**Duration**: 11 days

## Goal

**CRITICAL: Prepare for multi-process architecture where each module runs as a separate service.**

Per-module OpenAPI/AsyncAPI specs with auto-discovery:

- **Self-contained specs per module** → Each module has its own OpenAPI/AsyncAPI spec
- **Inter-module HTTP communication** → Modules communicate via HTTP (not direct Python imports)
- **Python HTTP clients** → Type-safe clients for inter-module calls (e.g., broker calls datafeed)
- **Frontend tree-shaking** → Module-specific TypeScript clients (import only what you need)
- **Microservice-ready** → Each module CAN run as separate process/container

## Architecture Transition

### Current (Monolith - Single Process)

```
┌─────────────────────────────────────┐
│  FastAPI App (Single Process)      │
│  ┌──────────┐     ┌──────────┐    │
│  │  Broker  │ ──▶ │ Datafeed │    │  Direct Python imports
│  │  Module  │     │  Module  │    │  (from trading_api.modules.datafeed...)
│  └──────────┘     └──────────┘    │
└─────────────────────────────────────┘
```

### Target (Multi-Process - Microservices)

```
┌──────────────────┐         ┌──────────────────┐
│ Broker Service   │         │ Datafeed Service │
│ (Process 1)      │  HTTP   │ (Process 2)      │
│ Port: 8001       │ ──────▶ │ Port: 8002       │
│                  │ Client  │                  │
│ Uses:            │         │ Exposes:         │
│ datafeed_client  │         │ /api/v1/symbols  │
└──────────────────┘         └──────────────────┘
         │                            │
         │         HTTP               │
         └────────────┬───────────────┘
                      ▼
              ┌──────────────┐
              │   Frontend   │
              │ trader-client│
              │   -broker    │
              │ trader-client│
              │   -datafeed  │
              └──────────────┘
```

## Why This Refactoring?

1. **Enable independent scaling** → Scale datafeed separately from broker
2. **Independent deployment** → Deploy broker without restarting datafeed
3. **Technology flexibility** → Future modules can use different languages
4. **Fault isolation** → Datafeed crash doesn't take down broker
5. **Development isolation** → Teams can work on modules independently

## Target Structure

```
backend/src/trading_api/modules/
├── broker/
│   ├── specs/
│   │   ├── openapi.json
│   │   └── asyncapi.json
│   └── ...
└── datafeed/
    ├── specs/
    │   ├── openapi.json
    │   └── asyncapi.json
    └── ...

backend/src/trading_api/clients/
├── __init__.py
├── broker_client.py
└── datafeed_client.py

frontend/src/clients/
├── trader-client-broker/
├── trader-client-datafeed/
├── ws-types-broker/
└── ws-types-datafeed/
```

---

## Implementation Phases

## Implementation Phases

### Phase 0: Auto-Discovery Setup (1 day)

**Goal**: Foundation without breaking existing functionality

#### Tasks

- [x] **0.1** Create helper functions in `backend/src/trading_api/shared/utils.py`
  - `discover_modules(base_dir: Path) -> list[str]`
  - `discover_modules_with_websockets(base_dir: Path) -> list[str]`
- [x] **0.2** Create directory structure
  - `mkdir -p backend/src/trading_api/modules/{broker,datafeed}/specs`
  - `mkdir -p backend/src/trading_api/clients`
- [x] **0.3** Update `.gitignore`
  - Add `backend/src/trading_api/modules/*/specs/`
  - Add `backend/src/trading_api/clients/*_client.py`
  - Add `frontend/src/clients/trader-client-*/`
  - Add `frontend/src/clients/ws-types-*/`
- [x] **0.4** Validate selective loading
  - Test: `ENABLED_MODULES=broker make test-module-broker`
  - Test: `ENABLED_MODULES=datafeed make test-module-datafeed`
  - Test: `ENABLED_MODULES=broker,datafeed make test`

**Completion**: All tests pass ✅

---

### Phase 1: Per-Module Spec Generation (3 days)

**Goal**: Generate OpenAPI/AsyncAPI specs per module

#### Tasks: OpenAPI (2 days)

- [x] **1.1** Update `backend/scripts/export_openapi_spec.py`
  - Add `discover_modules()` import
  - Add `module_name: str | None` parameter
  - Implement single-module export logic
  - Implement all-modules loop
  - Output to `modules/{module}/specs/openapi.json`
- [x] **1.2** Update `backend/Makefile`
  - Add `export-openapi-specs` target
  - Update `export-specs` to call new target
- [x] **1.3** Validate generation
  - Run: `make export-openapi-specs`
  - Verify: `ls backend/src/trading_api/modules/*/specs/openapi.json`
  - Check: Both broker and datafeed specs exist

#### Tasks: AsyncAPI (1 day)

- [x] **1.4** Update `backend/scripts/export_asyncapi_spec.py`
  - Add `discover_modules_with_websockets()` import
  - Add `module_name: str | None` parameter
  - Implement single-module export logic
  - Implement all-modules loop
  - Output to `modules/{module}/specs/asyncapi.json`
- [x] **1.5** Update `backend/Makefile`
  - Add `export-asyncapi-specs` target
  - Update `export-specs` to call new target
- [x] **1.6** Validate generation
  - Run: `make export-asyncapi-specs`
  - Verify: `ls backend/src/trading_api/modules/*/specs/asyncapi.json`
  - Check: Both broker and datafeed specs exist

**Completion**: All specs generated ✅

---

### Phase 2: Backend Python Client Generation (3 days)

**Goal**: Type-safe HTTP clients for inter-module communication when running as separate processes

**WHY THIS IS CRITICAL:**
When modules run as separate processes, they can't use direct Python imports. Instead:

```python
# ❌ Won't work in multi-process (different memory space)
from trading_api.modules.datafeed.api import get_symbols

# ✅ HTTP client for inter-process communication
from trading_api.clients.datafeed_client import DatafeedClient
client = DatafeedClient(base_url="http://datafeed-service:8002")
symbols = await client.get_symbols()
```

**USE CASE EXAMPLE:**
Broker module needs to fetch symbols from Datafeed module:

- **Monolith**: Direct import works (same process)
- **Multi-process**: HTTP client required (different processes)

**IMPLEMENTATION APPROACH:**

- **Tool**: Custom Python script (no external code generation tools)
- **Design**: Flat structure with clear naming (`{module}_client.py`)
- **Output**: Thin HTTP client wrappers only, models imported from `trading_api.models.*`
- **Key Constraint**: Models already exist in `backend/src/trading_api/models/` (broker/, market/, common.py)

#### Tasks

- [ ] **2.1** Create custom client generator script
  - Create `backend/scripts/generate_python_clients.py`
  - Parse OpenAPI specs from `modules/{module}/specs/openapi.json`
  - Extract operations (operationId, HTTP method, path, parameters, request/response schemas)
  - Map schema references to existing models in `trading_api.models.*`
  - Generate client classes with async httpx methods
- [ ] **2.2** Create Jinja2 templates
  - Create `backend/scripts/templates/python_client.py.j2`
  - Template generates single file: `{module}_client.py`
  - **Critical**: Import models from `trading_api.models.*` (no model generation)
  - Template includes: client class, async methods, type hints, docstrings
  - **Example imports**: `from trading_api.models import SymbolInfo, QuoteData, PlacedOrder`
- [ ] **2.3** Implement generator logic
  - Auto-discover modules with OpenAPI specs
  - For each module, generate `src/trading_api/clients/{module}_client.py`
  - Create `src/trading_api/clients/__init__.py` with exports
  - **File structure**: Flat, no subdirectories per client
  - **Naming convention**: `broker_client.py`, `datafeed_client.py`
- [ ] **2.4** Create Makefile target
  - Add `generate-python-clients` target to `backend/Makefile`
  - Command: `poetry run python scripts/generate_python_clients.py`
  - Add to `export-specs` dependency chain
- [ ] **2.5** Validate generation
  - **Cleanup first**: `rm -f backend/src/trading_api/clients/*_client.py` (remove old files)
  - Run: `make generate-python-clients`
  - Verify files exist: `ls src/trading_api/clients/{broker,datafeed}_client.py`
  - **Critical check**: Clients import from `trading_api.models` (NOT local models)
  - **Critical check**: Clients have async HTTP methods (using httpx)
  - Test import: `from trading_api.clients.datafeed_client import DatafeedClient`
  - Test type checking: `poetry run mypy src/trading_api/clients/`
- [ ] **2.6** Integration test - Multi-process communication
  - Start datafeed service: `ENABLED_MODULES=datafeed uvicorn trading_api.main:app --port 8002`
  - Start broker service: `ENABLED_MODULES=broker uvicorn trading_api.main:app --port 8001`
  - Test: Broker uses `DatafeedClient(base_url="http://localhost:8002")` to call datafeed
  - Verify: HTTP communication works, models serialize/deserialize correctly
  - Verify: Type safety maintained across process boundary

**Completion**: HTTP clients generated, reuse existing models, multi-process communication validated ✅

---

### Phase 3: Frontend Multi-Client Generation (2 days)

**Goal**: Tree-shakeable TypeScript clients per module (import only broker OR datafeed, not both)

**WHY THIS IS CRITICAL:**
Frontend needs to call different module services independently:

```typescript
// ✅ Import only what you need - smaller bundle size
import { BrokerApi } from "@/clients/trader-client-broker";
import { DatafeedApi } from "@/clients/trader-client-datafeed";

// Broker service at http://broker-service:8001
const brokerApi = new BrokerApi({ basePath: "http://broker-service:8001" });

// Datafeed service at http://datafeed-service:8002
const datafeedApi = new DatafeedApi({
  basePath: "http://datafeed-service:8002",
});
```

**BENEFIT**: TradingView chart only needs datafeed client, not broker → smaller bundle

#### Tasks

- [ ] **3.1** Update `frontend/scripts/generate-openapi-client.sh`
  - Loop over `../backend/src/trading_api/modules/*/specs/openapi.json`
  - Extract module name from directory path
  - Generate to `src/clients/trader-client-{module}/`
  - Use `typescript-axios` generator
- [ ] **3.2** Update `frontend/scripts/generate-asyncapi-types.sh`
  - Loop over `../backend/src/trading_api/modules/*/specs/asyncapi.json`
  - Extract module name from directory path
  - Generate to `src/clients/ws-types-{module}/`
  - Use existing type generation logic
- [ ] **3.3** Update `frontend/Makefile`
  - Update `generate-clients` target
  - Ensure both scripts run
- [ ] **3.4** Update `frontend/src/plugins/apiAdapter.ts`
  - Import from `trader-client-broker`
  - Import from `trader-client-datafeed`
  - Update configuration per module
- [ ] **3.5** Validate generation
  - Run: `cd frontend && make generate-clients`
  - Verify: `ls src/clients/trader-client-*/`
  - Verify: `ls src/clients/ws-types-*/`
  - Test: `npm run type-check`

**Completion**: TypeScript clients generated, type-check passes ✅

---

### Phase 4: Build Pipeline Integration (1 day)

**Goal**: Root-level orchestration

#### Tasks

- [ ] **4.1** Update `project.mk`
  - Add `export-specs-all` target (calls `cd backend && make export-specs`)
  - Add `generate-python-clients` target (calls `cd backend && make generate-python-clients`)
  - Add `generate-frontend-clients` target (calls `cd frontend && make generate-clients`)
  - Add `generate-clients-all` target (depends on both generation targets)
- [ ] **4.2** Validate pipeline
  - Run: `make -f project.mk export-specs-all`
  - Run: `make -f project.mk generate-clients-all`
  - Verify: All specs and clients generated
- [ ] **4.3** Update help target
  - Document new targets in `project.mk help`

**Completion**: Full pipeline works end-to-end ✅

---

### Phase 5: CI/CD Pipeline Updates (1 day)

**Goal**: Automated spec generation in CI

#### Tasks

- [ ] **5.1** Update `.github/workflows/ci.yml`
  - Add `backend-export-specs` job
  - Add artifact upload for `backend/specs/*.json`
  - Add `backend-generate-python-clients` job (depends on export)
  - Add `frontend-generate-clients` job (depends on export)
  - Download artifacts in dependent jobs
- [ ] **5.2** Validate CI
  - Push to feature branch
  - Verify: Specs uploaded as artifacts
  - Verify: Clients generated successfully
  - Verify: Type checks pass

**Completion**: CI pipeline generates all clients ✅

---

## Migration Notes

### Breaking Changes

| Component       | Old                       | New                                              |
| --------------- | ------------------------- | ------------------------------------------------ |
| Backend specs   | `backend/openapi.json`    | `backend/src/trading_api/modules/*/specs/*.json` |
| Backend specs   | `backend/asyncapi.json`   | `backend/src/trading_api/modules/*/specs/*.json` |
| Backend clients | N/A (direct imports)      | `trading_api.clients.{module}_client`            |
| Frontend REST   | `trader-client-generated` | `trader-client-{module}`                         |
| Frontend WS     | `ws-types-generated`      | `ws-types-{module}`                              |

### Rollout

Single PR with all changes (clean break, already in feature branch)

---

## Validation Checklist

Before merge:

- [ ] `make -f project.mk export-specs-all` works
- [ ] `make -f project.mk generate-clients-all` works
- [ ] Backend tests pass: `cd backend && make test`
- [ ] Frontend tests pass: `cd frontend && make test`
- [ ] Type checks pass: `cd frontend && npm run type-check`
- [ ] CI pipeline runs successfully
- [ ] Documentation updated (ARCHITECTURE.md, CLIENT-GENERATION.md, MAKEFILE-GUIDE.md)

---

**Last Updated**: October 30, 2025
