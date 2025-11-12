# API Versioning

**Status**: ✅ Production Ready  
**Last Updated**: November 5, 2025  
**Current Version**: v1

---

## Overview

The Trading API uses **URL-based versioning** in a modular architecture. Each module is mounted under a versioned base path (e.g., `/api/v1`), ensuring backwards compatibility and smooth transitions for API consumers.

**Key Architectural Change**: Health and version endpoints are **module-scoped and automatically exposed** via `APIRouterInterface`. Every module inheriting from `APIRouterInterface` gets `/health`, `/versions`, and `/version` endpoints automatically - no separate core module needed.

---

## Versioning Strategy

### URL Structure

**Pattern**: `/api/{version}/{module}/{resource}`

**Examples**:

- `/api/v1/broker/orders` - Broker module orders endpoint
- `/api/v1/datafeed/config` - Datafeed module configuration
- `/api/v1/broker/positions` - Broker module positions endpoint

### Version Format

- **Current**: `v1` (stable)
- **Future**: `v2`, `v3`, etc.

---

## Implementation

### Backend Structure

**Location**: `backend/src/trading_api/`

**Versioning is implemented through**:

1. **Base URL in Factory** (`app_factory.py`):

```python
base_url = "/api"
modular_app = ModularApp(modules=enabled_modules, base_url=base_url, ...)
```

2. **Module Mounting** (versioned directory structure):

```python
for module_app in self._modules_apps:
    for api_app in module_app.api_versions:
        mount_path = f"{self.base_url}/{api_app.version}/{module_app.module.name}"
        self.mount(mount_path, api_app)
        # Example: /api/v1/broker, /api/v1/datafeed
```

**Directory Structure** (per module):

```
modules/broker/
├── __init__.py         # BrokerModule class
├── service.py          # Inherits from Service base class
├── api/
│   ├── __init__.py
│   └── v1.py          # APIRouterInterface subclass for v1
└── ws/
    ├── __init__.py
    └── v1.py          # WsRouterInterface subclass for v1
```

**Module Loading Process**:

1. `Module.__init__()` auto-discovers versions from `api/` and `ws/` directories
2. For each version, dynamically imports the router class via `_import_api_routers_for_version(version)`
3. Router must inherit from `APIRouterInterface` (enforced - raises error if not)
4. `APIRouterInterface.__init__()` automatically registers `/health`, `/versions`, `/version` endpoints

5. **Version Auto-Discovery** (`shared/service.py`):

The base `Service` class automatically discovers available API versions from the module's directory structure:

```python
class Service(ABC):
    def __init__(self, module_dir: Path) -> None:
        api_dir = self.module_dir / "api"

        # Auto-discover version directories (v1, v2, etc.)
        version_dirs = [
            d.name for d in api_dir.iterdir()
            if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
        ]

        # Build version metadata
        self._api_metadata = APIMetadata(
            current_version=latest_version,
            available_versions=discovered_versions,
            documentation_url=f"/api/{current_version}/{self.module_name}/docs",
        )
```

### Automatic Health and Version Endpoints

**Every module automatically exposes these endpoints via `APIRouterInterface`**:

| Endpoint                      | Method | Response         | Description            |
| ----------------------------- | ------ | ---------------- | ---------------------- |
| `/api/v{N}/{module}/health`   | GET    | `HealthResponse` | Module health status   |
| `/api/v{N}/{module}/versions` | GET    | `APIMetadata`    | All available versions |
| `/api/v{N}/{module}/version`  | GET    | `VersionInfo`    | Current version info   |

**How It Works**:

```python
# shared/api/api_router_interface.py
class APIRouterInterface(APIRouter, ABC):
    def __init__(self, service: ServiceInterface, version: str, **kwargs):
        super().__init__(**kwargs)
        self._service = service
        self._version = version

        # Automatically registered on ALL routers inheriting this class
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

**ServiceInterface Base Class** (`shared/service_interface.py`):

Provides the data for health/version endpoints:

```python
class ServiceInterface(ABC):
    def __init__(self, module_dir: Path) -> None:
        # Auto-discovers versions from api/ directory structure
        self._api_metadata = APIMetadata(...)

    def get_health(self, current_version: str) -> HealthResponse:
        """Returns health status with version info"""

    def get_current_version_info(self, current_version: str) -> VersionInfo:
        """Returns version metadata"""

    @property
    def api_metadata(self) -> APIMetadata:
        """Returns all available versions metadata"""
```

**Example Module Implementation**:

```python
# modules/broker/api/v1.py
from trading_api.shared.api import APIRouterInterface

class BrokerApi(APIRouterInterface):  # Inherits health/version endpoints!
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Registers /health, /versions, /version

        # Add module-specific endpoints
        @self.post("/orders")
        async def placeOrder(order: PreOrder):
            return await self.service.place_order(order)
```

**Enforcement**:

Module loading validates that API routers inherit `APIRouterInterface`:

```python
# In module_interface.py::_import_api_routers_for_version()
if not issubclass(attr, APIRouterInterface):
    raise ValueError(f"No APIRouterInterface class found in api.{version}")
```

---

## Version Lifecycle

### Version States

**1. Stable**

- Fully supported and recommended for production
- No breaking changes introduced
- Bug fixes and minor enhancements only

**2. Deprecated**

- Still functional but not recommended
- Deprecation warnings can be included via Service methods
- Sunset date announced in version metadata

**3. Sunset**

- Version no longer supported
- Endpoints return appropriate error status

### Module Version Metadata

Each module's `Service` provides version metadata through the `api_metadata` property:

```python
# Example: Accessing version metadata from a service
metadata = broker_service.api_metadata

print(metadata.current_version)      # "v1"
print(metadata.available_versions)   # {"v1": VersionInfo(...)}
print(metadata.documentation_url)    # "/api/v1/broker/docs"
```

**VersionInfo Structure**:

```python
@dataclass
class VersionInfo:
    version: str
    release_date: str
    status: str  # "stable", "deprecated", "sunset"
    breaking_changes: list[str]
    deprecation_notice: str | None
    sunset_date: str | None
```

---

## Current Version (v1)

**Release Date**: 2025-10-04  
**Status**: Stable  
**Base Path**: `/api/v1`

**Available Modules**:

- `broker` - Trading operations (orders, positions, executions)
- `datafeed` - Market data (quotes, bars, symbols)

**Module Endpoints Pattern**:

- REST: `/api/v{N}/{module}/{resource}` - Module-specific endpoints
- Health: `/api/v{N}/{module}/health` - **Auto-exposed** via APIRouterInterface
- Versions: `/api/v{N}/{module}/versions` - **Auto-exposed** via APIRouterInterface
- Version: `/api/v{N}/{module}/version` - **Auto-exposed** via APIRouterInterface
- WebSocket: `/api/v{N}/{module}/ws` - When WebSocket support enabled
- Docs: `/api/v{N}/docs` - Merged OpenAPI for all modules
- AsyncAPI: `/api/v{N}/ws/asyncapi.json` - If WebSocket modules enabled

**Example Endpoints** (Broker Module v1):

```
/api/v1/broker/health       # Auto-exposed health check
/api/v1/broker/versions     # Auto-exposed version metadata
/api/v1/broker/version      # Auto-exposed current version info
/api/v1/broker/orders       # Module-specific endpoint
/api/v1/broker/positions    # Module-specific endpoint
/api/v1/broker/ws           # WebSocket endpoint
```

**Module Structure**:

```
modules/{module_name}/
├── __init__.py        # {ModuleName}Module class
├── service.py         # Service with auto-discovered versions
├── api/
│   ├── __init__.py
│   └── v{N}.py       # APIRouterInterface subclass (health/version auto-exposed)
└── ws/                # Optional
    ├── __init__.py
    └── v{N}.py       # WsRouterInterface subclass
```

---

## Adding New Versions

### Step 1: Create Version Directory

Add a new version directory in your module's `api/` and/or `ws/` folders:

```bash
# Example: Adding v2 to broker module
mkdir -p modules/broker/api/v2
touch modules/broker/api/v2/__init__.py
touch modules/broker/api/v2.py

# If WebSocket support needed
mkdir -p modules/broker/ws/v2
touch modules/broker/ws/v2/__init__.py
touch modules/broker/ws/v2.py
```

### Step 2: Implement Version Routes

**Create API routes** (`modules/broker/api/v2.py`):

```python
from trading_api.shared.api import APIRouterInterface
from trading_api.modules.broker.service import BrokerService

class BrokerApiV2(APIRouterInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # V2 endpoints with breaking changes
        @self.post("/orders")
        async def placeOrder(order: NewOrderModel):  # Different model
            return await self.service.place_order_v2(order)

    @property
    def service(self) -> BrokerService:
        if not isinstance(self._service, BrokerService):
            raise ValueError("Service not initialized")
        return self._service
```

### Step 3: Service Auto-Discovery

The `Service` base class **automatically discovers** the new version:

```python
# No code changes needed! Service.__init__ scans api/ directory
# and detects v1/ and v2/ automatically

broker_service = BrokerService(module_dir)
print(broker_service.api_metadata.available_versions)
# Output: {"v1": VersionInfo(...), "v2": VersionInfo(...)}
```

### Step 4: Update Version Metadata (Optional)

Customize version metadata by overriding in your service:

```python
class BrokerService(ServiceInterface):
    def __init__(self, module_dir: Path) -> None:
        super().__init__(module_dir)

        # Customize v2 metadata
        self._api_metadata.available_versions["v2"] = VersionInfo(
            version="v2",
            release_date="2026-01-15",
            status="stable",
            breaking_changes=[
                "New order model with additional required fields",
                "Changed response format for positions endpoint"
            ],
            deprecation_notice=None,
            sunset_date=None,
        )

        # Mark v1 as deprecated
        self._api_metadata.available_versions["v1"].status = "deprecated"
        self._api_metadata.available_versions["v1"].deprecation_notice = (
            "v1 will be sunset on 2026-07-15. Please migrate to v2."
        )
        self._api_metadata.available_versions["v1"].sunset_date = "2026-07-15"
```

### Step 5: Deploy Both Versions

The ModularApp automatically mounts all discovered versions:

```python
# In app_factory.py - No changes needed!
# ModularApp scans and mounts all versions automatically

# Resulting endpoints:
# /api/v1/broker/orders  (v1 routes)
# /api/v2/broker/orders  (v2 routes)
```

---

## Client Integration

### Auto-Generated Clients

**Frontend clients are generated from OpenAPI specs**:

```bash
# Generate TypeScript client (frontend)
cd frontend
make generate-openapi-client

# Generate Python client (backend) - per module
cd backend
make generate modules=broker  # Generates client for broker module
```

**Generated Client Structure**:

```typescript
// Frontend - importing from generated client
import { Configuration, DefaultApi } from "@clients/trader-client-generated";

const config = new Configuration({ basePath: "/api/v1" });
const api = new DefaultApi(config);

// Use module endpoints
await api.placeOrder({ symbol: "AAPL", qty: 100, side: "buy", type: "market" });
```

### Version-Aware Client Pattern

```typescript
class TradingClient {
  private api: DefaultApi;
  private version: string;

  constructor(version: string = "v1") {
    this.version = version;
    const config = new Configuration({
      basePath: `/api/${version}`,
    });
    this.api = new DefaultApi(config);
  }

  // Example: Client could check version metadata if module exposes it
  // Modules can optionally expose health/version endpoints
  async getModuleVersion(module: string): Promise<any> {
    // If module exposes version endpoint
    return await fetch(`/api/${this.version}/${module}/version`);
  }
}
```

---

## Migration Strategy

### When New Version Released

**1. Create New Version Directory**

- Add `api/v2/` and/or `ws/v2/` directories to your module
- Implement new routes with breaking changes
- Service auto-discovers the new version

**2. Update Version Metadata in Service**

- Set deprecation notice on old version
- Set sunset date (minimum 6 months recommended)
- Document breaking changes in new version's metadata

**3. Deploy with Both Versions Active**

- Both versions mount automatically via ModularApp
- Monitor usage metrics per version
- Support gradual migration

**4. Sunset Old Version**

- After sunset date passes
- Remove old version directory or mark routes as unavailable
- Redirect to migration documentation

### Breaking Changes Checklist

When introducing breaking changes in new version:

- [ ] Create new version directory (`api/v{N}/`, `ws/v{N}/`)
- [ ] Implement routes with breaking changes
- [ ] Update service to customize version metadata
- [ ] Set deprecation notice on previous version
- [ ] Document all breaking changes clearly
- [ ] Set sunset date (6+ months minimum recommended)
- [ ] Update documentation with migration guide
- [ ] Generate new client libraries
- [ ] Deploy both versions simultaneously
- [ ] Monitor adoption metrics per version
- [ ] Communicate sunset timeline to API consumers

---

## Best Practices

### For API Consumers

- ✅ Always specify version in requests (`/api/v{N}/...`)
- ✅ Use module health endpoints (`/api/v{N}/{module}/health`) to check status
- ✅ Monitor version metadata via `/api/v{N}/{module}/versions` for deprecation notices
- ✅ Check current version info via `/api/v{N}/{module}/version`
- ✅ Test against new versions early
- ✅ Plan migrations well before sunset dates
- ✅ Use auto-generated clients for type safety

### For API Development

- ✅ Never introduce breaking changes within a version
- ✅ Create new version directory for breaking changes
- ✅ Provide minimum 6 months notice for deprecations
- ✅ Maintain clear documentation of all changes
- ✅ Support previous version during transition
- ✅ Use version auto-discovery for clean separation
- ✅ Leverage ServiceInterface base class for consistent version metadata

---

## Related Documentation

- **[MODULAR_BACKEND_ARCHITECTURE.md](MODULAR_BACKEND_ARCHITECTURE.md)** - Module system and ServiceInterface base class
- **[MODULAR_VERSIONNING.md](MODULAR_VERSIONNING.md)** - Auto-discovery and version management
- **[SPECS_AND_CLIENT_GEN.md](SPECS_AND_CLIENT_GEN.md)** - Client generation
- **[API-METHODOLOGY.md](../../API-METHODOLOGY.md)** - API design patterns
- **[ARCHITECTURE.md](../../ARCHITECTURE.md)** - Overall system design

---

## Quick Reference

### Module Versioning Structure

```
modules/{module_name}/
├── __init__.py
├── service.py              # Inherits Service, auto-discovers versions
├── api/
│   ├── __init__.py
│   ├── v1.py              # Version 1 API routes
│   └── v2.py              # Version 2 API routes (when added)
└── ws/
    ├── __init__.py
    ├── v1.py              # Version 1 WebSocket routes
    └── v2.py              # Version 2 WebSocket routes (when added)
```

### Key Files

```
backend/src/trading_api/
├── models/
│   ├── health.py                  # HealthResponse model
│   └── versioning.py              # VersionInfo, APIMetadata models
├── shared/
│   ├── service_interface.py       # ServiceInterface base class with auto-discovery
│   ├── api/
│   │   └── api_router_interface.py  # APIRouterInterface (auto-exposes /health, /versions, /version)
│   ├── module_interface.py        # Module protocol and auto-discovery
│   └── module_registry.py         # Module registration
├── app_factory.py                 # ModularApp with version mounting
└── modules/
    ├── broker/
    │   ├── __init__.py            # BrokerModule
    │   ├── service.py             # BrokerService(ServiceInterface)
    │   └── api/v1.py              # Broker API v1 (APIRouterInterface subclass)
    └── datafeed/
        ├── __init__.py            # DatafeedModule
        ├── service.py             # DatafeedService(ServiceInterface)
        └── api/v1.py              # Datafeed API v1 (APIRouterInterface subclass)
```

### URL Patterns

```
# Current (v1) - Health/Version endpoints auto-exposed per module
/api/v1/broker/health            # Auto-exposed health endpoint
/api/v1/broker/versions          # Auto-exposed all versions metadata
/api/v1/broker/version           # Auto-exposed current version info
/api/v1/broker/orders            # Module-specific endpoint
/api/v1/broker/positions         # Module-specific endpoint

/api/v1/datafeed/health          # Auto-exposed health endpoint
/api/v1/datafeed/versions        # Auto-exposed all versions metadata
/api/v1/datafeed/version         # Auto-exposed current version info
/api/v1/datafeed/config          # Module-specific endpoint

# Merged documentation
/api/v1/docs                     # Interactive API docs (merged from all modules)
/api/v1/openapi.json             # OpenAPI specification (merged)
/api/v1/ws/asyncapi.json         # AsyncAPI specification (if WS enabled)

# Future (v2) - auto-mounted when v2.py files exist
/api/v2/broker/health            # Auto-exposed (v2)
/api/v2/broker/orders            # v2 implementation
/api/v2/datafeed/config          # v2 implementation
```

### Service Methods

```python
# Every module's service inherits these from ServiceInterface base class:
service.get_health(current_version: str) -> HealthResponse
service.get_current_version_info(current_version: str) -> VersionInfo
service.api_metadata -> APIMetadata  # Auto-discovered versions
service.module_name -> str
```

**Note**: These ServiceInterface methods provide the data for the health/version endpoints that are automatically exposed by `APIRouterInterface` in every module's API router.

---

## Example: Checking Health and Version

**Check Broker Module Health** (v1):

```bash
curl http://localhost:8000/api/v1/broker/health
# Response:
{
  "status": "ok",
  "timestamp": "2025-11-05T14:30:00Z",
  "module_name": "broker",
  "api_version": "v1"
}
```

**Get All Available Versions** (Broker Module):

```bash
curl http://localhost:8000/api/v1/broker/versions
# Response:
{
  "current_version": "v1",
  "available_versions": {
    "v1": {
      "version": "v1",
      "release_date": "TBD",
      "status": "stable",
      "breaking_changes": [],
      "deprecation_notice": null,
      "sunset_date": null
    }
  },
  "documentation_url": "/api/v1/broker/docs",
  "support_contact": "support@trading-pro.nodomainyet"
}
```

**Get Current Version Info**:

```bash
curl http://localhost:8000/api/v1/broker/version
# Response:
{
  "version": "v1",
  "release_date": "TBD",
  "status": "stable",
  "breaking_changes": [],
  "deprecation_notice": null,
  "sunset_date": null
}
```

---

**Maintainer**: Backend Team  
**Status**: ✅ Production-ready
