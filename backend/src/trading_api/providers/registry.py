"""Provider registry for auto-discovery and lazy-loading."""

import asyncio
import importlib
import logging
from pathlib import Path

from trading_api.models.common import (
    CapabilityNotFoundError,
    CapabilitySpec,
    ProviderNotFoundError,
)
from trading_api.providers.base import Provider

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
        self._providers_dir = providers_dir or Path(__file__).parent
        self._provider_classes: dict[str, type[Provider]] = {}
        self._instances: dict[str, Provider] = {}
        self._lock = asyncio.Lock()  # Thread-safe lazy loading

    def auto_discover(self) -> None:
        """Auto-discover providers from directory.

        Convention: providers/{name}/__init__.py exports {Name}Provider
        Example: providers/google/__init__.py exports GoogleProvider
        """
        discovered_providers = {}

        for provider_path in self._providers_dir.iterdir():
            # Skip non-directories and private modules
            if not provider_path.is_dir() or provider_path.name.startswith("_"):
                continue

            # Skip capabilities/ subdirectory
            if provider_path.name == "capabilities":
                continue

            provider_name = provider_path.name
            class_name = f"{provider_name.title()}Provider"

            try:
                # Import: trading_api.providers.google
                module_import = importlib.import_module(
                    f"trading_api.providers.{provider_name}"
                )
                # Get class: GoogleProvider
                provider_class = getattr(module_import, class_name)
                discovered_providers[provider_name] = provider_class
                logger.info(f"Auto-discovered provider: {provider_name}")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to discover provider '{provider_name}': {e}")
                continue

        # Register all discovered providers
        for provider_name, provider_class in discovered_providers.items():
            self.register(provider_class, provider_name)

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
            CapabilityNotFoundError: If capability not satisfied

        [LAZY-LOADING]: Provider instances created on first request.
        [ASYNC]: Must be awaited due to lifecycle hooks.
        """
        providers: dict[str, Provider] = {}  # Deduplication by name

        for req_cap in required_capabilities:
            matched = False

            # Find provider that satisfies this capability
            for name, provider_class in self._provider_classes.items():
                # Check if provider offers matching capability
                for prov_cap in provider_class.capabilities():
                    if req_cap.matches(prov_cap):
                        # Lazy-load provider instance
                        if name not in providers:
                            providers[name] = await self._get_instance(name)
                        matched = True
                        break

                if matched:
                    break

            if not matched:
                raise CapabilityNotFoundError(
                    f"No provider found for capability '{req_cap}'. "
                    f"Available providers: {list(self._provider_classes.keys())}"
                )

        return list(providers.values())

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
                raise ProviderNotFoundError(f"Provider '{name}' not registered")

            provider_class = self._provider_classes[name]
            instance = provider_class()

            # Call lifecycle hook
            await instance.on_startup()

            self._instances[name] = instance
            logger.debug(f"Lazy-loaded provider instance: {name}")

        return self._instances[name]

    async def get_provider(self, name: str) -> Provider:
        """Get specific provider by name.

        Args:
            name: Provider name

        Returns:
            Provider instance

        Raises:
            ProviderNotFoundError: If provider not found
        """
        return await self._get_instance(name)

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._provider_classes.keys())

    async def shutdown(self) -> None:
        """Shutdown all provider instances (call lifecycle hooks).

        Should be called during application shutdown.
        """
        for name, instance in self._instances.items():
            logger.debug(f"Shutting down provider: {name}")
            await instance.on_shutdown()

    def clear(self) -> None:
        """Clear all registered providers (testing only)."""
        self._provider_classes.clear()
        self._instances.clear()
