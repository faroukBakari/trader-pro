"""
Generic range types for time-based data structures.

This module provides reusable range abstractions for tracking
time intervals, cache coverage, and pending operations.
"""

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Protocol, Self, TypeVar

from psycopg.types.range import Range as PgRange
from pydantic import BaseModel, Field
from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import DATERANGE, INT8RANGE, TSTZRANGE

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


class IntRange(Range[int]):
    """Integer range for generic numeric intervals.

    Maps to PostgreSQL int8range.
    """


class DateTimeRange(Range[datetime]):
    """Timezone-aware datetime range.

    Maps to PostgreSQL tstzrange. Expects timezone-aware datetime objects.
    """


class DateOnlyRange(Range[date]):
    """Date-only range (no time component).

    Maps to PostgreSQL daterange.
    """


class Int8RangeType(TypeDecorator[Range[int]]):
    """Maps Range[int] (TimeRange, IntRange) to PostgreSQL int8range.

    SQLAlchemy uses this for:
    - DDL: CREATE TABLE ... (column int8range)
    - Query compilation: type coercion in WHERE clauses
    - Value conversion via process_bind_param/process_result_value
    """

    impl = INT8RANGE
    cache_ok = True
    requires_gist_index: ClassVar[bool] = True  # Marker for auto-GiST index creation

    def process_bind_param(
        self, value: Range[int] | dict[str, Any] | None, dialect: Dialect
    ) -> PgRange[int] | None:
        """Convert Range[int] to psycopg PgRange for database storage."""
        if value is None:
            return None
        # SQLModel serializes Pydantic models to dicts, so handle both
        if isinstance(value, dict):
            start = value["start"]
            end = value["end"]
        else:
            start = value.start
            end = value.end
        # Use half-open bounds "[)" with exclusive upper (PostgreSQL canonical form)
        return PgRange(start, end + 1, "[)")

    def process_result_value(
        self, value: PgRange[int] | None, dialect: Dialect
    ) -> IntRange | None:
        """Convert psycopg PgRange back to IntRange."""
        if value is None or value.isempty:
            return None
        if value.lower is None or value.upper is None:
            return None
        # PostgreSQL int8range canonicalizes to "[)" so upper is exclusive
        return IntRange(start=value.lower, end=value.upper - 1)


class TstzRangeType(TypeDecorator[Range[datetime]]):
    """Maps DateTimeRange to PostgreSQL tstzrange.

    For timezone-aware datetime ranges.
    """

    impl = TSTZRANGE
    cache_ok = True
    requires_gist_index: ClassVar[bool] = True

    def process_bind_param(
        self, value: Range[datetime] | dict[str, Any] | None, dialect: Dialect
    ) -> PgRange[datetime] | None:
        """Convert DateTimeRange to psycopg PgRange for database storage."""
        if value is None:
            return None
        # SQLModel serializes Pydantic models to dicts, so handle both
        if isinstance(value, dict):
            start = value["start"]
            end = value["end"]
        else:
            start = value.start
            end = value.end
        # Timestamps are continuous, use inclusive bounds
        return PgRange(start, end, "[]")

    def process_result_value(
        self, value: PgRange[datetime] | None, dialect: Dialect
    ) -> DateTimeRange | None:
        """Convert psycopg PgRange back to DateTimeRange."""
        if value is None or value.isempty:
            return None
        if value.lower is None or value.upper is None:
            return None
        return DateTimeRange(start=value.lower, end=value.upper)


class DateRangeType(TypeDecorator[Range[date]]):
    """Maps DateOnlyRange to PostgreSQL daterange.

    For date-only ranges.
    """

    impl = DATERANGE
    cache_ok = True
    requires_gist_index: ClassVar[bool] = True

    def process_bind_param(
        self, value: Range[date] | dict[str, Any] | None, dialect: Dialect
    ) -> PgRange[date] | None:
        """Convert DateOnlyRange to psycopg PgRange for database storage."""
        if value is None:
            return None
        # SQLModel serializes Pydantic models to dicts, so handle both
        if isinstance(value, dict):
            start = value["start"]
            end = value["end"]
        else:
            start = value.start
            end = value.end
        # Dates are discrete, PostgreSQL canonicalizes to "[)" so add 1 day to upper
        return PgRange(start, end + timedelta(days=1), "[)")

    def process_result_value(
        self, value: PgRange[date] | None, dialect: Dialect
    ) -> DateOnlyRange | None:
        """Convert psycopg PgRange back to DateOnlyRange."""
        if value is None or value.isempty:
            return None
        if value.lower is None or value.upper is None:
            return None
        # PostgreSQL daterange canonicalizes to "[)" so upper is exclusive
        return DateOnlyRange(start=value.lower, end=value.upper - timedelta(days=1))


__all__ = [
    "Range",
    "IntRange",
    "DateTimeRange",
    "DateOnlyRange",
    "Int8RangeType",
    "TstzRangeType",
    "DateRangeType",
]
