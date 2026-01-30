"""PostgreSQL datastore implementation.

[ARCHITECTURE] Wave 2A + 2B: Dual-mode datastore
- PostgresTable: JSONB storage for legacy/flexible schemas (Wave 2A)
- SQLModelTable: Typed column storage for SQLModel entities (Wave 2B)

This module provides:
- PostgresDatastore: Connection pool management with async factory
- PostgresTable: TableInterface implementation using JSONB storage
- table(): Unified API that auto-detects storage mode from model class

[SECURITY] Uses psycopg3's sql.SQL/sql.Identifier for safe SQL composition,
eliminating SQL injection vulnerabilities from dynamic table/field names.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool, AsyncNullConnectionPool
from pydantic import BaseModel
from sqlalchemy import Table, inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import Mapper
from sqlmodel import SQLModel

from trading_api.shared import DatastoreInterface, TableInterface
from trading_api.shared.config import Settings

from .engine import (
    AsyncEngineFactory,
    ConnectionTimeoutError,
    check_database_exists,
    parse_dsn,
)
from .sql_safe import validate_identifier
from .sqlmodel_table import SQLModelTable

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

__all__ = ["PostgresDatastore", "PostgresTable", "SQLModelTable"]


def get_table_name(model_class: type) -> str | None:
    """Get table name from SQLModel class if table=True, else None."""
    try:
        mapper: Mapper[Any] = inspect(model_class)
        table: Table = cast(Table, mapper.persist_selectable)
        return table.name
    except NoInspectionAvailable:
        return None


def extract_indexes(
    model_class: type[SQLModel],
) -> tuple[list[str], list[str], str | None]:
    """Extract index metadata from SQLModel Field() declarations.

    Reads index=True, unique=True, and primary_key=True from FieldInfo.
    Works for both table=True and table=False models.

    Returns:
        (indexes, unique_indexes, primary_key) tuple where:
        - indexes: Fields with index=True (non-unique secondary indexes)
        - unique_indexes: Fields with unique=True
        - primary_key: Field with primary_key=True (or None)
    """
    indexes: list[str] = []
    unique_indexes: list[str] = []
    primary_key: str | None = None

    for field_name, field_info in model_class.model_fields.items():
        # Check for primary_key (only in SQLModel FieldInfo)
        if getattr(field_info, "primary_key", None) is True:
            primary_key = field_name

        # Check for unique constraint
        if getattr(field_info, "unique", None) is True:
            unique_indexes.append(field_name)

        # Check for index (non-unique) - only add if not already unique
        if (
            getattr(field_info, "index", None) is True
            and field_name not in unique_indexes
        ):
            indexes.append(field_name)

    return indexes, unique_indexes, primary_key


class PostgresTable(TableInterface[Any]):
    """PostgreSQL table implementation using JSONB storage.

    Returns dict values (not BaseModel) - caller handles Pydantic conversion
    via Model.model_validate(). This matches the Wave 2A JSONB approach.

    [SECURITY] All SQL uses psycopg3's sql.SQL/sql.Identifier composition
    to prevent SQL injection from dynamic table/field names.

    Schema per table (created on first access):
        CREATE TABLE IF NOT EXISTS {table_name} (
            key TEXT PRIMARY KEY,
            value JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

    Index patterns:
        - Secondary index (1:N): CREATE INDEX idx_{table}_{field} ON {table} ((value->>'{field}'))
        - Unique index (1:1): CREATE UNIQUE INDEX uidx_{table}_{field} ON {table} ((value->>'{field}'))
    """

    def __init__(
        self,
        pool: AsyncConnectionPool[AsyncConnection[Any]],
        table_name: str,
        indexes: list[str] | None = None,
        unique_indexes: list[str] | None = None,
    ) -> None:
        # Validate table name at construction time
        validate_identifier(table_name, "table name")
        for idx in indexes or []:
            validate_identifier(idx, "index field")
        for idx in unique_indexes or []:
            validate_identifier(idx, "unique index field")

        self._pool = pool
        self._table_name = table_name
        self._indexes = indexes or []
        self._unique_indexes = unique_indexes or []
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def _ensure_table(self) -> None:
        """Create table and indexes if not exists (idempotent).

        Uses asyncio.Lock to serialize concurrent table creation attempts,
        preventing race conditions in concurrent writes.
        """
        if self._initialized:
            return

        async with self._init_lock:
            # Double-check after acquiring lock (another coroutine may have initialized)
            if self._initialized:
                return  # type: ignore[unreachable]

            async with self._pool.connection() as conn:
                try:
                    # Create table with JSONB value column
                    await conn.execute(
                        sql.SQL(
                            """
                            CREATE TABLE IF NOT EXISTS {} (
                                key TEXT PRIMARY KEY,
                                value JSONB NOT NULL,
                                created_at TIMESTAMPTZ DEFAULT NOW(),
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            )
                            """
                        ).format(sql.Identifier(self._table_name))
                    )

                    # Create secondary indexes (1:N mapping)
                    for field in self._indexes:
                        await conn.execute(
                            sql.SQL(
                                "CREATE INDEX IF NOT EXISTS {} ON {} ((value->>{}))"
                            ).format(
                                sql.Identifier(f"idx_{self._table_name}_{field}"),
                                sql.Identifier(self._table_name),
                                sql.Literal(field),
                            )
                        )

                    # Create unique indexes (1:1 mapping)
                    for field in self._unique_indexes:
                        await conn.execute(
                            sql.SQL(
                                "CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} ((value->>{}))"
                            ).format(
                                sql.Identifier(f"uidx_{self._table_name}_{field}"),
                                sql.Identifier(self._table_name),
                                sql.Literal(field),
                            )
                        )
                except Exception:
                    # Table may already exist from concurrent creation - re-raise if not
                    # Check if table exists now and skip error if so
                    result = await conn.execute(
                        sql.SQL(
                            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = {})"
                        ).format(sql.Literal(self._table_name))
                    )
                    row = await result.fetchone()
                    if not row or not row[0]:
                        raise  # Re-raise if table doesn't exist (real error)

            self._initialized = True

    async def get(self, key: str, index: str | None = None) -> Any:
        """Get a value by key or indexed field.

        Returns dict (caller handles Pydantic conversion via model_validate).
        Note: Type is Any since JSONB returns dict, not BaseModel.
        Repository layer calls Model.model_validate() for conversion.
        """
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if index is None:
                    query = sql.SQL("SELECT value FROM {} WHERE key = %s").format(
                        sql.Identifier(self._table_name)
                    )
                    await cur.execute(query, (key,))
                else:
                    validate_identifier(index, "index field")
                    query = sql.SQL(
                        "SELECT value FROM {} WHERE value->>{} = %s LIMIT 1"
                    ).format(
                        sql.Identifier(self._table_name),
                        sql.Literal(index),
                    )
                    await cur.execute(query, (key,))

                result = await cur.fetchone()
                if result is None:
                    return None
                # Return dict - caller uses Model.model_validate() for conversion
                return result["value"]

    async def get_all(self, key: str, index: str | None = None) -> list[Any]:
        """Get all values by key or indexed field.

        Returns list of dicts - caller handles Pydantic conversion.
        """
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if index is None:
                    query = sql.SQL("SELECT value FROM {} WHERE key = %s").format(
                        sql.Identifier(self._table_name)
                    )
                    await cur.execute(query, (key,))
                else:
                    validate_identifier(index, "index field")
                    query = sql.SQL(
                        "SELECT value FROM {} WHERE value->>{} = %s"
                    ).format(
                        sql.Identifier(self._table_name),
                        sql.Literal(index),
                    )
                    await cur.execute(query, (key,))

                rows = await cur.fetchall()
                return [row["value"] for row in rows]

    async def set(self, key: str, value: BaseModel) -> None:
        """Set a value by key (upsert pattern)."""
        await self._ensure_table()

        # Convert Pydantic model to dict wrapped in Jsonb for proper encoding
        value_dict = value.model_dump(mode="json")

        async with self._pool.connection() as conn:
            query = sql.SQL(
                """
                INSERT INTO {} (key, value, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = NOW()
                """
            ).format(sql.Identifier(self._table_name))
            await conn.execute(query, (key, Jsonb(value_dict)))

    async def delete(self, key: str, index: str | None = None) -> bool:
        """Delete a value by key or indexed field."""
        await self._ensure_table()

        async with self._pool.connection() as conn:
            if index is None:
                query = sql.SQL("DELETE FROM {} WHERE key = %s").format(
                    sql.Identifier(self._table_name)
                )
                cursor = await conn.execute(query, (key,))
            else:
                validate_identifier(index, "index field")
                query = sql.SQL("DELETE FROM {} WHERE value->>{} = %s").format(
                    sql.Identifier(self._table_name),
                    sql.Literal(index),
                )
                cursor = await conn.execute(query, (key,))

            # psycopg3 returns rowcount from cursor
            return int(cursor.rowcount) > 0

    async def exists(self, key: str, index: str | None = None) -> bool:
        """Check if a key or indexed value exists."""
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                if index is None:
                    query = sql.SQL("SELECT 1 FROM {} WHERE key = %s LIMIT 1").format(
                        sql.Identifier(self._table_name)
                    )
                    await cur.execute(query, (key,))
                else:
                    validate_identifier(index, "index field")
                    query = sql.SQL(
                        "SELECT 1 FROM {} WHERE value->>{} = %s LIMIT 1"
                    ).format(
                        sql.Identifier(self._table_name),
                        sql.Literal(index),
                    )
                    await cur.execute(query, (key,))

                row = await cur.fetchone()
                return row is not None

    async def keys(self, index: str | None = None) -> list[str]:
        """Get all keys or indexed values."""
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if index is None:
                    query = sql.SQL("SELECT key FROM {}").format(
                        sql.Identifier(self._table_name)
                    )
                    await cur.execute(query)
                    rows = await cur.fetchall()
                    return [row["key"] for row in rows]
                else:
                    validate_identifier(index, "index field")
                    query = sql.SQL(
                        "SELECT DISTINCT value->>{} as idx_val FROM {} "
                        "WHERE value->>{} IS NOT NULL"
                    ).format(
                        sql.Literal(index),
                        sql.Identifier(self._table_name),
                        sql.Literal(index),
                    )
                    await cur.execute(query)
                    rows = await cur.fetchall()
                    return [row["idx_val"] for row in rows]

    async def values(self) -> list[Any]:
        """Get all values in the table.

        Returns list of dicts - caller handles Pydantic conversion.
        """
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = sql.SQL("SELECT value FROM {}").format(
                    sql.Identifier(self._table_name)
                )
                await cur.execute(query)
                rows = await cur.fetchall()
                return [row["value"] for row in rows]

    async def clear(self) -> None:
        """Remove all entries from the table."""
        await self._ensure_table()

        async with self._pool.connection() as conn:
            query = sql.SQL("TRUNCATE TABLE {}").format(
                sql.Identifier(self._table_name)
            )
            await conn.execute(query)

    async def count(self) -> int:
        """Get the count of entries in the table."""
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = sql.SQL("SELECT COUNT(*) as cnt FROM {}").format(
                    sql.Identifier(self._table_name)
                )
                await cur.execute(query)
                row = await cur.fetchone()
                return int(row["cnt"]) if row else 0

    @property
    async def is_empty(self) -> bool:
        """Check if table has zero entries."""
        return await self.count() == 0

    async def iterate(self) -> AsyncIterator[tuple[str, Any]]:
        """Asynchronously iterate over key-value pairs.

        Yields (key, dict) tuples - caller handles Pydantic conversion.
        """
        await self._ensure_table()

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = sql.SQL("SELECT key, value FROM {}").format(
                    sql.Identifier(self._table_name)
                )
                await cur.execute(query)
                async for row in cur:
                    yield row["key"], row["value"]

    async def create_index(self, field_name: str) -> None:
        """Create an index on a specified field."""
        validate_identifier(field_name, "field name")
        await self._ensure_table()

        async with self._pool.connection() as conn:
            query = sql.SQL(
                "CREATE INDEX IF NOT EXISTS {} ON {} ((value->>{}))"
            ).format(
                sql.Identifier(f"idx_{self._table_name}_{field_name}"),
                sql.Identifier(self._table_name),
                sql.Literal(field_name),
            )
            await conn.execute(query)

        if field_name not in self._indexes:
            self._indexes.append(field_name)

    async def create_unique_index(self, field_name: str) -> None:
        """Create a unique index on a specified field.

        Raises ValueError if duplicate field values exist in current data.
        """
        validate_identifier(field_name, "field name")
        await self._ensure_table()

        async with self._pool.connection() as conn:
            # Check for duplicates first
            async with conn.cursor(row_factory=dict_row) as cur:
                check_query = sql.SQL(
                    """
                    SELECT value->>{} as field_val, COUNT(*) as cnt
                    FROM {}
                    WHERE value->>{} IS NOT NULL
                    GROUP BY value->>{}
                    HAVING COUNT(*) > 1
                    LIMIT 1
                    """
                ).format(
                    sql.Literal(field_name),
                    sql.Identifier(self._table_name),
                    sql.Literal(field_name),
                    sql.Literal(field_name),
                )
                await cur.execute(check_query)
                row = await cur.fetchone()

                if row:
                    raise ValueError(
                        f"Duplicate value '{row['field_val']}' for unique field '{field_name}'"
                    )

            # Create the index
            create_query = sql.SQL(
                "CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} ((value->>{}))"
            ).format(
                sql.Identifier(f"uidx_{self._table_name}_{field_name}"),
                sql.Identifier(self._table_name),
                sql.Literal(field_name),
            )
            await conn.execute(create_query)

        if field_name not in self._unique_indexes:
            self._unique_indexes.append(field_name)


def _is_testing() -> bool:
    """Detect if running inside pytest via PYTEST_CURRENT_TEST env var."""
    return os.environ.get("PYTEST_CURRENT_TEST") is not None


class PostgresDatastore(DatastoreInterface):
    """PostgreSQL datastore using psycopg3 connection pool.

    [ARCHITECTURE] Wave 2B: Unified table() API with auto-detection
    - table=True models → SQLModelTable (typed columns via SQLAlchemy)
    - table=False models → PostgresTable (JSONB storage with extracted indexes)

    Uses async factory pattern since pool creation is async:
        ds = await PostgresDatastore.create()

    Features:
    - JSONB storage for schema flexibility (Wave 2A)
    - SQLModel typed columns for performance (Wave 2B)
    - Connection pool with min/max size
    - Graceful shutdown via close()
    - [SECURITY] sql.SQL composition for injection-safe queries
    """

    def __init__(
        self,
        pool: AsyncConnectionPool[AsyncConnection[Any]],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize with existing pool (use create() factory instead)."""
        self._pool = pool
        self._session_factory = session_factory
        self._tables: dict[str, PostgresTable] = {}
        self._typed_tables: dict[str, SQLModelTable[Any]] = {}

    @classmethod
    async def create(
        cls,
        config: Settings | None = None,
    ) -> PostgresDatastore:
        """Async factory - required because pool creation is async.

        Args:
            config: Optional Settings instance for dependency injection (tests).
                   Defaults to global settings singleton.

        All configuration is read from settings (12-Factor compliant):
        - DSN: settings.postgres_dsn (from DATASTORE_POSTGRES_DSN or components)
        - Pool size: settings.DATASTORE_POSTGRES_POOL_MAX_SIZE
        - Timeouts: settings.DATASTORE_POSTGRES_POOL_*

        Auto-detects test mode via PYTEST_CURRENT_TEST env var to use
        NullConnectionPool (no background workers) preventing teardown hangs.

        Returns:
            PostgresDatastore instance with active connection pool

        Raises:
            ValueError: If PostgreSQL DSN is not configured
        """
        # [12-FACTOR] Config from injected settings or global singleton
        # Deferred import for SSOT - allows tests to inject config without module-level coupling
        from trading_api.shared.config import settings as default_settings

        cfg = config or default_settings
        dsn = cfg.postgres_dsn
        if not dsn:
            raise ValueError(
                "PostgreSQL DSN not configured. "
                "Set DATASTORE_POSTGRES_DSN or individual DATASTORE_POSTGRES_* vars in .env"
            )

        max_size = cfg.DATASTORE_POSTGRES_POOL_MAX_SIZE
        reconnect_timeout = cfg.DATASTORE_POSTGRES_POOL_RECONNECT_TIMEOUT
        open_timeout = cfg.DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT

        # Auto-detect pytest: use NullConnectionPool (no background workers)
        warm_bg_workers = not _is_testing()

        # [FAIL-FAST] Pre-flight check: verify database exists before attempting pool connection
        # This catches "database does not exist" errors immediately with clear remediation steps
        check_database_exists(dsn)

        # Create async connection pool with psycopg3
        # Note: psycopg3 handles JSONB encoding/decoding natively
        # [SHUTDOWN] reconnect_timeout + reconnect_failed prevent hangs when DB unavailable
        cnx_pool_type = (
            AsyncConnectionPool if warm_bg_workers else AsyncNullConnectionPool
        )
        pool = cnx_pool_type(
            conninfo=dsn,
            min_size=0 if not warm_bg_workers else 1,
            max_size=max_size,
            open=False,  # Manual open for async context
            reconnect_timeout=reconnect_timeout,
        )

        # [BOUNDED-TIMEOUT] Wrap pool.open() to prevent infinite retry hangs
        # This ensures Ctrl+C responsiveness and fail-fast on server down
        _, _, host, port, _ = parse_dsn(dsn)
        try:
            await asyncio.wait_for(pool.open(), timeout=open_timeout)
        except asyncio.TimeoutError:
            raise ConnectionTimeoutError(host, port, open_timeout) from None

        # Also create session factory for SQLModel tables (Wave 2B)
        session_factory = await AsyncEngineFactory.get_session_factory(dsn)

        # [EAGER SCHEMA] Create all SQLModel table=True tables at startup
        # This ensures schema exists before any operations, avoiding lazy init issues
        engine = await AsyncEngineFactory.get_engine(dsn)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        return cls(pool, session_factory)

    @property
    def has_persistence(self) -> bool:
        """PostgreSQL persists data across restarts."""
        return True

    @property
    def has_transactions(self) -> bool:
        """PostgreSQL supports ACID transactions."""
        return True

    @property
    def is_relational(self) -> bool:
        """PostgreSQL is a SQL-based relational database."""
        return True

    def table(
        self,
        model_class: type[SQLModel],
        primary_key: str = "id",
    ) -> TableInterface[Any]:
        """Get or create a table for the given SQLModel class.

        [ARCHITECTURE] Unified Wave 2A/2B: Auto-detects storage mode.
        - table=True models → SQLModelTable (typed columns via SQLAlchemy)
        - table=False models → PostgresTable (JSONB storage with extracted indexes)

        Index configuration is extracted from Field() metadata:
        - index=True → secondary index
        - unique=True → unique index
        - primary_key=True → primary key field

        Args:
            model_class: SQLModel class (table=True or table=False)
            primary_key: Primary key field name (default "id", extracted from Field if declared)

        Returns:
            TableInterface for the model
        """
        # Check if this is a table=True model
        table_name = get_table_name(model_class)

        if table_name is not None:
            # Wave 2B: SQLModel with typed columns
            if self._session_factory is None:
                raise RuntimeError(
                    "Session factory not initialized. "
                    "Use PostgresDatastore.create() factory method."
                )

            if table_name not in self._typed_tables:
                # Extract primary_key from Field() if available
                _, _, extracted_pk = extract_indexes(model_class)
                pk = extracted_pk or primary_key

                self._typed_tables[table_name] = SQLModelTable(
                    model_class=model_class,
                    session_factory=self._session_factory,
                    primary_key=pk,
                )
            return self._typed_tables[table_name]
        else:
            # Wave 2A: JSONB storage with extracted indexes
            name = getattr(model_class, "__tablename__", None)
            if name is None:
                raise ValueError(
                    "Model class must have __tablename__ attribute for JSONB storage"
                )
            if name not in self._tables:
                indexes, unique_indexes, extracted_pk = extract_indexes(model_class)
                # Use extracted primary_key if available, otherwise use parameter
                _ = (
                    extracted_pk or primary_key
                )  # Not used for JSONB but could be in future

                self._tables[name] = PostgresTable(
                    pool=self._pool,
                    table_name=name,
                    indexes=indexes,
                    unique_indexes=unique_indexes,
                )
            return self._tables[name]

    async def list_tables(self, prefix: str | None = None) -> list[str]:
        """List all table names in the datastore.

        Queries information_schema for tables in the public schema.
        This captures dynamically-created tables (e.g., bar tables) that
        are not tracked in the internal _tables cache.

        Args:
            prefix: Optional prefix filter (e.g., "bars_" for bar tables)

        Returns:
            List of table names matching the prefix filter
        """
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if prefix:
                    await cur.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name LIKE %s",
                        (f"{prefix}%",),
                    )
                else:
                    await cur.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                rows = await cur.fetchall()
                return [row["table_name"] for row in rows]

    async def drop_table(self, name: str) -> bool:
        """Drop a table by name.

        Executes DROP TABLE IF EXISTS and removes from internal tracking.

        Args:
            name: Table name to drop

        Returns:
            True if table was dropped, False if it didn't exist
        """
        validate_identifier(name, "table name")

        # Check if table exists first
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = %s"
                    ")",
                    (name,),
                )
                row = await cur.fetchone()
                if not row or not row["exists"]:
                    return False

            # Drop the table
            await conn.execute(
                sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(name))
            )

        # Remove from internal caches
        self._tables.pop(name, None)
        self._typed_tables.pop(name, None)

        return True

    async def close(self) -> None:
        """Graceful shutdown - close connection pool and dispose engine."""
        await self._pool.close()
        await AsyncEngineFactory.dispose()
