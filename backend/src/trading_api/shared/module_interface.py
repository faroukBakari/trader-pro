"""Module Protocol - Contract for pluggable modules.

Defines the interface that all modules (datafeed, broker, etc.) must implement
to integrate with the application factory pattern.
"""

from typing import Protocol, runtime_checkable

from fastapi import FastAPI
from fastapi.routing import APIRouter

from trading_api.shared.plugins.fastws_adapter import FastWSAdapter
from trading_api.shared.ws.router_interface import WsRouterInterface


@runtime_checkable
class Module(Protocol):
    """Protocol defining the interface for pluggable modules.

    All modules must implement this interface to be registered and loaded
    by the application factory.

    Properties:
        name: Unique identifier for the module (e.g., "datafeed", "broker")
        enabled: Whether this module is currently enabled for loading
        _enabled: Internal attribute for tracking enabled status (mutable)

    Methods:
        get_api_routers: Returns list of FastAPI routers for REST API endpoints
        get_ws_routers: Returns list of WebSocket routers for real-time endpoints
        get_openapi_tags: Returns OpenAPI tags for this module
        get_ws_app: Get or create module's WebSocket application
        register_ws_endpoint: Register module's WebSocket endpoint
        configure_app: Optional configuration hook for custom app setup
    """

    _enabled: bool  # Internal attribute for enabled status

    @property
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: Module name (e.g., "datafeed", "broker")
        """
        ...

    @property
    def enabled(self) -> bool:
        """Check if this module is enabled for loading.

        Returns:
            bool: True if module should be loaded, False otherwise
        """
        ...

    def get_api_routers(self) -> list[APIRouter]:
        """Get all FastAPI routers for this module's REST API endpoints.

        Returns:
            list[APIRouter]: List of configured API routers
        """
        ...

    def get_ws_routers(self) -> list[WsRouterInterface]:
        """Get all WebSocket routers for this module's real-time endpoints.

        Returns:
            list[WsRouterInterface]: List of WebSocket router instances
        """
        ...

    def get_openapi_tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for this module.

        Returns:
            list[dict[str, str]]: List of OpenAPI tag dictionaries with 'name'
                and 'description' keys
        """
        ...

    def get_ws_app(self, base_url: str) -> FastWSAdapter:
        """Get or create module's WebSocket application.

        Args:
            base_url: Base URL prefix (e.g., "/api/v1")

        Returns:
            FastWSAdapter: Module's WebSocket application instance
        """
        ...

    def register_ws_endpoint(self, api_app: FastAPI, base_url: str) -> None:
        """Register module's WebSocket endpoint.

        Args:
            api_app: FastAPI application instance
            base_url: Base URL prefix (e.g., "/api/v1")
        """
        ...

    def configure_app(self, api_app: FastAPI) -> None:
        """Optional hook for custom application configuration.

        Args:
            api_app: FastAPI application instance
        """
        ...
        ...
