# Reference

## Architecture & Codebase

**Contract-First Full-Stack Modular**: Backend Pydantic models → OpenAPI/AsyncAPI specs → TypeScript clients → Frontend types

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

**Modular Monorepo Principles**: Each module = decoupled microservice. Enforcement rules per `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md`.

**Module Development**: Detailed at `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md`. WebSocket router patterns: `backend/docs/BACKEND_WEBSOCKETS.md`.

**Frontend Service Pattern**: Detailed at `docs/ARCHITECTURE.md` §"Mapper Layer Architecture" and `docs/CLIENT-GENERATION.md` §"Data Mappers".

---

### Key File Locations

| Purpose                   | Location                                                    |
| ------------------------- | ----------------------------------------------------------- |
| Backend models (Pydantic) | `backend/src/trading_api/models/{domain}/`                  |
| Module implementations    | `backend/src/trading_api/modules/{name}/`                   |
| Provider implementations  | `backend/src/trading_api/providers/{name}/`                 |
| Frontend type mappers     | `frontend/src/plugins/mappers.ts`                           |
| WebSocket adapter         | `frontend/src/plugins/wsAdapter.ts`                         |
| Generated REST clients    | `frontend/src/clients_generated/trader-client-{module}_v1/` |
| Generated WS types        | `frontend/src/clients_generated/ws-types-{module}_v1/`      |
| Test fixtures             | `backend/tests/conftest.py`, `frontend/src/test-setup.ts`   |
| CLI permissions           | `.claude/settings.json`, `.claude/settings.local.json`      |
| Skill glossaries          | `.claude/skills/{category}/SKILL.md`                        |

### Documentation Navigation

Use `docs/DOCUMENTATION-GUIDE.md` as your map:

| Task                       | Primary Docs                                                                     |
| -------------------------- | -------------------------------------------------------------------------------- |
| Backend module dev         | `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md`                                   |
| WebSocket features         | `backend/docs/BACKEND_WEBSOCKETS.md` + `frontend/docs/WEBSOCKET-ARCHITECTURE.md` |
| Authentication             | `backend/docs/AUTHENTICATION.md`                                                 |
| Provider/capability system | `backend/docs/PROVIDER-SYSTEM.md`                                                |
| Client generation          | `backend/docs/SPECS_AND_CLIENT_GEN.md` + `docs/CLIENT-GENERATION.md`             |
| Testing strategy           | `docs/TESTING.md` + `backend/docs/BACKEND_TESTING.md`                            |
