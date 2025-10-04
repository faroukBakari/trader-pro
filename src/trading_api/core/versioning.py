"""API versioning models and utilities."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class APIVersion(str, Enum):
    """Supported API versions."""

    V1 = "v1"
    V2 = "v2"  # Future version for breaking changes

    @classmethod
    def get_latest(cls) -> "APIVersion":
        """Get the latest API version."""
        return cls.V1

    @classmethod
    def get_all(cls) -> List["APIVersion"]:
        """Get all supported API versions."""
        return list(cls)


class VersionInfo(BaseModel):
    """API version information."""

    version: APIVersion
    release_date: str
    status: str  # "stable", "deprecated", "beta"
    breaking_changes: List[str] = []
    deprecation_notice: Optional[str] = None
    sunset_date: Optional[str] = None


class APIMetadata(BaseModel):
    """Complete API metadata including version information."""

    current_version: APIVersion
    available_versions: List[VersionInfo]
    documentation_url: str
    support_contact: str


# Version-specific configurations
VERSION_CONFIG = {
    APIVersion.V1: VersionInfo(
        version=APIVersion.V1,
        release_date="2025-10-04",
        status="stable",
        breaking_changes=[],
        deprecation_notice=None,
        sunset_date=None,
    ),
    APIVersion.V2: VersionInfo(
        version=APIVersion.V2,
        release_date="TBD",
        status="planned",
        breaking_changes=[
            "Authentication required for all endpoints",
            "New response format for error messages",
            "Renamed health endpoint to status",
        ],
        deprecation_notice=None,
        sunset_date=None,
    ),
}
