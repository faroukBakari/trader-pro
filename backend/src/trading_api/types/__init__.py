"""Trading API types package.

This package contains reusable type definitions, generic abstractions,
and enums that are used across multiple modules.
"""

from .range import Range
from .storage import StorageType

__all__ = [
    "Range",
    "StorageType",
]
