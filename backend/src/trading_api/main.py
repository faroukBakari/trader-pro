"""Main FastAPI application with API versioning support."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI

from external_packages.fastws import Client
from trading_api.plugins.fastws_adapter import FastWSAdapter

from .api.datafeed import router as datafeed_router
from .api.health import router as health_router
from .api.versions import router as versions_router
from .core.versioning import APIVersion
from .ws.datafeed import router as ws_datafeed_router


def validate_response_models(app: FastAPI) -> None:
    """Validate that all routes have response_model defined for OpenAPI compliance"""
    from fastapi.routing import APIRoute

    missing_models = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            if route.response_model is None:
                # Skip OPTIONS method as it's auto-generated
                methods = route.methods or set()
                if methods and "OPTIONS" not in methods:
                    endpoint_name = getattr(route.endpoint, "__name__", "unknown")
                    path = route.path
                    missing_models.append(f"{list(methods)} {path} -> {endpoint_name}")

    if missing_models:
        error_msg = (
            "❌ FastAPI Response Model Violations Found:\n"
            + "\n".join(f"  - {model}" for model in missing_models)
            + "\n\nAll FastAPI routes must have response_model"
            + " defined for OpenAPI compliance."
        )
        raise ValueError(error_msg)

    print("✅ All FastAPI routes have response_model defined")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    # Startup: Validate all routes have response models
    validate_response_models(app)

    # Startup: Generate openapi.json file for file-based watching
    openapi_schema = app.openapi()

    # Write to file in the backend directory
    backend_dir = Path(__file__).parent.parent.parent
    openapi_file = backend_dir / "openapi.json"

    try:
        with open(openapi_file, "w") as f:
            json.dump(openapi_schema, f, indent=2)
        print(f"📝 Generated OpenAPI spec: {openapi_file}")
    except Exception as e:
        print(f"⚠️  Failed to generate OpenAPI file: {e}")

    yield

    # Shutdown: Cleanup is handled by FastAPIAdapter
    print("🛑 FastAPI application shutdown complete")


apiApp = FastAPI(
    title="Trading API",
    description=(
        "A comprehensive trading API server with market data "
        "and portfolio management. Supports multiple API versions for "
        "backwards compatibility."
    ),
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_tags=[
        {"name": "health", "description": "Health check operations"},
        {"name": "versioning", "description": "API version information"},
        {"name": "datafeed", "description": "Market data and symbols operations"},
    ],
    lifespan=lifespan,
)

wsApp = FastWSAdapter(
    title="Trading WebSockets",
    description=(
        "Real-time trading data streaming. "
        "Read the documentation to subscribe to specific data feeds."
    ),
    version="1.0.0",
    asyncapi_url="/api/v1/ws/asyncapi.json",
    asyncapi_docs_url="/api/v1/ws/asyncapi",
    heartbeat_interval=30.0,
    max_connection_lifespan=3600.0,
)

# Include version 1 routes
apiApp.include_router(health_router, prefix="/api/v1", tags=["v1"])
apiApp.include_router(versions_router, prefix="/api/v1", tags=["v1"])
apiApp.include_router(datafeed_router, prefix="/api/v1", tags=["v1"])

# Register WebSocket endpoints and AsyncAPI documentation
# Note: WebSocket endpoints don't appear in OpenAPI/Swagger docs (/api/v1/docs)
# They use AsyncAPI specification instead (see /api/v1/ws/asyncapi)
# Note: No prefix here - the prefix applies to HTTP paths, not WebSocket message types
wsApp.include_router(ws_datafeed_router)
wsApp.setup(apiApp)


# Register the WebSocket endpoint
@apiApp.websocket("/api/v1/ws")
async def websocket_bars_endpoint(
    client: Annotated[Client, Depends(wsApp.manage)],
) -> None:
    """WebSocket endpoint for real-time bar data streaming"""
    await wsApp.serve(client)


# Add version information to root endpoint
@apiApp.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "Trading API",
        "version": "1.0.0",
        "current_api_version": APIVersion.get_latest().value,
        "documentation": "/api/v1/docs",
        "health": "/api/v1/health",
        "versions": "/api/v1/versions",
        "datafeed": "/api/v1/datafeed",
        "websockets": {
            "bars": {
                "endpoint": "/api/v1/ws",
                "docs": wsApp.asyncapi_docs_url,
                "spec": wsApp.asyncapi_url,
                "operations": [
                    "bars.subscribe",
                    "bars.unsubscribe",
                    "bars.update",
                ],
                "note": "WebSocket endpoints use AsyncAPI spec, not OpenAPI/Swagger",
            },
        },
    }


# Backward compatibility alias for ASGI servers
app = apiApp
