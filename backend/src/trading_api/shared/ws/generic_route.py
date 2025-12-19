import asyncio
import logging
import os
from typing import Any, Generic, Literal, TypeVar, get_args

from fastapi.websockets import WebSocketState
from pydantic import BaseModel

from external_packages.fastws import Client
from trading_api.models import (
    ErrorPayload,
    SubscriptionError,
    SubscriptionRequest,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from trading_api.models.exceptions import TradingApiException
from trading_api.shared.exception_handlers import log_exception
from trading_api.shared.ws.ws_router import WsRouteFeature, WsRouteService

logger = logging.getLogger(__name__)

DEBUG_WS_ROUTER = os.environ.get("DEBUG_WS_ROUTER") == "true"
debug_log = logger.info


_TRequest = TypeVar("_TRequest", bound=BaseModel)
_TData = TypeVar("_TData", bound=BaseModel)


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
            payload: SubscriptionRequest[_TRequest],
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            self._clients.add(client)
            topic = self.topic_builder(payload.sub_params)
            if topic not in self._topics:
                self._create_topic(topic)
            client.subscribe(topic)
            if DEBUG_WS_ROUTER:
                debug_log(f"Client {client.uid} subscribed to topic: {topic}")
            return SubscriptionResponse(status="ok", sub_id=payload.sub_id, topic=topic)

        def recv_update(
            payload: SubscriptionUpdate[_TData],
        ) -> SubscriptionUpdate[_TData]:
            """Broadcast data updates to subscribed clients"""
            return payload

        def send_unsubscribe(
            payload: SubscriptionRequest[_TRequest],
            client: Client,
        ) -> SubscriptionResponse:
            """Unsubscribe from data updates"""
            topic = self.topic_builder(payload.sub_params)
            client.unsubscribe(topic)
            if DEBUG_WS_ROUTER:
                debug_log(f"Client {client.uid} unsubscribed from topic: {topic}")

            self._clients = self._refresh_active_clients()

            remaining_topic_clients = [
                clt for clt in self._clients if topic in clt.topics
            ]
            if not remaining_topic_clients:
                if DEBUG_WS_ROUTER:
                    debug_log(
                        f"No more clients for topic : {topic} in router {self.route}"
                    )
                self._remove_topic(topic)

            remaining_client_topics = [
                tpc for tpc in client.topics if tpc in self._topics
            ]
            if not remaining_client_topics:
                if DEBUG_WS_ROUTER:
                    debug_log(
                        f"No more topics for client: {client.uid} in router {self.route}"
                    )
                self._clients.discard(client)

            return SubscriptionResponse(
                status="ok",
                sub_id=payload.sub_id,
                topic=topic,
            )

        recv_update.__annotations__["payload"] = SubscriptionUpdate[data_type]  # type: ignore[valid-type]
        recv_update.__annotations__["return"] = SubscriptionUpdate[data_type]  # type: ignore[valid-type]
        self.recv("update")(recv_update)

        # Register error message type for AsyncAPI spec generation
        def recv_error(
            payload: SubscriptionError,
        ) -> SubscriptionError:
            """Broadcast error notifications to subscribed clients"""
            return payload

        self.recv("error")(recv_error)

        # Use correct parameter names and wrap request_type in SubscriptionRequest
        send_subscribe.__annotations__["payload"] = SubscriptionRequest[request_type]  # type: ignore[valid-type]
        self.send("subscribe", reply="subscribe.response")(send_subscribe)
        send_unsubscribe.__annotations__["payload"] = SubscriptionRequest[request_type]  # type: ignore[valid-type]
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

    async def _broadcast_payload(
        self,
        topic: str,
        payload: BaseModel,
        operation: Literal["update", "error"],
    ) -> None:
        """Broadcast payload to all clients subscribed to topic.

        Args:
            topic: Target subscription topic
            payload: Pydantic model to serialize (SubscriptionUpdate or SubscriptionError)
            operation: Message type suffix ("update" or "error")
        """
        self._clients = self._refresh_active_clients()
        topic_clients = [client for client in self._clients if topic in client.topics]

        if not topic_clients:
            if DEBUG_WS_ROUTER:
                debug_log(f"No more clients for topic : {topic} in router {self.route}")
            self._remove_topic(topic)
            return

        try:
            # Build message with pre-serialized payload to avoid model_dump overhead
            msg = f'{{"type":"{self.route}.{operation}","payload":{payload.model_dump_json()}}}'

            await asyncio.gather(
                *(client.ws.send_text(msg) for client in topic_clients)
            )

            if DEBUG_WS_ROUTER:
                debug_log(f"Broadcasted {self.route}.{operation} for topic {topic}")
        except Exception as e:
            logger.exception(
                f"Error during FastWS {self.route}.{operation} broadcast, {e}"
            )
            await asyncio.sleep(1)

    async def _broadcast_update(self, update: SubscriptionUpdate) -> None:
        """Broadcast data update to all clients subscribed to topic.

        Convenience wrapper around _broadcast_payload for data updates.
        """
        await self._broadcast_payload(update.topic, update, "update")

    def _create_topic(self, topic: str) -> None:
        """Create a new topic and register callbacks with the service.

        Sets up both update and error callbacks:
        - topic_update: Called by service/provider with data updates
        - topic_error: Called by service/provider with errors

        The error callback wrapper handles:
        - Recoverable errors: just log and broadcast error message
        - Unrecoverable errors: log and broadcast error message + remove topic and unsubscribe clients
        """

        async def topic_update(data: _TData) -> None:
            """Callback for data updates - wraps data in SubscriptionUpdate."""
            await self._broadcast_update(
                SubscriptionUpdate(
                    topic=topic,
                    payload=data,
                ),
            )

        async def topic_error(
            exc: TradingApiException,
            recoverable: bool = False,
            retry_after_ms: int | None = None,
        ) -> None:
            """Callback for errors - handles recoverable vs unrecoverable.

            Args:
                exc: The exception that occurred
                recoverable: If True, broadcast error and keep connection open.
                            If False, remove topic and unsubscribe clients.
                retry_after_ms: Suggested retry delay for recoverable errors
            """

            # Recoverable errors: broadcast error message, keep connection open
            await self._broadcast_payload(
                topic,
                SubscriptionError(
                    topic=topic,
                    error=ErrorPayload.from_exception(exc),
                    recoverable=recoverable,
                    retry_after_ms=retry_after_ms,
                ),
                "error",
            )

            # Unrecoverable errors: Unsubscribe all clients subscribed to this topic
            topic_clients = [c for c in self._clients if topic in c.topics]
            for client in topic_clients:
                log_exception(exc, client.ws)
                if not recoverable:
                    client.unsubscribe(topic)

            # Unrecoverable errors: remove topic
            if not recoverable:
                self._topics.discard(topic)

        if DEBUG_WS_ROUTER:
            debug_log(f"Creating new topic in {self.route} service: {topic}")

        self.service.create_topic(topic, topic_update, topic_error)
        self._topics.add(topic)

    def _remove_topic(self, topic: str) -> None:
        if DEBUG_WS_ROUTER:
            debug_log(f"Removing topic : {topic}")
        self._topics.discard(topic)
        self.service.remove_topic(topic)

    def _refresh_active_clients(self) -> set[Client]:
        return set(
            [
                client
                for client in self._clients
                if (
                    client.ws.client_state == WebSocketState.CONNECTED
                    and client.ws.application_state == WebSocketState.CONNECTED
                )
            ]
        )


# TODO !!!! need to debug bar unsubscribe / switch resolution more carefully !!!!
