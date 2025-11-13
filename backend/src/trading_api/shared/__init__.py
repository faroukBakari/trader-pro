"""Shared infrastructure - Module interface, registry, and plugins."""

from .config import Settings, settings
from .module_interface import Module, ModuleApp
from .module_registry import ModuleRegistry
from .ws import FastWSAdapter

__all__ = [
    "Module",
    "ModuleApp",
    "ModuleRegistry",
    "FastWSAdapter",
    "settings",
    "Settings",
]
