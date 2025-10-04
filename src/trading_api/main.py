"""Main FastAPI application."""
from fastapi import FastAPI

from trading_api.api.health import router as health_router

app = FastAPI(
    title="Trading API",
    description="A FastAPI-based trading API server",
    version="0.1.0",
)

app.include_router(health_router)
