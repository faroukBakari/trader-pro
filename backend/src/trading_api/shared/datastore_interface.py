"""Datastore interfaces for persistence abstraction.

Provides minimal abstraction for data persistence that enables:
- Testability via dependency injection
- Future PostgreSQL migration (Wave 2+)
- Per-table read-write locks for concurrent access
- Multi-table transactions with rollback support
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class RWLock:
    """Async read-write lock allowing concurrent reads with exclusive writes.

    Multiple readers can hold the lock simultaneously, but writers get
    exclusive access. Writers are prioritized to prevent starvation.
    """

    def __init__(self) -> None:
        self._read_count = 0
        self._write_locked = False
        self._write_waiting = 0
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def read(self, timeout: float | None = None) -> AsyncIterator[None]:
        """Acquire read lock (shared access).

        Args:
            timeout: Max seconds to wait for lock (None = no timeout)

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        async with asyncio.timeout(timeout):
            async with self._condition:
                # Wait while write is held or writers are waiting (writer priority)
                while self._write_locked or self._write_waiting > 0:
                    await self._condition.wait()
                self._read_count += 1
        try:
            yield
        finally:
            async with self._condition:
                self._read_count -= 1
                if self._read_count == 0:
                    self._condition.notify_all()

    @asynccontextmanager
    async def write(self, timeout: float | None = None) -> AsyncIterator[None]:
        """Acquire write lock (exclusive access).

        Args:
            timeout: Max seconds to wait for lock (None = no timeout)

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        async with asyncio.timeout(timeout):
            async with self._condition:
                self._write_waiting += 1
                try:
                    # Wait until no readers and no other writer
                    while self._read_count > 0 or self._write_locked:
                        await self._condition.wait()
                    self._write_locked = True
                finally:
                    self._write_waiting -= 1
        try:
            yield
        finally:
            async with self._condition:
                self._write_locked = False
                self._condition.notify_all()


class TableInterface(ABC):
    """Abstract interface for a datastore table with CRUD operations.

    Provides:
    - Per-table read-write lock for concurrent access
    - Type-safe CRUD operations with Pydantic models
    - Snapshot capability for transaction rollback
    """

    @property
    @abstractmethod
    def lock(self) -> RWLock:
        """Per-table read-write lock."""

    @abstractmethod
    async def get(self, key: str, index: str | None = None) -> BaseModel | None:
        """Get a value by key or indexed field.

        Args:
            key: Unique identifier or indexed field value
            index: Optional index field name to search by

        Returns:
            BaseModel instance or None if not found
        """

    @abstractmethod
    async def get_all(self, key: str, index: str | None = None) -> list[BaseModel]:
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
    async def values(self) -> list[BaseModel]:
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
    def iterate(self) -> AsyncIterator[tuple[str, BaseModel]]:
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

    @abstractmethod
    def table(
        self,
        name: str,
        *,
        indexes: list[str] | None = None,
        unique_indexes: list[str] | None = None,
    ) -> TableInterface:
        """Get or create a named storage table with optional index configuration.

        Args:
            name: Logical table name (e.g., "users", "tokens", "bars")
            indexes: Field names for secondary indexes (1:N mapping)
            unique_indexes: Field names for unique indexes (1:1 mapping)

        Returns:
            TableInterface for the named table

        Note:
            Index configuration is only applied when creating a new table.
            Subsequent calls with different index config are ignored.
        """
