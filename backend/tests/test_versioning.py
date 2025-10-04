"""Tests for API versioning functionality."""
import pytest
from httpx import AsyncClient

from trading_api.core.versioning import APIVersion
from trading_api.main import app


class TestAPIVersioning:
    """Test API versioning functionality."""

    @pytest.mark.asyncio
    async def test_root_endpoint_includes_version_info(self) -> None:
        """Test that root endpoint includes version information."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "current_api_version" in data
        assert data["current_api_version"] == "v1"
        assert "documentation" in data
        assert "health" in data
        assert "versions" in data

    @pytest.mark.asyncio
    async def test_versions_endpoint(self) -> None:
        """Test the versions endpoint returns all available versions."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/versions")

        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        assert "available_versions" in data
        assert "documentation_url" in data
        assert "support_contact" in data

        # Check current version
        assert data["current_version"] == "v1"

        # Check available versions structure
        assert isinstance(data["available_versions"], list)
        assert len(data["available_versions"]) >= 1

        # Check v1 version info
        v1_info = next(
            (v for v in data["available_versions"] if v["version"] == "v1"), None
        )
        assert v1_info is not None
        assert v1_info["status"] == "stable"
        assert "release_date" in v1_info

    @pytest.mark.asyncio
    async def test_current_version_endpoint(self) -> None:
        """Test the current version endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/version")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1"
        assert data["status"] == "stable"
        assert "release_date" in data
        assert "breaking_changes" in data
        assert isinstance(data["breaking_changes"], list)

    @pytest.mark.asyncio
    async def test_health_endpoint_includes_version(self) -> None:
        """Test that health endpoint includes version information."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert data["api_version"] == "v1"
        assert "version_info" in data

        version_info = data["version_info"]
        assert version_info["version"] == "v1"
        assert version_info["status"] == "stable"
        assert "release_date" in version_info

    @pytest.mark.asyncio
    async def test_openapi_spec_includes_version_info(self) -> None:
        """Test that OpenAPI spec includes proper version information."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/openapi.json")

        assert response.status_code == 200
        spec = response.json()

        # Check version in info
        assert "info" in spec
        assert "version" in spec["info"]
        assert "title" in spec["info"]
        assert "Trading API" in spec["info"]["title"]

        # Check versioning endpoints exist
        assert "paths" in spec
        assert "/api/v1/versions" in spec["paths"]
        assert "/api/v1/version" in spec["paths"]
        assert "/api/v1/health" in spec["paths"]

        # Check versioning tags
        versions_path = spec["paths"]["/api/v1/versions"]["get"]
        assert "versioning" in versions_path["tags"]

    def test_api_version_enum(self) -> None:
        """Test APIVersion enum functionality."""
        # Test latest version
        latest = APIVersion.get_latest()
        assert latest == APIVersion.V1

        # Test all versions
        all_versions = APIVersion.get_all()
        assert APIVersion.V1 in all_versions
        assert APIVersion.V2 in all_versions
        assert len(all_versions) == 2

    @pytest.mark.asyncio
    async def test_version_consistency_across_endpoints(self) -> None:
        """Test that version information is consistent across all endpoints."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Get version info from different endpoints
            root_response = await ac.get("/")
            versions_response = await ac.get("/api/v1/versions")
            version_response = await ac.get("/api/v1/version")
            health_response = await ac.get("/api/v1/health")

        # All should return 200
        assert root_response.status_code == 200
        assert versions_response.status_code == 200
        assert version_response.status_code == 200
        assert health_response.status_code == 200

        # Extract version information
        root_data = root_response.json()
        versions_data = versions_response.json()
        version_data = version_response.json()
        health_data = health_response.json()

        # Check consistency
        current_version = "v1"
        assert root_data["current_api_version"] == current_version
        assert versions_data["current_version"] == current_version
        assert version_data["version"] == current_version
        assert health_data["api_version"] == current_version

    @pytest.mark.asyncio
    async def test_api_tags_include_version(self) -> None:
        """Test that API endpoints are properly tagged with version."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/openapi.json")

        spec = response.json()

        # Check that health endpoint has v1 tag
        health_operation = spec["paths"]["/api/v1/health"]["get"]
        assert "v1" in health_operation["tags"]

        # Check that versions endpoint has v1 tag
        versions_operation = spec["paths"]["/api/v1/versions"]["get"]
        assert "v1" in versions_operation["tags"]
