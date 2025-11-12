"""API versioning models and utilities."""

from typing import List, Optional

from pydantic import BaseModel


class VersionInfo(BaseModel):
    """API version information."""

    version: str
    release_date: str
    status: str  # "stable", "deprecated", "beta"
    breaking_changes: List[str] = []
    deprecation_notice: Optional[str] = None
    sunset_date: Optional[str] = None


class APIMetadata(BaseModel):
    """Complete API metadata including version information."""

    current_version: str
    available_versions: dict[str, VersionInfo]
    documentation_url: str
    support_contact: str
