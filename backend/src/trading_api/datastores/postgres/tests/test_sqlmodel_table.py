"""SQLModelTable unit tests.

Tests the _session_scope context manager and transaction behavior.
"""

from collections.abc import AsyncIterator

import pytest
from sqlmodel import Field, SQLModel

from trading_api.datastores import PostgresDatastore
from trading_api.datastores.postgres.sqlmodel_table import SQLModelTable
from trading_api.shared.config import Settings

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


# Test model with table=True for SQLModelTable storage
class TransactionTestModel(SQLModel, table=True):
    """Test model for transaction tests."""

    id: str = Field(primary_key=True)
    name: str
    value: int


@pytest.fixture
async def datastore(test_settings: Settings) -> AsyncIterator[PostgresDatastore]:
    """Create PostgresDatastore for testing."""
    ds = await PostgresDatastore.create(config=test_settings)
    yield ds
    await ds.close()


@pytest.fixture
async def table(
    datastore: PostgresDatastore,
) -> AsyncIterator[SQLModelTable[TransactionTestModel]]:
    """Create SQLModelTable for TransactionTestModel."""
    tbl = datastore.table(TransactionTestModel)
    assert isinstance(tbl, SQLModelTable)
    await tbl._ensure_table()
    await tbl.clear()
    yield tbl
    await tbl.clear()


class TestSessionScope:
    """Tests for SQLModelTable._session_scope context manager."""

    async def test_session_scope_without_session_creates_and_commits(
        self, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """When no session provided, creates new session and commits."""
        # Use _session_scope without external session
        async with table._session_scope(session=None) as session:
            # Session should be valid
            assert session is not None

        # Verify commit was called by checking data persists
        model = TransactionTestModel(id="test1", name="test", value=42)
        await table.set("test1", model)

        result = await table.get("test1")
        assert result is not None
        assert result.name == "test"

    async def test_session_scope_with_session_does_not_commit(
        self, datastore: PostgresDatastore, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """When session provided, uses it without auto-commit.

        Caller is responsible for committing.
        """
        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as external_session:
            # Use _session_scope with external session
            async with table._session_scope(session=external_session) as s:
                assert s is external_session  # Same session instance

            # Session should still be usable (not committed/closed by _session_scope)
            # We need to explicitly commit
            await external_session.commit()

    async def test_session_scope_rollback_on_exception(
        self, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """When exception raised, session rolls back automatically."""
        # Add a model first
        await table.set(
            "initial", TransactionTestModel(id="initial", name="init", value=1)
        )

        # Attempt operation that raises, should rollback
        with pytest.raises(ValueError):
            async with table._session_scope(session=None) as session:
                # This would be committed on success, but we'll raise
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(TransactionTestModel).values(
                    id="rollback_test", name="should_rollback", value=0
                )
                await session.execute(stmt)
                raise ValueError("Simulated error")

        # Verify the rollback - record should not exist
        result = await table.get("rollback_test")
        assert result is None

        # But initial should still exist
        initial = await table.get("initial")
        assert initial is not None


class TestTransactionBatching:
    """Tests for multi-operation transactions using session injection."""

    async def test_multiple_operations_same_transaction(
        self, datastore: PostgresDatastore, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """Multiple operations with shared session commit atomically."""
        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as session:
            # Multiple operations in same transaction
            await table.set(
                "batch1",
                TransactionTestModel(id="batch1", name="first", value=1),
                session=session,
            )
            await table.set(
                "batch2",
                TransactionTestModel(id="batch2", name="second", value=2),
                session=session,
            )
            await table.delete("nonexistent", session=session)

            # Commit all at once
            await session.commit()

        # Verify both persisted
        r1 = await table.get("batch1")
        r2 = await table.get("batch2")
        assert r1 is not None and r1.value == 1
        assert r2 is not None and r2.value == 2

    async def test_delete_and_insert_atomic(
        self, datastore: PostgresDatastore, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """Delete + insert in same transaction is atomic."""
        # Setup: create initial record
        await table.set(
            "atomic_key",
            TransactionTestModel(id="atomic_key", name="original", value=100),
        )

        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as session:
            # Atomically: delete old + insert new
            await table.delete("atomic_key", session=session)
            await table.set(
                "atomic_key",
                TransactionTestModel(id="atomic_key", name="replaced", value=200),
                session=session,
            )
            await session.commit()

        # Verify replacement
        result = await table.get("atomic_key")
        assert result is not None
        assert result.name == "replaced"
        assert result.value == 200

    async def test_uncommitted_changes_not_visible(
        self, datastore: PostgresDatastore, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """Changes are not visible until commit."""
        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as session:
            # Insert without commit
            await table.set(
                "uncommitted",
                TransactionTestModel(id="uncommitted", name="pending", value=999),
                session=session,
            )

            # Without commit, checking from a different session should not see it
            result = await table.get("uncommitted")  # Uses its own session
            assert result is None  # Not committed yet

            # Now commit
            await session.commit()

        # After commit, it should be visible
        result = await table.get("uncommitted")
        assert result is not None
        assert result.name == "pending"

    async def test_read_your_writes_with_session(
        self, datastore: PostgresDatastore, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """When using same session, uncommitted writes are visible to reads."""
        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as session:
            # Write with session
            await table.set(
                "ryw_key",
                TransactionTestModel(id="ryw_key", name="visible", value=42),
                session=session,
            )

            # Read with SAME session should see uncommitted data
            result = await table.get("ryw_key", session=session)
            assert result is not None
            assert result.name == "visible"

            # exists() with same session should also work
            assert await table.exists("ryw_key", session=session) is True

            # get_all with same session
            all_results = await table.get_all("ryw_key", session=session)
            assert len(all_results) == 1

            # Now rollback - no commit
            await session.rollback()

        # After rollback, data should not exist
        result = await table.get("ryw_key")
        assert result is None

    async def test_clear_with_session_rolls_back(
        self, datastore: PostgresDatastore, table: SQLModelTable[TransactionTestModel]
    ) -> None:
        """clear() with session can be rolled back."""
        # Setup: add some data
        await table.set(
            "clear1", TransactionTestModel(id="clear1", name="one", value=1)
        )
        await table.set(
            "clear2", TransactionTestModel(id="clear2", name="two", value=2)
        )

        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as session:
            # Clear with session
            await table.clear(session=session)

            # Same session sees empty table
            assert await table.exists("clear1", session=session) is False
            assert await table.exists("clear2", session=session) is False

            # Rollback instead of commit
            await session.rollback()

        # After rollback, data should still exist
        assert await table.exists("clear1") is True
        assert await table.exists("clear2") is True
