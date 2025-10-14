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

from .generic import WsRouter

if TYPE_CHECKING:
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
else:
    from .generated import BarWsRouter


router = BarWsRouter(route="bars", tags=["datafeed"])
bars_topic_builder = router.topic_builder
