from . import broker
from .datafeed import ws_routers as datafeed_ws_routers
from .router_interface import WsRouterInterface

# Consolidate all WebSocket routers from different modules
ws_routers: list[WsRouterInterface] = [
    *datafeed_ws_routers,
    *broker.ws_routers,
]

__all__ = [
    "ws_routers",
    "broker",
]
