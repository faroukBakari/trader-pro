"""Shared WebSocket infrastructure - Router interface and generic route utilities."""

from .generic_route import WsRouter
from .router_interface import WsRouterInterface, WsRouteService

__all__ = [
    "WsRouter",
    "WsRouterInterface",
    "WsRouteService",
]
