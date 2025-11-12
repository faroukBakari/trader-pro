"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    QuoteData,
    QuoteDataSubscriptionRequest,
)
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.ws_route_interface import WsRouterInterface, WsRouteService

if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]

# Module logger for app_factory
logger = logging.getLogger(__name__)


class DatafeedWsRouters(WsRouterInterface):
    def __init__(self, service: WsRouteService):
        # Import generated routers locally to avoid circular import
        module_name = Path(__file__).parent.parent.parent.name

        self.generate_routers(__file__)
        if not TYPE_CHECKING:
            from .ws_generated import BarWsRouter, QuoteWsRouter

        # Instantiate routers
        bar_router = BarWsRouter(route="bars", tags=[module_name], service=service)
        quote_router = QuoteWsRouter(
            route="quotes", tags=[module_name], service=service
        )

        super().__init__(
            [
                bar_router,
                quote_router,
            ],
            service=service,
        )
