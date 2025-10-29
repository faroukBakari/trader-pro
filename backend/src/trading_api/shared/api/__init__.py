"""Shared API routers - Always loaded.

This module contains API routers that are always available regardless of
module configuration (health checks, versioning, etc.).
"""

from .health import HealthApi
from .versions import VersionApi

__all__ = ["HealthApi", "VersionApi"]
