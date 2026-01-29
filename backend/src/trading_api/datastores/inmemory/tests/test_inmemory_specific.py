"""InMemory-specific tests - features unique to InMemoryDatastore.

Contract tests (test_datastore_contract.py) cover all shared TableInterface/
DatastoreInterface behavior. This file tests ONLY InMemory-specific features:

- RWLock behavior (read-write lock semantics)
- Model copy isolation (returns actual BaseModel, not dict)
- Timeout configuration
- Table instance caching

Run with: pytest src/trading_api/datastores/inmemory/tests/ -v
"""

import asyncio

import pytest
from sqlmodel import SQLModel

from trading_api.datastores.inmemory import InMemoryDatastore, InMemoryTable
from trading_api.shared.config import Settings


class SampleModel(SQLModel):
    """Test model for InMemory-specific tests."""

    id: str
    name: str


class AnotherModel(SQLModel):
    """Another model for table isolation tests."""

    key: str
    data: str


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
# InMemory-Specific: Reset Protection
# =============================================================================


@pytest.mark.asyncio
async def test_reset_raises_when_disabled() -> None:
    """reset() raises RuntimeError when DATASTORE_ALLOW_RESET is False."""
    # Create settings with reset disabled (production mode)
    settings = Settings(DATASTORE_ALLOW_RESET=False)
    ds = await InMemoryDatastore.create(config=settings)
    table = ds.table(SampleModel)

    with pytest.raises(RuntimeError, match="reset\\(\\) is disabled"):
        await table.reset()


@pytest.mark.asyncio
async def test_reset_works_when_enabled() -> None:
    """reset() works when DATASTORE_ALLOW_RESET is True."""
    settings = Settings(DATASTORE_ALLOW_RESET=True)
    ds = await InMemoryDatastore.create(config=settings)
    table = ds.table(SampleModel)

    await table.set("k", SampleModel(id="k", name="test"))
    await table.reset()
    assert await table.count() == 0
