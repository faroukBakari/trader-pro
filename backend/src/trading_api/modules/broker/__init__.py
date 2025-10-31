"""Broker module - Trading operations.

Provides REST API and WebSocket streaming for orders, positions,
executions, and account information.
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastapi.routing import APIRouter

from external_packages.fastws import Client
from trading_api.shared import FastWSAdapter

from .api import BrokerApi
from .service import BrokerService
from .ws import BrokerWsRouters


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
        self._ws_app: FastWSAdapter | None = None
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
        # Prefix MUST match module name for consistency
        return [
            BrokerApi(service=self.service, prefix=f"/{self.name}", tags=[self.name])
        ]

    def get_ws_routers(self) -> list[Any]:
        """Get all WebSocket routers for broker real-time endpoints.

        Returns:
            list[Any]: List of WebSocket router instances for orders,
                      positions, executions, equity, and broker connection
        """
        return BrokerWsRouters(broker_service=self.service)

    def get_openapi_tags(self) -> list[dict[str, str]]:
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

    def get_ws_app(self, base_url: str) -> FastWSAdapter:
        """Get or create module's WebSocket application.

        Args:
            base_url: Base URL prefix (e.g., "/api/v1")

        Returns:
            FastWSAdapter: Module's WebSocket application instance
        """
        if self._ws_app is None:
            ws_url = f"{base_url}/{self.name}/ws"
            self._ws_app = FastWSAdapter(
                title=f"{self.name.title()} WebSockets",
                description=f"Real-time {self.name} data streaming for orders, positions, and executions",
                version="1.0.0",
                asyncapi_url=f"{ws_url}/asyncapi.json",
                asyncapi_docs_url=f"{ws_url}/asyncapi",
                heartbeat_interval=30.0,
                max_connection_lifespan=3600.0,
            )
            # Register module's WS routers
            for ws_router in self.get_ws_routers():
                self._ws_app.include_router(ws_router)

        return self._ws_app

    def register_ws_endpoint(self, api_app: FastAPI, base_url: str) -> None:
        """Register module's WebSocket endpoint.

        Args:
            api_app: FastAPI application instance
            base_url: Base URL prefix (e.g., "/api/v1")
        """
        ws_app = self.get_ws_app(base_url)
        ws_url = f"{base_url}/{self.name}/ws"

        @api_app.websocket(ws_url)
        async def websocket_endpoint(
            client: Annotated[Client, Depends(ws_app.manage)],
        ) -> None:
            f"""WebSocket endpoint for {self.name} real-time streaming"""
            await ws_app.serve(client)

    def configure_app(self, api_app: Any, ws_app: Any) -> None:
        """Optional hook for custom application configuration.

        Currently no custom configuration needed for broker module.

        Args:
            api_app: FastAPI application instance
            ws_app: FastWSAdapter WebSocket application instance (deprecated)
        """


__all__ = ["BrokerModule"]
