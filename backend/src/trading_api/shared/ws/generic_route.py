import asyncio
import logging
from typing import Any, Generic, Type, TypeVar, get_args

from pydantic import BaseModel

from external_packages.fastws import Client
from trading_api.models import SubscriptionResponse, SubscriptionUpdate
from trading_api.shared.ws.ws_router import WsRouteFeature, WsRouteService

logger = logging.getLogger(__name__)


_TRequest = TypeVar("_TRequest", bound=BaseModel)
_TData = TypeVar("_TData", bound=BaseModel)


# TODO : implement secure route that encapsulates authentication/authorization per client
# TODO : implement server side subscription cancelation


async def unset_broadcast_update(route: str, _: SubscriptionUpdate) -> None:
    raise NotImplementedError(f"Broadcast update function not set for route {route}.")


class WsRouter(WsRouteFeature, Generic[_TRequest, _TData]):

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

        request_type, data_type = self._resolve_generic_types()

        super().__init__(*args, **kwargs)
        self.service = service
        self.topic_trackers: dict[str, int] = {}
        self._active_clients: set[Client] = set()

        def update(
            payload: SubscriptionUpdate[_TData],
        ) -> SubscriptionUpdate[_TData]:
            """Broadcast data updates to subscribed clients"""
            return payload

        update.__annotations__["payload"] = SubscriptionUpdate[data_type]  # type: ignore[valid-type]
        update.__annotations__["return"] = SubscriptionUpdate[data_type]  # type: ignore[valid-type]
        self.recv("update")(update)

        async def send_subscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            self._active_clients.add(client)
            topic = self.topic_builder(payload)
            client.subscribe(topic)

            if topic not in self.topic_trackers:
                # nested function to avoid binding issue in closure
                async def topic_update(data: _TData) -> None:
                    await self.broadcast_update(
                        self.route,
                        SubscriptionUpdate(
                            topic=topic,
                            payload=data,
                        ),
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

        send_subscribe.__annotations__["payload"] = request_type
        self.send("subscribe", reply="subscribe.response")(send_subscribe)

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

        send_unsubscribe.__annotations__["payload"] = request_type
        self.send("unsubscribe", reply="unsubscribe.response")(send_unsubscribe)

    def _resolve_generic_types(self):
        """
        Introspects the class to find the Generic type arguments.
        """
        try:
            types = next(iter(getattr(self.__class__, "__orig_bases__", [])), None)
            assert types is not None, "Generic types not found."
            return get_args(types)
        except Exception as e:
            raise TypeError(
                f"Could not resolve generic types for {self.__class__.__name__}: {e} "
                "Ensure you inherit like: class MyRouter(WsRouter[Req, Res]): ..."
            )

    async def broadcast_update(self, route: str, update: SubscriptionUpdate) -> None:
        topic = update.topic
        clients = [client for client in self._active_clients if topic in client.topics]

        if not clients:
            logger.info(f"No clients subscribed to topic: {update.topic}")
            await asyncio.sleep(1)
            return

        try:
            # Build message with pre-serialized payload to avoid model_dump overhead
            # update.model_dump_json() uses orjson internally when configured
            msg = f'{{"type":"{route}.update","payload":{update.model_dump_json()}}}'

            await asyncio.gather(*(client.ws.send_text(msg) for client in clients))

            logger.info(f"Broadcasted message from router: {update.topic}: {update}")
        except Exception as e:
            logger.warning(f"Error during FastWS {route}.update broadcast, {e}")
            await asyncio.sleep(1)
