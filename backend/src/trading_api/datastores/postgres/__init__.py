"""PostgreSQL datastore implementation.

[ARCHITECTURE] Wave 2A + 2B: Dual-mode datastore
- PostgresTable: JSONB storage for flexible schemas (Wave 2A)
- SQLModelTable: Typed column storage for SQLModel entities (Wave 2B)
- AsyncEngineFactory: SQLAlchemy async engine singleton

Provides persistent storage with:
- Async connection pool via asyncpg (JSONB tables)
- SQLAlchemy AsyncSession via SQLModel (typed tables)
- PostgreSQL MVCC for concurrent access
- Alembic migrations for schema evolution
"""

from .datastore import PostgresDatastore, PostgresTable, SQLModelTable
from .engine import AsyncEngineFactory

__all__ = [
    "AsyncEngineFactory",
    "PostgresDatastore",
    "PostgresTable",
    "SQLModelTable",
]
