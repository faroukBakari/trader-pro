"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import logging

from external_packages.fastws import FastWS, OperationRouter
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
