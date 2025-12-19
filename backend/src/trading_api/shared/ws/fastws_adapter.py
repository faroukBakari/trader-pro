"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import logging

from pydantic import ValidationError

from external_packages.fastws import (
    Client,
    FastWS,
    NoMatchingOperation,
    OperationRouter,
)
from trading_api.shared.exception_handlers import exception_handler
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

    def shutdown(self) -> None:
        pass

    async def handle_exception(
        self,
        client: Client,
        exc: ValueError | ValidationError | NoMatchingOperation | TimeoutError,
    ) -> None:
        await exception_handler(client.ws, exc)
