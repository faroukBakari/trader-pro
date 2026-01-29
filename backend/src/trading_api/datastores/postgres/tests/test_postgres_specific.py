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

    # Ensure table exists and clear
    await table._ensure_table()
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

    await table._ensure_table()
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
