"""Datafeed module - Market data and symbol information.

Provides REST API and WebSocket streaming for market data.
"""

from pathlib import Path

from fastapi.routing import APIRouter

from trading_api.shared import Module
from trading_api.shared.ws.router_interface import WsRouteInterface

from .api import DatafeedApi
from .service import DatafeedService
from .ws import DatafeedWsRouters


class DatafeedModule(Module):
    """Datafeed module implementation.

    Implements the Module Protocol for pluggable datafeed functionality.
    Provides lazy-loaded service instantiation and router registration.

    Attributes:
        _service: Lazy-loaded DatafeedService instance
        _enabled: Whether this module is enabled for loading
    """

    def __init__(self) -> None:
        """Initialize the datafeed module with lazy service loading."""
        super().__init__()
        self._service: DatafeedService = DatafeedService()
        # Router has NO prefix - routes are at root level within module app
        # The module app will be mounted at /api/v1/datafeed by the factory
        self._api_routers: list[APIRouter] = [
            DatafeedApi(service=self.service, prefix="", tags=[self.name])
        ]
        self._ws_routers: list[WsRouteInterface] = DatafeedWsRouters(
            datafeed_service=self.service
        )

    @property
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: "datafeed"
        """
        return "datafeed"

    @property
    def module_dir(self) -> Path:
        """Return the directory path for this module.

        Returns:
            Path: Module directory path
        """
        return Path(__file__).parent

    @property
    def openapi_tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for datafeed module.

        Returns:
            list[dict[str, str]]: OpenAPI tags describing datafeed operations
        """
        return [
            {
                "name": "datafeed",
                "description": "Market data and symbols operations",
            }
        ]

    @property
    def service(self) -> DatafeedService:
        """Get or create the datafeed service instance.

        Lazy loads the service on first access for resource efficiency.

        Returns:
            DatafeedService: The datafeed service instance
        """
        return self._service

    @property
    def api_routers(self) -> list[APIRouter]:
        """Get all FastAPI routers for datafeed REST API endpoints.

        Returns:
            list[APIRouter]: List containing the DatafeedApi router
        """
        # Prefix MUST match module name for consistency
        return self._api_routers

    @property
    def ws_routers(self) -> list[WsRouteInterface]:
        """Get all WebSocket routers for datafeed real-time endpoints.

        Returns:
            list[WsRouteInterface]: List of WebSocket router instances for bars and quotes
        """
        return self._ws_routers


__all__ = ["DatafeedModule"]
