"""Main FastAPI application with API versioning support."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI

from trading_api.api.health import router as health_router
from trading_api.api.versions import router as versions_router
from trading_api.core.versioning import APIVersion


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
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

    # Shutdown: cleanup if needed
    pass


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
    ],
    lifespan=lifespan,
)

# Include version 1 routes
app.include_router(health_router, prefix="/api/v1", tags=["v1"])
app.include_router(versions_router, prefix="/api/v1", tags=["v1"])


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
    }
