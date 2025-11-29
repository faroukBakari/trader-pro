"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import asyncio
import logging

from external_packages.fastws import FastWS, OperationRouter
from trading_api.models.common import SubscriptionUpdate
from trading_api.shared.ws.ws_route_interface import WsRouteInterface

logger = logging.getLogger(__name__)


# TODO: need optimizations for idle states with no subscriptions / no clients
# TODO: need optimizations to handle load and optimize tasks when many clients are connected
class FastWSAdapter(FastWS):
    """
    Self-contained WebSocket adapter with embedded endpoint

    Creates a FastWS service with subscribe/unsubscribe operations
    and registers its own WebSocket endpoint.

    Type parameter T: The business model type (e.g., Bar)
    """

    def include_router(
        self,
        router: OperationRouter,
        *,
        prefix: str = "",
    ) -> None:
        super().include_router(router, prefix=prefix)

        if not isinstance(router, WsRouteInterface):
            logger.warning(
                f"Router {router} is not a WsRouteInterface, skipping broadcasting setup"
            )
            return

        setattr(router, "broadcast_update", self.broadcast_update)

    async def broadcast_update(self, route: str, update: SubscriptionUpdate) -> None:
        topic = update.topic
        clients = [
            client for client in self.connections.values() if topic in client.topics
        ]

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

    def shutdown(self) -> None:
        pass
