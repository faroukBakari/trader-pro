# API Versioning

**Status**: ✅ Production Ready  
**Last Updated**: November 2, 2025  
**Current Version**: v1

---

## Overview

The Trading API uses **URL-based versioning** in a modular architecture. Each module is mounted under a versioned base path (`/api/v1`), ensuring backwards compatibility and smooth transitions for API consumers.

---

## Versioning Strategy

### URL Structure

**Pattern**: `/api/{version}/{module}/{resource}`

**Examples**:

- `/api/v1/core/health` - Core module health endpoint
- `/api/v1/broker/orders` - Broker module orders endpoint
- `/api/v1/datafeed/config` - Datafeed module configuration

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
base_url = "/api/v1"
modular_app = ModularApp(modules=enabled_modules, base_url=base_url, ...)
```

2. **Module Mounting**:

```python
for module_app in self._modules_apps:
    mount_path = f"{self.base_url}/{module_app.module.name}"
    self.mount(mount_path, module_app.api_app)
    # Example: /api/v1/broker, /api/v1/datafeed
```

3. **Version Configuration** (`models/versioning.py`):

```python
class APIVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"  # Future

VERSION_CONFIG = {
    APIVersion.V1: VersionInfo(
        version=APIVersion.V1,
        release_date="2025-10-04",
        status="stable",
        breaking_changes=[],
        deprecation_notice=None,
        sunset_date=None,
    ),
    # ... future versions
}
```

### Version Information Endpoints

**Endpoints** (Core module):

- `GET /api/v1/core/versions` - All available API versions
- `GET /api/v1/core/version` - Current API version details
- `GET /api/v1/core/health` - Health check with version info

**Response Examples**:

```json
// GET /api/v1/core/versions
{
  "current_version": "v1",
  "available_versions": [
    {
      "version": "v1",
      "release_date": "2025-10-04",
      "status": "stable",
      "breaking_changes": [],
      "deprecation_notice": null,
      "sunset_date": null
    }
  ],
  "documentation_url": "/api/v1/docs",
  "support_contact": "support@trading-pro.nodomainyet"
}

// GET /api/v1/core/version
{
  "version": "v1",
  "release_date": "2025-10-04",
  "status": "stable",
  "breaking_changes": [],
  "deprecation_notice": null,
  "sunset_date": null
}

// GET /api/v1/core/health
{
  "status": "ok",
  "message": "Trading API is running",
  "timestamp": "2025-11-02T14:30:00Z",
  "api_version": "v1",
  "version_info": {
    "version": "v1",
    "release_date": "2025-10-04",
    "status": "stable",
    "deprecation_notice": null
  }
}
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
- Deprecation warnings included in responses
- Sunset date announced

**3. Sunset**

- Version no longer supported
- Endpoints return appropriate error status

---

## Current Version (v1)

**Release Date**: 2025-10-04  
**Status**: Stable  
**Base Path**: `/api/v1`

**Available Modules**:

- `core` - Health checks, versioning, system info
- `broker` - Trading operations (orders, positions, executions)
- `datafeed` - Market data (quotes, bars, symbols)

**Module Endpoints Pattern**:

- REST: `/api/v1/{module}/{resource}`
- WebSocket: `/api/v1/{module}/ws`
- Docs: `/api/v1/docs` (merged OpenAPI)
- AsyncAPI: `/api/v1/ws/asyncapi.json` (if WebSocket modules enabled)

---

## Adding New Versions

### Step 1: Update Version Models

**Location**: `backend/src/trading_api/models/versioning.py`

```python
class APIVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"  # Add new version

    @classmethod
    def get_latest(cls) -> "APIVersion":
        return cls.V2  # Update latest

VERSION_CONFIG = {
    # Existing v1 config...
    APIVersion.V2: VersionInfo(
        version=APIVersion.V2,
        release_date="2026-01-15",
        status="stable",
        breaking_changes=[
            "Authentication required for all endpoints",
            "New response format for error messages"
        ],
        deprecation_notice=None,
        sunset_date=None,
    ),
}
```

### Step 2: Update Application Factory

**Location**: `backend/src/trading_api/app_factory.py`

```python
def create_app(self, api_version: str = "v1", ...) -> ModularApp:
    # Create base URL from version
    base_url = f"/api/{api_version}"

    modular_app = ModularApp(
        modules=enabled_modules,
        base_url=base_url,
        ...
    )
```

### Step 3: Deploy Both Versions

**Option A: Separate Processes** (Recommended)

```bash
# Run v1 on port 8001
ENABLED_MODULES=all uvicorn trading_api.main:app --port 8001

# Run v2 on port 8002 (separate codebase or branch)
ENABLED_MODULES=all uvicorn trading_api.main:app --port 8002

# Nginx routes by path
location /api/v1/ {
    proxy_pass http://localhost:8001;
}
location /api/v2/ {
    proxy_pass http://localhost:8002;
}
```

**Option B: Single Process with Version Routing** (Future enhancement)

```python
# Create apps for both versions
v1_app = factory.create_app(api_version="v1")
v2_app = factory.create_app(api_version="v2")

# Mount both
root_app = FastAPI()
root_app.mount("/api/v1", v1_app)
root_app.mount("/api/v2", v2_app)
```

---

## Client Integration

### Auto-Generated Clients

**Frontend clients are generated from OpenAPI specs**:

```bash
# Generate TypeScript client (frontend)
cd frontend
make generate-openapi-client

# Generate Python client (backend)
cd backend
make generate modules=broker  # Generates client for each module
```

**Generated Client Structure**:

```typescript
// Frontend
import { Configuration, V1Api } from '@clients/trader-client-generated'

const config = new Configuration({ basePath: '/api/v1' })
const api = new V1Api(config)

// Backend
from trading_api.clients import BrokerClient

async with BrokerClient(base_url="http://localhost:8000/api/v1") as client:
    result = await client.placeOrder(order)
```

### Version-Aware Client Pattern

```typescript
class TradingClient {
  private api: V1Api;

  constructor(version: string = "v1") {
    const config = new Configuration({
      basePath: `/api/${version}`,
    });
    this.api = new V1Api(config);
  }

  async checkVersion(): Promise<VersionInfo> {
    const response = await this.api.getCurrentAPIVersion();

    if (response.data.deprecation_notice) {
      console.warn("API Deprecation:", response.data.deprecation_notice);
    }

    return response.data;
  }
}
```

---

## Migration Strategy

### When New Version Released

**1. Announce Deprecation**

- Update `VERSION_CONFIG` with deprecation notice
- Set sunset date (minimum 6 months)
- Notify clients via version endpoints

**2. Provide Migration Guide**

- Document breaking changes
- Provide code examples
- Offer migration tools

**3. Run Both Versions**

- Deploy new version alongside old
- Monitor usage metrics
- Support gradual migration

**4. Sunset Old Version**

- After sunset date passes
- Return 410 Gone for deprecated endpoints
- Redirect to latest version docs

### Breaking Changes Checklist

When introducing breaking changes in new version:

- [ ] Update `VERSION_CONFIG` with breaking changes list
- [ ] Set deprecation notice on previous version
- [ ] Update documentation with migration guide
- [ ] Generate new client libraries
- [ ] Deploy both versions simultaneously
- [ ] Monitor adoption metrics
- [ ] Plan sunset date (6+ months minimum)

---

## Best Practices

### For API Consumers

- ✅ Always specify version in requests
- ✅ Monitor version endpoints for deprecation notices
- ✅ Test against new versions before they're stable
- ✅ Plan migrations well before sunset dates
- ✅ Use auto-generated clients for type safety

### For API Development

- ✅ Never introduce breaking changes within a version
- ✅ Provide minimum 6 months notice for deprecations
- ✅ Maintain clear documentation of all changes
- ✅ Support previous version during transition
- ✅ Use modular architecture for clean version separation

---

## Related Documentation

- **[MODULAR_BACKEND_ARCHITECTURE.md](MODULAR_BACKEND_ARCHITECTURE.md)** - Module system and mounting
- **[SPECS_AND_CLIENT_GEN.md](SPECS_AND_CLIENT_GEN.md)** - Client generation
- **[API-METHODOLOGY.md](../../API-METHODOLOGY.md)** - API design patterns
- **[ARCHITECTURE.md](../../ARCHITECTURE.md)** - Overall system design

---

## Quick Reference

### Version Status Check

```bash
# Check current version
curl http://localhost:8000/api/v1/core/version

# Check all available versions
curl http://localhost:8000/api/v1/core/versions

# Health check with version
curl http://localhost:8000/api/v1/core/health
```

### Key Files

```
backend/src/trading_api/
├── models/versioning.py         # Version definitions
├── app_factory.py               # Base URL configuration
├── modules/core/
│   ├── api.py                   # Version endpoints
│   └── service.py               # Version logic
└── main.py                      # Entry point
```

### URL Patterns

```
/api/v1/core/health              # Core health endpoint
/api/v1/core/version             # Current version info
/api/v1/core/versions            # All versions info
/api/v1/broker/orders            # Broker module endpoint
/api/v1/datafeed/config          # Datafeed module endpoint
/api/v1/docs                     # Interactive API docs
/api/v1/openapi.json             # OpenAPI specification
/api/v1/ws/asyncapi.json         # AsyncAPI specification
```

---

**Maintainer**: Backend Team  
**Status**: ✅ Production-ready
