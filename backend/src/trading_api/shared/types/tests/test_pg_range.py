"""Tests for TstzRange Pydantic type.

Validates:
- Parsing from tuple, dict, and Range objects
- Serialization to JSON-compatible dict
- Timezone handling (naive → UTC)
- Error handling for invalid inputs
"""

from datetime import datetime, timezone

import pytest
from psycopg.types.range import TimestamptzRange

from trading_api.shared.types.pg_range import (
    DEFAULT_BOUNDS,
    TstzRange,
    parse_tstzrange,
    serialize_tstzrange,
)

# =============================================================================
# Test Data
# =============================================================================

# Timezone-aware datetimes
DT_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
DT_END = datetime(2026, 1, 30, 0, 0, 0, tzinfo=timezone.utc)

# Naive datetimes (should be converted to UTC)
DT_START_NAIVE = datetime(2026, 1, 1, 0, 0, 0)
DT_END_NAIVE = datetime(2026, 1, 30, 0, 0, 0)


# =============================================================================
# Parsing Tests
# =============================================================================


class TestParseFromTuple:
    """Test parsing from tuple[datetime, datetime]."""

    def test_parse_tuple_tz_aware(self) -> None:
        """Parse tuple with timezone-aware datetimes."""
        result = parse_tstzrange((DT_START, DT_END))

        assert isinstance(result, TimestamptzRange)
        assert result.lower == DT_START
        assert result.upper == DT_END
        assert result.bounds == DEFAULT_BOUNDS  # "[)"

    def test_parse_tuple_naive_converts_to_utc(self) -> None:
        """Parse tuple with naive datetimes - should convert to UTC."""
        result = parse_tstzrange((DT_START_NAIVE, DT_END_NAIVE))

        assert result.lower is not None
        assert result.upper is not None
        assert result.lower.tzinfo == timezone.utc
        assert result.upper.tzinfo == timezone.utc
        assert result.lower == DT_START  # Same instant

    def test_parse_list_same_as_tuple(self) -> None:
        """Parse list with same behavior as tuple."""
        result = parse_tstzrange([DT_START, DT_END])

        assert isinstance(result, TimestamptzRange)
        assert result.lower == DT_START

    def test_parse_tuple_with_none_bounds(self) -> None:
        """Parse tuple with None for unbounded ranges."""
        result = parse_tstzrange((None, DT_END))

        assert result.lower is None
        assert result.upper == DT_END


class TestParseFromDict:
    """Test parsing from dict representation."""

    def test_parse_dict_with_datetime_values(self) -> None:
        """Parse dict with datetime objects."""
        result = parse_tstzrange({"lower": DT_START, "upper": DT_END, "bounds": "[)"})

        assert result.lower == DT_START
        assert result.upper == DT_END
        assert result.bounds == "[)"

    def test_parse_dict_with_iso_strings(self) -> None:
        """Parse dict with ISO format datetime strings."""
        result = parse_tstzrange(
            {
                "lower": "2026-01-01T00:00:00+00:00",
                "upper": "2026-01-30T00:00:00Z",  # Z suffix
                "bounds": "[)",
            }
        )

        assert result.lower == DT_START
        assert result.upper == DT_END

    def test_parse_dict_default_bounds(self) -> None:
        """Parse dict without bounds - should use default [)."""
        result = parse_tstzrange(
            {
                "lower": DT_START,
                "upper": DT_END,
            }
        )

        assert result.bounds == DEFAULT_BOUNDS

    def test_parse_dict_all_bounds_variants(self) -> None:
        """Parse dict with all valid bounds combinations."""
        for bounds in ("[]", "[)", "(]", "()"):
            result = parse_tstzrange(
                {
                    "lower": DT_START,
                    "upper": DT_END,
                    "bounds": bounds,
                }
            )
            assert result.bounds == bounds

    def test_parse_dict_invalid_bounds_raises(self) -> None:
        """Invalid bounds string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid bounds"):
            parse_tstzrange(
                {
                    "lower": DT_START,
                    "upper": DT_END,
                    "bounds": "XX",  # Invalid
                }
            )


class TestParseFromRange:
    """Test parsing from TimestamptzRange passthrough."""

    def test_passthrough_timestamptzrange(self) -> None:
        """TimestamptzRange should pass through unchanged."""
        original = TimestamptzRange(DT_START, DT_END, "[)")
        result = parse_tstzrange(original)

        assert result is original  # Same object


class TestParseErrors:
    """Test error handling for invalid inputs."""

    def test_invalid_type_raises_typeerror(self) -> None:
        """Non-supported types should raise TypeError."""
        with pytest.raises(TypeError, match="Cannot parse"):
            parse_tstzrange("not a range")

    def test_tuple_wrong_length_raises(self) -> None:
        """Tuple with wrong length should raise."""
        with pytest.raises(TypeError, match="Cannot parse"):
            parse_tstzrange((DT_START,))  # Only 1 element

    def test_tuple_non_datetime_raises(self) -> None:
        """Tuple with non-datetime values should raise."""
        with pytest.raises(ValueError, match="must be datetime"):
            parse_tstzrange(("not a date", DT_END))


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialize:
    """Test serialization to JSON-compatible dict."""

    def test_serialize_to_dict(self) -> None:
        """Serialize range to dict with ISO strings."""
        range_obj = TimestamptzRange(DT_START, DT_END, "[)")
        result = serialize_tstzrange(range_obj)

        assert result == {
            "lower": "2026-01-01T00:00:00+00:00",
            "upper": "2026-01-30T00:00:00+00:00",
            "bounds": "[)",
        }

    def test_serialize_unbounded_lower(self) -> None:
        """Serialize range with unbounded lower."""
        range_obj = TimestamptzRange(None, DT_END, "()")
        result = serialize_tstzrange(range_obj)

        assert result["lower"] is None
        assert result["upper"] == "2026-01-30T00:00:00+00:00"

    def test_serialize_empty_range(self) -> None:
        """Serialize empty range."""
        range_obj = TimestamptzRange(empty=True)
        result = serialize_tstzrange(range_obj)

        assert result == {"lower": None, "upper": None, "bounds": "()"}


# =============================================================================
# Round-trip Tests
# =============================================================================


class TestRoundTrip:
    """Test parse → serialize → parse identity."""

    def test_roundtrip_tuple(self) -> None:
        """Round-trip from tuple."""
        original = (DT_START, DT_END)
        parsed = parse_tstzrange(original)
        serialized = serialize_tstzrange(parsed)
        reparsed = parse_tstzrange(serialized)

        assert reparsed.lower == DT_START
        assert reparsed.upper == DT_END
        assert reparsed.bounds == DEFAULT_BOUNDS

    def test_roundtrip_dict(self) -> None:
        """Round-trip from dict."""
        original = {"lower": DT_START, "upper": DT_END, "bounds": "(]"}
        parsed = parse_tstzrange(original)
        serialized = serialize_tstzrange(parsed)
        reparsed = parse_tstzrange(serialized)

        assert reparsed.lower == original["lower"]
        assert reparsed.upper == original["upper"]
        assert reparsed.bounds == "(]"


# =============================================================================
# Pydantic Integration Tests
# =============================================================================


class TestPydanticIntegration:
    """Test TstzRange works with Pydantic models."""

    def test_pydantic_model_validation(self) -> None:
        """TstzRange validates in Pydantic model."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            time_range: TstzRange

        model = TestModel(time_range=TimestamptzRange(DT_START, DT_END, "[)"))

        assert isinstance(model.time_range, TimestamptzRange)
        assert model.time_range.lower == DT_START

    def test_pydantic_model_serialization(self) -> None:
        """TstzRange serializes correctly in Pydantic model."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            time_range: TstzRange

        model = TestModel(time_range=TimestamptzRange(DT_START, DT_END, "[)"))
        data = model.model_dump(mode="json")

        assert data["time_range"]["lower"] == "2026-01-01T00:00:00+00:00"
        assert data["time_range"]["bounds"] == "[)"

    def test_pydantic_model_from_dict(self) -> None:
        """TstzRange parses from dict in Pydantic model."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            time_range: TstzRange

        model = TestModel.model_validate(
            {
                "time_range": {
                    "lower": "2026-01-01T00:00:00Z",
                    "upper": "2026-01-30T00:00:00Z",
                    "bounds": "[)",
                }
            }
        )

        assert model.time_range.lower == DT_START
        assert model.time_range.upper == DT_END
