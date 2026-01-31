"""Integration tests for TSTZRANGE column roundtrip.

[ARCHITECTURE] Wave 3B: CHECKPOINT 2 tests for SQLAlchemy/PostgreSQL integration.

Tests verify that TstzRange type works correctly with:
- SQLAlchemy TSTZRANGE column type
- psycopg3 range type adapters
- SQLModel create/read operations
"""

from datetime import datetime, timezone

import pytest
from psycopg.types.range import TimestamptzRange
from sqlalchemy import text
from sqlmodel import Session, select

from trading_api.models.coordination import CoveredRange


class TestTstzrangeRoundtrip:
    """Test TSTZRANGE column roundtrip through SQLModel."""

    @pytest.fixture
    def sample_range(self) -> TimestamptzRange:
        """Create a sample time range for testing."""
        return TimestamptzRange(
            datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            "[)",  # inclusive lower, exclusive upper
        )

    def test_create_with_time_range(
        self, db_session: Session, sample_range: TimestamptzRange
    ) -> None:
        """CoveredRange with time_range can be created and retrieved."""
        # Create range with both old and new columns
        assert sample_range.lower is not None and sample_range.upper is not None
        covered = CoveredRange(
            symbol="AAPL",
            resolution="1D",
            range_start=sample_range.lower,
            range_end=sample_range.upper,
            time_range=sample_range,
            storage="buffer",
        )

        db_session.add(covered)
        db_session.commit()
        db_session.refresh(covered)

        # Verify time_range was persisted
        # psycopg3 returns a Range-like object - use duck typing
        assert covered.id is not None
        assert covered.time_range is not None
        assert hasattr(covered.time_range, "lower")
        assert hasattr(covered.time_range, "upper")
        assert hasattr(covered.time_range, "bounds")
        assert covered.time_range.lower == sample_range.lower
        assert covered.time_range.upper == sample_range.upper
        assert covered.time_range.bounds == "[)"

    def test_read_time_range_from_db(
        self, db_session: Session, sample_range: TimestamptzRange
    ) -> None:
        """time_range is correctly read from database as TimestamptzRange."""
        # Insert directly
        assert sample_range.lower is not None and sample_range.upper is not None
        covered = CoveredRange(
            symbol="TSLA",
            resolution="60",
            range_start=sample_range.lower,
            range_end=sample_range.upper,
            time_range=sample_range,
            storage="parquet",
            file_path="/data/tsla_60.parquet",
        )
        db_session.add(covered)
        db_session.commit()

        # Query back
        result = db_session.exec(
            select(CoveredRange).where(CoveredRange.symbol == "TSLA")
        ).first()

        assert result is not None
        assert result.time_range is not None
        assert result.time_range.lower == datetime(
            2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        )
        assert result.time_range.upper == datetime(
            2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc
        )

    def test_time_range_nullable(self, db_session: Session) -> None:
        """time_range can be NULL for backwards compatibility."""
        covered = CoveredRange(
            symbol="GOOG",
            resolution="1D",
            range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            time_range=None,  # Explicitly NULL during migration
            storage="buffer",
        )

        db_session.add(covered)
        db_session.commit()
        db_session.refresh(covered)

        assert covered.time_range is None

    def test_time_range_from_tuple(self, db_session: Session) -> None:
        """time_range accepts tuple input through Pydantic validation."""
        start = datetime(2024, 6, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 30, tzinfo=timezone.utc)

        # Create with explicit TimestamptzRange
        covered = CoveredRange(
            symbol="AMZN",
            resolution="1D",
            range_start=start,
            range_end=end,
            time_range=TimestamptzRange(start, end, "[)"),
            storage="buffer",
        )

        db_session.add(covered)
        db_session.commit()
        db_session.refresh(covered)

        # Verify range persisted correctly
        assert covered.time_range is not None
        assert covered.time_range.lower == start
        assert covered.time_range.upper == end

    def test_range_operators_work(self, db_session: Session) -> None:
        """PostgreSQL range operators work on time_range column."""
        # Insert test data
        ranges = [
            CoveredRange(
                symbol="SPY",
                resolution="1D",
                range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                range_end=datetime(2024, 1, 10, tzinfo=timezone.utc),
                time_range=TimestamptzRange(
                    datetime(2024, 1, 1, tzinfo=timezone.utc),
                    datetime(2024, 1, 10, tzinfo=timezone.utc),
                    "[)",
                ),
                storage="buffer",
            ),
            CoveredRange(
                symbol="SPY",
                resolution="1D",
                range_start=datetime(2024, 1, 15, tzinfo=timezone.utc),
                range_end=datetime(2024, 1, 25, tzinfo=timezone.utc),
                time_range=TimestamptzRange(
                    datetime(2024, 1, 15, tzinfo=timezone.utc),
                    datetime(2024, 1, 25, tzinfo=timezone.utc),
                    "[)",
                ),
                storage="buffer",
            ),
        ]
        db_session.add_all(ranges)
        db_session.commit()

        # Test overlap query with && operator
        # Use literal string substitution since this is a test-only query
        result = db_session.execute(
            text(
                """
                SELECT id, time_range
                FROM covered_ranges
                WHERE symbol = 'SPY'
                AND time_range && '[2024-01-05 00:00:00+00, 2024-01-20 00:00:00+00)'::tstzrange
                """
            ),
        )
        overlapping = result.fetchall()

        # Both ranges should overlap [Jan 5, Jan 20)
        assert len(overlapping) == 2

    def test_range_containment(self, db_session: Session) -> None:
        """Test @> containment operator on time_range."""
        covered = CoveredRange(
            symbol="QQQ",
            resolution="60",
            range_start=datetime(2024, 3, 1, tzinfo=timezone.utc),
            range_end=datetime(2024, 3, 31, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 3, 1, tzinfo=timezone.utc),
                datetime(2024, 3, 31, tzinfo=timezone.utc),
                "[)",
            ),
            storage="buffer",
        )
        db_session.add(covered)
        db_session.commit()

        # Test point containment
        result = db_session.execute(
            text(
                """
                SELECT id
                FROM covered_ranges
                WHERE symbol = 'QQQ'
                AND time_range @> '2024-03-15 12:00:00+00'::timestamptz
                """
            )
        )
        containing = result.fetchall()
        assert len(containing) == 1

        # Test range containment
        result = db_session.execute(
            text(
                """
                SELECT id
                FROM covered_ranges
                WHERE symbol = 'QQQ'
                AND time_range @> '[2024-03-10 00:00:00+00, 2024-03-20 00:00:00+00)'::tstzrange
                """
            )
        )
        containing = result.fetchall()
        assert len(containing) == 1


class TestExclusionConstraint:
    """Test EXCLUDE constraint prevents overlapping ranges."""

    def test_adjacent_ranges_allowed(self, db_session: Session) -> None:
        """Adjacent ranges (no overlap) should be allowed."""
        # First range: Jan 1-10
        range1 = CoveredRange(
            symbol="MSFT",
            resolution="1D",
            range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 10, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 10, tzinfo=timezone.utc),
                "[)",  # [Jan 1, Jan 10)
            ),
            storage="buffer",
        )
        db_session.add(range1)
        db_session.commit()

        # Second range: Jan 10-20 (adjacent, no overlap with [) bounds)
        range2 = CoveredRange(
            symbol="MSFT",
            resolution="1D",
            range_start=datetime(2024, 1, 10, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 20, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 10, tzinfo=timezone.utc),
                datetime(2024, 1, 20, tzinfo=timezone.utc),
                "[)",  # [Jan 10, Jan 20)
            ),
            storage="buffer",
        )
        db_session.add(range2)
        # Should NOT raise - adjacent ranges allowed
        db_session.commit()

        # Verify both exist
        result = db_session.exec(
            select(CoveredRange).where(CoveredRange.symbol == "MSFT")
        ).all()
        assert len(result) == 2

    def test_overlapping_ranges_rejected(self, db_session: Session) -> None:
        """Overlapping ranges should be rejected by EXCLUDE constraint."""
        from psycopg.errors import ExclusionViolation
        from sqlalchemy.exc import IntegrityError

        # First range: Jan 1-15
        range1 = CoveredRange(
            symbol="NVDA",
            resolution="1D",
            range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 15, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 15, tzinfo=timezone.utc),
                "[)",
            ),
            storage="buffer",
        )
        db_session.add(range1)
        db_session.commit()

        # Second range: Jan 10-25 (overlaps with first)
        range2 = CoveredRange(
            symbol="NVDA",
            resolution="1D",
            range_start=datetime(2024, 1, 10, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 25, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 10, tzinfo=timezone.utc),
                datetime(2024, 1, 25, tzinfo=timezone.utc),
                "[)",  # Overlaps [Jan 10, Jan 15) with first range
            ),
            storage="buffer",
        )
        db_session.add(range2)

        # Should raise exclusion violation
        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        # Verify it's an exclusion violation (not other constraint)
        assert "excl_covered_ranges_overlap" in str(exc_info.value) or isinstance(
            exc_info.value.__cause__, ExclusionViolation
        )

    def test_different_symbols_can_overlap(self, db_session: Session) -> None:
        """Different symbols can have overlapping time ranges."""
        # AAPL: Jan 1-15
        range_aapl = CoveredRange(
            symbol="AAPL",
            resolution="1D",
            range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 15, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 15, tzinfo=timezone.utc),
                "[)",
            ),
            storage="buffer",
        )
        db_session.add(range_aapl)

        # GOOG: Jan 5-20 (overlaps in time but different symbol)
        range_goog = CoveredRange(
            symbol="GOOG",
            resolution="1D",
            range_start=datetime(2024, 1, 5, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 20, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 5, tzinfo=timezone.utc),
                datetime(2024, 1, 20, tzinfo=timezone.utc),
                "[)",
            ),
            storage="buffer",
        )
        db_session.add(range_goog)

        # Should NOT raise - different symbols
        db_session.commit()

        # Verify both exist
        assert (
            db_session.exec(
                select(CoveredRange).where(CoveredRange.symbol == "AAPL")
            ).first()
            is not None
        )
        assert (
            db_session.exec(
                select(CoveredRange).where(CoveredRange.symbol == "GOOG")
            ).first()
            is not None
        )

    def test_different_resolutions_can_overlap(self, db_session: Session) -> None:
        """Same symbol with different resolutions can have overlapping ranges."""
        # META 1D: Jan 1-15
        range_1d = CoveredRange(
            symbol="META",
            resolution="1D",
            range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 15, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 15, tzinfo=timezone.utc),
                "[)",
            ),
            storage="buffer",
        )
        db_session.add(range_1d)

        # META 60: Jan 5-20 (overlaps in time but different resolution)
        range_60 = CoveredRange(
            symbol="META",
            resolution="60",
            range_start=datetime(2024, 1, 5, tzinfo=timezone.utc),
            range_end=datetime(2024, 1, 20, tzinfo=timezone.utc),
            time_range=TimestamptzRange(
                datetime(2024, 1, 5, tzinfo=timezone.utc),
                datetime(2024, 1, 20, tzinfo=timezone.utc),
                "[)",
            ),
            storage="buffer",
        )
        db_session.add(range_60)

        # Should NOT raise - different resolutions
        db_session.commit()

        result = db_session.exec(
            select(CoveredRange).where(CoveredRange.symbol == "META")
        ).all()
        assert len(result) == 2
