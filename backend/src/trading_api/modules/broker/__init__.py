"""Broker module - Trading operations.

Provides REST API and WebSocket streaming for orders, positions,
executions, and account information.
"""

from typing import Any

from fastapi.routing import APIRouter

from trading_api.api.broker import BrokerApi
from trading_api.core.broker_service import BrokerService
from trading_api.ws.broker import BrokerWsRouters


class BrokerModule:
    """Broker module implementation.

    Implements the Module Protocol for pluggable broker functionality.
    Provides lazy-loaded service instantiation and router registration.

    Attributes:
        _service: Lazy-loaded BrokerService instance
        _enabled: Whether this module is enabled for loading
    """

    def __init__(self) -> None:
        """Initialize the broker module with lazy service loading."""
        self._service: BrokerService | None = None
        self._enabled: bool = True

    @property
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: "broker"
        """
        return "broker"

    @property
    def enabled(self) -> bool:
        """Check if this module is enabled for loading.

        Returns:
            bool: True if module should be loaded, False otherwise
        """
        return self._enabled

    @property
    def service(self) -> BrokerService:
        """Get or create the broker service instance.

        Lazy loads the service on first access for resource efficiency.

        Returns:
            BrokerService: The broker service instance
        """
        if self._service is None:
            self._service = BrokerService()
        return self._service

    def get_api_routers(self) -> list[APIRouter]:
        """Get all FastAPI routers for broker REST API endpoints.

        Returns:
            list[APIRouter]: List containing the BrokerApi router
        """
        return [BrokerApi(service=self.service)]

    def get_ws_routers(self) -> list[Any]:
        """Get all WebSocket routers for broker real-time endpoints.

        Returns:
            list[Any]: List of WebSocket router instances for orders,
                      positions, executions, equity, and broker connection
        """
        return BrokerWsRouters(broker_service=self.service)

    def configure_app(self, api_app: Any, ws_app: Any) -> None:
        """Optional hook for custom application configuration.

        Currently no custom configuration needed for broker module.

        Args:
            api_app: FastAPI application instance
            ws_app: FastWSAdapter WebSocket application instance
        """


__all__ = ["BrokerModule"]
