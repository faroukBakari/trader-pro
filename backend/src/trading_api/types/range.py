"""
Generic range types for time-based data structures.

This module provides reusable range abstractions for tracking
time intervals, cache coverage, and pending operations.
"""

from typing import TYPE_CHECKING, Generic, Protocol, Self, TypeVar

from pydantic import BaseModel, Field

if TYPE_CHECKING:

    class Comparable(Protocol):
        """Protocol for types supporting <= and >= comparison."""

        def __le__(self, other: Self, /) -> bool:
            ...

        def __ge__(self, other: Self, /) -> bool:
            ...

    T = TypeVar("T", bound=Comparable)
else:
    T = TypeVar("T")


class Range(BaseModel, Generic[T]):
    """Generic range with start/end boundaries.

    Type parameter T determines the boundary type (int for timestamps,
    datetime for temporal ranges, etc.).

    [IMMUTABLE]: Use model_copy() to create modified versions.
    [INCLUSIVE]: Both start and end are inclusive boundaries.
    """

    start: T = Field(..., description="Range start (inclusive)")
    end: T = Field(..., description="Range end (inclusive)")

    def contains(self, value: T) -> bool:
        """Check if value falls within range boundaries."""
        return self.start <= value <= self.end

    def overlaps(self, other: "Range[T]") -> bool:
        """Check if this range overlaps with another range."""
        return self.start <= other.end and other.start <= self.end


__all__ = ["Range"]
