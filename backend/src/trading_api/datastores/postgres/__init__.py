"""PostgreSQL datastore implementation.

[ARCHITECTURE] SQLModel-based typed column storage
- SQLModelTable: Typed column storage for SQLModel entities
- TimeSeriesSQLModelTable: Time-indexed storage with range queries
- RangeQuerySQLModelTable: Range-indexed storage with gap detection
- AsyncEngineFactory: SQLAlchemy async engine singleton

Provides persistent storage with:
- SQLAlchemy AsyncSession via SQLModel
- PostgreSQL MVCC for concurrent access
- Alembic migrations for schema evolution
"""

from .datastore import PostgresDatastore
from .sqlmodel_table import RangeQuerySQLModelTable

__all__ = ["PostgresDatastore", "RangeQuerySQLModelTable"]
