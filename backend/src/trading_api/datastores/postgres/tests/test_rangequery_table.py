"""RangeQuerySQLModelTable unit tests.

Tests the get_missing_ranges() gap detection functionality.
Validates PostgreSQL multirange operations via SQLAlchemy expression API.
"""

from collections.abc import AsyncIterator

import pytest

from trading_api.datastores import PostgresDatastore
from trading_api.datastores.postgres.sqlmodel_table import RangeQuerySQLModelTable
from trading_api.models.market import CoveredRange, Resolution, TimeRange
from trading_api.shared.config import Settings
from trading_api.types import IntRange, StorageType

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
async def datastore(test_settings: Settings) -> AsyncIterator[PostgresDatastore]:
    """Create PostgresDatastore for testing."""
    ds = await PostgresDatastore.create(config=test_settings)
    yield ds
    await ds.close()


@pytest.fixture
async def rangequery_table(
    datastore: PostgresDatastore,
) -> AsyncIterator[RangeQuerySQLModelTable[CoveredRange]]:
    """Create RangeQuerySQLModelTable for CoveredRange."""
    tbl = datastore.rangequery_table(CoveredRange)
    assert isinstance(tbl, RangeQuerySQLModelTable)
    await tbl._ensure_table()
    await tbl.clear()
    yield tbl
    await tbl.clear()


async def _add_coverage(
    table: RangeQuerySQLModelTable[CoveredRange],
    symbol: str,
    resolution: Resolution,
    start: int,
    end: int,
    bar_count: int = 100,
) -> CoveredRange:
    """Helper to add a covered range."""
    time_range = TimeRange(start=start, end=end)
    covered = CoveredRange(
        symbol=symbol,
        resolution=resolution,
        time_range=time_range,
        storage_type=StorageType.MEMORY,
        bar_count=bar_count,
    )
    key = f"{symbol}_{resolution.value}_{start}_{end}"
    await table.set(key, covered)
    return covered


class TestRangeQuerySQLModelTable:
    """Tests for get_missing_ranges() gap detection."""

    # --- Core functionality ---

    async def test_full_miss_no_coverage(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """No covered ranges → returns full request range."""
        lookup_key = "AAPL_1D"
        query_range = IntRange(start=0, end=300)

        gaps = await rangequery_table.get_missing_ranges(
            lookup_key=lookup_key, query_range=query_range
        )

        assert len(gaps) == 1
        assert gaps[0].start == 0
        assert gaps[0].end == 300

    async def test_full_coverage_no_gaps(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Full coverage → returns empty list."""
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 300)

        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=300)
        )

        assert gaps == []

    async def test_internal_gap_detected(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Internal gap between two covered ranges — THE BUG WE'RE FIXING."""
        # Covered: [0, 100], [200, 300]
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 100)
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 200, 300)

        # Request: [0, 300]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=300)
        )

        # Expected: [IntRange(101, 199)] ← internal gap
        assert len(gaps) == 1
        assert gaps[0].start == 101
        assert gaps[0].end == 199

    async def test_multiple_internal_gaps(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Multiple internal gaps detected."""
        # Covered: [0, 50], [100, 150], [200, 250]
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 50)
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 100, 150)
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 200, 250)

        # Request: [0, 300]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=300)
        )

        # Expected: 3 gaps [51-99], [151-199], [251-300]
        assert len(gaps) == 3
        assert gaps[0].start == 51
        assert gaps[0].end == 99
        assert gaps[1].start == 151
        assert gaps[1].end == 199
        assert gaps[2].start == 251
        assert gaps[2].end == 300

    async def test_partial_overlap_start(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Request extends before coverage."""
        # Covered: [100, 300]
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 100, 300)

        # Request: [0, 300]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=300)
        )

        # Expected: [IntRange(0, 99)]
        assert len(gaps) == 1
        assert gaps[0].start == 0
        assert gaps[0].end == 99

    async def test_partial_overlap_end(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Request extends after coverage."""
        # Covered: [0, 200]
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 200)

        # Request: [0, 300]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=300)
        )

        # Expected: [IntRange(201, 300)]
        assert len(gaps) == 1
        assert gaps[0].start == 201
        assert gaps[0].end == 300

    # --- Edge cases ---

    async def test_adjacent_ranges_no_gap(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Adjacent covered ranges have no gap."""
        # Covered: [0, 100], [101, 200] ← adjacent
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 100)
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 101, 200)

        # Request: [0, 200]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=200)
        )

        # Expected: []
        assert gaps == []

    async def test_single_point_gap(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Single-point gap detected."""
        # Covered: [0, 99], [101, 200] ← gap at 100
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 99)
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 101, 200)

        # Request: [0, 200]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=200)
        )

        # Expected: [IntRange(100, 100)]
        assert len(gaps) == 1
        assert gaps[0].start == 100
        assert gaps[0].end == 100

    async def test_lookup_key_isolation(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Different lookup_keys don't affect each other."""
        # Covered: AAPL [0, 300], MSFT [0, 100]
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 300)
        await _add_coverage(rangequery_table, "MSFT", Resolution.DAY_1, 0, 100)

        # Request: MSFT [0, 300]
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="MSFT_1D", query_range=IntRange(start=0, end=300)
        )

        # Expected: [IntRange(101, 300)] — AAPL coverage doesn't help MSFT
        assert len(gaps) == 1
        assert gaps[0].start == 101
        assert gaps[0].end == 300

    async def test_empty_table(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Empty table returns full miss."""
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=0, end=100)
        )

        assert len(gaps) == 1
        assert gaps[0].start == 0
        assert gaps[0].end == 100

    async def test_request_outside_coverage(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Request completely outside coverage returns full miss."""
        # Covered: [0, 100]
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 100)

        # Request: [500, 600] — no overlap
        gaps = await rangequery_table.get_missing_ranges(
            lookup_key="AAPL_1D", query_range=IntRange(start=500, end=600)
        )

        # Expected: [IntRange(500, 600)] — full miss
        assert len(gaps) == 1
        assert gaps[0].start == 500
        assert gaps[0].end == 600

    # --- Session injection ---

    async def test_session_injection(
        self,
        datastore: PostgresDatastore,
        rangequery_table: RangeQuerySQLModelTable[CoveredRange],
    ) -> None:
        """External session can be used for transaction batching."""
        await _add_coverage(rangequery_table, "AAPL", Resolution.DAY_1, 0, 100)

        session_factory = datastore.session_factory
        assert session_factory is not None

        async with session_factory() as session:
            gaps = await rangequery_table.get_missing_ranges(
                lookup_key="AAPL_1D",
                query_range=IntRange(start=0, end=200),
                session=session,
            )

            assert len(gaps) == 1
            assert gaps[0].start == 101
            assert gaps[0].end == 200

    # --- Field validation ---

    async def test_invalid_range_field_raises(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Invalid range_field name raises ValueError."""
        with pytest.raises(ValueError, match="has no field 'invalid_field'"):
            await rangequery_table.get_missing_ranges(
                lookup_key="AAPL_1D",
                query_range=IntRange(start=0, end=100),
                range_field="invalid_field",
            )

    async def test_invalid_group_field_raises(
        self, rangequery_table: RangeQuerySQLModelTable[CoveredRange]
    ) -> None:
        """Invalid group_field name raises ValueError."""
        with pytest.raises(ValueError, match="has no field 'invalid_field'"):
            await rangequery_table.get_missing_ranges(
                lookup_key="AAPL_1D",
                query_range=IntRange(start=0, end=100),
                group_field="invalid_field",
            )
