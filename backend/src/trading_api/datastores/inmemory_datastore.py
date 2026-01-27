"""In-memory datastore implementation.

Provides dict-based storage for MVP and testing with:
- Per-table read-write locks for concurrent access
- CRUD operations with Pydantic model validation
- Transaction support with automatic rollback
"""

import threading
from collections.abc import AsyncIterator

from pydantic import BaseModel

from trading_api.shared import DatastoreInterface, TableInterface
from trading_api.shared.datastore_interface import RWLock


class InMemoryTable(TableInterface):
    """In-memory table implementation with async CRUD and internal RWLock.

    Stores Pydantic models in a dict with per-table read-write locking
    for concurrent read access with exclusive write access.
    All CRUD operations are async and handle locking internally.
    """

    def __init__(self, timeout: float = 1.0) -> None:
        self.__data: dict[str, BaseModel] = {}
        self.__indexes: dict[str, dict[str, set[str]]] = {}
        self.__unique_indexes: dict[str, dict[str, str]] = {}
        self.__lock = RWLock()
        # Threading lock for cross-thread sync with TWS connection callbacks
        self.__threading_lock = threading.Lock()
        self.__timeout = timeout

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

    def __init__(self, timeout: float = 1.0) -> None:
        self._tables: dict[str, InMemoryTable] = {}
        self.__timeout = timeout
        self.__threading_lock = threading.Lock()

    @property
    def timeout(self) -> float:
        """Get the default timeout for lock acquisition."""
        return self.__timeout

    def table(self, name: str) -> TableInterface:
        """Get or create a named table."""
        with self.__threading_lock:
            if name not in self._tables:
                self._tables[name] = InMemoryTable(timeout=self.__timeout)
        return self._tables[name]
