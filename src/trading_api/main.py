"""Main FastAPI application."""
from fastapi import FastAPI

from trading_api.api.health import router as health_router

app = FastAPI(
    title="Trading API",
    description=(
        "A comprehensive trading API server with real-time market data "
        "and portfolio management"
    ),
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_tags=[{"name": "health", "description": "Health check operations"}],
)

app.include_router(health_router, prefix="/api/v1")
