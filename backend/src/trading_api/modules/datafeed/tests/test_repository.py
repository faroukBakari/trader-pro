"""
Tests for Datafeed Repository implementations.

Tests cover:
1. : store/get round-trip with 1000 bars
2. Postgres: integration tests (marked @pytest.mark.integration)
3. Time conversion: millisecond timestamps
4. Resolution enum: values stored correctly
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from trading_api.datastores import create_memory_datastore
from trading_api.datastores.postgres import PostgresDatastore
from trading_api.models.market import Bar, Resolution
from trading_api.modules.datafeed.repository import BarRepository
from trading_api.shared.config import Settings


def create_test_bars(
    count: int,
    base_time: int = 1704067200000,  # 2024-01-01 00:00:00 UTC in ms
    interval_ms: int = 60000,  # 1 minute
) -> list[Bar]:
    """Generate test bars with sequential timestamps."""
    bars: list[Bar] = []
    for i in range(count):
        bars.append(
            Bar(
                time=base_time + (i * interval_ms),
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000 + i * 10,
                count=50 + i,
            )
        )
    return bars


class TestBarRepository:
    """Test suite for BarRepository implementation."""

    @pytest.fixture
    def repository(self) -> BarRepository:
        """Fixture providing clean repository instance."""
        return BarRepository(datastore=create_memory_datastore())

    @pytest.mark.asyncio
    async def test_store_and_get_single_bar(self, repository: BarRepository) -> None:
        """Test storing and retrieving a single bar."""
        bar = Bar(
            time=1704067200000,  # 2024-01-01 00:00:00 UTC
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
        )

        stored_count = await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=[bar],
        )

        assert stored_count == 1

        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=1704067200000,
            to_time=1704067200000,
        )

        assert len(result) == 1
        assert result[0].time == bar.time
        assert result[0].open == bar.open
        assert result[0].close == bar.close

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_store_1000_bars_roundtrip(self, repository: BarRepository) -> None:
        """Test storing and retrieving 1000 bars (Step 4.1)."""
        bars = create_test_bars(count=1000)

        stored_count = await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=bars,
        )

        assert stored_count == 1000

        # Get all bars
        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=bars[0].time,
            to_time=bars[-1].time,
        )

        assert len(result) == 1000

        # Verify order (ascending by time)
        for i, bar in enumerate(result):
            assert bar.time == bars[i].time
            assert bar.open == bars[i].open
            assert bar.high == bars[i].high
            assert bar.low == bars[i].low
            assert bar.close == bars[i].close
            assert bar.volume == bars[i].volume

    @pytest.mark.asyncio
    async def test_time_range_filtering(self, repository: BarRepository) -> None:
        """Test that get_bars correctly filters by time range."""
        bars = create_test_bars(count=100)

        await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=bars,
        )

        # Request middle 50 bars (indices 25-74)
        from_time = bars[25].time
        to_time = bars[74].time

        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=from_time,
            to_time=to_time,
        )

        assert len(result) == 50
        assert result[0].time == from_time
        assert result[-1].time == to_time

    @pytest.mark.asyncio
    async def test_millisecond_timestamp_precision(
        self, repository: BarRepository
    ) -> None:
        """Test that millisecond timestamps are preserved exactly (Step 4.3)."""
        # Use precise millisecond timestamps
        precise_times = [
            1704067200001,  # +1ms
            1704067200123,  # +123ms
            1704067200999,  # +999ms
        ]

        bars = [
            Bar(time=t, open=100.0, high=101.0, low=99.0, close=100.0, volume=100)
            for t in precise_times
        ]

        await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=bars,
        )

        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=precise_times[0],
            to_time=precise_times[-1],
        )

        assert len(result) == 3
        for i, bar in enumerate(result):
            assert bar.time == precise_times[i], f"Timestamp mismatch at index {i}"

    @pytest.mark.asyncio
    async def test_resolution_enum_storage(self, repository: BarRepository) -> None:
        """Test that Resolution enum values are stored correctly (Step 4.4)."""
        bar = Bar(
            time=1704067200000,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
        )

        # Store with different resolutions
        resolutions = [
            Resolution.MIN_1,
            Resolution.MIN_5,
            Resolution.HOUR_1,
            Resolution.DAY_1,
        ]

        for resolution in resolutions:
            await repository.store_bars(
                symbol="AAPL",
                resolution=resolution,
                bars=[bar],
            )

        # Each resolution should be stored separately
        for resolution in resolutions:
            result = await repository.get_bars(
                symbol="AAPL",
                resolution=resolution,
                from_time=bar.time,
                to_time=bar.time,
            )
            assert (
                len(result) == 1
            ), f"Resolution {resolution.value} not stored correctly"

    @pytest.mark.asyncio
    async def test_symbol_isolation(self, repository: BarRepository) -> None:
        """Test that bars for different symbols are isolated."""
        bar = Bar(
            time=1704067200000,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
        )

        await repository.store_bars(
            symbol="AAPL", resolution=Resolution.MIN_1, bars=[bar]
        )
        await repository.store_bars(
            symbol="GOOGL", resolution=Resolution.MIN_1, bars=[bar]
        )

        aapl_result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=bar.time,
            to_time=bar.time,
        )
        googl_result = await repository.get_bars(
            symbol="GOOGL",
            resolution=Resolution.MIN_1,
            from_time=bar.time,
            to_time=bar.time,
        )
        msft_result = await repository.get_bars(
            symbol="MSFT",
            resolution=Resolution.MIN_1,
            from_time=bar.time,
            to_time=bar.time,
        )

        assert len(aapl_result) == 1
        assert len(googl_result) == 1
        assert len(msft_result) == 0  # Never stored

    @pytest.mark.asyncio
    async def test_deduplication_same_timestamp(
        self, repository: BarRepository
    ) -> None:
        """Test that storing bars with same timestamp deduplicates (upsert)."""
        time_ms = 1704067200000

        bar1 = Bar(
            time=time_ms, open=100.0, high=101.0, low=99.0, close=100.5, volume=1000
        )
        bar2 = Bar(
            time=time_ms, open=105.0, high=106.0, low=104.0, close=105.5, volume=2000
        )

        count1 = await repository.store_bars(
            symbol="AAPL", resolution=Resolution.MIN_1, bars=[bar1]
        )
        count2 = await repository.store_bars(
            symbol="AAPL", resolution=Resolution.MIN_1, bars=[bar2]
        )

        # First store should count as 1, second should be 0 (replaced existing)
        assert count1 == 1
        assert count2 == 0

        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=time_ms,
            to_time=time_ms,
        )

        # Should have only 1 bar (the latest one)
        assert len(result) == 1
        assert result[0].open == 105.0  # Updated value

    @pytest.mark.asyncio
    async def test_empty_store(self, repository: BarRepository) -> None:
        """Test storing empty list returns 0."""
        stored = await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=[],
        )

        assert stored == 0

    @pytest.mark.asyncio
    async def test_get_empty_range(self, repository: BarRepository) -> None:
        """Test getting bars from empty repository returns empty list."""
        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=1704067200000,
            to_time=1704153600000,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_sorted_return_order(self, repository: BarRepository) -> None:
        """Test that bars are always returned in ascending time order."""
        # Store bars in reverse order
        bars = [
            Bar(
                time=1704067260000,
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.5,
                volume=200,
            ),
            Bar(
                time=1704067200000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=100,
            ),
            Bar(
                time=1704067320000,
                open=104.0,
                high=105.0,
                low=103.0,
                close=104.5,
                volume=300,
            ),
        ]

        await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=bars,
        )

        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=1704067200000,
            to_time=1704067320000,
        )

        assert len(result) == 3
        # Should be sorted ascending
        assert result[0].time == 1704067200000
        assert result[1].time == 1704067260000
        assert result[2].time == 1704067320000


# =============================================================================
# PostgreSQL Integration Tests (Future - requires DB setup)
# =============================================================================


@pytest.mark.integration
class TestPostgresBarRepository:
    """Integration tests for PostgreSQL bar repository.

    These tests require a running PostgreSQL instance.
    Skip with: pytest -m "not integration"

    Tests verify:
    - TimeSeriesSQLModelTable.get_time_range() works with real PostgreSQL
    - TimeSeriesSQLModelTable.set_batch() handles bulk inserts correctly
    - TIMESTAMPTZ round-trip preserves millisecond precision
    """

    @pytest_asyncio.fixture
    async def repository(self, test_settings: Settings) -> AsyncIterator[BarRepository]:
        """Fixture for PostgreSQL repository using test container."""
        datastore = await PostgresDatastore.create(config=test_settings)
        repo = BarRepository(datastore=datastore)
        yield repo
        # Cleanup: drop all bar tables created during tests
        bar_tables = await datastore.list_tables(prefix="bars_")
        for table_name in bar_tables:
            await datastore.drop_table(table_name)
        await datastore.close()

    @pytest.mark.asyncio
    async def test_store_1000_bars_postgres(self, repository: BarRepository) -> None:
        """Test storing and retrieving 1000 bars with real PostgreSQL."""
        bars = create_test_bars(count=1000)

        stored_count = await repository.store_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            bars=bars,
        )

        assert stored_count == 1000

        result = await repository.get_bars(
            symbol="AAPL",
            resolution=Resolution.MIN_1,
            from_time=bars[0].time,
            to_time=bars[-1].time,
        )

        assert len(result) == 1000

    @pytest.mark.asyncio
    async def test_timestamptz_roundtrip(self, repository: BarRepository) -> None:
        """Test int (ms) ↔ TIMESTAMPTZ round-trip (Step 4.3)."""
        # Test edge cases for timestamp conversion
        edge_timestamps = [
            0,  # Unix epoch
            1704067200000,  # 2024-01-01 00:00:00 UTC
            1735689600000,  # 2025-01-01 00:00:00 UTC
            1704067200001,  # +1ms precision test
        ]

        for ts in edge_timestamps:
            bar = Bar(
                time=ts, open=100.0, high=101.0, low=99.0, close=100.0, volume=100
            )

            await repository.store_bars(
                symbol="TEST",
                resolution=Resolution.MIN_1,
                bars=[bar],
            )

            result = await repository.get_bars(
                symbol="TEST",
                resolution=Resolution.MIN_1,
                from_time=ts,
                to_time=ts,
            )

            assert len(result) == 1
            assert result[0].time == ts, f"TIMESTAMPTZ round-trip failed for {ts}"

    @pytest.mark.asyncio
    async def test_set_batch_upsert_semantics(self, repository: BarRepository) -> None:
        """Test that set_batch() properly handles INSERT...ON CONFLICT (upsert).

        Verifies TimeSeriesSQLModelTable.set_batch() returns count of NEW rows only.
        """
        time_ms = 1704067200000

        bar1 = Bar(
            time=time_ms, open=100.0, high=101.0, low=99.0, close=100.5, volume=1000
        )

        # First insert - should count as 1 new row
        count1 = await repository.store_bars(
            symbol="UPSERT_TEST", resolution=Resolution.MIN_1, bars=[bar1]
        )
        assert count1 == 1

        # Same timestamp with different values - should update, count = 0
        bar2 = Bar(
            time=time_ms, open=200.0, high=201.0, low=199.0, close=200.5, volume=2000
        )
        count2 = await repository.store_bars(
            symbol="UPSERT_TEST", resolution=Resolution.MIN_1, bars=[bar2]
        )
        assert count2 == 0  # Updated existing, not a new row

        # Verify updated values
        result = await repository.get_bars(
            symbol="UPSERT_TEST",
            resolution=Resolution.MIN_1,
            from_time=time_ms,
            to_time=time_ms,
        )
        assert len(result) == 1
        assert result[0].open == 200.0  # Updated value
        assert result[0].volume == 2000  # Updated value

    @pytest.mark.asyncio
    async def test_get_time_range_boundary_conditions(
        self, repository: BarRepository
    ) -> None:
        """Test get_time_range() inclusive boundary handling.

        Verifies TimeSeriesSQLModelTable.get_time_range() with exact boundaries.
        """
        bars = create_test_bars(count=10, base_time=1704067200000, interval_ms=60000)

        await repository.store_bars(
            symbol="BOUNDARY_TEST", resolution=Resolution.MIN_1, bars=bars
        )

        # Exact match on first bar only
        result = await repository.get_bars(
            symbol="BOUNDARY_TEST",
            resolution=Resolution.MIN_1,
            from_time=bars[0].time,
            to_time=bars[0].time,
        )
        assert len(result) == 1
        assert result[0].time == bars[0].time

        # Exact match on last bar only
        result = await repository.get_bars(
            symbol="BOUNDARY_TEST",
            resolution=Resolution.MIN_1,
            from_time=bars[-1].time,
            to_time=bars[-1].time,
        )
        assert len(result) == 1
        assert result[0].time == bars[-1].time

        # Range outside all bars (before)
        result = await repository.get_bars(
            symbol="BOUNDARY_TEST",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=bars[0].time - 1,
        )
        assert len(result) == 0

        # Range outside all bars (after)
        result = await repository.get_bars(
            symbol="BOUNDARY_TEST",
            resolution=Resolution.MIN_1,
            from_time=bars[-1].time + 1,
            to_time=bars[-1].time + 1000000,
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_batch_insert_multiple_bars(self, repository: BarRepository) -> None:
        """Test bulk insert of multiple bars in single set_batch() call."""
        bars = create_test_bars(count=100)

        # Single batch insert
        stored_count = await repository.store_bars(
            symbol="BATCH_TEST", resolution=Resolution.MIN_1, bars=bars
        )
        assert stored_count == 100

        # Verify all bars retrievable
        result = await repository.get_bars(
            symbol="BATCH_TEST",
            resolution=Resolution.MIN_1,
            from_time=bars[0].time,
            to_time=bars[-1].time,
        )
        assert len(result) == 100

        # Verify order preserved (ascending by time)
        for i in range(len(result) - 1):
            assert result[i].time < result[i + 1].time

    @pytest.mark.asyncio
    async def test_resolution_isolation_postgres(
        self, repository: BarRepository
    ) -> None:
        """Test that different resolutions create separate PostgreSQL tables."""
        bar = Bar(
            time=1704067200000,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
        )

        # Store same bar at different resolutions
        await repository.store_bars(
            symbol="RESOLUTION_TEST", resolution=Resolution.MIN_1, bars=[bar]
        )
        await repository.store_bars(
            symbol="RESOLUTION_TEST", resolution=Resolution.HOUR_1, bars=[bar]
        )

        # Each resolution should be isolated
        min1_result = await repository.get_bars(
            symbol="RESOLUTION_TEST",
            resolution=Resolution.MIN_1,
            from_time=bar.time,
            to_time=bar.time,
        )
        hour1_result = await repository.get_bars(
            symbol="RESOLUTION_TEST",
            resolution=Resolution.HOUR_1,
            from_time=bar.time,
            to_time=bar.time,
        )

        assert len(min1_result) == 1
        assert len(hour1_result) == 1
