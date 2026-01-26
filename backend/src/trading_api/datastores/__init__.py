"""Datastore abstractions for persistence layer.

Provides a minimal interface for data storage that can be swapped
between in-memory (MVP) and PostgreSQL (Wave 2+) implementations.
"""

from .inmemory_datastore import InMemoryDatastore, InMemoryTable

__all__ = [
    # Implementations
    "InMemoryDatastore",
    "InMemoryTable",
]
