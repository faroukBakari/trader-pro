"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import asyncio
import logging
from typing import AsyncGenerator

from fastapi import WebSocket

from external_packages.fastws import Client, FastWS, OperationRouter
from trading_api.models.common import SubscriptionUpdate
from trading_api.shared.ws.ws_router import WsRouteFeature

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

        if not isinstance(router, WsRouteFeature):
            logger.warning(
                f"Router {router} is not a WsRouteFeature, skipping broadcasting setup"
            )
            return

    async def manage(self, ws: WebSocket) -> AsyncGenerator[Client, None]:
        if not await self._auth(ws):
            return
        client = Client(ws)
        self._connect(client)
        try:
            yield client
        finally:
            # if self._on_disconnect:
            #     await self._on_disconnect(client)  # <-- cleanup here
            logger.info(f"Client {client.uid} LoooooooooooooooooooooooooooooooooL")
            self._disconnect(client)

    def shutdown(self) -> None:
        pass
