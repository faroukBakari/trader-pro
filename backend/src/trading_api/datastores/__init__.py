"""Datastore abstractions for persistence layer.

Provides a minimal interface for data storage that can be swapped
between in-memory (MVP) and PostgreSQL (Wave 2+) implementations.

Directory structure follows registry pattern:
  datastores/
  ├── __init__.py           # Re-exports (backward compat)
  ├── inmemory/             # InMemoryDatastore implementation
  │   ├── __init__.py
  │   └── tests/
  ├── postgres/             # PostgresDatastore implementation (Wave 2A)
  │   ├── __init__.py
  │   └── tests/
  └── README.md
"""

from .inmemory import InMemoryDatastore
from .postgres import PostgresDatastore

__all__ = [
    "InMemoryDatastore",
    "PostgresDatastore",
]
