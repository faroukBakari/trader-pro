"""Core module - Health checks and versioning.

Provides essential infrastructure endpoints that are always available
regardless of which feature modules are enabled.
"""

from pathlib import Path
from typing import Any

from fastapi.routing import APIRouter

from trading_api.shared import Module
from trading_api.shared.ws.router_interface import WsRouteInterface, WsRouteService

from .api import CoreApi
from .service import CoreService


class CoreModule(Module):
    """Core module implementation.

    Implements the Module Protocol for core infrastructure functionality.
    Provides health checks and API version information that are always
    available regardless of enabled modules.

    Attributes:
        _service: CoreService instance
        _api_routers: List of FastAPI routers (CoreApi)
        _ws_routers: Empty list (no WebSocket routes)
    """

    def __init__(self) -> None:
        """Initialize the core module with service and API router."""
        super().__init__()
        self._service: CoreService = CoreService()
        # Router has NO prefix - routes are at root level within module app
        # The module app will be mounted at /api/v1/core by the factory
        self._api_routers: list[APIRouter] = [
            CoreApi(service=self._service, prefix="", tags=[self.name])
        ]
        self._ws_routers: list[WsRouteInterface] = []

    @property
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: "core"
        """
        return "core"

    @property
    def module_dir(self) -> Path:
        """Return the directory path for this module.

        Returns:
            Path: Module directory path
        """
        return Path(__file__).parent

    @property
    def tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for core module.

        Returns:
            list[dict[str, str]]: OpenAPI tags describing core operations
        """
        return [
            {
                "name": "core",
                "description": "Core infrastructure (health checks, versioning)",
            }
        ]

    @property
    def service(self, *args: Any, **kwargs: Any) -> WsRouteService:
        """Get the core service instance.

        Note: CoreService doesn't implement WsRouteService since core module
        has no WebSocket routes, but we return it to satisfy the protocol.

        Returns:
            WsRouteService: The core service instance (cast for protocol compliance)
        """
        return self._service  # type: ignore[return-value]

    @property
    def api_routers(self) -> list[APIRouter]:
        """Get all FastAPI routers for core REST API endpoints.

        Returns:
            list[APIRouter]: List containing the CoreApi router
        """
        return self._api_routers

    @property
    def ws_routers(self) -> list[WsRouteInterface]:
        """Get all WebSocket routers for core real-time endpoints.

        Returns:
            list[WsRouteInterface]: Empty list (no WebSocket routes)
        """
        return self._ws_routers


__all__ = ["CoreModule"]
