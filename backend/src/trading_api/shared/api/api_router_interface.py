from abc import ABC
from typing import Any

from fastapi import APIRouter

from trading_api.models.health import HealthResponse
from trading_api.models.versioning import APIMetadata, VersionInfo
from trading_api.shared.service_interface import ServiceInterface


class APIRouterInterface(APIRouter, ABC):
    def __init__(
        self, *args: Any, service: ServiceInterface, version: str, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._service = service
        self._version = version

        @self.get(
            "/health",
            summary="Health Check",
            description=(
                "Returns the current health status of the trading API service "
                "with version information"
            ),
            response_model=HealthResponse,
            operation_id="getHealthStatus",
            tags=[version],
        )
        async def healthcheck() -> HealthResponse:
            """Health check endpoint that returns the service status and version info."""
            return service.get_health(version)

        @self.get(
            "/versions",
            summary="API Versions",
            description="Returns information about all available API versions",
            response_model=APIMetadata,
            operation_id="getAPIVersions",
            tags=["versioning", version],
        )
        async def get_api_versions() -> APIMetadata:
            """Get information about all available API versions."""
            return service.api_metadata

        @self.get(
            "/version",
            summary="Current API Version",
            description="Returns information about the current API version",
            operation_id="getCurrentAPIVersion",
            tags=["versioning", version],
        )
        async def get_current_version() -> VersionInfo:
            """Get information about the current API version."""
            return service.get_current_version_info(version)

    @property
    def module_name(self) -> str:
        """Get the name of the module this router belongs to.

        Returns:
            str: The module name
        """
        return self._service.module_name

    @property
    def service(self) -> ServiceInterface:
        """Get the Service instance.

        Returns:
            Service: The service instance
        """
        return self._service

    @property
    def version(self) -> str:
        """Get the API version for this router.

        Returns:
            str: The API version
        """
        return self._version


__all__ = ["APIRouterInterface"]
