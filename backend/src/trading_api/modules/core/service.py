"""Core service for health checks and versioning.

Provides business logic for core infrastructure endpoints.
"""

from datetime import datetime

from trading_api.models import HealthResponse
from trading_api.models.versioning import VERSION_CONFIG, APIMetadata, APIVersion


class CoreService:
    """Service for core infrastructure operations.

    Handles health checks and API version information retrieval.
    """

    def __init__(self) -> None:
        """Initialize the core service."""

    def get_health(self) -> HealthResponse:
        """Get the current health status of the API.

        Returns:
            HealthResponse: Health status with version information
        """
        current_version = APIVersion.get_latest()
        version_info = VERSION_CONFIG[current_version]

        return HealthResponse(
            status="ok",
            message="Trading API is running",
            timestamp=datetime.utcnow().isoformat() + "Z",
            api_version=current_version.value,
            version_info={
                "version": version_info.version.value,
                "release_date": version_info.release_date,
                "status": version_info.status,
                "deprecation_notice": version_info.deprecation_notice,
            },
        )

    def get_all_versions(self) -> APIMetadata:
        """Get information about all available API versions.

        Returns:
            APIMetadata: Metadata about all API versions
        """
        return APIMetadata(
            current_version=APIVersion.get_latest(),
            available_versions=list(VERSION_CONFIG.values()),
            documentation_url="/api/v1/docs",
            support_contact="support@trading-pro.nodomainyet",
        )

    def get_current_version(self) -> dict:
        """Get information about the current API version.

        Returns:
            dict: Current API version information
        """
        current_version = APIVersion.get_latest()
        version_info = VERSION_CONFIG[current_version]

        return {
            "version": version_info.version.value,
            "release_date": version_info.release_date,
            "status": version_info.status,
            "breaking_changes": version_info.breaking_changes,
            "deprecation_notice": version_info.deprecation_notice,
            "sunset_date": version_info.sunset_date,
        }
