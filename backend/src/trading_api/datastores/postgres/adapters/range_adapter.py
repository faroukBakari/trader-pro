"""psycopg3 adapters for Range[T] ↔ PostgreSQL range type conversion.

Thin wrappers using psycopg's public API (dump_range_text, load_range_text, etc.)
to convert between application Range models and PostgreSQL range types.

Usage:
    from trading_api.datastores.postgres.adapters import register_range_adapters

    async with await psycopg.AsyncConnection.connect(conninfo) as conn:
        register_range_adapters(conn)
        # Range subclasses now auto-convert to/from PostgreSQL ranges

Supported mappings:
    - TimeRange (int ms) ↔ int8range
    - IntRange (int) ↔ int8range
    - DateTimeRange (datetime) ↔ tstzrange
    - DateOnlyRange (date) ↔ daterange

Notes:
    - All Range types use inclusive bounds "[]"; PostgreSQL may canonicalize
    - Empty ranges are not supported (Range requires start/end)
    - Unbounded ranges (NULL lower/upper) are not supported
    - Both TEXT and BINARY formats supported
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, TypeVar

from psycopg.abc import Buffer
from psycopg.adapt import Dumper, Loader
from psycopg.postgres import types as pg_types
from psycopg.pq import Format
from psycopg.types.range import Range as PgRange
from psycopg.types.range import (
    dump_range_binary,
    dump_range_text,
    load_range_binary,
    load_range_text,
)

from trading_api.models.market import TimeRange
from trading_api.types import DateOnlyRange, DateTimeRange, IntRange, Range

if TYPE_CHECKING:
    from psycopg import AsyncConnection, Connection


# Type variables
T = TypeVar("T", int, datetime, date)
R = TypeVar("R", bound=Range)


# =============================================================================
# Element Serializers (module-level to avoid closure allocation)
# =============================================================================


def _dump_int(x: int) -> bytes:
    return str(x).encode("utf-8")


def _load_int(b: Buffer) -> int:
    return int(bytes(b).decode("utf-8"))


def _dump_datetime(x: datetime) -> bytes:
    return x.isoformat().encode("utf-8")


def _load_datetime(b: Buffer) -> datetime:
    return datetime.fromisoformat(bytes(b).decode("utf-8"))


def _dump_date(x: date) -> bytes:
    return x.isoformat().encode("utf-8")


def _load_date(b: Buffer) -> date:
    return date.fromisoformat(bytes(b).decode("utf-8"))


# Binary format element serializers
def _dump_int_binary(x: int) -> bytes:
    return x.to_bytes(8, "big", signed=True)


def _load_int_binary(b: Buffer) -> int:
    return int.from_bytes(bytes(b), "big", signed=True)


def _dump_datetime_binary(x: datetime) -> bytes:
    # PostgreSQL timestamptz: microseconds since 2000-01-01 00:00:00 UTC
    pg_epoch = datetime(2000, 1, 1, tzinfo=x.tzinfo)
    delta = x - pg_epoch
    microseconds = int(delta.total_seconds() * 1_000_000)
    return microseconds.to_bytes(8, "big", signed=True)


def _load_datetime_binary(b: Buffer) -> datetime:
    from datetime import timezone

    microseconds = int.from_bytes(bytes(b), "big", signed=True)
    pg_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    return pg_epoch + timedelta(microseconds=microseconds)


def _dump_date_binary(x: date) -> bytes:
    # PostgreSQL date: days since 2000-01-01
    pg_epoch = date(2000, 1, 1)
    days = (x - pg_epoch).days
    return days.to_bytes(4, "big", signed=True)


def _load_date_binary(b: Buffer) -> date:
    days = int.from_bytes(bytes(b), "big", signed=True)
    pg_epoch = date(2000, 1, 1)
    return pg_epoch + timedelta(days=days)


# =============================================================================
# Conversion Helpers
# =============================================================================


def _from_pg_range(
    pg_range: PgRange[T],
    range_cls: type[R],
    is_discrete: bool = False,
) -> R:
    """Convert psycopg Range to application Range.

    Handles PostgreSQL's canonical form adjustment for discrete ranges.
    """
    if pg_range.isempty:
        raise ValueError("Cannot convert empty range to Range")

    if pg_range.lower is None or pg_range.upper is None:
        raise ValueError("Cannot convert unbounded range to Range")

    lower = pg_range.lower
    upper = pg_range.upper

    # Adjust for PostgreSQL's canonical form on discrete ranges
    # int8range and daterange canonicalize "[a,b]" to "[a,b+1)"
    if is_discrete:
        if pg_range.bounds == "[)":
            upper = _decrement(upper)
        elif pg_range.bounds == "(]":
            lower = _increment(lower)
        elif pg_range.bounds == "()":
            lower = _increment(lower)
            upper = _decrement(upper)

    return range_cls(start=lower, end=upper)


def _increment(value: T) -> T:
    """Increment value by 1 unit (for discrete ranges)."""
    if isinstance(value, int):
        return value + 1
    elif isinstance(value, date):
        return value + timedelta(days=1)
    return value


def _decrement(value: T) -> T:
    """Decrement value by 1 unit (for discrete ranges)."""
    if isinstance(value, int):
        return value - 1
    elif isinstance(value, date):
        return value - timedelta(days=1)
    return value


# =============================================================================
# Dumpers - Composition using standalone functions
# =============================================================================


class Int8RangeDumper(Dumper):
    """Dumps IntRange/TimeRange → PostgreSQL int8range (TEXT)."""

    format = Format.TEXT
    oid = pg_types["int8range"].oid

    def dump(self, obj: Range[int]) -> Buffer:
        pg_range: PgRange[int] = PgRange(obj.start, obj.end, "[]")
        return dump_range_text(pg_range, _dump_int)


class Int8RangeBinaryDumper(Dumper):
    """Dumps IntRange/TimeRange → PostgreSQL int8range (BINARY)."""

    format = Format.BINARY
    oid = pg_types["int8range"].oid

    def dump(self, obj: Range[int]) -> Buffer:
        pg_range: PgRange[int] = PgRange(obj.start, obj.end, "[]")
        return dump_range_binary(pg_range, _dump_int_binary)


class TstzRangeDumper(Dumper):
    """Dumps DateTimeRange → PostgreSQL tstzrange (TEXT)."""

    format = Format.TEXT
    oid = pg_types["tstzrange"].oid

    def dump(self, obj: Range[datetime]) -> Buffer:
        pg_range: PgRange[datetime] = PgRange(obj.start, obj.end, "[]")
        return dump_range_text(pg_range, _dump_datetime)


class TstzRangeBinaryDumper(Dumper):
    """Dumps DateTimeRange → PostgreSQL tstzrange (BINARY)."""

    format = Format.BINARY
    oid = pg_types["tstzrange"].oid

    def dump(self, obj: Range[datetime]) -> Buffer:
        pg_range: PgRange[datetime] = PgRange(obj.start, obj.end, "[]")
        return dump_range_binary(pg_range, _dump_datetime_binary)


class DateRangeDumper(Dumper):
    """Dumps DateOnlyRange → PostgreSQL daterange (TEXT)."""

    format = Format.TEXT
    oid = pg_types["daterange"].oid

    def dump(self, obj: Range[date]) -> Buffer:
        pg_range: PgRange[date] = PgRange(obj.start, obj.end, "[]")
        return dump_range_text(pg_range, _dump_date)


class DateRangeBinaryDumper(Dumper):
    """Dumps DateOnlyRange → PostgreSQL daterange (BINARY)."""

    format = Format.BINARY
    oid = pg_types["daterange"].oid

    def dump(self, obj: Range[date]) -> Buffer:
        pg_range: PgRange[date] = PgRange(obj.start, obj.end, "[]")
        return dump_range_binary(pg_range, _dump_date_binary)


# =============================================================================
# Loaders - Composition using standalone functions
# =============================================================================


class Int8RangeLoader(Loader):
    """Loads PostgreSQL int8range → IntRange (TEXT)."""

    format = Format.TEXT

    def load(self, data: Buffer) -> IntRange:
        pg_range, _ = load_range_text(data, _load_int)
        return _from_pg_range(pg_range, IntRange, is_discrete=True)


class Int8RangeBinaryLoader(Loader):
    """Loads PostgreSQL int8range → IntRange (BINARY)."""

    format = Format.BINARY

    def load(self, data: Buffer) -> IntRange:
        pg_range = load_range_binary(data, _load_int_binary)
        return _from_pg_range(pg_range, IntRange, is_discrete=True)


class TimeRangeLoader(Loader):
    """Loads PostgreSQL int8range → TimeRange (TEXT)."""

    format = Format.TEXT

    def load(self, data: Buffer) -> TimeRange:
        pg_range, _ = load_range_text(data, _load_int)
        return _from_pg_range(pg_range, TimeRange, is_discrete=True)


class TimeRangeBinaryLoader(Loader):
    """Loads PostgreSQL int8range → TimeRange (BINARY)."""

    format = Format.BINARY

    def load(self, data: Buffer) -> TimeRange:
        pg_range = load_range_binary(data, _load_int_binary)
        return _from_pg_range(pg_range, TimeRange, is_discrete=True)


class TstzRangeLoader(Loader):
    """Loads PostgreSQL tstzrange → DateTimeRange (TEXT)."""

    format = Format.TEXT

    def load(self, data: Buffer) -> DateTimeRange:
        pg_range, _ = load_range_text(data, _load_datetime)
        return _from_pg_range(pg_range, DateTimeRange, is_discrete=False)


class TstzRangeBinaryLoader(Loader):
    """Loads PostgreSQL tstzrange → DateTimeRange (BINARY)."""

    format = Format.BINARY

    def load(self, data: Buffer) -> DateTimeRange:
        pg_range = load_range_binary(data, _load_datetime_binary)
        return _from_pg_range(pg_range, DateTimeRange, is_discrete=False)


class DateRangeLoader(Loader):
    """Loads PostgreSQL daterange → DateOnlyRange (TEXT)."""

    format = Format.TEXT

    def load(self, data: Buffer) -> DateOnlyRange:
        pg_range, _ = load_range_text(data, _load_date)
        return _from_pg_range(pg_range, DateOnlyRange, is_discrete=True)


class DateRangeBinaryLoader(Loader):
    """Loads PostgreSQL daterange → DateOnlyRange (BINARY)."""

    format = Format.BINARY

    def load(self, data: Buffer) -> DateOnlyRange:
        pg_range = load_range_binary(data, _load_date_binary)
        return _from_pg_range(pg_range, DateOnlyRange, is_discrete=True)


# =============================================================================
# Registration
# =============================================================================


def register_range_adapters(conn: AsyncConnection | Connection) -> None:
    """Register all Range adapters on a psycopg connection.

    After registration, Range subclasses can be used directly in queries
    and will be automatically converted to/from PostgreSQL ranges.
    Both TEXT and BINARY formats are supported.

    Args:
        conn: psycopg AsyncConnection or Connection to configure

    Mappings:
        - TimeRange → int8range (ms timestamps)
        - IntRange → int8range (generic integers)
        - DateTimeRange → tstzrange (tz-aware datetime)
        - DateOnlyRange → daterange (date only)

    Example:
        async with await psycopg.AsyncConnection.connect(conninfo) as conn:
            register_range_adapters(conn)

            # Now works automatically:
            await conn.execute(
                "INSERT INTO ranges (time_range) VALUES (%s)",
                [TimeRange(start=1000, end=2000)]
            )
    """
    # Register TEXT dumpers (Python → PostgreSQL)
    conn.adapters.register_dumper(TimeRange, Int8RangeDumper)
    conn.adapters.register_dumper(IntRange, Int8RangeDumper)
    conn.adapters.register_dumper(DateTimeRange, TstzRangeDumper)
    conn.adapters.register_dumper(DateOnlyRange, DateRangeDumper)

    # Register BINARY dumpers (Python → PostgreSQL)
    conn.adapters.register_dumper(TimeRange, Int8RangeBinaryDumper)
    conn.adapters.register_dumper(IntRange, Int8RangeBinaryDumper)
    conn.adapters.register_dumper(DateTimeRange, TstzRangeBinaryDumper)
    conn.adapters.register_dumper(DateOnlyRange, DateRangeBinaryDumper)

    # Register TEXT loaders (PostgreSQL → Python)
    # Note: Only one loader per PG type. TimeRange is the default for int8range.
    conn.adapters.register_loader("int8range", TimeRangeLoader)
    conn.adapters.register_loader("tstzrange", TstzRangeLoader)
    conn.adapters.register_loader("daterange", DateRangeLoader)

    # Register BINARY loaders (PostgreSQL → Python)
    conn.adapters.register_loader("int8range", TimeRangeBinaryLoader)
    conn.adapters.register_loader("tstzrange", TstzRangeBinaryLoader)
    conn.adapters.register_loader("daterange", DateRangeBinaryLoader)


def register_int_range_loader(conn: AsyncConnection | Connection) -> None:
    """Register IntRange as the loader for int8range instead of TimeRange.

    Use this if you prefer IntRange over TimeRange when loading int8range.
    """
    conn.adapters.register_loader("int8range", Int8RangeLoader)
    conn.adapters.register_loader("int8range", Int8RangeBinaryLoader)


__all__ = [
    # Dumpers (TEXT)
    "Int8RangeDumper",
    "TstzRangeDumper",
    "DateRangeDumper",
    # Dumpers (BINARY)
    "Int8RangeBinaryDumper",
    "TstzRangeBinaryDumper",
    "DateRangeBinaryDumper",
    # Loaders (TEXT)
    "Int8RangeLoader",
    "TimeRangeLoader",
    "TstzRangeLoader",
    "DateRangeLoader",
    # Loaders (BINARY)
    "Int8RangeBinaryLoader",
    "TimeRangeBinaryLoader",
    "TstzRangeBinaryLoader",
    "DateRangeBinaryLoader",
    # Registration
    "register_range_adapters",
    "register_int_range_loader",
]
