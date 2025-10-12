"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

import logging
from typing import Any, Callable

from external_packages.fastws import Client, OperationRouter
from trading_api.models.market.bars import Bar
from trading_api.ws.common import SubscriptionRequest, SubscriptionResponse

logger = logging.getLogger(__name__)
router = OperationRouter(prefix="bars.", tags=["datafeed"])

# Type alias for topic builder
TopicBuilder = Callable[[str, dict[str, Any]], str]


# Topic builder for bars: bars:SYMBOL:RESOLUTION
def bars_topic_builder(symbol: str, params: dict[str, Any]) -> str:
    return f"bars:{symbol}:{params.get('resolution', '1')}"


@router.send("subscribe", reply="subscribe.response")  # type: ignore[misc]
async def send_subscribe(
    payload: SubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    """Subscribe to real-time data updates"""
    topic = bars_topic_builder(payload.symbol, payload.params)
    client.subscribe(topic)

    logger.debug(f"Client {client.uid} subscribed to topic: {topic}")

    return SubscriptionResponse(
        status="ok",
        symbol=payload.symbol,
        message=f"Subscribed to {payload.symbol}",
        topic=topic,
    )


@router.send("unsubscribe", reply="unsubscribe.response")  # type: ignore[misc]
async def send_unsubscribe(
    payload: SubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    """Unsubscribe from data updates"""
    topic = bars_topic_builder(payload.symbol, payload.params)
    client.unsubscribe(topic)

    logger.debug(f"Client {client.uid} unsubscribed from topic: {topic}")

    return SubscriptionResponse(
        status="ok",
        symbol=payload.symbol,
        message=f"Unsubscribed from {payload.symbol}",
        topic=topic,
    )


@router.recv("update")  # type: ignore[misc]
async def update(payload: Bar) -> Bar:
    """Broadcast data updates to subscribed clients"""
    return payload
