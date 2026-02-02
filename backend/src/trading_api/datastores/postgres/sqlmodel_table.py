"""SQLModel-based TableInterface implementation.

[ARCHITECTURE] Wave 2B: SQLModel Table
Replaces JSONB storage with typed columns using SQLModel ORM.
Used for tables with defined SQLModel classes (table=True).

Lazy table creation pattern matches PostgresTable behavior:
- Tables are created on first access via _ensure_table()
- Uses SQLModel.metadata.create_all(checkfirst=True) for idempotent creation
- No dependency on Alembic for initial schema bootstrap
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy import CursorResult, Table, delete, func, inspect, literal, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.sql import quoted_name
from sqlmodel import SQLModel

from trading_api.shared.datastore_interface import TableInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)


class SQLModelTable(TableInterface[T]):
    """TableInterface implementation using SQLModel + AsyncSession.

    Design:
    - Typed column storage (not JSONB)
    - Uses SQLModel class for schema definition
    - Supports upsert via PostgreSQL INSERT ... ON CONFLICT

    Usage:
        table = SQLModelTable(User, session_factory, primary_key="id")
        user = await table.get("user_123")
    """

    def __init__(
        self,
        model_class: type[T],
        session_factory: async_sessionmaker[AsyncSession],
        primary_key: str = "id",
    ) -> None:
        """Initialize SQLModelTable.

        Args:
            model_class: SQLModel class with table=True
            session_factory: Async session factory for database operations
            primary_key: Name of the primary key field
        """
        self._model = model_class
        self._session_factory = session_factory
        self._pk = primary_key
        self._pk_col = getattr(model_class, primary_key)
        self._initialized = False

        # Extract SQLAlchemy Table for targeted create_all
        try:
            mapper = inspect(model_class)
            assert mapper is not None
            self._sa_table: Table | None = cast(Table, mapper.persist_selectable)
        except NoInspectionAvailable:
            self._sa_table = None

        # Detect range columns requiring GiST indexes (no DB access yet)
        self._gist_index_columns: list[str] = self._detect_range_columns()

    def _detect_range_columns(self) -> list[str]:
        """Detect columns with range types requiring GiST indexes.

        Scans model columns for TypeDecorators with `requires_gist_index=True`
        marker attribute. Called at __init__ time (no DB access).

        Returns:
            List of column names that need GiST indexes.
        """
        if self._sa_table is None:
            return []

        range_columns: list[str] = []
        for col in self._sa_table.columns:
            col_type = col.type
            # Check for marker attribute on TypeDecorator
            if getattr(col_type, "requires_gist_index", False):
                if col.name is not None:  # Narrow type for type checker
                    range_columns.append(col.name)

        return range_columns

    @asynccontextmanager
    async def _session_scope(
        self, session: "AsyncSession | None" = None
    ) -> "AsyncIterator[AsyncSession]":
        """Context manager for session with ownership-based commit.

        If session is provided (caller owns it):
          - Yields the session as-is
          - Does NOT commit (caller is responsible)

        If session is None (we own it):
          - Creates new session from factory
          - Yields the session
          - Commits on successful exit
          - Rolls back on exception (automatic via context manager)

        This pattern enables:
          - Single-operation calls: auto-commit
          - Multi-operation transactions: caller controls commit

        Industry pattern: "Unit of Work propagation" / "Session injection"
        Reference: SQLAlchemy docs on session lifecycle management.

        Args:
            session: Optional externally-managed session

        Yields:
            AsyncSession for database operations
        """
        if session is not None:
            # Caller owns transaction - yield without commit
            yield session
        else:
            # We own transaction - commit on success
            async with self._session_factory() as owned_session:
                yield owned_session
                await owned_session.commit()

    async def _create_gist_index(
        self,
        conn: AsyncConnection,
        table_name: str,
        col_name: str,
    ) -> None:
        """Create GiST index on a range column (idempotent).

        Uses CREATE INDEX IF NOT EXISTS for safe concurrent execution.
        Only executes on PostgreSQL dialect.

        Args:
            conn: Database connection
            table_name: Table name
            col_name: Column name to index
        """
        # Only create GiST on PostgreSQL
        dialect_name = conn.dialect.name
        if dialect_name != "postgresql":
            logger.debug(f"Skipping GiST index on {dialect_name} (not supported)")
            return

        idx_name = f"idx_{table_name}_{col_name}_gist"

        # Use quoted_name for SQL injection safety
        safe_table = quoted_name(table_name, quote=True)
        safe_idx = quoted_name(idx_name, quote=True)
        safe_col = quoted_name(col_name, quote=True)

        await conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {safe_idx} "
                f"ON {safe_table} USING gist ({safe_col})"
            )
        )
        logger.info(f"Created GiST index {idx_name} on {table_name}.{col_name}")

    async def _ensure_table(self) -> None:
        """Create table and GiST indexes if not exists (idempotent).

        Uses SQLModel.metadata.create_all with checkfirst=True to safely
        create only missing tables. Then creates GiST indexes for any
        detected range columns. Matches PostgresTable._ensure_table() pattern.
        """
        if self._initialized:
            return

        sa_table = self._sa_table
        if sa_table is None:
            logger.warning(
                f"Cannot auto-create table for {self._model.__name__}: "
                "no SQLAlchemy table mapping found"
            )
            self._initialized = True
            return

        table_name = getattr(sa_table, "name", self._model.__name__)

        async with self._session_factory() as session:
            conn = await session.connection()

            # Step 1: Create table
            await conn.run_sync(
                lambda sync_conn: sa_table.create(sync_conn, checkfirst=True)
            )

            # Step 2: Create GiST indexes for detected range columns
            for col_name in self._gist_index_columns:
                await self._create_gist_index(conn, table_name, col_name)

            await session.commit()  # DDL needs explicit commit

        logger.debug(f"Ensured table exists: {table_name}")
        self._initialized = True

    async def get(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> T | None:
        """Get by primary key or indexed field.

        Args:
            key: Primary key or indexed field value
            index: Optional index field name
            session: Optional external session for transaction batching
        """
        await self._ensure_table()
        async with self._session_scope(session) as s:
            if index is None:
                stmt = select(self._model).where(self._pk_col == key)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(self._model).where(idx_col == key).limit(1)

            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> list[T]:
        """Get all matching by primary key or indexed field.

        Args:
            key: Primary key or indexed field value
            index: Optional index field name
            session: Optional external session for transaction batching
        """
        await self._ensure_table()
        async with self._session_scope(session) as s:
            if index is None:
                stmt = select(self._model).where(self._pk_col == key)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(self._model).where(idx_col == key)

            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def set(
        self,
        key: str,
        value: BaseModel,
        session: "AsyncSession | None" = None,
    ) -> None:
        """Upsert by key using INSERT ... ON CONFLICT.

        Args:
            key: Primary key value
            value: Model to upsert
            session: Optional external session for transaction batching
        """
        await self._ensure_table()

        async with self._session_scope(session) as s:
            # Ensure key is set on the model
            value_dict = value.model_dump()
            value_dict[self._pk] = key

            # PostgreSQL upsert
            stmt = pg_insert(self._model).values(**value_dict)
            stmt = stmt.on_conflict_do_update(
                index_elements=[self._pk],
                set_={k: v for k, v in value_dict.items() if k != self._pk},
            )

            await s.execute(stmt)
            # Note: commit handled by _session_scope if we own the session

    # ────────────────────────────────────────────────────────────────────────
    # Timeseries / Bulk Operations
    # ────────────────────────────────────────────────────────────────────────

    async def get_many(
        self,
        from_time: int,
        to_time: int,
        session: "AsyncSession | None" = None,
    ) -> list[T]:
        """Get values within time range using B-tree index. [TIMESERIES]

        Efficient range query leveraging the primary key index on time column.
        Returns results ordered by primary key (time) ascending.

        Args:
            from_time: Range start (inclusive), typically milliseconds timestamp
            to_time: Range end (inclusive), typically milliseconds timestamp
            session: Optional external session for transaction batching

        Returns:
            List of values ordered by time ascending
        """
        await self._ensure_table()
        async with self._session_scope(session) as s:
            stmt = (
                select(self._model)
                .where(self._pk_col >= from_time)
                .where(self._pk_col <= to_time)
                .order_by(self._pk_col)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def set_many(
        self,
        values: list[T],
        session: "AsyncSession | None" = None,
    ) -> int:
        """Bulk upsert values using batch INSERT...ON CONFLICT. [BATCH]

        Efficiently stores multiple values in a single database roundtrip.
        Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE for upsert semantics.

        Args:
            values: List of model instances to upsert
            session: Optional external session for transaction batching

        Returns:
            Number of values processed (note: doesn't distinguish inserts vs updates)
        """
        if not values:
            return 0

        await self._ensure_table()

        async with self._session_scope(session) as s:
            # Convert models to dicts for batch insert
            rows = [v.model_dump() for v in values]

            # Get non-PK columns for update set
            update_cols = [k for k in rows[0].keys() if k != self._pk]

            # PostgreSQL batch upsert
            stmt = pg_insert(self._model).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[self._pk],
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            await s.execute(stmt)

        return len(values)

    async def delete(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> bool:
        """Delete by primary key or indexed field.

        Args:
            key: Key value to match
            index: Optional index field name
            session: Optional external session for transaction batching

        Returns:
            True if rows were deleted
        """
        await self._ensure_table()

        async with self._session_scope(session) as s:
            if index is None:
                stmt = delete(self._model).where(self._pk_col == key)
            else:
                idx_col = getattr(self._model, index)
                stmt = delete(self._model).where(idx_col == key)

            result = await s.execute(stmt)
            # Cast to CursorResult for DML statements
            cursor = cast(CursorResult[Any], result)
            return bool(cursor.rowcount and cursor.rowcount > 0)
            # Note: commit handled by _session_scope if we own the session

    async def exists(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> bool:
        """Check existence by primary key or indexed field.

        Args:
            key: Primary key or indexed field value
            index: Optional index field name
            session: Optional external session for transaction batching
        """
        await self._ensure_table()
        async with self._session_scope(session) as s:
            if index is None:
                stmt = select(literal(1)).where(self._pk_col == key).limit(1)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(literal(1)).where(idx_col == key).limit(1)

            result = await s.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def keys(self, index: str | None = None) -> list[str]:
        """Get all primary keys or distinct indexed values."""
        await self._ensure_table()
        async with self._session_factory() as session:
            if index is None:
                stmt = select(self._pk_col)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(idx_col).distinct()

            result = await session.execute(stmt)
            return [str(row[0]) for row in result.all()]

    async def values(self) -> list[T]:
        """Get all records."""
        await self._ensure_table()
        async with self._session_factory() as session:
            result = await session.execute(select(self._model))
            return list(result.scalars().all())

    async def clear(self, session: "AsyncSession | None" = None) -> None:
        """Delete all rows from table.

        Args:
            session: Optional external session for transaction batching
        """
        await self._ensure_table()
        async with self._session_scope(session) as s:
            await s.execute(delete(self._model))

    async def count(self) -> int:
        """Count records."""
        await self._ensure_table()
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(self._model)
            )
            return result.scalar() or 0

    @property
    async def is_empty(self) -> bool:
        """Check if table has zero entries."""
        await self._ensure_table()
        async with self._session_factory() as session:
            stmt = select(literal(1)).select_from(self._model).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is None

    async def iterate(self) -> AsyncIterator[tuple[str, T]]:
        """Iterate over (key, record) pairs."""
        await self._ensure_table()
        async with self._session_factory() as session:
            result = await session.stream(select(self._model))
            async for row in result:
                record = row[0]
                key = str(getattr(record, self._pk))
                yield key, record
