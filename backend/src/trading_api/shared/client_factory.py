"""Inter-module HTTP client factory with typed access.

Provides lazy-loaded, cached clients for cross-module communication.
Generated clients have smart defaults baked in at generation time.
Environment variables can override for multi-process deployments.

Usage:
    from trading_api.shared.client_factory import InterModuleClients

    clients = InterModuleClients(caller_id="my-provider")
    quotes = await clients.datafeed.getQuotes(GetQuotesRequest(symbols=["AAPL"]))

Environment Variables:
    DATAFEED_SERVICE_URL: Override datafeed module URL (default uses client's baked-in URL)
    BROKER_SERVICE_URL: Override broker module URL (default uses client's baked-in URL)
    INTER_MODULE_TIMEOUT: Default timeout in seconds (default: 5.0)
"""

from __future__ import annotations

import logging
import os
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trading_api.modules.broker.client_generated import BrokerClient
    from trading_api.modules.datafeed.client_generated import DatafeedClient

logger = logging.getLogger(__name__)


class InterModuleClients:
    """Factory for inter-module HTTP clients with type-safe access."""

    def __init__(self, caller_id: str) -> None:
        """Initialize factory with caller identity for HMAC signing.

        Args:
            caller_id: Identifier for this caller (used in request signatures)
        """
        self.caller_id = caller_id
        self._timeout = float(os.environ.get("INTER_MODULE_TIMEOUT", "5.0"))

    @cached_property
    def datafeed(self) -> DatafeedClient:
        """Type-safe DatafeedClient with full IDE support.

        Uses client's baked-in default URL unless DATAFEED_SERVICE_URL is set.

        Returns:
            DatafeedClient configured for inter-module communication
        """
        from trading_api.modules.datafeed.client_generated import DatafeedClient

        if url := os.environ.get("DATAFEED_SERVICE_URL"):
            logger.debug(f"Creating DatafeedClient with override base_url={url}")
            return DatafeedClient(
                caller_id=self.caller_id,
                base_url=url.rstrip("/"),
                timeout=self._timeout,
            )
        logger.debug("Creating DatafeedClient with default base_url")
        return DatafeedClient(caller_id=self.caller_id, timeout=self._timeout)

    @cached_property
    def broker(self) -> BrokerClient:
        """Type-safe BrokerClient with full IDE support.

        Uses client's baked-in default URL unless BROKER_SERVICE_URL is set.

        Returns:
            BrokerClient configured for inter-module communication
        """
        from trading_api.modules.broker.client_generated import BrokerClient

        if url := os.environ.get("BROKER_SERVICE_URL"):
            logger.debug(f"Creating BrokerClient with override base_url={url}")
            return BrokerClient(
                caller_id=self.caller_id,
                base_url=url.rstrip("/"),
                timeout=self._timeout,
            )
        logger.debug("Creating BrokerClient with default base_url")
        return BrokerClient(caller_id=self.caller_id, timeout=self._timeout)

    async def close_all(self) -> None:
        """Cleanup all client connections.

        Should be called during application shutdown.
        """
        for name in ["datafeed", "broker"]:
            if name in self.__dict__:  # Check cached_property was accessed
                client = getattr(self, name)
                await client.close()
                logger.debug(f"Closed {name} client connection")


__all__ = ["InterModuleClients"]
