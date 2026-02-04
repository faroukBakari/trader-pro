"""PostgreSQL datastore implementation.

[ARCHITECTURE] SQLModel-based typed column storage
- SQLModelTable: Typed column storage for SQLModel entities
- TimeSeriesSQLModelTable: Time-indexed storage with range queries
- AsyncEngineFactory: SQLAlchemy async engine singleton

Provides persistent storage with:
- SQLAlchemy AsyncSession via SQLModel
- PostgreSQL MVCC for concurrent access
- Alembic migrations for schema evolution
"""

from .datastore import PostgresDatastore

__all__ = ["PostgresDatastore"]
