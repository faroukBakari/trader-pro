"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

import logging
from pathlib import Path

from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    QuoteData,
    QuoteDataSubscriptionRequest,
)
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.ws_router import WsRouterBase, WsRouteService

# Module logger for app_factory
logger = logging.getLogger(__name__)


class BarRouter(WsRouter[BarsSubscriptionRequest, Bar]):
    pass


class QuoteRouter(WsRouter[QuoteDataSubscriptionRequest, QuoteData]):
    pass


class DatafeedWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        # Import generated routers locally to avoid circular import
        module_name = Path(__file__).parent.parent.parent.name

        # Instantiate routers
        bar_router = BarRouter(route="bars", tags=[module_name], service=service)
        quote_router = QuoteRouter(route="quotes", tags=[module_name], service=service)

        super().__init__(
            [
                bar_router,
                quote_router,
            ],
            service=service,
        )
