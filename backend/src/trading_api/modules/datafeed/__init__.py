"""Datafeed module - Market data and symbol information.

Provides REST API and WebSocket streaming for market data.
"""

from typing import Any

from fastapi.routing import APIRouter

from trading_api.api.datafeed import DatafeedApi
from trading_api.core.datafeed_service import DatafeedService
from trading_api.ws.datafeed import DatafeedWsRouters


class DatafeedModule:
    """Datafeed module implementation.

    Implements the Module Protocol for pluggable datafeed functionality.
    Provides lazy-loaded service instantiation and router registration.

    Attributes:
        _service: Lazy-loaded DatafeedService instance
        _enabled: Whether this module is enabled for loading
    """

    def __init__(self) -> None:
        """Initialize the datafeed module with lazy service loading."""
        self._service: DatafeedService | None = None
        self._enabled: bool = True

    @property
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: "datafeed"
        """
        return "datafeed"

    @property
    def enabled(self) -> bool:
        """Check if this module is enabled for loading.

        Returns:
            bool: True if module should be loaded, False otherwise
        """
        return self._enabled

    @property
    def service(self) -> DatafeedService:
        """Get or create the datafeed service instance.

        Lazy loads the service on first access for resource efficiency.

        Returns:
            DatafeedService: The datafeed service instance
        """
        if self._service is None:
            self._service = DatafeedService()
        return self._service

    def get_api_routers(self) -> list[APIRouter]:
        """Get all FastAPI routers for datafeed REST API endpoints.

        Returns:
            list[APIRouter]: List containing the DatafeedApi router
        """
        return [DatafeedApi(service=self.service)]

    def get_ws_routers(self) -> list[Any]:
        """Get all WebSocket routers for datafeed real-time endpoints.

        Returns:
            list[Any]: List of WebSocket router instances for bars and quotes
        """
        return DatafeedWsRouters(datafeed_service=self.service)

    def configure_app(self, api_app: Any, ws_app: Any) -> None:
        """Optional hook for custom application configuration.

        Currently no custom configuration needed for datafeed module.

        Args:
            api_app: FastAPI application instance
            ws_app: FastWSAdapter WebSocket application instance
        """
        pass


__all__ = ["DatafeedModule"]
