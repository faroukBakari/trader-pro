"""Datastore abstractions for persistence layer.

Provides a minimal interface for data storage that can be swapped
between DuckDB (prototyping / in-memory) and PostgreSQL (production).

Directory structure follows registry pattern:
  datastores/
  ├── __init__.py           # Re-exports (backward compat)
  ├── _utils.py             # Shared utilities (extract_indexes)
  ├── duckdb/               # DuckDBDatastore implementation
  │   ├── __init__.py
  │   └── tests/
  ├── postgres/             # PostgresDatastore implementation
  │   ├── __init__.py
  │   └── tests/
  └── README.md
"""

from .duckdb import DuckDBDatastore, create_memory_datastore
from .postgres import PostgresDatastore

__all__ = [
    "DuckDBDatastore",
    "PostgresDatastore",
    "create_memory_datastore",
]
