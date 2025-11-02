"""Shared WebSocket infrastructure - Router interface and generic route utilities."""

from .generic_route import WsRouter
from .router_interface import WsRouteInterface, WsRouteService

__all__ = [
    "WsRouter",
    "WsRouteInterface",
    "WsRouteService",
]
