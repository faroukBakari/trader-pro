"""PostgreSQL datastore implementation using asyncpg + JSONB.

Provides persistent storage with:
- Async connection pool via asyncpg
- JSONB storage for schema flexibility
- PostgreSQL MVCC for concurrent access (no app-level locking needed)
- Dynamic table/index DDL on first access

Wave 2A: JSONB-based storage (validates TableInterface contract)
Wave 2B: SQLModel + Alembic for schema migrations (future)
"""

from .datastore import PostgresDatastore, PostgresTable

__all__ = ["PostgresDatastore", "PostgresTable"]
