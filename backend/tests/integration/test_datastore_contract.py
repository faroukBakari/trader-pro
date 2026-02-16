"""Datastore Contract Tests - validates all DatastoreInterface implementations.

These tests ensure every datastore implementation conforms to the DatastoreInterface
contract. Tests are parametrized to run against DuckDB and Postgres datastores.

[ARCHITECTURE] DRY principle: Common behavior tested once, implementation-specific
tests focus only on unique features (e.g., psycopg UniqueViolation, connection pools).

Run with:
- All datastores: pytest tests/integration/test_datastore_contract.py -v
- DuckDB only: pytest tests/integration/test_datastore_contract.py -v -k duckdb
- Postgres only: pytest tests/integration/test_datastore_contract.py -v -k postgres -m integration
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, cast

import duckdb
import pytest
from sqlmodel import Field, SQLModel

from trading_api.datastores import DuckDBDatastore
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import (
    DatastoreInterface,
    TableInterface,
    TimeSeriesTableInterface,
)

# =============================================================================
# Test Models
# =============================================================================


class ContractTestModel(SQLModel, table=True):
    """Standard test model for CRUD operations."""

    __tablename__ = cast(Any, "contract_test_model")

    id: str = Field(primary_key=True)
    name: str
    category: str = "default"


class IndexedContractModel(SQLModel, table=True):
    """Model with declarative index for index contract tests."""

    __tablename__ = cast(Any, "indexed_contract_model")

    id: str = Field(primary_key=True)
    name: str
    category: str = Field(default="default", index=True)


class UniqueIndexedContractModel(SQLModel, table=True):
    """Model with declarative unique index for unique index contract tests."""

    __tablename__ = cast(Any, "unique_indexed_contract_model")

    id: str = Field(primary_key=True)
    name: str = Field(unique=True)
    category: str = "default"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def duckdb_datastore() -> AsyncIterator[DatastoreInterface]:
    """DuckDBDatastore fixture using in-memory database."""
    conn = duckdb.connect(":memory:")
    ds = DuckDBDatastore(conn)
    yield ds
    await ds.close()


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
        pytest.param("duckdb", id="duckdb", marks=[pytest.mark.integration]),
        pytest.param(
            "postgres",
            id="postgres",
            marks=[pytest.mark.integration, pytest.mark.postgres],
        ),
    ]
)
async def any_datastore(
    request: pytest.FixtureRequest,
    duckdb_datastore: DatastoreInterface,
    postgres_datastore: DatastoreInterface | None,
) -> AsyncIterator[DatastoreInterface]:
    """Parametrized fixture providing each datastore implementation.

    All variants require @pytest.mark.integration marker.
    Postgres additionally has @pytest.mark.postgres for selective runs.
    """
    if request.param == "duckdb":
        yield duckdb_datastore
    elif request.param == "postgres":
        if postgres_datastore is None:
            pytest.skip("PostgreSQL not available")
        yield postgres_datastore


@pytest.fixture
async def table(
    any_datastore: DatastoreInterface,
) -> AsyncIterator[TableInterface[Any]]:
    """Table fixture with table drop/recreate for test isolation.

    Uses drop_table() before and after test to ensure clean state,
    including removal of any custom indexes created during the test.
    """
    table_name = cast(str, ContractTestModel.__tablename__)
    await any_datastore.drop_table(table_name)
    tbl = any_datastore.table(ContractTestModel)
    yield tbl
    await any_datastore.drop_table(table_name)


@pytest.fixture
async def indexed_table(
    any_datastore: DatastoreInterface,
) -> AsyncIterator[TableInterface[Any]]:
    """Table with Field(index=True) on category for index contract tests."""
    table_name = cast(str, IndexedContractModel.__tablename__)
    await any_datastore.drop_table(table_name)
    tbl = any_datastore.table(IndexedContractModel)
    yield tbl
    await any_datastore.drop_table(table_name)


@pytest.fixture
async def unique_indexed_table(
    any_datastore: DatastoreInterface,
) -> AsyncIterator[TableInterface[Any]]:
    """Table with Field(unique=True) on name for unique index contract tests."""
    table_name = cast(str, UniqueIndexedContractModel.__tablename__)
    await any_datastore.drop_table(table_name)
    tbl = any_datastore.table(UniqueIndexedContractModel)
    yield tbl
    await any_datastore.drop_table(table_name)


# =============================================================================
# DatastoreInterface Contract Tests
# =============================================================================


class TestDatastoreInterfaceContract:
    """Tests that validate DatastoreInterface implementation requirements."""

    @pytest.mark.asyncio
    async def test_has_capability_returns_bool(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """has_capability() returns boolean for any capability name."""
        assert isinstance(any_datastore.has_capability("persistence"), bool)
        assert isinstance(any_datastore.has_capability("transactions"), bool)
        assert isinstance(any_datastore.has_capability("unknown"), bool)
        assert any_datastore.has_capability("unknown") is False

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

    @pytest.mark.asyncio
    async def test_drop_table_returns_true_when_exists(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """drop_table() returns True when table exists."""
        table = any_datastore.table(ContractTestModel)
        # Actually create table by writing to it (postgres creates lazily)
        await table.set("test_key", ContractTestModel(id="1", name="test"))
        table_name = cast(str, ContractTestModel.__tablename__)

        dropped = await any_datastore.drop_table(table_name)
        assert dropped is True

    @pytest.mark.asyncio
    async def test_drop_table_returns_false_when_not_exists(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """drop_table() returns False when table doesn't exist."""
        dropped = await any_datastore.drop_table("nonexistent_table_contract_test")
        assert dropped is False

    @pytest.mark.asyncio
    async def test_drop_table_allows_recreation(
        self, any_datastore: DatastoreInterface
    ) -> None:
        """After drop_table(), table can be recreated fresh."""
        table1 = any_datastore.table(ContractTestModel)
        await table1.set("k", ContractTestModel(id="1", name="old"))
        table_name = cast(str, ContractTestModel.__tablename__)

        await any_datastore.drop_table(table_name)

        # Recreate and verify it's fresh
        table2 = any_datastore.table(ContractTestModel)
        assert await table2.count() == 0


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
        assert result.name == "test"
        assert result.category == "A"

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
        names = {v.name for v in values}
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
    async def test_is_empty_true_when_no_entries(
        self, table: TableInterface[Any]
    ) -> None:
        """is_empty returns True for empty table."""
        assert await table.is_empty is True

    @pytest.mark.asyncio
    async def test_is_empty_false_when_has_entries(
        self, table: TableInterface[Any]
    ) -> None:
        """is_empty returns False when table has entries."""
        await table.set("k", ContractTestModel(id="1", name="test"))
        assert await table.is_empty is False

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
        assert result is not None
        assert result.name == "new"
        assert await table.count() == 1


# =============================================================================
# Index Contract Tests (Field(index=True))
# =============================================================================


class TestTableIndexContract:
    """Tests that validate TableInterface declarative index operations."""

    @pytest.mark.asyncio
    async def test_field_index_enables_lookup(
        self, indexed_table: TableInterface[Any]
    ) -> None:
        """Field(index=True) enables lookup by indexed field."""
        await indexed_table.set(
            "idx1", IndexedContractModel(id="idx1", name="test", category="X")
        )

        result = await indexed_table.get("X", index="category")
        assert result is not None
        assert result.id == "idx1"

    @pytest.mark.asyncio
    async def test_get_by_index_returns_correct_record(
        self, indexed_table: TableInterface[Any]
    ) -> None:
        """get with index returns correct record among multiple."""
        await indexed_table.set(
            "gi1", IndexedContractModel(id="1", name="first", category="A")
        )
        await indexed_table.set(
            "gi2", IndexedContractModel(id="2", name="second", category="B")
        )

        result = await indexed_table.get("B", index="category")
        assert result is not None
        assert result.name == "second"

    @pytest.mark.asyncio
    async def test_delete_by_index(self, indexed_table: TableInterface[Any]) -> None:
        """delete with index removes correct record."""
        await indexed_table.set(
            "di1", IndexedContractModel(id="1", name="target", category="Z")
        )

        deleted = await indexed_table.delete("Z", index="category")
        assert deleted is True
        assert await indexed_table.get("di1") is None

    @pytest.mark.asyncio
    async def test_index_updated_on_overwrite(
        self, indexed_table: TableInterface[Any]
    ) -> None:
        """Index is updated when record is overwritten with different value."""
        await indexed_table.set(
            "io1", IndexedContractModel(id="1", name="old", category="OLD")
        )
        await indexed_table.set(
            "io1", IndexedContractModel(id="1", name="new", category="NEW")
        )

        # Old index value should not find it
        assert await indexed_table.get("OLD", index="category") is None
        # New index value should find it
        result = await indexed_table.get("NEW", index="category")
        assert result is not None

    @pytest.mark.asyncio
    async def test_keys_with_index_returns_indexed_values(
        self, indexed_table: TableInterface[Any]
    ) -> None:
        """keys(index=...) returns distinct indexed field values."""
        await indexed_table.set(
            "ki1", IndexedContractModel(id="1", name="a", category="CAT1")
        )
        await indexed_table.set(
            "ki2", IndexedContractModel(id="2", name="b", category="CAT2")
        )

        indexed_keys = await indexed_table.keys(index="category")
        assert set(indexed_keys) == {"CAT1", "CAT2"}


# =============================================================================
# Unique Index Contract Tests (Field(unique=True))
# =============================================================================


class TestTableUniqueIndexContract:
    """Tests that validate TableInterface declarative unique index operations."""

    @pytest.mark.asyncio
    async def test_field_unique_enables_lookup(
        self, unique_indexed_table: TableInterface[Any]
    ) -> None:
        """Field(unique=True) enables lookup by unique field."""
        await unique_indexed_table.set(
            "ui1", UniqueIndexedContractModel(id="ui1", name="alice", category="A")
        )

        result = await unique_indexed_table.get("alice", index="name")
        assert result is not None
        assert result.id == "ui1"

    @pytest.mark.asyncio
    async def test_unique_index_allows_update_same_key(
        self, unique_indexed_table: TableInterface[Any]
    ) -> None:
        """Unique index allows updating same key with same unique value."""
        await unique_indexed_table.set(
            "us1", UniqueIndexedContractModel(id="1", name="bob", category="A")
        )
        await unique_indexed_table.set(
            "us1", UniqueIndexedContractModel(id="1", name="bob", category="B")
        )

        result = await unique_indexed_table.get("us1")
        assert result is not None
        assert result.category == "B"

    @pytest.mark.asyncio
    async def test_unique_index_cleanup_on_delete(
        self, unique_indexed_table: TableInterface[Any]
    ) -> None:
        """Unique index entry removed when record deleted."""
        await unique_indexed_table.set(
            "ud1", UniqueIndexedContractModel(id="1", name="charlie", category="A")
        )

        await unique_indexed_table.delete("ud1")

        # Now should be able to insert same unique value with different key
        await unique_indexed_table.set(
            "ud2", UniqueIndexedContractModel(id="2", name="charlie", category="B")
        )
        assert await unique_indexed_table.count() == 1


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
    """Tests that validate feature flag consistency via capabilities()."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_duckdb_feature_flags(
        self, duckdb_datastore: DatastoreInterface
    ) -> None:
        """DuckDBDatastore has timeseries but no persistence/transactions."""
        assert duckdb_datastore.has_capability("timeseries") is True
        assert duckdb_datastore.has_capability("persistence") is False
        assert duckdb_datastore.has_capability("transactions") is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.postgres
    async def test_postgres_feature_flags(
        self, postgres_datastore: DatastoreInterface
    ) -> None:
        """PostgresDatastore has expected capabilities (all)."""
        if postgres_datastore is None:
            pytest.skip("PostgreSQL not available")
        assert postgres_datastore.has_capability("persistence") is True
        assert postgres_datastore.has_capability("transactions") is True


# =============================================================================
# Timeseries Contract Tests
# =============================================================================


class TimeSeriesContractModel(SQLModel, table=True):
    """Test model for timeseries contract tests."""

    __tablename__ = cast(Any, "timeseries_contract_model")

    time: int = Field(primary_key=True)
    value: float


@pytest.fixture(
    params=[
        pytest.param("duckdb", id="duckdb", marks=[pytest.mark.integration]),
        pytest.param(
            "postgres",
            id="postgres",
            marks=[pytest.mark.integration, pytest.mark.postgres],
        ),
    ]
)
async def timeseries_datastore(
    request: pytest.FixtureRequest,
    duckdb_datastore: DatastoreInterface,
    postgres_datastore: DatastoreInterface | None,
) -> AsyncIterator[DatastoreInterface]:
    """Parametrized fixture for datastores with timeseries capability."""
    if request.param == "duckdb":
        yield duckdb_datastore
    elif request.param == "postgres":
        if postgres_datastore is None:
            pytest.skip("PostgreSQL not available")
        yield postgres_datastore


@pytest.fixture
async def ts_table(
    timeseries_datastore: DatastoreInterface,
) -> AsyncIterator[TimeSeriesTableInterface[Any]]:
    """Timeseries table fixture with drop/recreate for test isolation.

    Mirrors the `table` fixture pattern: drops before and after each test
    to ensure no leftover data from previous tests.
    """
    table_name = cast(str, TimeSeriesContractModel.__tablename__)
    await timeseries_datastore.drop_table(table_name)
    ts = timeseries_datastore.timeseries_table(TimeSeriesContractModel)
    yield ts
    await timeseries_datastore.drop_table(table_name)


class TestTimeSeriesContract:
    """Contract tests for TimeSeriesTableInterface implementations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_set_batch_returns_new_insert_count(
        self, ts_table: TimeSeriesTableInterface[Any]
    ) -> None:
        """set_batch returns count of NEW inserts, not updates."""
        # First batch: all new
        items = [
            TimeSeriesContractModel(time=100, value=1.0),
            TimeSeriesContractModel(time=200, value=2.0),
        ]
        assert await ts_table.set_batch(items) == 2

        # Second batch: 1 update + 1 new
        items2 = [
            TimeSeriesContractModel(time=200, value=2.5),
            TimeSeriesContractModel(time=300, value=3.0),
        ]
        assert await ts_table.set_batch(items2) == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_set_batch_empty_returns_zero(
        self, ts_table: TimeSeriesTableInterface[Any]
    ) -> None:
        """set_batch with empty list returns 0."""
        assert await ts_table.set_batch([]) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_time_range_inclusive_bounds_ordered(
        self, ts_table: TimeSeriesTableInterface[Any]
    ) -> None:
        """get_time_range uses inclusive bounds and returns ascending order."""
        items = [
            TimeSeriesContractModel(time=100, value=1.0),
            TimeSeriesContractModel(time=200, value=2.0),
            TimeSeriesContractModel(time=300, value=3.0),
            TimeSeriesContractModel(time=400, value=4.0),
        ]
        await ts_table.set_batch(items)

        results = await ts_table.get_time_range(200, 300)
        assert len(results) == 2
        assert results[0].time == 200
        assert results[1].time == 300

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_time_range_empty_table(
        self, ts_table: TimeSeriesTableInterface[Any]
    ) -> None:
        """get_time_range on empty table returns empty list."""
        assert await ts_table.get_time_range(0, 9999) == []

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_set_batch_upsert_overwrites_value(
        self, ts_table: TimeSeriesTableInterface[Any]
    ) -> None:
        """set_batch with existing key updates the value."""
        await ts_table.set_batch([TimeSeriesContractModel(time=100, value=1.0)])
        await ts_table.set_batch([TimeSeriesContractModel(time=100, value=9.9)])

        results = await ts_table.get_time_range(100, 100)
        assert len(results) == 1
        assert results[0].value == 9.9

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_timeseries_table_is_timeseries_interface(
        self, ts_table: TimeSeriesTableInterface[Any]
    ) -> None:
        """timeseries_table returns a TimeSeriesTableInterface instance."""
        assert isinstance(ts_table, TimeSeriesTableInterface)
