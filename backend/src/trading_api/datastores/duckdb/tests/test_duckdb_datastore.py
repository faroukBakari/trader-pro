"""Tests for DuckDBDatastore and DuckDBTable."""

import asyncio
from typing import cast

import duckdb
import pytest
from sqlmodel import Field, SQLModel

from trading_api.datastores.duckdb import DuckDBDatastore
from trading_api.shared import TableInterface


class SampleModel(SQLModel):
    """Test model for datastore operations."""

    id: str = Field(primary_key=True)
    name: str
    category: str = "default"


class IndexedModel(SQLModel):
    """Test model with declarative index on category field."""

    id: str = Field(primary_key=True)
    name: str
    category: str = Field(default="default", index=True)


class UniqueIndexedModel(SQLModel):
    """Test model with declarative unique index on name field."""

    id: str = Field(primary_key=True)
    name: str = Field(index=True, unique=True)
    category: str = "default"


class AnotherModel(SQLModel):
    """Another test model for table isolation tests."""

    key: str = Field(primary_key=True)
    data: str


@pytest.fixture
def datastore() -> DuckDBDatastore:
    """Create fresh in-memory DuckDB datastore for each test."""
    conn = duckdb.connect(":memory:")
    return DuckDBDatastore(conn)


@pytest.fixture
def table(datastore: DuckDBDatastore) -> TableInterface[SampleModel]:
    """Create fresh table for each test."""
    return datastore.table(SampleModel)


# =============================================================================
# CRUD Tests
# =============================================================================


@pytest.mark.asyncio
async def test_set_and_get(table: TableInterface[SampleModel]) -> None:
    """Basic store and retrieve."""
    model = SampleModel(id="1", name="test")
    await table.set("1", model)

    result = await table.get("1")
    assert result is not None
    assert isinstance(result, SampleModel)
    assert result.name == "test"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(table: TableInterface[SampleModel]) -> None:
    """Get non-existent key returns None."""
    result = await table.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_delete_existing_returns_true(table: TableInterface[SampleModel]) -> None:
    """Delete existing key returns True."""
    await table.set("1", SampleModel(id="1", name="test"))

    deleted = await table.delete("1")
    assert deleted is True
    assert await table.get("1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(
    table: TableInterface[SampleModel],
) -> None:
    """Delete non-existent key returns False."""
    deleted = await table.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_exists_returns_expected(table: TableInterface[SampleModel]) -> None:
    """Exists returns correct boolean."""
    assert await table.exists("1") is False

    await table.set("1", SampleModel(id="1", name="test"))
    assert await table.exists("1") is True


@pytest.mark.asyncio
async def test_keys_and_values(table: TableInterface[SampleModel]) -> None:
    """Keys and values return all entries."""
    await table.set("a", SampleModel(id="a", name="alpha"))
    await table.set("b", SampleModel(id="b", name="beta"))

    keys = await table.keys()
    assert set(keys) == {"a", "b"}

    values = await table.values()
    assert len(values) == 2
    names = {v.name for v in values}
    assert names == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_clear_removes_all(table: TableInterface[SampleModel]) -> None:
    """Clear removes all entries."""
    await table.set("a", SampleModel(id="a", name="alpha"))
    await table.set("b", SampleModel(id="b", name="beta"))

    await table.clear()

    assert await table.count() == 0
    assert await table.keys() == []


@pytest.mark.asyncio
async def test_count_returns_entry_count(table: TableInterface[SampleModel]) -> None:
    """Count returns correct number of entries."""
    assert await table.count() == 0

    await table.set("1", SampleModel(id="1", name="one"))
    assert await table.count() == 1

    await table.set("2", SampleModel(id="2", name="two"))
    assert await table.count() == 2


@pytest.mark.asyncio
async def test_is_empty(table: TableInterface[SampleModel]) -> None:
    """is_empty returns correct boolean."""
    assert await table.is_empty is True

    await table.set("1", SampleModel(id="1", name="test"))
    assert await table.is_empty is False


@pytest.mark.asyncio
async def test_iterate_yields_all_pairs(table: TableInterface[SampleModel]) -> None:
    """Iterate yields all key-value pairs."""
    await table.set("a", SampleModel(id="a", name="alpha"))
    await table.set("b", SampleModel(id="b", name="beta"))

    pairs = [(k, v) async for k, v in table.iterate()]

    assert len(pairs) == 2
    keys = {k for k, _ in pairs}
    assert keys == {"a", "b"}


@pytest.mark.asyncio
async def test_set_overwrites_existing(table: TableInterface[SampleModel]) -> None:
    """set() overwrites existing value for same key."""
    await table.set("1", SampleModel(id="1", name="old"))
    await table.set("1", SampleModel(id="1", name="new"))

    result = await table.get("1")
    assert result is not None
    assert result.name == "new"
    assert await table.count() == 1


@pytest.mark.asyncio
async def test_get_all(table: TableInterface[SampleModel]) -> None:
    """get_all returns list of matching records."""
    await table.set("1", SampleModel(id="1", name="test"))

    results = await table.get_all("1")
    assert len(results) == 1
    assert results[0].name == "test"

    # Non-existent returns empty list
    results = await table.get_all("nonexistent")
    assert results == []


# =============================================================================
# Declarative Indexing Tests (Field(index=True))
# =============================================================================


@pytest.mark.asyncio
async def test_field_index_enables_secondary_lookup(
    datastore: DuckDBDatastore,
) -> None:
    """Field(index=True) enables lookup by indexed field value."""
    table = datastore.table(IndexedModel)
    await table.set("1", IndexedModel(id="1", name="test", category="A"))

    result = await table.get("A", index="category")
    assert result is not None
    assert result.id == "1"


@pytest.mark.asyncio
async def test_field_index_get_returns_correct_record(
    datastore: DuckDBDatastore,
) -> None:
    """Get by declarative index returns the correct record."""
    table = datastore.table(IndexedModel)
    await table.set("1", IndexedModel(id="1", name="first", category="X"))
    await table.set("2", IndexedModel(id="2", name="second", category="Y"))

    result = await table.get("Y", index="category")
    assert result is not None
    assert result.name == "second"


@pytest.mark.asyncio
async def test_field_index_delete_by_index_removes_record(
    datastore: DuckDBDatastore,
) -> None:
    """Delete by declarative index removes the correct record."""
    table = datastore.table(IndexedModel)
    await table.set("1", IndexedModel(id="1", name="test", category="Z"))

    deleted = await table.delete("Z", index="category")
    assert deleted is True
    assert await table.get("1") is None


@pytest.mark.asyncio
async def test_field_index_updates_on_overwrite(
    datastore: DuckDBDatastore,
) -> None:
    """Set auto-updates declarative index when overwriting with different value."""
    table = datastore.table(IndexedModel)
    await table.set("1", IndexedModel(id="1", name="old", category="A"))

    # Overwrite with new category
    await table.set("1", IndexedModel(id="1", name="new", category="B"))

    # Old index should not find it
    assert await table.get("A", index="category") is None
    # New index should find it
    result = await table.get("B", index="category")
    assert result is not None
    assert result.name == "new"


@pytest.mark.asyncio
async def test_field_index_keys_returns_indexed_values(
    datastore: DuckDBDatastore,
) -> None:
    """Keys with declarative index returns indexed field values."""
    table = datastore.table(IndexedModel)
    await table.set("1", IndexedModel(id="1", name="a", category="X"))
    await table.set("2", IndexedModel(id="2", name="b", category="Y"))

    indexed_keys = await table.keys(index="category")
    assert set(indexed_keys) == {"X", "Y"}


@pytest.mark.asyncio
async def test_get_all_by_index(datastore: DuckDBDatastore) -> None:
    """get_all with index returns all matching records."""
    table = datastore.table(IndexedModel)
    await table.set("1", IndexedModel(id="1", name="a", category="X"))
    await table.set("2", IndexedModel(id="2", name="b", category="X"))
    await table.set("3", IndexedModel(id="3", name="c", category="Y"))

    results = await table.get_all("X", index="category")
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"a", "b"}


# =============================================================================
# Declarative Unique Index Tests (Field(unique=True))
# =============================================================================


@pytest.mark.asyncio
async def test_field_unique_enables_lookup(
    datastore: DuckDBDatastore,
) -> None:
    """Field(unique=True) enables lookup by unique field value."""
    table = datastore.table(UniqueIndexedModel)
    await table.set("1", UniqueIndexedModel(id="1", name="alice", category="A"))

    result = await table.get("alice", index="name")
    assert result is not None
    assert result.id == "1"


@pytest.mark.asyncio
async def test_field_unique_rejects_duplicate_on_insert(
    datastore: DuckDBDatastore,
) -> None:
    """Field(unique=True) rejects insert with duplicate field value."""
    table = datastore.table(UniqueIndexedModel)
    await table.set("1", UniqueIndexedModel(id="1", name="alice", category="A"))

    with pytest.raises(ValueError, match="Duplicate value 'alice'"):
        await table.set("2", UniqueIndexedModel(id="2", name="alice", category="B"))

    # Original should still exist
    assert await table.count() == 1


@pytest.mark.asyncio
async def test_field_unique_allows_update_same_key(
    datastore: DuckDBDatastore,
) -> None:
    """Field(unique=True) allows updating same record with same unique value."""
    table = datastore.table(UniqueIndexedModel)
    await table.set("1", UniqueIndexedModel(id="1", name="alice", category="A"))

    # Update same key with same name should work
    await table.set("1", UniqueIndexedModel(id="1", name="alice", category="B"))

    result = await table.get("1")
    assert result is not None
    assert result.category == "B"


@pytest.mark.asyncio
async def test_field_unique_cleanup_on_delete(
    datastore: DuckDBDatastore,
) -> None:
    """Unique index entry is removed when record is deleted."""
    table = datastore.table(UniqueIndexedModel)
    await table.set("1", UniqueIndexedModel(id="1", name="alice", category="A"))

    await table.delete("1")

    # Now should be able to insert same unique value with different key
    await table.set("2", UniqueIndexedModel(id="2", name="alice", category="B"))
    assert await table.count() == 1


# =============================================================================
# Concurrency Tests
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_reads_allowed(table: TableInterface[SampleModel]) -> None:
    """Multiple concurrent reads should not block each other."""
    await table.set("k", SampleModel(id="k", name="value"))

    async def reader() -> SampleModel | None:
        result = await table.get("k")
        return SampleModel.model_validate(result) if result is not None else None

    results = await asyncio.gather(*[reader() for _ in range(10)])
    assert all(r is not None and r.name == "value" for r in results)


@pytest.mark.asyncio
async def test_concurrent_writes_serialized(
    table: TableInterface[SampleModel],
) -> None:
    """Concurrent writes should be serialized without corruption."""

    async def writer(i: int) -> None:
        await table.set(str(i), SampleModel(id=str(i), name=f"item_{i}"))

    await asyncio.gather(*[writer(i) for i in range(20)])
    assert await table.count() == 20


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_datastore_table_retrieval(datastore: DuckDBDatastore) -> None:
    """Datastore returns same table instance for same model class."""
    table1 = datastore.table(SampleModel)
    table2 = datastore.table(SampleModel)

    assert table1 is table2

    # Different model classes get different tables
    table3 = datastore.table(AnotherModel)
    assert table3 is not table1


@pytest.mark.asyncio
async def test_datastore_capabilities(datastore: DuckDBDatastore) -> None:
    """DuckDB has timeseries capability."""
    assert datastore.has_capability("timeseries") is True
    assert datastore.has_capability("persistence") is False
    assert datastore.has_capability("transactions") is False


@pytest.mark.asyncio
async def test_datastore_name() -> None:
    """DuckDBDatastore.datastore_name() returns 'duckdb'."""
    assert DuckDBDatastore.datastore_name() == "duckdb"


# =============================================================================
# Datastore-Level Operations
# =============================================================================


@pytest.mark.asyncio
async def test_list_tables(datastore: DuckDBDatastore) -> None:
    """list_tables returns created table names."""
    assert await datastore.list_tables() == []

    datastore.table(SampleModel)
    tables = await datastore.list_tables()
    assert "samplemodel" in tables


@pytest.mark.asyncio
async def test_list_tables_with_prefix(datastore: DuckDBDatastore) -> None:
    """list_tables filters by prefix."""
    datastore.table(SampleModel)
    datastore.table(AnotherModel)

    tables = await datastore.list_tables(prefix="sample")
    assert "samplemodel" in tables
    assert "anothermodel" not in tables


@pytest.mark.asyncio
async def test_drop_table_existing(datastore: DuckDBDatastore) -> None:
    """drop_table returns True for existing table."""
    datastore.table(SampleModel)
    dropped = await datastore.drop_table("samplemodel")
    assert dropped is True

    # Table should no longer exist
    tables = await datastore.list_tables()
    assert "samplemodel" not in tables


@pytest.mark.asyncio
async def test_drop_table_nonexistent(datastore: DuckDBDatastore) -> None:
    """drop_table returns False for non-existent table."""
    dropped = await datastore.drop_table("nonexistent_table")
    assert dropped is False


@pytest.mark.asyncio
async def test_drop_table_allows_recreation(datastore: DuckDBDatastore) -> None:
    """After drop, table can be recreated fresh."""
    table = datastore.table(SampleModel)
    await table.set("k", SampleModel(id="1", name="old"))

    await datastore.drop_table("samplemodel")

    # Recreate and verify it's fresh
    table2 = datastore.table(SampleModel)
    assert await table2.count() == 0


# =============================================================================
# Factory & Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_factory_default() -> None:
    """create() factory returns a working DuckDBDatastore."""
    ds = await DuckDBDatastore.create()
    table = ds.table(SampleModel)
    await table.set("1", SampleModel(id="1", name="test"))
    assert await table.get("1") is not None
    await ds.close()


@pytest.mark.asyncio
async def test_exclusion_constraint_rejected(datastore: DuckDBDatastore) -> None:
    """Models with exclusion constraints raise NotImplementedError."""

    class ExclusionModel(SQLModel):
        id: str = Field(primary_key=True)
        name: str
        __table_args__ = {"info": {"exclusion": "some_constraint"}}

    with pytest.raises(NotImplementedError, match="exclusion constraints"):
        datastore.table(ExclusionModel)


@pytest.mark.asyncio
async def test_invalid_index_column_rejected(
    table: TableInterface[SampleModel],
) -> None:
    """Passing an unknown column as index raises ValueError."""
    await table.set("1", SampleModel(id="1", name="test"))

    with pytest.raises(ValueError, match="Unknown index column"):
        await table.get("1", index="nonexistent_column")

    with pytest.raises(ValueError, match="Unknown index column"):
        await table.delete("1", index="nonexistent_column")

    with pytest.raises(ValueError, match="Unknown index column"):
        await table.exists("1", index="nonexistent_column")

    with pytest.raises(ValueError, match="Unknown index column"):
        await table.keys(index="nonexistent_column")


# =============================================================================
# TimeSeriesTable Tests
# =============================================================================


class TimeSeriesModel(SQLModel):
    """Test model for timeseries operations."""

    time: int = Field(primary_key=True)
    value: float


class NoPrimaryKeyModel(SQLModel):
    """Model without primary_key for validation test."""

    name: str
    value: float


@pytest.mark.asyncio
async def test_timeseries_set_batch_and_get_range(
    datastore: DuckDBDatastore,
) -> None:
    """set_batch stores items and get_time_range retrieves by range."""
    ts_table = datastore.timeseries_table(TimeSeriesModel)

    items = [
        TimeSeriesModel(time=100, value=1.0),
        TimeSeriesModel(time=200, value=2.0),
        TimeSeriesModel(time=300, value=3.0),
        TimeSeriesModel(time=400, value=4.0),
    ]
    await ts_table.set_batch(items)

    # Query a subset
    results = await ts_table.get_time_range(150, 350)
    assert len(results) == 2
    assert cast(TimeSeriesModel, results[0]).time == 200
    assert cast(TimeSeriesModel, results[1]).time == 300

    # Query all
    results = await ts_table.get_time_range(100, 400)
    assert len(results) == 4


@pytest.mark.asyncio
async def test_timeseries_get_range_empty(
    datastore: DuckDBDatastore,
) -> None:
    """get_time_range on empty table returns empty list."""
    ts_table = datastore.timeseries_table(TimeSeriesModel)

    results = await ts_table.get_time_range(0, 9999)
    assert results == []


@pytest.mark.asyncio
async def test_timeseries_set_batch_returns_new_count(
    datastore: DuckDBDatastore,
) -> None:
    """set_batch returns count of NEW inserts, not updates."""
    ts_table = datastore.timeseries_table(TimeSeriesModel)

    # First batch: all new
    items = [
        TimeSeriesModel(time=100, value=1.0),
        TimeSeriesModel(time=200, value=2.0),
    ]
    new_count = await ts_table.set_batch(items)
    assert new_count == 2

    # Second batch: 1 update + 1 new
    items2 = [
        TimeSeriesModel(time=200, value=2.5),  # update existing
        TimeSeriesModel(time=300, value=3.0),  # new
    ]
    new_count = await ts_table.set_batch(items2)
    assert new_count == 1

    # Verify updated value
    results = await ts_table.get_time_range(200, 200)
    assert len(results) == 1
    assert cast(TimeSeriesModel, results[0]).value == 2.5


@pytest.mark.asyncio
async def test_timeseries_set_batch_empty(
    datastore: DuckDBDatastore,
) -> None:
    """set_batch with empty list returns 0."""
    ts_table = datastore.timeseries_table(TimeSeriesModel)
    assert await ts_table.set_batch([]) == 0


@pytest.mark.asyncio
async def test_timeseries_table_requires_primary_key(
    datastore: DuckDBDatastore,
) -> None:
    """timeseries_table raises ValueError if model has no primary key."""
    with pytest.raises(ValueError, match="requires Field\\(primary_key=True\\)"):
        datastore.timeseries_table(NoPrimaryKeyModel)


@pytest.mark.asyncio
async def test_table_then_timeseries_table_raises_type_error(
    datastore: DuckDBDatastore,
) -> None:
    """Creating plain table then timeseries_table for same model raises TypeError."""
    datastore.table(TimeSeriesModel)

    with pytest.raises(TypeError, match="already exists as DuckDBTable"):
        datastore.timeseries_table(TimeSeriesModel)


@pytest.mark.asyncio
async def test_timeseries_get_range_inverted_returns_empty(
    datastore: DuckDBDatastore,
) -> None:
    """get_time_range with from_time > to_time returns empty list."""
    ts_table = datastore.timeseries_table(TimeSeriesModel)
    await ts_table.set_batch([TimeSeriesModel(time=100, value=1.0)])

    results = await ts_table.get_time_range(200, 50)
    assert results == []


@pytest.mark.asyncio
async def test_capabilities_includes_timeseries(datastore: DuckDBDatastore) -> None:
    """DuckDB capabilities include timeseries."""
    caps = datastore.capabilities()
    cap_names = [c.name for c in caps]
    assert "timeseries" in cap_names
