"""Datastore registry for auto-discovery and centralized management.

Mirrors ProviderRegistry pattern with auto-discovery from datastores/ directory.
Provides synchronous instantiation (unlike async providers).
"""

import importlib
import logging
import threading
from pathlib import Path

from trading_api.shared.datastore_interface import DatastoreInterface

logger = logging.getLogger(__name__)


class DatastoreRegistry:
    """Registry for datastore implementations.

    Mirrors ProviderRegistry pattern with auto-discovery and lazy-loading.
    Unlike providers, datastores are synchronously instantiated.

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
        self._lock = threading.Lock()  # Thread-safe lazy loading

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
        discovered_datastores: dict[str, type[DatastoreInterface]] = {}

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

            # Scan __all__ for DatastoreInterface subclasses (same pattern as ProviderRegistry)
            for attr_name in getattr(module_import, "__all__", []):
                obj = getattr(module_import, attr_name, None)
                if not (
                    isinstance(obj, type)
                    and issubclass(obj, DatastoreInterface)
                    and obj is not DatastoreInterface
                ):
                    continue

                # Use folder name for canonical name (mirrors Provider pattern)
                discovered_datastores[folder_name] = obj
                logger.info(
                    f"Auto-discovered datastore: {folder_name} ({obj.__name__})"
                )

        # Register all discovered datastores
        for name, datastore_class in discovered_datastores.items():
            self.register(datastore_class, name)

    def register(self, datastore_class: type[DatastoreInterface], name: str) -> None:
        """Register a datastore class.

        Args:
            datastore_class: Datastore class implementing DatastoreInterface
            name: Datastore name (e.g., "inmemory", "postgres")

        Raises:
            ValueError: If datastore already registered
        """
        if name in self._datastore_classes:
            raise ValueError(f"Datastore '{name}' already registered")

        self._datastore_classes[name] = datastore_class
        logger.info(f"Registered datastore class: {name}")

    def get_datastores(
        self, names: list[str] | None = None
    ) -> list[DatastoreInterface]:
        """Get datastore instances by name.

        Args:
            names: Datastore names to get (None = all registered)

        Returns:
            List of datastore instances

        Raises:
            ValueError: If requested datastore not found

        [LAZY-LOADING]: Datastore instances created on first request.
        [SYNC]: Unlike providers, datastores are synchronously instantiated.
        """
        if names is None:
            names = list(self._datastore_classes.keys())

        datastores: list[DatastoreInterface] = []

        for name in names:
            datastores.append(self._get_instance(name))

        return datastores

    def _get_instance(self, name: str) -> DatastoreInterface:
        """Get or create datastore instance (lazy loading).

        Args:
            name: Datastore name

        Returns:
            DatastoreInterface instance

        Raises:
            ValueError: If datastore not registered

        [THREAD-SAFE]: Uses lock to prevent race conditions.
        """
        # Fast path: instance already exists
        if name in self._instances:
            return self._instances[name]

        # Slow path: create instance with lock
        with self._lock:
            # Double-check after acquiring lock
            if name in self._instances:
                return self._instances[name]

            if name not in self._datastore_classes:
                raise ValueError(
                    f"Datastore '{name}' not registered. "
                    f"Available: {list(self._datastore_classes.keys())}"
                )

            datastore_class = self._datastore_classes[name]
            instance = datastore_class()

            self._instances[name] = instance
            logger.debug(f"Lazy-loaded datastore instance: {name}")

        return self._instances[name]

    def get_datastore(self, name: str) -> DatastoreInterface:
        """Get specific datastore by name.

        Args:
            name: Datastore name

        Returns:
            DatastoreInterface instance

        Raises:
            ValueError: If datastore not found
        """
        return self._get_instance(name)

    def list_datastores(self) -> list[str]:
        """List all registered datastore names."""
        return list(self._datastore_classes.keys())

    def clear(self) -> None:
        """Clear all registered datastores (testing only)."""
        self._datastore_classes.clear()
        self._instances.clear()
