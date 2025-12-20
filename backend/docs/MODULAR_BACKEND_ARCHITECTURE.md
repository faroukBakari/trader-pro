# Modular Backend Architecture

**Status**: ✅ Production Ready  
**Last Updated**: November 30, 2025  
**Version**: 5.3.0

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
    @classmethod
    def module_dir(cls) -> Path:
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
# Start only your new module (all versions)
ENABLED_MODULES=my_module make dev

# Start only specific version
ENABLED_MODULES=my_module:v1 make dev

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

    @classmethod
    @abstractmethod
    def module_dir(cls) -> Path:
        """Module's directory path.

        Must be a class method because it's used during version discovery
        and service class loading, which occur before instantiation.
        """

    def __init__(self, versions: list[str] | None = None):
        # Auto-discover versions from api/ and ws/ directories
        if versions is None:
            versions = self._discover_versions()

        self._versions = versions

        # Import shared service (version-agnostic)
        service_class = self._service_class()
        self._service = service_class(self.module_dir())

        # Import version-specific routers
        self._api_routers: dict[str, APIRouterInterface] = {}
        self._ws_routers: dict[str, WsRouterBase] = {}

        for version in versions:
            # Import from api/v1.py (file)
            self._api_routers[version] = self._import_api_routers_for_version(version)
            # Import from ws/v1/__init__.py (directory) - optional
            ws_router = self._import_ws_routers_for_version(version)
            if ws_router is not None:
                self._ws_routers[version] = ws_router

    @property
    def name(self) -> str:
        """Unique module identifier (e.g., 'broker', 'datafeed')"""
        return self.module_dir().name

    @property
    def service(self) -> ServiceInterface:
        """Module's business logic service (extends ServiceInterface base class)"""

    @property
    def api_routers(self) -> dict[str, APIRouterInterface]:
        """API routers organized by version (all extend APIRouterInterface)"""

    @property
    def ws_routers(self) -> dict[str, WsRouterBase]:
        """WebSocket routers organized by version (WsRouterBase extends list[WsRouteFeature])"""

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

#### Class Methods vs Instance Methods

The Module ABC uses a hybrid approach with both class methods and instance methods:

**Class Methods** (called before or during instantiation):

- `module_dir()` - Returns module directory path, used by version discovery
- `_discover_versions()` - Scans api/ and ws/ directories for available versions
- `_get_import_path()` - Constructs import path for dynamic module loading
- `_service_class()` - Imports and returns the service class (not instance)

**Instance Methods** (require instantiated module):

- `_import_api_routers_for_version()` - Imports API routers (needs service instance)
- `_import_ws_routers_for_version()` - Imports WebSocket routers (needs service instance)

**Rationale**: Version discovery and service class loading must occur before instance state is available. The `module_dir()` class method enables these operations to work with the class itself rather than requiring an instance. The service is then instantiated in `__init__()` and passed to router imports.

**Reference**: See `backend/src/trading_api/shared/module_interface.py` for complete implementation.

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

### 3. ServiceInterface Base Class with Version Discovery and Provider Resolution

The `ServiceInterface` base class provides **automatic version discovery**, metadata, and **provider capability resolution**:

```python
# shared/service_interface.py
class ServiceInterface(ABC):
    def __init__(
        self,
        module_dir: Path,
        *,  # Force keyword-only
        providers: list["Provider"] | None = None,
    ) -> None:
        """Initialize service.

        Args:
            module_dir: Module directory path
            providers: Provider instances for required capabilities

        Raises:
            CommonException: If required capability not satisfied
        """
        super().__init__()
        self.module_dir = module_dir
        self._providers = providers or []

        # Build capability map and fail-fast validate
        self._capability_map: dict[str, "Provider"] = {}
        self._resolve_capabilities()

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

    @classmethod
    @abstractmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return required capabilities for this service.

        [CLASSMETHOD]: Static declaration for app startup analysis.

        Returns:
            List of capability requirements

        Examples:
            >>> AuthService.capabilities()
            [CapabilitySpec(name="auth")]
        """
        ...

    def _resolve_capabilities(self) -> None:
        """Resolve and cache capability → provider mapping.

        [FAIL-FAST]: Validates at initialization, not at request time.

        Raises:
            CommonException: If required capability not found
        """
        from trading_api.models.exceptions import CommonException

        required_capabilities = self.capabilities()

        for req_cap in required_capabilities:
            matched = False

            for provider in self._providers:
                # Check if provider offers matching capability
                for prov_cap in provider.capabilities():
                    if req_cap.matches(prov_cap):
                        self._capability_map[req_cap.name] = provider
                        matched = True
                        break

                if matched:
                    break

            if not matched:
                raise CommonException(
                    code="COMMON_CAPABILITY_NOT_FOUND",
                    message=(
                        f"Service '{self.module_name}' requires capability "
                        f"'{req_cap}' but no provider found. "
                        f"Available providers: {[p.name for p in self._providers]}"
                    ),
                )

    def _get_capability_provider(self, capability_name: str) -> "Provider":
        """Get provider for specific capability (cached lookup).

        Args:
            capability_name: Name of capability to get

        Returns:
            Provider instance

        [PERFORMANCE]: O(1) lookup after initialization.
        """
        provider = self._capability_map.get(capability_name)
        if provider is None:
            raise RuntimeError(
                f"Capability '{capability_name}' not initialized. "
                "This should never happen - validation should occur at init."
            )
        return provider
```

**Benefits**:

- Auto-discovery from directory structure
- Convention-based versioning
- Automatic API metadata generation
- **Fail-fast provider validation** at service initialization
- **O(1) provider lookup** via cached capability map
- **Type-safe capability matching** with CapabilitySpec

**Reference**: See `backend/src/trading_api/shared/service_interface.py` for complete implementation.

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
└── v1/                # ✅ MUST be directory for WsRouterBase subclass
    └── __init__.py    # Contains WsRouterBase subclass with WsRouter[T,D] instances
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
        # ws_routers is dict[str, WsRouterBase]
        # WsRouterBase extends list[WsRouteFeature]
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
def _import_ws_routers_for_version(self, version: str) -> WsRouterBase | None:
    """Import WebSocket routers for a specific version."""
    try:
        ws_module = importlib.import_module(f"...ws.{version}")

        # Scan for WsRouterBase subclass
        for attr_name in dir(ws_module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(ws_module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, WsRouterBase)  # ← VALIDATION
                and attr is not WsRouterBase
            ):
                return attr(service=self._service)

        return None  # WebSocket is optional
    except ImportError:
        return None  # WebSocket support not required
```

**What This Enforces**:

- ✅ WS routers **should** inherit from `WsRouterBase` if present
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

### Provider System Integration

The modular architecture integrates a **pluggable provider/capability system** for external integrations (authentication, broker APIs, data feeds). Providers are auto-discovered and injected into services that declare capability requirements.

**Provider-Enabled Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                      AppFactory                              │
│  ┌────────────────────┐         ┌────────────────────┐     │
│  │  ModuleRegistry    │         │ ProviderRegistry   │     │
│  │  - auto_discover() │         │ - auto_discover()  │     │
│  │  - get_modules()   │         │ - get_providers()  │     │
│  └────────────────────┘         └────────────────────┘     │
│           │                               │                 │
│           │  1. Resolve capabilities      │                 │
│           │  from service classes         │                 │
│           │                               │                 │
│           │  2. Request providers ────────┤                 │
│           │                               │                 │
│           │  3. Instantiate modules ◄─────┤                 │
│           │     with providers            │                 │
└───────────┼───────────────────────────────┼─────────────────┘
            │                               │
            ▼                               ▼
    ┌──────────────┐              ┌─────────────────┐
    │    Module    │              │    Provider     │
    │  __init__(   │              │  - capabilities │
    │   providers) │              │  - verify_token │
    └──────┬───────┘              └─────────────────┘
           │                               ▲
           │  4. Inject providers          │
           ▼                               │
    ┌──────────────┐                      │
    │   Service    │                      │
    │  __init__(   │──────────────────────┘
    │   providers) │   5. Cache capability map
    │              │      (fail-fast validation)
    └──────────────┘
```

**Two-Phase Loading Process:**

The AppFactory uses a two-phase loading pattern to resolve provider dependencies:

1. **Phase 1 - Discovery**: Auto-discover module and provider classes (no instantiation)
2. **Phase 2 - Static Analysis**: Use `ServiceInterface.capabilities()` classmethod to determine required capabilities
3. **Phase 3 - Provider Loading**: Get provider instances matching required capabilities (lazy-loading with lifecycle hooks)
4. **Phase 4 - Module Instantiation**: Create modules with providers injected via `Module.__init__(providers=...)`

**Key Integration Points:**

- **`ServiceInterface.capabilities()`**: Classmethod declaring required capabilities (e.g., `[CapabilitySpec(name="auth")]`)
- **`ServiceInterface.__init__(providers=...)`**: Receives provider instances, validates at initialization (fail-fast)
- **`ServiceInterface._get_capability_provider(name)`**: O(1) cached lookup for provider access
- **`Module.__init__(providers=...)`**: Keyword-only parameter passes providers to service initialization

**Example - AuthService with Provider:**

```python
class AuthService(ServiceInterface):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]  # Requires auth capability

    @property
    def auth_provider(self) -> AuthCapability:
        """Get auth capability provider (cached lookup)."""
        provider = self._get_capability_provider("auth")
        if not isinstance(provider, AuthCapability):
            raise TypeError(f"Expected AuthCapability, got {type(provider).__name__}")
        return provider

    async def authenticate_google_user(self, id_token: str) -> TokenResponse:
        # Use injected provider instead of direct Google API call
        claims = await self.auth_provider.verify_token(id_token)
        # ... rest of authentication logic
```

**Reference**: See `backend/docs/PROVIDER-SYSTEM.md` for complete provider implementation guide.

### Directory Structure

```
backend/src/trading_api/
├── app_factory.py              # Application factory and ModularApp
├── main.py                     # Entry point (creates app via factory)
│
├── shared/                     # Shared infrastructure (always loaded)
│   ├── module_interface.py    # Module ABC definition
│   ├── module_registry.py     # Module discovery and registration
│   ├── provider_interface.py  # Provider ABC definition
│   ├── provider_registry.py   # Provider discovery and lazy-loading
│   ├── service_interface.py   # ServiceInterface (version discovery, capability resolution)
│   ├── client_generation_service.py  # Python client generation
│   ├── api/                   # Shared API utilities
│   │   └── api_router_interface.py  # APIRouterInterface (auto health/version)
│   ├── middleware/            # Shared middleware
│   │   └── auth.py           # Stateless JWT validation (public key only)
│   ├── plugins/               # FastWS adapter and plugins
│   ├── ws/                    # WebSocket framework
│   │   ├── fastws_adapter.py  # FastWSAdapter integration
│   │   ├── ws_router.py       # WsRouterBase (list[WsRouteFeature]), WsRouteService
│   │   └── generic_route.py   # WsRouter[TRequest, TData] generic class
│   └── templates/             # Code generation templates
│
├── modules/                   # Feature modules (pluggable)
│   ├── auth/                 # Auth module (optional)
│   │   ├── __init__.py       # AuthModule class
│   │   ├── service.py        # AuthService (extends ServiceInterface)
│   │   ├── repository.py     # User and refresh token repositories
│   │   ├── api/              # Versioned API routers
│   │   │   └── v1.py         # ✅ v1 API router (file pattern)
│   │   ├── specs_generated/  # OpenAPI specs
│   │   ├── client_generated/ # Python HTTP client
│   │   └── tests/            # Module tests
│   │
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
- **WsRouterBase**: Is `list[WsRouteFeature]`, allowing multiple WS routers per version

---

## Module System

### Module Lifecycle

```
1. Discovery              → registry.auto_discover(modules_dir)
2. Registration           → registry.register(ModuleClass, "module_name")
3. Capability Resolution  → factory._resolve_capabilities(enabled_modules)  # Static analysis
4. Provider Discovery     → provider_registry.auto_discover()
5. Provider Instantiation → provider_registry.get_providers(capabilities)  # Lazy-loading with lifecycle hooks
6. Module Loading         → registry.get_modules(module_names, providers)  # Filtering + lazy instantiation with providers
7. Service Validation     → service._resolve_capabilities()  # Fail-fast validation in each service
8. App Wrapping           → ModuleApp(module)  # Creates FastAPI apps per version
9. Mounting               → main_app.mount(f"/api/{version}/{module.name}", api_app)
```

**Key Points:**

- **Two-Phase Loading**: Classes discovered before instances created (prevents circular dependencies)
- **Fail-Fast Validation**: Services validate capabilities at initialization, not request time
- **Lazy Provider Loading**: Providers instantiated only when first needed, with thread-safe locking

**Reference**: See `backend/src/trading_api/app_factory.py` lines 139-191 for complete implementation.

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
from trading_api.models import PlacedOrder, OrderSubscriptionRequest, Position, PositionSubscriptionRequest
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.ws_router import WsRouterBase, WsRouteService

class BrokerWsRouters(WsRouterBase):
    """Broker WebSocket v1 routers."""

    def __init__(self, service: WsRouteService):
        module_name = "broker"

        # Direct generic type instantiation
        order_router = WsRouter[OrderSubscriptionRequest, PlacedOrder](
            route="orders", tags=[module_name], service=service
        )
        position_router = WsRouter[PositionSubscriptionRequest, Position](
            route="positions", tags=[module_name], service=service
        )

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

        # Get modules to enable (None = all modules, list = specific modules)
        enabled_modules = self.registry.get_modules(enabled_module_names)

        app = ModularApp(
            modules=enabled_modules,
            base_url="/api",
            title="Trading API",
            version="1.0.0",
        )

        return app
```

### Exception Handler Registration

The factory registers global exception handlers on the `ModularApp` instance to provide unified error handling across all modules:

```python
from trading_api.shared.exception_handlers import register_exception_handlers

# In AppFactory.create_app()
modular_app = ModularApp(...)
register_exception_handlers(modular_app)
```

This enables:

- **Consistent error responses**: All exceptions converted to structured JSON format
- **Automatic status code mapping**: Error codes mapped to appropriate HTTP status
- **WebSocket error handling**: Exceptions translated to proper close codes
- **Clean logging**: Project-only backtraces with external library frames filtered

Exception handlers are also registered on mounted sub-apps for routing completeness, but duplicate logging is prevented via request state tracking.

See [ERROR-MANAGEMENT.md](./ERROR-MANAGEMENT.md) for complete error handling patterns and exception hierarchy.

### Usage Examples

```python
factory = AppFactory()

app = factory.create_app()  # Load all modules
app = factory.create_app(enabled_module_names=["broker", "datafeed"])  # Specific modules
app = factory.create_app(enabled_module_names=["broker"])  # Single module
```

#### Registry API Simplification

The module registry uses a **functional API** for module filtering:

- **Single method**: `get_modules(enabled_modules)` replaces three methods
- **Stateless**: No internal state to manage
- **Easier testing**: Direct input/output, no setup required

**Before (old API)**:

```python
registry.set_enabled_modules(["broker"])
modules = registry.get_enabled_modules()
```

**After (current API)**:

```python
modules = registry.get_modules(["broker"])
```

**Benefits**:

- Eliminates two-step workflow
- Functional (no side effects)
- Clearer intent at call site

---

## Module Registry

The `ModuleRegistry` provides centralized, functional module management with lazy instantiation and version selection.

### Version-Specific Module Loading

**[PERFORMANCE]** Modules can be loaded with specific versions to optimize memory and startup time:

```python
# Load specific versions
registry.get_modules(["broker:v1", "datafeed:v2"])

# Mix versioned and all-versions
registry.get_modules(["broker:v1", "datafeed"])  # datafeed loads all versions

# Load all versions (default)
registry.get_modules(["broker"])  # loads all available versions
```

### Module Spec Format

Module specifications use the format `module_name:version`:

- `broker` → Loads all versions (v1, v2, etc.)
- `broker:v1` → Loads only v1
- `broker:v2` → Loads only v2

**[DECISION]**: Version is optional. Omitting version loads all available versions for backward compatibility [performance-vs-convenience tradeoff] [rejected: requiring version - breaks existing configs] [2025-11-20]

### Cache Isolation

The registry maintains separate instances for different version combinations:

```python
broker_v1 = registry.get_modules(["broker:v1"])[0]
broker_v2 = registry.get_modules(["broker:v2"])[0]
broker_all = registry.get_modules(["broker"])[0]

# broker_v1, broker_v2, and broker_all are different instances
# Cache keys: "broker:v1", "broker:v2", "broker"
```

**Reference:** See `backend/src/trading_api/shared/module_registry.py` for implementation details.

---

## Provider/Capability System

The backend implements a **pluggable provider/capability system** for external integrations, enabling services to declare required capabilities (authentication, broker APIs, data feeds) and have matching provider implementations automatically injected at runtime.

### Overview

The provider system decouples service logic from external implementation details through:

- **Capability Declarations**: Services use `capabilities()` classmethod to declare requirements
- **Provider Auto-Discovery**: Providers discovered automatically from `providers/` directory
- **Type-Safe Matching**: `CapabilitySpec` dataclass ensures capability matching correctness
- **Dependency Injection**: AppFactory resolves and injects providers into modules/services
- **Fail-Fast Validation**: Capability requirements validated at app startup, not request time

**Reference**: See `backend/docs/PROVIDER-SYSTEM.md` for complete developer guide including step-by-step provider creation.

### Core Concepts

#### CapabilitySpec - Type-Safe Capability Declaration

```python
from trading_api.models.common import CapabilitySpec

# Service declares: "I need any auth provider"
req = CapabilitySpec(name="auth")

# Provider declares: "I provide auth v1"
prov = CapabilitySpec(name="auth", version="v1")

# Matching: Does provider satisfy service requirement?
req.matches(prov)  # True - version matches or not specified
```

**File**: `backend/src/trading_api/models/common.py`

#### Provider ABC - Base Class for All Providers

```python
from trading_api.shared import Provider

class MyProvider(Provider):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """What this provider offers"""
        return [CapabilitySpec(name="auth")]

    @property
    def name(self) -> str:
        """Provider identifier"""
        return "myprovider"

    # ... implement abstract methods (config, provider_dir)
```

**Convention**: `providers/{name}/__init__.py` exports `{Name}Provider` class (e.g., `GoogleProvider`)

**File**: `backend/src/trading_api/shared/provider_interface.py`

#### AuthCapability - Authentication Contract Interface

```python
from trading_api.capabilities.auth import AuthCapability

class MyProvider(Provider, AuthCapability):
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Implement the auth capability"""
        # Your verification logic
        return {"sub": "user_id", "email": "user@example.com"}
```

**File**: `backend/src/trading_api/providers/capabilities/auth.py`

### Integration Points

#### AppFactory.\_resolve_capabilities() - Static Analysis

```python
def _resolve_capabilities(self, module_names: list[str] | None) -> list[CapabilitySpec]:
    """Resolve required capabilities from module service classes.

    [STATIC ANALYSIS]: No instances created, uses classmethods.
    """
    capabilities: set[CapabilitySpec] = set()

    for module_name in module_names:
        # Get service class (not instance)
        service_class = module_class._service_class()

        # Get capabilities (classmethod, no instance)
        if hasattr(service_class, 'capabilities'):
            capabilities.update(service_class.capabilities())

    return list(capabilities)
```

**File**: `backend/src/trading_api/app_factory.py` lines 139-172

#### ServiceInterface Methods

**capabilities() - Classmethod Declaration**

```python
@classmethod
@abstractmethod
def capabilities(cls) -> list[CapabilitySpec]:
    """Return required capabilities for this service.

    Examples:
        >>> AuthService.capabilities()
        [CapabilitySpec(name="auth")]
    """
    ...
```

**\_get_capability_provider() - Cached Lookup**

```python
def _get_capability_provider(self, capability_name: str) -> "Provider":
    """Get provider for specific capability (O(1) cached lookup).

    [PERFORMANCE]: O(1) lookup after initialization.
    """
    provider = self._capability_map.get(capability_name)
    if provider is None:
        raise RuntimeError(f"Capability '{capability_name}' not initialized.")
    return provider
```

**File**: `backend/src/trading_api/shared/service_interface.py` lines 15-110

### Example - AuthService Using GoogleProvider

**Service Declaration:**

```python
# modules/auth/service.py
from trading_api.models.common import CapabilitySpec
from trading_api.capabilities.auth import AuthCapability

class AuthService(ServiceInterface):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]  # Requires auth capability

    @property
    def auth_provider(self) -> AuthCapability:
        """Get auth capability provider (cached, type-safe lookup)."""
        provider = self._get_capability_provider("auth")

        # Type narrowing
        if not isinstance(provider, AuthCapability):
            raise TypeError(f"Expected AuthCapability, got {type(provider).__name__}")

        return provider

    async def authenticate_google_user(self, id_token: str) -> TokenResponse:
        # Use injected provider instead of direct Google API call
        claims = await self.auth_provider.verify_token(id_token)

        # Extract user info from claims
        google_id = claims["sub"]
        email = claims["email"]
        # ... rest of authentication logic
```

**Provider Implementation:**

```python
# providers/google/__init__.py
from trading_api.shared import Provider
from trading_api.capabilities.auth import AuthCapability

class GoogleProvider(Provider, AuthCapability):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    async def verify_token(self, token: str) -> dict[str, Any]:
        # Verify Google ID token via tokeninfo endpoint
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"id_token": token}
            )

            if resp.status_code != 200:
                raise AuthenticationError(f"Invalid Google token: {resp.text}")

            claims = resp.json()

            # Validate audience and email
            if claims.get("aud") != self.config.client_id:
                raise AuthenticationError("Invalid token audience")

            return claims
```

### File Locations

**Provider Infrastructure:**

- **Provider ABC**: `backend/src/trading_api/shared/provider_interface.py`
- **Provider Registry**: `backend/src/trading_api/shared/provider_registry.py`
- **Auth Capability**: `backend/src/trading_api/providers/capabilities/auth.py`

**Provider Implementations:**

- **GoogleProvider**: `backend/src/trading_api/providers/google/__init__.py`
- **Future Providers**: `providers/local/`, `providers/ibkr/`, etc.

**Models & Configuration:**

- **Shared Models**: `backend/src/trading_api/models/common.py` (CapabilitySpec, ProviderConfig, exceptions)
- **Provider Configs**: `backend/src/trading_api/models/providers/google_oauth_configs.py` (GoogleProviderConfig, etc.)

**Integration:**

- **AppFactory**: `backend/src/trading_api/app_factory.py` (two-phase loading, capability resolution)
- **ServiceInterface**: `backend/src/trading_api/shared/service_interface.py` (provider resolution, cached lookup)
- **Module Interface**: `backend/src/trading_api/shared/module_interface.py` (providers parameter)

### Benefits

- ✅ **Easy Provider Addition**: Follow naming convention, auto-discovered
- ✅ **Test with Mocks**: Inject mock providers in tests (no external API calls)
- ✅ **Clean Separation**: Service logic vs provider implementation decoupled
- ✅ **Type-Safe**: Strict MyPy validation, compile-time error detection
- ✅ **Fail-Fast**: Capability mismatches caught at app startup
- ✅ **Performance**: O(1) provider lookup via cached capability map
- ✅ **Future-Ready**: Architecture supports broker/datafeed providers

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
│       └── __init__.py      # Exports WsRouterBase subclass with WsRouter[T,D] instances
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
- **`ws/v1/`**: WebSocket router as **directory** with `__init__.py` containing `WsRouterBase` subclass
- **Versioning patterns**: API flexible (file or directory), WS strict (directory only)
- **APIRouterInterface**: All API routers extend this for automatic health/version endpoints
- **ServiceInterface**: All services extend this base class for version metadata and health checks
- **WsRouterBase**: List-based pattern (`extends list[WsRouteFeature]`) supporting multiple WS routers per version

**Understanding WsRouterBase**:

`WsRouterBase` extends `list[WsRouteFeature]`, which means:

```python
# Each version maps to a WsRouterBase, which IS a list
ws_routers: dict[str, WsRouterBase] = {
    "v1": BrokerWsRouters(service=service)  # Contains [order_router, position_router]
}

# You can iterate directly over it
for ws_router in module.ws_routers["v1"]:  # WsRouterBase is a list!
    ws_app.include_router(ws_router)

# Actual usage in broker module
class BrokerWsRouters(WsRouterBase):  # Inherits from list!
    def __init__(self, service: WsRouteService):
        order_router = WsRouter[OrderSubscriptionRequest, PlacedOrder](
            route="orders", tags=["broker"], service=service
        )
        position_router = WsRouter[PositionSubscriptionRequest, Position](
            route="positions", tags=["broker"], service=service
        )

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
- [ ] (Optional) Create `ws/v1/` **directory** with `__init__.py` extending `WsRouterBase`
- [ ] Add module tests in `tests/` directory
- [ ] Verify module with `make test-module-{module_name}`

**Required Base Classes**:

- **Module** → Extend `trading_api.shared.module_interface.Module` (ABC)
- **ServiceInterface** → Extend `trading_api.shared.service_interface.ServiceInterface` (ABC)
- **API Router** → Extend `trading_api.shared.api.api_router_interface.APIRouterInterface`
- **WebSocket Router** → Extend `trading_api.shared.ws.ws_router.WsRouterBase` (list-based)

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

### WsRouterBase and WsRouteService

**WsRouterBase** extends `list[WsRouteFeature]`:

```python
# shared/ws/ws_router.py
class WsRouterBase(list[WsRouteFeature]):
    """Collection of WebSocket routers for a module version."""

    def __init__(self, *args: Any, service: ServiceInterface, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._service = service
```

### Dynamic Type Resolution

WebSocket routers use **runtime type introspection** instead of code generation:

```python
# In WsRouter (shared/ws/generic_route.py)
def _resolve_generic_types(self):
    """
    Introspects the class to find the Generic type arguments.
    Uses __orig_bases__ to extract [TRequest, TData] at runtime.
    """
    types = next(iter(getattr(self.__class__, "__orig_bases__", [])), None)
    return get_args(types)  # Returns (RequestType, DataType)
```

**Usage Pattern** (class inheritance required):

```python
# Step 1: Define concrete router class
class OrderRouter(WsRouter[OrderSubscriptionRequest, PlacedOrder]):
    pass

# Step 2: Instantiate in router factory
order_router = OrderRouter(route="orders", tags=[module_name], service=service)
```

**Why Class Inheritance?** The `_resolve_generic_types()` method introspects `__orig_bases__` which only exists on concrete subclasses. Direct generic instantiation (`WsRouter[T, D](...)`) would not preserve type information.

**What This Enables**:

- ✅ Type parameters resolved at runtime (no code generation)
- ✅ Annotations set dynamically for AsyncAPI spec generation
- ✅ Type-safe subscribe/unsubscribe handlers
- ✅ Proper IDE autocomplete via generic type hints

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

### WebSocket Router Pattern

WebSocket routers are defined in versioned directories using direct generic types:

```python
# modules/broker/ws/v1/__init__.py
class BrokerWsRouters(WsRouterBase):
    """Broker WebSocket v1 routers."""

    def __init__(self, service: WsRouteService):
        # Direct generic type instantiation - no code generation
        order_router = WsRouter[OrderSubscriptionRequest, PlacedOrder](
            route="orders", tags=["broker"], service=service
        )
        position_router = WsRouter[PositionSubscriptionRequest, Position](
            route="positions", tags=["broker"], service=service
        )

        super().__init__([order_router, position_router], service=service)
```

---

## Authentication Integration

The platform uses JWT-based authentication with stateless middleware for both REST and WebSocket endpoints.

### Shared Middleware Pattern

Authentication middleware is located in `shared/middleware/auth.py` and is **independent** of the auth module:

- ✅ NO database queries
- ✅ NO private key access (public key only)
- ✅ Stateless validation only
- ✅ Works with REST and WebSocket

**Functions:**

```python
from trading_api.shared.middleware.auth import get_current_user, get_current_user_ws
from trading_api.models.auth import UserData

# REST endpoint authentication
async def get_current_user(request: Request) -> UserData:
    """Validates JWT from cookie and returns user data."""
    # 1. Extract token from cookie
    # 2. Decode JWT with public key (RS256)
    # 3. Validate payload structure
    # 4. Return UserData object

# WebSocket authentication
async def get_current_user_ws(websocket: WebSocket) -> UserData:
    """WebSocket-specific authentication (same process, different exception type)."""
```

### Authenticated Endpoint Pattern

Modules add authentication to endpoints via dependency injection:

```python
from typing import Annotated
from fastapi import Depends
from trading_api.models.auth import UserData
from trading_api.shared.middleware.auth import get_current_user

class BrokerApi(APIRouterInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        @self.get("/orders")
        async def get_orders(
            user_data: Annotated[UserData, Depends(get_current_user)]
        ) -> list[Order]:
            """Get orders for authenticated user."""
            return await self.service.get_user_orders(user_data.user_id)

        @self.post("/orders")
        async def create_order(
            order: Order,
            user_data: Annotated[UserData, Depends(get_current_user)]
        ) -> OrderResponse:
            """Create order for authenticated user."""
            return await self.service.create_order(order, user_data.user_id)
```

**UserData Model:**

```python
class UserData(BaseModel):
    """User data extracted from JWT token."""
    user_id: str
    email: str
    full_name: str | None
    picture: str | None
```

### WebSocket Authentication

WebSocket connections are authenticated automatically via cookies:

```python
from trading_api.shared.middleware.auth import get_current_user_ws

class BrokerWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        # Router automatically validates authentication
        order_router = WsRouter[OrderSubscriptionRequest, PlacedOrder](
            route="orders", tags=["broker"], service=service
        )

        # Access user data in route handler
        @order_router.on_subscribe
        async def handle_subscribe(client: Client, topic: str):
            # Extract user data from connection
            user_data = await get_current_user_ws(client.websocket)
            # Filter data by user_id
            await service.subscribe_user_orders(user_data.user_id, topic)

        super().__init__([order_router], service=service)
```

**Key Points:**

- Browser automatically includes cookies in WebSocket handshake
- No query parameters needed
- Same security as REST endpoints (HttpOnly cookies)
- `get_current_user_ws` middleware validates token

### Cookie-Based Authentication

**Cookie Configuration:**

- **Name:** `access_token`
- **Flags:** `httponly=True, secure=True, samesite="strict"`
- **Expiry:** 5 minutes (matches JWT expiry)

**Security Benefits:**

1. **XSS Protection**: HttpOnly prevents JavaScript access
2. **CSRF Protection**: SameSite=Strict blocks cross-site requests
3. **Automatic Handling**: Browser sends cookies automatically (REST + WebSocket)
4. **No Manual Management**: Frontend never touches access tokens

**CORS Configuration Required:**

```python
# backend/src/trading_api/shared/config.py
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGINS = ["http://localhost:5173"]  # Frontend URL
```

### Auth Module Architecture

The auth module follows the standard modular pattern:

```
modules/auth/
├── __init__.py         # AuthModule class
├── service.py          # AuthService (Google OAuth, JWT generation)
├── repository.py       # User and refresh token repositories
├── api/v1.py          # REST API (/login, /refresh-token, /logout, /me, /introspect)
└── tests/             # 92 tests (repository, service, API, integration)
```

**Endpoints:**

| Endpoint                     | Method | Purpose                           |
| ---------------------------- | ------ | --------------------------------- |
| `/api/v1/auth/login`         | POST   | Authenticate with Google OAuth    |
| `/api/v1/auth/refresh-token` | POST   | Refresh access token              |
| `/api/v1/auth/logout`        | POST   | Logout and revoke refresh token   |
| `/api/v1/auth/me`            | GET    | Get current user info             |
| `/api/v1/auth/introspect`    | GET    | Validate token (for route guards) |

See [auth module documentation](../src/trading_api/modules/auth/README.md) for complete implementation details.

---

## Deployment Modes

### 1. Single-Process Mode (Development)

Run all modules in one process:

```bash
# All modules with all versions
python -m trading_api.main

# Specific modules with all versions
ENABLED_MODULES=broker,datafeed python -m trading_api.main

# Specific modules with specific versions
ENABLED_MODULES=broker:v1,datafeed:v2 python -m trading_api.main

# Mix of versioned and all-versions
ENABLED_MODULES=broker:v1,datafeed python -m trading_api.main
```

Or using make:

```bash
make dev  # Starts with all modules (all versions)

# Selective loading
ENABLED_MODULES=broker,datafeed make dev
ENABLED_MODULES=broker:v1 make dev  # Load only v1
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
| WS router base     | `WsRouterBase`       | `shared/ws/ws_router.py`             | `from trading_api.shared.ws.ws_router import WsRouterBase`                   |
| WS route feature   | `WsRouteFeature`     | `shared/ws/ws_router.py`             | `from trading_api.shared.ws.ws_router import WsRouteFeature`                 |
| WS generic router  | `WsRouter[T, D]`     | `shared/ws/generic_route.py`         | `from trading_api.shared.ws.generic_route import WsRouter`                   |
| Module base class  | `Module`             | `shared/module_interface.py`         | `from trading_api.shared.module_interface import Module`                     |
| WS route service   | `WsRouteService`     | `shared/ws/ws_router.py`             | `from trading_api.shared.ws.ws_router import WsRouteService`                 |

### Version Pattern Reference

| Component         | Pattern                | Example                                  | Notes                               |
| ----------------- | ---------------------- | ---------------------------------------- | ----------------------------------- |
| API Router        | File or Directory      | `api/v1.py` or `api/v1/__init__.py`      | Both supported via `.stem` property |
| WebSocket Router  | Directory only         | `ws/v1/__init__.py`                      | Required for WsRouterBase subclass  |
| Version Discovery | Auto-detected          | Scans `api/` and `ws/` dirs              | Uses `d.stem.startswith("v")`       |
| Enforcement       | Import-time validation | Module loading fails if wrong base class | See section 7                       |

### Module Structure Quick Copy

```python
# modules/mymodule/__init__.py
from pathlib import Path
from trading_api.shared.module_interface import Module

class MymoduleModule(Module):
    @classmethod
    def module_dir(cls) -> Path:
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
- **Strict WS Versioning**: WebSocket routers require directories (`ws/v1/`) for WsRouterBase subclass
- **ABC Pattern**: Uses Python's `abc.ABC`, not `typing.Protocol`
- **List-Based WS**: `WsRouterBase` extends `list[WsRouteFeature]` for multiple routers per version
- **Direct Generic Types**: WebSocket routers use `WsRouter[TRequest, TData]` pattern (no code generation)
- **Auto Health/Version**: All modules get health/version endpoints via `APIRouterInterface` inheritance
- **Enforcement**: Module loading validates base class inheritance at import time

Modules are **independently deployable versioned applications** that compose into a cohesive system.
