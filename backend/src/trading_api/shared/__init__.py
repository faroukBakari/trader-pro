"""Shared infrastructure for modular backend."""

from .module_interface import Module
from .module_registry import ModuleRegistry

__all__ = ["Module", "ModuleRegistry"]
