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

from .generic_route import WsRouter
from .router_interface import WsRouterInterface

if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
else:
    from .generated import BarWsRouter, QuoteWsRouter


bar_router = BarWsRouter(route="bars", tags=["datafeed"])
bars_topic_builder = bar_router.topic_builder

quote_router = QuoteWsRouter(route="quotes", tags=["datafeed"])
quotes_topic_builder = quote_router.topic_builder


ws_routers: list[WsRouterInterface] = [bar_router, quote_router]
