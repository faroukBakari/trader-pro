from .datafeed import ws_routers as datafeed_ws_routers
from .router_interface import WsRouterInterface

ws_routers: list[WsRouterInterface] = datafeed_ws_routers

__all__ = ["ws_routers"]
