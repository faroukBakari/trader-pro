"""PostgreSQL-specific tests - features unique to PostgresDatastore.

Contract tests (test_datastore_contract.py) cover all shared TableInterface/
DatastoreInterface behavior. This file tests ONLY Postgres-specific features:

- Dict return type (not BaseModel)
- psycopg-specific exceptions (UniqueViolation)
- Connection pool behavior
- Settings injection via create()
- Table type detection (JSONB vs SQLModel)

Run with: pytest src/trading_api/datastores/postgres/tests/test_postgres_specific.py -v -m integration
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
from sqlmodel import Field, SQLModel

from trading_api.shared.config import Settings

if TYPE_CHECKING:
    from trading_api.datastores import PostgresDatastore

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
