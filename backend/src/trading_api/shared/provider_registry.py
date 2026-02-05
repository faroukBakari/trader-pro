"""Provider registry for auto-discovery and lazy-loading."""

import asyncio
import importlib
import logging
from pathlib import Path

from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import CommonException
from trading_api.shared import Provider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for authentication and capability providers.

    Mirrors ModuleRegistry pattern with auto-discovery and lazy-loading.

    [THREAD-SAFE]: Uses asyncio.Lock for concurrent instance creation.
    """

    def __init__(self, providers_dir: Path | None = None) -> None:
        """Initialize provider registry.

        Args:
            providers_dir: Path to providers directory
                          (defaults to trading_api/providers/)
        """
        self._providers_dir = (
            providers_dir or Path(__file__).parent.parent / "providers"
        )
        self._provider_classes: dict[str, type[Provider]] = {}
        self._instances: dict[str, Provider] = {}
        self._lock = asyncio.Lock()  # Thread-safe lazy loading

    def auto_discover(self, enabled_names: list[str] | None = None) -> None:
        """Auto-discover providers from directory, optionally filtering by name.

        Scans provider modules for classes that inherit from Provider interface.
        Uses provider_dir().name for canonical provider name (same pattern as ModuleRegistry).

        Args:
            enabled_names: Provider folder names to load (None = all).
                          e.g., ["tws", "google"] or ["fakebroker"]

        Example: providers/tws/__init__.py exports TWSDatafeedProvider(Provider)
                 → registered as "tws" (from provider_dir().name)
        """
        discovered_providers: dict[str, type[Provider]] = {}

        for provider_path in self._providers_dir.iterdir():
            # Skip non-directories and private modules
            if not provider_path.is_dir() or provider_path.name.startswith("_"):
                continue

            # Skip capabilities/ and tests/ subdirectories
            if provider_path.name == "tests":
                continue

            folder_name = provider_path.name

            # Filter by enabled_names if provided
            if enabled_names and folder_name not in enabled_names:
                logger.debug(f"Skipping provider '{folder_name}' (not in enabled list)")
                continue

            class_name = folder_name

            try:
                # Import: trading_api.providers.tws
                module_import = importlib.import_module(
                    f"trading_api.providers.{class_name}"
                )
            except ImportError as e:
                logger.warning(f"Failed to import provider module '{class_name}': {e}")
                continue

            # Scan __all__ for Provider subclasses (same pattern as ModuleRegistry)
            for attr_name in getattr(module_import, "__all__", []):
                obj = getattr(module_import, attr_name, None)
                if not (
                    isinstance(obj, type)
                    and issubclass(obj, Provider)
                    and obj is not Provider
                ):
                    continue

                # Use provider_dir().name for canonical name (mirrors Module.module_dir().name)
                discovered_providers[obj.__name__] = obj
                logger.info(f"Auto-discovered provider: {class_name} ({obj.__name__})")

        # Register all discovered providers
        for class_name, provider_class in discovered_providers.items():
            self.register(provider_class, class_name)

    def register(self, provider_class: type[Provider], name: str) -> None:
        """Register a provider class.

        Args:
            provider_class: Provider class implementing Provider protocol
            name: Provider name

        Raises:
            ValueError: If provider already registered
        """
        if name in self._provider_classes:
            raise ValueError(f"Provider '{name}' already registered")

        self._provider_classes[name] = provider_class
        logger.info(f"Registered provider class: {name}")

    async def get_providers(
        self, required_capabilities: list[CapabilitySpec]
    ) -> list[Provider]:
        """Get provider instances matching required capabilities.

        Args:
            required_capabilities: List of capability requirements

        Returns:
            List of provider instances (deduplicated)

        Raises:
            CommonException: If capability not satisfied

        [LAZY-LOADING]: Provider instances created on first request.
        [ASYNC]: Must be awaited due to lifecycle hooks.
        """
        providers: dict[str, list[Provider]] = {}  # Deduplication by name

        for req_cap in required_capabilities:
            # Find provider that satisfies this capability
            providers[req_cap.name] = await asyncio.gather(
                *[
                    self._get_instance(name)
                    for name, provider_class in self._provider_classes.items()
                    if any(
                        req_cap.matches(prov_cap)
                        for prov_cap in provider_class.capabilities()
                    )
                ]
            )

            if not providers[req_cap.name]:
                raise CommonException(
                    code="COMMON_CAPABILITY_NOT_FOUND",
                    message=f"No provider found for capability '{req_cap}'. "
                    f"Available providers: {list(self._provider_classes.keys())}",
                )

        return [prov for prov_list in providers.values() for prov in prov_list]

    async def _get_instance(self, name: str) -> Provider:
        """Get or create provider instance (lazy loading).

        Args:
            name: Provider name

        Returns:
            Provider instance

        [THREAD-SAFE]: Uses lock to prevent race conditions in concurrent environments.
        """
        # Fast path: instance already exists
        if name in self._instances:
            return self._instances[name]

        # Slow path: create instance with lock
        async with self._lock:
            # Double-check after acquiring lock
            if name in self._instances:
                return self._instances[name]

            if name not in self._provider_classes:
                raise CommonException(
                    code="COMMON_PROVIDER_NOT_FOUND",
                    message=f"Provider '{name}' not registered",
                )

            provider_class = self._provider_classes[name]
            instance = provider_class()

            self._instances[name] = instance
            logger.debug(f"Lazy-loaded provider instance: {name}")

        return self._instances[name]

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._provider_classes.keys())

    def clear(self) -> None:
        """Clear all registered providers (testing only)."""
        self._provider_classes.clear()
        self._instances.clear()
