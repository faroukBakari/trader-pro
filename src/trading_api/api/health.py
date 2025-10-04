"""Health API router."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health", summary="Healthcheck", tags=["health"])
async def healthcheck() -> JSONResponse:
    """Health check endpoint that returns the service status."""
    return JSONResponse({"status": "ok"})
