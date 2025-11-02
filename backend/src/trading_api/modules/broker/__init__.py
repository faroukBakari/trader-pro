"""Broker module - Trading operations.

Provides REST API and WebSocket streaming for orders, positions,
executions, and account information.
"""

from pathlib import Path

from fastapi.routing import APIRouter

from trading_api.shared import Module
from trading_api.shared.ws.router_interface import WsRouterInterface

from .api import BrokerApi
from .service import BrokerService
from .ws import BrokerWsRouters


class BrokerModule(Module):
    """Broker module implementation.

    Implements the Module Protocol for pluggable broker functionality.
    Provides eager service instantiation and router registration.

    Attributes:
        _service: BrokerService instance
        _api_routers: List of FastAPI routers
        _ws_routers: List of WebSocket routers
    """

    def __init__(self) -> None:
        """Initialize the broker module with service and routers."""
        super().__init__()
        self._service: BrokerService = BrokerService()
        # Router has NO prefix - routes are at root level within module app
        # The module app will be mounted at /api/v1/broker by the factory
        self._api_routers: list[APIRouter] = [
            BrokerApi(service=self.service, prefix="", tags=[self.name])
        ]
        self._ws_routers: list[WsRouterInterface] = BrokerWsRouters(
            broker_service=self.service
        )

    @property
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: "broker"
        """
        return "broker"

    @property
    def module_dir(self) -> Path:
        """Return the directory path for this module.

        Returns:
            Path: Module directory path
        """
        return Path(__file__).parent

    @property
    def openapi_tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for broker module.

        Returns:
            list[dict[str, str]]: OpenAPI tags describing broker operations
        """
        return [
            {
                "name": "broker",
                "description": "Broker operations (orders, positions, executions)",
            }
        ]

    @property
    def service(self) -> BrokerService:
        """Get the broker service instance.

        Returns:
            BrokerService: The broker service instance
        """
        return self._service

    @property
    def api_routers(self) -> list[APIRouter]:
        """Get all FastAPI routers for broker REST API endpoints.

        Returns:
            list[APIRouter]: List containing the BrokerApi router
        """
        # Prefix MUST match module name for consistency
        return self._api_routers

    @property
    def ws_routers(self) -> list[WsRouterInterface]:
        """Get all WebSocket routers for broker real-time endpoints.

        Returns:
            list[WsRouterInterface]: List of WebSocket router instances for orders,
                      positions, executions, equity, and broker connection
        """
        return self._ws_routers


__all__ = ["BrokerModule"]
__all__ = ["BrokerModule"]
__all__ = ["BrokerModule"]
