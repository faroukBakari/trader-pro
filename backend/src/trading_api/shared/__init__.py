"""Shared infrastructure - Module interface, registry, and plugins."""

from .module_interface import Module
from .module_registry import ModuleRegistry
from .plugins import FastWSAdapter

__all__ = ["Module", "ModuleRegistry", "FastWSAdapter"]
