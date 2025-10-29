"""Shared infrastructure - Module interface, registry, plugins, and shared API routers."""

from .api import HealthApi, VersionApi
from .module_interface import Module
from .module_registry import ModuleRegistry
from .plugins import FastWSAdapter

__all__ = ["Module", "ModuleRegistry", "FastWSAdapter", "HealthApi", "VersionApi"]
