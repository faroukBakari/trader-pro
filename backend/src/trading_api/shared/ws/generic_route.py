import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from external_packages.fastws import Client
from trading_api.models import SubscriptionResponse, SubscriptionUpdate
from trading_api.shared.ws.ws_route_interface import WsRouteInterface, WsRouteService

logger = logging.getLogger(__name__)


_TRequest = TypeVar("_TRequest", bound=BaseModel)
_TData = TypeVar("_TData", bound=BaseModel)


# TODO : implement secure route that encapsulates authentication/authorization per client
# TODO : implement server side subscription cancelation
class WsRouter(WsRouteInterface, Generic[_TRequest, _TData]):
    def __init__(self, service: WsRouteService, *args: Any, **kwargs: Any) -> None:
        # Validate service implements WsRouteService protocol BEFORE initialization
        if not hasattr(service, "create_topic"):
            raise TypeError(
                f"Service must implement WsRouteService protocol (missing 'create_topic' method). "
                f"Got: {type(service).__name__}"
            )
        if not hasattr(service, "remove_topic"):
            raise TypeError(
                f"Service must implement WsRouteService protocol (missing 'remove_topic' method). "
                f"Got: {type(service).__name__}"
            )

        super().__init__(*args, **kwargs)
        self.service = service
        self.topic_trackers: dict[str, int] = {}

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

            if topic not in self.topic_trackers:
                # nested function to avoid binding issue in closure
                def topic_update(data: _TData) -> None:
                    self.updates_queue.put_nowait(
                        SubscriptionUpdate(
                            topic=topic,
                            payload=data,
                        )
                    )

                await self.service.create_topic(topic, topic_update)
                self.topic_trackers[topic] = 1
            else:
                self.topic_trackers[topic] = self.topic_trackers[topic] + 1

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

            self.topic_trackers[topic] = self.topic_trackers[topic] - 1
            if self.topic_trackers[topic] <= 0:
                self.service.remove_topic(topic)
                self.topic_trackers.pop(topic, None)

            logger.info(f"Client {client.uid} unsubscribed from topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                message="Unsubscribed",
                topic=topic,
            )
