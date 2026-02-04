"""PostgreSQL datastore implementation.

[ARCHITECTURE] SQLModel-based typed column storage.

This module provides:
- PostgresDatastore: Connection pool management with async factory
- SQLModelTable: TableInterface implementation using typed SQLModel columns
- table(): API for accessing tables from SQLModel(table=True) classes

All models must:
- Use SQLModel with table=True
- Define a primary key via Field(primary_key=True)

[SECURITY] Uses psycopg3's sql.SQL/sql.Identifier for safe SQL composition,
eliminating SQL injection vulnerabilities from dynamic table/field names.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, TypeVar, cast

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, AsyncNullConnectionPool
from sqlalchemy import Table, inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import Mapper
from sqlmodel import SQLModel

from trading_api.models.common import DatastoreCapabilitySpec
from trading_api.shared import (
    DatastoreInterface,
    RangeQueryTableInterface,
    TableInterface,
    TimeSeriesTableInterface,
)
from trading_api.shared.config import Settings

from .engine import (
    AsyncEngineFactory,
    ConnectionTimeoutError,
    check_database_exists,
    parse_dsn,
)
from .exclusion_listener import register_exclusion_listener
from .sql_safe import validate_identifier
from .sqlmodel_table import (
    RangeQuerySQLModelTable,
    SQLModelTable,
    TimeSeriesSQLModelTable,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)

if TYPE_CHECKING:
    pass

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

__all__ = ["PostgresDatastore", "SQLModelTable"]


def get_table_name(model_class: type) -> str:
    """Get table name from SQLModel class with table=True.

    Args:
        model_class: SQLModel class with table=True or subclass with __tablename__

    Returns:
        Table name from the model's metadata or __tablename__ attribute

    Raises:
        ValueError: If model does not have table=True or __tablename__
    """
    # First try SQLAlchemy inspection (works for statically defined table=True models)
    try:
        mapper: Mapper[Any] = inspect(model_class)
        table: Table = cast(Table, mapper.persist_selectable)
        return table.name
    except NoInspectionAvailable:
        pass

    # Fallback for dynamic subclasses: check __tablename__ directly
    table_name = getattr(model_class, "__tablename__", None)
    if table_name is not None:
        return str(table_name)

    raise ValueError(
        f"Model {model_class.__name__} does not have table=True "
        f"and no __tablename__ attribute found"
    )


def extract_indexes(
    model_class: type[SQLModel],
) -> tuple[list[str], list[str], str | None]:
    """Extract index metadata from SQLModel Field() declarations.

    Reads index=True, unique=True, and primary_key=True from FieldInfo.
    Works for both table=True and table=False models.

    For dynamic subclasses (e.g., BarRepository._create_bar_model), also
    checks parent class model_fields for inherited field metadata since
    Pydantic doesn't preserve SQLModel-specific attributes (primary_key, etc.)
    during subclassing.

    Returns:
        (indexes, unique_indexes, primary_key) tuple where:
        - indexes: Fields with index=True (non-unique secondary indexes)
        - unique_indexes: Fields with unique=True
        - primary_key: Field with primary_key=True (or None)
    """
    indexes: list[str] = []
    unique_indexes: list[str] = []
    primary_key: str | None = None

    # for field_name, field_info in all_fields.items():
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


def _is_testing() -> bool:
    """Detect if running inside pytest via PYTEST_CURRENT_TEST env var."""
    return os.environ.get("PYTEST_CURRENT_TEST") is not None


class PostgresDatastore(DatastoreInterface):
    """PostgreSQL datastore using psycopg3 connection pool.

    [ARCHITECTURE] SQLModel-based typed column storage
    - All models must have table=True and a primary key field
    - table() returns SQLModelTable (typed columns via SQLAlchemy)

    Uses async factory pattern since pool creation is async:
        ds = await PostgresDatastore.create()

    Features:
    - SQLModel typed columns via SQLAlchemy ORM
    - Connection pool with min/max size
    - Graceful shutdown via close()
    - [SECURITY] sql.SQL composition for injection-safe queries
    """

    # Class-level tracker for exclusion listener registration (improves test isolation)
    _exclusion_listener_tracker: set[int] = set()

    def __init__(
        self,
        pool: AsyncConnectionPool[AsyncConnection[Any]],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize with existing pool (use create() factory instead)."""
        self._pool = pool
        self._session_factory = session_factory
        self._typed_tables: dict[str, SQLModelTable[Any]] = {}
        self._timeseries_tables: dict[str, TimeSeriesSQLModelTable[Any]] = {}
        self._rangequery_tables: dict[str, RangeQuerySQLModelTable[Any]] = {}

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
        # Register exclusion listener before create_all so constraints are created
        register_exclusion_listener(_registered_tracker=cls._exclusion_listener_tracker)

        engine = await AsyncEngineFactory.get_engine(dsn)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        return cls(pool, session_factory)

    @classmethod
    def capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """PostgreSQL provides all datastore capabilities.

        Returns:
            List with persistence, transactions, timeseries, rangequery, exclusion
        """
        return [
            DatastoreCapabilitySpec(name="persistence"),
            DatastoreCapabilitySpec(name="transactions"),
            DatastoreCapabilitySpec(name="timeseries"),
            DatastoreCapabilitySpec(name="rangequery"),
            DatastoreCapabilitySpec(name="exclusion"),
        ]

    @property
    def session_factory(self) -> "async_sessionmaker[AsyncSession]":
        """Get session factory for transaction support.

        Required for atomic multi-table operations.

        Returns:
            Session factory for creating async sessions.

        Raises:
            RuntimeError: If datastore not initialized via create().
        """
        if self._session_factory is None:
            raise RuntimeError(
                "Session factory not initialized. "
                "Use PostgresDatastore.create() factory method."
            )
        return self._session_factory

    def table(
        self,
        model_class: type[T],
    ) -> TableInterface[T]:
        """Get or create a table for the given SQLModel class.

        All models must use SQLModel with table=True and define a primary key
        via Field(primary_key=True).

        Index configuration is extracted from Field() metadata:
        - index=True → secondary index
        - unique=True → unique index
        - primary_key=True → primary key field (REQUIRED)

        Args:
            model_class: SQLModel class with table=True and Field(primary_key=True)

        Returns:
            TableInterface for the model

        Raises:
            NoInspectionAvailable: If model does not have table=True
            ValueError: If model does not define a primary key field
        """
        # get_table_name raises NoInspectionAvailable for non-table models
        table_name = get_table_name(model_class)

        if self._session_factory is None:
            raise RuntimeError(
                "Session factory not initialized. "
                "Use PostgresDatastore.create() factory method."
            )

        if table_name not in self._typed_tables:
            # Extract primary_key from Field(primary_key=True)
            _, _, extracted_pk = extract_indexes(model_class)
            if extracted_pk is None:
                raise ValueError(
                    f"Model {model_class.__name__} must define a primary key field "
                    f"via Field(primary_key=True). No primary key found in schema."
                )

            self._typed_tables[table_name] = SQLModelTable[T](
                model_class=model_class,
                session_factory=self._session_factory,
                primary_key=extracted_pk,
            )
        return self._typed_tables[table_name]

    def timeseries_table(
        self,
        model_class: type[T],
    ) -> TimeSeriesTableInterface[T]:
        """Get or create a timeseries table for time-indexed models.

        For models with time-based primary keys (e.g., bars), provides
        efficient time-range queries and batch operations.

        Args:
            model_class: SQLModel class with time-based Field(primary_key=True)

        Returns:
            TimeSeriesTableInterface for the model

        Raises:
            NoInspectionAvailable: If model does not have table=True
            ValueError: If model does not define a primary key field
        """
        table_name = get_table_name(model_class)

        if self._session_factory is None:
            raise RuntimeError(
                "Session factory not initialized. "
                "Use PostgresDatastore.create() factory method."
            )

        if table_name not in self._timeseries_tables:
            _, _, extracted_pk = extract_indexes(model_class)
            if extracted_pk is None:
                raise ValueError(
                    f"Model {model_class.__name__} must define a primary key field "
                    f"via Field(primary_key=True). No primary key found in schema."
                )
            pk_field = model_class.model_fields[extracted_pk]
            if pk_field.annotation not in (int, float):
                raise TypeError(
                    f"timeseries_table() requires numeric PK for range queries, "
                    f"but {model_class.__name__}.{extracted_pk} is {pk_field.annotation}"
                )

            self._timeseries_tables[table_name] = TimeSeriesSQLModelTable[T](
                model_class=model_class,
                session_factory=self._session_factory,
                primary_key=extracted_pk,
            )
        return self._timeseries_tables[table_name]

    def rangequery_table(
        self,
        model_class: type[T],
    ) -> RangeQueryTableInterface[T]:
        """Get or create a rangequery table for range-indexed models.

        For models with Range fields (e.g., CoveredRange), provides
        efficient gap detection using PostgreSQL multirange operations.

        Requires PostgreSQL 14+ for range_agg() aggregate function.

        Args:
            model_class: SQLModel class with Range field (e.g., Int8RangeType)

        Returns:
            RangeQueryTableInterface for the model

        Raises:
            NoInspectionAvailable: If model does not have table=True
            ValueError: If model does not define a primary key field
        """
        table_name = get_table_name(model_class)

        if self._session_factory is None:
            raise RuntimeError(
                "Session factory not initialized. "
                "Use PostgresDatastore.create() factory method."
            )

        if table_name not in self._rangequery_tables:
            _, _, extracted_pk = extract_indexes(model_class)
            if extracted_pk is None:
                raise ValueError(
                    f"Model {model_class.__name__} must define a primary key field "
                    f"via Field(primary_key=True). No primary key found in schema."
                )

            self._rangequery_tables[table_name] = RangeQuerySQLModelTable[T](
                model_class=model_class,
                session_factory=self._session_factory,
                primary_key=extracted_pk,
            )
        return self._rangequery_tables[table_name]

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

        # Remove from internal cache
        self._typed_tables.pop(name, None)

        return True

    async def close(self) -> None:
        """Graceful shutdown - close connection pool and dispose engine."""
        await self._pool.close()
        await AsyncEngineFactory.dispose()
