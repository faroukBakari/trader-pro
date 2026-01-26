"""In-memory datastore implementation.

Provides dict-based storage for MVP and testing with:
- Per-table read-write locks for concurrent access
- CRUD operations with Pydantic model validation
- Transaction support with automatic rollback
"""

from pydantic import BaseModel

from trading_api.shared import DatastoreInterface, RWLock, TableInterface


class InMemoryTable(TableInterface):
    """In-memory table implementation with RWLock and CRUD operations.

    Stores Pydantic models in a dict with per-table read-write locking
    for concurrent read access with exclusive write access.
    """

    def __init__(self) -> None:
        self._data: dict[str, BaseModel] = {}
        self._lock = RWLock()

    @property
    def lock(self) -> RWLock:
        """Per-table read-write lock."""
        return self._lock

    def get(self, key: str) -> BaseModel | None:
        """Get a value by key."""
        return self._data.get(key)

    def set(self, key: str, value: BaseModel) -> None:
        """Set a value by key."""
        self._data[key] = value

    def delete(self, key: str) -> bool:
        """Delete a value by key."""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self._data

    def keys(self) -> list[str]:
        """Get all keys in the table."""
        return list(self._data.keys())

    def values(self) -> list[BaseModel]:
        """Get all values in the table."""
        return list(self._data.values())

    def clear(self) -> None:
        """Remove all entries from the table."""
        self._data.clear()

    def snapshot(self) -> dict[str, BaseModel]:
        """Create a shallow copy of the table data for rollback."""
        return dict(self._data)

    def restore(self, snapshot: dict[str, BaseModel]) -> None:
        """Restore table data from a snapshot."""
        self._data.clear()
        self._data.update(snapshot)


class InMemoryDatastore(DatastoreInterface):
    """In-memory datastore implementation for MVP and testing.

    Uses InMemoryTable instances for storage with per-table RWLocks
    for concurrent read access with exclusive write access.
    """

    def __init__(self) -> None:
        self._tables: dict[str, InMemoryTable] = {}

    def table(self, name: str) -> TableInterface:
        """Get or create a named table."""
        if name not in self._tables:
            self._tables[name] = InMemoryTable()
        return self._tables[name]
