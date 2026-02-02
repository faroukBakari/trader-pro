"""InMemory-specific tests - features unique to InMemoryDatastore.

Contract tests (test_datastore_contract.py) cover all shared TableInterface/
DatastoreInterface behavior. This file tests ONLY InMemory-specific features:

- RWLock behavior (read-write lock semantics)
- Model copy isolation (returns actual BaseModel, not dict)
- Timeout configuration
- Table instance caching
- Exclusion constraint rejection (fail-fast for unsupported models)

Run with: pytest src/trading_api/datastores/inmemory/tests/ -v
"""

import asyncio
from typing import Any, cast

import pytest
from sqlmodel import Field, SQLModel

from trading_api.datastores.inmemory import InMemoryDatastore, InMemoryTable
from trading_api.shared.config import Settings


class SampleModel(SQLModel):
    """Test model for InMemory-specific tests."""

    id: str = Field(primary_key=True)
    name: str


class AnotherModel(SQLModel):
    """Another model for table isolation tests."""

    key: str = Field(primary_key=True)
    data: str


class ExclusionRequiredModel(SQLModel, table=True):
    """Model that requires exclusion constraints (should be rejected by InMemory)."""

    __tablename__ = cast(Any, "exclusion_test")
    __table_args__ = {
        "info": {"exclusion": {"range_field": "time_range", "group": "lookup_key"}}
    }

    id: int | None = Field(default=None, primary_key=True)
    lookup_key: str
    time_range_start: int
    time_range_end: int


# =============================================================================
# InMemory-Specific: Model Return Type
# =============================================================================


@pytest.mark.asyncio
async def test_get_returns_basemodel_instance() -> None:
    """InMemory get() returns actual BaseModel instance (not dict)."""
    table: InMemoryTable = InMemoryTable(timeout=1.0)
    model = SampleModel(id="1", name="test")
    await table.set("1", model)

    result = await table.get("1")

    # InMemory returns BaseModel instance directly (Postgres returns dict)
    assert isinstance(result, SampleModel)
    assert result.name == "test"


@pytest.mark.asyncio
async def test_returned_model_is_deep_copy() -> None:
    """InMemory returns deep copy, not reference to internal storage."""
    table: InMemoryTable = InMemoryTable(timeout=1.0)
    original = SampleModel(id="1", name="original")
    await table.set("1", original)

    retrieved = await table.get("1")

    # Must be different object (deep copy)
    assert retrieved is not original
    # But with same values
    assert isinstance(retrieved, SampleModel)
    assert retrieved.name == original.name


# =============================================================================
# InMemory-Specific: Timeout Configuration
# =============================================================================


@pytest.mark.asyncio
async def test_table_timeout_configurable() -> None:
    """InMemoryTable accepts custom timeout."""
    table = InMemoryTable(timeout=5.0)
    assert table.timeout == 5.0


@pytest.mark.asyncio
async def test_datastore_timeout_propagates_to_tables() -> None:
    """InMemoryDatastore timeout is used by tables."""
    ds = InMemoryDatastore(timeout=3.0)
    assert ds.timeout == 3.0


# =============================================================================
# InMemory-Specific: Table Instance Caching
# =============================================================================


@pytest.mark.asyncio
async def test_table_returns_same_instance_for_same_class() -> None:
    """Same model class returns same table instance."""
    ds = InMemoryDatastore()
    table1 = ds.table(SampleModel)
    table2 = ds.table(SampleModel)
    assert table1 is table2


@pytest.mark.asyncio
async def test_table_returns_different_instance_for_different_class() -> None:
    """Different model classes get different table instances."""
    ds = InMemoryDatastore()
    table1 = ds.table(SampleModel)
    table2 = ds.table(AnotherModel)
    assert table1 is not table2


# =============================================================================
# InMemory-Specific: RWLock Behavior
# =============================================================================


@pytest.mark.asyncio
async def test_rwlock_allows_concurrent_reads() -> None:
    """RWLock allows multiple concurrent read acquisitions."""
    table: InMemoryTable = InMemoryTable(timeout=1.0)
    await table.set("k", SampleModel(id="k", name="value"))

    read_count = 0

    async def reader() -> None:
        nonlocal read_count
        async with table.lock.read():
            read_count += 1
            await asyncio.sleep(0.01)  # Hold lock briefly

    # Start 5 concurrent reads - they should all hold lock simultaneously
    await asyncio.gather(*[reader() for _ in range(5)])
    assert read_count == 5


@pytest.mark.asyncio
async def test_rwlock_write_blocks_reads() -> None:
    """RWLock write acquisition blocks pending reads."""
    table: InMemoryTable = InMemoryTable(timeout=2.0)
    events: list[str] = []

    async def writer() -> None:
        async with table.lock.write():
            events.append("write_start")
            await asyncio.sleep(0.05)
            events.append("write_end")

    async def reader() -> None:
        await asyncio.sleep(0.01)  # Let writer start first
        async with table.lock.read():
            events.append("read")

    await asyncio.gather(writer(), reader())

    # Read should happen after write completes
    assert events.index("read") > events.index("write_end")


# =============================================================================
# InMemory-Specific: Create Factory
# =============================================================================


@pytest.mark.asyncio
async def test_create_accepts_config_parameter() -> None:
    """InMemoryDatastore.create() accepts Settings parameter (contract compliance)."""
    settings = Settings(API_PORT=9999)  # Any settings, unused by InMemory

    ds = await InMemoryDatastore.create(config=settings)

    assert isinstance(ds, InMemoryDatastore)


@pytest.mark.asyncio
async def test_create_works_without_config() -> None:
    """InMemoryDatastore.create() works without config parameter."""
    ds = await InMemoryDatastore.create()
    assert isinstance(ds, InMemoryDatastore)


# =============================================================================
# InMemory-Specific: drop_table()
# =============================================================================


@pytest.mark.asyncio
async def test_drop_table_returns_true_when_exists() -> None:
    """drop_table() returns True when table exists and is dropped."""
    ds = await InMemoryDatastore.create()
    ds.table(SampleModel)  # Create the table

    dropped = await ds.drop_table("samplemodel")

    assert dropped is True
    assert "samplemodel" not in await ds.list_tables()


@pytest.mark.asyncio
async def test_drop_table_returns_false_when_not_exists() -> None:
    """drop_table() returns False when table doesn't exist."""
    ds = await InMemoryDatastore.create()

    dropped = await ds.drop_table("nonexistent")

    assert dropped is False


@pytest.mark.asyncio
async def test_drop_table_allows_recreation() -> None:
    """After drop_table(), table can be recreated fresh."""
    ds = await InMemoryDatastore.create()
    table1 = ds.table(SampleModel)
    await table1.set("k", SampleModel(id="k", name="old"))

    await ds.drop_table("samplemodel")

    # Recreate and verify it's fresh
    table2 = ds.table(SampleModel)
    assert await table2.count() == 0
    assert table1 is not table2  # Different instance


# =============================================================================
# InMemory-Specific: is_empty property
# =============================================================================


@pytest.mark.asyncio
async def test_is_empty_true_when_no_entries() -> None:
    """is_empty returns True for empty table."""
    table: InMemoryTable = InMemoryTable()
    assert await table.is_empty is True


@pytest.mark.asyncio
async def test_is_empty_false_when_has_entries() -> None:
    """is_empty returns False when table has entries."""
    table: InMemoryTable = InMemoryTable()
    await table.set("k", SampleModel(id="k", name="test"))
    assert await table.is_empty is False


# =============================================================================
# InMemory-Specific: list_tables()
# =============================================================================


@pytest.mark.asyncio
async def test_list_tables_returns_all() -> None:
    """list_tables() returns all table names."""
    ds = await InMemoryDatastore.create()
    ds.table(SampleModel)
    ds.table(AnotherModel)

    tables = await ds.list_tables()

    assert "samplemodel" in tables
    assert "anothermodel" in tables


@pytest.mark.asyncio
async def test_list_tables_with_prefix() -> None:
    """list_tables() filters by prefix."""
    ds = await InMemoryDatastore.create()
    # Access _tables directly to add a bar-style table name
    ds._tables["bars_aapl_r1d"] = InMemoryTable()
    ds._tables["bars_msft_r1d"] = InMemoryTable()
    ds.table(SampleModel)  # Creates "samplemodel"

    # All tables
    all_tables = await ds.list_tables()
    assert len(all_tables) >= 3

    # Only bar tables
    bar_tables = await ds.list_tables(prefix="bars_")
    assert len(bar_tables) == 2
    assert "bars_aapl_r1d" in bar_tables
    assert "bars_msft_r1d" in bar_tables
    assert "samplemodel" not in bar_tables


@pytest.mark.asyncio
async def test_list_tables_empty() -> None:
    """list_tables() returns empty list when no tables exist."""
    ds = await InMemoryDatastore.create()

    tables = await ds.list_tables()
    assert tables == []


# =============================================================================
# InMemory-Specific: Exclusion Constraint Rejection (Fail-Fast)
# =============================================================================


@pytest.mark.asyncio
async def test_table_rejects_models_requiring_exclusion() -> None:
    """table() raises NotImplementedError for models with exclusion requirements.

    Models that declare __table_args__["info"]["exclusion"] require database-level
    exclusion constraints (PostgreSQL EXCLUDE USING GIST). InMemory cannot provide
    this guarantee, so it fails fast rather than silently allowing overlapping ranges.
    """
    ds = await InMemoryDatastore.create()

    with pytest.raises(NotImplementedError) as exc_info:
        ds.table(ExclusionRequiredModel)

    assert "exclusion constraints" in str(exc_info.value)
    assert "ExclusionRequiredModel" in str(exc_info.value)
    assert "PostgresDatastore" in str(exc_info.value)


@pytest.mark.asyncio
async def test_table_allows_models_without_exclusion() -> None:
    """table() allows normal models without exclusion requirements."""
    ds = await InMemoryDatastore.create()

    # Should not raise - no exclusion requirement
    table = ds.table(SampleModel)
    assert table is not None
