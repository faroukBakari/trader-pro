"""DEPRECATED: Re-export from shared.ws for backward compatibility.

This module is deprecated. Use 'from trading_api.shared.ws import ...' instead.
Will be removed after full migration to modular architecture.

DEPRECATION NOTICE:
- DatafeedWsRouters has moved to trading_api.modules.datafeed.ws
- BrokerWsRouters has moved to trading_api.modules.broker.ws

Please update imports to use:
    from trading_api.modules.datafeed import DatafeedWsRouters
    from trading_api.modules.broker import BrokerWsRouters
"""

from trading_api.shared.ws import WsRouter, WsRouterInterface, WsRouteService

from ..modules.broker.ws import BrokerWsRouters

# Backward compatibility re-exports (DEPRECATED)
from ..modules.datafeed.ws import DatafeedWsRouters

__all__ = [
    "BrokerWsRouters",
    "DatafeedWsRouters",
    "WsRouter",
    "WsRouterInterface",
    "WsRouteService",
]
