"""Tests for DatastoreRegistry auto-discovery and lazy-loading."""

from pathlib import Path

import pytest

from trading_api.shared import DatastoreInterface
from trading_api.shared.datastore_registry import DatastoreRegistry


class TestDatastoreRegistry:
    """Test suite for DatastoreRegistry."""

    @pytest.fixture
    def registry(self) -> DatastoreRegistry:
        """Create fresh registry pointing to actual datastores dir."""
        datastores_dir = Path(__file__).parent.parent.parent / "datastores"
        return DatastoreRegistry(datastores_dir)

    def test_auto_discover_finds_inmemory(self, registry: DatastoreRegistry) -> None:
        """Registry discovers InMemoryDatastore from inmemory/ subdirectory."""
        registry.auto_discover()

        assert "inmemory" in registry.list_datastores()

    @pytest.mark.asyncio
    async def test_get_datastores_returns_instances(
        self, registry: DatastoreRegistry
    ) -> None:
        """get_datastores() returns DatastoreInterface instances."""
        registry.auto_discover()

        datastores = await registry.get_datastores()

        assert len(datastores) >= 1
        assert all(isinstance(ds, DatastoreInterface) for ds in datastores)

    @pytest.mark.asyncio
    async def test_get_datastores_filters_by_auto_discover(
        self, registry: DatastoreRegistry
    ) -> None:
        """get_datastores() returns only what was enabled in auto_discover."""
        registry.auto_discover(enabled_names=["inmemory"])

        datastores = await registry.get_datastores()

        assert len(datastores) == 1
        assert datastores[0].__class__.__name__ == "InMemoryDatastore"

    def test_clear_resets_registry(self, registry: DatastoreRegistry) -> None:
        """clear() removes all registered datastores and instances."""
        registry.auto_discover()
        assert len(registry.list_datastores()) > 0

        registry.clear()

        assert len(registry.list_datastores()) == 0

    def test_enabled_names_filter(self, registry: DatastoreRegistry) -> None:
        """auto_discover(enabled_names=[...]) filters by folder name."""
        # Discover with filter that excludes inmemory
        registry.auto_discover(enabled_names=["nonexistent"])

        assert len(registry.list_datastores()) == 0

    def test_enabled_names_includes_inmemory(self, registry: DatastoreRegistry) -> None:
        """auto_discover(enabled_names=["inmemory"]) includes inmemory."""
        registry.auto_discover(enabled_names=["inmemory"])

        assert "inmemory" in registry.list_datastores()

    @pytest.mark.asyncio
    async def test_lazy_loading_creates_single_instance(
        self, registry: DatastoreRegistry
    ) -> None:
        """Multiple get_datastores() calls return same instance."""
        registry.auto_discover(enabled_names=["inmemory"])

        # First call creates instance
        datastores1 = await registry.get_datastores()
        # Second call returns cached instance
        datastores2 = await registry.get_datastores()

        assert datastores1[0] is datastores2[0]
