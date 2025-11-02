"""Core API router with health and versioning endpoints."""

from typing import Any

from fastapi import APIRouter

from trading_api.models import HealthResponse
from trading_api.models.versioning import APIMetadata

from .service import CoreService


class CoreApi(APIRouter):
    """Core API router providing health checks and version information.

    Combines health and versioning endpoints that are always available
    regardless of which modules are enabled.
    """

    def __init__(
        self,
        service: CoreService,
        prefix: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the CoreApi router.

        Args:
            service: CoreService instance for business logic
            prefix: URL prefix for all routes in this router
            *args: Additional positional arguments for APIRouter
            **kwargs: Additional keyword arguments for APIRouter
        """
        super().__init__(prefix=prefix, *args, **kwargs)
        self.service = service

        @self.get(
            "/health",
            summary="Health Check",
            description=(
                "Returns the current health status of the trading API service "
                "with version information"
            ),
            response_model=HealthResponse,
            operation_id="getHealthStatus",
            tags=["v1"],
        )
        async def healthcheck() -> HealthResponse:
            """Health check endpoint that returns the service status and version info."""
            return self.service.get_health()

        @self.get(
            "/versions",
            summary="API Versions",
            description="Returns information about all available API versions",
            response_model=APIMetadata,
            operation_id="getAPIVersions",
            tags=["versioning", "v1"],
        )
        async def get_api_versions() -> APIMetadata:
            """Get information about all available API versions."""
            return self.service.get_all_versions()

        @self.get(
            "/version",
            summary="Current API Version",
            description="Returns information about the current API version",
            operation_id="getCurrentAPIVersion",
            tags=["versioning", "v1"],
        )
        async def get_current_version() -> dict:
            """Get information about the current API version."""
            return self.service.get_current_version()
