# Modular Backend Architecture

**Status**: ✅ Production Ready  
**Last Updated**: November 2, 2025  
**Version**: 4.0.0

## Table of Contents

- [Overview](#overview)
- [Core Design Principles](#core-design-principles)
- [Architecture Components](#architecture-components)
- [Module System](#module-system)
- [Application Factory](#application-factory)
- [Module Structure](#module-structure)
- [WebSocket Architecture](#websocket-architecture)
- [Code Generation](#code-generation)
- [Deployment Modes](#deployment-modes)
- [Testing Strategy](#testing-strategy)

---

## Overview

The Trading Pro backend implements a **modular factory-based architecture** that enables:

- **Independent Development**: Modules can be developed, tested, and deployed separately
- **Selective Deployment**: Deploy only the modules you need
- **Protocol-Based Design**: All modules implement the same `Module` protocol
- **Self-Contained Modules**: Each module owns its complete FastAPI app (REST + WebSocket)
- **Automatic Spec Generation**: OpenAPI and AsyncAPI specs generated per module
- **Type-Safe Integration**: Protocol-based contracts ensure consistency

### Key Benefits

✅ **Modularity**: Add/remove features without affecting core system  
✅ **Testability**: Test modules in isolation with dedicated fixtures  
✅ **Scalability**: Run modules in separate processes for horizontal scaling  
✅ **Maintainability**: Clear boundaries and ownership per module  
✅ **Developer Experience**: Work on single module without full system

---

## Core Design Principles

### 1. Protocol-Based Contracts

Every module implements the `Module` protocol defined in `shared/module_interface.py`:

```python
class Module(ABC):
    """Protocol that all modules must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module identifier (e.g., 'broker', 'datafeed')"""

    @property
    @abstractmethod
    def module_dir(self) -> Path:
        """Module's directory path"""

    @property
    @abstractmethod
    def service(self) -> WsRouteService:
        """Module's business logic service"""

    @property
    @abstractmethod
    def api_routers(self) -> list[APIRouter]:
        """REST API routers"""

    @property
    @abstractmethod
    def ws_routers(self) -> list[WsRouteInterface]:
        """WebSocket routers"""

    @property
    @abstractmethod
    def tags(self) -> list[dict[str, str]]:
        """OpenAPI documentation tags"""

    def create_app(self) -> tuple[FastAPI, FastWSAdapter | None]:
        """Create module's complete FastAPI application"""
```

### 2. Self-Contained Module Apps

Each module creates its **own FastAPI application** with:

- **REST endpoints** via `APIRouter` instances
- **WebSocket endpoint** (`/ws`) via `FastWSAdapter`
- **Lifespan management** for spec generation and cleanup
- **Independent documentation** (OpenAPI/AsyncAPI)

The factory **mounts** module apps rather than collecting routers:

```python
# Module creates complete app
app, ws_app = module.create_app()

# Factory mounts it
main_app.mount(f"/api/v1/{module.name}", app)
```

### 3. Auto-Discovery and Registration

The `ModuleRegistry` automatically discovers modules:

```python
# Convention: modules/<module_name>/__init__.py exports <ModuleName>Module
modules/
├── broker/__init__.py      → exports BrokerModule
├── datafeed/__init__.py    → exports DatafeedModule
└── core/__init__.py        → exports CoreModule

# Registry auto-discovers and validates
registry.auto_discover(modules_dir)
```

**Validation Rules**:

- Module names use hyphens (not underscores): `market-data` ✅, `market_data` ❌
- Class naming: `{ModuleName}Module` (e.g., `BrokerModule`)
- No duplicate module names

### 4. Lazy Loading

Modules are **lazy-loaded** only when needed:

```python
# Registration stores classes, not instances
registry.register(BrokerModule, "broker")

# Instance created on first access
module = registry.get_module("broker")  # Creates BrokerModule() here
```

Benefits:

- Faster startup (no unnecessary initialization)
- Resource efficiency (only load what's enabled)
- Test isolation (each test gets fresh instances)

---

## Architecture Components

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     ModularFastAPI                          │
│  (Main Application - Coordinator)                           │
│                                                             │
│  • Mounts module apps at /api/v1/{module}                  │
│  • Merges OpenAPI specs                                     │
│  • Merges AsyncAPI specs                                    │
│  • Tracks WebSocket apps                                    │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Core Module  │    │ Broker Module│    │Datafeed Module│
│              │    │              │    │              │
│ FastAPI App  │    │ FastAPI App  │    │ FastAPI App  │
│ + WS (none)  │    │ + WS App     │    │ + WS App     │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Directory Structure

```
backend/src/trading_api/
├── app_factory.py              # Application factory and ModularFastAPI
├── main.py                     # Entry point (creates app via factory)
│
├── shared/                     # Shared infrastructure (always loaded)
│   ├── module_interface.py    # Module Protocol definition
│   ├── module_registry.py     # Module discovery and registration
│   ├── client_generation_service.py  # Python client generation
│   ├── api/                   # Shared API utilities
│   ├── plugins/               # FastWS adapter and plugins
│   ├── ws/                    # WebSocket framework
│   └── templates/             # Code generation templates
│
├── modules/                   # Feature modules (pluggable)
│   ├── core/                  # Core module (always enabled)
│   │   ├── __init__.py       # CoreModule class
│   │   ├── service.py        # CoreService (health, versions)
│   │   ├── api.py            # CoreApi (REST endpoints)
│   │   ├── specs_generated/  # OpenAPI specs
│   │   ├── client_generated/ # Python HTTP client
│   │   └── tests/            # Module tests
│   │
│   ├── broker/               # Broker module (optional)
│   │   ├── __init__.py       # BrokerModule class
│   │   ├── service.py        # BrokerService
│   │   ├── api.py            # BrokerApi
│   │   ├── ws.py             # WebSocket routers definition
│   │   ├── ws_generated/     # Auto-generated WS routers
│   │   ├── specs_generated/  # OpenAPI + AsyncAPI specs
│   │   ├── client_generated/ # Python HTTP client
│   │   └── tests/            # Module tests
│   │
│   └── datafeed/             # Datafeed module (optional)
│       ├── __init__.py       # DatafeedModule class
│       ├── service.py        # DatafeedService
│       ├── api.py            # DatafeedApi
│       ├── ws.py             # WebSocket routers definition
│       ├── ws_generated/     # Auto-generated WS routers
│       ├── specs_generated/  # OpenAPI + AsyncAPI specs
│       ├── client_generated/ # Python HTTP client
│       └── tests/            # Module tests
│
└── models/                   # Shared Pydantic models (topic-based)
    ├── bars.py               # Bar/candle data models
    ├── broker.py             # Order, position, execution models
    ├── common.py             # Common types (TimeFrame, etc.)
    └── datafeed.py           # Symbol, quote models
```

---

## Module System

### Module Lifecycle

```
1. Discovery    → registry.auto_discover(modules_dir)
2. Registration → registry.register(ModuleClass, "module_name")
3. Filtering    → registry.set_enabled_modules(["broker", "datafeed"])
4. Loading      → registry.get_enabled_modules()  # Lazy instantiation
5. App Creation → module.create_app()  # Returns (FastAPI, FastWSAdapter | None)
6. Mounting     → main_app.mount(f"/api/v1/{module.name}", module_app)
```

### Module Implementation Example

```python
# modules/broker/__init__.py
from pathlib import Path
from fastapi.routing import APIRouter
from trading_api.shared import Module
from trading_api.shared.ws.router_interface import WsRouteInterface

from .api import BrokerApi
from .service import BrokerService
from .ws import BrokerWsRouters


class BrokerModule(Module):
    """Broker module - Trading operations."""

    def __init__(self) -> None:
        super().__init__()
        self._service = BrokerService()
        # NO prefix - routes at root level within module app
        # Factory will mount at /api/v1/broker
        self._api_routers = [
            BrokerApi(service=self.service, prefix="", tags=[self.name])
        ]
        self._ws_routers = BrokerWsRouters(broker_service=self.service)

    @property
    def name(self) -> str:
        return "broker"

    @property
    def module_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def service(self) -> BrokerService:
        return self._service

    @property
    def api_routers(self) -> list[APIRouter]:
        return self._api_routers

    @property
    def ws_routers(self) -> list[WsRouteInterface]:
        return self._ws_routers

    @property
    def tags(self) -> list[dict[str, str]]:
        return [
            {
                "name": "broker",
                "description": "Broker operations (orders, positions, executions)",
            }
        ]
```

### URL Structure

Modules create **root-level routes** that get mounted with module prefix:

| Module   | Mount Point        | Module Route | Final URL                         |
| -------- | ------------------ | ------------ | --------------------------------- |
| Core     | `/api/v1/core`     | `/health`    | `/api/v1/core/health`             |
| Core     | `/api/v1/core`     | `/versions`  | `/api/v1/core/versions`           |
| Broker   | `/api/v1/broker`   | `/orders`    | `/api/v1/broker/orders`           |
| Broker   | `/api/v1/broker`   | `/ws`        | `/api/v1/broker/ws` (WebSocket)   |
| Datafeed | `/api/v1/datafeed` | `/config`    | `/api/v1/datafeed/config`         |
| Datafeed | `/api/v1/datafeed` | `/ws`        | `/api/v1/datafeed/ws` (WebSocket) |

**Key Pattern**:

- Module defines: `prefix=""` in routers
- Factory mounts: `app.mount("/api/v1/{module.name}", module_app)`
- Result: Clean, consistent URLs

---

## Application Factory

### ModularFastAPI Class

The `ModularFastAPI` class extends FastAPI with module management:

```python
class ModularFastAPI(FastAPI):
    """FastAPI with integrated module and WebSocket tracking."""

    def __init__(self, modules: list[Module], base_url: str, **kwargs):
        self.base_url = base_url
        self._modules_apps = [ModuleApp(module) for module in modules]

        # Create FastAPI with merged OpenAPI tags
        super().__init__(
            openapi_url=f"{base_url}/openapi.json",
            docs_url=f"{base_url}/docs",
            openapi_tags=[...],  # Merged from all modules
            **kwargs
        )

        # Mount each module's app
        for module_app in self._modules_apps:
            mount_path = f"{self.base_url}/{module_app.module.name}"
            self.mount(mount_path, module_app.api_app)

    def openapi(self) -> dict[str, Any]:
        """Generate merged OpenAPI schema from all modules."""
        # Merges paths, components from all mounted module apps

    def asyncapi(self) -> dict[str, Any]:
        """Generate merged AsyncAPI schema from all modules."""
        # Merges channels, components from all module WebSocket apps

    @property
    def ws_apps(self) -> list[FastWSAdapter]:
        """Get all WebSocket apps from modules."""
        return [m.ws_app for m in self._modules_apps if m.ws_app]
```

### Factory Pattern

```python
class AppFactory:
    """Factory for creating ModularFastAPI applications."""

    def create_app(
        self,
        enabled_module_names: list[str] | None = None
    ) -> ModularFastAPI:
        """Create app with selective module loading.

        Args:
            enabled_module_names: Modules to enable (None = all).
                                 Core is always enabled.

        Returns:
            ModularFastAPI instance with mounted modules
        """
        # 1. Clear and auto-discover modules
        self.registry.clear()
        self.registry.auto_discover(self.modules_dir)

        # 2. Ensure core is always enabled
        if enabled_module_names is not None:
            if "core" not in enabled_module_names:
                enabled_module_names.append("core")

        # 3. Set enabled modules
        self.registry.set_enabled_modules(enabled_module_names)

        # 4. Get enabled module instances (lazy-loaded)
        enabled_modules = self.registry.get_enabled_modules()

        # 5. Create ModularFastAPI
        app = ModularFastAPI(
            modules=enabled_modules,
            base_url="/api/v1",
            title="Trading API",
            version="1.0.0",
        )

        return app
```

### Usage Examples

```python
# Create factory
factory = AppFactory()

# Load all modules (default)
app = factory.create_app()

# Load specific modules (core always included)
app = factory.create_app(enabled_module_names=["datafeed"])

# Load only core
app = factory.create_app(enabled_module_names=[])
```

---

## Module Structure

### Anatomy of a Module

Each module follows this structure:

```
modules/{module_name}/
├── __init__.py              # {ModuleName}Module class (implements Protocol)
├── service.py               # Business logic (implements WsRouteService if WS)
├── api.py                   # REST API endpoints (extends APIRouter)
├── ws.py                    # WebSocket router definitions (TypeAlias)
├── ws_generated/            # Auto-generated concrete WS router classes
│   ├── {operation}_router.py
│   └── ...
├── specs_generated/         # Generated API specifications
│   ├── {module}_openapi.json
│   └── {module}_asyncapi.json
├── client_generated/        # Generated Python HTTP client
│   ├── {module}_client.py
│   └── __init__.py
└── tests/                   # Module-specific tests
    ├── test_api.py
    ├── test_service.py
    └── test_ws.py
```

### Module Creation Checklist

When creating a new module:

- [ ] Create `modules/{module_name}/` directory
- [ ] Implement `{ModuleName}Module` class with `Module` protocol
- [ ] Create `service.py` with business logic
- [ ] Create `api.py` with `APIRouter` subclass (REST endpoints)
- [ ] (Optional) Create `ws.py` with WebSocket router TypeAliases
- [ ] (Optional) WebSocket routers auto-generate on `make dev`
- [ ] Add module tests in `tests/` directory
- [ ] Verify with `make test-module-{module_name}`

---

## WebSocket Architecture

### Module-Scoped WebSocket Apps

Each module with real-time features creates its **own FastWSAdapter**:

```python
# In module.create_app()
if self.ws_routers:
    # Create module-specific WebSocket app
    ws_app = FastWSAdapter(
        title=f"{self.name.title()} WebSockets",
        description=f"Real-time WebSocket app for {self.name} module",
        version="1.0.0",
        asyncapi_url="ws/asyncapi.json",
        heartbeat_interval=30.0,
        max_connection_lifespan=3600.0,
    )

    # Register module's WebSocket routers
    for ws_router in self.ws_routers:
        ws_app.include_router(ws_router)

    # Register WebSocket endpoint in module's FastAPI app
    @app.websocket("/ws")
    async def websocket_endpoint(
        client: Annotated[Client, Depends(ws_app.manage)],
    ) -> None:
        await ws_app.serve(client)
```

### WebSocket URL Structure

| Module   | WebSocket Endpoint    | AsyncAPI Docs                  |
| -------- | --------------------- | ------------------------------ |
| Broker   | `/api/v1/broker/ws`   | `/api/v1/broker/ws/asyncapi`   |
| Datafeed | `/api/v1/datafeed/ws` | `/api/v1/datafeed/ws/asyncapi` |

### WsRouteService Protocol

Services implement the `WsRouteService` protocol for topic lifecycle:

```python
class WsRouteService(Protocol):
    """Protocol for services that support WebSocket topic subscriptions."""

    async def create_topic(self, topic: str) -> None:
        """Start generating data for topic (first subscriber)."""

    async def remove_topic(self, topic: str) -> None:
        """Stop generating data for topic (last unsubscribe)."""
```

**Reference Counting Pattern**:

```python
# In WebSocket router
topic_trackers: dict[str, int] = {}

async def subscribe(topic: str):
    if topic not in topic_trackers:
        topic_trackers[topic] = 0
        await service.create_topic(topic)  # First subscriber
    topic_trackers[topic] += 1

async def unsubscribe(topic: str):
    topic_trackers[topic] -= 1
    if topic_trackers[topic] == 0:
        await service.remove_topic(topic)  # Last unsubscribe
        del topic_trackers[topic]
```

---

## Code Generation

### Per-Module Spec Generation

Each module generates its **own specifications**:

```python
# In module.create_app() lifespan
async def lifespan(api_app: FastAPI):
    # Generate module's specs
    module.gen_specs_and_clients(
        api_app=api_app,
        ws_app=ws_app
    )

    if ws_app:
        ws_app.setup(api_app)

    yield
```

**Output Structure**:

```
modules/{module}/
├── specs_generated/
│   ├── {module}_openapi.json    # Module's REST API spec
│   └── {module}_asyncapi.json   # Module's WebSocket spec
└── client_generated/
    └── {module}_client.py        # Generated Python client
```

### Merged Specifications

The main app **merges** all module specs:

```python
# OpenAPI merge
main_app.openapi()  # Merges all module OpenAPI specs
# → /api/v1/openapi.json

# AsyncAPI merge
main_app.asyncapi()  # Merges all module AsyncAPI specs
# → /api/v1/ws/asyncapi.json (if WebSocket endpoint exists)
```

### WebSocket Router Generation

WebSocket routers are **auto-generated** from TypeAlias definitions:

```python
# modules/broker/ws.py
BarsSubscribeRouter: TypeAlias = GenericWsRoute[
    BarsSubscribeRequest,    # TRequest
    BarsSubscribeResponse,   # TResponse
    BarData,                 # TData (streaming)
]

# Auto-generates: modules/broker/ws_generated/bars_subscribe_router.py
class BarsSubscribeRouter(WsRouteInterface):
    # Concrete implementation with proper types
    ...
```

**Generation**: Automatic on app startup (`make dev`)

---

## Deployment Modes

### 1. Single-Process Mode (Development)

Run all modules in one process:

```bash
make dev  # Starts with all modules

# Or selective loading
ENABLED_MODULES=broker,datafeed make dev
```

### 2. Multi-Process Mode (Production)

Run modules in **separate processes** with nginx routing:

```bash
# Start multi-process backend
make backend-manager-start  # Uses dev-config.yaml

# Configuration: backend/dev-config.yaml
servers:
  - module: core
    host: 127.0.0.1
    port: 8001
  - module: broker
    host: 127.0.0.1
    port: 8002
  - module: datafeed
    host: 127.0.0.1
    port: 8003

nginx:
  listen_port: 8000
  routing_strategy: "path"  # Routes by /api/v1/{module}/*
```

**Architecture**:

```
Client Request → Nginx (8000) → Route by path → Module Process
                                 /api/v1/core/*      → Core (8001)
                                 /api/v1/broker/*    → Broker (8002)
                                 /api/v1/datafeed/*  → Datafeed (8003)
```

**Commands**:

```bash
make backend-manager-start   # Start all processes
make backend-manager-stop    # Stop all processes
make backend-manager-status  # Check status
make logs-tail               # View unified logs
```

### 3. Module-Specific Deployment

Deploy individual modules:

```python
# Start only broker module
from trading_api.app_factory import AppFactory

factory = AppFactory()
app = factory.create_app(enabled_module_names=["broker"])

# Run with uvicorn
uvicorn.run(app, host="0.0.0.0", port=8002)
```

---

## Testing Strategy

### Module Isolation

Each module has **independent test fixtures**:

```python
# modules/broker/tests/conftest.py
import pytest
from trading_api.app_factory import AppFactory

@pytest.fixture
def broker_app():
    """Broker module app only (core automatically included)."""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])

@pytest.fixture
def broker_client(broker_app):
    """Test client for broker module."""
    from fastapi.testclient import TestClient
    return TestClient(broker_app)
```

### Test Categories

```bash
# Module-specific tests
make test-module-broker      # Broker module only
make test-module-datafeed    # Datafeed module only
make test-module-core        # Core module only

# Boundary tests
make test-boundaries         # Import validation

# Integration tests
make test-integration        # Cross-module integration

# All tests
make test                    # Run everything
```

### Test Structure

```
tests/
├── conftest.py                    # Root fixtures (all modules)
├── test_deployment_config.py      # Config validation
├── test_import_boundaries.py      # Import rules
├── test_module_registry.py        # Registry tests
└── integration/
    ├── conftest.py               # Integration fixtures
    └── test_module_isolation.py  # Module isolation tests

modules/broker/tests/
├── conftest.py                   # Broker fixtures
├── test_api.py                   # REST API tests
├── test_service.py               # Service tests
└── test_ws.py                    # WebSocket tests
```

---

## Related Documentation

- **[ARCHITECTURE.md](../../ARCHITECTURE.md)** - Overall system architecture
- **[backend/README.md](../README.md)** - Backend setup and reference
- **[VERSIONING.md](./VERSIONING.md)** - API versioning strategy
- **[WEBSOCKETS.md](./WEBSOCKETS.md)** - WebSocket implementation guide
- **[PYTHON_CLIENT_GEN.md](./PYTHON_CLIENT_GEN.md)** - Python client generation
- **[docs/DOCUMENTATION-GUIDE.md](../../docs/DOCUMENTATION-GUIDE.md)** - Documentation index

---

## Summary

The modular backend architecture provides:

✅ **Protocol-Based Design** - All modules implement `Module` protocol  
✅ **Self-Contained Apps** - Each module owns complete FastAPI app  
✅ **Auto-Discovery** - Modules registered automatically via convention  
✅ **Lazy Loading** - Resources initialized only when needed  
✅ **Independent Testing** - Test modules in complete isolation  
✅ **Selective Deployment** - Run only the modules you need  
✅ **Horizontal Scaling** - Multi-process deployment with nginx  
✅ **Automatic Specs** - OpenAPI/AsyncAPI per module + merged  
✅ **Type Safety** - Protocol enforcement at compile time

**Key Insight**: Modules are **not just code organization** - they are **independently deployable applications** that compose into a cohesive system.
