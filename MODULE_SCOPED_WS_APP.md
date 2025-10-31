# Module-Scoped WebSocket Apps - Implementation Guide

> **Document Status**: ✅ Implementation completed and verified. All module-scoped WebSocket endpoints are working.
>
> **Related Documents**:
>
> - [API Methodology](API-METHODOLOGY.md) - REST API design patterns
> - [WebSocket Methodology](WEBSOCKET-METHODOLOGY.md) - WebSocket design patterns
> - [Architecture](ARCHITECTURE.md) - Overall system architecture

---

## Table of Contents

1. [Phase 1: Current Architecture Overview](#phase-1-current-architecture-overview)
2. [Phase 2: Problem Statement](#phase-2-problem-statement)
3. [Phase 3: Solution Design](#phase-3-solution-design)
4. [Phase 4: Implementation](#phase-4-implementation)

---

## Phase 1: Current Architecture Overview

### Module Prefix Pattern (REST API)

The backend uses a **modular factory-based pattern** where modules self-configure their API prefixes.

#### 1.1 Module-Level Prefix Configuration

Each module (broker, datafeed) defines its prefix in `__init__.py`:

```python
# modules/broker/__init__.py
def get_api_routers(self) -> list[APIRouter]:
    return [
        BrokerApi(service=self.service, prefix=f"/{self.name}", tags=[self.name])
    ]
    # self.name = "broker" → prefix = "/broker"

# modules/datafeed/__init__.py
def get_api_routers(self) -> list[APIRouter]:
    return [
        DatafeedApi(service=self.service, prefix=f"/{self.name}", tags=[self.name])
    ]
    # self.name = "datafeed" → prefix = "/datafeed"
```

#### 1.2 API Router Classes Pattern

All API classes extend `APIRouter` and accept prefix in constructor:

```python
# modules/broker/api.py
class BrokerApi(APIRouter):
    def __init__(self, service: BrokerService, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # Accepts prefix, tags from kwargs
        self.service = service

# modules/datafeed/api.py
class DatafeedApi(APIRouter):
    def __init__(self, service: DatafeedService, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.service = service

# shared/api/health.py
class HealthApi(APIRouter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

# shared/api/versions.py
class VersionApi(APIRouter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
```

#### 1.3 App Factory Registration

`app_factory.py` includes all routers with base URL prefix `/api/v1`:

```python
base_url = "/api/v1"

# Shared routers (no module prefix)
api_app.include_router(HealthApi(tags=["health"]), prefix=base_url, tags=["v1"])
api_app.include_router(VersionApi(tags=["versioning"]), prefix=base_url, tags=["v1"])

# Module routers (module adds own prefix)
for module in registry.get_enabled_modules():
    for router in module.get_api_routers():
        api_app.include_router(router, prefix=base_url, tags=["v1"])
```

#### 1.4 REST API URL Structure

| Component           | Prefix                  | Route       | Final URL                 |
| ------------------- | ----------------------- | ----------- | ------------------------- |
| **Shared API**      | `/api/v1`               | `/health`   | `/api/v1/health`          |
| **Shared API**      | `/api/v1`               | `/versions` | `/api/v1/versions`        |
| **Broker Module**   | `/api/v1` + `/broker`   | `/orders`   | `/api/v1/broker/orders`   |
| **Datafeed Module** | `/api/v1` + `/datafeed` | `/config`   | `/api/v1/datafeed/config` |

#### 1.5 REST API Design Principles

1. ✅ **Module Self-Configuration**: Each module sets its own prefix via `self.name`
2. ✅ **Consistent Pattern**: `prefix=f"/{self.name}"` enforces module name as prefix
3. ✅ **Inheritance Pattern**: API classes extend `APIRouter` and pass through kwargs
4. ✅ **Two-Level Prefixing**:
   - App factory adds version prefix (`/api/v1`)
   - Module adds namespace prefix (`/broker`, `/datafeed`)
5. ✅ **Shared APIs No Module Prefix**: Health and versions at `/api/v1/{endpoint}`
6. ✅ **Module APIs With Prefix**: All module endpoints at `/api/v1/{module}/{endpoint}`

---

## Phase 2: Problem Statement

### 2.1 WebSocket Architecture Issue

The current WebSocket implementation **does not follow** the established module prefix pattern:

❌ **Current WebSocket Endpoints**:

- Single global `FastWSAdapter` at `/api/v1/ws`
- All modules share the same WebSocket endpoint
- Inconsistent with REST API pattern (`/api/v1/{module}/endpoint`)

❌ **Specific Problems**:

```python
# app_factory.py - CURRENT IMPLEMENTATION
@api_app.websocket(ws_url)  # ws_url = "/api/v1/ws"
async def websocket_endpoint(
    client: Annotated[Client, Depends(ws_app.manage)],
) -> None:
    """WebSocket endpoint for real-time bar data streaming"""
    await ws_app.serve(client)
```

**Issues**:

1. Single global WebSocket endpoint doesn't follow module namespacing
2. All modules (broker, datafeed) share `/api/v1/ws`
3. Can't have module-specific WebSocket configurations
4. AsyncAPI specs mixed together instead of per-module
5. Inconsistent with documented REST API pattern

### 2.2 Required Consistency

✅ **Expected WebSocket Pattern**:

- Broker: `/api/v1/broker/ws`
- Datafeed: `/api/v1/datafeed/ws`
- Matches REST pattern: `/api/v1/{module}/{resource}`

---

## Phase 3: Solution Design

### 3.1 Recommended Approach: Module-Owned FastWS Apps

Each module creates and manages its own `FastWSAdapter` instance.

#### 3.1.1 Module WebSocket App Ownership

```python
# modules/broker/__init__.py
class BrokerModule:
    def __init__(self) -> None:
        self._service: BrokerService | None = None
        self._ws_app: FastWSAdapter | None = None  # Module-owned
        self._enabled: bool = True

    def get_ws_app(self, base_url: str) -> FastWSAdapter:
        """Get or create module's WebSocket application"""
        if self._ws_app is None:
            ws_url = f"{base_url}/{self.name}/ws"
            self._ws_app = FastWSAdapter(
                title=f"{self.name.title()} WebSockets",
                description=f"Real-time {self.name} data streaming",
                version="1.0.0",
                asyncapi_url=f"{ws_url}/asyncapi.json",
                asyncapi_docs_url=f"{ws_url}/asyncapi",
                heartbeat_interval=30.0,
                max_connection_lifespan=3600.0,
            )
            # Register module's WS routers
            for ws_router in self.get_ws_routers():
                self._ws_app.include_router(ws_router)

        return self._ws_app

    def register_ws_endpoint(self, api_app: FastAPI, base_url: str) -> None:
        """Register module's WebSocket endpoint"""
        ws_app = self.get_ws_app(base_url)
        ws_url = f"{base_url}/{self.name}/ws"

        @api_app.websocket(ws_url)
        async def websocket_endpoint(
            client: Annotated[Client, Depends(ws_app.manage)],
        ) -> None:
            f"""WebSocket endpoint for {self.name} real-time streaming"""
            await ws_app.serve(client)
```

#### 3.1.2 App Factory Integration

```python
# app_factory.py
def create_app(enabled_modules: list[str] | None = None) -> tuple[FastAPI, list[FastWSAdapter]]:
    base_url = "/api/v1"
    ws_apps = []  # Collect all module WS apps

    # Load enabled modules
    for module in registry.get_enabled_modules():
        # Include API routers
        for router in module.get_api_routers():
            api_app.include_router(router, prefix=base_url, tags=["v1"])

        # Register module's WebSocket endpoint (if supported)
        if hasattr(module, 'register_ws_endpoint'):
            module.register_ws_endpoint(api_app, base_url)
            ws_apps.append(module.get_ws_app(base_url))

        # Call configure_app hook
        module.configure_app(api_app, None)  # ws_app param deprecated

    return api_app, ws_apps
```

### 3.2 Result URL Structure

✅ **Module-Scoped WebSocket URLs**:

- `/api/v1/broker/ws` - Broker WebSocket endpoint
- `/api/v1/datafeed/ws` - Datafeed WebSocket endpoint
- `/api/v1/broker/ws/asyncapi` - Broker AsyncAPI docs
- `/api/v1/datafeed/ws/asyncapi` - Datafeed AsyncAPI docs

### 3.3 Design Benefits

1. ✅ **Consistent with REST Pattern**: Each module at `/api/v1/{module}/ws`
2. ✅ **Module Encapsulation**: Module owns its WS app lifecycle
3. ✅ **Independent AsyncAPI Specs**: Each module has separate documentation
4. ✅ **Isolated Configuration**: Different heartbeat intervals, lifespans per module
5. ✅ **Testable**: Can test each module's WebSocket independently
6. ✅ **Scalable**: Easy to add new modules with their own WS endpoints

### 3.4 Trade-offs and Mitigations

| Trade-off                       | Mitigation                                                    |
| ------------------------------- | ------------------------------------------------------------- |
| Multiple WebSocket connections  | Frontend multiplexes efficiently; modern browsers handle well |
| Slightly more complex lifecycle | Centralized in module protocol; consistent pattern            |
| Separate AsyncAPI specs         | Each module's spec is clearer; can aggregate if needed        |

---

## Phase 4: Implementation

### 4.1 Step-by-Step Migration Plan

#### Step 1: Add Module WebSocket Methods

Add `get_ws_app()` and `register_ws_endpoint()` methods to each module that supports WebSockets.

**For BrokerModule (`backend/src/trading_api/modules/broker/__init__.py`):**

```python
from typing import Any
from fastapi import Depends, FastAPI
from fastapi.routing import APIRouter
from external_packages.fastws import Client, FastWSAdapter
from typing import Annotated

class BrokerModule:
    def __init__(self) -> None:
        self._service: BrokerService | None = None
        self._ws_app: FastWSAdapter | None = None  # Add this
        self._enabled: bool = True

    def get_ws_app(self, base_url: str) -> FastWSAdapter:
        """Get or create module's WebSocket application."""
        if self._ws_app is None:
            ws_url = f"{base_url}/{self.name}/ws"
            self._ws_app = FastWSAdapter(
                title=f"{self.name.title()} WebSockets",
                description=f"Real-time {self.name} data streaming for orders, positions, and executions",
                version="1.0.0",
                asyncapi_url=f"{ws_url}/asyncapi.json",
                asyncapi_docs_url=f"{ws_url}/asyncapi",
                heartbeat_interval=30.0,
                max_connection_lifespan=3600.0,
            )
            # Register module's WS routers
            for ws_router in self.get_ws_routers():
                self._ws_app.include_router(ws_router)

        return self._ws_app

    def register_ws_endpoint(self, api_app: FastAPI, base_url: str) -> None:
        """Register module's WebSocket endpoint."""
        ws_app = self.get_ws_app(base_url)
        ws_url = f"{base_url}/{self.name}/ws"

        @api_app.websocket(ws_url)
        async def websocket_endpoint(
            client: Annotated[Client, Depends(ws_app.manage)],
        ) -> None:
            f"""WebSocket endpoint for {self.name} real-time streaming"""
            await ws_app.serve(client)
```

**For DatafeedModule (`backend/src/trading_api/modules/datafeed/__init__.py`):**

```python
from typing import Any
from fastapi import Depends, FastAPI
from fastapi.routing import APIRouter
from external_packages.fastws import Client, FastWSAdapter
from typing import Annotated

class DatafeedModule:
    def __init__(self) -> None:
        self._service: DatafeedService | None = None
        self._ws_app: FastWSAdapter | None = None  # Add this
        self._enabled: bool = True

    def get_ws_app(self, base_url: str) -> FastWSAdapter:
        """Get or create module's WebSocket application."""
        if self._ws_app is None:
            ws_url = f"{base_url}/{self.name}/ws"
            self._ws_app = FastWSAdapter(
                title=f"{self.name.title()} WebSockets",
                description=f"Real-time {self.name} data streaming for market data and quotes",
                version="1.0.0",
                asyncapi_url=f"{ws_url}/asyncapi.json",
                asyncapi_docs_url=f"{ws_url}/asyncapi",
                heartbeat_interval=30.0,
                max_connection_lifespan=3600.0,
            )
            # Register module's WS routers
            for ws_router in self.get_ws_routers():
                self._ws_app.include_router(ws_router)

        return self._ws_app

    def register_ws_endpoint(self, api_app: FastAPI, base_url: str) -> None:
        """Register module's WebSocket endpoint."""
        ws_app = self.get_ws_app(base_url)
        ws_url = f"{base_url}/{self.name}/ws"

        @api_app.websocket(ws_url)
        async def websocket_endpoint(
            client: Annotated[Client, Depends(ws_app.manage)],
        ) -> None:
            f"""WebSocket endpoint for {self.name} real-time streaming"""
            await ws_app.serve(client)
```

#### Step 2: Update App Factory

Modify `backend/src/trading_api/app_factory.py` to use module-scoped WebSocket apps:

**Changes needed:**

1. Remove the global `ws_app` creation
2. Collect module WebSocket apps in a list
3. Update lifespan to handle multiple AsyncAPI specs
4. Remove the global WebSocket endpoint registration
5. Return list of WebSocket apps instead of single app

```python
def create_app(
    enabled_modules: list[str] | None = None,
) -> tuple[FastAPI, list[FastWSAdapter]]:
    """Create and configure FastAPI and FastWSAdapter applications.

    Args:
        enabled_modules: List of module names to enable.

    Returns:
        tuple[FastAPI, list[FastWSAdapter]]: API app and list of module WS apps
    """
    # ... (module registration code remains the same) ...

    base_url = "/api/v1"
    ws_apps: list[FastWSAdapter] = []  # Collect all module WS apps

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Handle application startup and shutdown events."""
        validate_response_models(app)
        backend_dir = Path(__file__).parent.parent.parent

        # Generate OpenAPI spec (same as before)
        openapi_schema = app.openapi()
        openapi_file = backend_dir / "openapi.json"
        try:
            with open(openapi_file, "w") as f:
                json.dump(openapi_schema, f, indent=2)
            print(f"📝 Generated OpenAPI spec: {openapi_file}")
        except Exception as e:
            print(f"⚠️  Failed to generate OpenAPI file: {e}")

        # Generate AsyncAPI specs for each module
        for idx, ws_app in enumerate(ws_apps):
            asyncapi_schema = ws_app.asyncapi()
            # Use module-specific filename or numbered if needed
            asyncapi_file = backend_dir / f"asyncapi-{idx}.json"
            try:
                with open(asyncapi_file, "w") as f:
                    json.dump(asyncapi_schema, f, indent=2)
                print(f"📝 Generated AsyncAPI spec: {asyncapi_file}")
            except Exception as e:
                print(f"⚠️  Failed to generate AsyncAPI file: {e}")

        # Setup all WebSocket apps
        for ws_app in ws_apps:
            ws_app.setup(app)

        yield

        print("🛑 FastAPI application shutdown complete")

    # Create FastAPI app (same as before)
    api_app = FastAPI(
        # ... (same configuration) ...
        lifespan=lifespan,
    )

    # Add CORS middleware (same as before)
    api_app.add_middleware(CORSMiddleware, ...)

    # Load shared routers (same as before)
    api_app.include_router(HealthApi(tags=["health"]), prefix=base_url, tags=["v1"])
    api_app.include_router(VersionApi(tags=["versioning"]), prefix=base_url, tags=["v1"])

    # Load enabled modules
    for module in registry.get_enabled_modules():
        # Include API routers (same as before)
        for router in module.get_api_routers():
            api_app.include_router(router, prefix=base_url, tags=["v1"])

        # Register module's WebSocket endpoint (NEW)
        if hasattr(module, 'register_ws_endpoint'):
            module.register_ws_endpoint(api_app, base_url)
            ws_apps.append(module.get_ws_app(base_url))

        # Call configure_app hook - ws_app parameter deprecated
        module.configure_app(api_app, None)

    # REMOVE the global WebSocket endpoint registration
    # @api_app.websocket(ws_url)  <-- DELETE THIS

    return api_app, ws_apps
```

#### Step 3: Update Module Protocol

Update the module protocol/interface documentation to reflect new methods:

**In module docstrings or protocol definition:**

```python
class ModuleProtocol(Protocol):
    """Protocol for pluggable modules."""

    @property
    def name(self) -> str:
        """Module unique identifier."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether module is enabled."""
        ...

    def get_api_routers(self) -> list[APIRouter]:
        """Get REST API routers."""
        ...

    def get_ws_routers(self) -> list[Any]:
        """Get WebSocket routers."""
        ...

    def get_openapi_tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags."""
        ...

    def configure_app(self, api_app: Any, ws_app: Any | None) -> None:
        """Configure application (ws_app deprecated)."""
        ...

    # NEW METHODS
    def get_ws_app(self, base_url: str) -> FastWSAdapter:
        """Get or create module's WebSocket application."""
        ...

    def register_ws_endpoint(self, api_app: FastAPI, base_url: str) -> None:
        """Register module's WebSocket endpoint."""
        ...
```

#### Step 4: Update Startup Scripts

Update any startup scripts or deployment configs that reference the WebSocket app:

**In `backend/src/trading_api/__main__.py` or similar:**

```python
# Before:
# api_app, ws_app = create_app()

# After:
api_app, ws_apps = create_app()
# ws_apps is now a list of FastWSAdapter instances
```

#### Step 5: Update Tests

Update tests that check WebSocket functionality:

**Example test updates:**

```python
# Before:
def test_websocket_endpoint():
    api_app, ws_app = create_app()
    assert ws_app.asyncapi_url == "/api/v1/ws/asyncapi.json"

# After:
def test_websocket_endpoints():
    api_app, ws_apps = create_app()
    assert len(ws_apps) == 2  # broker and datafeed

    # Check broker WebSocket
    broker_ws = ws_apps[0]
    assert broker_ws.asyncapi_url == "/api/v1/broker/ws/asyncapi.json"

    # Check datafeed WebSocket
    datafeed_ws = ws_apps[1]
    assert datafeed_ws.asyncapi_url == "/api/v1/datafeed/ws/asyncapi.json"
```

#### Step 6: Update API Documentation

Add root endpoint that lists all WebSocket endpoints:

**In `backend/src/trading_api/shared/api/versions.py`:**

```python
@self.get(
    "/",
    summary="API Overview",
    description="Returns API metadata including WebSocket endpoints",
    operation_id="getAPIOverview",
)
async def get_api_overview() -> dict:
    """Get API overview including WebSocket endpoints."""
    from trading_api.app_factory import registry

    base_url = "/api/v1"
    websocket_endpoints = []

    for module in registry.get_enabled_modules():
        if hasattr(module, 'get_ws_app'):
            ws_url = f"{base_url}/{module.name}/ws"
            websocket_endpoints.append({
                "module": module.name,
                "url": ws_url,
                "asyncapi_url": f"{ws_url}/asyncapi.json",
                "asyncapi_docs": f"{ws_url}/asyncapi",
            })

    return {
        "api_version": "v1",
        "documentation": f"{base_url}/docs",
        "openapi_spec": f"{base_url}/openapi.json",
        "websocket_endpoints": websocket_endpoints,
    }
```

### 4.2 Verification Checklist

After implementation, verify:

- [ ] Each module has `get_ws_app()` and `register_ws_endpoint()` methods
- [ ] `create_app()` returns `tuple[FastAPI, list[FastWSAdapter]]`
- [ ] Broker WebSocket accessible at `/api/v1/broker/ws`
- [ ] Datafeed WebSocket accessible at `/api/v1/datafeed/ws`
- [ ] Each module has separate AsyncAPI docs at `/{module}/ws/asyncapi`
- [ ] Global `/api/v1/ws` endpoint removed
- [ ] All tests pass with module-scoped WebSockets
- [ ] Frontend clients updated to use module-specific endpoints
- [ ] AsyncAPI specs generated correctly for each module
- [ ] No regression in WebSocket functionality

### 4.3 Migration Impact

**Breaking Changes:**

1. ❌ Old endpoint `/api/v1/ws` will be removed
2. ✅ New endpoints: `/api/v1/broker/ws` and `/api/v1/datafeed/ws`
3. ✅ Frontend must update WebSocket connection URLs
4. ✅ AsyncAPI documentation now module-specific

**Migration Guide for Clients:**

```typescript
// Before:
const ws = new WebSocket("ws://localhost:8000/api/v1/ws");

// After - for broker data:
const brokerWs = new WebSocket("ws://localhost:8000/api/v1/broker/ws");

// After - for datafeed data:
const datafeedWs = new WebSocket("ws://localhost:8000/api/v1/datafeed/ws");
```

### 4.4 Documentation Alignment

This implementation **fully aligns** with API-METHODOLOGY.md:

- ✅ Module prefix pattern: `prefix=f"/{self.name}"`
- ✅ Two-tier URL structure: `/api/v1` + `/{module}` + `/ws`
- ✅ Module registration via factory pattern
- ✅ Consistent REST and WebSocket URL patterns

---

## Summary

The module-scoped WebSocket implementation ensures **complete consistency** across the entire API:

### Before (Inconsistent)

- REST: `/api/v1/{module}/{endpoint}` ✅
- WebSocket: `/api/v1/ws` ❌

### After (Consistent)

- REST: `/api/v1/{module}/{endpoint}` ✅
- WebSocket: `/api/v1/{module}/ws` ✅

All modules follow the pattern:

- **Base tier**: `/api/v1` (app factory)
- **Module tier**: `/{module_name}` (module self-configuration)
- **Resource tier**: `/{endpoint}` or `/ws` (specific resource)
