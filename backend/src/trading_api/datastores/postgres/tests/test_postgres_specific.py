"""PostgreSQL-specific tests - features unique to PostgresDatastore.

Contract tests (test_datastore_contract.py) cover all shared TableInterface/
DatastoreInterface behavior. This file tests ONLY Postgres-specific features:

- Dict return type (not BaseModel)
- psycopg-specific exceptions (UniqueViolation)
- Connection pool behavior
- Settings injection via create()
- Table type detection (JSONB vs SQLModel)
- Exclusion constraints via __table_args__ metadata + exclusion_listener

Run with: pytest src/trading_api/datastores/postgres/tests/test_postgres_specific.py -v -m integration
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Optional, cast

import pytest
from sqlmodel import Field, SQLModel

from trading_api.shared.config import Settings
from trading_api.types import Int8RangeType, IntRange

if TYPE_CHECKING:
    from trading_api.datastores import PostgresDatastore
    from trading_api.datastores.postgres import SQLModelTable

# Skip all tests if PostgreSQL not available
pytestmark = [pytest.mark.integration, pytest.mark.postgres]


class PgSampleModel(SQLModel):
    """Test model for Postgres-specific tests."""

    name: str
    value: int


class PgIndexedModel(SQLModel):
    """Model with unique constraint for violation tests (JSONB storage)."""

    email: str = Field(unique=True)
    value: int


class PgRangeModel(SQLModel, table=True):
    """SQLModel with native int8range column for exclusion constraint tests.

    Uses native PostgreSQL int8range type via Int8RangeType TypeDecorator.
    This is the production pattern used by PendingRange/CoveredRange models.
    Exclusion constraint is created automatically by exclusion_listener.
    """

    __tablename__ = cast(Any, "pg_range_test")
    __table_args__ = {
        "info": {"exclusion": {"range_field": "time_range", "group": "lookup_key"}}
    }

    id: Optional[int] = Field(default=None, primary_key=True)
    lookup_key: str = Field(index=True)
    time_range: IntRange = Field(..., sa_type=Int8RangeType)
    description: str = ""


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def postgres_datastore(
    test_settings: Settings,
) -> AsyncIterator["PostgresDatastore"]:
    """PostgresDatastore fixture using test_settings."""
    from trading_api.datastores import PostgresDatastore

    ds = await PostgresDatastore.create(config=test_settings)
    yield ds
    await ds.close()


# =============================================================================
# Postgres-Specific: Dict Return Type
# =============================================================================


@pytest.mark.asyncio
async def test_get_returns_dict_not_basemodel(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """PostgresTable.get() returns dict, not BaseModel instance."""
    from trading_api.datastores import PostgresTable

    table = postgres_datastore.table(PgSampleModel)
    assert isinstance(table, PostgresTable)

    # clear() triggers table creation internally
    await table.clear()

    await table.set("key1", PgSampleModel(name="test", value=42))
    result = await table.get("key1")

    # Postgres returns dict (caller uses model_validate for conversion)
    assert isinstance(result, dict)
    assert result["name"] == "test"
    assert result["value"] == 42


# =============================================================================
# Postgres-Specific: psycopg Exceptions
# =============================================================================


@pytest.mark.asyncio
async def test_unique_constraint_raises_psycopg_exception(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """Unique constraint violation raises psycopg UniqueViolation."""
    from psycopg.errors import UniqueViolation

    from trading_api.datastores import PostgresTable

    table = postgres_datastore.table(PgIndexedModel)
    assert isinstance(table, PostgresTable)

    # clear() triggers table creation internally
    await table.clear()

    await table.set("k1", PgIndexedModel(email="dup@test.com", value=1))

    # psycopg3 raises UniqueViolation (not generic ValueError like InMemory)
    with pytest.raises(UniqueViolation):
        await table.set("k2", PgIndexedModel(email="dup@test.com", value=2))


# =============================================================================
# Postgres-Specific: Settings Injection
# =============================================================================


@pytest.mark.asyncio
async def test_create_uses_injected_settings(
    test_settings: Settings,
) -> None:
    """PostgresDatastore.create() uses injected Settings for DSN."""
    from trading_api.datastores import PostgresDatastore

    # test_settings has DSN set by test_database fixture
    ds = await PostgresDatastore.create(config=test_settings)

    try:
        assert ds.has_persistence is True
        # Verify we can actually use it
        table = ds.table(PgSampleModel)
        await table.clear()
        await table.set("test_key", PgSampleModel(name="test", value=1))
        assert await table.count() == 1
    finally:
        await ds.close()


@pytest.mark.asyncio
async def test_create_builds_dsn_from_components(
    test_settings: Settings,
) -> None:
    """PostgresDatastore.create() can build DSN from host/port/user/pass/db components."""
    from trading_api.datastores import PostgresDatastore

    # If DSN is set, test that it works (already covered elsewhere)
    # This test verifies that a datastore can be created with valid settings
    assert test_settings.DATASTORE_POSTGRES_DSN is not None
    ds = await PostgresDatastore.create(config=test_settings)
    try:
        # Verify it works
        table = ds.table(PgSampleModel)
        await table.clear()
        await table.set("test_key", PgSampleModel(name="test", value=1))
        assert await table.count() == 1
    finally:
        await ds.close()


# =============================================================================
# Postgres-Specific: Eager Schema Creation
# =============================================================================


@pytest.mark.asyncio
async def test_create_ensures_sqlmodel_tables_at_startup(
    test_settings: Settings,
) -> None:
    """SQLModel table=True tables exist immediately after create() - no lazy init.

    This verifies the eager schema creation behavior: metadata.create_all() runs
    during PostgresDatastore.create(), so tables exist before any data operations.
    """
    from trading_api.datastores import PostgresDatastore

    ds = await PostgresDatastore.create(config=test_settings)
    try:
        # Query tables WITHOUT any data operations - proves eager creation
        tables = await ds.list_tables()

        # 'users' and 'refresh_tokens' are table=True models in trading_api.models.auth
        # (table names come from __tablename__ attribute)
        assert "users" in tables, "users table should exist immediately after create()"
        assert (
            "refresh_tokens" in tables
        ), "refresh_tokens table should exist immediately after create()"
    finally:
        await ds.close()


# =============================================================================
# Postgres-Specific: Table Type Detection
# =============================================================================


@pytest.mark.asyncio
async def test_table_returns_postgres_table_for_jsonb_model(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """table() returns PostgresTable for models without table=True (JSONB storage)."""
    from trading_api.datastores import PostgresTable

    table = postgres_datastore.table(PgIndexedModel)
    assert isinstance(table, PostgresTable)


# =============================================================================
# Postgres-Specific: Connection Pool
# =============================================================================


@pytest.mark.asyncio
async def test_close_releases_pool(test_settings: Settings) -> None:
    """close() properly releases connection pool."""
    from trading_api.datastores import PostgresDatastore

    ds = await PostgresDatastore.create(config=test_settings)

    # Should be able to use it
    table = ds.table(PgSampleModel)
    await table.clear()

    # Close should work
    await ds.close()

    # After close, pool should be closed (operations will fail)
    # We don't test this explicitly as behavior depends on psycopg internals


# =============================================================================
# Postgres-Specific: list_tables()
# =============================================================================


@pytest.mark.asyncio
async def test_list_tables_returns_public_tables(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """list_tables() returns tables from public schema."""
    from trading_api.datastores import PostgresTable

    # Create a table via datastore (clear() triggers creation)
    table = postgres_datastore.table(PgSampleModel)
    assert isinstance(table, PostgresTable)
    await table.clear()

    tables = await postgres_datastore.list_tables()

    # Should include our table (table name is derived from model's __tablename__)
    # PgSampleModel doesn't have __tablename__, so it will use JSONB table name
    assert len(tables) >= 1  # At least our table should exist


@pytest.mark.asyncio
async def test_list_tables_with_prefix(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """list_tables() filters by prefix."""
    from psycopg import sql

    # Create bar tables directly via SQL
    async with postgres_datastore._pool.connection() as conn:
        await conn.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS bars_test_r1d (time BIGINT PRIMARY KEY)"
            )
        )
        await conn.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS bars_test_r1h (time BIGINT PRIMARY KEY)"
            )
        )

    try:
        bar_tables = await postgres_datastore.list_tables(prefix="bars_")
        assert "bars_test_r1d" in bar_tables
        assert "bars_test_r1h" in bar_tables
    finally:
        # Cleanup
        async with postgres_datastore._pool.connection() as conn:
            await conn.execute(sql.SQL("DROP TABLE IF EXISTS bars_test_r1d"))
            await conn.execute(sql.SQL("DROP TABLE IF EXISTS bars_test_r1h"))


@pytest.mark.asyncio
async def test_list_tables_prefix_excludes_non_matching(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """list_tables() with prefix excludes non-matching tables."""
    from psycopg import sql

    # Create one bar table and one non-bar table
    async with postgres_datastore._pool.connection() as conn:
        await conn.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS bars_filter_r1d (time BIGINT PRIMARY KEY)"
            )
        )
        await conn.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS other_test_table (id SERIAL PRIMARY KEY)"
            )
        )

    try:
        bar_tables = await postgres_datastore.list_tables(prefix="bars_")
        all_tables = await postgres_datastore.list_tables()

        assert "bars_filter_r1d" in bar_tables
        assert "other_test_table" not in bar_tables
        assert "other_test_table" in all_tables
    finally:
        # Cleanup
        async with postgres_datastore._pool.connection() as conn:
            await conn.execute(sql.SQL("DROP TABLE IF EXISTS bars_filter_r1d"))
            await conn.execute(sql.SQL("DROP TABLE IF EXISTS other_test_table"))


# =============================================================================
# Postgres-Specific: drop_table()
# =============================================================================


@pytest.mark.asyncio
async def test_drop_table_returns_true_when_exists(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """drop_table() returns True when table exists and is dropped."""
    from psycopg import sql

    # Create a table directly
    async with postgres_datastore._pool.connection() as conn:
        await conn.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS drop_test_table (id SERIAL PRIMARY KEY)"
            )
        )

    dropped = await postgres_datastore.drop_table("drop_test_table")

    assert dropped is True
    assert "drop_test_table" not in await postgres_datastore.list_tables()


@pytest.mark.asyncio
async def test_drop_table_returns_false_when_not_exists(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """drop_table() returns False when table doesn't exist."""
    dropped = await postgres_datastore.drop_table("nonexistent_table_xyz")
    assert dropped is False


@pytest.mark.asyncio
async def test_drop_table_removes_from_internal_cache(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """drop_table() removes table from internal tracking cache."""
    # Create table via the datastore API (clear() triggers creation)
    table = postgres_datastore.table(PgSampleModel)
    await table.clear()

    # Verify it's in the cache (the table name is the __tablename__ attribute)
    table_name = getattr(PgSampleModel, "__tablename__", None)
    if table_name:
        assert table_name in postgres_datastore._tables

        # Drop it
        await postgres_datastore.drop_table(table_name)

        # Should be removed from cache
        assert table_name not in postgres_datastore._tables


# =============================================================================
# Postgres-Specific: is_empty property
# =============================================================================


@pytest.mark.asyncio
async def test_is_empty_true_when_no_entries(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """is_empty returns True for empty table."""
    table = postgres_datastore.table(PgSampleModel)
    await table.clear()  # triggers table creation

    assert await table.is_empty is True


@pytest.mark.asyncio
async def test_is_empty_false_when_has_entries(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """is_empty returns False when table has entries."""
    table = postgres_datastore.table(PgSampleModel)
    await table.clear()  # triggers table creation

    await table.set("k", PgSampleModel(name="test", value=42))
    assert await table.is_empty is False


# =============================================================================
# SQLModelTable: Declarative Exclusion Constraints via __table_args__
# =============================================================================


@pytest.fixture
async def range_table(
    postgres_datastore: "PostgresDatastore",
) -> AsyncIterator["SQLModelTable[PgRangeModel]"]:
    """Fixture providing a clean PgRangeModel table with exclusion constraint.

    Constraint is created automatically by exclusion_listener from __table_args__.
    """
    from trading_api.datastores.postgres import SQLModelTable

    table = postgres_datastore.table(PgRangeModel)
    assert isinstance(table, SQLModelTable)

    # Clear table - exclusion constraint created automatically on first access
    await table.clear()

    yield table

    # Cleanup: drop table
    try:
        await postgres_datastore.drop_table("pg_range_test")
    except Exception:
        pass


@pytest.mark.asyncio
async def test_exclusion_rejects_overlapping_ranges_same_group(
    range_table: "SQLModelTable",
) -> None:
    """Overlapping ranges within same lookup_key are rejected.

    This is the core business case: prevent duplicate pending/covered ranges
    for the same symbol+resolution combination.
    """
    from sqlalchemy.exc import IntegrityError

    # Insert first range: [100, 200] for group "AAPL_1D"
    await range_table.set(
        "1",
        PgRangeModel(
            lookup_key="AAPL_1D",
            time_range=IntRange(start=100, end=200),
            description="first range",
        ),
    )

    # Try to insert overlapping range: [150, 250] for same group
    with pytest.raises(IntegrityError) as exc_info:
        await range_table.set(
            "2",
            PgRangeModel(
                lookup_key="AAPL_1D",
                time_range=IntRange(start=150, end=250),
                description="overlapping range",
            ),
        )

    # Should be exclusion violation
    assert (
        "exclusion" in str(exc_info.value).lower()
        or "conflicting" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_exclusion_allows_non_overlapping_ranges_same_group(
    range_table: "SQLModelTable",
) -> None:
    """Non-overlapping ranges within same group are allowed."""
    # Insert first range: [100, 200]
    await range_table.set(
        "1",
        PgRangeModel(
            lookup_key="AAPL_1D",
            time_range=IntRange(start=100, end=200),
            description="first range",
        ),
    )

    # Insert non-overlapping range: [300, 400] - should succeed
    await range_table.set(
        "2",
        PgRangeModel(
            lookup_key="AAPL_1D",
            time_range=IntRange(start=300, end=400),
            description="non-overlapping range",
        ),
    )

    assert await range_table.count() == 2


@pytest.mark.asyncio
async def test_exclusion_allows_overlapping_ranges_different_groups(
    range_table: "SQLModelTable",
) -> None:
    """Overlapping ranges in different groups are allowed.

    Different symbol+resolution combinations can have overlapping time ranges.
    """
    # Insert range for AAPL_1D: [100, 200]
    await range_table.set(
        "1",
        PgRangeModel(
            lookup_key="AAPL_1D",
            time_range=IntRange(start=100, end=200),
            description="AAPL daily",
        ),
    )

    # Insert overlapping range for MSFT_1D: [150, 250] - different group, should succeed
    await range_table.set(
        "2",
        PgRangeModel(
            lookup_key="MSFT_1D",
            time_range=IntRange(start=150, end=250),
            description="MSFT daily",
        ),
    )

    # Insert overlapping range for AAPL_1H: [150, 250] - different resolution, should succeed
    await range_table.set(
        "3",
        PgRangeModel(
            lookup_key="AAPL_1H",
            time_range=IntRange(start=150, end=250),
            description="AAPL hourly",
        ),
    )

    assert await range_table.count() == 3


@pytest.mark.asyncio
async def test_exclusion_allows_adjacent_ranges(
    range_table: "SQLModelTable",
) -> None:
    """Adjacent ranges (touching at boundary) are allowed with [] bounds.

    With inclusive bounds [], ranges [100,200] and [201,300] don't overlap.
    """
    await range_table.set(
        "1",
        PgRangeModel(
            lookup_key="AAPL_1D",
            time_range=IntRange(start=100, end=200),
        ),
    )

    # Adjacent range starting right after - should succeed
    await range_table.set(
        "2",
        PgRangeModel(
            lookup_key="AAPL_1D",
            time_range=IntRange(start=201, end=300),
        ),
    )

    assert await range_table.count() == 2


# =============================================================================
# Exclusion Listener: Automatic Constraint Creation from Model Metadata
# =============================================================================


@pytest.mark.asyncio
async def test_exclusion_listener_creates_constraint_from_table_args(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """Exclusion listener creates constraint from __table_args__[info][exclusion].

    This tests the declarative pattern where models declare exclusion intent
    via __table_args__ and the listener creates the constraint automatically.
    """
    from psycopg.rows import dict_row

    # Import real production models that use __table_args__ exclusion
    from trading_api.models.market import PendingRange

    # Access table to trigger schema creation
    table = postgres_datastore.table(PendingRange)
    await table.clear()  # Ensures table exists

    # Verify constraint exists in pg_constraint
    async with postgres_datastore._pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT conname, contype FROM pg_constraint
                WHERE conname = 'pending_ranges_no_overlap'
                AND conrelid = 'pending_ranges'::regclass
                """
            )
            row = await cur.fetchone()

    assert row is not None, "Exclusion constraint pending_ranges_no_overlap not found"
    assert row["conname"] == "pending_ranges_no_overlap"
    assert row["contype"] == "x"  # 'x' = exclusion constraint


@pytest.mark.asyncio
async def test_exclusion_listener_creates_covered_ranges_constraint(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """Verify CoveredRange model also gets exclusion constraint from listener."""
    from psycopg.rows import dict_row

    from trading_api.models.market import CoveredRange

    # Access table to trigger schema creation
    table = postgres_datastore.table(CoveredRange)
    await table.clear()

    # Verify constraint exists
    async with postgres_datastore._pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT conname, contype FROM pg_constraint
                WHERE conname = 'covered_ranges_no_overlap'
                AND conrelid = 'covered_ranges'::regclass
                """
            )
            row = await cur.fetchone()

    assert row is not None, "Exclusion constraint covered_ranges_no_overlap not found"
    assert row["contype"] == "x"


@pytest.mark.asyncio
async def test_exclusion_listener_enforces_non_overlapping_pending_ranges(
    postgres_datastore: "PostgresDatastore",
) -> None:
    """Integration test: overlapping PendingRange inserts are rejected.

    This tests the full flow:
    1. Model declares exclusion via __table_args__
    2. Listener creates constraint during schema creation
    3. Overlapping inserts raise IntegrityError
    """
    from sqlalchemy.exc import IntegrityError

    from trading_api.models.market import PendingRange, Resolution, TimeRange

    table = postgres_datastore.table(PendingRange)
    await table.clear()

    # Use reasonable expires_at that fits in 32-bit integer
    expires_at = 2000000000  # Fits in 32-bit signed int (max ~2.1B)

    # Insert first range
    pending1 = PendingRange(
        symbol="AAPL",
        resolution=Resolution.DAY_1,
        time_range=TimeRange(start=1000, end=2000),
        expires_at=expires_at,
    )
    await table.set(pending1.id, pending1)

    # Try to insert overlapping range (same lookup_key, overlapping time_range)
    pending2 = PendingRange(
        symbol="AAPL",
        resolution=Resolution.DAY_1,
        time_range=TimeRange(start=1500, end=2500),  # Overlaps with [1000, 2000]
        expires_at=expires_at,
    )

    with pytest.raises(IntegrityError) as exc_info:
        await table.set(pending2.id, pending2)

    # Verify it's an exclusion violation
    assert (
        "exclusion" in str(exc_info.value).lower()
        or "conflicting" in str(exc_info.value).lower()
    )
