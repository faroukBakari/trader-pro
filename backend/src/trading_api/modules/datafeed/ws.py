"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

from typing import TYPE_CHECKING, TypeAlias

from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    QuoteData,
    QuoteDataSubscriptionRequest,
)
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.router_interface import WsRouterInterface, WsRouteService

if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]


class DatafeedWsRouters(list[WsRouterInterface]):
    def __init__(self, datafeed_service: WsRouteService):
        # Import generated routers locally to avoid circular import
        if not TYPE_CHECKING:
            from .ws_generated import BarWsRouter, QuoteWsRouter

        # Instantiate routers
        bar_router = BarWsRouter(
            route="bars", tags=["datafeed"], service=datafeed_service
        )
        quote_router = QuoteWsRouter(
            route="quotes", tags=["datafeed"], service=datafeed_service
        )

        super().__init__(
            [
                bar_router,
                quote_router,
            ]
        )
