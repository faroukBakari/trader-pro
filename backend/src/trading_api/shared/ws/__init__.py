"""Shared WebSocket infrastructure - Router interface and generic route utilities."""

from .fastws_adapter import FastWSAdapter
from .generic_route import WsRouter
from .ws_route_interface import WsRouteInterface, WsRouteService

__all__ = [
    "WsRouter",
    "WsRouteInterface",
    "WsRouteService",
    "FastWSAdapter",
]
