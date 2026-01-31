"""PostgreSQL range type integration for Pydantic/SQLModel.

[ARCHITECTURE] Wave 3B: TstzRange type for coordination layer.

This module provides a Pydantic-compatible wrapper around psycopg3's
TimestamptzRange that enables:
- Validation from tuple, dict, or Range objects
- JSON serialization for API responses
- SQLAlchemy TSTZRANGE column integration via sa_column override

Usage:
    from trading_api.shared.types import TstzRange

    class CoveredRange(SQLModel, table=True):
        time_range: TstzRange = Field(
            sa_column=Column(TSTZRANGE, nullable=False)
        )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from psycopg.types.range import Range, TimestamptzRange
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

__all__ = ["TstzRange", "parse_tstzrange", "serialize_tstzrange"]

# Default bounds: [) = inclusive lower, exclusive upper
# This is the standard for time ranges (start <= t < end)
DEFAULT_BOUNDS = "[)"


def parse_tstzrange(value: Any) -> TimestamptzRange:
    """Parse various input formats into TimestamptzRange.

    Accepts:
    - TimestamptzRange: passthrough
    - tuple[datetime, datetime]: creates range with default bounds [)
    - dict: {"lower": datetime|str, "upper": datetime|str, "bounds": str}
    - Range[datetime]: generic range with datetime bounds

    Args:
        value: Input value to parse

    Returns:
        TimestamptzRange instance

    Raises:
        ValueError: If input cannot be parsed
        TypeError: If input type is not supported
    """
    # Passthrough if already correct type
    if isinstance(value, TimestamptzRange):
        return value

    # Generic Range with datetime bounds
    if isinstance(value, Range) and not isinstance(value, TimestamptzRange):
        lower = _ensure_tz_aware(value.lower) if value.lower is not None else None
        upper = _ensure_tz_aware(value.upper) if value.upper is not None else None
        bounds = value.bounds if value.bounds else DEFAULT_BOUNDS
        return TimestamptzRange(lower, upper, bounds)

    # Tuple of (start, end) datetimes
    if isinstance(value, (tuple, list)) and len(value) == 2:
        lower, upper = value
        if lower is not None and not isinstance(lower, datetime):
            raise ValueError(f"Lower bound must be datetime, got {type(lower)}")
        if upper is not None and not isinstance(upper, datetime):
            raise ValueError(f"Upper bound must be datetime, got {type(upper)}")
        lower = _ensure_tz_aware(lower) if lower is not None else None
        upper = _ensure_tz_aware(upper) if upper is not None else None
        return TimestamptzRange(lower, upper, DEFAULT_BOUNDS)

    # Dict with lower/upper/bounds keys
    if isinstance(value, dict):
        lower = _parse_datetime(value.get("lower"))
        upper = _parse_datetime(value.get("upper"))
        bounds = value.get("bounds", DEFAULT_BOUNDS)
        if bounds not in ("[]", "[)", "(]", "()"):
            raise ValueError(
                f"Invalid bounds '{bounds}', must be one of: [], [), (], ()"
            )
        return TimestamptzRange(lower, upper, bounds)

    raise TypeError(
        f"Cannot parse {type(value).__name__} as TimestamptzRange. "
        "Expected TimestamptzRange, tuple[datetime, datetime], or dict."
    )


def serialize_tstzrange(value: TimestamptzRange) -> dict[str, Any]:
    """Serialize TimestamptzRange to JSON-compatible dict.

    Output format:
        {"lower": "ISO8601", "upper": "ISO8601", "bounds": "[)"}

    Empty ranges serialize to:
        {"lower": null, "upper": null, "bounds": "()"}
    """
    if value.isempty:
        return {"lower": None, "upper": None, "bounds": "()"}

    return {
        "lower": value.lower.isoformat() if value.lower else None,
        "upper": value.upper.isoformat() if value.upper else None,
        "bounds": value.bounds or DEFAULT_BOUNDS,
    }


def _ensure_tz_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (default to UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_datetime(value: Any) -> datetime | None:
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_tz_aware(value)
    if isinstance(value, str):
        # Parse ISO format string
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _ensure_tz_aware(dt)
    raise ValueError(f"Cannot parse datetime from {type(value).__name__}: {value}")


class _TstzRangeAnnotation:
    """Pydantic custom type annotation for TimestamptzRange.

    Implements __get_pydantic_core_schema__ for full Pydantic v2 integration,
    enabling use in BaseModel/SQLModel fields without arbitrary_types_allowed.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Build Pydantic core schema with validation and serialization."""
        return core_schema.no_info_plain_validator_function(
            parse_tstzrange,
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_tstzrange,
                info_arg=False,
                return_schema=core_schema.dict_schema(),
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Generate JSON schema for OpenAPI docs."""
        return {
            "type": "object",
            "properties": {
                "lower": {"type": "string", "format": "date-time", "nullable": True},
                "upper": {"type": "string", "format": "date-time", "nullable": True},
                "bounds": {
                    "type": "string",
                    "enum": ["()", "(]", "[)", "[]"],
                    "default": "[)",
                },
            },
            "required": ["lower", "upper"],
        }


# Pydantic-compatible annotated type
# Use this in SQLModel fields with sa_column=Column(TSTZRANGE)
TstzRange = Annotated[TimestamptzRange, _TstzRangeAnnotation]
