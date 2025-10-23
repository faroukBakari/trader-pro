"""Health API router with versioning support."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from trading_api.core.versioning import VERSION_CONFIG, APIVersion

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str = "Service is healthy"
    timestamp: str
    api_version: str
    version_info: dict


@router.get(
    "/health",
    summary="Health Check",
    description=(
        "Returns the current health status of the trading API service "
        "with version information"
    ),
    response_model=HealthResponse,
    operation_id="getHealthStatus",
)
async def healthcheck() -> HealthResponse:
    """Health check endpoint that returns the service status and version info."""
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
