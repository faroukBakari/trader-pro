"""Tests for CoordinationRepository gap detection.

[ARCHITECTURE] Wave 3B: CHECKPOINT 5 tests for gap detection via native
PostgreSQL range operations.

Test scenarios:
- No coverage: full requested range is a gap
- Full coverage: no gaps returned
- Partial coverage: multiple gaps computed correctly
- Adjacent ranges: properly merged by range_agg()
"""

from datetime import datetime, timezone

import pytest
from psycopg.types.range import TimestamptzRange

from trading_api.modules.datafeed.coordination_repository import CoordinationRepository


class TestFindGaps:
    """Test gap detection with various coverage scenarios."""

    @pytest.fixture
    def jan_1(self) -> datetime:
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_5(self) -> datetime:
        return datetime(2024, 1, 5, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_10(self) -> datetime:
        return datetime(2024, 1, 10, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_15(self) -> datetime:
        return datetime(2024, 1, 15, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_20(self) -> datetime:
        return datetime(2024, 1, 20, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_30(self) -> datetime:
        return datetime(2024, 1, 30, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_no_coverage_returns_full_range(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_30: datetime,
    ) -> None:
        """When no coverage exists, the entire requested range is a gap."""
        requested = TimestamptzRange(jan_1, jan_30, "[)")

        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        # Should return single gap = full requested range
        assert len(gaps) == 1
        assert gaps[0].lower == jan_1
        assert gaps[0].upper == jan_30

    @pytest.mark.asyncio
    async def test_full_coverage_returns_empty(
        self,
        coordination_repo: CoordinationRepository,
        jan_5: datetime,
        jan_10: datetime,
        jan_1: datetime,
        jan_15: datetime,
    ) -> None:
        """When requested range is fully covered, no gaps returned."""
        # Record coverage that fully includes requested range [Jan 5, Jan 10)
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_1, jan_15, "[)"),
        )

        requested = TimestamptzRange(jan_5, jan_10, "[)")
        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        assert gaps == []

    @pytest.mark.asyncio
    async def test_multiple_gaps(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_5: datetime,
        jan_10: datetime,
        jan_15: datetime,
        jan_20: datetime,
        jan_30: datetime,
    ) -> None:
        """Multiple gaps computed correctly from fragmented coverage."""
        # Coverage: [Jan 5-10), [Jan 15-20)
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_5, jan_10, "[)"),
        )
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_15, jan_20, "[)"),
        )

        # Request [Jan 1, Jan 30)
        # Expected gaps: [Jan 1-5), [Jan 10-15), [Jan 20-30)
        requested = TimestamptzRange(jan_1, jan_30, "[)")
        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        assert len(gaps) == 3

        # Gap 1: [Jan 1, Jan 5)
        assert gaps[0].lower == jan_1
        assert gaps[0].upper == jan_5

        # Gap 2: [Jan 10, Jan 15)
        assert gaps[1].lower == jan_10
        assert gaps[1].upper == jan_15

        # Gap 3: [Jan 20, Jan 30)
        assert gaps[2].lower == jan_20
        assert gaps[2].upper == jan_30

    @pytest.mark.asyncio
    async def test_adjacent_ranges_merged(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_5: datetime,
        jan_10: datetime,
        jan_15: datetime,
    ) -> None:
        """Adjacent coverage ranges are merged by range_agg()."""
        # Two adjacent ranges: [Jan 1-5), [Jan 5-10)
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_1, jan_5, "[)"),
        )
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_5, jan_10, "[)"),
        )

        # Request [Jan 1, Jan 15) - should have one gap [Jan 10, Jan 15)
        requested = TimestamptzRange(jan_1, jan_15, "[)")
        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        assert len(gaps) == 1
        assert gaps[0].lower == jan_10
        assert gaps[0].upper == jan_15

    @pytest.mark.asyncio
    async def test_empty_requested_range(
        self,
        coordination_repo: CoordinationRepository,
    ) -> None:
        """Empty requested range returns no gaps."""
        # Empty range
        requested = TimestamptzRange(empty=True)

        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        assert gaps == []

    @pytest.mark.asyncio
    async def test_different_symbol_not_counted(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_10: datetime,
        jan_30: datetime,
    ) -> None:
        """Coverage for different symbol doesn't affect gap calculation."""
        # Record coverage for GOOG, not AAPL
        await coordination_repo.record_coverage(
            symbol="GOOG",
            resolution="1D",
            time_range=TimestamptzRange(jan_1, jan_30, "[)"),
        )

        # AAPL should have no coverage
        requested = TimestamptzRange(jan_1, jan_10, "[)")
        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        assert len(gaps) == 1
        assert gaps[0] == requested

    @pytest.mark.asyncio
    async def test_different_resolution_not_counted(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_10: datetime,
        jan_30: datetime,
    ) -> None:
        """Coverage for different resolution doesn't affect gap calculation."""
        # Record coverage for 1H, not 1D
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="60",  # 1 hour
            time_range=TimestamptzRange(jan_1, jan_30, "[)"),
        )

        # 1D should have no coverage
        requested = TimestamptzRange(jan_1, jan_10, "[)")
        gaps = await coordination_repo.find_gaps("AAPL", "1D", requested)

        assert len(gaps) == 1


class TestIsCovered:
    """Test coverage check functionality."""

    @pytest.fixture
    def jan_1(self) -> datetime:
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_15(self) -> datetime:
        return datetime(2024, 1, 15, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_5(self) -> datetime:
        return datetime(2024, 1, 5, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_10(self) -> datetime:
        return datetime(2024, 1, 10, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_covered_returns_true(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_5: datetime,
        jan_10: datetime,
        jan_15: datetime,
    ) -> None:
        """Returns True when range is fully covered."""
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_1, jan_15, "[)"),
        )

        requested = TimestamptzRange(jan_5, jan_10, "[)")

        assert await coordination_repo.is_covered("AAPL", "1D", requested) is True

    @pytest.mark.asyncio
    async def test_not_covered_returns_false(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_15: datetime,
    ) -> None:
        """Returns False when no coverage exists."""
        requested = TimestamptzRange(jan_1, jan_15, "[)")

        assert await coordination_repo.is_covered("AAPL", "1D", requested) is False

    @pytest.mark.asyncio
    async def test_partial_coverage_returns_false(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_10: datetime,
        jan_15: datetime,
    ) -> None:
        """Returns False when only partially covered."""
        # Coverage only [Jan 1, Jan 10)
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=TimestamptzRange(jan_1, jan_10, "[)"),
        )

        # Request [Jan 1, Jan 15) - partially covered
        requested = TimestamptzRange(jan_1, jan_15, "[)")

        assert await coordination_repo.is_covered("AAPL", "1D", requested) is False

    @pytest.mark.asyncio
    async def test_empty_range_always_covered(
        self,
        coordination_repo: CoordinationRepository,
    ) -> None:
        """Empty range is always considered covered."""
        empty = TimestamptzRange(empty=True)

        assert await coordination_repo.is_covered("AAPL", "1D", empty) is True


class TestRecordCoverage:
    """Test coverage recording functionality."""

    @pytest.fixture
    def jan_1(self) -> datetime:
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def jan_15(self) -> datetime:
        return datetime(2024, 1, 15, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_record_creates_entry(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_15: datetime,
    ) -> None:
        """Recording coverage creates a database entry."""
        time_range = TimestamptzRange(jan_1, jan_15, "[)")

        covered = await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=time_range,
            storage="buffer",
            row_count=100,
        )

        assert covered.id is not None
        assert covered.symbol == "AAPL"
        assert covered.resolution == "1D"
        assert covered.range_start == jan_1
        assert covered.range_end == jan_15
        assert covered.storage == "buffer"
        assert covered.row_count == 100

    @pytest.mark.asyncio
    async def test_recorded_coverage_affects_gaps(
        self,
        coordination_repo: CoordinationRepository,
        jan_1: datetime,
        jan_15: datetime,
    ) -> None:
        """Recorded coverage is reflected in gap detection."""
        time_range = TimestamptzRange(jan_1, jan_15, "[)")

        # Initially has gaps
        gaps_before = await coordination_repo.find_gaps("AAPL", "1D", time_range)
        assert len(gaps_before) == 1

        # Record coverage
        await coordination_repo.record_coverage(
            symbol="AAPL",
            resolution="1D",
            time_range=time_range,
        )

        # Now fully covered
        gaps_after = await coordination_repo.find_gaps("AAPL", "1D", time_range)
        assert gaps_after == []
