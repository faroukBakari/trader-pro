"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import logging
from typing import Annotated, Any, Callable, Generic, Type, TypeVar

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from external_packages.fastws import Client, FastWS, Message, OperationRouter
from trading_api.ws.common import SubscriptionRequest, SubscriptionResponse

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Type alias for topic builder
TopicBuilder = Callable[[str, dict[str, Any]], str]


class FastWSAdapter(Generic[T]):
    """
    Self-contained WebSocket adapter with embedded endpoint

    Creates a FastWS service with subscribe/unsubscribe operations
    and registers its own WebSocket endpoint.

    Type parameter T: The business model type (e.g., Bar)
    """

    def __init__(
        self,
        route_prefix: str,
        data_model: Type[T],
        endpoint_path: str,
        topic_builder: TopicBuilder,
        title: str,
        description: str,
        version: str = "1.0.0",
        asyncapi_url: str | None = None,
        asyncapi_docs_url: str | None = None,
        heartbeat_interval: float = 30.0,
        max_connection_lifespan: float | None = 3600.0,
    ):
        """
        Initialize FastWS adapter with generic operations

        Args:
            route_prefix: Route prefix (e.g., "bars") - used in operation names
            data_model: The business data model class (e.g., Bar)
            endpoint_path: WebSocket endpoint path (e.g., "/api/v1/ws/bars")
            topic_builder: Function to build topic from (symbol, params) -> topic
            title: AsyncAPI title
            description: AsyncAPI description
            version: API version
            asyncapi_url: AsyncAPI JSON endpoint path
            asyncapi_docs_url: AsyncAPI UI endpoint path
            heartbeat_interval: WebSocket heartbeat interval in seconds
            max_connection_lifespan: Maximum connection duration in seconds
        """
        self.route_prefix = route_prefix.rstrip(".")
        self.data_model = data_model
        self.endpoint_path = endpoint_path
        self.topic_builder = topic_builder

        # Initialize FastWS service
        self.service = FastWS(
            title=title,
            version=version,
            description=description,
            asyncapi_url=asyncapi_url,
            asyncapi_docs_url=asyncapi_docs_url,
            heartbeat_interval=heartbeat_interval,
            max_connection_lifespan=max_connection_lifespan,
            debug=True,
        )

        # Create router with prefix
        self.router = OperationRouter(prefix=f"{self.route_prefix}.")

        # Register operations (subscribe/unsubscribe only)
        self._register_operations()

        # Include router in service
        self.service.include_router(self.router)

        logger.info(f"✅ FastWSAdapter initialized for '{self.route_prefix}'")

    def _register_operations(self) -> None:
        """Register subscribe, unsubscribe, and update operations"""

        # Store data_model in local scope for use in decorators
        data_model = self.data_model

        # Subscribe operation
        @self.router.send("subscribe", reply="subscribe.response")  # type: ignore[misc]
        async def send_subscribe(
            payload: SubscriptionRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            topic = self.topic_builder(payload.symbol, payload.params)
            client.subscribe(topic)

            logger.debug(f"Client {client.uid} subscribed to topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                symbol=payload.symbol,
                message=f"Subscribed to {payload.symbol}",
                topic=topic,
            )

        # Unsubscribe operation
        @self.router.send(
            "unsubscribe", reply="unsubscribe.response"
        )  # type: ignore[misc]
        async def send_unsubscribe(
            payload: SubscriptionRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Unsubscribe from data updates"""
            topic = self.topic_builder(payload.symbol, payload.params)
            client.unsubscribe(topic)

            logger.debug(f"Client {client.uid} unsubscribed from topic: {topic}")

            return SubscriptionResponse(
                status="ok",
                symbol=payload.symbol,
                message=f"Unsubscribed from {payload.symbol}",
                topic=topic,
            )

        # Update operation (server -> client broadcast)
        @self.router.recv("update")  # type: ignore[misc]
        async def update(payload: data_model) -> data_model:  # type: ignore[valid-type]
            """Broadcast data updates to subscribed clients"""
            # Return the payload to broadcast it to subscribed clients
            return payload

    def register_endpoint(self, app: FastAPI) -> None:
        """
        Register WebSocket endpoint and AsyncAPI docs with FastAPI app

        This creates the WebSocket endpoint at the configured path and
        sets up AsyncAPI documentation.
        """
        # Setup AsyncAPI documentation endpoints first
        self.service.setup(app)
        logger.info(f"📚 AsyncAPI docs: {self.service.asyncapi_docs_url}")

        # Register WebSocket endpoint
        @app.websocket(self.endpoint_path)
        async def websocket_endpoint(
            client: Annotated[Client, Depends(self.service.manage)],
        ) -> None:
            """WebSocket endpoint - docstring will be replaced by setup()"""
            await self.service.serve(client)

        # Update docstring for OpenAPI
        websocket_endpoint.__doc__ = (
            f"WebSocket endpoint for {self.route_prefix} data streaming\n\n"
            f"Operations:\n"
            f"- {self.route_prefix}.subscribe - Subscribe to updates\n"
            f"- {self.route_prefix}.unsubscribe - Unsubscribe from updates\n\n"
            f"AsyncAPI Documentation: {self.service.asyncapi_docs_url}"
        )

        logger.info(f"🔌 WebSocket endpoint registered: {self.endpoint_path}")
        logger.info(f"📚 AsyncAPI docs: {self.service.asyncapi_docs_url}")

    async def broadcast(
        self,
        symbol: str,
        data: T,
        params: dict[str, Any] | None = None,
    ) -> None:
        """
        Broadcast data update to all subscribed clients

        Args:
            symbol: Symbol identifier
            data: Business model instance (e.g., Bar)
            params: Parameters used to build topic (must match subscription params)
        """
        topic = self.topic_builder(symbol, params or {})

        # Create message with data model directly as payload
        message = Message(
            type=f"{self.route_prefix}.update",
            payload=data.model_dump(),
        )

        await self.service.server_send(message, topic=topic)

        logger.debug(f"Broadcasted {self.route_prefix}.update to topic: {topic}")
