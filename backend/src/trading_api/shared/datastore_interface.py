"""Datastore interfaces for persistence abstraction.

Provides minimal abstraction for data persistence that enables:
- Testability via dependency injection
- Future PostgreSQL migration (Wave 2+)
- Per-table read-write locks for concurrent access
- Multi-table transactions with rollback support
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from trading_api.shared.config import Settings

T = TypeVar("T", bound=BaseModel)


class TableInterface(ABC, Generic[T]):
    """Abstract interface for a datastore table with CRUD operations.

    Provides:
    - Type-safe CRUD operations with Pydantic models
    - Snapshot capability for transaction rollback
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
            BaseModel instance or None if not found
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
            List of BaseModel instances
        """

    @abstractmethod
    async def set(
        self,
        key: str,
        value: BaseModel,
        session: "AsyncSession | None" = None,
    ) -> None:
        """Set a value by key (upsert pattern).

        Automatically updates all registered indexes (via create_index).

        Args:
            key: Unique identifier
            value: Pydantic model to store
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

    @property
    @abstractmethod
    async def is_empty(self) -> bool:
        """Check if table has zero entries.

        Returns:
            True if table has no entries, False otherwise
        """

    @abstractmethod
    def iterate(self) -> AsyncIterator[tuple[str, T]]:
        """Asynchronously iterate over key-value pairs.

        Yields:
            Tuples of (key, value) for each entry
        """


class DatastoreInterface(ABC):
    """Abstract interface for datastore with transaction support.

    Implementations:
    - InMemoryDatastore: Dict-based storage for MVP/testing
    - PostgresDatastore: psycopg pool-based (Wave 2+)
    """

    @property
    @abstractmethod
    def has_persistence(self) -> bool:
        """Whether this datastore persists data across restarts.

        Returns:
            True if data survives process restarts (e.g., PostgreSQL).
            False for ephemeral storage (e.g., InMemory).
        """
        ...

    @property
    @abstractmethod
    def is_relational(self) -> bool:
        """Whether this datastore supports ACID transactions.

        Returns:
            True if datastore provides transactional guarantees.
            False for simple key-value storage without transactions.
        """
        ...

    @property
    @abstractmethod
    def has_transactions(self) -> bool:
        """Whether this datastore supports ACID transactions.

        Returns:
            True if datastore provides transactional guarantees.
            False for simple key-value storage without transactions.
        """
        ...

    @property
    @abstractmethod
    def has_exclusion(self) -> bool:
        """Whether this datastore supports range exclusion constraints.

        When True, exclusion constraints are automatically created from
        model __table_args__ metadata by the exclusion_listener. This creates
        database-level constraints (e.g., PostgreSQL EXCLUDE USING GIST)
        that atomically prevent overlapping ranges across concurrent writes.

        When False, exclusion constraints are not supported and overlap
        prevention must be handled via application-level checks.

        Returns:
            True if datastore supports atomic exclusion constraints.
            False for datastores without native range constraint support.
        """
        ...

    @property
    def session_factory(self) -> "async_sessionmaker[AsyncSession] | None":
        """Get session factory for transaction support.

        Returns:
            Session factory if datastore supports transactions, None otherwise.
            Callers should check has_transactions before using.

        Usage:
            if datastore.has_transactions and datastore.session_factory:
                async with datastore.session_factory() as session:
                    # ... multiple operations in one transaction ...
                    await session.commit()
        """
        return None  # Default for non-transactional datastores

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
