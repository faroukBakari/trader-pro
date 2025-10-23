from . import broker, datafeed
from .router_interface import WsRouterInterface

# Consolidate all WebSocket routers from different modules
ws_routers: list[WsRouterInterface] = [
    *datafeed.ws_routers,
    *broker.ws_routers,
]

__all__ = ["ws_routers"]
