import asyncio
import logging
from typing import Any, Generic, TypeVar, get_args

from fastapi.websockets import WebSocketState
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
        self._clients: set[Client] = set()
        self._topics: set[str] = set()

        async def send_subscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            topic = await self._register_topic(payload)
            self._clients.add(client)
            client.subscribe(topic)
            logger.info(f"Client {client.uid} subscribed to topic: {topic}")
            return SubscriptionResponse(
                status="ok",
                message="Subscribed",
                topic=topic,
            )

        def update(
            payload: SubscriptionUpdate[_TData],
        ) -> SubscriptionUpdate[_TData]:
            """Broadcast data updates to subscribed clients"""
            return payload

        def send_unsubscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Unsubscribe from data updates"""
            topic = self.topic_builder(payload)
            try:
                self._clients = set(
                    [
                        client
                        for client in self._clients
                        if (
                            client.ws.client_state == WebSocketState.CONNECTED
                            and client.ws.application_state == WebSocketState.CONNECTED
                        )
                    ]
                )

                if client in self._clients:
                    client.unsubscribe(topic)
                    logger.info(f"Client {client.uid} unsubscribed from topic: {topic}")

                    remaining_topic_clients = [
                        clt
                        for clt in self._clients
                        if (
                            clt.ws.client_state == WebSocketState.CONNECTED
                            and clt.ws.application_state == WebSocketState.CONNECTED
                            and topic in clt.topics
                        )
                    ]

                    if not remaining_topic_clients:
                        logger.info(f"No more clients for topic : {topic}")
                        self._unregister_topic(topic)

                    if not client.topics:
                        self._clients.discard(client)

                    logger.info(f"Client {client.uid} unsubscribed from topic: {topic}")

                else:
                    logger.warning(
                        f"Client {client.uid} tried to unsubscribe from topic"
                        f" {topic} but was not found in clients list."
                    )

                return SubscriptionResponse(
                    status="ok",
                    message="Unsubscribed",
                    topic=topic,
                )
            except Exception as e:
                logger.warning(f"Error during unsubscribe for topic {topic}: {e}")
                return SubscriptionResponse(
                    status="error",
                    message=f"Unsubscribe failed: {e}",
                    topic="",
                )

        update.__annotations__["payload"] = SubscriptionUpdate[data_type]  # type: ignore[valid-type]
        update.__annotations__["return"] = SubscriptionUpdate[data_type]  # type: ignore[valid-type]
        self.recv("update")(update)
        send_subscribe.__annotations__["payload"] = request_type
        self.send("subscribe", reply="subscribe.response")(send_subscribe)
        send_unsubscribe.__annotations__["payload"] = request_type
        self.send("unsubscribe", reply="unsubscribe.response")(send_unsubscribe)

    def _resolve_generic_types(self) -> tuple[type[_TRequest], type[_TData]]:
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
        self._clients = set(
            [
                client
                for client in self._clients
                if (
                    client.ws.client_state == WebSocketState.CONNECTED
                    and client.ws.application_state == WebSocketState.CONNECTED
                )
            ]
        )
        topic_clients = [client for client in self._clients if topic in client.topics]

        if not topic_clients:
            logger.info(f"No more client for topic : {update.topic}")
            self._unregister_topic(topic)
            await asyncio.sleep(1)
            return

        try:
            # Build message with pre-serialized payload to avoid model_dump overhead
            # update.model_dump_json() uses orjson internally when configured
            msg = f'{{"type":"{route}.update","payload":{update.model_dump_json()}}}'

            await asyncio.gather(
                *(client.ws.send_text(msg) for client in topic_clients)
            )

            logger.info(f"Broadcasted message from router: {update.topic}: {update}")
        except Exception as e:
            logger.warning(f"Error during FastWS {route}.update broadcast, {e}")
            await asyncio.sleep(1)

    async def _register_topic(self, payload: _TRequest) -> str:
        topic = self.topic_builder(payload)

        if topic not in self._topics:

            async def topic_update(data: _TData) -> None:
                await self.broadcast_update(
                    self.route,
                    SubscriptionUpdate(
                        topic=topic,
                        payload=data,
                    ),
                )

            logger.info(f"Registering new topic in router: {topic}")
            await self.service.create_topic(topic, topic_update)
            self._topics.add(topic)

        return topic

    def _unregister_topic(self, topic: str) -> None:
        logger.info(f"Unregistering topic : {topic}")
        self._topics.discard(topic)
        self.service.remove_topic(topic)
