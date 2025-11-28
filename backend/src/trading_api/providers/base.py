"""Provider base classes and interfaces."""

from abc import ABC, abstractmethod
from pathlib import Path

from trading_api.models.common import CapabilitySpec, ProviderConfig


class Provider(ABC):
    """Abstract base class for all providers.

    Providers implement one or more capabilities and can be auto-discovered
    by the ProviderRegistry.

    [CONVENTION]: providers/{name}/__init__.py exports {Name}Provider class
    """

    @classmethod
    @abstractmethod
    def provider_dir(cls) -> Path:
        """Return the directory path for this provider.

        Returns:
            Path: Provider directory path (e.g., providers/google/)
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name identifier for this provider.

        Returns:
            str: Provider name (e.g., "google", "ibkr", "local")
        """
        ...

    @classmethod
    @abstractmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return capabilities provided by this provider.

        [CLASSMETHOD]: Static declaration, no instance needed for discovery.
        [CRITICAL]: Must be classmethod for startup analysis, NOT instance method.

        Returns:
            list[CapabilitySpec]: Capabilities this provider implements

        Examples:
            >>> GoogleProvider.capabilities()
            [CapabilitySpec(name="auth")]  # ← Must match service requirements
        """
        ...

    @property
    @abstractmethod
    def config(self) -> ProviderConfig:
        """Return provider-specific configuration.

        Returns:
            ProviderConfig: Configuration instance
        """
        ...

    def shutdown(self) -> None:
        """Perform any necessary cleanup on provider shutdown."""
