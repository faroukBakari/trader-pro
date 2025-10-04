"""Health API router."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str = "Service is healthy"
    timestamp: str


@router.get(
    "/health",
    summary="Health Check",
    description="Returns the current health status of the trading API service",
    response_model=HealthResponse,
    operation_id="getHealthStatus",
    tags=["health"],
)
async def healthcheck() -> HealthResponse:
    """Health check endpoint that returns the service status."""
    from datetime import datetime

    return HealthResponse(
        status="ok",
        message="Trading API is running",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
