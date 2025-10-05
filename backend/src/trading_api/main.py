"""Main FastAPI application with API versioning support."""

from fastapi import FastAPI

from trading_api.api.health import router as health_router
from trading_api.api.versions import router as versions_router
from trading_api.core.versioning import APIVersion

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
