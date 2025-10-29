"""DEPRECATED: Re-export from shared.ws for backward compatibility.

This module is deprecated. Use 'from trading_api.shared.ws import ...' instead.
Will be removed after full migration to modular architecture.

Note: broker.py and datafeed.py remain here as they belong to modules, not shared.
"""

from trading_api.shared.ws import WsRouter, WsRouterInterface, WsRouteService

from .broker import BrokerWsRouters
from .datafeed import DatafeedWsRouters

__all__ = [
    "BrokerWsRouters",
    "DatafeedWsRouters",
    "WsRouter",
    "WsRouterInterface",
    "WsRouteService",
]
