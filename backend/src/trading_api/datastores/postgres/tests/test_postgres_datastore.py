"""PostgreSQL Datastore integration tests.

These tests validate PostgresDatastore against a real PostgreSQL database.
They are marked with @pytest.mark.integration and require the test_database
fixture which creates an ephemeral test database.

Run with: pytest -m integration
Skip with: pytest -m "not integration"
"""

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from sqlmodel import Field, SQLModel

from trading_api.datastores import PostgresDatastore
from trading_api.datastores.postgres.sqlmodel_table import SQLModelTable
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import TableInterface

# Skip all tests if PostgreSQL not available
pytestmark = [pytest.mark.integration, pytest.mark.postgres]


# Test models as SQLModel(table=True) classes for SQLModelTable storage
class CrudTestModel(SQLModel, table=True):
    """Test model for CRUD operations."""

    __tablename__ = cast(Any, "crud_test_model")

    id: str = Field(primary_key=True)
    name: str
    value: int


class IndexedTestModel(SQLModel, table=True):
    """Test model with indexed fields."""

    __tablename__ = cast(Any, "indexed_test_model")

    id: str = Field(primary_key=True)
    email: str = Field(unique=True)  # Unique index (1:1)
    group: str = Field(index=True)  # Secondary index (1:N)
    value: int


# Type alias for fixture return types
TableFixture = tuple[SQLModelTable[CrudTestModel], type[CrudTestModel]]
IndexedTableFixture = tuple[SQLModelTable[IndexedTestModel], type[IndexedTestModel]]


@pytest.fixture
async def postgres_datastore(
    test_settings: Settings,
) -> AsyncIterator[PostgresDatastore]:
    """Create PostgresDatastore for testing with cleanup.

    Uses test_settings which has DATASTORE_POSTGRES_DSN configured.
    PostgresDatastore.create() reads config and auto-detects test mode.
    """
    ds = await PostgresDatastore.create(config=test_settings)
    yield ds
    # Cleanup: close connection pool
    await ds.close()


class TestPostgresDatastoreInterface:
    """Test PostgresDatastore implements DatastoreInterface correctly."""

    @pytest.mark.asyncio
    async def test_has_persistence_true(
        self, postgres_datastore: PostgresDatastore
    ) -> None:
        """PostgresDatastore.has_persistence returns True."""
        assert postgres_datastore.has_persistence is True

    @pytest.mark.asyncio
    async def test_has_transactions_true(
        self, postgres_datastore: PostgresDatastore
    ) -> None:
        """PostgresDatastore.has_transactions returns True."""
        assert postgres_datastore.has_transactions is True

    @pytest.mark.asyncio
    async def test_datastore_name(self) -> None:
        """PostgresDatastore.datastore_name() returns 'postgres'."""
        assert PostgresDatastore.datastore_name() == "postgres"

    @pytest.mark.asyncio
    async def test_table_returns_table_interface(
        self, postgres_datastore: PostgresDatastore
    ) -> None:
        """table() returns a TableInterface implementation."""
        table = postgres_datastore.table(CrudTestModel)
        assert isinstance(table, TableInterface)
        assert isinstance(table, SQLModelTable)


class TestSQLModelTableCRUD:
    """Test SQLModelTable CRUD operations."""

    @pytest.fixture
    async def table(
        self, postgres_datastore: PostgresDatastore
    ) -> AsyncIterator[TableFixture]:
        """Create a test table with cleanup."""
        # Get table as SQLModelTable
        tbl = postgres_datastore.table(CrudTestModel)
        assert isinstance(tbl, SQLModelTable)
        # Ensure table exists and is empty
        await tbl._ensure_table()
        await tbl.clear()
        yield tbl, CrudTestModel
        # Cleanup
        await tbl.clear()

    @pytest.mark.asyncio
    async def test_set_and_get(self, table: TableFixture) -> None:
        """Test basic set and get operations."""
        tbl, Model = table

        model = Model(id="key1", name="test", value=42)
        await tbl.set("key1", model)

        result = await tbl.get("key1")
        assert result is not None
        assert result.name == "test"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, table: TableFixture) -> None:
        """Test get returns None for nonexistent key."""
        tbl, _ = table
        result = await tbl.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self, table: TableFixture) -> None:
        """Test delete returns True for existing key."""
        tbl, Model = table

        model = Model(id="delete_key", name="to_delete", value=1)
        await tbl.set("delete_key", model)

        result = await tbl.delete("delete_key")
        assert result is True

        # Verify deleted
        assert await tbl.get("delete_key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, table: TableFixture) -> None:
        """Test delete returns False for nonexistent key."""
        tbl, _ = table
        result = await tbl.delete("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_expected(self, table: TableFixture) -> None:
        """Test exists returns correct boolean."""
        tbl, Model = table

        model = Model(id="exists_key", name="exists_test", value=1)
        await tbl.set("exists_key", model)

        assert await tbl.exists("exists_key") is True
        assert await tbl.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_keys_and_values(self, table: TableFixture) -> None:
        """Test keys() and values() return correct data."""
        tbl, Model = table

        await tbl.set("k1", Model(id="k1", name="a", value=1))
        await tbl.set("k2", Model(id="k2", name="b", value=2))

        keys = await tbl.keys()
        assert set(keys) == {"k1", "k2"}

        values = await tbl.values()
        assert len(values) == 2

    @pytest.mark.asyncio
    async def test_clear_removes_all(self, table: TableFixture) -> None:
        """Test clear removes all entries."""
        tbl, Model = table

        await tbl.set("k1", Model(id="k1", name="a", value=1))
        await tbl.set("k2", Model(id="k2", name="b", value=2))
        await tbl.clear()

        assert await tbl.count() == 0

    @pytest.mark.asyncio
    async def test_count_returns_entry_count(self, table: TableFixture) -> None:
        """Test count returns correct number."""
        tbl, Model = table

        assert await tbl.count() == 0
        await tbl.set("k1", Model(id="k1", name="a", value=1))
        assert await tbl.count() == 1
        await tbl.set("k2", Model(id="k2", name="b", value=2))
        assert await tbl.count() == 2


class TestSQLModelTableIndexes:
    """Test SQLModelTable index functionality."""

    @pytest.fixture
    async def indexed_table(
        self, postgres_datastore: PostgresDatastore
    ) -> AsyncIterator[IndexedTableFixture]:
        """Create a table with indexes (extracted from Field metadata)."""
        # Get table - indexes are extracted from Field(index=True, unique=True)
        tbl = postgres_datastore.table(IndexedTestModel)
        assert isinstance(tbl, SQLModelTable)
        await tbl._ensure_table()
        await tbl.clear()
        yield tbl, IndexedTestModel
        await tbl.clear()

    @pytest.mark.asyncio
    async def test_get_by_unique_index(
        self, indexed_table: IndexedTableFixture
    ) -> None:
        """Test get with unique index returns correct record."""
        tbl, Model = indexed_table

        await tbl.set("k1", Model(id="k1", email="a@test.com", group="admin", value=1))
        await tbl.set("k2", Model(id="k2", email="b@test.com", group="user", value=2))

        result = await tbl.get("a@test.com", index="email")
        assert result is not None
        assert result.value == 1

    @pytest.mark.asyncio
    async def test_get_all_by_secondary_index(
        self, indexed_table: IndexedTableFixture
    ) -> None:
        """Test get_all with secondary index returns multiple records."""
        tbl, Model = indexed_table

        await tbl.set("k1", Model(id="k1", email="a@test.com", group="admin", value=1))
        await tbl.set("k2", Model(id="k2", email="b@test.com", group="admin", value=2))
        await tbl.set("k3", Model(id="k3", email="c@test.com", group="user", value=3))

        results = await tbl.get_all("admin", index="group")
        assert len(results) == 2
        values = {r.value for r in results}
        assert values == {1, 2}

    @pytest.mark.asyncio
    async def test_delete_by_index(self, indexed_table: IndexedTableFixture) -> None:
        """Test delete with index removes correct record."""
        tbl, Model = indexed_table

        await tbl.set(
            "k1", Model(id="k1", email="delete@test.com", group="admin", value=1)
        )

        result = await tbl.delete("delete@test.com", index="email")
        assert result is True
        assert await tbl.get("k1") is None

    @pytest.mark.asyncio
    async def test_unique_index_constraint(
        self, indexed_table: IndexedTableFixture
    ) -> None:
        """Test unique index raises on duplicate."""
        tbl, Model = indexed_table

        await tbl.set(
            "k1", Model(id="k1", email="dup@test.com", group="admin", value=1)
        )

        # SQLAlchemy raises IntegrityError for constraint violations
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await tbl.set(
                "k2", Model(id="k2", email="dup@test.com", group="user", value=2)
            )
