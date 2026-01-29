"""Datastore interfaces for persistence abstraction.

Provides minimal abstraction for data persistence that enables:
- Testability via dependency injection
- Future PostgreSQL migration (Wave 2+)
- Per-table read-write locks for concurrent access
- Multi-table transactions with rollback support
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class TableInterface(ABC, Generic[T]):
    """Abstract interface for a datastore table with CRUD operations.

    Provides:
    - Type-safe CRUD operations with Pydantic models
    - Snapshot capability for transaction rollback
    """

    @abstractmethod
    async def get(self, key: str, index: str | None = None) -> T | None:
        """Get a value by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by

        Returns:
            BaseModel instance or None if not found
        """

    @abstractmethod
    async def get_all(self, key: str, index: str | None = None) -> list[T]:
        """Get all values by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by

        Returns:
            List of BaseModel instances
        """

    @abstractmethod
    async def set(self, key: str, value: BaseModel) -> None:
        """Set a value by key.

        Automatically updates all registered indexes (via create_index).

        Args:
            key: Unique identifier
            value: Pydantic model to store
        """

    @abstractmethod
    async def delete(self, key: str, index: str | None = None) -> bool:
        """Delete a value by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by

        Returns:
            True if deleted, False if key didn't exist
        """

    @abstractmethod
    async def exists(self, key: str, index: str | None = None) -> bool:
        """Check if a key or indexed value exists.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by

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
    async def clear(self) -> None:
        """Remove all entries from the table."""

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

    @abstractmethod
    async def create_index(self, field_name: str) -> None:
        """Create an index on a specified field.

        Args:
            field_name: Name of the model field to index
        """

    @abstractmethod
    async def create_unique_index(self, field_name: str) -> None:
        """Create a unique index on a specified field.

        Enforces uniqueness constraint: each field value maps to exactly one key.
        Raises ValueError if existing data contains duplicate field values.

        Args:
            field_name: Name of the model field to index uniquely

        Raises:
            ValueError: If duplicate field values exist in current data
        """


class DatastoreInterface(ABC):
    """Abstract interface for datastore with transaction support.

    Implementations:
    - InMemoryDatastore: Dict-based storage for MVP/testing
    - PostgresDatastore: asyncpg pool-based (Wave 2+)
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

    @classmethod
    @abstractmethod
    async def create(cls) -> "DatastoreInterface":
        """Async factory for datastore creation.

        Default implementation wraps sync instantiation. Override in subclasses
        that require actual async initialization (e.g., PostgresDatastore for
        asyncpg pool creation).

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
        primary_key: str = "id",
    ) -> TableInterface:
        """Get or create a table for the given model class.

        Index configuration is extracted from Field() metadata:
        - index=True → secondary index
        - unique=True → unique index
        - primary_key=True → primary key field

        For SQLModel table=True classes, uses typed column storage.
        For table=False or Pydantic models, uses JSONB storage.

        Args:
            model_class: Model class (SQLModel or Pydantic BaseModel)
            primary_key: Primary key field name (default "id", extracted from Field if declared)

        Returns:
            TableInterface for the model
        """
