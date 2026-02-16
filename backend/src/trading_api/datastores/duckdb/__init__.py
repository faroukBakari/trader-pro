"""DuckDB datastore implementation.

Provides lightweight SQL-backed storage for prototyping and testing with:
- In-memory (`:memory:`) or file-based DuckDB backend
- Thread-safe via threading.Lock + asyncio.to_thread()
- CRUD operations with Pydantic/SQLModel validation
- Declarative indexing from Field() metadata
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, get_args

import duckdb
from sqlmodel import SQLModel

from trading_api.datastores._utils import extract_indexes
from trading_api.models.common import DatastoreCapabilitySpec
from trading_api.shared import (
    DatastoreInterface,
    TableInterface,
    TimeSeriesTableInterface,
)

if TYPE_CHECKING:
    from trading_api.shared.config import Settings

# Internal column name for the external key passed to set()
_KEY_COL = "_row_key"


def python_type_to_duckdb(annotation: Any) -> str:
    """Map Python type annotation to DuckDB SQL type.

    Handles Optional[X] by unwrapping. Falls back to VARCHAR for unknowns.
    """
    # Unwrap Optional[X] / Union[X, None] / X | None
    args = get_args(annotation)
    if args and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            annotation = non_none[0]

    type_map: dict[type, str] = {
        str: "VARCHAR",
        int: "BIGINT",
        float: "DOUBLE",
        bool: "BOOLEAN",
        datetime: "TIMESTAMPTZ",
        date: "DATE",
    }
    return type_map.get(annotation, "VARCHAR")


class DuckDBTable(TableInterface):
    """DuckDB-backed table with async CRUD via asyncio.to_thread().

    All SQL operations are serialized through a shared threading.Lock
    since DuckDB connections are not thread-safe.
    """

    _SAFE_IDENT = __import__("re").compile(r"^[a-z][a-z0-9_]*$")

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        lock: threading.Lock,
        table_name: str,
        model_class: type[SQLModel],
        primary_key: str | None,
        indexes: list[str],
        unique_indexes: list[str],
    ) -> None:
        # Validate identifiers used in SQL f-strings (defense-in-depth)
        for ident in [table_name, *model_class.model_fields.keys()]:
            if not self._SAFE_IDENT.match(ident):
                raise ValueError(
                    f"Unsafe SQL identifier: '{ident}'. " f"Must match [a-z][a-z0-9_]*"
                )

        self._conn = conn
        self._lock = lock
        self._table_name = table_name
        self._model_class = model_class
        self._primary_key = primary_key
        self._indexes = indexes
        self._unique_indexes = unique_indexes

        # Build ordered list of model field names
        self._model_columns: list[str] = list(model_class.model_fields.keys())
        # All columns: _row_key + model fields
        self._all_columns: list[str] = [_KEY_COL, *self._model_columns]

        # Create table and indexes (sync, caller MUST hold self._lock)
        self._create_table()
        self._create_indexes()

    def _create_table(self) -> None:
        """Create the SQL table if it doesn't exist.

        MUST be called while self._lock is already held by the caller.
        """
        col_defs = [f"{_KEY_COL} VARCHAR PRIMARY KEY"]
        for field_name in self._model_columns:
            field_info = self._model_class.model_fields[field_name]
            sql_type = python_type_to_duckdb(field_info.annotation)
            col_defs.append(f"{field_name} {sql_type}")

        sql = (
            f"CREATE TABLE IF NOT EXISTS {self._table_name} " f"({', '.join(col_defs)})"
        )
        self._conn.execute(sql)

    def _create_indexes(self) -> None:
        """Create SQL indexes for declared index fields.

        MUST be called while self._lock is already held by the caller.
        """
        for field in self._indexes:
            idx_name = f"idx_{self._table_name}_{field}"
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                f"ON {self._table_name}({field})"
            )
        # No SQL unique indexes — unique enforcement via pre-check
        # for consistent ValueError messages across datastores

    def _row_to_model(self, row: tuple, columns: list[str]) -> SQLModel:
        """Deserialize a SQL row tuple into a model instance."""
        data = dict(zip(columns, row))
        return self._model_class.model_validate(data)

    def _validate_index(self, index: str | None) -> None:
        """Validate that index is a known model column (defense-in-depth)."""
        if index is not None and index not in self._model_columns:
            raise ValueError(
                f"Unknown index column '{index}'. "
                f"Valid columns: {self._model_columns}"
            )

    # ── CRUD Methods ──────────────────────────────────────────────────

    async def get(
        self,
        key: str,
        index: str | None = None,
        session: Any = None,  # noqa: ARG002
    ) -> SQLModel | None:
        self._validate_index(index)

        def _do() -> SQLModel | None:
            with self._lock:
                if index is not None:
                    sql = (
                        f"SELECT {', '.join(self._model_columns)} "
                        f"FROM {self._table_name} WHERE {index} = ? LIMIT 1"
                    )
                else:
                    sql = (
                        f"SELECT {', '.join(self._model_columns)} "
                        f"FROM {self._table_name} WHERE {_KEY_COL} = ? LIMIT 1"
                    )
                row = self._conn.execute(sql, [key]).fetchone()
                if row is None:
                    return None
                return self._row_to_model(row, self._model_columns)

        return await asyncio.to_thread(_do)

    async def get_all(
        self,
        key: str,
        index: str | None = None,
        session: Any = None,  # noqa: ARG002
    ) -> list[SQLModel]:
        self._validate_index(index)

        def _do() -> list[SQLModel]:
            with self._lock:
                if index is not None:
                    sql = (
                        f"SELECT {', '.join(self._model_columns)} "
                        f"FROM {self._table_name} WHERE {index} = ?"
                    )
                else:
                    sql = (
                        f"SELECT {', '.join(self._model_columns)} "
                        f"FROM {self._table_name} WHERE {_KEY_COL} = ?"
                    )
                rows = self._conn.execute(sql, [key]).fetchall()
                return [self._row_to_model(row, self._model_columns) for row in rows]

        return await asyncio.to_thread(_do)

    async def set(
        self,
        key: str,
        value: SQLModel,
        session: Any = None,  # noqa: ARG002
    ) -> None:
        def _do() -> None:
            with self._lock:
                # Pre-check unique constraints (consistent ValueError format)
                for field_name in self._unique_indexes:
                    field_value = getattr(value, field_name, None)
                    if field_value is not None:
                        row = self._conn.execute(
                            f"SELECT {_KEY_COL} FROM {self._table_name} "
                            f"WHERE {field_name} = ?",
                            [field_value],
                        ).fetchone()
                        if row is not None and row[0] != key:
                            raise ValueError(
                                f"Duplicate value '{field_value}' "
                                f"for unique field '{field_name}'"
                            )

                # DELETE + INSERT (not INSERT OR REPLACE) to work around
                # DuckDB bug where indexed columns silently retain old values.
                # Affected: DuckDB 1.4.2–1.4.4. Fix: PR #20962 (unreleased).
                # https://github.com/duckdb/duckdb/issues/20952
                # TODO(duckdb>=1.5): re-test and simplify to INSERT OR REPLACE
                self._conn.execute(
                    f"DELETE FROM {self._table_name} WHERE {_KEY_COL} = ?",
                    [key],
                )

                col_names = ", ".join(self._all_columns)
                placeholders = ", ".join(["?"] * len(self._all_columns))
                vals: list[Any] = [key]
                for field_name in self._model_columns:
                    vals.append(getattr(value, field_name, None))

                self._conn.execute(
                    f"INSERT INTO {self._table_name} "
                    f"({col_names}) VALUES ({placeholders})",
                    vals,
                )

        await asyncio.to_thread(_do)

    async def delete(
        self,
        key: str,
        index: str | None = None,
        session: Any = None,  # noqa: ARG002
    ) -> bool:
        self._validate_index(index)

        def _do() -> bool:
            with self._lock:
                if index is not None:
                    # Find by index, then delete by primary key
                    row = self._conn.execute(
                        f"SELECT {_KEY_COL} FROM {self._table_name} "
                        f"WHERE {index} = ? LIMIT 1",
                        [key],
                    ).fetchone()
                    if row is None:
                        return False
                    actual_key = row[0]
                    self._conn.execute(
                        f"DELETE FROM {self._table_name} WHERE {_KEY_COL} = ?",
                        [actual_key],
                    )
                    return True
                else:
                    row = self._conn.execute(
                        f"SELECT 1 FROM {self._table_name} WHERE {_KEY_COL} = ?",
                        [key],
                    ).fetchone()
                    if row is None:
                        return False
                    self._conn.execute(
                        f"DELETE FROM {self._table_name} WHERE {_KEY_COL} = ?",
                        [key],
                    )
                    return True

        return await asyncio.to_thread(_do)

    async def exists(
        self,
        key: str,
        index: str | None = None,
        session: Any = None,  # noqa: ARG002
    ) -> bool:
        self._validate_index(index)

        def _do() -> bool:
            with self._lock:
                if index is not None:
                    sql = (
                        f"SELECT 1 FROM {self._table_name} "
                        f"WHERE {index} = ? LIMIT 1"
                    )
                else:
                    sql = (
                        f"SELECT 1 FROM {self._table_name} "
                        f"WHERE {_KEY_COL} = ? LIMIT 1"
                    )
                return self._conn.execute(sql, [key]).fetchone() is not None

        return await asyncio.to_thread(_do)

    async def keys(self, index: str | None = None) -> list[str]:
        self._validate_index(index)

        def _do() -> list[str]:
            with self._lock:
                if index is not None:
                    sql = f"SELECT DISTINCT {index} FROM {self._table_name}"
                else:
                    sql = f"SELECT {_KEY_COL} FROM {self._table_name}"
                rows = self._conn.execute(sql).fetchall()
                return [str(row[0]) for row in rows]

        return await asyncio.to_thread(_do)

    async def values(self) -> list[SQLModel]:
        def _do() -> list[SQLModel]:
            with self._lock:
                sql = (
                    f"SELECT {', '.join(self._model_columns)} "
                    f"FROM {self._table_name}"
                )
                rows = self._conn.execute(sql).fetchall()
                return [self._row_to_model(row, self._model_columns) for row in rows]

        return await asyncio.to_thread(_do)

    async def clear(self, session: Any = None) -> None:  # noqa: ARG002
        def _do() -> None:
            with self._lock:
                self._conn.execute(f"DELETE FROM {self._table_name}")

        await asyncio.to_thread(_do)

    async def count(self) -> int:
        def _do() -> int:
            with self._lock:
                row = self._conn.execute(
                    f"SELECT COUNT(*) FROM {self._table_name}"
                ).fetchone()
                return row[0] if row else 0

        return await asyncio.to_thread(_do)

    @property
    async def is_empty(self) -> bool:
        def _do() -> bool:
            with self._lock:
                row = self._conn.execute(
                    f"SELECT 1 FROM {self._table_name} LIMIT 1"
                ).fetchone()
                return row is None

        return await asyncio.to_thread(_do)

    async def iterate(self) -> AsyncIterator[tuple[str, SQLModel]]:
        def _do() -> list[tuple]:
            with self._lock:
                sql = (
                    f"SELECT {_KEY_COL}, {', '.join(self._model_columns)} "
                    f"FROM {self._table_name}"
                )
                return self._conn.execute(sql).fetchall()

        rows = await asyncio.to_thread(_do)
        for row in rows:
            key = row[0]
            data = dict(zip(self._model_columns, row[1:]))
            model = self._model_class.model_validate(data)
            yield key, model


class DuckDBTimeSeriesTable(DuckDBTable, TimeSeriesTableInterface[SQLModel]):
    """DuckDB-backed timeseries table with batch upsert and range queries.

    Extends DuckDBTable with:
    - get_time_range(): SQL BETWEEN query on primary key column
    - set_batch(): DELETE+INSERT batch upsert returning new-insert count

    Requires model to have Field(primary_key=True).
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self._primary_key is None:
            raise ValueError(
                f"DuckDBTimeSeriesTable requires a primary key, "
                f"but {self._model_class.__name__} has none."
            )
        self._pk: str = self._primary_key

    async def get_time_range(
        self,
        from_time: int,
        to_time: int,
        session: Any = None,  # noqa: ARG002
    ) -> list[SQLModel]:
        pk = self._pk

        def _do() -> list[SQLModel]:
            with self._lock:
                sql = (
                    f"SELECT {', '.join(self._model_columns)} "
                    f"FROM {self._table_name} "
                    f"WHERE {pk} BETWEEN ? AND ? "
                    f"ORDER BY {pk}"
                )
                rows = self._conn.execute(sql, [from_time, to_time]).fetchall()
                return [self._row_to_model(row, self._model_columns) for row in rows]

        return await asyncio.to_thread(_do)

    async def set_batch(
        self,
        values: Sequence[SQLModel],
        session: Any = None,  # noqa: ARG002
    ) -> int:
        if not values:
            return 0

        def _do() -> int:
            with self._lock:
                # Count existing rows before insert
                row = self._conn.execute(
                    f"SELECT COUNT(*) FROM {self._table_name}"
                ).fetchone()
                count_before: int = row[0] if row else 0

                # DELETE+INSERT each value (same workaround as DuckDBTable.set,
                # see https://github.com/duckdb/duckdb/issues/20952)
                for value in values:
                    key = str(getattr(value, self._pk))
                    self._conn.execute(
                        f"DELETE FROM {self._table_name} WHERE {_KEY_COL} = ?",
                        [key],
                    )
                    vals: list[Any] = [key]
                    for field_name in self._model_columns:
                        vals.append(getattr(value, field_name, None))

                    col_names = ", ".join(self._all_columns)
                    placeholders = ", ".join(["?"] * len(self._all_columns))
                    self._conn.execute(
                        f"INSERT INTO {self._table_name} "
                        f"({col_names}) VALUES ({placeholders})",
                        vals,
                    )

                # New inserts = total after - total before
                row_after = self._conn.execute(
                    f"SELECT COUNT(*) FROM {self._table_name}"
                ).fetchone()
                count_after: int = row_after[0] if row_after else 0
                return count_after - count_before

        return await asyncio.to_thread(_do)


class DuckDBDatastore(DatastoreInterface):
    """DuckDB-backed datastore for lightweight SQL storage.

    Defaults to in-memory (`:memory:`) for prototyping and tests.
    Set DATASTORE_DUCKDB_PATH to a file path for persistent storage.
    """

    @classmethod
    def capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """DuckDB provides timeseries capability for time-range queries."""
        return [DatastoreCapabilitySpec(name="timeseries")]

    @classmethod
    async def create(cls, config: Settings | None = None) -> "DuckDBDatastore":
        """Create a DuckDBDatastore with optional config.

        Args:
            config: Optional Settings. Uses DATASTORE_DUCKDB_PATH if available,
                   defaults to `:memory:`.
        """
        if config is None:
            from trading_api.shared.config import settings

            config = settings
        path = getattr(config, "DATASTORE_DUCKDB_PATH", ":memory:")
        conn = duckdb.connect(path)
        return cls(conn)

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._lock = threading.Lock()
        self._tables: dict[str, DuckDBTable] = {}
        self._closed = False

    @property
    def session_factory(self) -> None:
        """DuckDB datastore does not support session-based transactions."""
        return None

    def _check_closed(self) -> None:
        if self._closed:
            raise RuntimeError("DuckDBDatastore is closed.")

    def table(self, model_class: type[SQLModel]) -> TableInterface:
        """Get or create a table for the given model class.

        Args:
            model_class: SQLModel subclass with Field(primary_key=True)

        Returns:
            TableInterface for the model

        Raises:
            NotImplementedError: If model requires exclusion constraints
            RuntimeError: If datastore has been closed
        """
        self._check_closed()
        # Fail-fast: reject models that require exclusion constraints
        table_args = getattr(model_class, "__table_args__", None)
        if table_args and isinstance(table_args, dict):
            exclusion_meta = table_args.get("info", {}).get("exclusion")
            if exclusion_meta:
                raise NotImplementedError(
                    f"Model {model_class.__name__} requires exclusion constraints "
                    f"(via __table_args__), but DuckDBDatastore does not support them. "
                    f"Use PostgresDatastore for models with exclusion requirements."
                )

        name = (
            getattr(model_class, "__tablename__", None) or model_class.__name__.lower()
        )
        with self._lock:
            if name not in self._tables:
                indexes, unique_indexes, primary_key = extract_indexes(model_class)
                self._tables[name] = DuckDBTable(
                    conn=self._conn,
                    lock=self._lock,
                    table_name=name,
                    model_class=model_class,
                    primary_key=primary_key,
                    indexes=indexes,
                    unique_indexes=unique_indexes,
                )
        return self._tables[name]

    def timeseries_table(self, model_class: type[SQLModel]) -> DuckDBTimeSeriesTable:
        """Get or create a timeseries table for time-indexed models.

        Args:
            model_class: Model class with Field(primary_key=True)

        Returns:
            DuckDBTimeSeriesTable with get_time_range() and set_batch()

        Raises:
            ValueError: If model does not define a primary key field
            RuntimeError: If datastore has been closed
        """
        self._check_closed()
        name = (
            getattr(model_class, "__tablename__", None) or model_class.__name__.lower()
        )
        with self._lock:
            if name not in self._tables:
                indexes, unique_indexes, primary_key = extract_indexes(model_class)
                if primary_key is None:
                    raise ValueError(
                        f"Model {model_class.__name__} requires Field(primary_key=True) "
                        f"for timeseries_table()."
                    )
                self._tables[name] = DuckDBTimeSeriesTable(
                    conn=self._conn,
                    lock=self._lock,
                    table_name=name,
                    model_class=model_class,
                    primary_key=primary_key,
                    indexes=indexes,
                    unique_indexes=unique_indexes,
                )
            table = self._tables[name]
            if not isinstance(table, DuckDBTimeSeriesTable):
                raise TypeError(
                    f"Table '{name}' already exists as {type(table).__name__}. "
                    f"Use timeseries_table() from the start."
                )
            return table

    async def list_tables(self, prefix: str | None = None) -> list[str]:
        """List all table names in the DuckDB database."""

        def _do() -> list[str]:
            with self._lock:
                rows = self._conn.execute("SHOW TABLES").fetchall()
                names = [row[0] for row in rows]
            if prefix:
                names = [n for n in names if n.startswith(prefix)]
            return names

        return await asyncio.to_thread(_do)

    async def drop_table(self, name: str) -> bool:
        """Drop a table by name.

        Returns:
            True if table was dropped, False if it didn't exist.
        """

        def _do() -> bool:
            with self._lock:
                rows = self._conn.execute("SHOW TABLES").fetchall()
                exists = any(row[0] == name for row in rows)
                if not exists:
                    return False
                self._conn.execute(f"DROP TABLE IF EXISTS {name}")
                self._tables.pop(name, None)
                return True

        return await asyncio.to_thread(_do)

    async def close(self) -> None:
        """Close the DuckDB connection and invalidate cached tables."""

        def _do() -> None:
            with self._lock:
                self._tables.clear()
                self._closed = True
                self._conn.close()

        await asyncio.to_thread(_do)


def create_memory_datastore() -> DuckDBDatastore:
    """Create a DuckDB datastore backed by an in-memory database.

    Convenience factory for tests and prototyping — a fully-capable
    DuckDB :memory: instance for lightweight use cases.
    """
    return DuckDBDatastore(duckdb.connect(":memory:"))


__all__ = [
    "DuckDBDatastore",
    "DuckDBTable",
    "DuckDBTimeSeriesTable",
    "create_memory_datastore",
]
