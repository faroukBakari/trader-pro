"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

import logging
import os
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    QuoteData,
    QuoteDataSubscriptionRequest,
)
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.module_router_generator import generate_module_routers
from trading_api.shared.ws.router_interface import WsRouterInterface, WsRouteService

if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]

# Module logger for app_factory
logger = logging.getLogger(__name__)


class DatafeedWsRouters(list[WsRouterInterface]):
    def __init__(self, datafeed_service: WsRouteService):
        # Import generated routers locally to avoid circular import
        module_name = os.path.basename(os.path.dirname(__file__))
        try:
            generated = generate_module_routers(module_name)
            if generated:
                logger.info(f"Generated WS routers for module '{module_name}'")
        except RuntimeError as e:
            # Fail loudly with module context
            logger.error(
                f"WebSocket router generation failed for module '{module_name}'!"
            )
            logger.error(str(e))
            raise
        if not TYPE_CHECKING:
            from .ws_generated import BarWsRouter, QuoteWsRouter

        # Instantiate routers
        bar_router = BarWsRouter(
            route="bars", tags=[module_name], service=datafeed_service
        )
        quote_router = QuoteWsRouter(
            route="quotes", tags=[module_name], service=datafeed_service
        )

        super().__init__(
            [
                bar_router,
                quote_router,
            ]
        )
