"""Module Registry - Centralized module management.

Provides registration, discovery, and filtering of pluggable modules.
"""

import importlib
import logging
from pathlib import Path

from trading_api.models.common import CapabilitySpec
from trading_api.shared import DatastoreInterface
from trading_api.shared.provider_interface import Provider

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
        self._module_classes: dict[str, type[Module]] = {}
        self._instances: dict[str, Module] = {}
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

    def auto_discover(self, enabled_modules: list[str] | None = None) -> None:
        """Auto-discover and register modules from directory.

        Convention: modules/<module_name>/__init__.py exports <ModuleName>Module.
        Example: modules/broker/__init__.py exports BrokerModule

        Args:
            enabled_modules: List of enabled module specifications (None = all)

        Raises:
            ValueError: If module naming validation fails
        """
        enabled_modules = enabled_modules or []
        enabled_module_names = {
            name
            for name, _ in [
                self._parse_module_spec(module_spec) for module_spec in enabled_modules
            ]
        }
        discovered_modules = {}

        # Step 1: Discover all modules
        for module_path in self._modules_dir.iterdir():
            # Skip non-directories and private/internal modules
            if not module_path.is_dir() or module_path.name.startswith("_"):
                continue

            if enabled_module_names and module_path.name not in enabled_module_names:
                logger.debug(
                    f"Skipping module '{module_path.name}' (not in enabled list)"
                )
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
        providers: list[Provider] | None = None,
        datastores: list[DatastoreInterface] | None = None,
    ) -> Module:
        """Get or create module instance (lazy loading).

        Args:
            module_name: Name of module to instantiate
            version: Specific version to load (e.g., "v1"), or None for all versions
            providers: Provider instances to inject
            datastores: Optional shared datastores for service repository injection

        Returns:
            Module: Module instance
        """
        providers = providers or []
        datastores = datastores or []

        # Cache key includes version for proper isolation
        cache_key = f"{module_name}:{version}" if version else module_name

        if cache_key not in self._instances:
            module_class = self._module_classes[module_name]
            # Pass as single-item list or None
            versions = [version] if version else None
            # Instantiate with keyword arguments
            instance = module_class(
                versions=versions, providers=providers, datastores=datastores
            )
            self._instances[cache_key] = instance
            logger.debug(f"Lazy-loaded module instance: {cache_key}")
        return self._instances[cache_key]

    def get_modules(
        self,
        *,  # Force keyword-only
        providers: list[Provider] | None = None,
        datastores: list[DatastoreInterface] | None = None,
    ) -> list[Module]:
        """Get modules filtered by enabled list with providers injected.

        Args:
            providers: Provider instances to inject into modules
            datastores: Optional shared datastores for service repository injection

        Returns:
            List of module instances

        [KEYWORD-ONLY]: Prevents positional argument errors.
        """
        providers = providers or []
        datastores = datastores or []

        return [
            self._get_instance(name, providers=providers, datastores=datastores)
            for name in self._module_classes.keys()
        ]

    def required_capabilities(self) -> list[CapabilitySpec]:
        """Get the set of all required capabilities across registered modules.

        Returns:
            List of unique capability names required by all modules.
        """
        capabilities: set[CapabilitySpec] = set()

        # Get module specs to enable
        module_specs = list(self._module_classes.keys())

        for spec in module_specs:
            # Parse "broker:v1" → "broker"
            module_name = spec.split(":")[0] if ":" in spec else spec

            # Get module class (not instance)
            module_class = self._module_classes.get(module_name)
            if module_class is None:
                continue

            # Get service class (static, no instantiation)
            service_class = module_class._service_class()

            # Get capabilities (classmethod, no instance)
            # NOTE: Services may not have capabilities() yet (Phase 4)
            if hasattr(service_class, "capabilities"):
                service_caps = service_class.capabilities()
                if service_caps is not None:
                    capabilities.update(service_caps)

        return list(capabilities)

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
