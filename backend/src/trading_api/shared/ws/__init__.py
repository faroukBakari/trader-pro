"""Shared WebSocket infrastructure - Router interface and generic route utilities."""

from .fastws_adapter import FastWSAdapter
from .generic_route import WsRouter
from .ws_router import WsRouteFeature, WsRouteService

__all__ = [
    "WsRouter",
    "WsRouteFeature",
    "WsRouteService",
    "FastWSAdapter",
]
