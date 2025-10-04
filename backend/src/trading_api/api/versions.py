"""API versioning endpoints."""
from fastapi import APIRouter

from trading_api.core.versioning import VERSION_CONFIG, APIMetadata, APIVersion

router = APIRouter()


@router.get(
    "/versions",
    summary="API Versions",
    description="Returns information about all available API versions",
    response_model=APIMetadata,
    operation_id="getAPIVersions",
    tags=["versioning"],
)
async def get_api_versions() -> APIMetadata:
    """Get information about all available API versions."""
    return APIMetadata(
        current_version=APIVersion.get_latest(),
        available_versions=list(VERSION_CONFIG.values()),
        documentation_url="https://api.trading.com/docs",
        support_contact="support@trading.com",
    )


@router.get(
    "/version",
    summary="Current API Version",
    description="Returns information about the current API version",
    operation_id="getCurrentAPIVersion",
    tags=["versioning"],
)
async def get_current_version() -> dict:
    """Get information about the current API version."""
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
