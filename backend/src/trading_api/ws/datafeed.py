"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

import logging

from external_packages.fastws import Client, OperationRouter
from trading_api.models import BarsSubscriptionRequest, SubscriptionResponse
from trading_api.models.common import SubscriptionUpdate
from trading_api.models.market.bars import Bar

logger = logging.getLogger(__name__)
router = OperationRouter(prefix="bars.", tags=["datafeed"])


# Topic builder for bars: bars:SYMBOL:RESOLUTION
def bars_topic_builder(params: BarsSubscriptionRequest) -> str:
    return f"bars:{params.symbol}:{params.resolution}"


@router.send("subscribe", reply="subscribe.response")  # type: ignore[misc]
async def send_subscribe(
    payload: BarsSubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    """Subscribe to real-time data updates"""
    topic = bars_topic_builder(payload)
    client.subscribe(topic)

    logger.info(f"Client {client.uid} subscribed to topic: {topic}")

    return SubscriptionResponse(
        status="ok",
        message=f"Subscribed to {payload.symbol}",
        topic=topic,
    )


@router.send("unsubscribe", reply="unsubscribe.response")  # type: ignore[misc]
async def send_unsubscribe(
    payload: BarsSubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    """Unsubscribe from data updates"""
    topic = bars_topic_builder(payload)
    client.unsubscribe(topic)

    logger.info(f"Client {client.uid} unsubscribed from topic: {topic}")

    return SubscriptionResponse(
        status="ok",
        message=f"Unsubscribed from {payload.symbol}",
        topic=topic,
    )


@router.recv("update")  # type: ignore[misc]
async def update(payload: SubscriptionUpdate[Bar]) -> SubscriptionUpdate[Bar]:
    """Broadcast data updates to subscribed clients"""
    return payload
