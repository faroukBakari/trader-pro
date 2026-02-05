"""Datastore interfaces for persistence abstraction.

Provides minimal abstraction for data persistence that enables:
- Testability via dependency injection
- Future PostgreSQL migration (Wave 2+)
- Per-table read-write locks for concurrent access
- Multi-table transactions with rollback support

Interface Segregation Pattern (ISP):
- TableInterface: Core CRUD operations (all datastores)
- TimeSeriesTableInterface: Time-range queries (PostgreSQL timeseries tables)
- RangeQueryTableInterface: Gap detection via multirange operations (PostgreSQL)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar, cast

from sqlmodel import SQLModel

from trading_api.models.common import DatastoreCapabilitySpec

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from trading_api.shared.config import Settings
    from trading_api.types import Range

T = TypeVar("T", bound=SQLModel)


def create_dynamic_table_model(
    base_model: type[T],
    table_name: str,
    class_name: str | None = None,
) -> type[T]:
    """Create dynamic SQLModel subclass with preserved field metadata."""
    if class_name is None:
        class_name = f"{base_model.__name__}_{table_name.replace('-', '_')}"

    # type() invokes SQLModel metaclass properly
    dynamic_class = type(
        class_name,
        (base_model,),
        {"__tablename__": table_name, "__module__": base_model.__module__},
    )

    # Preserve SQLModel field metadata (Pydantic strips primary_key, index, etc.)
    for field_name, parent_field_info in base_model.model_fields.items():
        dynamic_class.model_fields[field_name] = parent_field_info  # type: ignore

    return cast(type[T], dynamic_class)


class TableInterface(ABC, Generic[T]):
    """Abstract interface for a datastore table with CRUD operations.

    Provides:
    - Type-safe CRUD operations with Pydantic models
    - Snapshot capability for transaction rollback
    """

    @property
    @abstractmethod
    async def is_empty(self) -> bool:
        """Check if table has zero entries.

        Returns:
            True if table has no entries, False otherwise
        """

    @abstractmethod
    async def get(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> T | None:
        """Get a value by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by
            session: Optional external session for transaction batching.
                    If provided, reads uncommitted writes from that session.

        Returns:
            SQLModel instance or None if not found
        """

    @abstractmethod
    async def get_all(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> list[T]:
        """Get all values by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by
            session: Optional external session for transaction batching.
                    If provided, reads uncommitted writes from that session.

        Returns:
            List of SQLModel instances
        """

    @abstractmethod
    async def set(
        self,
        key: str,
        value: SQLModel,
        session: "AsyncSession | None" = None,
    ) -> None:
        """Set a value by key (upsert pattern).

        Automatically updates all registered indexes (via create_index).

        Args:
            key: Unique identifier
            value: SQLModel to store
            session: Optional external session for transaction batching.
                    If provided, caller is responsible for commit.
        """

    @abstractmethod
    async def delete(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> bool:
        """Delete a value by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by
            session: Optional external session for transaction batching.
                    If provided, caller is responsible for commit.

        Returns:
            True if deleted, False if key didn't exist
        """

    @abstractmethod
    async def exists(
        self,
        key: str,
        index: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> bool:
        """Check if a key or indexed value exists.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by
            session: Optional external session for transaction batching.
                    If provided, checks uncommitted writes from that session.

        Returns:
            True if key exists
        """

    @abstractmethod
    async def keys(self, index: str | None = None) -> list[str]:
        """Get all keys, optionally filtered by index.

        Args:
            index: Optional index field name to get indexed values

        Returns:
            List of keys or indexed values
        """

    @abstractmethod
    async def values(self) -> list[T]:
        """Get all values in the table.

        Returns:
            List of all values
        """

    @abstractmethod
    async def clear(self, session: "AsyncSession | None" = None) -> None:
        """Remove all entries from the table.

        Args:
            session: Optional external session for transaction batching.
                    If provided, caller is responsible for commit.
        """

    @abstractmethod
    async def count(self) -> int:
        """Get the count of entries in the table.

        Returns:
            Number of entries
        """

    @abstractmethod
    def iterate(self) -> AsyncIterator[tuple[str, T]]:
        """Asynchronously iterate over key-value pairs.

        Yields:
            Tuples of (key, value) for each entry
        """


class TimeSeriesTableInterface(TableInterface[T], ABC):
    """Extended table interface for time-indexed data (e.g., bars).

    Provides efficient time-range queries and batch operations using
    PostgreSQL B-tree indexes on time-based primary keys.

    Use datastore.timeseries_table(model_class) to obtain this interface.
    Check isinstance(table, TimeSeriesTableInterface) before using these methods.
    """

    @abstractmethod
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

    @abstractmethod
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
            Number of values processed (note: doesn't distinguish inserts vs updates)
        """


class RangeQueryTableInterface(TableInterface[T], ABC):
    """Extended table interface for range-indexed data with gap detection.

    Provides efficient gap detection using PostgreSQL GiST indexes and
    multirange operations (range_agg, multirange subtraction).

    Use datastore.rangequery_table(model_class) to obtain this interface.
    Check datastore.has_capability("rangequery") before using.

    Requirements:
        - Model must have a Range field (e.g., time_range: Int8RangeType)
        - Model must have a grouping field (e.g., lookup_key: str)
        - PostgreSQL 14+ (for range_agg aggregate function)
    """

    @abstractmethod
    async def get_missing_ranges(
        self,
        lookup_key: str,
        query_range: "Range[int]",
        range_field: str = "time_range",
        group_field: str = "lookup_key",
        session: "AsyncSession | None" = None,
    ) -> "list[Range[int]]":
        """Find gaps in coverage using PostgreSQL multirange subtraction.

        Executes: requested_range - range_agg(covered_ranges)

        Args:
            lookup_key: Filter value for group_field (e.g., "AAPL_1d")
            query_range: Requested range to check coverage for
            range_field: Column name storing Range values (default: "time_range")
            group_field: Column name for filtering (default: "lookup_key")
            session: Optional external session for transaction batching

        Returns:
            List of Range gaps that are not covered (empty = full coverage)
        """


class DatastoreInterface(ABC):
    """Abstract interface for datastore with transaction support.

    Implementations:
    - InMemoryDatastore: Dict-based storage for MVP/testing
    - PostgresDatastore: psycopg pool-based (Wave 2+)
    """

    def has_capability(self, name: str) -> bool:
        """Check if datastore has a specific capability.

        Convenience method that checks the capabilities() classmethod.
        Use this instead of individual has_* properties.

        Args:
            name: Capability name (e.g., "persistence", "transactions", "timeseries")

        Returns:
            True if datastore provides the named capability

        Examples:
            >>> datastore.has_capability("persistence")
            True
            >>> datastore.has_capability("timeseries")
            False  # for InMemoryDatastore
        """
        return any(cap.name == name for cap in self.capabilities())

    @property
    def session_factory(self) -> "async_sessionmaker[AsyncSession] | None":
        """Get session factory for transaction support.

        Returns:
            Session factory if datastore supports transactions, None otherwise.
            Callers should check has_capability("transactions") before using.

        Usage:
            if datastore.has_capability("transactions") and datastore.session_factory:
                async with datastore.session_factory() as session:
                    # ... multiple operations in one transaction ...
                    await session.commit()
        """
        return None  # Default for non-transactional datastores

    @classmethod
    @abstractmethod
    def capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """Declare capabilities this datastore provides.

        Used by DatastoreRegistry to filter datastores by required capabilities.
        Mirrors Provider.capabilities() pattern.

        Returns:
            List of capabilities this datastore provides

        Examples:
            >>> PostgresDatastore.capabilities()
            [DatastoreCapabilitySpec(name="persistence"), ...]
        """
        ...

    @classmethod
    @abstractmethod
    async def create(cls, config: Settings | None = None) -> "DatastoreInterface":
        """Async factory for datastore creation with optional config injection.

        Args:
            config: Optional Settings instance for dependency injection (tests).
                   Defaults to global settings singleton for production (SSOT).

        Default implementation wraps sync instantiation. Override in subclasses
        that require actual async initialization (e.g., PostgresDatastore for
        psycopg pool creation).

        Returns:
            DatastoreInterface instance
        """
        ...

    @classmethod
    def datastore_name(cls) -> str:
        """Canonical name for registry lookup.

        Override in subclasses if the default (lowercase class prefix) is not desired.
        E.g., InMemoryDatastore → "inmemory", PostgresDatastore → "postgres"

        Returns:
            str: Datastore name used by DatastoreRegistry
        """
        # Default: strip "Datastore" suffix and lowercase
        # InMemoryDatastore → "inmemory"
        name = cls.__name__.removesuffix("Datastore")
        return name.lower()

    @abstractmethod
    def table(
        self,
        model_class: type,
    ) -> TableInterface:
        """Get or create a table for the given model class.

        Index configuration is extracted from Field() metadata:
        - index=True → secondary index
        - unique=True → unique index
        - primary_key=True → primary key field (REQUIRED)

        All models must define a primary key via Field(primary_key=True).

        Args:
            model_class: Model class with Field(primary_key=True) defined

        Returns:
            TableInterface for the model

        Raises:
            ValueError: If model does not define a primary key field
        """

    def timeseries_table(
        self,
        model_class: type,
    ) -> TimeSeriesTableInterface:
        """Get or create a timeseries table for time-indexed models.

        For models with time-based primary keys (e.g., bars), provides
        time-range queries and batch operations.

        Args:
            model_class: Model class with time-based Field(primary_key=True)

        Returns:
            TimeSeriesTableInterface for the model

        Raises:
            NotImplementedError: If datastore doesn't support timeseries tables
            ValueError: If model does not define a primary key field
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support timeseries_table(). "
            "Use PostgresDatastore for time-range queries and batch operations."
        )

    def rangequery_table(
        self,
        model_class: type,
    ) -> RangeQueryTableInterface:
        """Get or create a rangequery table for gap detection.

        For models with Range fields (e.g., CoveredRange), provides efficient
        gap detection using PostgreSQL multirange operations.

        Args:
            model_class: Model class with Range field (e.g., time_range: Int8RangeType)

        Returns:
            RangeQueryTableInterface for the model

        Raises:
            NotImplementedError: If datastore doesn't support rangequery tables
            ValueError: If model does not define expected fields
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support rangequery_table(). "
            "Use PostgresDatastore for multirange gap detection."
        )

    @abstractmethod
    async def list_tables(self, prefix: str | None = None) -> list[str]:
        """List all table names in the datastore.

        Queries the datastore for existing tables. For PostgreSQL, this queries
        information_schema to find dynamically-created tables (e.g., bar tables).
        For InMemory, this returns keys from the internal tables dict.

        Args:
            prefix: Optional prefix filter (e.g., "bars_" to list only bar tables)

        Returns:
            List of table names matching the prefix filter (or all if no prefix)
        """
        ...

    @abstractmethod
    async def drop_table(self, name: str) -> bool:
        """Drop a table by name.

        Removes the table from the datastore and unregisters it from internal tracking.
        For PostgreSQL, executes DROP TABLE IF EXISTS.
        For InMemory, removes from the internal tables dict.

        Args:
            name: Table name to drop

        Returns:
            True if table was dropped, False if it didn't exist
        """
        ...
