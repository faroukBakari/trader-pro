"""Tests for health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthcheck_returns_200_and_payload(async_client: AsyncClient) -> None:
    """Test that health endpoint returns status 200 with correct payload."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Trading API is running"
    assert "timestamp" in data
    assert "api_version" in data
    assert data["api_version"] == "v1"
    assert "version_info" in data
    assert data["version_info"]["version"] == "v1"
    assert data["version_info"]["status"] == "stable"
