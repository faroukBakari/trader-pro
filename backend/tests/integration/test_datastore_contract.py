"""Datastore Contract Tests - validates all DatastoreInterface implementations.

These tests ensure every datastore implementation conforms to the DatastoreInterface
contract. Tests are parametrized to run against InMemory and Postgres datastores.

[ARCHITECTURE] DRY principle: Common behavior tested once, implementation-specific
tests focus only on unique features (e.g., psycopg UniqueViolation, connection pools).

Run with:
- All datastores: pytest tests/integration/test_datastore_contract.py -v
- InMemory only: pytest tests/integration/test_datastore_contract.py -v -k inmemory
- Postgres only: pytest tests/integration/test_datastore_contract.py -v -k postgres -m integration
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlmodel import Field, SQLModel

from trading_api.datastores import InMemoryDatastore
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import DatastoreInterface, TableInterface

# =============================================================================
# Test Models
# =============================================================================


class ContractTestModel(SQLModel):
    """Standard test model for CRUD operations."""

    id: str
    name: str
    category: str = "default"


class IndexedContractModel(SQLModel):
    """Model with indexes for index contract tests."""

    email: str = Field(unique=True)
    group: str = Field(index=True)
    value: int


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def inmemory_datastore(
    test_settings: Settings,
) -> AsyncIterator[DatastoreInterface]:
    """InMemoryDatastore fixture using test_settings."""
    ds = await InMemoryDatastore.create(config=test_settings)
    yield ds


@pytest.fixture
async def postgres_datastore(
    test_settings: Settings,
) -> AsyncIterator[DatastoreInterface]:
    """PostgresDatastore fixture using test_settings.

    Requires @pytest.mark.integration marker.
    """
    from trading_api.datastores import PostgresDatastore

    # test_database fixture already set DSN in test_settings
    ds = await PostgresDatastore.create(config=test_settings)
    yield ds
    await ds.close()


@pytest.fixture(
    params=[
        pytest.param("inmemory", id="inmemory"),
        pytest.param(
            "postgres",
            id="postgres",
            marks=[pytest.mark.integration, pytest.mark.postgres],
        ),
    ]
)
async def any_datastore(
    request: pytest.FixtureRequest,
    inmemory_datastore: DatastoreInterface,
    postgres_datastore: DatastoreInterface | None,
) -> AsyncIterator[DatastoreInterface]:
    """Parametrized fixture providing each datastore implementation.

    InMemory runs always, Postgres requires integration marker.
    """
    if request.param == "inmemory":
        yield inmemory_datastore
    elif request.param == "postgres":
        if postgres_datastore is None:
            pytest.skip("PostgreSQL not available")
        yield postgres_datastore


@pytest.fixture
async def table(
    any_datastore: DatastoreInterface,
) -> AsyncIterator[TableInterface[Any]]:
    """Table fixture with full reset for test isolation.

    Uses reset() instead of clear() to ensure indexes are also removed,
    allowing tests to run in parallel without index conflicts.
    """
    tbl = any_datastore.table(ContractTestModel)
    await tbl.reset()
    yield tbl
    await tbl.reset()


@pytest.fixture
async def indexed_table(
    any_datastore: DatastoreInterface,
) -> AsyncIterator[TableInterface[Any]]:
    """Table with indexes fixture with full reset for test isolation."""
    tbl = any_datastore.table(IndexedContractModel)
    await tbl.reset()
    yield tbl
    await tbl.reset()


# =============================================================================
# Helper Functions
# =============================================================================


def normalize_result(result: Any) -> dict[str, Any]:
    """Normalize result to dict for comparison.

    InMemory returns BaseModel, Postgres returns dict.
    """
    if result is None:
        return {}
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return dict(result)


# =============================================================================
# DatastoreInterface Contract Tests
# =============================================================================


class TestDatastoreInterfaceContract:
    """Tests that validate DatastoreInterface implementation requirements."""

    @pytest.mark.asyncio
    async def test_has_persistence_returns_bool(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """has_persistence property returns boolean."""
        assert isinstance(any_datastore.has_persistence, bool)

    @pytest.mark.asyncio
    async def test_has_transactions_returns_bool(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """has_transactions property returns boolean."""
        assert isinstance(any_datastore.has_transactions, bool)

    @pytest.mark.asyncio
    async def test_is_relational_returns_bool(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """is_relational property returns boolean."""
        assert isinstance(any_datastore.is_relational, bool)

    @pytest.mark.asyncio
    async def test_datastore_name_returns_string(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """datastore_name() returns non-empty string."""
        name = any_datastore.datastore_name()
        assert isinstance(name, str)
        assert len(name) > 0

    @pytest.mark.asyncio
    async def test_table_returns_table_interface(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """table() returns TableInterface implementation."""
        tbl = any_datastore.table(ContractTestModel)
        assert isinstance(tbl, TableInterface)

    @pytest.mark.asyncio
    async def test_table_returns_same_instance(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """table() returns same instance for same model class."""
        tbl1 = any_datastore.table(ContractTestModel)
        tbl2 = any_datastore.table(ContractTestModel)
        assert tbl1 is tbl2


# =============================================================================
# CRUD Contract Tests
# =============================================================================


class TestTableCRUDContract:
    """Tests that validate TableInterface CRUD operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, table: TableInterface[Any]) -> None:
        """Basic store and retrieve operation."""
        model = ContractTestModel(id="1", name="test", category="A")
        await table.set("1", model)

        result = await table.get("1")
        assert result is not None
        data = normalize_result(result)
        assert data["name"] == "test"
        assert data["category"] == "A"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, table: TableInterface[Any]
    ) -> None:
        """Get non-existent key returns None."""
        result = await table.get("nonexistent_key_12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(
        self, table: TableInterface[Any]
    ) -> None:
        """Delete existing key returns True."""
        await table.set("del_key", ContractTestModel(id="del", name="to_delete"))

        deleted = await table.delete("del_key")
        assert deleted is True
        assert await table.get("del_key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(
        self, table: TableInterface[Any]
    ) -> None:
        """Delete non-existent key returns False."""
        deleted = await table.delete("nonexistent_key_67890")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_exists_true_when_present(self, table: TableInterface[Any]) -> None:
        """exists() returns True when key present."""
        await table.set("exists_key", ContractTestModel(id="e", name="exists"))
        assert await table.exists("exists_key") is True

    @pytest.mark.asyncio
    async def test_exists_false_when_absent(self, table: TableInterface[Any]) -> None:
        """exists() returns False when key absent."""
        assert await table.exists("absent_key_11111") is False

    @pytest.mark.asyncio
    async def test_keys_returns_all_keys(self, table: TableInterface[Any]) -> None:
        """keys() returns all stored keys."""
        await table.set("k1", ContractTestModel(id="1", name="a"))
        await table.set("k2", ContractTestModel(id="2", name="b"))

        keys = await table.keys()
        assert set(keys) == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_values_returns_all_values(self, table: TableInterface[Any]) -> None:
        """values() returns all stored values."""
        await table.set("v1", ContractTestModel(id="1", name="alpha"))
        await table.set("v2", ContractTestModel(id="2", name="beta"))

        values = await table.values()
        assert len(values) == 2
        names = {normalize_result(v)["name"] for v in values}
        assert names == {"alpha", "beta"}

    @pytest.mark.asyncio
    async def test_clear_removes_all_entries(self, table: TableInterface[Any]) -> None:
        """clear() removes all entries."""
        await table.set("c1", ContractTestModel(id="1", name="a"))
        await table.set("c2", ContractTestModel(id="2", name="b"))

        await table.clear()

        assert await table.count() == 0
        assert await table.keys() == []

    @pytest.mark.asyncio
    async def test_count_returns_entry_count(self, table: TableInterface[Any]) -> None:
        """count() returns correct number of entries."""
        assert await table.count() == 0

        await table.set("cnt1", ContractTestModel(id="1", name="one"))
        assert await table.count() == 1

        await table.set("cnt2", ContractTestModel(id="2", name="two"))
        assert await table.count() == 2

    @pytest.mark.asyncio
    async def test_iterate_yields_all_pairs(self, table: TableInterface[Any]) -> None:
        """iterate() yields all key-value pairs."""
        await table.set("it1", ContractTestModel(id="1", name="alpha"))
        await table.set("it2", ContractTestModel(id="2", name="beta"))

        pairs = [(k, v) async for k, v in table.iterate()]

        assert len(pairs) == 2
        keys = {k for k, _ in pairs}
        assert keys == {"it1", "it2"}

    @pytest.mark.asyncio
    async def test_set_overwrites_existing(self, table: TableInterface[Any]) -> None:
        """set() overwrites existing value for same key."""
        await table.set("ow_key", ContractTestModel(id="1", name="old"))
        await table.set("ow_key", ContractTestModel(id="1", name="new"))

        result = await table.get("ow_key")
        data = normalize_result(result)
        assert data["name"] == "new"
        assert await table.count() == 1


# =============================================================================
# Index Contract Tests
# =============================================================================


class TestTableIndexContract:
    """Tests that validate TableInterface index operations."""

    @pytest.mark.asyncio
    async def test_create_index_enables_lookup(
        self, table: TableInterface[Any]
    ) -> None:
        """create_index enables lookup by indexed field."""
        await table.set("idx1", ContractTestModel(id="1", name="test", category="X"))
        await table.create_index("category")

        result = await table.get("X", index="category")
        assert result is not None
        data = normalize_result(result)
        assert data["id"] == "1"

    @pytest.mark.asyncio
    async def test_get_by_index_returns_correct_record(
        self, table: TableInterface[Any]
    ) -> None:
        """get with index returns correct record among multiple."""
        await table.set("gi1", ContractTestModel(id="1", name="first", category="A"))
        await table.set("gi2", ContractTestModel(id="2", name="second", category="B"))
        await table.create_index("category")

        result = await table.get("B", index="category")
        data = normalize_result(result)
        assert data["name"] == "second"

    @pytest.mark.asyncio
    async def test_delete_by_index(self, table: TableInterface[Any]) -> None:
        """delete with index removes correct record."""
        await table.set("di1", ContractTestModel(id="1", name="target", category="Z"))
        await table.create_index("category")

        deleted = await table.delete("Z", index="category")
        assert deleted is True
        assert await table.get("di1") is None

    @pytest.mark.asyncio
    async def test_index_updated_on_overwrite(self, table: TableInterface[Any]) -> None:
        """Index is updated when record is overwritten with different value."""
        await table.create_index("category")
        await table.set("io1", ContractTestModel(id="1", name="old", category="OLD"))
        await table.set("io1", ContractTestModel(id="1", name="new", category="NEW"))

        # Old index value should not find it
        assert await table.get("OLD", index="category") is None
        # New index value should find it
        result = await table.get("NEW", index="category")
        assert result is not None

    @pytest.mark.asyncio
    async def test_keys_with_index_returns_indexed_values(
        self, table: TableInterface[Any]
    ) -> None:
        """keys(index=...) returns distinct indexed field values."""
        await table.create_index("category")
        await table.set("ki1", ContractTestModel(id="1", name="a", category="CAT1"))
        await table.set("ki2", ContractTestModel(id="2", name="b", category="CAT2"))

        indexed_keys = await table.keys(index="category")
        assert set(indexed_keys) == {"CAT1", "CAT2"}


# =============================================================================
# Unique Index Contract Tests
# =============================================================================


class TestTableUniqueIndexContract:
    """Tests that validate TableInterface unique index operations."""

    @pytest.mark.asyncio
    async def test_create_unique_index_enables_lookup(
        self, table: TableInterface[Any]
    ) -> None:
        """create_unique_index enables lookup by unique field."""
        await table.set("ui1", ContractTestModel(id="1", name="alice", category="A"))
        await table.create_unique_index("name")

        result = await table.get("alice", index="name")
        assert result is not None
        data = normalize_result(result)
        assert data["id"] == "1"

    @pytest.mark.asyncio
    async def test_unique_index_allows_update_same_key(
        self, table: TableInterface[Any]
    ) -> None:
        """Unique index allows updating same key with same unique value."""
        await table.create_unique_index("name")
        await table.set("us1", ContractTestModel(id="1", name="bob", category="A"))
        await table.set("us1", ContractTestModel(id="1", name="bob", category="B"))

        result = await table.get("us1")
        data = normalize_result(result)
        assert data["category"] == "B"

    @pytest.mark.asyncio
    async def test_unique_index_cleanup_on_delete(
        self, table: TableInterface[Any]
    ) -> None:
        """Unique index entry removed when record deleted."""
        await table.create_unique_index("name")
        await table.set("ud1", ContractTestModel(id="1", name="charlie", category="A"))

        await table.delete("ud1")

        # Now should be able to insert same unique value with different key
        await table.set("ud2", ContractTestModel(id="2", name="charlie", category="B"))
        assert await table.count() == 1

    @pytest.mark.asyncio
    async def test_create_unique_index_fails_on_duplicates(
        self, table: TableInterface[Any]
    ) -> None:
        """Creating unique index fails if duplicates already exist."""
        await table.set("uf1", ContractTestModel(id="1", name="dup", category="A"))
        await table.set("uf2", ContractTestModel(id="2", name="dup", category="B"))

        with pytest.raises(ValueError, match="[Dd]uplicate"):
            await table.create_unique_index("name")


# =============================================================================
# Concurrency Contract Tests
# =============================================================================


class TestTableConcurrencyContract:
    """Tests that validate concurrent access behavior."""

    @pytest.mark.asyncio
    async def test_concurrent_reads_succeed(self, table: TableInterface[Any]) -> None:
        """Multiple concurrent reads complete successfully."""
        await table.set("cr_key", ContractTestModel(id="cr", name="value"))

        async def reader() -> bool:
            result = await table.get("cr_key")
            return result is not None

        results = await asyncio.gather(*[reader() for _ in range(10)])
        assert all(results)

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_data_loss(
        self, table: TableInterface[Any]
    ) -> None:
        """Concurrent writes complete without data loss."""

        async def writer(i: int) -> None:
            await table.set(f"cw_{i}", ContractTestModel(id=str(i), name=f"item_{i}"))

        await asyncio.gather(*[writer(i) for i in range(20)])

        assert await table.count() == 20


# =============================================================================
# Feature Flag Consistency Tests
# =============================================================================


class TestFeatureFlagConsistency:
    """Tests that validate feature flag consistency."""

    @pytest.mark.asyncio
    async def test_inmemory_feature_flags(
        self, inmemory_datastore: DatastoreInterface
    ) -> None:
        """InMemoryDatastore has expected feature flags."""
        assert inmemory_datastore.has_persistence is False
        assert inmemory_datastore.has_transactions is False
        assert inmemory_datastore.is_relational is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.postgres
    async def test_postgres_feature_flags(
        self, postgres_datastore: DatastoreInterface
    ) -> None:
        """PostgresDatastore has expected feature flags."""
        if postgres_datastore is None:
            pytest.skip("PostgreSQL not available")
        assert postgres_datastore.has_persistence is True
        assert postgres_datastore.has_transactions is True
        assert postgres_datastore.is_relational is True
