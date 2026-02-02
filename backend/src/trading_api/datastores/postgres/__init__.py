"""PostgreSQL datastore implementation.

[ARCHITECTURE] SQLModel-based typed column storage
- SQLModelTable: Typed column storage for SQLModel entities
- AsyncEngineFactory: SQLAlchemy async engine singleton

Provides persistent storage with:
- SQLAlchemy AsyncSession via SQLModel
- PostgreSQL MVCC for concurrent access
- Alembic migrations for schema evolution
"""

from .datastore import PostgresDatastore, SQLModelTable
from .engine import (
    AsyncEngineFactory,
    ConnectionTimeoutError,
    DatabaseNotFoundError,
    check_database_exists,
)
from .exclusion_listener import register_exclusion_listener

__all__ = [
    "AsyncEngineFactory",
    "ConnectionTimeoutError",
    "DatabaseNotFoundError",
    "PostgresDatastore",
    "SQLModelTable",
    "check_database_exists",
    "register_exclusion_listener",
]
