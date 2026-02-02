"""PostgreSQL type adapters for custom domain types.

This package provides psycopg3 adapters for seamless conversion between
application domain types and PostgreSQL native types.
"""

from .range_adapter import (
    DateRangeBinaryDumper,
    DateRangeBinaryLoader,
    DateRangeDumper,
    DateRangeLoader,
    Int8RangeBinaryDumper,
    Int8RangeBinaryLoader,
    Int8RangeDumper,
    Int8RangeLoader,
    TimeRangeBinaryLoader,
    TimeRangeLoader,
    TstzRangeBinaryDumper,
    TstzRangeBinaryLoader,
    TstzRangeDumper,
    TstzRangeLoader,
    register_int_range_loader,
    register_range_adapters,
)

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
