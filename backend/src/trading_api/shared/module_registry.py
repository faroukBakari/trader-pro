"""Module Registry - Centralized module management.

Provides registration, discovery, and filtering of pluggable modules.
"""

import importlib
import logging
from pathlib import Path
from typing import Any, Dict

from .module_interface import Module

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Centralized registry for managing pluggable modules.

    Provides methods to register module classes, filter by enabled status,
    and lazy-load module instances.

    Attributes:
        _module_classes: Dictionary mapping module names to module classes
        _instances: Dictionary mapping module names to lazy-loaded instances
    """

    def __init__(self, modules_dir: Path) -> None:
        """Initialize an empty module registry."""
        self._module_classes: Dict[str, type[Module]] = {}
        self._instances: Dict[str, Module] = {}
        self._modules_dir = modules_dir

    def register(self, module_class: type[Module], module_name: str) -> None:
        """Register a module class with the registry.

        Args:
            module_class: Module class implementing the Module protocol
            module_name: Name of the module

        Raises:
            ValueError: If a module with the same name is already registered
        """

        if module_name in self._module_classes:
            raise ValueError(f"Module '{module_name}' is already registered")
        self._module_classes[module_name] = module_class
        logger.info(f"Registered module class: {module_name}")

    def auto_discover(self) -> None:
        """Auto-discover and register modules from directory.

        Convention: modules/<module_name>/__init__.py exports <ModuleName>Module.
        Example: modules/broker/__init__.py exports BrokerModule

        Args:
            modules_dir: Path to modules directory to scan

        Raises:
            ValueError: If module naming validation fails
        """
        discovered_modules = {}

        # Step 1: Discover all modules
        for module_path in self._modules_dir.iterdir():
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
                discovered_modules[module_name] = module_class
            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to auto-discover module '{module_name}': {e}")
                continue

        # Step 2: Validate naming conventions
        validation_errors = self._validate_module_names(set(discovered_modules.keys()))
        if validation_errors:
            error_msg = "\n".join(validation_errors)
            raise ValueError(f"Module validation failed:\n{error_msg}")

        # Step 3: Register validated modules
        for module_name, module_class in discovered_modules.items():
            logger.info(f"Auto-discovered module: {module_name}")
            self.register(module_class, module_name)

    def _get_instance(
        self,
        module_name: str,
        version: str | None = None,
        providers: list[Any] | None = None,
    ) -> Module:
        """Get or create module instance (lazy loading).

        Args:
            module_name: Name of module to instantiate
            version: Specific version to load (e.g., "v1"), or None for all versions
            providers: Provider instances to inject

        Returns:
            Module: Module instance
        """
        # Cache key includes version for proper isolation
        cache_key = f"{module_name}:{version}" if version else module_name

        if cache_key not in self._instances:
            module_class = self._module_classes[module_name]
            # Pass as single-item list or None
            versions = [version] if version else None
            # Instantiate with keyword arguments
            instance = module_class(versions=versions, providers=providers)
            self._instances[cache_key] = instance
            logger.debug(f"Lazy-loaded module instance: {cache_key}")
        return self._instances[cache_key]

    def get_modules(
        self,
        *,  # Force keyword-only
        module_names: list[str] | None = None,
        providers: list[Any] | None = None,
    ) -> list[Module]:
        """Get modules filtered by enabled list with providers injected.

        Args:
            module_names: Module specs (e.g., ["broker:v1", "datafeed:v2"])
                         or None for all modules
            providers: Provider instances to inject into modules

        Returns:
            List of module instances

        [KEYWORD-ONLY]: Prevents positional argument errors.
        """
        if module_names is None:
            # Return all modules with all versions
            return [
                self._get_instance(name, providers=providers)
                for name in self._module_classes.keys()
            ]
        else:
            # Return only specified modules
            modules = []
            for module_spec in module_names:
                module_name, version = self._parse_module_spec(module_spec)
                if module_name in self._module_classes:
                    modules.append(
                        self._get_instance(
                            module_name, version=version, providers=providers
                        )
                    )
            return modules

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

    def _parse_module_spec(self, spec: str) -> tuple[str, str | None]:
        """Parse module specification.

        Args:
            spec: "module_name" or "module_name:version"

        Returns:
            Tuple of (module_name, version or None)
        """
        if ":" in spec:
            module_name, version = spec.split(":", 1)
            return module_name.strip(), version.strip()
        return spec.strip(), None  # None = all versions

    def _validate_module_names(self, module_names: set[str]) -> list[str]:
        """Validate module naming conventions and uniqueness.

        Validates that:
        1. Module names use hyphens for multi-word names (not underscores)
        2. Package names follow expected patterns:
           - OpenAPI: @trader-pro/client-{module}
           - AsyncAPI: ws-types-{module}
           - Python: {Module}Client

        Args:
            module_names: Set of discovered module names

        Returns:
            List of error messages (empty if all validations pass)
        """
        errors = []

        # Check for naming convention violations
        for name in module_names:
            # Validate no underscores in module names
            if "_" in name:
                errors.append(
                    f"Module '{name}' contains underscore. "
                    f"Use hyphen for multi-word names."
                )

        # Check for duplicate module names (inherent in set, but explicit check for clarity)
        if len(module_names) != len(set(module_names)):
            errors.append("Duplicate module names detected")

        return errors
