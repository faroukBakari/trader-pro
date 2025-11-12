# Modular Backend Architecture

**Status**: ✅ Production Ready  
**Last Updated**: November 11, 2025  
**Version**: 5.1.0

## Table of Contents

- [Overview](#overview)
- [Quick Start for Module Development](#quick-start-for-module-development)
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
- **ABC-Based Design**: All modules extend the same `Module` abstract base class
- **Self-Contained Modules**: Each module owns its complete FastAPI app (REST + WebSocket)
- **Automatic Spec Generation**: OpenAPI and AsyncAPI specs generated per module
- **Type-Safe Integration**: ABC-based contracts ensure consistency

### Key Benefits

- **Modularity**: Add/remove features without affecting core system
- **Testability**: Test modules in isolation with dedicated fixtures
- **Scalability**: Run modules in separate processes for horizontal scaling
- **Maintainability**: Clear boundaries and ownership per module
- **Developer Experience**: Work on single module without full system

---

## Quick Start for Module Development

### Creating a New Module

Follow these steps to add a new feature module to the system:

**1. Create module directory structure**:

```bash
backend/src/trading_api/modules/my_module/
├── __init__.py           # MyModuleModule(Module) class
├── service.py            # MyModuleService(ServiceInterface) class
├── api/
│   └── v1.py            # MyModuleApi(APIRouterInterface) class
├── ws/
│   └── v1/
│       └── __init__.py  # WS routers (optional)
└── tests/
    └── test_my_module.py
```

**2. Implement the Module ABC**:

```python
# modules/my_module/__init__.py
from pathlib import Path
from trading_api.shared import Module

class MyModuleModule(Module):
    @property
    def name(self) -> str:
        return "my_module"

    @property
    def module_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def tags(self) -> list[dict[str, str]]:
        return [{"name": "My Module", "description": "My module operations"}]
```

**3. Implement the Service** (extends `ServiceInterface`):

```python
# modules/my_module/service.py
from trading_api.shared import ServiceInterface

class MyModuleService(ServiceInterface):
    def __init__(self, module_dir: Path):
        super().__init__(module_dir)
        # Your service logic here
```

**4. Implement the API Router** (extends `APIRouterInterface`):

```python
# modules/my_module/api/v1.py
from trading_api.shared.api import APIRouterInterface

class MyModuleApi(APIRouterInterface):
    def __init__(self, service: MyModuleService, version: str = "v1"):
        super().__init__(service=service, version=version, prefix="", tags=["My Module"])

        @self.get("/data")
        async def get_data():
            return {"message": "Hello from my module"}
```

**5. Auto-Discovery**: The module is automatically discovered by the registry. No manual registration needed!

**6. Test in isolation**:

```bash
# Start only your new module
ENABLED_MODULES=my_module make dev

# Access your endpoint
curl http://localhost:8000/api/v1/my_module/data
curl http://localhost:8000/api/v1/my_module/health
```

See sections below for complete implementation patterns and advanced features.

---

## Core Design Principles

### 1. Abstract Base Class Contracts

Every module extends the `Module` abstract base class defined in `shared/module_interface.py`:

```python
class Module(ABC):
    """Abstract base class defining the interface for pluggable modules."""

    def __init__(self, versions: list[str] | None = None):
        # Auto-discover versions from api/ and ws/ directories
        if versions is None:
            versions = self._discover_versions()

        self._versions = versions
        self._service = self._import_service()

        # Import version-specific routers
        self._api_routers: dict[str, APIRouterInterface] = {}
        self._ws_routers: dict[str, WsRouterInterface] = {}

        for version in versions:
            # Import from api/v1.py (file)
            self._api_routers[version] = self._import_api_routers_for_version(version)
            # Import from ws/v1/__init__.py (directory) - optional
            ws_router = self._import_ws_routers_for_version(version)
            if ws_router is not None:
                self._ws_routers[version] = ws_router

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module identifier (e.g., 'broker', 'datafeed')"""

    @property
    @abstractmethod
    def module_dir(self) -> Path:
        """Module's directory path"""

    @property
    def service(self) -> ServiceInterface:
        """Module's business logic service (extends ServiceInterface base class)"""

    @property
    def api_routers(self) -> dict[str, APIRouterInterface]:
        """API routers organized by version (all extend APIRouterInterface)"""

    @property
    def ws_routers(self) -> dict[str, WsRouterInterface]:
        """WebSocket routers organized by version (WsRouterInterface is list[WsRouteInterface])"""

    @property
    @abstractmethod
    def tags(self) -> list[dict[str, str]]:
        """OpenAPI documentation tags"""
```

**Key Architecture Patterns**:

- **ABC Pattern**: Uses Python's `ABC` (Abstract Base Class), not `Protocol`
- **Versioned Structure**:
  - API: `api/v1.py` (file)
  - WebSocket: `ws/v1/` (directory with `__init__.py`)
- **Auto-discovery**: Versions detected from directory structure
- **Type Safety**: All API routers extend `APIRouterInterface`

**Design Pattern**:

- Uses **ABC-based design** with Python's `abc.ABC` and `@abstractmethod`
- Subclasses must implement abstract methods at instantiation time

### 2. APIRouterInterface Auto-Exposing Health and Version Endpoints

All module API routers **inherit from `APIRouterInterface`**, which automatically provides:

- **`/health`** - Health check with module name and version
- **`/versions`** - All available API versions for the module
- **`/version`** - Current version information

```python
# shared/api/api_router_interface.py
class APIRouterInterface(APIRouter, ABC):
    def __init__(self, *args: Any, service: ServiceInterface, version: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._service = service
        self._version = version

        @self.get("/health", response_model=HealthResponse)
        async def healthcheck() -> HealthResponse:
            return service.get_health(version)

        @self.get("/versions", response_model=APIMetadata)
        async def get_api_versions() -> APIMetadata:
            return service.api_metadata

        @self.get("/version", response_model=VersionInfo)
        async def get_current_version() -> VersionInfo:
            return service.get_current_version_info(version)
```

**Example Usage**:

```bash
# Each module automatically exposes health/version endpoints
curl http://localhost:8000/api/v1/broker/health
curl http://localhost:8000/api/v1/broker/versions
curl http://localhost:8000/api/v1/datafeed/health
curl http://localhost:8000/api/v2/broker/health  # Different version
```

**Benefits**:

- No duplication - Every module gets health/version endpoints automatically
- Consistency - Uniform health check pattern across all modules
- Version-aware - Each version has its own health endpoint
- Module-scoped - Health checks specific to each module

### 3. ServiceInterface Base Class with Version Discovery

The `ServiceInterface` base class provides **automatic version discovery** and metadata:

```python
# shared/service_interface.py
class ServiceInterface(ABC):
    def __init__(self, module_dir: Path) -> None:
        self.module_dir = module_dir

        # Auto-discover versions from api/ directory structure
        api_dir = self.module_dir / "api"
        available_versions: dict[str, VersionInfo] = {}

        if api_dir.exists() and api_dir.is_dir():
            # Discover versions using .stem (supports both v1.py files and v1/ directories)
            version_dirs = [
                d.stem
                for d in api_dir.iterdir()
                if d.stem.startswith("v")
            ]

            # Build version metadata
            for version in version_dirs:
                available_versions[version] = VersionInfo(
                    version=version,
                    release_date="TBD",
                    status="stable",
                )

        self._api_metadata = APIMetadata(
            current_version=version_dirs[-1] if version_dirs else "v1",
            available_versions=available_versions,
        )
```

**Benefits**:

- Auto-discovery from directory structure
- Convention-based versioning
- Automatic API metadata generation

### 4. Version Discovery Patterns

The system uses a **mixed approach** for version discovery:

**API Routers** (`api/`):

```
modules/broker/api/
└── v1.py              # ✅ File pattern (recommended)
   OR
└── v1/                # ✅ Directory pattern (also supported)
    └── __init__.py
```

**Note**: API versioning supports **both file and directory patterns equally** via Python's `.stem` property. Use files for simplicity unless you need subdirectories.

**WebSocket Routers** (`ws/`):

```
modules/broker/ws/
└── v1/                # ✅ MUST be directory (required for generated routers)
    ├── __init__.py
    └── ws_generated/  # Generated routers created here
```

**Discovery Logic**:

```python
# In Module._discover_versions() - shared/module_interface.py
def _discover_versions(self) -> list[str]:
    """Auto-discover available versions from api/ and ws/ directories."""
    versions: set[str] = set()

    # Check api/ directory - .stem works for both files and directories
    # v1.py → .stem = "v1" ✅
    # v1/  → .stem = "v1" ✅
    api_dir = module_dir / "api"
    if api_dir.exists():
        versions.update(
            d.stem for d in api_dir.iterdir()
            if d.stem.startswith("v")
        )

    # Check ws/ directory - MUST be directories (enforced by d.is_dir())
    ws_dir = module_dir / "ws"
    if ws_dir.exists():
        ws_versions = {
            d.stem for d in ws_dir.iterdir()
            if d.is_dir() and d.stem.startswith("v")  # ← Directory required
        }
        versions |= ws_versions

    if not versions:
        raise ValueError(f"No versions found for module {self.name}")

    return sorted(versions)
```

### 5. Self-Contained Module Apps

Each module creates its **own FastAPI application** via `ModuleApp` wrapper:

- **REST endpoints** via `APIRouter` instances
- **WebSocket endpoint** (`/ws`) via `FastWSAdapter`
- **Independent documentation** (OpenAPI/AsyncAPI)

The factory **mounts** module apps:

```python
# ModuleApp creates complete apps per version
for version, api_router in module.api_routers.items():
    api_app = FastAPI(...)
    api_app.include_router(api_router)

    # WebSocket setup if available
    if module.ws_routers:
        ws_app = FastWSAdapter(...)
        # Note: ws_routers is dict[str, WsRouterInterface]
        # WsRouterInterface is actually list[WsRouteInterface]
        for version, ws_routers in module.ws_routers.items():
            for ws_router in ws_routers:
                ws_app.include_router(ws_router)

# Factory mounts it
main_app.mount(f"/api/{version}/{module.name}", api_app)
```

### 6. Auto-Discovery and Registration

The `ModuleRegistry` automatically discovers modules:

```python
# Convention: modules/<module_name>/__init__.py exports <ModuleName>Module
modules/
├── broker/__init__.py      → exports BrokerModule
└── datafeed/__init__.py    → exports DatafeedModule

# Registry auto-discovers and validates
registry.auto_discover(modules_dir)
```

**Validation Rules**:

- Module names use hyphens (not underscores): `market-data` ✅, `market_data` ❌
- Class naming: `{ModuleName}Module` (e.g., `BrokerModule`)
- No duplicate module names

### 7. Module Loading Enforcement

The module system **validates** that all routers follow the required patterns during import:

**API Router Enforcement**:

```python
# In Module._import_api_routers_for_version()
def _import_api_routers_for_version(self, version: str) -> APIRouterInterface:
    """Import API routers for a specific version."""
    api_module = importlib.import_module(f"...api.{version}")

    # Scan module for APIRouterInterface subclass
    for attr_name in dir(api_module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(api_module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, APIRouterInterface)  # ← VALIDATION
            and attr is not APIRouterInterface
        ):
            return attr(service=self._service, version=version, prefix="", tags=[self.name])

    # Fail if no valid router found
    raise ValueError(f"No APIRouterInterface class found in api.{version}")
```

**What This Enforces**:

- ✅ API routers **must** inherit from `APIRouterInterface`
- ✅ Automatically gets `/health`, `/versions`, `/version` endpoints
- ✅ Module name used for tags
- ✅ Prefix always empty (mounting adds the prefix)
- ❌ Modules without `APIRouterInterface` inheritance fail to load

**WebSocket Router Enforcement**:

```python
# In Module._import_ws_routers_for_version()
def _import_ws_routers_for_version(self, version: str) -> WsRouterInterface | None:
    """Import WebSocket routers for a specific version."""
    try:
        ws_module = importlib.import_module(f"...ws.{version}")

        # Scan for WsRouterInterface subclass
        for attr_name in dir(ws_module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(ws_module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, WsRouterInterface)  # ← VALIDATION
                and attr is not WsRouterInterface
            ):
                return attr(service=self._service)

        return None  # WebSocket is optional
    except ImportError:
        return None  # WebSocket support not required
```

**What This Enforces**:

- ✅ WS routers **should** inherit from `WsRouterInterface` if present
- ✅ WebSocket support is **optional** (returns None if not found)
- ✅ Version **must** be a directory (enforced in `_discover_versions()`)
- ✅ Multiple routers per version supported (list-based pattern)

**Error Examples**:

```python
# Missing APIRouterInterface inheritance
# api/v1.py
class BrokerApi(APIRouter):  # ❌ Wrong! Must inherit APIRouterInterface
    pass

# Result: ValueError: No APIRouterInterface class found in api.v1

# No versions found
# Empty api/ and ws/ directories
# Result: ValueError: No versions found for module broker
```

### 8. Lazy Loading

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
│                     ModularApp                              │
│  (Main Application - Coordinator)                           │
│                                                             │
│  • Mounts module apps at /api/{version}/{module}           │
│  • Merges OpenAPI specs                                     │
│  • Merges AsyncAPI specs                                    │
│  • Tracks WebSocket apps                                    │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Broker Module│    │Datafeed Module│    │ Other Modules│
│              │    │              │    │              │
│ FastAPI App  │    │ FastAPI App  │    │ FastAPI App  │
│ + WS App     │    │ + WS App     │    │ + WS App     │
└──────────────┘    └──────────────┘    └──────────────┘

  Each module provides:
  • Health endpoints via APIRouterInterface
  • Version endpoints via APIRouterInterface
  • Business logic via Service base class
  • Auto-discovered versions from directory structure
```

### Directory Structure

```
backend/src/trading_api/
├── app_factory.py              # Application factory and ModularApp
├── main.py                     # Entry point (creates app via factory)
│
├── shared/                     # Shared infrastructure (always loaded)
│   ├── module_interface.py    # Module ABC definition
│   ├── module_registry.py     # Module discovery and registration
│   ├── service.py             # Base Service class (health, versions)
│   ├── client_generation_service.py  # Python client generation
│   ├── api/                   # Shared API utilities
│   │   └── api_router_interface.py  # APIRouterInterface (auto health/version)
│   ├── plugins/               # FastWS adapter and plugins
│   ├── ws/                    # WebSocket framework
│   │   ├── fastws_adapter.py  # FastWSAdapter integration
│   │   └── ws_route_interface.py  # WsRouterInterface (list[WsRouteInterface])
│   └── templates/             # Code generation templates
│
├── modules/                   # Feature modules (pluggable)
│   ├── broker/               # Broker module (optional)
│   │   ├── __init__.py       # BrokerModule class
│   │   ├── service.py        # BrokerService (extends ServiceInterface)
│   │   ├── api/              # Versioned API routers
│   │   │   └── v1.py         # ✅ v1 API router (file pattern - recommended)
│   │   ├── ws/               # Versioned WebSocket routers
│   │   │   └── v1/           # ✅ v1 WS router (directory pattern - required)
│   │   │       └── __init__.py  # BrokerWsRouters class
│   │   ├── specs_generated/  # OpenAPI + AsyncAPI specs
│   │   ├── client_generated/ # Python HTTP client
│   │   └── tests/            # Module tests
│   │
│   └── datafeed/             # Datafeed module (optional)
│       ├── __init__.py       # DatafeedModule class
│       ├── service.py        # DatafeedService (extends ServiceInterface)
│       ├── api/              # Versioned API routers
│       │   └── v1.py         # ✅ v1 API router file (extends APIRouterInterface)
│       ├── ws/               # Versioned WebSocket routers
│       │   └── v1/           # ✅ v1 WS router directory
│       │       └── __init__.py  # DatafeedWsRouters class
│       ├── specs_generated/  # OpenAPI + AsyncAPI specs
│       ├── client_generated/ # Python HTTP client
│       └── tests/            # Module tests
│
└── models/                   # Shared Pydantic models (topic-based)
    ├── bars.py               # Bar/candle data models
    ├── broker/               # Broker-specific models
    │   ├── account.py        # Account models
    │   ├── orders.py         # Order models
    │   └── positions.py      # Position models
    ├── common.py             # Common types (TimeFrame, etc.)
    ├── datafeed.py           # Symbol, quote models
    ├── health.py             # Health check models
    └── versioning.py         # Version info models
```

**Key Structure Points**:

- **`api/v1.py`**: Version-specific API router as **file** (or `v1/__init__.py` - both supported)
- **`ws/v1/`**: Version-specific WebSocket router as **directory** (required for generated routers)
- **Flexible API versioning**: API supports both file and directory patterns via `.stem`
- **Required WS directories**: WebSocket versions must be directories
- **No core module**: Health/version functionality provided by `shared/service_interface.py` and `shared/api/api_router_interface.py`
- **APIRouterInterface**: All API routers inherit from this, automatically getting health/version endpoints
- **WsRouterInterface**: Is `list[WsRouteInterface]`, allowing multiple WS routers per version

---

## Module System

### Module Lifecycle

```
1. Discovery    → registry.auto_discover(modules_dir)
2. Registration → registry.register(ModuleClass, "module_name")
3. Filtering    → registry.set_enabled_modules(["broker", "datafeed"])
4. Loading      → registry.get_enabled_modules()  # Lazy instantiation
5. App Wrapping → ModuleApp(module)  # Creates FastAPI apps per version
6. Mounting     → main_app.mount(f"/api/{version}/{module.name}", api_app)
```

### Module Implementation Example

```python
# modules/broker/__init__.py
from pathlib import Path
from trading_api.shared import Module

class BrokerModule(Module):
    """Broker module - Trading operations."""

    @property
    def module_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def tags(self) -> list[dict[str, str]]:
        return [
            {
                "name": "broker",
                "description": "Broker operations (orders, positions, executions)",
            }
        ]

# modules/broker/service.py
from trading_api.shared.service_interface import ServiceInterface

class BrokerService(ServiceInterface):
    """Broker business logic."""

    def __init__(self, module_dir: Path):
        super().__init__(module_dir)

# modules/broker/api/v1.py (FILE, not directory)
from trading_api.shared.api import APIRouterInterface
from trading_api.models.broker.orders import Order, OrderResponse

class BrokerApi(APIRouterInterface):
    """Broker API v1.

    Automatically provides: /health, /versions, /version
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        @self.post("/orders", response_model=OrderResponse)
        async def create_order(order: Order) -> OrderResponse:
            return await self.service.create_order(order)

# modules/broker/ws/v1/__init__.py (DIRECTORY with __init__.py)
from trading_api.shared.ws import WsRouterInterface

class BrokerWsRouters(WsRouterInterface):
    """Broker WebSocket v1 routers."""

    def __init__(self, service: WsRouteService):
        self.generate_routers(__file__)

        from .ws_generated import OrderWsRouter, PositionWsRouter

        order_router = OrderWsRouter(route="orders", service=service)
        position_router = PositionWsRouter(route="positions", service=service)

        super().__init__([order_router, position_router], service=service)
```

**URL Results After Mounting**:

| Module Route (defined) | Mount Point (factory) | Final URL                    |
| ---------------------- | --------------------- | ---------------------------- |
| `/health`              | `/api/v1/broker`      | `/api/v1/broker/health`      |
| `/versions`            | `/api/v1/broker`      | `/api/v1/broker/versions`    |
| `/orders`              | `/api/v1/broker`      | `/api/v1/broker/orders`      |
| `/orders/{id}`         | `/api/v1/broker`      | `/api/v1/broker/orders/{id}` |

**Pattern**:

- Module API router: `prefix=""` (routes at root level)
- Extends `APIRouterInterface` (gets automatic health/version endpoints)
- Factory mounts at: `/api/{version}/{module.name}`
- Service extends `Service` base class (gets version metadata)
- Result: Clean, consistent URLs with automatic health/version support

### URL Structure

| Module   | Version | Mount Point        | Module Route | Final URL                         |
| -------- | ------- | ------------------ | ------------ | --------------------------------- |
| Broker   | v1      | `/api/v1/broker`   | `/health`    | `/api/v1/broker/health` (auto)    |
| Broker   | v1      | `/api/v1/broker`   | `/versions`  | `/api/v1/broker/versions` (auto)  |
| Broker   | v1      | `/api/v1/broker`   | `/version`   | `/api/v1/broker/version` (auto)   |
| Broker   | v1      | `/api/v1/broker`   | `/orders`    | `/api/v1/broker/orders`           |
| Broker   | v1      | `/api/v1/broker`   | `/ws`        | `/api/v1/broker/ws` (WebSocket)   |
| Broker   | v2      | `/api/v2/broker`   | `/health`    | `/api/v2/broker/health` (auto)    |
| Datafeed | v1      | `/api/v1/datafeed` | `/health`    | `/api/v1/datafeed/health` (auto)  |
| Datafeed | v1      | `/api/v1/datafeed` | `/config`    | `/api/v1/datafeed/config`         |
| Datafeed | v1      | `/api/v1/datafeed` | `/ws`        | `/api/v1/datafeed/ws` (WebSocket) |

Routes marked "(auto)" are automatically provided by `APIRouterInterface` inheritance.

---

## Application Factory

### ModularApp Class

The `ModularApp` class extends FastAPI with module management:

```python
class ModularApp(FastAPI):
    """FastAPI with integrated module and WebSocket tracking."""

    def __init__(self, modules: list[Module], base_url: str, **kwargs):
        self.base_url = base_url
        self._modules_apps = [ModuleApp(module) for module in modules]

        super().__init__(
            openapi_url=f"{base_url}/openapi.json",
            docs_url=f"{base_url}/docs",
            openapi_tags=[...],
            **kwargs
        )

        for module_app in self._modules_apps:
            for api_app in module_app.api_versions:
                mount_path = f"{self.base_url}/{api_app.version}/{module_app.module.name}"
                self.mount(mount_path, api_app)

    def openapi(self) -> dict[str, Any]:
        """Generate merged OpenAPI schema from all modules."""
        # Merges paths, components from all mounted module apps

    def asyncapi(self) -> dict[str, Any]:
        """Generate merged AsyncAPI schema from all modules."""
        # Merges channels, components from all module WebSocket apps

    @property
    def modules_apps(self) -> list[ModuleApp]:
        """Get all module app wrappers."""
        return self._modules_apps
```

### ModuleApp Wrapper

```python
class ModuleApp:
    """Wraps a module and creates versioned FastAPI/WebSocket apps."""

    def __init__(self, module: Module):
        self.module = module
        self.versions: dict[str, tuple[FastAPI, FastWSAdapter | None]] = {}

        for version, api_router in module.api_routers.items():
            api_app = FastAPI(
                title=f"{module.name.title()} API",
                version=version,
                openapi_tags=module.tags,
            )
            api_app.include_router(api_router)

            ws_app: FastWSAdapter | None = None
            if module.ws_routers:
                ws_app = FastWSAdapter(...)

                for version, ws_routers in module.ws_routers.items():
                    for ws_router in ws_routers:
                        ws_app.include_router(ws_router)

                @api_app.websocket("/ws")
                async def websocket_endpoint(client):
                    await ws_app.serve(client)

            self.versions[version] = (api_app, ws_app)

    @property
    def api_versions(self) -> list[FastAPI]:
        return [v[0] for v in self.versions.values()]

    @property
    def ws_versions(self) -> list[FastWSAdapter]:
        return [v[1] for v in self.versions.values() if v[1] is not None]
```

### Factory Pattern

```python
class AppFactory:
    """Factory for creating ModularApp applications."""

    def create_app(
        self,
        enabled_module_names: list[str] | None = None
    ) -> ModularApp:
        """Create app with selective module loading."""
        self.registry.clear()
        self.registry.auto_discover(self.modules_dir)
        self.registry.set_enabled_modules(enabled_module_names)

        enabled_modules = self.registry.get_enabled_modules()

        app = ModularApp(
            modules=enabled_modules,
            base_url="/api",
            title="Trading API",
            version="1.0.0",
        )

        return app
```

### Usage Examples

```python
factory = AppFactory()

app = factory.create_app()  # Load all modules
app = factory.create_app(enabled_module_names=["broker", "datafeed"])  # Specific modules
app = factory.create_app(enabled_module_names=["broker"])  # Single module
```

---

## Module Structure

### Anatomy of a Module

Each module follows this structure:

```
modules/{module_name}/
├── __init__.py              # {ModuleName}Module class (extends Module ABC)
├── service.py               # Business logic (extends ServiceInterface base class)
├── api/                     # Versioned REST API routers
│   └── v1.py                # ✅ v1 API router (file pattern - recommended for API)
├── ws/                      # Versioned WebSocket routers (optional)
│   └── v1/                  # ✅ v1 WS router (directory pattern - required for WS)
│       ├── __init__.py      # Exports WsRouterInterface subclass
│       └── ws_generated/    # Generated routers
├── specs_generated/         # Generated API specifications
│   ├── {module}_v1_openapi.json
│   └── {module}_v1_asyncapi.json
├── client_generated/        # Generated Python HTTP client
│   ├── {module}_v1_client.py
│   └── __init__.py
└── tests/                   # Module-specific tests
    ├── test_api.py
    ├── test_service.py
    └── test_ws.py
```

**Key Structure Points**:

- **`api/v1.py`**: API router as **file** (recommended, though directories also work via `.stem`)
- **`ws/v1/`**: WebSocket router as **directory** with `__init__.py` (required for generated routers)
- **Versioning patterns**: API flexible (file or directory), WS strict (directory only)
- **APIRouterInterface**: All API routers extend this for automatic health/version endpoints
- **ServiceInterface**: All services extend this base class for version metadata and health checks
- **WsRouterInterface**: List-based pattern (`extends list[WsRouteInterface]`) supporting multiple WS routers per version

**Understanding WsRouterInterface**:

`WsRouterInterface` extends `list[WsRouteInterface]`, which means:

```python
# Each version maps to a WsRouterInterface, which IS a list
ws_routers: dict[str, WsRouterInterface] = {
    "v1": WsRouterInterface([router1, router2, router3], service=service)
}

# You can iterate directly over it
for ws_router in module.ws_routers["v1"]:  # WsRouterInterface is a list!
    ws_app.include_router(ws_router)

# Actual usage in broker module
class BrokerWsRouters(WsRouterInterface):  # Inherits from list!
    def __init__(self, service: WsRouteService):
        order_router = OrderWsRouter(route="orders", service=service)
        position_router = PositionWsRouter(route="positions", service=service)

        # Pass list to parent constructor
        super().__init__([order_router, position_router], service=service)
```

This design allows each module version to have **multiple WebSocket routers** (orders, positions, executions, etc.) that are managed as a cohesive unit.

### Module Creation Checklist

When creating a new module:

- [ ] Create `modules/{module_name}/` directory
- [ ] Implement `{ModuleName}Module` class extending `Module` ABC
- [ ] Create `service.py` extending `ServiceInterface` base class
- [ ] Create `api/v1.py` **file** extending `APIRouterInterface` with `prefix=""`
- [ ] (Optional) Create `ws/v1/` **directory** with `__init__.py` extending `WsRouterInterface`
- [ ] Add module tests in `tests/` directory
- [ ] Verify module with `make test-module-{module_name}`

**Required Base Classes**:

- **Module** → Extend `trading_api.shared.module_interface.Module` (ABC)
- **ServiceInterface** → Extend `trading_api.shared.service_interface.ServiceInterface` (ABC)
- **API Router** → Extend `trading_api.shared.api.api_router_interface.APIRouterInterface`
- **WebSocket Router** → Extend `trading_api.shared.ws.ws_route_interface.WsRouterInterface` (list-based)

---

## WebSocket Architecture

### Module-Scoped WebSocket Apps

Each module with real-time features creates its **own FastWSAdapter** via `ModuleApp`:

```python
# In ModuleApp.__init__()
if module.ws_routers:
    ws_app = FastWSAdapter(
        title=f"{module.name.title()} WebSockets",
        description=f"Real-time WebSocket app for {module.name} module",
        version=version,
        asyncapi_url="/ws/asyncapi.json",
        heartbeat_interval=30.0,
        max_connection_lifespan=3600.0,
    )

    for version, ws_routers in module.ws_routers.items():
        for ws_router in ws_routers:
            ws_app.include_router(ws_router)

    @app.websocket("/ws")
    async def websocket_endpoint(client):
        await ws_app.serve(client)
```

### WebSocket URL Structure

| Module   | WebSocket Endpoint    | AsyncAPI Docs                  |
| -------- | --------------------- | ------------------------------ |
| Broker   | `/api/v1/broker/ws`   | `/api/v1/broker/ws/asyncapi`   |
| Datafeed | `/api/v1/datafeed/ws` | `/api/v1/datafeed/ws/asyncapi` |

### WsRouterInterface and WsRouteService

**WsRouterInterface** is `list[WsRouteInterface]`:

```python
# shared/ws/ws_route_interface.py
class WsRouterInterface(list[WsRouteInterface]):
    """Collection of WebSocket routers for a module version."""

    def __init__(self, *args, service: ServiceInterface, **kwargs):
        super().__init__(*args, **kwargs)
        self._service = service

    def generate_routers(self, ws_file: str) -> None:
        """Generate WebSocket routers from type aliases."""
```

**WsRouteService Protocol** for topic lifecycle:

```python
class WsRouteService(ServiceInterface):
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start generating data for topic (first subscriber)."""

    def remove_topic(self, topic: str) -> None:
        """Stop generating data for topic (last unsubscribe)."""
```

**Reference Counting Pattern**:

```python
topic_trackers: dict[str, int] = {}

async def subscribe(topic: str):
    if topic not in topic_trackers:
        topic_trackers[topic] = 0
        await service.create_topic(topic)
    topic_trackers[topic] += 1

async def unsubscribe(topic: str):
    topic_trackers[topic] -= 1
    if topic_trackers[topic] == 0:
        service.remove_topic(topic)
        del topic_trackers[topic]
```

---

## Code Generation

### Per-Module Spec Generation

Each module generates its own specifications:

```python
module_app.gen_specs_and_clients(clean_first=False)
```

**Output**:

```
modules/{module}/
├── specs_generated/
│   ├── {module}_v1_openapi.json    # Module's v1 REST API spec
│   └── {module}_v1_asyncapi.json   # Module's v1 WebSocket spec
└── client_generated/
    └── {module}_v1_client.py       # Generated Python client
```

### Merged Specifications

The main app merges all module specs:

```python
main_app.openapi()  # → /api/openapi.json
main_app.asyncapi()  # → /api/ws/asyncapi.json
```

### WebSocket Router Generation

WebSocket routers are defined in versioned directories:

```python
class BrokerWsRouters(WsRouterInterface):
    """Broker WebSocket v1 routers."""

    def __init__(self, service: WsRouteService):
        self.generate_routers(__file__)

        from .ws_generated import OrderWsRouter, PositionWsRouter

        order_router = OrderWsRouter(route="orders", service=service)
        position_router = PositionWsRouter(route="positions", service=service)

        super().__init__([order_router, position_router], service=service)
```

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

Run modules in separate processes with nginx routing:

```bash
make backend-manager-start  # Uses dev-config.yaml
```

**Configuration** (`backend/dev-config.yaml`):

```yaml
servers:
  - module: broker
    host: 127.0.0.1
    port: 8001
  - module: datafeed
    host: 127.0.0.1
    port: 8002

nginx:
  listen_port: 8000
  routing_strategy: "path"
```

**Architecture**:

```
Client → Nginx (8000) → /api/v1/broker/*    → Broker (8001)
                      → /api/v1/datafeed/*  → Datafeed (8002)
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
from trading_api.app_factory import AppFactory

factory = AppFactory()
app = factory.create_app(enabled_module_names=["broker"])

uvicorn.run(app, host="0.0.0.0", port=8002)
```

### 4. Multi-Process Deployment with Backend Manager (Production)

For production workloads, the **Backend Manager** orchestrates multiple module processes with an nginx gateway for load balancing and routing.

**Configuration**: `backend/dev-config.yaml`

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
  # Broker operations server
  broker:
    port: 8001
    instances: 1
    modules:
      - broker
    reload: true

  # Market data server
  datafeed:
    port: 8002
    instances: 1
    modules:
      - datafeed
    reload: true

# WebSocket routing strategy
websocket:
  routing_strategy: "path" # "query_param" or "path"
  query_param_name: "type" # Used when routing_strategy is "query_param"

# Module to server mapping for WebSocket routing
websocket_routes:
  broker: broker # /api/v1/broker/ws → broker server
  datafeed: datafeed # /api/v1/datafeed/ws → datafeed server
```

**Commands**:

```bash
# Start all configured servers + nginx
make backend-dev-multi

# Check status of all processes
make backend-status

# View logs
make backend-logs          # All server logs
make backend-logs-nginx    # Nginx logs only

# Stop all processes
make backend-stop

# Restart all processes
make backend-restart
```

**Architecture**:

```
Client Requests
    ↓
nginx Gateway (port 8000)
    ├─→ /api/v1/broker/*   → Broker Process (port 8001)
    ├─→ /api/v1/datafeed/* → Datafeed Process (port 8002)
    └─→ WebSocket routing based on path or query param
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

- **Process Isolation**: Module crashes don't affect other modules
- **Independent Scaling**: Run multiple instances of heavy modules
- **Resource Management**: Apply CPU/memory limits per process
- **Zero-Downtime Deploys**: Rolling restarts per module
- **Automatic Nginx Config**: Backend Manager generates nginx.conf from dev-config.yaml
- **PID Tracking**: Graceful process management and cleanup

**Generated Nginx Configuration**: The Backend Manager automatically generates `nginx-dev.conf` with:

- Upstream server definitions for each module
- Location-based routing for REST endpoints
- WebSocket upgrade headers and routing
- Proper proxy headers for backend communication

See [BACKEND_MANAGER_GUIDE.md](BACKEND_MANAGER_GUIDE.md) for complete deployment guide including:

- Detailed configuration file reference
- Process management commands
- Nginx routing strategies
- Production deployment patterns
- Troubleshooting guide

---

## Testing Strategy

### Module Isolation

Each module has independent test fixtures:

```python
@pytest.fixture
def broker_app():
    """Broker module app only."""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])

@pytest.fixture
def broker_client(broker_app):
    """Test client for broker module."""
    return TestClient(broker_app)
```

### Test Categories

```bash
# Module-specific tests
make test-module-broker      # Broker module only
make test-module-datafeed    # Datafeed module only

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

## Quick Reference

### Terminology Consistency Table

Use these exact names when working with the modular architecture:

| Concept            | Correct Class Name   | File Location                        | Import Path                                                                  |
| ------------------ | -------------------- | ------------------------------------ | ---------------------------------------------------------------------------- |
| Service base class | `ServiceInterface`   | `shared/service_interface.py`        | `from trading_api.shared.service_interface import ServiceInterface`          |
| API router base    | `APIRouterInterface` | `shared/api/api_router_interface.py` | `from trading_api.shared.api.api_router_interface import APIRouterInterface` |
| WS router base     | `WsRouterInterface`  | `shared/ws/ws_route_interface.py`    | `from trading_api.shared.ws.ws_route_interface import WsRouterInterface`     |
| Module base class  | `Module`             | `shared/module_interface.py`         | `from trading_api.shared.module_interface import Module`                     |
| WS route service   | `WsRouteService`     | `shared/ws/ws_route_interface.py`    | `from trading_api.shared.ws.ws_route_interface import WsRouteService`        |

### Version Pattern Reference

| Component         | Pattern                | Example                                  | Notes                               |
| ----------------- | ---------------------- | ---------------------------------------- | ----------------------------------- |
| API Router        | File or Directory      | `api/v1.py` or `api/v1/__init__.py`      | Both supported via `.stem` property |
| WebSocket Router  | Directory only         | `ws/v1/__init__.py`                      | Required for generated routers      |
| Version Discovery | Auto-detected          | Scans `api/` and `ws/` dirs              | Uses `d.stem.startswith("v")`       |
| Enforcement       | Import-time validation | Module loading fails if wrong base class | See section 7                       |

### Module Structure Quick Copy

```python
# modules/mymodule/__init__.py
from pathlib import Path
from trading_api.shared.module_interface import Module

class MymoduleModule(Module):
    @property
    def module_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def tags(self) -> list[dict[str, str]]:
        return [{"name": "mymodule", "description": "My module description"}]

# modules/mymodule/service.py
from pathlib import Path
from trading_api.shared.service_interface import ServiceInterface

class MymoduleService(ServiceInterface):
    def __init__(self, module_dir: Path) -> None:
        super().__init__(module_dir)
        # Add custom service logic here

# modules/mymodule/api/v1.py
from trading_api.shared.api.api_router_interface import APIRouterInterface

class MymoduleApi(APIRouterInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Auto-registers /health, /versions, /version

        @self.get("/example")
        async def example_endpoint():
            return {"message": "Hello from mymodule"}
```

---

## Related Documentation

- **[ARCHITECTURE.md](../../ARCHITECTURE.md)** - Overall system architecture
- **[backend/README.md](../README.md)** - Backend setup and reference
- **[MODULAR_VERSIONNING.md](./MODULAR_VERSIONNING.md)** - API versioning strategy
- **[BACKEND_WEBSOCKETS.md](./BACKEND_WEBSOCKETS.md)** - WebSocket implementation guide
- **[SPECS_AND_CLIENT_GEN.md](./SPECS_AND_CLIENT_GEN.md)** - Spec and client generation
- **[WS_ROUTERS_GEN.md](./WS_ROUTERS_GEN.md)** - WebSocket router generation
- **[docs/DOCUMENTATION-GUIDE.md](../../docs/DOCUMENTATION-GUIDE.md)** - Documentation index

---

## Summary

The modular backend architecture provides:

- **ABC-Based Design** - All modules extend `Module` abstract base class
- **Self-Contained Apps** - Each module owns complete FastAPI app per version
- **Auto-Discovery** - Modules registered automatically via convention
- **Lazy Loading** - Resources initialized only when needed
- **Independent Testing** - Test modules in complete isolation
- **Selective Deployment** - Run only needed modules
- **Horizontal Scaling** - Multi-process deployment with nginx
- **Automatic Specs** - OpenAPI/AsyncAPI per module + merged
- **Type Safety** - ABC enforcement at instantiation time

**Architectural Patterns**:

- **Flexible API Versioning**: API routers support both file (`api/v1.py`) and directory (`api/v1/`) patterns via `.stem`
- **Strict WS Versioning**: WebSocket routers require directories (`ws/v1/`) for generated routers
- **ABC Pattern**: Uses Python's `abc.ABC`, not `typing.Protocol`
- **List-Based WS**: `WsRouterInterface` extends `list[WsRouteInterface]` for multiple routers per version
- **Auto Health/Version**: All modules get health/version endpoints via `APIRouterInterface` inheritance
- **Enforcement**: Module loading validates base class inheritance at import time

Modules are **independently deployable versioned applications** that compose into a cohesive system.
