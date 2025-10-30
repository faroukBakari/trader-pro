# API Spec Refactoring - Per-Module Specs

**Status**: In Progress  
**Started**: October 30, 2025  
**Duration**: 11 days

## Goal

Per-module OpenAPI/AsyncAPI specs with auto-discovery:

- Self-contained specs per module
- Inter-module HTTP communication (Python clients)
- Frontend tree-shaking (module-specific imports)
- Microservice-ready architecture

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
├── broker_client/
└── datafeed_client/

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
  - Add `backend/src/trading_api/clients/*_client/`
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

**Goal**: Type-safe inter-module HTTP clients

#### Tasks

- [ ] **2.1** Create `backend/scripts/generate-python-client.sh`
  - Accept MODULE_NAME parameter
  - Use OpenAPI Generator Docker image
  - Output to `src/trading_api/clients/{module}_client/`
  - Set package name to `{module}_client`
- [ ] **2.2** Make script executable
  - `chmod +x backend/scripts/generate-python-client.sh`
- [ ] **2.3** Update `backend/Makefile`
  - Add `generate-python-clients` target
  - Depend on `export-openapi-specs`
  - Loop over `specs/openapi-*.json` files
  - Extract module name and call generation script
- [ ] **2.4** Validate generation
  - Run: `make generate-python-clients`
  - Verify: `ls src/trading_api/clients/*/`
  - Check: Both broker_client and datafeed_client exist
  - Test import: `from trading_api.clients.datafeed_client import DefaultApi`

**Completion**: Python clients generated and importable ✅

---

### Phase 3: Frontend Multi-Client Generation (2 days)

**Goal**: Tree-shakeable TypeScript clients per module

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

| Component     | Old                       | New                                              |
| ------------- | ------------------------- | ------------------------------------------------ |
| Backend specs | `backend/openapi.json`    | `backend/src/trading_api/modules/*/specs/*.json` |
| Backend specs | `backend/asyncapi.json`   | `backend/src/trading_api/modules/*/specs/*.json` |
| Frontend REST | `trader-client-generated` | `trader-client-{module}`                         |
| Frontend WS   | `ws-types-generated`      | `ws-types-{module}`                              |

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
