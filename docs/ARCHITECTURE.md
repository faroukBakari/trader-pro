# Trading Pro - Architecture Documentation

**Version**: 4.1.0 (Modular Architecture)
**Last Updated**: November 30, 2025
**Status**: ✅ Production Ready

## Overview

Trading Pro is a modern full-stack trading platform built with **FastAPI** backend and **Vue.js** frontend, featuring RESTful API (OpenAPI) and real-time WebSocket streaming (AsyncAPI). The architecture is centered around **type safety**, **code generation**, and **test-driven development** to maintain coherence across the stack.

## Core Architectural Principles

### 1. Contract-First Development (Code Generation as Foundation)

The entire system is built on **specification-driven development** where API contracts (OpenAPI/AsyncAPI) drive automatic client generation:

```
Backend Models (Pydantic) → OpenAPI/AsyncAPI Specs → TypeScript Clients → Frontend Types
```

This ensures:

- **Single Source of Truth**: Backend models define the contract
- **Compile-Time Safety**: Breaking changes caught during build
- **Zero Drift**: Frontend and backend types always synchronized
- **Automatic Updates**: Client regeneration on spec changes

### 2. Type-Safe Data Flow (End-to-End Type Coherence)

```
Python (Pydantic) ←→ JSON (OpenAPI/AsyncAPI) ←→ TypeScript (Generated) ←→ Vue Components
```

**Critical Pattern**: Mapper layer isolates type transformations

- Backend types confined to `mappers.ts` (never in services)
- Services work exclusively with frontend types
- Breaking changes detected at compile time, not runtime

### 3. Test-Driven Architecture (TDD at Every Layer)

```
Unit Tests (Fast) → Integration Tests (Medium) → E2E Tests (Slow)
    ↓                       ↓                          ↓
Backend (pytest)     Frontend+Backend         Full Stack (Playwright)
Frontend (Vitest)    (Contract Tests)         (User Workflows)
```

**Key Design**: Independent test suites (no cross-dependencies) enable parallel CI/CD execution.

### 4. Real-Time Coherence (WebSocket State Synchronization)

```
Backend Service → FastWSAdapter → WebSocketBase (Singleton) → Multiple Clients → UI Updates
```

**Critical**: Topic-based subscription with reference counting ensures:

- Automatic resource cleanup (last unsubscribe stops data generation)
- Single WebSocket connection shared across all clients
- Server-confirmed subscriptions (no race conditions)

### 5. Incremental Development (Fallback-Driven Design)

Every service has dual implementations:

- **Fallback Client**: Mock implementation for offline development
- **Real Client**: Generated from backend API
- **Smart Adapter**: Automatically switches based on backend availability

This enables:

- Frontend development without backend
- Backend development without frontend
- Graceful degradation in production

### 6. Multi-Module Monitoring (Independent Module Health)

The system provides **per-module health monitoring** for independent service observability:

```
Backend Modules (broker, datafeed) → Health/Versions Endpoints → ApiAdapter Registry → Per-Module UI Cards
```

**Key Design Decisions:**

- **No Overall Health**: System health = independent module health (no aggregation)
- **Static Discovery**: Module list hardcoded in `ApiAdapter` (no runtime discovery)
- **AsyncAPI Detection**: WebSocket support detected via `WsAdapter.getModules()`
- **Error Isolation**: Individual module failures don't block other modules
- **Response Time Tracking**: Per-module performance metrics

**UI Architecture:**

```
ApiStatus.vue (Grid Layout)
    ↓ queries
ApiService.getAllModulesHealth() → Map<string, ModuleHealth>
    ↓ delegates to
ApiAdapter.getModuleHealth(name) → Parallel queries per module
    ↓ routes to
Module-specific API clients (broker, datafeed)
```

**Benefits:**

- ✅ Individual module failures visible
- ✅ Partial system degradation supported
- ✅ Per-module documentation links (OpenAPI/AsyncAPI)
- ✅ Independent module versioning displayed

### 7. Authentication & Authorization (Stateless JWT)

The system implements **cookie-based JWT authentication** with Google OAuth integration:

```
Google OAuth → Backend Auth Module → JWT Access Token (Cookie) → Stateless Middleware → Protected Endpoints
```

**Key Design Decisions:**

- **Cookie-Based Sessions**: HttpOnly cookies for XSS protection
- **Stateless Validation**: Middleware validates JWT with public key only (no database)
- **Modular Auth**: Auth module follows standard modular pattern (optional)
- **WebSocket Authentication**: Automatic via cookies (no query params)
- **Refresh Token Rotation**: Device fingerprinting for security
- **Service-Based Frontend**: No Pinia store, authentication in service layer

**Authentication Flow:**

```
User Login (Google OAuth)
    ↓
Auth Module validates token, creates JWT
    ↓
Set access_token cookie (HttpOnly, Secure, SameSite=Strict)
    ↓
Frontend router guard checks auth via API introspection
    ↓
Protected REST/WebSocket endpoints validate cookie
```

**Security Architecture:**

- **Frontend**: Service-based auth (`authService.ts`), stateless guards, no manual token handling
- **Backend**: Shared middleware (`shared/middleware/auth.py`), public key validation, no DB queries
- **WebSocket**: Automatic cookie authentication in handshake, same security as REST

**Implementation Details:**

- **Backend Tests**: 92 tests (19 repository + 14 service + 21 middleware + 18 API + 10 integration + 10 broker/datafeed auth)
- **Frontend Tests**: Service unit tests + integration tests
- **Test Coverage**: 100% passing (strict mypy + pyright compliance)
- **Storage**: In-memory repositories (MVP), PostgreSQL/Redis migration path documented
- **JWT Algorithm**: RS256 (4096-bit RSA keys)
- **Token Expiry**: Access token 5 minutes, refresh token 7 days

**Benefits:**

- ✅ XSS Protection (HttpOnly cookies)
- ✅ CSRF Protection (SameSite=Strict)
- ✅ Stateless middleware (horizontally scalable)
- ✅ Independent auth module (can be disabled)
- ✅ Type-safe JWT payload (`UserData` model)
- ✅ Automatic WebSocket auth (no frontend code needed)
- ✅ Comprehensive test coverage (100% passing)
- ✅ Production-ready security (device fingerprinting, token rotation)

See [AUTHENTICATION.md](./AUTHENTICATION.md) for complete implementation details.

### 8. Provider/Capability System (Pluggable External Integrations)

The backend implements a **pluggable provider architecture** for decoupling service logic from external implementations:

```
Services declare capabilities → ProviderRegistry discovers → AppFactory injects → Services use via interface
```

**Key Design Decisions:**

- **Capability-Based**: Services declare what they need (auth, broker, datafeed), not which provider
- **Auto-Discovery**: Providers automatically discovered from `providers/` directory
- **Lazy Loading**: Provider instances created only when needed
- **Fail-Fast**: Missing providers detected at app startup, not production
- **Type-Safe**: Capability interfaces ensure compile-time correctness
- **Multi-Capability**: Single provider can implement multiple capabilities (e.g., IBKR auth + trading)

**Provider Flow:**

```
Application Startup
    ↓
ModuleRegistry.auto_discover() + ProviderRegistry.auto_discover()
    ↓
AppFactory._resolve_capabilities() (static analysis)
    ↓
ProviderRegistry.get_providers(required_capabilities)
    ↓
ModuleRegistry.get_modules(providers=[...])
    ↓
Service._resolve_capabilities() (fail-fast validation)
    ↓
Application Ready
```

**Architecture Components:**

- **CapabilitySpec**: Type-safe capability declaration (`name`, `version`)
- **Provider ABC**: Base class with `capabilities()`, lifecycle hooks
- **Capability Interfaces**: Contracts (e.g., `AuthCapability.verify_token()`)
- **ProviderRegistry**: Auto-discovery and instance management
- **Per-Provider Config**: Pydantic models with env variable auto-loading

**Current Implementations:**

- ✅ GoogleProvider (AuthCapability) - Google OAuth authentication
- 🔄 LocalProvider (AuthCapability) - Email/password (future)
- 🔄 IBKRProvider (AuthCapability + BrokerCapability) - Interactive Brokers (future)

**Benefits:**

- ✅ Multiple auth providers simultaneously (Google + local + IBKR)
- ✅ Easy testing (mock providers instead of external APIs)
- ✅ Clean separation (service logic vs implementation details)
- ✅ Independent provider lifecycle (startup/shutdown hooks)
- ✅ Type-safe dependency injection
- ✅ O(1) cached provider lookups
- ✅ Connection pooling and resource sharing

**Example: AuthService using provider**

```python
class AuthService(ServiceInterface):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    @property
    def auth_provider(self) -> AuthCapability:
        return self._get_capability_provider("auth")

    async def authenticate_user(self, token: str):
        claims = await self.auth_provider.verify_token(token)
        # Service logic continues...
```

See [backend/docs/PROVIDER-SYSTEM.md](../backend/docs/PROVIDER-SYSTEM.md) for complete developer guide.

---

## Technology Stack

### Backend

- **Framework**: FastAPI 0.104+ (ASGI async)
- **WebSocket**: FastWS 0.1.7 (AsyncAPI documented)
- **Runtime**: Python 3.11 + Uvicorn
- **Package Mgmt**: Poetry
- **Type Safety**: MyPy + Pydantic
- **Testing**: pytest + pytest-asyncio + httpx TestClient

### Frontend

- **Framework**: Vue 3 + Composition API + TypeScript
- **Build**: Vite 7+ with HMR
- **Package Mgmt**: npm (Node.js 20+)
- **State**: Pinia stores
- **Testing**: Vitest + Vue Test Utils
- **Charts**: TradingView Advanced Charting Library

### DevOps

- **CI/CD**: GitHub Actions (parallel jobs)
- **Build**: Makefile orchestration (NEVER use npm/poetry directly)
- **Quality**: Pre-commit hooks (Black, isort, ESLint, Prettier)
- **Development**: VS Code multi-root workspace

---

## Code Generation Pipeline (Central Architecture Pillar)

Code generation is the **foundational mechanism** that maintains type coherence across the entire stack.

### 1. Backend Spec Generation (Offline Mode)

**Command**: `make generate` (backend - unified generation for all specs and clients)

**Process Flow**:

```
FastAPI App + Pydantic Models → Export Script → openapi.json
FastWS App + AsyncAPI Decorator → Export Script → asyncapi.json
```

**Key Features**:

- No server startup required (< 1 second execution)
- Script-based extraction from app configuration
- Automatic model introspection via Pydantic
- Generates OpenAPI 3.0 and AsyncAPI 2.4.0 specs

### 2. Frontend Client Generation (Automatic)

**Generation Targets**:

| Command                        | Input Spec            | Output Location                                         | Artifacts Generated                              |
| ------------------------------ | --------------------- | ------------------------------------------------------- | ------------------------------------------------ |
| `make generate-openapi-client` | backend/openapi.json  | frontend/src/clients_generated/trader-client-generated/ | TypeScript interfaces, API client classes        |
| `make generate-asyncapi-types` | backend/asyncapi.json | frontend/src/clients_generated/ws-types-generated/      | WebSocket message types, subscription interfaces |

**Process Flow**:

```
OpenAPI Spec → OpenAPI Generator Tool → TypeScript Client Code
AsyncAPI Spec → Custom Type Extractor → TypeScript Interfaces
```

**Type Alignment**:

- Python Pydantic models → JSON Schema → TypeScript interfaces
- Enum values preserved across languages
- Optional fields mapped to TypeScript optional properties
- Discriminated unions for polymorphic types

### 3. Module-Level Spec Generation

**New in Modular Architecture**: Each module generates its own OpenAPI/AsyncAPI specifications in addition to the global specs.

**Process**:

```
Module.gen_module_specs_and_clients()
    ├─→ Generate module OpenAPI spec
    │   └─→ modules/{module_name}/specs_generated/openapi.json
    ├─→ Generate module AsyncAPI spec (if WebSocket routes exist)
    │   └─→ modules/{module_name}/specs_generated/asyncapi.json
    └─→ Generate Python client for module
        └─→ modules/{module_name}/specs_generated/client_generated.py
```

**Module Specs vs Global Specs**:

| Type             | Location                                        | Purpose                      | Scope               |
| ---------------- | ----------------------------------------------- | ---------------------------- | ------------------- |
| **Module Specs** | `modules/{name}/specs_generated/`               | Module-specific API contract | Single module only  |
| **Global Specs** | `backend/openapi.json`, `backend/asyncapi.json` | Complete system API          | All enabled modules |

**Key Features**:

- **Module Isolation**: Each module's spec can be versioned and deployed independently
- **Automatic Aggregation**: Global specs combine all enabled modules
- **Python Client Generation**: Each module generates its own Python client for inter-module communication
- **Automatic Regeneration**:
  - Backend restart triggers module spec regeneration
  - Frontend client regeneration triggered by global spec file changes
  - Watch system in `dev-fullstack` mode handles automatic updates

**When Module Specs Are Generated**:

1. **On module initialization** (first import)
2. **On backend restart** (development mode)
3. **Manually**: `make generate` (backend root)

See [backend/docs/SPECS_AND_CLIENT_GEN.md](../backend/docs/SPECS_AND_CLIENT_GEN.md) for complete generation guide.

### 4. File Watchers (Development Mode)

**Command**: `make dev-fullstack` (root)

**Watch Loop Flow**:

```
File System Monitor → Detect Spec Change → Trigger Regeneration → HMR Update
        ↓                    ↓                      ↓                  ↓
  Watch specs      openapi.json or      Run generator       Frontend reloads
                   asyncapi.json        command             with new types
```

**Monitored Files**:

- `backend/openapi.json` → Triggers REST client regeneration
- `backend/asyncapi.json` → Triggers WebSocket types regeneration

**Developer Experience**:

- Change backend model → Spec auto-regenerates → Frontend types update → Hot reload applies
- Average update cycle: 2-3 seconds
- No manual intervention required

### 5. Type Safety Enforcement

**Critical Rule**: Backend types NEVER imported directly in services

**Type Isolation Architecture**:

```
Services Layer (Frontend Types Only)
        ↑
        │ Uses frontend types exclusively
        │
Mappers Layer (Type Transformations)
        ↑
        │ Imports both backend and frontend types
        │
Generated Clients (Backend Types)
```

**Benefits of Isolation**:

- **Compile-Time Detection**: Breaking changes fail TypeScript compilation
- **Single Responsibility**: Mappers own all type transformations
- **Testability**: Services mock frontend types, not backend types
- **Maintainability**: Type changes localized to mapper layer

### 6. CI/CD Integration

**Pipeline Flow**:

```
Backend Job → Export Specs → Frontend Job → Generate Clients → Type Check
     ↓              ↓              ↓                ↓                ↓
  Run tests    openapi.json   Install deps    TypeScript gen    Validate types
              asyncapi.json                                     (fails on mismatch)
```

**Job Dependencies**:

- Frontend job depends on backend completion (specs availability)
- Type check runs after client generation
- Breaking changes detected before merge

**Quality Gates**:

- Backend tests must pass
- Specs must generate successfully
- Frontend types must compile
- All tests must pass with new types

**Guarantee**: Pull requests with breaking changes fail type-check step.

---

## Component Architecture

### Backend Structure

```
src/trading_api/
├── main.py              # Minimal entrypoint - calls create_app()
├── app_factory.py       # Application factory with module composition
├── models/              # Centralized Pydantic models (topic-based organization)
│   ├── common.py        # Shared types (BaseApiResponse, SubscriptionUpdate, etc.)
│   ├── health.py        # Health check models
│   ├── versioning.py    # API version models
│   ├── broker/          # Broker business domain models
│   │   ├── common.py       # Shared broker models (SuccessResponse)
│   │   ├── orders.py       # Order models (REST + WebSocket)
│   │   ├── positions.py    # Position models (REST + WebSocket)
│   │   ├── executions.py   # Execution models (REST + WebSocket)
│   │   ├── account.py      # Account/equity models (REST + WebSocket)
│   │   ├── connection.py   # Connection status models (WebSocket)
│   │   └── leverage.py     # Leverage models (REST)
│   └── market/          # Market data business domain models
│       ├── bars.py         # Bar/OHLC models (REST + WebSocket)
│       ├── quotes.py       # Quote models (REST + WebSocket)
│       ├── instruments.py  # Symbol/instrument models (REST)
│       ├── search.py       # Search models (REST)
│       └── configuration.py # Datafeed config models (REST)
├── shared/              # Always-loaded shared infrastructure
│   ├── module_interface.py  # Module Protocol definition
│   ├── module_registry.py   # Module registry for dynamic composition
│   ├── api/                 # Shared REST endpoints
│   │   ├── health.py        # HealthApi class - Health checks
│   │   └── versions.py      # VersionApi class - API versioning
│   ├── ws/                  # Shared WebSocket infrastructure
│   │   ├── ws_router.py         # WsRouteFeature, WsRouterBase, WsRouteService Protocol
│   │   └── generic_route.py     # WsRouter generic implementation
│   ├── plugins/
│   │   └── fastws_adapter.py  # FastWS integration adapter
│   └── tests/
│       └── conftest.py      # Shared test fixtures
└── modules/             # Pluggable feature modules
    ├── datafeed/        # Market data module
    │   ├── __init__.py     # DatafeedModule class (implements Module Protocol)
    │   ├── service.py      # DatafeedService (implements WsRouteService Protocol)
    │   ├── api.py          # DatafeedApi class - Market data REST endpoints
    │   ├── ws/             # WebSocket routers using direct generic types
    │   │   └── v1/         # Version-specific routers
    │   │       └── __init__.py  # DatafeedWsRouters (bars, quotes)
    │   └── tests/          # Module-specific tests
    │       ├── conftest.py
    │       └── test_ws_datafeed.py
    └── broker/          # Trading operations module
        ├── __init__.py     # BrokerModule class (implements Module Protocol)
        ├── service.py      # BrokerService (implements WsRouteService Protocol)
        ├── api.py          # BrokerApi class - Broker REST endpoints
        ├── ws/             # WebSocket routers using direct generic types
        │   └── v1/         # Version-specific routers
        │       └── __init__.py  # BrokerWsRouters (orders, positions, etc.)
        └── tests/          # Module-specific tests
            ├── conftest.py
            ├── test_api_broker.py
            └── test_ws_broker.py

tests/
├── conftest.py          # Root test configuration
├── test_import_boundaries.py  # Import boundary enforcement
└── integration/         # Cross-module integration tests
    ├── conftest.py
    ├── test_broker_datafeed_workflow.py
    ├── test_full_stack.py
    └── test_module_isolation.py

shared/tests/
├── conftest.py          # Shared test factory
├── test_api_health.py   # Health endpoint tests
└── test_api_versioning.py  # Versioning API tests
```

### Backend Manager (Multi-Process Orchestration)

**Component**: `backend/scripts/backend_manager.py` (1,571 lines)

**Purpose**: Orchestrates multi-process backend deployment with nginx gateway and comprehensive process lifecycle management.

#### Key Features

**1. Configuration-Driven Deployment**

- Reads `dev-config.yaml` for server definitions
- Generates nginx configuration automatically
- Validates module assignments and port allocation
- Supports flexible WebSocket routing strategies

**2. Process Management**

- Tracks PIDs for all servers and nginx in `.local/*.pid` files
- Graceful startup/shutdown sequences
- Crash detection and status monitoring
- Automatic cleanup on failures

**3. Nginx Integration**

- Auto-generates `nginx-dev.conf` from configuration
- Manages nginx lifecycle (install, start, stop, reload)
- Configures REST API routing by URL path prefix
- Handles WebSocket upgrade headers and routing
- Supports both path-based and query-param routing

**4. Logging & Monitoring**

- Per-server log files in `.local/logs/{server}.log`
- Nginx access and error logs
- Unified log tailing with `make backend-logs`
- Process status inspection with `make backend-status`

#### Commands (via Makefile)

```bash
# Development Workflow
make backend-dev-multi    # Start all processes + nginx
make backend-stop         # Stop all processes gracefully
make backend-restart      # Restart all processes
make backend-status       # Show process status (running/stopped)

# Log Management
make backend-logs         # Tail all server logs
make backend-logs-nginx   # Tail nginx logs only

# Configuration Management
make backend-gen-nginx    # Regenerate nginx.conf from dev-config.yaml
```

#### Architecture Components

```
Backend Manager (backend_manager.py)
    ├─→ Configuration Parser (dev-config.yaml)
    │   ├─ Server definitions (modules, ports, instances)
    │   ├─ Nginx gateway config (port, workers)
    │   └─ WebSocket routing strategy
    │
    ├─→ Nginx Config Generator
    │   ├─ Upstream server blocks
    │   ├─ Location-based REST routing
    │   ├─ WebSocket upgrade configuration
    │   └─ Proxy headers and timeouts
    │
    ├─→ Process Manager
    │   ├─ PID file tracking (.local/*.pid)
    │   ├─ Uvicorn server spawning
    │   ├─ Nginx process control
    │   └─ Graceful shutdown handling
    │
    └─→ Monitoring & Logging
        ├─ Server log files (.local/logs/)
        ├─ Nginx log files (.local/logs/nginx-*.log)
        ├─ Process status checks
        └─ Health check integration
```

#### File Structure

```
backend/
├── dev-config.yaml           # User-editable deployment configuration
├── nginx-dev.conf            # Auto-generated nginx config (DO NOT EDIT)
├── scripts/
│   ├── backend_manager.py    # Main orchestration script
│   └── install_nginx.py      # Nginx installation helper
└── .local/                   # Runtime files (git-ignored)
    ├── *.pid                 # Process ID tracking
    ├── logs/                 # Log files
    │   ├── broker.log
    │   ├── datafeed.log
    │   ├── nginx-access.log
    │   └── nginx-error.log
    └── temp/                 # Nginx temporary directories
```

#### Integration with Module System

The Backend Manager seamlessly integrates with the modular architecture:

- **Module-to-Server Mapping**: Assigns modules to specific server processes
- **Selective Loading**: Each server only loads its assigned modules via `ENABLED_MODULES`
- **Dynamic Routing**: Nginx routes requests based on module name in URL
- **Independent Scaling**: Modules can run multiple instances on different ports

**Example**: Running broker and datafeed on separate servers:

```yaml
# dev-config.yaml
servers:
  broker:
    port: 8001
    modules: [broker]
  datafeed:
    port: 8002
    modules: [datafeed]
```

Result: Broker module isolated in process on port 8001, datafeed on 8002, nginx gateway on 8000.

See [backend/docs/BACKEND_MANAGER_GUIDE.md](../backend/docs/BACKEND_MANAGER_GUIDE.md) for complete reference including:

- Detailed configuration file schema
- Advanced deployment patterns
- Production deployment guide
- Troubleshooting common issues
- Performance tuning recommendations

### Modular Backend Architecture

**Architectural Pattern**: The backend follows a **modular factory-based architecture** enabling independent development, testing, and deployment of feature modules.

#### Module System Design

**Core Components**:

1. **Module Protocol** (`shared/module_interface.py`) - Defines standard interface for all modules
2. **Module Registry** (`shared/module_registry.py`) - Centralized module management
3. **Application Factory** (`app_factory.py`) - Dynamic composition with selective loading
4. **Shared Infrastructure** (`shared/`) - Always-loaded core functionality
5. **Feature Modules** (`modules/`) - Pluggable business domain implementations

**Module Protocol Definition**:

```python
# shared/module_interface.py
class Module(Protocol):
  @property
  def name(self) -> str:
    """Unique module identifier (e.g., 'broker', 'datafeed')"""
    ...

  def get_api_routers(self) -> list[APIRouter]:
    """Return module's REST API routers"""
    ...

  def get_ws_routers(self) -> list[WsRouteFeature]:
    """Return module's WebSocket routers"""
    ...

  def configure_app(self, api_app: FastAPI, ws_app: FastWSAdapter) -> None:
    """Optional module-specific app configuration"""
    ...

# Note: Modules are lazily instantiated when requested via
# `ModuleRegistry.get_modules(enabled_modules: list[str] | None)`.
# Module specs can optionally include version filters (e.g., "broker:v1")
# to load only specific versions. Per-module mutable `enabled` state was
# removed to keep the registry functional and stateless; the selection of
# which modules to load is driven by the registry call (e.g. from
# `ENABLED_MODULES` env var like "broker:v1,datafeed:v2").
```

**Module Implementation Pattern**:

```python
# modules/broker/__init__.py
class BrokerModule:
  def __init__(self) -> None:
    # Service instances remain lazily created on first access
    self._service: BrokerService | None = None

  @property
  def name(self) -> str:
    return "broker"

  @property
  def service(self) -> BrokerService:
    if self._service is None:
      self._service = BrokerService()  # Lazy load
    return self._service

  def get_api_routers(self) -> list[APIRouter]:
    return [BrokerApi(service=self.service, prefix=f"/{self.name}")]

  def get_ws_routers(self) -> list[WsRouteFeature]:
    return BrokerWsRouters(service=self.service)
```

**Application Factory Pattern**:

```python
# app_factory.py
def create_app(enabled_modules: list[str] | None = None) -> ModularApp:
    registry = ModuleRegistry(modules_dir)
    registry.clear()  # Critical for test isolation

    # Auto-discover and register all available modules
    registry.auto_discover()  # Discovers: AuthModule, BrokerModule, DatafeedModule

    # Create apps
    api_app = FastAPI(...)

    # Include shared infrastructure (always loaded)
    api_app.include_router(HealthApi(...), ...)
    api_app.include_router(VersionApi(...), ...)

    # Get modules to enable (None = all modules, list = specific modules)
    for module in registry.get_modules(enabled_modules):
        for router in module.get_api_routers():
            api_app.include_router(router, prefix=f"/api/v1/{module.name}", ...)
        for ws_router in module.get_ws_routers():
            ws_app.include_router(ws_router)

    return api_app
```

**Module-Specific Deployment**:

```bash
# Start with specific module (all versions)
ENABLED_MODULES=datafeed uvicorn trading_api.main:app
ENABLED_MODULES=broker uvicorn trading_api.main:app

# Start with specific module version only
ENABLED_MODULES=broker:v1 uvicorn trading_api.main:app
ENABLED_MODULES=datafeed:v2 uvicorn trading_api.main:app

# Start with multiple specific versions
ENABLED_MODULES=broker:v1,datafeed:v2 uvicorn trading_api.main:app

# Start with all modules (default)
uvicorn trading_api.main:app
```

#### Multi-Process Deployment with Nginx Gateway

**Overview**: Production deployments run modules in separate processes coordinated by an nginx reverse proxy gateway. This enables process isolation, independent scaling, and zero-downtime deployments.

**Architecture**:

```
Client Requests
    ↓
nginx Gateway (port 8000)
    ├─→ /api/v1/broker/*   → Broker Process (port 8001)
    ├─→ /api/v1/datafeed/* → Datafeed Process (port 8002)
    └─→ WebSocket routing based on path or query param
```

**Configuration** (`backend/dev-config.yaml`):

```yaml
# API base URL prefix
api_base_url: "/api/v1"

# Nginx gateway configuration
nginx:
  port: 8000 # Single public-facing port
  worker_processes: 1 # 'auto' or specific number
  worker_connections: 1024

# Backend server instances
servers:
  broker:
    port: 8001
    instances: 1
    modules: [broker]
    reload: true

  datafeed:
    port: 8002
    instances: 1
    modules: [datafeed]
    reload: true

# WebSocket routing strategy
websocket:
  routing_strategy: "path" # "query_param" or "path"
  query_param_name: "type"

# Module-to-server mapping for WebSocket routing
websocket_routes:
  broker: broker # /api/v1/broker/ws → broker server
  datafeed: datafeed # /api/v1/datafeed/ws → datafeed server
```

**Deployment Commands**:

```bash
# Start orchestrated multi-process backend
make backend-dev-multi

# Managed by backend_manager.py (1,571 lines):
# - Generates nginx.conf from dev-config.yaml
# - Starts module processes with PID tracking
# - Configures nginx routing (REST + WebSocket)
# - Handles graceful shutdown
```

**WebSocket Routing Strategies**:

1. **Path-Based** (default): `ws://host/api/v1/broker/ws`

   - Nginx routes based on URL path prefix
   - Matches frontend URL structure
   - Simpler configuration

2. **Query-Param**: `ws://host/api/v1/ws?type=orders`
   - Nginx inspects query parameter
   - Single WebSocket endpoint
   - More flexible for complex routing

**Benefits**:

- ✅ **Process Isolation**: Module crashes don't affect others
- ✅ **Horizontal Scaling**: Run multiple instances per module
- ✅ **Resource Management**: CPU/memory limits per process
- ✅ **Zero-Downtime Deploys**: Rolling restarts per module
- ✅ **Auto-Generated Config**: nginx.conf generated from YAML
- ✅ **PID Tracking**: Graceful process lifecycle management

See [backend/docs/BACKEND_MANAGER_GUIDE.md](../backend/docs/BACKEND_MANAGER_GUIDE.md) for complete deployment guide.

**Benefits**:

- \u2705 **Independent Development**: Modules developed and tested in isolation
- \u2705 **Lazy Loading**: Services created only when module enabled
- \u2705 **Zero Configuration**: New modules auto-discovered via registry
- \u2705 **Microservice Ready**: Modules can be extracted to separate services
- \u2705 **Test Isolation**: Each module tested independently with factory pattern
- \u2705 **Import Boundaries**: Automated enforcement prevents cross-module coupling

**Import Boundary Enforcement**:

```python
# Enforced rules (AST-based validation)
\u2705 modules/*  \u2192 models/*, shared/*      # Modules can import shared infrastructure
\u2705 shared/*   \u2192 models/*               # Shared can import models only
\u2705 models/*   \u2192 (nothing)               # Models are pure data

\u274c modules/broker \u2192 modules/datafeed   # Cross-module imports forbidden
\u274c shared/*       \u2192 modules/*          # Shared cannot depend on modules
```

Validation: `make test-boundaries` (runs automatically in CI/CD)

### Backend Models Architecture

**Organizational Principle**: Models are grouped by **business concepts/domains**, not by technical layers or API types.

#### Topic-Based Model Organization

The backend follows a **domain-driven design** approach where models are organized around business concepts (topics) rather than technical API types:

```
models/
├── common.py           # Cross-cutting shared models
├── broker/             # Broker business domain
│   ├── orders.py       # Everything related to orders (REST + WS)
│   ├── positions.py    # Everything related to positions (REST + WS)
│   ├── executions.py   # Everything related to executions (REST + WS)
│   ├── account.py      # Everything related to accounts (REST + WS)
│   ├── connection.py   # Everything related to broker connections (WS)
│   └── leverage.py     # Everything related to leverage (REST)
└── market/             # Market data business domain
    ├── bars.py         # Everything related to bars/OHLC (REST + WS)
    ├── quotes.py       # Everything related to quotes (REST + WS)
    ├── instruments.py  # Everything related to instruments/symbols (REST)
    ├── search.py       # Everything related to search (REST)
    └── configuration.py # Everything related to datafeed config (REST)
```

#### Design Principles

1. **Business Concept Grouping**

   - Each file represents a **single business concept** (orders, positions, bars, etc.)
   - All model variations for that concept live in the same file
   - Both REST and WebSocket models coexist in topic files

2. **Model Type Coexistence**

   - REST request/response models: `PreOrder`, `PlacedOrder`
   - WebSocket subscription models: `OrderSubscriptionRequest`
   - WebSocket update models: Use the same response models as REST
   - All related to the same business concept stay together

3. **No Technical Segregation**

   - ❌ **AVOID**: Separating by API type (`rest_models/`, `ws_models/`)
   - ❌ **AVOID**: Separating by operation type (`requests/`, `responses/`)
   - ✅ **PREFER**: One topic file contains all model types for that domain

4. **Domain Separation**
   - Top-level separation by business domain (`broker/`, `market/`)
   - Reflects the two main API areas: trading operations vs market data
   - Aligns with TradingView API structure (broker API vs datafeed API)

#### Example: orders.py Model Organization

**Model Categories in Single File**:

| Category                   | Model Name                   | Usage                                       |
| -------------------------- | ---------------------------- | ------------------------------------------- |
| **Enumerations**           | OrderStatus, OrderType, Side | Shared across REST and WebSocket            |
| **REST Request**           | PreOrder                     | Input for placing orders via POST           |
| **REST/WS Response**       | PlacedOrder                  | Order status (REST responses + WS updates)  |
| **WebSocket Subscription** | OrderSubscriptionRequest     | Parameters for subscribing to order updates |

**Key Design Insight**:

- `PlacedOrder` serves dual purpose:
  - REST API response: `GET /api/v1/broker/orders` returns list of PlacedOrder
  - WebSocket update: `orders.update` broadcasts PlacedOrder on changes
- Single model definition eliminates duplication
- Ensures type consistency across communication channels

#### Benefits of Topic-Based Organization

✅ **Single Source of Truth**: One place for all order-related models
✅ **Reduced Duplication**: Shared models between REST and WebSocket
✅ **Easier Maintenance**: Changes to business logic happen in one file
✅ **Better Discoverability**: Developers find all related models together
✅ **Domain Alignment**: Matches business concepts, not technical infrastructure
✅ **Type Reusability**: Same `PlacedOrder` model for REST responses and WS updates
✅ **Enum Sharing**: Enumerations (`OrderStatus`, `OrderType`) shared across all operations

#### Anti-Patterns to Avoid

❌ **Technical Layer Separation**:

```
models/
├── rest/
│   ├── orders.py
│   └── positions.py
└── websocket/
    ├── orders.py       # Duplication!
    └── positions.py    # Duplication!
```

❌ **Operation Type Separation**:

```
models/
├── requests/
│   ├── order_request.py
│   └── subscription_request.py
└── responses/
    ├── order_response.py
    └── subscription_response.py
```

✅ **Business Topic Organization** (Current):

```
models/
├── broker/
│   ├── orders.py       # PreOrder, PlacedOrder, OrderSubscriptionRequest
│   └── positions.py    # Position, PositionSubscriptionRequest
└── market/
    └── bars.py         # Bar, BarsSubscriptionRequest
```

#### Integration with WebSocket Routers

**Model-to-Router Flow**:

```
Topic File (models/broker/orders.py) → Router File (modules/broker/ws/v1/__init__.py)
        ↓                                      ↓
  OrderSubscriptionRequest              WsRouter[OrderSubscriptionRequest, PlacedOrder]
  PlacedOrder                           Direct generic type instantiation
```

**Integration Pattern**:

1. **Business concept** defines all related models in one topic file (`models/broker/orders.py`)
2. **Router factory** imports subscription request + update model from topic file
3. **Direct generic instantiation** using `WsRouter[Request, Data]` pattern
4. **Type safety** ensured at compile time via Python generics

**Benefits**:

- Models and routers stay synchronized
- Change in topic file automatically propagates to router
- Type mismatches caught at build time
- No code generation overhead - direct generic types

#### Guidelines for New Models

When adding new models:

1. **Identify the business concept** (order, position, bar, quote, etc.)
2. **Locate the appropriate topic file** (`broker/orders.py`, `market/bars.py`, etc.)
3. **Add all model types** to that single file (request, response, subscription)
4. **Share enumerations and common types** across REST and WebSocket
5. **Export from topic `__init__.py`** to maintain clean imports
6. **Update domain `__init__.py`** (`broker/__init__.py`, `market/__init__.py`)
7. **Export from main models** (`models/__init__.py`) for external access

**Never** create separate files for WebSocket vs REST models of the same business concept.

### Provider/Capability System

**Architectural Pattern**: The backend implements a **pluggable provider system** that decouples service logic from external implementations through capability-based dependency injection.

#### Core Design Philosophy

**Problem**: Services (e.g., AuthService) need external capabilities (authentication, broker APIs, data feeds) without tight coupling to specific implementations.

**Solution**: Provider/Capability system with automatic discovery and injection:

```text
Services declare what they need → ProviderRegistry finds implementations → AppFactory injects providers
```

**Benefits**:

- ✅ **Multiple implementations**: Support Google OAuth + local auth + IBKR auth simultaneously
- ✅ **Easy testing**: Mock providers instead of external APIs
- ✅ **Clean separation**: Service logic separated from implementation details
- ✅ **Fail-fast validation**: Missing providers detected at app startup, not production

#### Architecture Components

**1. Capability Specification** (`models/common.py`)

```python
@dataclass(frozen=True)
class CapabilitySpec:
    """Type-safe capability declaration."""
    name: CapabilityName  # "auth", "broker", "datafeed"
    version: str | None = None  # None = any version

    def matches(self, provider_capability: CapabilitySpec) -> bool:
        """Check if provider satisfies requirement."""
```

**Design Decision**: Immutable dataclass ensures specs cannot be mutated after creation.

**2. Provider Base Class** (`providers/base.py`)

```python
class Provider(ABC):
    """Base class for all providers."""

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Declare what capabilities this provider offers."""

    @property
    def name(self) -> str:
        """Unique provider identifier."""
```

**3. Capability Interfaces** (`providers/capabilities/`)

```python
# providers/capabilities/auth.py
class AuthCapability(ABC):
    """Authentication capability contract."""

    @abstractmethod
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify authentication token and return user claims."""
```

**Future capabilities**: `BrokerCapability`, `DatafeedCapability` will follow same pattern.

**4. Provider Registry** (`providers/registry.py`)

```python
class ProviderRegistry:
    """Auto-discover and manage provider instances."""

    def auto_discover(self) -> None:
        """Find all providers in providers/ directory."""

    async def get_providers(
        self, required_capabilities: list[CapabilitySpec]
    ) -> list[Provider]:
        """Lazy-load provider instances matching capabilities."""
```

**Performance**: Lazy-loading ensures providers only instantiated when needed.

#### Provider Lifecycle Flow

```text
Application Startup (AppFactory.create_app)
    ↓
1. ModuleRegistry.auto_discover() - Find all modules
    ↓
2. ProviderRegistry.auto_discover() - Find all providers
    ↓
3. AppFactory._resolve_capabilities() - Static analysis of service requirements
    ↓
4. ProviderRegistry.get_providers() - Lazy-load matching providers
    ↓
6. ModuleRegistry.get_modules(providers=...) - Inject providers into modules
    ↓
7. Service._resolve_capabilities() - Build capability map (FAIL-FAST)
    ↓
Application Ready ✓

Request Handling
    ↓
Service method called → service.auth_provider (O(1) cached lookup) → provider.verify_token()
```

#### Provider Implementation Pattern

**Example**: GoogleProvider implementing AuthCapability

```
providers/
├── google/
│   ├── __init__.py              # GoogleProvider class
│   └── tests/
│       └── test_google_provider.py
└── capabilities/
    └── auth.py                   # AuthCapability interface

models/
└── providers/
    └── google_oauth_configs.py       # GoogleProviderConfig
```

**Naming Convention (STRICT)**:

- Directory: `providers/{name}/` (lowercase)
- Class: `{Name}Provider` (PascalCase + "Provider" suffix)
- Export: `__init__.py` must export `{Name}Provider`

**Implementation Example**:

```python
# providers/google/__init__.py
class GoogleProvider(Provider, AuthCapability):
    """Google OAuth authentication provider."""

    def __init__(self, config: GoogleProviderConfig | None = None):
        self._config = config or GoogleProviderConfig()

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    @property
    def name(self) -> str:
        return "google"

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Implement AuthCapability - verify Google ID token."""
        # Call Google tokeninfo endpoint
        # Validate audience, email_verified
        # Return standardized claims
```

#### Service Integration

**Services declare required capabilities**:

```python
# modules/auth/service.py
class AuthService(ServiceInterface):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Declare what this service needs."""
        return [CapabilitySpec(name="auth")]

    @property
    def auth_provider(self) -> AuthCapability:
        """Type-safe access to auth capability."""
        provider = self._get_capability_provider("auth")
        return cast(AuthCapability, provider)

    async def authenticate_user(self, token: str):
        """Use injected provider for authentication."""
        claims = await self.auth_provider.verify_token(token)
        # Service logic continues...
```

**Dependency Injection Flow**:

```text
AppFactory → Module.__init__(providers=[...]) → Service.__init__(providers=[...])
    ↓
Service._resolve_capabilities() validates at initialization
    ↓
service._capability_map caches provider lookups (O(1) access)
```

#### Configuration Management

**Per-Provider Pydantic Configuration**:

```python
# models/providers/google_oauth_configs.py
class GoogleProviderConfig(ProviderConfig):
    """Google OAuth configuration."""

    client_id: str = Field(..., description="Google OAuth client ID")

    class Config:
        env_prefix = "GOOGLE_"  # Auto-loads GOOGLE_CLIENT_ID from env
```

**Environment Variables**:

```bash
# .env.local (development)
GOOGLE_CLIENT_ID=your_google_client_id_here

# Production: Use system environment or secrets management
```

**Security**: Configs never log secrets, support secrets management integration.

#### Multi-Capability Providers

**Advanced Pattern**: Single provider implementing multiple capabilities

```python
class IBKRProvider(Provider, AuthCapability, BrokerCapability):
    """IBKR provider implementing auth + broker capabilities."""

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(name="auth"),
            CapabilitySpec(name="broker"),
        ]

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Implement AuthCapability."""

    async def execute_order(self, order: dict) -> str:
        """Implement BrokerCapability."""
```

**Benefit**: Both AuthService and BrokerService share same IBKR connection instance (automatic deduplication).

#### Error Handling & Validation

**Fail-Fast Validation**:

```python
# Service initialization
def _resolve_capabilities(self) -> None:
    for req_cap in self.capabilities():
        if not self._find_matching_provider(req_cap):
            raise CapabilityNotFoundError(
                f"Service '{self.module_name}' requires '{req_cap}' "
                "but no provider found. App cannot start."
            )
```

**Provider Exceptions** (`models/common.py`):

```python
class ProviderError(Exception):
    """Base provider exception."""

class AuthenticationError(ProviderError):
    """Authentication verification failed."""

class CapabilityNotFoundError(ProviderError):
    """Required capability not satisfied."""
```

**Design Decision**: Custom exceptions instead of HTTPException enables provider reusability outside FastAPI.

#### Testing Strategy

**Unit Testing with Mock Providers**:

```python
@pytest.fixture
def mock_config():
    return GoogleProviderConfig(client_id="test_client_id")

@pytest.fixture
def provider(mock_config):
    return GoogleProvider(config=mock_config)

@pytest.mark.asyncio
async def test_verify_token(provider):
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock external API call
        claims = await provider.verify_token("test_token")
```

**Integration Testing**:

```python
async def test_provider_injection():
    factory = AppFactory()
    app = await factory.create_app(enabled_module_names=["auth"])

    # Verify provider was injected
    auth_module = factory.module_registry.get_module("auth")
    assert isinstance(auth_module.service._providers[0], GoogleProvider)
```

#### Performance Characteristics

| Metric                       | Value  | Notes                        |
| ---------------------------- | ------ | ---------------------------- |
| App startup overhead         | <50ms  | One-time discovery cost      |
| Provider discovery           | <20ms  | Directory scanning + imports |
| Capability resolution        | <10ms  | Static analysis              |
| Provider lookup (cached)     | <1ms   | O(1) dict lookup             |
| Memory overhead per provider | ~2-5MB | Instance + capability map    |

**Optimization**: Connection pooling in providers (e.g., httpx.AsyncClient reuse).

#### Documentation & Developer Guide

**Complete Reference**: See [backend/docs/PROVIDER-SYSTEM.md](../backend/docs/PROVIDER-SYSTEM.md) for:

- Step-by-step provider creation guide
- Configuration patterns
- Testing best practices
- Advanced multi-capability patterns
- Debugging & troubleshooting
- API reference

**Quick Start**: 5-minute example showing how to add new provider with auto-discovery.

#### Current Implementation Status

**Implemented**:

- ✅ Core infrastructure (CapabilitySpec, Provider, ProviderRegistry)
- ✅ GoogleProvider with AuthCapability
- ✅ AppFactory integration with two-phase loading
- ✅ ServiceInterface capability resolution
- ✅ Full test coverage (16 core + 11 Google + integration tests)

**Future Capabilities**:

- 🔄 BrokerCapability (for IBKR, Alpaca, etc.)
- 🔄 DatafeedCapability (for market data providers)
- 🔄 LocalProvider (email/password authentication)

**Migration Status**: AuthService successfully migrated to provider-based authentication.

## WebSocket Real-Time Architecture

### WsRouteService Protocol Pattern

The backend implements a **Protocol-based WebSocket service architecture** where services manage their own topic generators and broadcast updates through the FastWSAdapter.

#### Core Components

**1. `WsRouteService` (Protocol)**

**Location**: `shared/ws/ws_router.py`

**Protocol Methods**:

| Method       | Signature                   | Purpose                                       |
| ------------ | --------------------------- | --------------------------------------------- |
| create_topic | `async (topic: str) → None` | Create and start data generation for a topic  |
| remove_topic | `(topic: str) → None`       | Stop and clean up data generation for a topic |

**Implementations**: `BrokerService`, `DatafeedService`

**Design Benefits**:

- Protocol-based (no inheritance required)
- Services remain independent
- Clean dependency injection pattern

**Service Layer (Self-Managed Generators)**

**Locations**: `modules/datafeed/service.py`, `modules/broker/service.py`

**Service Architecture**:

```
BrokerService
    ├─ _update_callbacks: dict[str, Callable]  # Maps topic_type → broadcast callback
    ├─ _execution_simulator_task: Optional[Task]  # Single background execution task
    ├─ Business state (_orders, _positions, _executions, accounting)
    └─ Methods implementing WsRouteService Protocol
       ├─ create_topic(topic, topic_update) → Register callback, start simulator
       └─ remove_topic(topic) → Unregister callback, stop simulator if last
```

**Execution Simulator Architecture** (see `docs/BROKER-ARCHITECTURE.md` for details):

- **Single Background Task**: Random execution loop (1-2 second intervals)
- **Callback-Based Broadcasting**: Direct invocation, no queue overhead
- **Automatic Lifecycle**: Starts with first subscription, stops with last unsubscription
- **Execution Cascade**: execution → order → equity → position updates

```
Execution Simulator → _simulate_execution()
  ├─→ Create Execution → callback["executions"](execution)
  ├─→ Update Order Status → callback["orders"](order)
  ├─→ _update_equity() → callback["equity"](equity)
  └─→ _update_position() → callback["positions"](position)
```

**Current Data Flow**:

1. **create_topic()** called by WsRouter when first subscriber arrives

   - Registers `topic_update` callback in `_update_callbacks[topic_type]`
   - Starts execution simulator if not already running (first subscription)
   - Service ready to broadcast updates for this topic

2. **Execution Simulator Loop** (background task)

   - Picks random WORKING orders at 1-2 second intervals
   - Calls `_simulate_execution(order_id)` → triggers cascade
   - Execution cascade invokes callbacks directly (no queues)

3. **Callback Broadcasting** (immediate, deterministic order)

   - Execution created → `callback["executions"](execution)`
   - Order updated → `callback["orders"](order)`
   - Equity updated → `callback["equity"](equity)`
   - Position updated → `callback["positions"](position)`

4. **remove_topic()** called when last subscriber unsubscribes
   - Removes callback from `_update_callbacks`
   - Stops execution simulator if no more subscribers (automatic cleanup)

**Design Benefits**:

- ✅ Zero latency: Direct callback invocation (no queue delays)
- ✅ Deterministic ordering: Cascade always executes in same sequence
- ✅ Resource efficient: Simulator runs only when clients are subscribed
- ✅ Simple debugging: Stack trace shows full execution path

**3. `WsRouter` (Generic Implementation with Reference Counting)**

**Location**: `shared/ws/generic_route.py`

**Router Responsibilities**:

| Operation       | Trigger                     | Action                                                                   |
| --------------- | --------------------------- | ------------------------------------------------------------------------ |
| **Subscribe**   | First subscriber            | Increment counter to 1, call `service.create_topic(topic, topic_update)` |
| **Subscribe**   | Additional subscriber       | Increment counter                                                        |
| **Unsubscribe** | Not last subscriber         | Decrement counter                                                        |
| **Unsubscribe** | Last subscriber (count → 0) | Delete tracker entry, call `service.remove_topic(topic)`                 |

**Reference Counting Flow**:

```
Subscribe Request
    ↓
  Build topic from parameters
    ↓
  Check topic_trackers dictionary
    ↓
  If new topic → Set counter = 1 → create_topic(topic, topic_update)
  If existing → Increment counter
    ↓
  Client subscribes to topic
    ↓
  Send confirmation response
```

**Unsubscribe Flow**:

```
Unsubscribe Request
    ↓
  Build topic from parameters
    ↓
  Decrement topic_trackers[topic]
    ↓
  If counter ≤ 0 → remove_topic() → Delete tracker entry
    ↓
  Client unsubscribes from topic
```

**4. `FastWSAdapter` (Broadcasting with Per-Router Queues)**

**Location**: `shared/plugins/fastws_adapter.py`

**Adapter Responsibilities**:

| Component            | Purpose                     | Details                                             |
| -------------------- | --------------------------- | --------------------------------------------------- |
| Connection Lifecycle | Manages client connections  | `manage()` context manager for client lifecycle     |
| Router Registration  | `include_router()` override | Registers router, validates WsRouteFeature type     |
| Client Tracking      | Per-router active clients   | `router._active_clients: set[Client]` (in WsRouter) |
| Message Broadcasting | Direct client iteration     | Router's `broadcast_update()` filters by topic      |

**Broadcasting Flow** (Direct Pattern):

```
Service generator calls topic_update(data)
    ↓
  topic_update wraps in SubscriptionUpdate(topic, data)
    ↓
  WsRouter.broadcast_update(route, update) called
    ↓
  Filters _active_clients by topic subscription
    ↓
  Create Message(type="{route}.update", payload=update.model_dump_json())
    ↓
  asyncio.gather sends to all matching clients
```

#### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WebSocket Data Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Service Layer (BrokerService / DatafeedService)            │
│     └─> Manages _topic_trackers: dict[str, Callable]           │
│     └─> create_topic(topic, topic_update) stores callback      │
│     └─> Service generates data and calls topic_update(data)    │
│                                                                 │
│  2. WsRouter (Subscription Management + Broadcasting)          │
│     └─> topic_update callback calls broadcast_update()         │
│     └─> _active_clients: set[Client] tracks subscribed clients │
│     └─> broadcast_update() filters clients by topic            │
│                                                                 │
│  3. FastWSAdapter (Connection Lifecycle)                       │
│     └─> manage() context manager for client connections        │
│     └─> include_router() registers WsRouteFeature routers      │
│                                                                 │
│  4. WsRouter (Subscription Tracking)                           │
│     └─> Subscribe: Increments topic_trackers[topic]            │
│     └─> First subscriber → service.create_topic()              │
│     └─> Unsubscribe: Decrements topic_trackers[topic]          │
│     └─> Last unsubscribe → service.remove_topic()              │
│                                                                 │
│  5. FastWS Framework                                           │
│     └─> Manages WebSocket connections                          │
│     └─> Delivers updates to subscribed clients via topics      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Decisions

**1. Protocol-Based Contracts**

- Services implement simple two-method Protocol
- No inheritance required (BrokerService, DatafeedService are independent)
- Clean dependency injection

**2. Service-Managed Generators**

- Each service owns its `_topic_generators` dict
- Services control timing and data generation
- Services call `publish()` to broadcast updates

**3. Reference Counting with Simple Dict**

- `topic_trackers: dict[str, int]` tracks subscriber count
- First subscriber triggers `create_topic()`
- Last unsubscribe triggers `remove_topic()`

**4. FastWSAdapter Broadcasting**

- Per-router queues for message distribution
- Background tasks poll queues and broadcast
- Clean separation: services → adapter → clients

#### Router Factory Pattern

**Pattern Comparison**:

| Component             | Pattern         | Constructor Injection             | Benefits                           |
| --------------------- | --------------- | --------------------------------- | ---------------------------------- |
| **REST API Routers**  | Class-based     | `BrokerApi(broker_service)`       | Service passed as dependency       |
| **WebSocket Routers** | Factory pattern | `BrokerWsRouters(broker_service)` | Returns list of configured routers |

**REST API Router Pattern**:

- Inherits from `APIRouter`
- Constructor accepts service dependency
- Defines routes in `__init__` method
- Example: `BrokerApi`, `DatafeedApi`, `HealthApi`

**WebSocket Router Factory Pattern**:

- Inherits from `WsRouterBase` (which extends `list[WsRouteFeature]`)
- Constructor creates multiple related routers
- Each router configured with shared service
- Returns list for registration
- Example: `BrokerWsRouters`, `DatafeedWsRouters`

**Shared Benefits**:

- Dependency injection (no global state)
- No singletons
- Testable (easily mock services)
- Clean lifecycle management

```python
# modules/broker/api.py
class BrokerApi(APIRouter):
    def __init__(self, broker_service: BrokerService, prefix: str = "/broker"):
        super().__init__(prefix=prefix, tags=["broker"])
        self.broker_service = broker_service
        # Define routes in __init__
```

**WebSocket Router Factories**:

```python
# modules/broker/ws/v1/__init__.py
class BrokerWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        order_router = WsRouter[OrderSubscriptionRequest, PlacedOrder](
            route="orders", tags=["broker"], service=service
        )
        position_router = WsRouter[PositionSubscriptionRequest, Position](
            route="positions", tags=["broker"], service=service
        )
        super().__init__([order_router, position_router], service=service)
```

**Benefits**:

- Dependency injection (services passed in constructor)
- No global state or singletons
- Testable (mock services easily)
- Clean lifecycle management

### Frontend Structure

```
src/
├── main.ts             # App entry point
├── App.vue             # Root component
├── router/             # Vue Router config
├── stores/             # Pinia state management
├── services/           # API service layer
│   ├── brokerTerminalService.ts   # Broker adapter
│   └── datafeedService.ts         # Datafeed adapter
├── plugins/
│   ├── wsAdapter.ts    # Centralized WebSocket clients wrapper
│   ├── wsClientBase.ts # WebSocket base client (singleton)
│   ├── mappers.ts      # Type-safe data transformations
│   └── apiAdapter.ts   # REST client wrapper
├── clients/            # Auto-generated clients
│   ├── trader-client-generated/   # REST API client
│   └── ws-types-generated/        # WebSocket types
├── components/         # Vue components
└── types/              # TypeScript type definitions

scripts/
├── generate-openapi-client.sh    # REST client generation
└── generate-asyncapi-types.sh    # WebSocket types generation
```

## Data Flow

### 1. REST API Request/Response Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REST API DATA FLOW                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   Vue Component │  User action (place order, fetch positions, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Layer   │  brokerTerminalService.placeOrder(preOrder)
│ (Frontend)      │  • Uses frontend types only (PreOrder, PlacedOrder)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Mapper Layer    │  mapPreOrder(preOrder) → PreOrder_Api_Backend
│ (mappers.ts)    │  • Type transformation happens HERE
│                 │  • Enum conversions, null/undefined handling
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Generated REST  │  POST /api/v1/broker/orders
│ Client          │  • Type-safe API calls with backend types
│ (OpenAPI Gen)   │  • Automatic serialization/deserialization
└────────┬────────┘
         │
         │ HTTP POST (JSON)
         ▼
┌─────────────────┐
│ FastAPI Router  │  BrokerApi.placeOrder(PreOrder_Api_Backend)
│ (api/broker.py) │  • Pydantic validation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Business Logic  │  BrokerService.placeOrder()
│ (BrokerService) │  • Process order, update state
└────────┬────────┘
         │
         │ Response: PlaceOrderResult
         ▼
┌─────────────────┐
│ Pydantic Model  │  PlaceOrderResult serialization
│ Validation      │  • Type validation, JSON encoding
└────────┬────────┘
         │
         │ HTTP 200 (JSON)
         ▼
┌─────────────────┐
│ Generated REST  │  Deserialize to PlaceOrderResult_Api_Backend
│ Client          │  • Type-safe response handling
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Layer   │  Process result, update UI state
│ (Frontend)      │  • Uses frontend types only
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Vue Component │  Render result to user
└─────────────────┘
```

### 2. WebSocket Subscription Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET SUBSCRIPTION FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   Vue Component │  Subscribe to real-time updates
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Layer   │  wsAdapter.bars.subscribe(listenerId, params, onUpdate)
│ (Frontend)      │  • Params: { symbol: "AAPL", resolution: "1" }
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WebSocketClient │  Build topic: "bars:{"resolution":"1","symbol":"AAPL"}"
│ (wsClientBase)  │  • Topic format uses JSON-serialized params
│                 │  • Register listener with callback
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WebSocketBase   │  Check if subscription exists for topic
│ (Singleton)     │  • New topic: Create subscription state
│                 │  • Existing topic: Add listener to existing subscription
└────────┬────────┘
         │
         │ Send: { type: "bars.subscribe", payload: params }
         ▼
┌─────────────────┐
│ FastWS Router   │  Receive subscribe request
│ (Backend)       │  • Route: bars.subscribe
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WsRouter        │  Build topic using same algorithm
│ (Generic)       │  • topic = buildTopicParams(params)
│                 │  • Check topic_trackers dict
└────────┬────────┘
         │
         ├─ First subscriber for topic?
         │  YES ──────────┐
         │                ▼
         │         ┌─────────────────┐
         │         │ WsRouteService  │  create_topic(topic, topic_update)
         │         │ (BrokerService) │  • Create asyncio.Task for data generation
         │         │                 │  • Store topic_update callback
         │         │                 │  • Start generator loop
         │         └────────┬────────┘
         │                  │
         ├──────────────────┘
         │
         │  Increment topic_trackers[topic]
         │  Client.subscribe(topic) in FastWS
         │
         │ Send: { type: "bars.subscribe.response", payload: { status: "ok", topic: ... }}
         ▼
┌─────────────────┐
│ WebSocketBase   │  Receive subscription confirmation
│ (Singleton)     │  • Match by topic
│                 │  • Mark subscription.confirmed = true
│                 │  • Resolve pending promise
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Layer   │  Subscription confirmed, ready for updates
│ (Frontend)      │  • Returns topic string to caller
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Vue Component │  Display "subscribed" status
└─────────────────┘
```

### 3. WebSocket Data Update Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      WEBSOCKET UPDATE FLOW                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│ Data Generator  │  asyncio.Task running in BrokerService
│ (Service Layer) │  • Generates mock/real market data
│                 │  • Infinite loop with await asyncio.sleep()
└────────┬────────┘
         │
         │ New data available: Bar(time=..., open=..., high=...)
         ▼
┌─────────────────┐
│ topic_update    │  Callback registered during create_topic()
│ Callback        │  • Called by data generator
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WsRouter        │  topic_update(data) → broadcast_update()
│ (Generic)       │  • Wraps in SubscriptionUpdate(topic, data)
│                 │  • Filters _active_clients by topic
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WsRouter        │  Direct broadcasting to subscribed clients
│ Broadcasting    │  • asyncio.gather sends to all matching clients
│                 │  • Message type: "{route}.update"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FastWS Server   │  server_send(message, topic=update.topic)
│                 │  • Message type: "bars.update"
│                 │  • Only sends to clients subscribed to topic
└────────┬────────┘
         │
         │ WebSocket message: { type: "bars.update", payload: { topic, payload: {...}}}
         ▼
┌─────────────────┐
│ WebSocketBase   │  Receive update message
│ (Singleton)     │  • Parse message, extract topic
│                 │  • Route to subscriptions matching topic
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Subscription    │  Check subscription.confirmed === true
│ State           │  • Only route to confirmed subscriptions
│                 │  • Iterate over all listeners for topic
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WebSocketClient │  Apply data mapper: mapQuoteData(backendData)
│ Mapper          │  • Transform backend types to frontend types
│                 │  • TBackendData → TData
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Listener        │  Execute onUpdate(mappedData) callback
│ Callback        │  • Registered during subscribe()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Layer   │  Process update, update reactive state
│ (Frontend)      │  • Store in Pinia, update component state
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Vue Component │  Reactivity triggers re-render
│                 │  • Display new data to user
└─────────────────┘
```

### 4. Code Generation Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CODE GENERATION PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│ Developer       │  Modify backend Pydantic model
│ Action          │  • e.g., Add field to PlacedOrder
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ make dev-       │  Backend starts with auto-spec generation
│ fullstack       │  • make -f project.mk dev-fullstack
└────────┬────────┘
         │
         ├────────────────────────────────────────────────────────┐
         │                                                        │
         ▼                                                        ▼
┌─────────────────┐                                    ┌─────────────────┐
│ Backend Startup │  Uvicorn starts FastAPI app       │ File Watchers   │
└────────┬────────┘                                    │ (inotifywait)   │
         │                                             │ Monitor specs   │
         ▼                                             └────────┬────────┘
┌─────────────────┐                                             │
│ Spec Export     │  make generate (unified)                    │
│ (Offline Mode)  │  Generates OpenAPI, AsyncAPI, Python clients│
│                 │  • scripts/export_openapi_spec.py           │
│                 │  • scripts/export_asyncapi_spec.py          │
└────────┬────────┘                                             │
         │                                                       │
         │ Generate: backend/openapi.json                        │
         │           backend/asyncapi.json                       │
         ▼                                                       │
┌─────────────────┐                                             │
│ Wait for        │  Health endpoint check                      │
│ Backend Ready   │  • Poll http://localhost:8000/api/v1/health │
└────────┬────────┘                                             │
         │                                                       │
         ▼                                                       │
┌─────────────────┐                                             │
│ Frontend Client │  make generate-openapi-client               │
│ Generation      │  make generate-asyncapi-types               │
│ (Initial)       │  • OpenAPI Generator Tool                   │
│                 │  • Custom AsyncAPI type extractor           │
└────────┬────────┘                                             │
         │                                                       │
         │ Generate: frontend/src/clients_generated/            │
         │   ├─ trader-client-generated/                        │
         │   │  ├─ apis/                                        │
         │   │  ├─ models/                                      │
         │   │  └─ index.ts                                     │
         │   └─ ws-types-generated/                             │
         │      └─ index.ts                                     │
         ▼                                                       │
┌─────────────────┐                                             │
│ Frontend Dev    │  Vite starts with HMR                       │
│ Server Starts   │  • Port 5173                                │
└────────┬────────┘                                             │
         │                                                       │
         │◄────────────────────────────────────────────────────┐│
         │                                                      ││
         │ File watcher detects spec change                    ││
         │                                                      ││
         ▼                                                      ││
┌─────────────────┐                                            ││
│ Auto-           │  inotifywait triggers on spec file change  ││
│ Regeneration    │  • backend/openapi.json modified           ││
│                 │  • backend/asyncapi.json modified          ││
└────────┬────────┘                                            ││
         │                                                      ││
         ▼                                                      ││
┌─────────────────┐                                            ││
│ Run Client      │  make generate-openapi-client              ││
│ Generation      │  make generate-asyncapi-types              ││
└────────┬────────┘                                            ││
         │                                                      ││
         │ Updated TypeScript types                            ││
         ▼                                                      ││
┌─────────────────┐                                            ││
│ Vite HMR        │  Frontend hot-reloads with new types       ││
│ Update          │  • Breaking changes → TypeScript errors    ││
│                 │  • Compatible changes → Seamless update    ││
└────────┬────────┘                                            ││
         │                                                      ││
         └──────────────────────────────────────────────────────┘│
         │                                                       │
         │  Continue watching for changes                        │
         └───────────────────────────────────────────────────────┘

Key Features:
• Offline spec generation (no server needed for export)
• File-based watching (efficient, no polling)
• Automatic type synchronization
• Breaking changes caught at compile time
• ~2-3 second update cycle
```

### 5. Type Transformation Flow (Mapper Layer)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   TYPE TRANSFORMATION FLOW                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      BACKEND TYPE SOURCES                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Python (Pydantic Models)                                               │
│  ├─ models/broker/orders.py                                            │
│  │  ├─ class PreOrder(BaseModel)                                       │
│  │  │     symbol: str                                                  │
│  │  │     type: OrderType (Literal["market", "limit", "stop"])         │
│  │  │     side: Side (Literal["buy", "sell"])                          │
│  │  │     qty: float                                                   │
│  │  │     limitPrice: float | None = None                              │
│  │  │                                                                  │
│  │  └─ class PlacedOrder(BaseModel)                                    │
│  │        id: str                                                      │
│  │        symbol: str                                                  │
│  │        status: OrderStatus (Literal["working", "filled", ...])      │
│  │        ... (same fields as PreOrder)                                │
│  │                                                                     │
│  └─ models/market/quotes.py                                            │
│     └─ class QuoteData(BaseModel)                                      │
│           s: Literal["ok", "error"]                                    │
│           n: str  # symbol name                                        │
│           v: QuoteOkValue | QuoteErrorValue                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ OpenAPI/AsyncAPI Generation
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   GENERATED TYPESCRIPT TYPES                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  // frontend/src/clients_generated/trader-client-generated/models/                │
│  export interface PreOrder {                                            │
│    symbol: string                                                       │
│    type: "market" | "limit" | "stop"                                    │
│    side: "buy" | "sell"                                                 │
│    qty: number                                                          │
│    limitPrice?: number | null                                           │
│  }                                                                      │
│                                                                         │
│  // frontend/src/clients_generated/ws-types-generated/index.ts                    │
│  export interface PlacedOrder {                                         │
│    id: string                                                           │
│    symbol: string                                                       │
│    type: "market" | "limit" | "stop"                                    │
│    side: "buy" | "sell"                                                 │
│    status: "working" | "filled" | "rejected" | "canceled"               │
│    qty: number                                                          │
│    limitPrice?: number | null                                           │
│  }                                                                      │
│                                                                         │
│  export interface QuoteData {                                           │
│    s: "ok" | "error"                                                    │
│    n: string                                                            │
│    v: QuoteOkValue | QuoteErrorValue                                    │
│  }                                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Import with strict naming
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       MAPPER LAYER (mappers.ts)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  // ⚠️ STRICT NAMING CONVENTION ⚠️                                      │
│  import type {                                                          │
│    PreOrder as PreOrder_Api_Backend                                     │
│  } from '@clients/trader-client-generated'                              │
│                                                                         │
│  import type {                                                          │
│    PlacedOrder as PlacedOrder_Ws_Backend,                               │
│    QuoteData as QuoteData_Ws_Backend                                    │
│  } from '@clients/ws-types-generated'                                   │
│                                                                         │
│  import type {                                                          │
│    PreOrder, PlacedOrder, QuoteData                                     │
│  } from '@public/trading_terminal/charting_library'                     │
│                                                                         │
│  // Mapper functions                                                    │
│  export function mapPreOrder(                                           │
│    order: PreOrder                                                      │
│  ): PreOrder_Api_Backend {                                              │
│    return {                                                             │
│      symbol: order.symbol,                                              │
│      type: order.type as unknown as PreOrder_Api_Backend['type'],       │
│      side: order.side as unknown as PreOrder_Api_Backend['side'],       │
│      qty: order.qty,                                                    │
│      limitPrice: order.limitPrice ?? null,  // undefined → null         │
│      stopPrice: order.stopPrice ?? null,                                │
│      // ... other fields                                                │
│    }                                                                    │
│  }                                                                      │
│                                                                         │
│  export function mapOrder(                                              │
│    order: PlacedOrder_Ws_Backend                                        │
│  ): PlacedOrder {                                                       │
│    return {                                                             │
│      id: order.id,                                                      │
│      symbol: order.symbol,                                              │
│      type: order.type as unknown as PlacedOrder['type'],                │
│      side: order.side as unknown as PlacedOrder['side'],                │
│      status: order.status as unknown as PlacedOrder['status'],          │
│      qty: order.qty,                                                    │
│      limitPrice: order.limitPrice ?? undefined,  // null → undefined    │
│      // ... other fields                                                │
│    }                                                                    │
│  }                                                                      │
│                                                                         │
│  export function mapQuoteData(                                          │
│    quote: QuoteData_Ws_Backend                                          │
│  ): QuoteData {                                                         │
│    if (quote.s === 'error') {                                           │
│      return { s: 'error', n: quote.n, v: quote.v }                      │
│    }                                                                    │
│    return { s: 'ok', n: quote.n, v: { ...quote.v } }                    │
│  }                                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Services import ONLY frontend types
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  // services/brokerTerminalService.ts                                   │
│  import { mapPreOrder, mapOrder } from '@/plugins/mappers'              │
│  import type { PreOrder, PlacedOrder } from '@public/trading_terminal/  │
│     charting_library'                                                   │
│                                                                         │
│  // ❌ NEVER import backend types here                                  │
│  // ❌ import type { PreOrder } from '@clients/trader-client-generated' │
│                                                                         │
│  class BrokerTerminalService {                                          │
│    async placeOrder(order: PreOrder): Promise<PlacedOrder> {            │
│      const backendOrder = mapPreOrder(order)  // Transform              │
│      const result = await api.placeOrder(backendOrder)                  │
│      return mapOrder(result.order)  // Transform back                   │
│    }                                                                    │
│  }                                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Key Principles:
• Backend types confined to mappers.ts (NEVER in services)
• Strict naming: _Api_Backend, _Ws_Backend suffixes
• Services work exclusively with frontend types
• Breaking changes detected at TypeScript compile time
• Single responsibility: Mappers own all transformations
```

### 6. WebSocket Reconnection Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   WEBSOCKET RECONNECTION FLOW                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│ WebSocketBase   │  Connection is active, subscriptions confirmed
│ (Connected)     │  • ws.readyState === WebSocket.OPEN
└────────┬────────┘
         │
         │ Network error, server restart, etc.
         ▼
┌─────────────────┐
│ ws.onclose      │  Connection closed event
│ Event           │  • ws.readyState === WebSocket.CLOSED
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reconnection    │  setTimeout(() => this.resubscribeAll(), 0)
│ Trigger         │  • Non-blocking trigger
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ resubscribeAll()│  await new Promise(resolve => setTimeout(2000))
│                 │  • Wait 2 seconds before attempting reconnection
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Clear Pending   │  this.pendingRequests.forEach(pending => clearTimeout)
│ Requests        │  this.pendingRequests.clear()
│                 │  • Clean up old timeouts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Mark All        │  for (const sub of subscriptions.values())
│ Unconfirmed     │    subscription.confirmed = false
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reconnect       │  await this.__socketConnect()
│ WebSocket       │  • Create new WebSocket instance
│                 │  • Wait for ws.onopen
└────────┬────────┘
         │
         │ Connection established
         ▼
┌─────────────────┐
│ Resubscribe     │  for (const subscription of subscriptions.values())
│ All Topics      │    • subscription.confirmed = false
│                 │    • Send subscription request
│                 │    • Wait for confirmation
│                 │    • subscription.confirmed = true
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Resume Data     │  All subscriptions confirmed
│ Streaming       │  • Updates flow to listeners again
└─────────────────┘

Key Features:
• Automatic reconnection on connection loss
• All active subscriptions re-established
• No data loss (buffering in backend queues)
• Transparent to application layer
• Reference counting preserved across reconnections
```

### 7. Complete Backend/Frontend Interaction Patterns

```
┌─────────────────────────────────────────────────────────────────────────┐
│              BACKEND/FRONTEND INTERACTION PATTERNS                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ PATTERN 1: REST API CALL (Synchronous Request/Response)                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Frontend: brokerTerminalService.placeOrder(preOrder)                    │
│     ↓                                                                   │
│ mapPreOrder: PreOrder → PreOrder_Api_Backend                            │
│     ↓                                                                   │
│ HTTP POST /api/v1/broker/orders {symbol, type, side, qty, ...}         │
│     ↓                                                                   │
│ Backend: BrokerApi.placeOrder(preOrder: PreOrder_Api_Backend)           │
│     ↓                                                                   │
│ BrokerService.placeOrder() → Updates state, returns PlaceOrderResult   │
│     ↓                                                                   │
│ HTTP 200 {success: true, order: {id, symbol, status, ...}}             │
│     ↓                                                                   │
│ Frontend: Receives PlaceOrderResult_Api_Backend                         │
│     ↓                                                                   │
│ Updates UI (show order placed confirmation)                             │
│                                                                         │
│ Timing: ~50-200ms round-trip                                            │
│ Use Case: User actions requiring immediate confirmation                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ PATTERN 2: WEBSOCKET SUBSCRIPTION (Asynchronous Push Updates)          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Frontend: wsAdapter.orders.subscribe(listenerId, {accountId}, onUpdate)│
│     ↓                                                                   │
│ WebSocketClient builds topic: "orders:{"accountId":"DEMO-ACCOUNT"}"    │
│     ↓                                                                   │
│ WebSocket SEND {type: "orders.subscribe", payload: {accountId}}        │
│     ↓                                                                   │
│ Backend: OrderWsRouter receives subscription                            │
│     ↓                                                                   │
│ Reference counting: topic_trackers[topic]++                             │
│     ↓                                                                   │
│ First subscriber? service.create_topic(topic, topic_update)            │
│     ↓                                                                   │
│ BrokerService stores topic_update callback                              │
│     ↓                                                                   │
│ WebSocket SEND {type: "orders.subscribe.response", payload: {status}}  │
│     ↓                                                                   │
│ Frontend: Subscription confirmed, waiting for updates...               │
│                                                                         │
│ --- Later: Order status changes ---                                    │
│                                                                         │
│ Backend: Order fills, BrokerService updates state                       │
│     ↓                                                                   │
│ Calls topic_update(updatedOrder) → Triggers broadcast_update()         │
│     ↓                                                                   │
│ WsRouter filters _active_clients by topic, sends to all                 │
│     ↓                                                                   │
│ WebSocket SEND {type: "orders.update", payload: {topic, payload}}      │
│     ↓                                                                   │
│ Frontend: WebSocketBase routes to confirmed subscriptions              │
│     ↓                                                                   │
│ WebSocketClient applies mapper: PlacedOrder_Ws_Backend → PlacedOrder   │
│     ↓                                                                   │
│ onUpdate(mappedOrder) callback executes                                 │
│     ↓                                                                   │
│ UI reactively updates (order status changed)                            │
│                                                                         │
│ Timing: ~10-50ms per update (after initial subscription)               │
│ Use Case: Real-time monitoring of trading state                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ PATTERN 3: HYBRID (REST + WebSocket)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ PHASE 1: Subscribe to real-time updates                                │
│     Frontend: wsAdapter.positions.subscribe(...)                        │
│     Backend: Service registers subscription, starts tracking            │
│                                                                         │
│ PHASE 2: Perform action via REST                                       │
│     Frontend: HTTP POST /api/v1/broker/positions/{id}/close            │
│     Backend: BrokerService.closePosition() → Updates state             │
│     Response: {success: true}                                           │
│                                                                         │
│ PHASE 3: Receive update via WebSocket                                  │
│     Backend: Detects position closed, calls topic_update(position)     │
│     WebSocket broadcasts: positions.update                              │
│     Frontend: onUpdate receives closed position                         │
│     UI: Position disappears from list (reactive update)                 │
│                                                                         │
│ Why Hybrid?                                                             │
│   • REST: Reliable action confirmation (synchronous)                    │
│   • WebSocket: Real-time state sync (all clients notified)              │
│   • Best of both: Immediate feedback + global state coherence           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ PATTERN 4: TYPE-SAFE CONTRACT EVOLUTION                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Developer adds new field to PlacedOrder model:                          │
│                                                                         │
│ 1. Backend Change (models/broker/orders.py):                            │
│    class PlacedOrder(BaseModel):                                        │
│        ...existing fields...                                            │
│        parentOrderId: str | None = None  # NEW FIELD                    │
│                                                                         │
│ 2. Spec Regeneration (automatic):                                       │
│    File watcher detects change → make generate                          │
│    backend/openapi.json updated with new field                          │
│                                                                         │
│ 3. Frontend Client Generation (automatic):                              │
│    File watcher detects openapi.json change                             │
│    → make generate-openapi-client                                       │
│    PlacedOrder_Api_Backend interface updated                            │
│                                                                         │
│ 4. TypeScript Compilation:                                              │
│    ✅ Compatible change: Builds successfully                             │
│    ❌ Breaking change: Compilation fails with error locations           │
│                                                                         │
│ 5. Mapper Update (if needed):                                           │
│    mappers.ts: Add parentOrderId field mapping                          │
│    TypeScript validates transformation correctness                      │
│                                                                         │
│ 6. Service Layer (automatic):                                           │
│    Services already use frontend types → No changes needed              │
│    Type safety maintained end-to-end                                    │
│                                                                         │
│ Result: Breaking changes caught at compile time, not runtime!           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ PATTERN 5: MULTI-CLIENT SUBSCRIPTION (Reference Counting)              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Scenario: Two components subscribe to same data                         │
│                                                                         │
│ Component A: wsAdapter.quotes.subscribe("A", {symbol: "AAPL"}, ...)    │
│     Topic: "quotes:{"symbol":"AAPL"}"                                   │
│     Backend: topic_trackers["quotes:..."] = 1                           │
│     Service: create_topic() called → Start data generation              │
│                                                                         │
│ Component B: wsAdapter.quotes.subscribe("B", {symbol: "AAPL"}, ...)    │
│     Same topic: "quotes:{"symbol":"AAPL"}"                              │
│     Backend: topic_trackers["quotes:..."] = 2                           │
│     Service: create_topic() NOT called (already exists)                 │
│     → Both components receive same data stream                          │
│                                                                         │
│ Component A unsubscribes:                                               │
│     Backend: topic_trackers["quotes:..."] = 1                           │
│     Service: remove_topic() NOT called (still has subscriber)           │
│     → Component B continues receiving updates                           │
│                                                                         │
│ Component B unsubscribes:                                               │
│     Backend: topic_trackers["quotes:..."] = 0                           │
│     Service: remove_topic() called → Stop data generation               │
│     → Resource cleanup (no more subscribers)                            │
│                                                                         │
│ Benefits:                                                               │
│   • Single data stream shared across multiple subscribers               │
│   • Automatic resource management (no memory leaks)                     │
│   • Efficient: Backend generates data only when needed                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Client Generation

### Automated Workflow

1. **Backend Startup** → Generates `openapi.json` + `asyncapi.json`
2. **File Watchers** → Monitor spec files for changes
3. **Auto-Generation** → Regenerate clients on spec changes
4. **Type Safety** → Full TypeScript types from Pydantic models

**Benefits**:

- ✅ Automatic sync on backend changes
- ✅ Hot reload integration
- ✅ File-based (efficient, no server polling)
- ✅ One command startup: `make dev-fullstack`

## API Versioning

**Current**: `/api/v1/` (Stable)
**Planned**: `/api/v2/` (Future breaking changes)

**Strategy**:

- URL-based versioning (`/api/v{major}/`)
- No breaking changes within versions
- 6-month deprecation period
- Version info in responses

**Lifecycle**: Development → Beta → Stable → Deprecated → Sunset

## Testing Strategy

### Testing Pyramid

```
┌────────────────────────────────────────┐
│ E2E (Playwright)    │ Full workflows   │
├────────────────────────────────────────┤
│ Integration         │ API contracts    │
├────────────────────────────────────────┤
│ Unit Tests          │ Isolated logic   │
│ • Backend (pytest)  │ • FastAPI Test   │
│ • Frontend (Vitest) │ • Vue Test Utils │
└────────────────────────────────────────┘
```

**Key Features**:

- Independent backend/frontend testing (no cross-dependencies)
- FastAPI TestClient for backend (no server needed)
- Mock services for frontend (offline testing)
- Parallel execution in CI/CD

## Mapper Layer Architecture

### Overview

The mapper layer provides centralized, type-safe data transformations between backend and frontend types, ensuring clean separation of concerns.

**Location**: `frontend/src/plugins/mappers.ts`

### ⚠️ STRICT NAMING CONVENTIONS ⚠️

**CRITICAL**: Always follow these naming conventions when importing types in mappers:

```typescript
// ✅ CORRECT: Strict naming pattern
import type { QuoteData as QuoteData_Api_Backend } from "@clients/trader-client-generated";
import type { PlacedOrder as PlacedOrder_Ws_Backend } from "@clients/ws-types-generated";
import type {
  QuoteData,
  PlacedOrder,
} from "@public/trading_terminal/charting_library";

// ❌ WRONG: Inconsistent naming
import type { QuoteData as QuoteData_Backend } from "@clients/trader-client-generated";
import type { PlacedOrder as Order_Backend } from "@clients/ws-types-generated";
```

**Naming Rules**:

- **API Backend imports**: `<TYPE>_Api_Backend` (e.g., `QuoteData_Api_Backend`)
- **WebSocket Backend imports**: `<TYPE>_Ws_Backend` (e.g., `PlacedOrder_Ws_Backend`)
- **Frontend imports**: `<TYPE>` (e.g., `QuoteData`, `PlacedOrder`)

**Why Strict Naming?**

- **Readability**: Instantly identify source of each type
- **Maintainability**: Consistent pattern across all mappers
- **Type Safety**: Clear distinction between backend variants (API vs WS)
- **Debugging**: Easy to trace type mismatches

### Design Pattern

```
Backend Types (Python Pydantic)
    ↓ OpenAPI/AsyncAPI Generation
Generated Types (*_Backend suffix)
    ↓ Mapper Functions
Frontend Types (TradingView/Custom)
```

### Available Mappers

#### `mapQuoteData()`

**Purpose**: Transforms backend quote data to TradingView frontend format

**Transformation Details**:

| Aspect        | Backend Type               | Frontend Type              | Handling               |
| ------------- | -------------------------- | -------------------------- | ---------------------- |
| Status field  | `s: "ok" \| "error"`       | `s: "ok" \| "error"`       | Direct mapping         |
| Error state   | `v: { error: string }`     | `v: string`                | Unwrap error message   |
| Success state | `v: { lp, bid, ask, ... }` | `v: { lp, bid, ask, ... }` | Field-by-field mapping |
| Symbol name   | `n: string`                | `n: string`                | Direct mapping         |

**Usage**: Integrated in `WsAdapter` for real-time quotes, also used in REST API responses.

#### `mapPreOrder()`

**Purpose**: Transforms frontend order to backend format with enum conversions

**Transformation Details**:

| Field      | Frontend              | Backend                       | Conversion               |
| ---------- | --------------------- | ----------------------------- | ------------------------ |
| symbol     | `string`              | `string`                      | Direct                   |
| type       | Numeric enum          | String literal                | Cast with type assertion |
| side       | Numeric enum (1/-1)   | String literal ("buy"/"sell") | Cast with type assertion |
| qty        | `number`              | `number`                      | Direct                   |
| limitPrice | `number \| undefined` | `number \| null`              | `?? null` operator       |
| stopPrice  | `number \| undefined` | `number \| null`              | `?? null` operator       |

**Usage**: Used in broker service for order placement.

### Integration Points

**Integration Methods**:

| Integration Point      | Description                                | Pattern                                       |
| ---------------------- | ------------------------------------------ | --------------------------------------------- |
| **WebSocket Clients**  | Mappers applied automatically in WsAdapter | Client constructed with mapper function       |
| **REST API Responses** | Mappers used in service layer              | Array.map() with mapper function              |
| **Type Isolation**     | Services never import backend types        | Import mappers only, work with frontend types |

**Architectural Rule**:

```
Services Layer
    ↓
  Import mappers from @/plugins/mappers
  Import frontend types only
    ↓
  Never import from @/clients/trader-client-generated
  Never import from @/clients/ws-types-generated
```

### Benefits

✅ **Type Safety**: Compile-time validation of transformations
✅ **Reusability**: Single mapper for REST + WebSocket
✅ **Maintainability**: Centralized transformation logic
✅ **Backend Isolation**: Backend types confined to mapper layer
✅ **Runtime Validation**: Handles enum conversions and null handling

## Real-Time Architecture

### WebSocket Implementation

**Endpoint**: `ws://localhost:8000/api/v1/ws`
**Framework**: FastWS 0.1.7
**Documentation**: AsyncAPI at `/api/v1/ws/asyncapi`

> **Note**: WebSocket routers use direct generic types (`WsRouter[Request, Data]`) for type safety. See [backend/docs/BACKEND_WEBSOCKETS.md](../backend/docs/BACKEND_WEBSOCKETS.md) for implementation details.

### Centralized Adapter Pattern

**WsAdapter Structure**:

| Client Property | Route        | Mapper Function       | Purpose                                        |
| --------------- | ------------ | --------------------- | ---------------------------------------------- |
| bars            | "bars"       | Identity (no mapping) | Bar data already in correct format             |
| quotes          | "quotes"     | mapQuoteData          | Transform backend quotes to TradingView format |
| orders          | "orders"     | Identity              | Order updates                                  |
| positions       | "positions"  | Identity              | Position updates                               |
| executions      | "executions" | Identity              | Trade executions                               |
| equity          | "equity"     | Identity              | Account equity updates                         |

**Adapter Features**:

- Single entry point for all WebSocket operations
- Singleton WebSocket connection (shared across all clients)
- Automatic data mapping via mapper functions
- Server-confirmed subscriptions
- Auto-reconnection with resubscription
- Type-safe operations with generic parameters

### Message Pattern

**WebSocket Message Structure**:

| Field   | Type   | Description             | Example                             |
| ------- | ------ | ----------------------- | ----------------------------------- |
| type    | string | Operation identifier    | `"bars.subscribe"`, `"bars.update"` |
| payload | object | Operation-specific data | Request parameters or update data   |

### Operations

**Subscribe to Bars**:

| Direction       | Message Type              | Payload                | Purpose              |
| --------------- | ------------------------- | ---------------------- | -------------------- |
| Client → Server | `bars.subscribe`          | `{symbol, resolution}` | Request subscription |
| Server → Client | `bars.subscribe.response` | `{status, topic}`      | Confirm subscription |

**Receive Updates**:

| Direction       | Message Type  | Payload                                  | Purpose            |
| --------------- | ------------- | ---------------------------------------- | ------------------ |
| Server → Client | `bars.update` | `{time, open, high, low, close, volume}` | Broadcast bar data |

### Topic Format

**CRITICAL**: Topics use **JSON-serialized parameters** with sorted keys, not simple string concatenation.

```
{route}:{JSON-serialized-params}
```

**Examples**:

- `bars:{"resolution":"1","symbol":"AAPL"}` - Apple 1-minute bars
- `orders:{"accountId":"TEST-001"}` - Orders for account TEST-001
- `executions:{"accountId":"TEST-001","symbol":"AAPL"}` - AAPL executions for account

**⚠️ Topic Builder Compliance**: The topic builder algorithm MUST be **identical** in backend (Python) and frontend (TypeScript). See:

- Backend: `backend/src/trading_api/shared/ws/ws_router.py` - `buildTopicParams()`
- Frontend: `frontend/src/plugins/wsClientBase.ts` - `buildTopicParams()`
- Documentation: `docs/WEBSOCKET-CLIENTS.md`

**Features**:

- Multi-symbol/multi-account subscriptions per client
- Topic-based filtering with complex parameters
- Broadcast only to subscribers with matching topics
- Automatic cleanup on disconnect
- Type-safe parameter serialization

### Connection Management

- **Heartbeat**: 30s interval (client must send messages)
- **Max Lifespan**: 1 hour per connection
- **Error Handling**: Graceful with WS status codes
- **Authentication**: Extensible (currently optional)

## Development Workflow

### Full-Stack Development

**Command**: `make -f project.mk dev-fullstack`

**Workflow Steps**:

| Step | Action                    | Purpose                                            |
| ---- | ------------------------- | -------------------------------------------------- |
| 1    | Port availability check   | Ensure 8000 (backend) and 5173 (frontend) are free |
| 2    | Start backend server      | Launch FastAPI + Uvicorn                           |
| 3    | Generate specs            | Export openapi.json and asyncapi.json              |
| 4    | Wait for backend ready    | Health endpoint check                              |
| 5    | Generate frontend clients | TypeScript types from specs                        |
| 6    | Start file watchers       | Monitor specs for changes                          |
| 7    | Start frontend dev server | Launch Vite with HMR                               |
| 8    | Monitor all processes     | Track status, handle errors                        |

### Component Development

**Development Commands**:

| Component     | Command                                  | Prerequisites          | Use Case                     |
| ------------- | ---------------------------------------- | ---------------------- | ---------------------------- |
| Backend only  | `cd backend && make dev`                 | Poetry environment     | Backend feature development  |
| Frontend only | `cd frontend && make dev`                | Backend running        | Frontend feature development |
| Run all tests | `make -f project.mk test-all`            | Dependencies installed | Verify all changes           |
| Code quality  | `make -f project.mk lint-all format-all` | Pre-commit hooks       | Before committing            |

## Design Patterns

### Backend Patterns

- **Dependency Injection** - FastAPI's DI system
- **Service Layer** - Business logic separation
- **Repository Pattern** - Data access abstraction
- **Response Models** - Consistent API responses

### Frontend Patterns

- **Composition API** - Vue 3 modern pattern
- **Store Pattern** - Pinia state management
- **Service Layer** - API abstraction with smart fallbacks
- **Dual-Client System** - Mock + Real backend adapters

### Cross-Cutting

- **Contract-First** - OpenAPI/AsyncAPI specifications
- **Test-Driven** - TDD workflow
- **Type-First** - TypeScript/Python type safety

## Performance Considerations

### Backend

- ASGI async/await for high concurrency
- In-memory caching for frequently accessed data
- Pydantic model optimization
- Efficient WebSocket broadcasting (topic-based)

### Frontend

- Vite for fast ES builds
- Code splitting and lazy loading
- Vue 3 Composition API optimizations
- Efficient state management with Pinia

### Real-Time

- Connection pooling
- Topic-based filtering (send only to subscribers)
- Heartbeat system for connection health
- Configurable rate limiting

## Security

### Authentication & Authorization

**Implementation Status**: ✅ **Production Ready** (MVP with in-memory storage)

- **JWT Access Tokens**: RS256-signed tokens (5-minute expiry)
- **Refresh Token Rotation**: Opaque tokens with device fingerprinting
- **Cookie-Based Sessions**: HttpOnly, Secure, SameSite=Strict cookies
- **Google OAuth Integration**: ID token verification via `authlib`
- **Stateless Middleware**: Public key validation only (no database queries)
- **WebSocket Authentication**: Automatic via cookies

**Architecture:**

- **Auth Module**: `backend/src/trading_api/modules/auth/` (JWT generation, Google OAuth)
- **Shared Middleware**: `backend/src/trading_api/shared/middleware/auth.py` (stateless validation)
- **Frontend Service**: `frontend/src/services/authService.ts` (service-based, no Pinia store)
- **Router Guards**: Stateless with API introspection (30s cache)

**Production Migration Path:**

- Replace in-memory user storage with PostgreSQL
- Replace in-memory refresh tokens with Redis (TTL + persistence)
- Enhanced device fingerprinting (more entropy)
- Rate limiting on login endpoints

See [AUTHENTICATION.md](./AUTHENTICATION.md) for complete details.

### Current Measures

- CORS configuration with credentials support
- Pydantic input validation
- MyPy + TypeScript static analysis
- Comprehensive test coverage (92 auth-specific tests)
- JWT signature verification (RS256)
- HttpOnly cookies (XSS protection)
- SameSite=Strict (CSRF protection)

### Planned Enhancements

- JWT authentication
- Per-endpoint rate limiting
- HTTPS/WSS for production
- Enhanced input sanitization

## Monitoring & Observability

**Current**:

- Health endpoints (`/api/v1/health`)
- API version tracking
- WebSocket connection metrics
- Comprehensive test reporting

**Planned**:

- Application metrics (response times, error rates)
- WebSocket lifecycle tracking
- Centralized error logging
- Performance profiling

## Documentation Structure

### Core Documentation

- **ARCHITECTURE.md** - System architecture (this file)
- **docs/methodologies/API-METHODOLOGY.md** - TDD implementation guide
- **docs/methodologies/WEBSOCKET-METHODOLOGY.md** - WebSocket integration methodology
- **docs/DEVELOPMENT.md** - Development workflows
- **docs/TESTING.md** - Testing strategies
- **docs/CLIENT-GENERATION.md** - API client generation
- **docs/WEBSOCKET-CLIENTS.md** - WebSocket implementation

### Configuration

- **WORKSPACE-SETUP.md** - VS Code workspace
- **ENVIRONMENT-CONFIG.md** - Environment variables
- **MAKEFILE-GUIDE.md** - Make commands reference
- **HOOKS-SETUP.md** - Git hooks

### Component Documentation

- **backend/docs/** - Backend-specific docs
- **frontend/** - Frontend implementation docs

## Development Environment

### Vite Development Proxy

**Purpose**: The frontend uses Vite's built-in proxy to forward API requests to the backend during development, avoiding CORS issues and simplifying configuration.

**Configuration** (`frontend/vite.config.ts`):

```typescript
server: {
  port: parseInt(process.env.FRONTEND_PORT || '5173'),
  proxy: {
    '/api/': {
      target: process.env.VITE_API_URL || 'http://localhost:8000',
      changeOrigin: true,
      secure: false,
      ws: true, // Enable WebSocket proxying
    },
  },
}
```

**How It Works**:

| Request Path                       | Proxied To                         | Notes                 |
| ---------------------------------- | ---------------------------------- | --------------------- |
| `http://localhost:5173/api/v1/...` | `http://localhost:8000/api/v1/...` | REST API calls        |
| `ws://localhost:5173/api/v1/ws`    | `ws://localhost:8000/api/v1/ws`    | WebSocket connections |
| `http://localhost:5173/health`     | `http://localhost:8000/health`     | Health checks         |
| `http://localhost:5173/src/...`    | (No proxy - served by Vite)        | Frontend assets       |

**Environment Variables**:

- **`VITE_API_URL`**: Backend URL for proxy target (default: `http://localhost:8000`)

  - **MUST** have `VITE_` prefix to be accessible in browser code
  - Used by Vite proxy configuration at build time
  - Example: `VITE_API_URL=http://localhost:8000`

- **`VITE_TRADER_API_BASE_PATH`**: API base path for generated clients (default: empty string)
  - **MUST** have `VITE_` prefix to be exposed to frontend
  - Used by OpenAPI clients for constructing request URLs
  - Empty in development (relies on Vite proxy at `/api/`)
  - Set for production: `VITE_TRADER_API_BASE_PATH=/api`

**Development Flow**:

```
Frontend Code (Browser)
    ↓
apiAdapter.ts → new BrokerApi(basePath: '')
    ↓
HTTP Request: GET http://localhost:5173/orders
    ↓
Vite Proxy (intercepts /api/* pattern)
    ↓
Forward to: GET http://localhost:8000/orders
    ↓
Backend FastAPI (handles request)
```

**Benefits**:

- ✅ **No CORS Issues**: Same-origin requests from browser perspective
- ✅ **Simple Configuration**: Single environment variable
- ✅ **WebSocket Support**: Proxy handles both HTTP and WS
- ✅ **Hot Reload**: Changes apply immediately
- ✅ **Production-Ready**: Same code works with different basePath in production

**Production Difference**:

In production, set `VITE_TRADER_API_BASE_PATH=/api` and deploy without proxy:

```bash
# Development (uses Vite proxy)
VITE_TRADER_API_BASE_PATH=
npm run dev

# Production (direct API calls)
VITE_TRADER_API_BASE_PATH=/api
npm run build
```

See `ENVIRONMENT-CONFIG.md` for complete environment variable documentation.

## Deployment

### Development

**Development Deployment**:

| Aspect      | Details                            |
| ----------- | ---------------------------------- |
| Command     | `make -f project.mk dev-fullstack` |
| Backend     | Uvicorn with auto-reload           |
| Frontend    | Vite dev server with HMR + Proxy   |
| WebSocket   | Development endpoint (ws)          |
| Environment | Local machine                      |

### Production (Planned)

**Production Architecture**:

| Component     | Technology           | Purpose                              |
| ------------- | -------------------- | ------------------------------------ |
| Load Balancer | nginx                | SSL/TLS termination, WebSocket proxy |
| Orchestration | Docker/Kubernetes    | Container management, scaling        |
| Database      | Redis + PostgreSQL   | Caching and persistent storage       |
| Monitoring    | Prometheus + Grafana | Metrics and observability            |
| Logging       | ELK Stack            | Centralized log aggregation          |

## Future Roadmap

### Short Term (3 months)

- Complete JWT authentication
- Docker containerization
- Real market data integration
- E2E test suite completion

### Medium Term (6 months)

- Cloud deployment (Kubernetes)
- Production monitoring
- Performance analytics
- Enhanced security measures

### Long Term (12+ months)

- Mobile application
- AI-powered trading insights
- Advanced charting features
- Multi-region deployment

## Success Metrics

✅ **Independent Development** - Parallel team workflows
✅ **Type Safety** - End-to-end type checking
✅ **Real-Time Ready** - WebSocket infrastructure complete
✅ **Test-Driven** - Comprehensive testing at all levels
✅ **DevOps Friendly** - Automated CI/CD pipelines
✅ **Developer Experience** - Zero-config setup with intelligent fallbacks
✅ **Production Ready** - Scalable architecture for deployment

---

## Terminology Glossary

### General Terms

| Term                  | Definition                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Trading Host**      | The `IBrokerConnectionAdapterHost` interface provided by TradingView that allows pushing updates to the UI |
| **Broker API**        | Your implementation of `IBrokerWithoutRealtime` or `IBrokerTerminal` that handles trading operations       |
| **Datafeed**          | Service providing market data (bars, quotes, symbols) to the charting library                              |
| **Client Generation** | Automatic creation of TypeScript types and API clients from OpenAPI/AsyncAPI specs                         |

### Backend Terms

| Term               | Definition                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| **WsRouteService** | Protocol defining WebSocket topic lifecycle management (create_topic, remove_topic)                    |
| **WsRouter**       | Generic WebSocket router handling subscriptions with type-safe request/data parameters                 |
| **FastWSAdapter**  | Self-contained WebSocket adapter with embedded broadcasting and per-router message queues              |
| **Topic Builder**  | Algorithm creating consistent topic strings from subscription parameters (must match backend/frontend) |
| **Router Factory** | Pattern using class constructors to instantiate multiple related routers with dependency injection     |

### Frontend Terms

| Term              | Definition                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------- |
| **WsAdapter**     | Centralized wrapper exposing all WebSocket clients (bars, quotes, orders, etc.)          |
| **WsFallback**    | Mock WebSocket implementation for offline development and testing                        |
| **WebSocketBase** | Singleton managing WebSocket connection with auto-reconnection and subscription tracking |
| **Mapper**        | Type-safe function transforming backend types to frontend types (e.g., `mapQuoteData`)   |
| **wsClientBase**  | Generic WebSocket client with server-confirmed subscriptions and topic-based routing     |

### WebSocket Terms

| Term                    | Definition                                                                                    |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| **Topic**               | JSON-serialized subscription identifier (e.g., `bars:{"resolution":"1","symbol":"AAPL"}`)     |
| **Server Confirmation** | Backend sends `{route}.subscribe.response` before client routes messages to subscribers       |
| **Reference Counting**  | Tracking subscription count per topic for automatic cleanup when last subscriber unsubscribes |
| **Auto-Resubscription** | Automatically resubscribing to all active topics when WebSocket reconnects                    |
| **Topic-Based Routing** | Filtering and delivering messages only to subscribers matching the exact topic                |

### TradingView Terms

| Term                | Definition                                                                         |
| ------------------- | ---------------------------------------------------------------------------------- |
| **Order Ticket**    | TradingView dialog for placing/modifying orders with risk calculations             |
| **Account Manager** | Bottom panel showing account info, orders, positions, executions                   |
| **Broker Terminal** | Complete trading solution integrating broker API with TradingView charts           |
| **Watched Value**   | Reactive value created by `host.factory.createWatchedValue()` that auto-updates UI |
| **Trading Context** | Chart context for trade actions (symbol, price, position on chart)                 |

### Testing Terms

| Term                 | Definition                                                       |
| -------------------- | ---------------------------------------------------------------- |
| **TDD Red Phase**    | Writing failing tests before implementation                      |
| **TDD Green Phase**  | Implementing minimal code to make tests pass                     |
| **Smoke Test**       | High-level end-to-end test verifying critical paths work         |
| **Integration Test** | Test verifying multiple components work together correctly       |
| **Mock Service**     | Fake implementation replacing real service for testing isolation |

---

✅ **Real-Time Ready** - WebSocket infrastructure complete
✅ **Test-Driven** - Comprehensive testing at all levels
✅ **DevOps Friendly** - Automated CI/CD pipelines
✅ **Developer Experience** - Zero-config setup with intelligent fallbacks
✅ **Production Ready** - Scalable architecture for deployment

---

**Maintained by**: Development Team
**Review Schedule**: Quarterly architecture reviews
