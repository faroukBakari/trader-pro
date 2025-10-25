from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    message: str = "Service is healthy"
    timestamp: str
    api_version: str
    version_info: dict
