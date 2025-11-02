"""Tests for core service."""

import pytest

from trading_api.models.versioning import APIVersion
from trading_api.modules.core.service import CoreService


class TestCoreService:
    """Test CoreService functionality."""

    @pytest.fixture
    def service(self) -> CoreService:
        """Create a CoreService instance for testing."""
        return CoreService()

    def test_get_health(self, service: CoreService) -> None:
        """Test get_health returns proper health response."""
        health = service.get_health()

        assert health.status == "ok"
        assert health.message == "Trading API is running"
        assert health.api_version == "v1"
        assert "timestamp" in health.model_dump()
        assert health.version_info["version"] == "v1"
        assert health.version_info["status"] == "stable"

    def test_get_all_versions(self, service: CoreService) -> None:
        """Test get_all_versions returns metadata about all versions."""
        metadata = service.get_all_versions()

        assert metadata.current_version == APIVersion.V1
        assert len(metadata.available_versions) >= 1
        assert metadata.documentation_url == "/api/v1/docs"
        assert metadata.support_contact == "support@trading-pro.nodomainyet"

        # Check that v1 version exists
        v1_info = next(
            (v for v in metadata.available_versions if v.version == APIVersion.V1),
            None,
        )
        assert v1_info is not None
        assert v1_info.status == "stable"

    def test_get_current_version(self, service: CoreService) -> None:
        """Test get_current_version returns current version info."""
        version = service.get_current_version()

        assert version["version"] == "v1"
        assert version["status"] == "stable"
        assert "release_date" in version
        assert "breaking_changes" in version
        assert isinstance(version["breaking_changes"], list)

    def test_health_timestamp_format(self, service: CoreService) -> None:
        """Test that health timestamp is in ISO format with Z suffix."""
        health = service.get_health()
        timestamp = health.timestamp

        assert timestamp.endswith("Z")
        assert "T" in timestamp  # ISO format includes T separator

    def test_version_consistency(self, service: CoreService) -> None:
        """Test that version is consistent across all endpoints."""
        health = service.get_health()
        metadata = service.get_all_versions()
        current = service.get_current_version()

        # All should report the same current version
        assert health.api_version == "v1"
        assert metadata.current_version == APIVersion.V1
        assert current["version"] == "v1"
