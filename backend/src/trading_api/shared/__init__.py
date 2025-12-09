"""Shared infrastructure - Module interface, registry, and plugins."""

from .config import Settings, settings
from .module_interface import Module, ModuleApp
from .module_registry import ModuleRegistry
from .provider_interface import Provider
from .provider_registry import ProviderRegistry
from .ws import FastWSAdapter

__all__ = [
    "Module",
    "ModuleApp",
    "ModuleRegistry",
    "Provider",
    "ProviderRegistry",
    "FastWSAdapter",
    "settings",
    "Settings",
]
