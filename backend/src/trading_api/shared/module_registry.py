"""Module Registry - Centralized module management.

Provides registration, discovery, and filtering of pluggable modules.
"""

import importlib
import logging
from pathlib import Path
from typing import Dict

from .module_interface import Module

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Centralized registry for managing pluggable modules.

    Provides methods to register module classes, filter by enabled status,
    and lazy-load module instances.

    Attributes:
        _module_classes: Dictionary mapping module names to module classes
        _instances: Dictionary mapping module names to lazy-loaded instances
        _enabled_modules: Set of module names to enable (None = all enabled)
    """

    def __init__(self) -> None:
        """Initialize an empty module registry."""
        self._module_classes: Dict[str, type[Module]] = {}
        self._instances: Dict[str, Module] = {}
        self._enabled_modules: set[str] | None = None

    def register(self, module_class: type[Module]) -> None:
        """Register a module class with the registry.

        Args:
            module_class: Module class implementing the Module protocol

        Raises:
            ValueError: If a module with the same name is already registered
        """
        # Create temporary instance to get module name
        temp_instance = module_class()
        module_name = temp_instance.name

        if module_name in self._module_classes:
            raise ValueError(f"Module '{module_name}' is already registered")
        self._module_classes[module_name] = module_class
        logger.info(f"Registered module class: {module_name}")

    def auto_discover(self, modules_dir: Path) -> None:
        """Auto-discover and register modules from directory.

        Convention: modules/<module_name>/__init__.py exports <ModuleName>Module.
        Example: modules/broker/__init__.py exports BrokerModule

        Args:
            modules_dir: Path to modules directory to scan
        """
        for module_path in modules_dir.iterdir():
            # Skip non-directories and private/internal modules
            if not module_path.is_dir() or module_path.name.startswith("_"):
                continue

            module_name = module_path.name
            class_name = f"{module_name.title()}Module"

            try:
                # Import module: trading_api.modules.broker
                module_import = importlib.import_module(
                    f"trading_api.modules.{module_name}"
                )
                # Get module class: BrokerModule
                module_class = getattr(module_import, class_name)
                self.register(module_class)
                logger.info(f"Auto-discovered module: {module_name}")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to auto-discover module '{module_name}': {e}")
                continue

    def _get_instance(self, module_name: str) -> Module:
        """Get or create module instance (lazy loading).

        Args:
            module_name: Name of module to instantiate

        Returns:
            Module: Module instance
        """
        if module_name not in self._instances:
            module_class = self._module_classes[module_name]
            instance = module_class()

            # Set enabled state based on registry's enabled modules list
            if hasattr(instance, "_enabled"):
                if self._enabled_modules is None:
                    # None means all modules enabled
                    instance._enabled = True
                else:
                    # Only enable if in the enabled modules set
                    instance._enabled = module_name in self._enabled_modules

            self._instances[module_name] = instance
            logger.debug(f"Lazy-loaded module instance: {module_name}")
        return self._instances[module_name]

    def set_enabled_modules(self, enabled_modules: list[str] | None) -> None:
        """Set which modules should be enabled.

        Args:
            enabled_modules: List of module names to enable, or None to enable all
        """
        if enabled_modules is None:
            self._enabled_modules = None  # Enable all
        else:
            self._enabled_modules = set(enabled_modules)  # Enable specific modules

    def get_enabled_modules(self) -> list[Module]:
        """Get all registered modules that are currently enabled.

        Lazy-loads module instances only when requested.

        Returns:
            list[Module]: List of enabled module instances
        """
        enabled_modules = []
        for module_name in self._module_classes.keys():
            # Check if module should be enabled
            if self._enabled_modules is None or module_name in self._enabled_modules:
                module = self._get_instance(module_name)
                if module.enabled:
                    enabled_modules.append(module)
        return enabled_modules

    def get_all_modules(self) -> list[Module]:
        """Get all registered modules regardless of enabled status.

        Lazy-loads all module instances.

        Returns:
            list[Module]: List of all registered module instances
        """
        return [self._get_instance(name) for name in self._module_classes.keys()]

    def get_module(self, name: str) -> Module | None:
        """Get a specific module by name.

        Lazy-loads the module instance if it exists.

        Args:
            name: Module name to retrieve

        Returns:
            Module | None: Module instance if found, None otherwise
        """
        if name in self._module_classes:
            return self._get_instance(name)
        return None

    def clear(self) -> None:
        """Clear all registered modules and instances.

        Primarily used for testing purposes.
        """
        self._module_classes.clear()
        self._instances.clear()
        self._enabled_modules = None
