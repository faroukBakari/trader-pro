"""In-memory datastore implementation.

Provides dict-based storage for MVP and testing with:
- Per-table read-write locks for concurrent access
- CRUD operations with Pydantic model validation
- Transaction support with automatic rollback
"""

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import BaseModel
from sqlmodel import SQLModel

from trading_api.shared import DatastoreInterface, TableInterface


def extract_indexes(
    model_class: type[BaseModel],
) -> tuple[list[str], list[str], str | None]:
    """Extract index metadata from SQLModel/Pydantic Field() declarations.

    Reads index=True, unique=True, and primary_key=True from FieldInfo.
    Works for both SQLModel and Pydantic BaseModel classes.

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


class InMemoryTable(TableInterface):
    """In-memory table implementation with async CRUD and internal RWLock.

    Stores Pydantic models in a dict with per-table read-write locking
    for concurrent read access with exclusive write access.
    All CRUD operations are async and handle locking internally.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        indexes: list[str] | None = None,
        unique_indexes: list[str] | None = None,
    ) -> None:
        self.__data: dict[str, BaseModel] = {}
        self.__indexes: dict[str, dict[str, set[str]]] = {}
        self.__unique_indexes: dict[str, dict[str, str]] = {}
        self.__lock = RWLock()
        # Threading lock for cross-thread sync with TWS connection callbacks
        self.__threading_lock = threading.Lock()
        self.__timeout = timeout

        # Register indexes at construction time (sync, no lock needed)
        for field_name in indexes or []:
            self.__indexes[field_name] = {}
        for field_name in unique_indexes or []:
            self.__unique_indexes[field_name] = {}

    @property
    def timeout(self) -> float:
        """Get the default timeout for lock acquisition."""
        return self.__timeout

    @property
    def lock(self) -> RWLock:
        """Get the read-write lock for the table."""
        return self.__lock

    def __get_by_index(
        self, field_value: str, field_name: str | None = None
    ) -> list[tuple[str, BaseModel]]:
        """Get values by indexed field (read-locked)."""
        keys: set[str] = {field_value}
        if field_name is not None:
            # First check unique indexes (1:1 mapping)
            unique_index = self.__unique_indexes.get(field_name, {})
            unique_key = unique_index.get(field_value)
            if unique_key is not None:
                keys = {unique_key}
            else:
                # Fall back to non-unique indexes (1:N mapping)
                index = self.__indexes.get(field_name, {})
                keys = index.get(field_value, set())
        return [
            (key, data)
            for key, data in [(key, self.__data.get(key)) for key in keys]
            if data is not None
        ]

    def __get_first_by_index(
        self, field_value: str, field_name: str | None = None
    ) -> tuple[str, BaseModel] | None:
        """Get first value by indexed field (read-locked)."""
        results = self.__get_by_index(field_value, field_name)
        return results[0] if results else None

    def __delete(self, key: str, index: str | None = None) -> bool:
        """Delete a value by key (write-locked)."""
        record = self.__get_first_by_index(key, index)
        if record is not None:
            key, _ = record
            del self.__data[key]
            # Clean up non-unique indexes
            for index_dict in self.__indexes.values():
                for keys_set in index_dict.values():
                    keys_set.discard(key)
            # Clean up unique indexes
            for unique_index in self.__unique_indexes.values():
                keys_to_remove = [k for k, v in unique_index.items() if v == key]
                for k in keys_to_remove:
                    del unique_index[k]
            return True
        return False

    async def get(self, key: str, index: str | None = None) -> BaseModel | None:
        """Get a value by key (read-locked)."""
        async with self.__lock.read(self.timeout):
            record = next(iter(self.__get_by_index(key, index)), None)
            if record is None:
                return None
            _, value = record
            return value.model_copy(deep=True) if value is not None else None

    async def get_all(self, key: str, index: str | None = None) -> list[BaseModel]:
        """Get all values by indexed field (read-locked)."""
        async with self.__lock.read(self.timeout):
            records = self.__get_by_index(key, index)
            return [value.model_copy(deep=True) for _, value in records]

    async def set(self, key: str, value: BaseModel) -> None:
        """Set a value by key (write-locked). Auto-indexes all registered fields.

        Raises:
            ValueError: If value violates a unique index constraint
        """
        async with self.__lock.write(self.timeout):
            with self.__threading_lock:
                # Check unique constraints before modifying data
                for field_name, unique_index in self.__unique_indexes.items():
                    field_value = getattr(value, field_name, None)
                    if field_value is not None:
                        str_value = str(field_value)
                        existing_key = unique_index.get(str_value)
                        if existing_key is not None and existing_key != key:
                            raise ValueError(
                                f"Duplicate value '{field_value}' for unique field '{field_name}'"
                            )

                # Delete by primary key to clean up old index entries
                self.__delete(key)
                self.__data[key] = value

                # Auto-index all registered index fields
                for field_name, index_dict in self.__indexes.items():
                    field_value = getattr(value, field_name, None)
                    if field_value is not None:
                        index_dict.setdefault(str(field_value), set()).add(key)

                # Auto-index all registered unique index fields
                for field_name, unique_index in self.__unique_indexes.items():
                    field_value = getattr(value, field_name, None)
                    if field_value is not None:
                        unique_index[str(field_value)] = key

    async def delete(self, key: str, index: str | None = None) -> bool:
        """Delete a value by key (write-locked)."""
        async with self.__lock.write(self.timeout):
            with self.__threading_lock:
                return self.__delete(key, index)

    async def exists(self, key: str, index: str | None = None) -> bool:
        """Check if a key exists (read-locked)."""
        async with self.__lock.read(self.timeout):
            return self.__get_by_index(key, index) != []

    async def keys(self, index: str | None = None) -> list[str]:
        """Get all keys matching an indexed field value (read-locked)."""
        async with self.__lock.read(self.timeout):
            dict_index = (
                self.__indexes.get(index, {}) if index is not None else self.__data
            )
            return list(dict_index.keys())

    async def values(self) -> list[BaseModel]:
        """Get all values in the table (read-locked)."""
        async with self.__lock.read(self.timeout):
            return [value.model_copy(deep=True) for value in self.__data.values()]

    async def clear(self) -> None:
        """Remove all entries from the table (write-locked)."""
        async with self.__lock.write(self.timeout):
            with self.__threading_lock:
                self.__data.clear()
                self.__indexes.clear()
                self.__unique_indexes.clear()

    async def count(self) -> int:
        """Get the count of entries in the table (read-locked)."""
        async with self.__lock.read(self.timeout):
            return len(self.__data)

    async def iterate(self) -> AsyncIterator[tuple[str, BaseModel]]:
        """Asynchronously iterate over key-value pairs in the table (read-locked)."""
        async with self.__lock.read(self.timeout):
            for key, value in self.__data.items():
                yield key, value.model_copy(deep=True)

    async def create_index(self, field_name: str) -> None:
        """Create an index on a specified field (write-locked)."""
        # TODO: fix behavior when existing unique / non-unique index
        async with self.__lock.write(self.timeout):
            with self.__threading_lock:
                index: dict[str, set[str]] = {}
                for key, model in self.__data.items():
                    field_value = getattr(model, field_name, None)
                    if field_value is not None:
                        index.setdefault(field_value, set()).add(key)
                self.__indexes[field_name] = index

    async def create_unique_index(self, field_name: str) -> None:
        """Create a unique index on a specified field (write-locked).

        Raises ValueError if duplicate field values exist in current data.
        """
        # TODO: fix behavior when existing unique / non-unique index
        async with self.__lock.write(self.timeout):
            with self.__threading_lock:
                unique_index: dict[str, str] = {}
                for key, model in self.__data.items():
                    field_value = getattr(model, field_name, None)
                    if field_value is not None:
                        str_value = str(field_value)
                        if str_value in unique_index:
                            raise ValueError(
                                f"Duplicate value '{field_value}' for unique field '{field_name}'"
                            )
                        unique_index[str_value] = key
                self.__unique_indexes[field_name] = unique_index


class InMemoryDatastore(DatastoreInterface):
    """In-memory datastore implementation for MVP and testing.

    Uses InMemoryTable instances for storage with per-table RWLocks
    for concurrent read access with exclusive write access.
    """

    @classmethod
    async def create(cls) -> "InMemoryDatastore":
        return cls()

    def __init__(self, timeout: float = 1.0) -> None:
        self._tables: dict[str, InMemoryTable] = {}
        self.__timeout = timeout
        self.__threading_lock = threading.Lock()

    @property
    def has_persistence(self) -> bool:
        """Whether this datastore persists data across restarts.

        Returns:
            True if data survives process restarts (e.g., PostgreSQL).
            False for ephemeral storage (e.g., InMemory).
        """
        return False

    @property
    def has_transactions(self) -> bool:
        """Whether this datastore supports ACID transactions.

        Returns:
            True if datastore provides transactional guarantees.
            False for simple key-value storage without transactions.
        """
        return False

    @property
    def is_relational(self) -> bool:
        """InMemory datastore is not a relational database."""
        return False

    @property
    def timeout(self) -> float:
        """Get the default timeout for lock acquisition."""
        return self.__timeout

    def table(
        self,
        model_class: type[BaseModel],
        primary_key: str = "id",
    ) -> TableInterface:
        """Get or create a table for the given model class.

        Index configuration is extracted from Field() metadata:
        - index=True → secondary index
        - unique=True → unique index

        Args:
            model_class: Model class (SQLModel or Pydantic BaseModel)
            primary_key: Primary key field name (unused in InMemory but kept for API parity)

        Returns:
            TableInterface for the model
        """
        name = model_class.__name__.lower()
        with self.__threading_lock:
            if name not in self._tables:
                indexes, unique_indexes, _ = extract_indexes(model_class)
                self._tables[name] = InMemoryTable(
                    timeout=self.__timeout,
                    indexes=indexes,
                    unique_indexes=unique_indexes,
                )
        return self._tables[name]


__all__ = ["InMemoryDatastore", "InMemoryTable"]
