"""Tests for health endpoint."""
import pytest
from httpx import AsyncClient

from trading_api.main import app


@pytest.mark.asyncio
async def test_healthcheck_returns_200_and_payload() -> None:
    """Test that health endpoint returns status 200 with correct payload."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Trading API is running"
    assert "timestamp" in data
