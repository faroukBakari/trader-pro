"""Module Registry - Centralized module management.

Provides registration, discovery, and filtering of pluggable modules.
"""

from typing import Dict

from .module_interface import Module


class ModuleRegistry:
    """Centralized registry for managing pluggable modules.

    Provides methods to register modules, filter by enabled status,
    and retrieve registered modules.

    Attributes:
        _modules: Dictionary mapping module names to module instances
    """

    def __init__(self) -> None:
        """Initialize an empty module registry."""
        self._modules: Dict[str, Module] = {}

    def register(self, module: Module) -> None:
        """Register a module with the registry.

        Args:
            module: Module instance implementing the Module protocol

        Raises:
            ValueError: If a module with the same name is already registered
        """
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' is already registered")
        self._modules[module.name] = module

    def get_enabled_modules(self) -> list[Module]:
        """Get all registered modules that are currently enabled.

        Returns:
            list[Module]: List of enabled module instances
        """
        return [module for module in self._modules.values() if module.enabled]

    def get_all_modules(self) -> list[Module]:
        """Get all registered modules regardless of enabled status.

        Returns:
            list[Module]: List of all registered module instances
        """
        return list(self._modules.values())

    def get_module(self, name: str) -> Module | None:
        """Get a specific module by name.

        Args:
            name: Module name to retrieve

        Returns:
            Module | None: Module instance if found, None otherwise
        """
        return self._modules.get(name)

    def clear(self) -> None:
        """Clear all registered modules.

        Primarily used for testing purposes.
        """
        self._modules.clear()
