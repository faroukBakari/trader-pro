from fastapi import APIRouter

from . import broker, datafeed, health, versions

api_routers: list[APIRouter] = [
    health.router,
    versions.router,
    datafeed.router,
    broker.router,
]

__all__ = ["api_routers"]
