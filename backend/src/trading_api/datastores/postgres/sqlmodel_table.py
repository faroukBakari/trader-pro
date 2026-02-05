"""SQLModel-based TableInterface implementation.

[ARCHITECTURE] Wave 2B: SQLModel Table
Replaces JSONB storage with typed columns using SQLModel ORM.
Used for tables with defined SQLModel classes (table=True).

Interface Segregation Pattern:
- SQLModelTable: Core CRUD operations (TableInterface)
- TimeSeriesSQLModelTable: Time-range queries + batch ops (TimeSeriesTableInterface)

Lazy table creation pattern matches PostgresTable behavior:
- Tables are created on first access via _ensure_table()
- Uses SQLModel.metadata.create_all(checkfirst=True) for idempotent creation
- No dependency on Alembic for initial schema bootstrap

Dynamic Table Support:
- Supports dynamic subclasses of table=True models (e.g., bars_{symbol}_{resolution})
- Creates SQLAlchemy Table objects from parent model's column definitions
- Tables are created with custom __tablename__ but parent's columns
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy import Column, CursorResult, MetaData, Table
from sqlalchemy import cast as sa_cast
from sqlalchemy import delete, func, inspect, literal, select, text
from sqlalchemy.dialects.postgresql import INT8MULTIRANGE
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.sql import quoted_name
from sqlmodel import SQLModel

from trading_api.shared.datastore_interface import (
    RangeQueryTableInterface,
    TableInterface,
    TimeSeriesTableInterface,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

    from trading_api.types import Range

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)


class SQLModelTable(TableInterface[T]):
    """TableInterface implementation using SQLModel + AsyncSession.

    Design:
    - Typed column storage (not JSONB)
    - Uses SQLModel class for schema definition
    - Supports upsert via PostgreSQL INSERT ... ON CONFLICT
    - Supports dynamic subclasses with custom __tablename__

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
            model_class: SQLModel class with table=True or dynamic subclass
            session_factory: Async session factory for database operations
            primary_key: Name of the primary key field
        """
        self._model = model_class
        self._session_factory = session_factory
        self._pk = primary_key
        self._pk_col = getattr(model_class, primary_key)
        self._initialized = False
        self._init_lock = asyncio.Lock()  # Serialize table creation
        self._table_name: str | None = None

        # Extract SQLAlchemy Table for targeted create_all
        try:
            mapper = inspect(model_class)
            assert mapper is not None
            self._sa_table: Table | None = cast(Table, mapper.persist_selectable)
            self._table_name = self._sa_table.name
        except NoInspectionAvailable:
            # Dynamic subclass - create table from parent's columns
            self._sa_table = self._create_dynamic_table(model_class, primary_key)

        # Detect range columns requiring GiST indexes (no DB access yet)
        self._gist_index_columns: list[str] = self._detect_range_columns()

    def _create_dynamic_table(
        self, model_class: type[T], primary_key: str
    ) -> Table | None:
        """Create SQLAlchemy Table for dynamic subclasses.

        For models created via BarRepository._create_bar_model(), we need
        to construct a Table with the custom __tablename__ but using
        column definitions from the parent model.

        Args:
            model_class: Dynamic subclass with __tablename__
            primary_key: Name of the primary key field

        Returns:
            SQLAlchemy Table or None if parent table not found
        """
        # Get table name from model class
        table_name = getattr(model_class, "__tablename__", None)
        if table_name is None:
            logger.warning(
                f"Cannot create dynamic table for {model_class.__name__}: "
                "no __tablename__ attribute"
            )
            return None
        self._table_name = str(table_name)

        # Find parent class with table=True to get column definitions
        from sqlalchemy.orm import Mapper

        parent_table: Table | None = None
        for parent in model_class.__mro__:
            if parent is model_class:
                continue
            if parent is SQLModel or parent is object:
                break
            try:
                parent_mapper: Mapper[Any] = inspect(parent)
                parent_table = cast(Table, parent_mapper.persist_selectable)
                break
            except NoInspectionAvailable:
                continue

        if parent_table is None:
            logger.warning(
                f"Cannot create dynamic table for {model_class.__name__}: "
                "no parent with table=True found"
            )
            return None

        # Create new table with same columns but different name
        # Use a local metadata to avoid polluting SQLModel.metadata
        local_metadata = MetaData()
        columns = [
            Column(col.name, col.type, primary_key=col.primary_key)
            for col in parent_table.columns
        ]
        dynamic_table = Table(self._table_name, local_metadata, *columns)

        logger.debug(
            f"Created dynamic table {self._table_name} from parent {parent_table.name}"
        )
        return dynamic_table

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

        async with self._init_lock:
            # Double-check after acquiring lock (another coroutine may have initialized)
            if self._initialized:
                return  # type: ignore[unreachable]

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


class TimeSeriesSQLModelTable(SQLModelTable[T], TimeSeriesTableInterface[T]):
    """SQLModelTable with timeseries operations for time-indexed data.

    Extends SQLModelTable with efficient time-range queries and batch operations.
    Use datastore.timeseries_table(model_class) to obtain this interface.

    Requirements:
        - Model must have time-based primary key (e.g., timestamp in ms)
        - Model must use SQLModel with table=True

    Usage:
        table = TimeSeriesSQLModelTable(Bar, session_factory, primary_key="time")
        bars = await table.get_time_range(from_time, to_time)
    """

    async def get_time_range(
        self,
        from_time: int,
        to_time: int,
        session: "AsyncSession | None" = None,
    ) -> list[T]:
        """Get values within time range using B-tree index.

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

        if self._sa_table is None:
            raise RuntimeError(f"No table for {self._model.__name__}")

        # Use sa_table for dynamic subclasses that aren't mapper-inspectable
        pk_col = self._sa_table.c[self._pk]

        async with self._session_scope(session) as s:
            stmt = (
                select(self._sa_table)
                .where(pk_col >= from_time)
                .where(pk_col <= to_time)
                .order_by(pk_col)
            )
            result = await s.execute(stmt)
            rows = result.fetchall()
            # Convert Row objects to model instances
            return [self._model.model_validate(dict(row._mapping)) for row in rows]

    async def set_batch(
        self,
        values: list[T],
        session: "AsyncSession | None" = None,
    ) -> int:
        """Bulk upsert values using batch INSERT...ON CONFLICT.

        Efficiently stores multiple values in a single database roundtrip.
        Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE for upsert semantics.

        Args:
            values: List of model instances to upsert
            session: Optional external session for transaction batching

        Returns:
            Number of NEW rows inserted (not updates to existing rows)
        """
        if not values:
            return 0

        await self._ensure_table()

        if self._sa_table is None:
            raise RuntimeError(f"No table for {self._model.__name__}")

        async with self._session_scope(session) as s:
            # Convert models to dicts for batch insert
            rows = [v.model_dump() for v in values]

            # Get non-PK columns for update set
            update_cols = [k for k in rows[0].keys() if k != self._pk]

            # Use sa_table for dynamic subclasses
            insert_stmt = pg_insert(self._sa_table).values(rows)
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[self._pk],
                set_={col: insert_stmt.excluded[col] for col in update_cols},
            )

            # Execute and get xmax to distinguish inserts vs updates
            # xmax=0 means newly inserted row, xmax>0 means updated existing
            returning_stmt = upsert_stmt.returning(text("(xmax = 0) AS is_insert"))
            result = await s.execute(returning_stmt)
            rows_result = result.fetchall()
            new_inserts = sum(1 for row in rows_result if row.is_insert)

        return new_inserts


class RangeQuerySQLModelTable(SQLModelTable[T], RangeQueryTableInterface[T]):
    """SQLModelTable with range query support via PostgreSQL multirange.

    Provides efficient gap detection using PostgreSQL's range_agg() aggregate
    and multirange subtraction. Uses SQLAlchemy expression API (not raw SQL)
    for type safety and statement caching.

    Requirements:
        - Model must have a Range field (e.g., time_range: Int8RangeType)
        - Model must have a grouping field (e.g., lookup_key: str)
        - PostgreSQL 14+ (for range_agg aggregate function)

    Performance:
        - Statement caching: Query compiled once, cached thereafter
        - GiST index: Overlap queries use index (O(log n))
        - Multirange ops: Native PostgreSQL, not Python iteration

    Usage:
        table = RangeQuerySQLModelTable(CoveredRange, session_factory, "id")
        gaps = await table.get_missing_ranges("AAPL_1d", IntRange(start=0, end=300))
    """

    async def get_missing_ranges(
        self,
        lookup_key: str,
        query_range: "Range[int]",
        range_field: str = "time_range",
        group_field: str = "lookup_key",
        session: "AsyncSession | None" = None,
    ) -> "list[Range[int]]":
        """Find gaps in coverage using PostgreSQL multirange subtraction.

        Executes the equivalent of:
            SELECT (int8range(from, to, '[]') - COALESCE(range_agg(time_range), '{}'))::int8multirange
            FROM table
            WHERE lookup_key = :key AND time_range && int8range(from, to, '[]')

        Args:
            lookup_key: Filter value for group_field (e.g., "AAPL_1d")
            query_range: Requested range to check coverage for
            range_field: Column name storing Range values (default: "time_range")
            group_field: Column name for filtering (default: "lookup_key")
            session: Optional session for transaction batching

        Returns:
            List of IntRange gaps that are not covered (empty list = full coverage)

        Raises:
            ValueError: If range_field or group_field don't exist on model
        """
        # Import here to avoid circular dependency at module load time
        from trading_api.types import IntRange

        await self._ensure_table()

        # Validate field names exist
        if not hasattr(self._model, range_field):
            raise ValueError(
                f"Model {self._model.__name__} has no field '{range_field}'"
            )
        if not hasattr(self._model, group_field):
            raise ValueError(
                f"Model {self._model.__name__} has no field '{group_field}'"
            )

        range_col = getattr(self._model, range_field)
        group_col = getattr(self._model, group_field)

        # Build request range using int8range() function (not literal)
        # to ensure 64-bit integer type matching the column type.
        # Use "[)" bounds (PostgreSQL canonical form for discrete ranges)
        request_range = func.int8range(
            query_range.start, query_range.end + 1, literal("[)")
        )

        # Wrap in int8multirange for subtraction (range - multirange not supported)
        request_multirange = func.int8multirange(request_range)

        # Build the gap detection expression:
        # int8multirange(request_range) - COALESCE(range_agg(covered), '{}')
        agg = func.range_agg(range_col)
        empty_multirange = sa_cast(literal("{}"), INT8MULTIRANGE)
        coalesced = func.coalesce(agg, empty_multirange)
        subtraction = request_multirange.op("-")(coalesced)
        result_expr = sa_cast(subtraction, INT8MULTIRANGE).label("gaps")

        # Build SELECT with filters
        stmt = (
            select(result_expr)
            .where(group_col == lookup_key)
            .where(range_col.op("&&")(request_range))  # Overlap filter for GiST
        )

        async with self._session_scope(session) as s:
            result = await s.execute(stmt)
            row = result.one_or_none()

            # No matching rows = full miss (nothing covered)
            if row is None or row.gaps is None:
                return [IntRange(start=query_range.start, end=query_range.end)]

            # Empty multirange = full coverage (no gaps)
            if not row.gaps:
                return []

            # Convert SQLAlchemy Range list to IntRange list
            # Adjust bounds: PostgreSQL returns "[)" canonical form
            return [
                IntRange(start=r.lower, end=r.upper - 1)
                for r in row.gaps
                if not r.isempty and r.lower is not None and r.upper is not None
            ]
