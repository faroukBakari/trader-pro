"""PostgreSQL datastore implementation with asyncpg + JSONB storage.

This module provides:
- PostgresDatastore: Connection pool management with async factory
- PostgresTable: TableInterface implementation using JSONB storage

Design decisions:
- Async factory pattern required (asyncpg pool creation is async)
- JSONB storage enables schema flexibility for Wave 2A
- Caller handles Pydantic model conversion (returns dict from get())
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from trading_api.shared import DatastoreInterface, TableInterface

if TYPE_CHECKING:
    import asyncpg

__all__ = ["PostgresDatastore", "PostgresTable"]


class PostgresTable(TableInterface[Any]):
    """PostgreSQL table implementation using JSONB storage.

    Returns dict values (not BaseModel) - caller handles Pydantic conversion
    via Model.model_validate(). This matches the Wave 2A JSONB approach.

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
        pool: asyncpg.Pool[asyncpg.Record],
        table_name: str,
        indexes: list[str] | None = None,
        unique_indexes: list[str] | None = None,
    ) -> None:
        self._pool = pool
        self._table_name = table_name
        self._indexes = indexes or []
        self._unique_indexes = unique_indexes or []
        self._initialized = False

    async def _ensure_table(self) -> None:
        """Create table and indexes if not exists (idempotent)."""
        if self._initialized:
            return

        async with self._pool.acquire() as conn:
            # Create table with JSONB value column
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Create secondary indexes (1:N mapping)
            for field in self._indexes:
                await conn.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{self._table_name}_{field}
                    ON {self._table_name} ((value->>'{field}'))
                """
                )

            # Create unique indexes (1:1 mapping)
            for field in self._unique_indexes:
                await conn.execute(
                    f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS uidx_{self._table_name}_{field}
                    ON {self._table_name} ((value->>'{field}'))
                """
                )

        self._initialized = True

    async def get(self, key: str, index: str | None = None) -> Any:
        """Get a value by key or indexed field.

        Returns dict (caller handles Pydantic conversion via model_validate).
        Note: Type is Any since JSONB returns dict, not BaseModel.
        Repository layer calls Model.model_validate() for conversion.
        """
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            if index is None:
                row = await conn.fetchrow(
                    f"SELECT value FROM {self._table_name} WHERE key = $1",
                    key,
                )
            else:
                row = await conn.fetchrow(
                    f"SELECT value FROM {self._table_name} WHERE value->>'{index}' = $1 LIMIT 1",
                    key,
                )

            if row is None:
                return None
            # Return dict - caller uses Model.model_validate() for conversion
            return row["value"]

    async def get_all(self, key: str, index: str | None = None) -> list[Any]:
        """Get all values by key or indexed field.

        Returns list of dicts - caller handles Pydantic conversion.
        """
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            if index is None:
                rows = await conn.fetch(
                    f"SELECT value FROM {self._table_name} WHERE key = $1",
                    key,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT value FROM {self._table_name} WHERE value->>'{index}' = $1",
                    key,
                )

            return [row["value"] for row in rows]

    async def set(self, key: str, value: BaseModel) -> None:
        """Set a value by key (upsert pattern)."""
        await self._ensure_table()

        # Convert Pydantic model to dict - JSONB codec handles JSON encoding
        # Note: Do NOT use model_dump_json() as that returns a string which
        # would get double-encoded by the JSONB codec's json.dumps encoder
        value_dict = value.model_dump(mode="json")

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self._table_name} (key, value, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = $2,
                    updated_at = NOW()
                """,
                key,
                value_dict,
            )

    async def delete(self, key: str, index: str | None = None) -> bool:
        """Delete a value by key or indexed field."""
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            if index is None:
                result = await conn.execute(
                    f"DELETE FROM {self._table_name} WHERE key = $1",
                    key,
                )
            else:
                result = await conn.execute(
                    f"DELETE FROM {self._table_name} WHERE value->>'{index}' = $1",
                    key,
                )

            # asyncpg returns "DELETE N" where N is rows affected
            return result != "DELETE 0"

    async def exists(self, key: str, index: str | None = None) -> bool:
        """Check if a key or indexed value exists."""
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            if index is None:
                row = await conn.fetchrow(
                    f"SELECT 1 FROM {self._table_name} WHERE key = $1 LIMIT 1",
                    key,
                )
            else:
                row = await conn.fetchrow(
                    f"SELECT 1 FROM {self._table_name} WHERE value->>'{index}' = $1 LIMIT 1",
                    key,
                )

            return row is not None

    async def keys(self, index: str | None = None) -> list[str]:
        """Get all keys or indexed values."""
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            if index is None:
                rows = await conn.fetch(f"SELECT key FROM {self._table_name}")
                return [row["key"] for row in rows]
            else:
                rows = await conn.fetch(
                    f"SELECT DISTINCT value->>'{index}' as idx_val FROM "
                    f"{self._table_name} WHERE value->>'{index}' IS NOT NULL"
                )
                return [row["idx_val"] for row in rows]

    async def values(self) -> list[Any]:
        """Get all values in the table.

        Returns list of dicts - caller handles Pydantic conversion.
        """
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT value FROM {self._table_name}")
            return [row["value"] for row in rows]

    async def clear(self) -> None:
        """Remove all entries from the table."""
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            await conn.execute(f"TRUNCATE TABLE {self._table_name}")

    async def count(self) -> int:
        """Get the count of entries in the table."""
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {self._table_name}")
            return int(row["cnt"]) if row else 0

    async def iterate(self) -> AsyncIterator[tuple[str, Any]]:
        """Asynchronously iterate over key-value pairs.

        Yields (key, dict) tuples - caller handles Pydantic conversion.
        """
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                async for row in conn.cursor(
                    f"SELECT key, value FROM {self._table_name}"
                ):
                    yield row["key"], row["value"]

    async def create_index(self, field_name: str) -> None:
        """Create an index on a specified field."""
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table_name}_{field_name}
                ON {self._table_name} ((value->>'{field_name}'))
            """
            )

        if field_name not in self._indexes:
            self._indexes.append(field_name)

    async def create_unique_index(self, field_name: str) -> None:
        """Create a unique index on a specified field.

        Raises ValueError if duplicate field values exist in current data.
        """
        await self._ensure_table()

        async with self._pool.acquire() as conn:
            # Check for duplicates first
            row = await conn.fetchrow(
                f"""
                SELECT value->>'{field_name}' as field_val, COUNT(*) as cnt
                FROM {self._table_name}
                WHERE value->>'{field_name}' IS NOT NULL
                GROUP BY value->>'{field_name}'
                HAVING COUNT(*) > 1
                LIMIT 1
            """
            )

            if row:
                raise ValueError(
                    f"Duplicate value '{row['field_val']}' for unique field '{field_name}'"
                )

            await conn.execute(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uidx_{self._table_name}_{field_name}
                ON {self._table_name} ((value->>'{field_name}'))
            """
            )

        if field_name not in self._unique_indexes:
            self._unique_indexes.append(field_name)


def _build_dsn() -> str:
    """Build PostgreSQL DSN from environment variables.

    Priority:
    1. DATASTORE_POSTGRES_DSN (full connection string)
    2. Individual vars: DATASTORE_POSTGRES_USER, _PASSWORD, _HOST, _PORT, _DB
    """
    dsn = os.environ.get("DATASTORE_POSTGRES_DSN")
    if dsn:
        return dsn

    user = os.environ.get("DATASTORE_POSTGRES_USER", "trader")
    password = os.environ.get("DATASTORE_POSTGRES_PASSWORD", "trader_dev")
    host = os.environ.get("DATASTORE_POSTGRES_HOST", "localhost")
    port = os.environ.get("DATASTORE_POSTGRES_PORT", "5433")
    db = os.environ.get("DATASTORE_POSTGRES_DB", "trader_bars")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


class PostgresDatastore(DatastoreInterface):
    """PostgreSQL datastore using asyncpg connection pool.

    Uses async factory pattern since pool creation is async:
        ds = await PostgresDatastore.create()

    Features:
    - JSONB storage for schema flexibility
    - Connection pool with min/max size
    - Graceful shutdown via close()
    """

    def __init__(self, pool: asyncpg.Pool[asyncpg.Record]) -> None:
        """Initialize with existing pool (use create() factory instead)."""
        self._pool = pool
        self._tables: dict[str, PostgresTable] = {}

    @classmethod
    async def create(
        cls,
        dsn: str | None = None,
        *,
        min_size: int = 2,
        max_size: int = 10,
    ) -> PostgresDatastore:
        """Async factory - required because pool creation is async.

        Args:
            dsn: PostgreSQL connection string (or use env vars)
            min_size: Minimum pool connections
            max_size: Maximum pool connections

        Returns:
            PostgresDatastore instance with active connection pool
        """
        import asyncpg

        dsn = dsn or _build_dsn()

        # Register JSONB codec for automatic dict conversion
        async def init_connection(conn: asyncpg.Connection[Any]) -> None:
            await conn.set_type_codec(
                "jsonb",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
                format="text",
            )

        pool = await asyncpg.create_pool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            init=init_connection,
        )

        if pool is None:
            raise RuntimeError("Failed to create asyncpg connection pool")

        return cls(pool)

    @property
    def has_persistence(self) -> bool:
        """PostgreSQL persists data across restarts."""
        return True

    @property
    def has_transactions(self) -> bool:
        """PostgreSQL supports ACID transactions."""
        return True

    def table(
        self,
        name: str,
        *,
        indexes: list[str] | None = None,
        unique_indexes: list[str] | None = None,
    ) -> TableInterface[Any]:
        """Get or create a named table with optional index configuration.

        Note: Table/index DDL is executed lazily on first operation.
        Returns TableInterface[Any] since JSONB returns dict, not BaseModel.
        """
        if name not in self._tables:
            self._tables[name] = PostgresTable(
                pool=self._pool,
                table_name=name,
                indexes=indexes,
                unique_indexes=unique_indexes,
            )
        return self._tables[name]

    async def close(self) -> None:
        """Graceful shutdown - close connection pool."""
        await self._pool.close()
