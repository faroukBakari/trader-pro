"""
Storage type definitions for cache backends.
"""

from enum import Enum


class StorageType(str, Enum):
    """Storage backend for cached bar data.

    Used by CoveredRange to track where data is persisted.
    """

    MEMORY = "memory"
    DATABASE = "database"
    DATALAKE = "datalake"


__all__ = ["StorageType"]
