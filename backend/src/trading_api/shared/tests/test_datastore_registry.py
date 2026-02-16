"""Tests for DatastoreRegistry auto-discovery and lazy-loading."""

import asyncio
from pathlib import Path

import pytest

from trading_api.models.common import DatastoreCapabilitySpec
from trading_api.shared import DatastoreInterface
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import TableInterface
from trading_api.shared.datastore_registry import DatastoreRegistry


class TestDatastoreRegistry:
    """Test suite for DatastoreRegistry."""

    @pytest.fixture
    def registry(self) -> DatastoreRegistry:
        """Create fresh registry pointing to actual datastores dir."""
        datastores_dir = Path(__file__).parent.parent.parent / "datastores"
        return DatastoreRegistry(datastores_dir)

    def test_auto_discover_finds_duckdb(self, registry: DatastoreRegistry) -> None:
        """Registry discovers DuckDBDatastore from duckdb/ subdirectory."""
        registry.auto_discover()

        assert "duckdb" in registry.list_datastores()

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
        registry.auto_discover(enabled_names=["duckdb"])

        datastores = await registry.get_datastores()

        assert len(datastores) == 1
        assert datastores[0].__class__.__name__ == "DuckDBDatastore"

    def test_clear_resets_registry(self, registry: DatastoreRegistry) -> None:
        """clear() removes all registered datastores and instances."""
        registry.auto_discover()
        assert len(registry.list_datastores()) > 0

        registry.clear()

        assert len(registry.list_datastores()) == 0

    def test_enabled_names_filter(self, registry: DatastoreRegistry) -> None:
        """auto_discover(enabled_names=[...]) filters by folder name."""
        # Discover with filter that excludes duckdb
        registry.auto_discover(enabled_names=["nonexistent"])

        assert len(registry.list_datastores()) == 0

    def test_enabled_names_includes_duckdb(self, registry: DatastoreRegistry) -> None:
        """auto_discover(enabled_names=["duckdb"]) includes duckdb."""
        registry.auto_discover(enabled_names=["duckdb"])

        assert "duckdb" in registry.list_datastores()

    @pytest.mark.asyncio
    async def test_lazy_loading_creates_single_instance(
        self, registry: DatastoreRegistry
    ) -> None:
        """Multiple get_datastores() calls return same instance."""
        registry.auto_discover(enabled_names=["duckdb"])

        # First call creates instance
        datastores1 = await registry.get_datastores()
        # Second call returns cached instance
        datastores2 = await registry.get_datastores()

        assert datastores1[0] is datastores2[0]


class TestConcurrentDatastoreCreation:
    """Regression tests for concurrent datastore creation via asyncio.gather.

    Prior bug: threading.Lock + await inside _get_instance = thread-level deadlock.
    A thread-level deadlock freezes the event loop, so asyncio.wait_for cannot
    help — its timeout callback never fires on a blocked thread. We rely on
    pytest-timeout (SIGALRM) as the hard backstop: @pytest.mark.timeout(3)
    ensures the test fails fast instead of hanging for the global 10s default.
    """

    @pytest.fixture
    def registry(self) -> DatastoreRegistry:
        return DatastoreRegistry()

    def _make_fake_datastore(
        self, name: str, create_delay: float = 0
    ) -> type[DatastoreInterface]:
        """Build a fake DatastoreInterface subclass with configurable async delay."""

        class FakeDatastore(DatastoreInterface):
            @classmethod
            def capabilities(cls) -> list[DatastoreCapabilitySpec]:
                return []

            @classmethod
            async def create(cls, config: Settings | None = None) -> "FakeDatastore":
                if create_delay > 0:
                    await asyncio.sleep(create_delay)
                return cls()

            def table(self, model_class: type) -> TableInterface:
                raise NotImplementedError

            async def list_tables(self, prefix: str | None = None) -> list[str]:
                return []

            async def drop_table(self, name: str) -> bool:
                return False

        FakeDatastore.__name__ = name
        FakeDatastore.__qualname__ = name
        return FakeDatastore

    @pytest.mark.asyncio
    @pytest.mark.timeout(3)
    async def test_concurrent_creation_no_deadlock(
        self, registry: DatastoreRegistry
    ) -> None:
        """3+ datastores with mixed sync/async create() must not deadlock.

        Reproduces the exact scenario: asyncio.gather runs N coroutines,
        one yields on a real await, others must not block the event loop.
        SIGALRM at 3s kills the test if the event loop is frozen.
        """
        # Register 3 fake datastores: instant, slow (real await), instant
        registry._datastore_classes["fast_a"] = self._make_fake_datastore("FastA")
        registry._datastore_classes["slow_b"] = self._make_fake_datastore(
            "SlowB", create_delay=0.1
        )
        registry._datastore_classes["fast_c"] = self._make_fake_datastore("FastC")

        datastores = await registry.get_datastores()

        assert len(datastores) == 3
        assert all(isinstance(ds, DatastoreInterface) for ds in datastores)

    @pytest.mark.asyncio
    @pytest.mark.timeout(3)
    async def test_concurrent_creation_all_slow(
        self, registry: DatastoreRegistry
    ) -> None:
        """All datastores with real async create() must not deadlock."""
        for i in range(4):
            name = f"slow_{i}"
            registry._datastore_classes[name] = self._make_fake_datastore(
                f"Slow{i}", create_delay=0.05
            )

        datastores = await registry.get_datastores()

        assert len(datastores) == 4
