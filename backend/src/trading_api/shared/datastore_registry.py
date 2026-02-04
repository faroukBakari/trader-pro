"""Datastore registry for auto-discovery and centralized management.

Mirrors ProviderRegistry pattern with auto-discovery from datastores/ directory.
All datastores use uniform async factory pattern via DatastoreInterface.create().
"""

import asyncio
import importlib
import logging
import threading
from pathlib import Path

from trading_api.models.common import DatastoreCapabilitySpec
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import DatastoreInterface

logger = logging.getLogger(__name__)


class DatastoreRegistry:
    """Registry for datastore implementations.

    Mirrors ProviderRegistry pattern with auto-discovery and lazy-loading.
    All datastores are instantiated via async `cls.create()` factory.

    [THREAD-SAFE]: Uses threading.Lock for concurrent instance creation.
    """

    def __init__(self, datastores_dir: Path | None = None) -> None:
        """Initialize datastore registry.

        Args:
            datastores_dir: Path to datastores directory
                           (defaults to trading_api/datastores/)
        """
        self._datastores_dir = (
            datastores_dir or Path(__file__).parent.parent / "datastores"
        )
        self._datastore_classes: dict[str, type[DatastoreInterface]] = {}
        self._instances: dict[str, DatastoreInterface] = {}
        self._lock = threading.Lock()  # Thread-safe to extend usage beyond asyncio

    def auto_discover(self, enabled_names: list[str] | None = None) -> None:
        """Auto-discover datastores from directory, optionally filtering by name.

        Scans datastore modules for classes that inherit from DatastoreInterface.
        Uses folder name for canonical datastore name (same pattern as ProviderRegistry).

        Args:
            enabled_names: Datastore folder names to load (None = all).
                          e.g., ["inmemory"] or ["inmemory", "postgres"]

        Example: datastores/inmemory/__init__.py exports InMemoryDatastore(DatastoreInterface)
                 → registered as "inmemory" (from folder name)
        """
        enabled_names = enabled_names or []
        for datastore_path in self._datastores_dir.iterdir():
            # Skip non-directories and private modules
            if not datastore_path.is_dir() or datastore_path.name.startswith("_"):
                continue

            # Skip tests/ subdirectory
            if datastore_path.name == "tests":
                continue

            folder_name = datastore_path.name

            # Filter by enabled_names if provided
            if enabled_names and folder_name not in enabled_names:
                logger.debug(
                    f"Skipping datastore '{folder_name}' (not in enabled list)"
                )
                continue

            try:
                # Import: trading_api.datastores.inmemory
                module_import = importlib.import_module(
                    f"trading_api.datastores.{folder_name}"
                )
            except ImportError as e:
                logger.warning(
                    f"Failed to import datastore module '{folder_name}': {e}"
                )
                continue

            # Scan __all__ for DatastoreInterface subclasses
            for attr_name in getattr(module_import, "__all__", []):
                obj = getattr(module_import, attr_name, None)
                if not (
                    isinstance(obj, type)
                    and issubclass(obj, DatastoreInterface)
                    and obj is not DatastoreInterface
                ):
                    continue

                # Use folder name for canonical name (mirrors Provider pattern)
                if folder_name in self._datastore_classes:
                    logger.warning(f"Datastore '{folder_name}' already registered")
                    continue

                self._datastore_classes[folder_name] = obj
                logger.info(
                    f"Auto-discovered datastore: {folder_name} ({obj.__name__})"
                )

    async def get_datastores(
        self,
        required_capabilities: list[DatastoreCapabilitySpec] | None = None,
        config: Settings | None = None,
    ) -> list[DatastoreInterface]:
        """Get datastore instances, optionally filtered by capabilities.

        Args:
            required_capabilities: Optional capability requirements to filter by.
                                  If None, returns all datastores.
            config: Optional Settings for dependency injection (tests).
                   Defaults to global settings singleton.

        Returns:
            List of datastore instances matching requirements

        Raises:
            ValueError: If requested datastore not found

        [LAZY-LOADING]: Datastore instances created on first request via cls.create().
        [CAPABILITY-FILTERING]: Mirrors ProviderRegistry pattern.
        """
        if required_capabilities is None:
            # No filtering - return all datastores
            return await asyncio.gather(
                *[
                    self._get_instance(name, config=config)
                    for name in self._datastore_classes.keys()
                ]
            )

        # Filter datastores by capability requirements
        # A datastore must satisfy ALL required (non-optional) capabilities
        matching_names: list[str] = []

        for name, datastore_class in self._datastore_classes.items():
            provided_caps = datastore_class.capabilities()
            satisfies_all = True

            for req_cap in required_capabilities:
                matched = any(req_cap.matches(prov_cap) for prov_cap in provided_caps)
                if not matched and not req_cap.optional:
                    satisfies_all = False
                    break

            if satisfies_all:
                matching_names.append(name)

        return await asyncio.gather(
            *[self._get_instance(name, config=config) for name in matching_names]
        )

    async def _get_instance(
        self, name: str, config: Settings | None = None
    ) -> DatastoreInterface:
        """Get or create datastore instance via async factory.

        Args:
            name: Datastore name
            config: Optional Settings for dependency injection (tests).
                   Defaults to global settings singleton.

        Returns:
            DatastoreInterface instance

        Raises:
            ValueError: If datastore not registered

        [THREAD-SAFE]: Uses lock to prevent race conditions.
        """
        # Slow path: create instance with lock
        # Needed as we have multithreading + asyncio
        with self._lock:
            # Check after acquiring lock
            if name in self._instances:
                return self._instances[name]

            if name not in self._datastore_classes:
                raise ValueError(
                    f"Datastore '{name}' not registered. "
                    f"Available: {list(self._datastore_classes.keys())}"
                )

            datastore_class = self._datastore_classes[name]
            instance = await datastore_class.create(config=config)

            self._instances[name] = instance
            logger.debug(f"Loaded datastore instance: {name}")

        return self._instances[name]

    def list_datastores(self) -> list[str]:
        """List all registered datastore names."""
        return list(self._datastore_classes.keys())

    def clear(self) -> None:
        """Clear all registered datastores (testing only)."""
        self._datastore_classes.clear()
        self._instances.clear()
