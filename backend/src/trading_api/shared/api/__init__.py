"""Shared API module.

Note: HealthApi and VersionApi have been moved to the core module.
They are no longer part of the shared infrastructure.
"""

from .api_router_interface import APIRouterInterface

__all__: list[str] = ["APIRouterInterface"]
