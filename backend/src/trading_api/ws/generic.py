"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

import logging
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel

from external_packages.fastws import Client, OperationRouter
from trading_api.models import SubscriptionResponse, SubscriptionUpdate

__TRequest = TypeVar("__TRequest", bound=BaseModel)
__TData = TypeVar("__TData", bound=BaseModel)

logger = logging.getLogger(__name__)


class WsRouter(OperationRouter, Generic[__TRequest, __TData]):
    def __init__(
        self,
        *,
        route: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        super().__init__(prefix=f"{route}.", tags=tags)
        self.route = route

        @self.send("subscribe", reply="subscribe.response")  # type: ignore[misc]
        async def send_subscribe(
            payload: __TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            topic = self.topic_builder(payload)
            client.subscribe(topic)

            logger.info(f"Client {client.uid} subscribed to topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                message="Subscribed",
                topic=topic,
            )

        @self.send("unsubscribe", reply="unsubscribe.response")  # type: ignore[misc]
        async def send_unsubscribe(
            payload: __TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Unsubscribe from data updates"""
            topic = self.topic_builder(payload)
            client.unsubscribe(topic)

            logger.info(f"Client {client.uid} unsubscribed from topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                message="Unsubscribed",
                topic=topic,
            )

        @self.recv("update")  # type: ignore[misc]
        async def update(
            payload: SubscriptionUpdate[__TData],
        ) -> SubscriptionUpdate[__TData]:
            """Broadcast data updates to subscribed clients"""
            return payload

        # Topic builder for bars: bars:SYMBOL:RESOLUTION

    def topic_builder(self, params: BaseModel) -> str:
        return ":".join(
            [self.route] + [str(getattr(params, attr)) for attr in sorted(vars(params))]
        )
