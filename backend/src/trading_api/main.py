"""Main FastAPI application with API versioning support."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from pydantic import BaseModel

from trading_api.api.datafeed import router as datafeed_router
from trading_api.api.health import router as health_router
from trading_api.api.versions import router as versions_router
from trading_api.api.websockets import router as websockets_router
from trading_api.core.versioning import APIVersion


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

    # Copy AsyncAPI spec to accessible location
    asyncapi_source = backend_dir / "asyncapi.yaml"
    if asyncapi_source.exists():
        print(f"📝 AsyncAPI spec available at: {asyncapi_source}")
    else:
        print(f"⚠️  AsyncAPI spec not found at: {asyncapi_source}")

    # Startup: Start real-time data feeds
    try:
        from trading_api.core.realtime_service import realtime_data_service

        await realtime_data_service.start()
        print("🚀 Real-time data feeds started")
    except Exception as e:
        print(f"⚠️  Failed to start real-time data feeds: {e}")

    yield

    # Shutdown: Stop real-time data feeds
    try:
        from trading_api.core.realtime_service import realtime_data_service

        await realtime_data_service.stop()
        print("🛑 Real-time data feeds stopped")
    except Exception as e:
        print(f"⚠️  Error stopping real-time data feeds: {e}")


app = FastAPI(
    title="Trading API",
    description=(
        "A comprehensive trading API server with real-time market data "
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
        {"name": "websocket", "description": "Real-time WebSocket communication"},
    ],
    lifespan=lifespan,
)

# Include version 1 routes
app.include_router(health_router, prefix="/api/v1", tags=["v1"])
app.include_router(versions_router, prefix="/api/v1", tags=["v1"])
app.include_router(datafeed_router, prefix="/api/v1", tags=["v1"])
app.include_router(websockets_router, prefix="/api/v1", tags=["v1"])


# Add version information to root endpoint
@app.get("/", tags=["root"])
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
        "websocket": "/api/v1/ws/v1",
        "websocket_config": "/api/v1/ws/config",
        "asyncapi": "/api/v1/asyncapi.yaml",
    }


class AsyncAPIResponse(BaseModel):
    """Response model for AsyncAPI spec"""

    content: str


@app.get(
    "/api/v1/asyncapi.yaml", tags=["documentation"], response_model=AsyncAPIResponse
)
async def get_asyncapi_spec() -> AsyncAPIResponse:
    """Get AsyncAPI specification for WebSocket endpoints"""
    backend_dir = Path(__file__).parent.parent.parent
    asyncapi_file = backend_dir / "asyncapi.yaml"

    try:
        with open(asyncapi_file, "r") as f:
            content = f.read()
        return AsyncAPIResponse(content=content)
    except FileNotFoundError:
        return AsyncAPIResponse(content="AsyncAPI specification not found")
