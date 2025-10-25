import logging
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel

from external_packages.fastws import Client
from trading_api.models import SubscriptionResponse, SubscriptionUpdate
from trading_api.ws.router_interface import (
    WsRouterInterface,
    WsRouteService,
    topicTracker,
)

logger = logging.getLogger(__name__)


_TRequest = TypeVar("_TRequest", bound=BaseModel)
_TData = TypeVar("_TData", bound=BaseModel)


# TODO : implement secure route that encapsulates authentication/authorization per client
class WsRouter(WsRouterInterface, Generic[_TRequest, _TData]):
    def __init__(
        self,
        *,
        route: str = "",
        tags: list[str | Enum] | None = None,
        service: WsRouteService,
    ) -> None:
        super().__init__(prefix=f"{route}.", tags=tags)
        self.route = route
        self.service = service
        self.topic_queues: dict[str, topicTracker[_TData]] = {}

        @self.recv("update")  # type: ignore[misc]
        def update(
            payload: SubscriptionUpdate[_TData],
        ) -> SubscriptionUpdate[_TData]:
            """Broadcast data updates to subscribed clients"""
            return payload

        @self.send("subscribe", reply="subscribe.response")  # type: ignore[misc]
        async def send_subscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            topic = self.topic_builder(payload)
            client.subscribe(topic)

            if topic not in self.topic_queues:
                await self.service.create_topic(topic)

                def send_update(data: _TData) -> None:
                    update(SubscriptionUpdate[_TData](topic=topic, payload=data))

                self.topic_queues[topic] = topicTracker[_TData](
                    topic, self.service, send_update
                )
            else:
                self.topic_queues[topic].inc()

            logger.info(f"Client {client.uid} subscribed to topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                message="Subscribed",
                topic=topic,
            )

        @self.send("unsubscribe", reply="unsubscribe.response")  # type: ignore[misc]
        def send_unsubscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Unsubscribe from data updates"""
            topic = self.topic_builder(payload)
            client.unsubscribe(topic)

            self.topic_queues[topic].dec()

            logger.info(f"Client {client.uid} unsubscribed from topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                message="Unsubscribed",
                topic=topic,
            )
