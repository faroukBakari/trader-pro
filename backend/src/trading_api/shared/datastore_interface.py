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
    def get(self, key: str) -> BaseModel | None:
        """Get a value by key.

        Args:
            key: Unique identifier

        Returns:
            BaseModel instance or None if not found
        """

    @abstractmethod
    def set(self, key: str, value: BaseModel) -> None:
        """Set a value by key.

        Args:
            key: Unique identifier
            value: Pydantic model to store
        """

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a value by key.

        Args:
            key: Unique identifier

        Returns:
            True if deleted, False if key didn't exist
        """

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: Unique identifier

        Returns:
            True if key exists
        """

    @abstractmethod
    def keys(self) -> list[str]:
        """Get all keys in the table.

        Returns:
            List of all keys
        """

    @abstractmethod
    def values(self) -> list[BaseModel]:
        """Get all values in the table.

        Returns:
            List of all values
        """

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries from the table."""

    @abstractmethod
    def snapshot(self) -> dict[str, BaseModel]:
        """Create a shallow copy of the table data for rollback.

        Returns:
            Copy of current table state
        """

    @abstractmethod
    def restore(self, snapshot: dict[str, BaseModel]) -> None:
        """Restore table data from a snapshot.

        Args:
            snapshot: Previous table state to restore
        """


class TransactionContext:
    """Context manager for multi-table transactions with rollback.

    Acquires write locks on all specified tables in sorted order
    (to prevent deadlocks) and provides automatic rollback on exception.
    """

    def __init__(
        self,
        tables: dict[str, TableInterface],
        timeout: float = 5.0,
    ) -> None:
        """Initialize transaction context.

        Args:
            tables: Dict mapping table names to TableInterface instances
            timeout: Max seconds to wait for all locks
        """
        self.tables = tables
        self.timeout = timeout
        self._snapshots: dict[str, dict[str, BaseModel]] = {}
        self._acquired_locks: list[str] = []

    async def __aenter__(self) -> dict[str, TableInterface]:
        """Acquire locks and create snapshots for rollback."""
        # Sort table names to prevent deadlock
        sorted_names = sorted(self.tables.keys())

        # Calculate per-lock timeout
        per_lock_timeout = self.timeout / len(sorted_names) if sorted_names else 0

        for name in sorted_names:
            table = self.tables[name]
            # Acquire write lock with timeout
            await table.lock.write(timeout=per_lock_timeout).__aenter__()
            self._acquired_locks.append(name)
            # Snapshot for rollback
            self._snapshots[name] = table.snapshot()

        return self.tables

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        """Release locks and rollback on exception."""
        # Rollback on exception
        if exc_type is not None:
            for name in self._acquired_locks:
                self.tables[name].restore(self._snapshots[name])

        # Release locks in reverse order
        for name in reversed(self._acquired_locks):
            await self.tables[name].lock.write().__aexit__(None, None, None)

        self._acquired_locks.clear()
        self._snapshots.clear()

        return False  # Don't suppress exceptions


class DatastoreInterface(ABC):
    """Abstract interface for datastore with transaction support.

    Implementations:
    - InMemoryDatastore: Dict-based storage for MVP/testing
    - PostgresDatastore: asyncpg pool-based (Wave 2+)
    """

    @abstractmethod
    def table(self, name: str) -> TableInterface:
        """Get or create a named storage table.

        Args:
            name: Logical table name (e.g., "users", "tokens", "bars")

        Returns:
            TableInterface for the named table
        """

    @property
    def lock(self) -> asyncio.Lock:
        """DEPRECATED: Global lock for backward compatibility.

        Use table(name).lock for per-table locking instead.
        This returns a new lock each call - not shared!
        """
        import warnings

        warnings.warn(
            "DatastoreInterface.lock is deprecated. Use table(name).lock instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return asyncio.Lock()

    @asynccontextmanager
    async def transaction(
        self,
        table_names: list[str],
        timeout: float = 5.0,
    ) -> AsyncIterator[dict[str, TableInterface]]:
        """Begin a transaction on multiple tables with rollback support.

        Acquires write locks on all tables in sorted order (deadlock prevention)
        and automatically rolls back on exception.

        Args:
            table_names: List of table names to include in transaction
            timeout: Max seconds to wait for all locks

        Yields:
            Dict mapping table names to TableInterface instances

        Raises:
            asyncio.TimeoutError: If lock acquisition exceeds timeout

        Example:
            async with datastore.transaction(["users", "tokens"]) as txn:
                user = txn["users"].get(user_id)
                txn["tokens"].set(token_id, token)
                # Rolls back both tables if exception raised
        """
        tables = {name: self.table(name) for name in table_names}
        ctx = TransactionContext(tables, timeout)
        async with ctx as txn:
            yield txn
