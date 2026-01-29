"""Tests for InMemoryDatastore and InMemoryTable."""

import asyncio

import pytest
from sqlmodel import SQLModel

from trading_api.datastores.inmemory import InMemoryDatastore, InMemoryTable
from trading_api.shared import DatastoreInterface, TableInterface


class SampleModel(SQLModel):
    """Test model for datastore operations."""

    id: str
    name: str
    category: str = "default"


class AnotherModel(SQLModel):
    """Another test model for table isolation tests."""

    key: str
    data: str


@pytest.fixture
def table() -> TableInterface[SampleModel]:
    """Create fresh table for each test."""
    return InMemoryTable(timeout=1.0)


@pytest.fixture
def datastore() -> DatastoreInterface:
    """Create fresh datastore for each test."""
    return InMemoryDatastore(timeout=1.0)


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
async def test_iterate_yields_all_pairs(table: TableInterface[SampleModel]) -> None:
    """Iterate yields all key-value pairs."""
    await table.set("a", SampleModel(id="a", name="alpha"))
    await table.set("b", SampleModel(id="b", name="beta"))

    pairs = [(k, v) async for k, v in table.iterate()]

    assert len(pairs) == 2
    keys = {k for k, _ in pairs}
    assert keys == {"a", "b"}


# =============================================================================
# Indexing Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_index_enables_secondary_lookup(
    table: TableInterface[SampleModel],
) -> None:
    """Index allows lookup by field value."""
    await table.set("1", SampleModel(id="1", name="test", category="A"))
    await table.create_index("category")

    # Lookup by indexed field
    result = await table.get("A", index="category")
    assert result is not None
    assert result.id == "1"


@pytest.mark.asyncio
async def test_get_by_index_returns_correct_record(
    table: TableInterface[SampleModel],
) -> None:
    """Get by index returns the correct record."""
    await table.set("1", SampleModel(id="1", name="first", category="X"))
    await table.set("2", SampleModel(id="2", name="second", category="Y"))
    await table.create_index("category")

    result = await table.get("Y", index="category")
    assert result is not None
    assert result.name == "second"


@pytest.mark.asyncio
async def test_delete_by_index_removes_record(
    table: TableInterface[SampleModel],
) -> None:
    """Delete by index removes the correct record."""
    await table.set("1", SampleModel(id="1", name="test", category="Z"))
    await table.create_index("category")

    deleted = await table.delete("Z", index="category")
    assert deleted is True
    assert await table.get("1") is None


@pytest.mark.asyncio
async def test_set_with_index_updates_on_overwrite(
    table: TableInterface[SampleModel],
) -> None:
    """Set auto-updates index when overwriting with different field value."""
    await table.create_index("category")
    await table.set("1", SampleModel(id="1", name="old", category="A"))

    # Overwrite with new category
    await table.set("1", SampleModel(id="1", name="new", category="B"))

    # Old index should not find it
    assert await table.get("A", index="category") is None
    # New index should find it
    result = await table.get("B", index="category")
    assert result is not None
    assert result.name == "new"


@pytest.mark.asyncio
async def test_keys_with_index_returns_indexed_values(
    table: TableInterface[SampleModel],
) -> None:
    """Keys with index returns indexed field values."""
    await table.create_index("category")
    await table.set("1", SampleModel(id="1", name="a", category="X"))
    await table.set("2", SampleModel(id="2", name="b", category="Y"))

    indexed_keys = await table.keys(index="category")
    assert set(indexed_keys) == {"X", "Y"}


# =============================================================================
# Unique Index Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_unique_index_enables_lookup(
    table: TableInterface[SampleModel],
) -> None:
    """Unique index allows lookup by field value."""
    await table.set("1", SampleModel(id="1", name="alice", category="A"))
    await table.create_unique_index("name")

    result = await table.get("alice", index="name")
    assert result is not None
    assert result.id == "1"


@pytest.mark.asyncio
async def test_unique_index_rejects_duplicate_on_insert(
    table: TableInterface[SampleModel],
) -> None:
    """Unique index rejects insert with duplicate field value."""
    await table.create_unique_index("name")
    await table.set("1", SampleModel(id="1", name="alice", category="A"))

    # Should raise ValueError for duplicate name
    with pytest.raises(ValueError, match="Duplicate value 'alice'"):
        await table.set("2", SampleModel(id="2", name="alice", category="B"))

    # Original should still exist
    assert await table.count() == 1


@pytest.mark.asyncio
async def test_unique_index_allows_update_same_key(
    table: TableInterface[SampleModel],
) -> None:
    """Unique index allows updating same record with same unique value."""
    await table.create_unique_index("name")
    await table.set("1", SampleModel(id="1", name="alice", category="A"))

    # Update same key with same name should work
    await table.set("1", SampleModel(id="1", name="alice", category="B"))

    result = await table.get("1")
    assert result is not None
    assert result.category == "B"


@pytest.mark.asyncio
async def test_unique_index_cleanup_on_delete(
    table: TableInterface[SampleModel],
) -> None:
    """Unique index entry is removed when record is deleted."""
    await table.create_unique_index("name")
    await table.set("1", SampleModel(id="1", name="alice", category="A"))

    await table.delete("1")

    # Now should be able to insert same unique value with different key
    await table.set("2", SampleModel(id="2", name="alice", category="B"))
    assert await table.count() == 1


@pytest.mark.asyncio
async def test_create_unique_index_fails_if_duplicates_exist(
    table: TableInterface[SampleModel],
) -> None:
    """Creating unique index fails if data already has duplicate values."""
    await table.set("1", SampleModel(id="1", name="alice", category="A"))
    await table.set("2", SampleModel(id="2", name="alice", category="B"))

    with pytest.raises(ValueError, match="Duplicate value 'alice'"):
        await table.create_unique_index("name")


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

    # Launch 10 concurrent reads - should complete quickly
    results = await asyncio.gather(*[reader() for _ in range(10)])
    assert all(r is not None and r.name == "value" for r in results)


@pytest.mark.asyncio
async def test_concurrent_writes_serialized(table: TableInterface[SampleModel]) -> None:
    """Concurrent writes should be serialized without corruption."""
    counter = {"value": 0}

    async def writer(i: int) -> None:
        await table.set(str(i), SampleModel(id=str(i), name=f"item_{i}"))
        counter["value"] += 1

    # Launch 20 concurrent writes
    await asyncio.gather(*[writer(i) for i in range(20)])

    # All writes should have completed
    assert await table.count() == 20
    assert counter["value"] == 20


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_model_copy_isolation(table: TableInterface[SampleModel]) -> None:
    """Returned models are copies, not references to internal storage."""
    original = SampleModel(id="1", name="original")
    await table.set("1", original)

    retrieved = await table.get("1")
    assert retrieved is not None
    assert retrieved is not original  # Different object


@pytest.mark.asyncio
async def test_datastore_table_retrieval(datastore: InMemoryDatastore) -> None:
    """Datastore returns same table instance for same model class."""
    table1 = datastore.table(SampleModel)
    table2 = datastore.table(SampleModel)

    assert table1 is table2

    # Different model classes get different tables
    table3 = datastore.table(AnotherModel)
    assert table3 is not table1
