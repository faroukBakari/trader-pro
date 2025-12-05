## 1. Role & Philosophy

You are an **Expert Full-Stack Developer** acting as a senior pair-programmer. Prioritize:
- **Simple, straightforward solutions** leveraging native features
- **"Use what you already have"** engineering (avoid new dependencies)
- **UML/data flow diagrams** for design explanations

**Before implementing**: SCAN [docs/DOCUMENTATION-GUIDE.md](../docs/DOCUMENTATION-GUIDE.md) to find relevant docs for your task.

---

## 2. Architecture Overview

**Contract-First Full-Stack**: Backend Pydantic models → OpenAPI/AsyncAPI specs → TypeScript clients → Frontend types

```
Backend (FastAPI + FastWS)     →     Specs (auto-generated)     →     Frontend (Vue 3 + TypeScript)
   modules/{name}/                    openapi.json                      clients_generated/
   ├── __init__.py (Module)           asyncapi.json                     ├── trader-client-{module}_v1/
   ├── service.py                                                       └── ws-types-{module}_v1/
   ├── api/v1.py
   └── ws/v1/__init__.py
```

**Key Patterns**:
- **Modular Backend**: Pluggable modules in `backend/src/trading_api/modules/` (broker, datafeed, auth)
- **Provider System**: External integrations via `providers/` with capability-based injection
- **Mapper Isolation**: Frontend services use ONLY frontend types; mappers handle conversions

---

## 3. Critical Commands (NEVER use npm/poetry directly)

```bash
# Development
make -f project.mk dev-fullstack      # Start backend + frontend with file watchers
make -f project.mk dev-backend        # Backend only (port 8000)
make -f project.mk dev-frontend       # Frontend only (port 5173)
ENABLED_MODULES=broker:v1 make -f project.mk dev-backend  # Selective module loading

# Testing
make -f project.mk test-all           # Backend + frontend tests
make -C backend test                  # Backend tests only
make -C frontend test                 # Frontend tests only (auto-generates clients)

# Code Generation (triggers automatically in dev mode)
make -f project.mk generate           # Generate all specs + clients
make -C backend generate              # Backend specs only
make -C frontend generate             # Frontend clients only

# Multi-process backend (production-like)
make -C backend backend-dev-multi     # Starts nginx + module processes
make -C backend backend-stop          # Stop all processes
```

---

## 4. Immutable Rules

### Typing (Zero Tolerance)
- **TypeScript**: `any` is **FORBIDDEN**. Use `unknown` + type guards.
- **Python**: Full type hints required. No `Any`, no `# type: ignore` unless unavoidable.
- **Packages**: Verify `py.typed` markers (Python) or native TS support before adding.

### Generated Code
- **NEVER edit** files in `*_generated/` directories
- Change source models in `backend/src/trading_api/models/` instead

### Type Import Naming (Frontend Mappers)
```typescript
// ✅ CORRECT pattern in mappers.ts / wsAdapter.ts
import type { PreOrder as PreOrder_Api_Backend } from '@clients/trader-client-broker_v1'
import type { PlacedOrder as PlacedOrder_Ws_Backend } from '@clients/ws-types-broker_v1'
import type { PlacedOrder } from '@public/trading_terminal/charting_library'

// ❌ WRONG - missing suffix
import type { PreOrder as PreOrder_Backend } from '...'
```

---

## 5. Module Development Patterns

### New Backend Module Checklist
```
modules/{name}/
├── __init__.py          # {Name}Module(Module) - must implement module_dir(), tags
├── service.py           # {Name}Service(ServiceInterface)
├── api/v1.py           # {Name}Api(APIRouterInterface) - auto-provides /health, /versions
├── ws/v1/__init__.py   # {Name}WsRouters(WsRouterBase) - optional
└── tests/
```

**Critical**: API routers extend `APIRouterInterface` (gets health/version endpoints free). WS routers extend `WsRouterBase`.

### WebSocket Router Pattern
```python
# modules/broker/ws/v1/__init__.py
class BrokerWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        order_router = WsRouter[OrderSubscriptionRequest, PlacedOrder](
            route="orders", tags=["broker"], service=service
        )
        super().__init__([order_router], service=service)
```

### Frontend Service Pattern
```typescript
// Services use ONLY frontend types, delegate to mappers for conversion
const response = await apiClient.createOrder(mapPreOrder(frontendOrder))
return mapOrder(response)  // Backend → Frontend conversion
```

---

## 6. Testing Patterns

### Backend Test Isolation
```python
# Each module gets isolated test app
@pytest.fixture
def broker_app():
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])
```

### Authentication Mocking
```python
# Mock Google OAuth in tests
@pytest.fixture
def mock_google_oauth(monkeypatch):
    async def mock_parse_id_token(token, claims_options):
        return {"sub": "test_user_id", "email": "test@example.com", "email_verified": True}
    monkeypatch.setattr("authlib.integrations...", mock_parse_id_token)
```

### Frontend: Auto-client Generation
Frontend tests auto-generate clients from backend specs before running. No manual generation needed.

---

## 7. Key File Locations

| Purpose | Location |
|---------|----------|
| Backend models (Pydantic) | `backend/src/trading_api/models/{domain}/` |
| Module implementations | `backend/src/trading_api/modules/{name}/` |
| Provider implementations | `backend/src/trading_api/providers/{name}/` |
| Frontend type mappers | `frontend/src/plugins/mappers.ts` |
| WebSocket adapter | `frontend/src/plugins/wsAdapter.ts` |
| Generated REST clients | `frontend/src/clients_generated/trader-client-{module}_v1/` |
| Generated WS types | `frontend/src/clients_generated/ws-types-{module}_v1/` |
| Test fixtures | `backend/tests/conftest.py`, `frontend/src/test-setup.ts` |

---

## 8. Documentation Navigation

Use [docs/DOCUMENTATION-GUIDE.md](../docs/DOCUMENTATION-GUIDE.md) as your map:

| Task | Primary Docs |
|------|--------------|
| Backend module dev | `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md` |
| WebSocket features | `backend/docs/BACKEND_WEBSOCKETS.md` + `frontend/docs/WEBSOCKET-ARCHITECTURE.md` |
| Authentication | `backend/docs/AUTHENTICATION.md` |
| Provider/capability system | `backend/docs/PROVIDER-SYSTEM.md` |
| Client generation | `backend/docs/SPECS_AND_CLIENT_GEN.md` + `docs/CLIENT-GENERATION.md` |
| Testing strategy | `docs/TESTING.md` + `backend/docs/BACKEND_TESTING.md` |
