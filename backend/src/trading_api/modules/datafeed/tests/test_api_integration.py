"""Test DatafeedService delegates to provider correctly.

Uses shared MockDatafeedProvider from conftest.py for provider-agnostic testing.
"""

from datetime import datetime
from pathlib import Path

import pytest

from trading_api.datastores import PostgresDatastore, create_memory_datastore
from trading_api.models.market import Bar, Resolution, SearchSymbolResultItem
from trading_api.modules.datafeed.service import DatafeedService
from trading_api.shared.config import Settings

from .conftest import MockDatafeedProvider


@pytest.fixture
def mock_provider() -> MockDatafeedProvider:
    """Create a fresh mock provider for each test."""
    return MockDatafeedProvider()


@pytest.fixture
def service(mock_provider: MockDatafeedProvider) -> DatafeedService:
    """Create DatafeedService with mock provider."""
    module_dir = Path(__file__).parent.parent
    datastore = create_memory_datastore()
    return DatafeedService(
        module_dir, providers=[mock_provider], datastores=[datastore]
    )


@pytest.fixture
async def cached_service(
    test_settings: Settings, mock_provider: MockDatafeedProvider
) -> DatafeedService:
    """Create DatafeedService with PostgresDatastore for caching tests.

    This fixture provides full read-through cache functionality:
    - BarRepository for persistent bar storage
    - BarCacheManager for gap detection and pending range locking
    """
    datastore = await PostgresDatastore.create(config=test_settings)
    module_dir = Path(__file__).parent.parent
    svc = DatafeedService(module_dir, providers=[mock_provider], datastores=[datastore])
    # Clear cache state for clean tests
    if svc._cache_manager:
        await svc._cache_manager.clear()
    if svc._bar_repository:
        # Clear any existing bar data
        pass  # Tables are per-symbol, created on demand
    return svc


@pytest.mark.asyncio
async def test_search_symbols_delegates_to_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test search_symbols delegates to datafeed provider."""
    # Configure mock return value
    mock_provider.return_values["search_symbols"] = [
        SearchSymbolResultItem(
            symbol="AAPL",
            exchange="NASDAQ",
            type="stock",
            description="Apple Inc.",
            ticker="AAPL:NASDAQ",
        )
    ]

    # Call service method
    results = await service.search_symbols(
        user_input="AAPL", exchange="", symbol_type="", max_results=50
    )

    # Verify provider was called with correct pattern
    assert len(mock_provider.calls["search_symbols"]) == 1
    call = mock_provider.calls["search_symbols"][0]
    assert call["pattern"] == "AAPL"
    assert "timeout" in call

    # Verify results
    assert len(results) == 1
    assert results[0].symbol == "AAPL"
    assert results[0].exchange == "NASDAQ"
    assert results[0].ticker == "AAPL:NASDAQ"


@pytest.mark.asyncio
async def test_search_symbols_filters_results(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test search_symbols applies business logic filters after provider call."""
    # Mock provider returns multiple results
    mock_provider.return_values["search_symbols"] = [
        SearchSymbolResultItem(
            symbol="AAPL",
            exchange="NASDAQ",
            type="stock",
            description="Apple Inc.",
            ticker="AAPL:NASDAQ",
        ),
        SearchSymbolResultItem(
            symbol="GOOGL",
            exchange="NASDAQ",
            type="stock",
            description="Alphabet Inc. Class A",
            ticker="GOOGL:NASDAQ",
        ),
        SearchSymbolResultItem(
            symbol="IBM",
            exchange="NYSE",
            type="stock",
            description="International Business Machines",
            ticker="IBM:NYSE",
        ),
    ]

    # Filter by exchange
    results = await service.search_symbols(
        user_input="", exchange="NASDAQ", symbol_type="", max_results=50
    )

    # Should filter to only NASDAQ
    assert len(results) == 2
    assert all(r.exchange == "NASDAQ" for r in results)


@pytest.mark.asyncio
async def test_search_symbols_respects_max_results(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test search_symbols limits results to max_results."""
    # Mock provider returns many results
    mock_provider.return_values["search_symbols"] = [
        SearchSymbolResultItem(
            symbol=f"SYM{i}",
            exchange="NASDAQ",
            type="stock",
            description=f"Symbol {i}",
            ticker=f"SYM{i}:NASDAQ",
        )
        for i in range(100)
    ]

    # Request only 10 results
    results = await service.search_symbols(
        user_input="", exchange="", symbol_type="", max_results=10
    )

    # Should limit to 10
    assert len(results) == 10


@pytest.mark.asyncio
async def test_get_bars_delegates_to_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test get_bars delegates to provider with proper parameter conversion."""
    # Mock provider with bars
    mock_bars = [
        Bar(
            time=1609459200000,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
            count=None,
        ),
        Bar(
            time=1609545600000,
            open=100.5,
            high=102.0,
            low=100.0,
            close=101.5,
            volume=1500,
            count=None,
        ),
        Bar(
            time=1609632000000,
            open=101.5,
            high=103.0,
            low=101.0,
            close=102.5,
            volume=2000,
            count=None,
        ),
    ]
    mock_provider.return_values["get_historical_bars"] = mock_bars

    # Call get_bars with Resolution enum
    from_time = 1609459200000  # Unix milliseconds
    to_time = 1609632000000
    results = await service.get_bars(
        ticker="AAPL:NASDAQ",
        resolution=Resolution.DAY_1,
        from_time=from_time,
        to_time=to_time,
        count_back=None,
    )

    # Verify provider was called with converted parameters
    assert len(mock_provider.calls["get_historical_bars"]) == 1
    call = mock_provider.calls["get_historical_bars"][0]

    # Verify ticker_name passed through
    assert call["ticker_name"] == "AAPL:NASDAQ"

    # Verify resolution passed through
    assert call["resolution"] == Resolution.DAY_1

    # Verify timestamp conversion (milliseconds → datetime)
    assert isinstance(call["start_time"], datetime)
    assert isinstance(call["end_time"], datetime)
    assert call["start_time"].timestamp() == from_time / 1000
    assert call["end_time"].timestamp() == to_time / 1000

    # Verify results returned
    assert len(results.bars) == 3
    assert results.bars[0].time == 1609459200000


@pytest.mark.asyncio
async def test_get_bars_applies_count_back_filter(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test get_bars applies count_back limit to provider results."""
    # Mock provider returns 10 bars
    mock_bars = [
        Bar(
            time=i * 86400000,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
            count=None,
        )
        for i in range(10)
    ]
    mock_provider.return_values["get_historical_bars"] = mock_bars

    # Request only last 3 bars
    results = await service.get_bars(
        ticker="AAPL",
        resolution=Resolution.DAY_1,
        from_time=0,
        to_time=999999999999,
        count_back=3,
    )

    # Should return only last 3 bars
    assert len(results.bars) == 3
    assert results.bars == mock_bars[-3:]


# =============================================================================
# Cache Integration Tests (PostgresDatastore)
# =============================================================================


class TestGetBarsCaching:
    """Integration tests for DatafeedService read-through cache orchestration.

    These tests verify the full caching pipeline:
    - Gap detection via BarCacheManager.find_missing_ranges()
    - Pending range locking via try_add_pending()
    - Provider fetch for uncached ranges
    - Storage via BarRepository
    - Coverage tracking via mark_covered()

    Uses PostgresDatastore for real exclusion constraint behavior.
    """

    @pytest.mark.asyncio
    async def test_cache_bypass_with_duckdb_lite_datastore(
        self, service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test that DuckDB lite datastore bypasses cache (no exclusion capability)."""
        # Arrange: Configure provider to return bars
        mock_bars = [
            Bar(
                time=1000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            )
        ]
        mock_provider.return_values["get_historical_bars"] = mock_bars

        # Verify service has no cache_manager with DuckDB lite datastore
        assert service._cache_manager is None

        # Act: First call
        await service.get_bars(
            ticker="TEST",
            resolution=Resolution.DAY_1,
            from_time=0,
            to_time=100000,
            count_back=None,
        )

        # Act: Second identical call
        await service.get_bars(
            ticker="TEST",
            resolution=Resolution.DAY_1,
            from_time=0,
            to_time=100000,
            count_back=None,
        )

        # Assert: Provider called BOTH times (no caching)
        assert len(mock_provider.calls["get_historical_bars"]) == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_miss_fetches_and_stores(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test cache miss triggers provider fetch and stores result."""
        # Arrange: Configure provider to return bars
        mock_bars = [
            Bar(
                time=1000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            ),
            Bar(
                time=2000,
                open=100.5,
                high=102.0,
                low=100.0,
                close=101.5,
                volume=1500,
                count=None,
            ),
        ]
        mock_provider.return_values["get_historical_bars"] = mock_bars

        # Act: First request (cache miss)
        results = await cached_service.get_bars(
            ticker="CACHE_MISS",
            resolution=Resolution.DAY_1,
            from_time=0,
            to_time=10000,
            count_back=None,
        )

        # Assert: Provider was called
        assert len(mock_provider.calls["get_historical_bars"]) == 1
        # Assert: Bars returned
        assert len(results.bars) == 2
        assert results.bars[0].time == 1000
        assert results.bars[1].time == 2000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test cache hit returns data without calling provider."""
        # Arrange: Configure provider to return bars
        mock_bars = [
            Bar(
                time=5000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            ),
        ]
        mock_provider.return_values["get_historical_bars"] = mock_bars

        # First request populates cache
        await cached_service.get_bars(
            ticker="CACHE_HIT",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=10000,
            count_back=None,
        )
        assert len(mock_provider.calls["get_historical_bars"]) == 1

        # Act: Second identical request (cache hit)
        results = await cached_service.get_bars(
            ticker="CACHE_HIT",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=10000,
            count_back=None,
        )

        # Assert: Provider NOT called again
        assert len(mock_provider.calls["get_historical_bars"]) == 1
        # Assert: Bars still returned from cache
        assert len(results.bars) == 1
        assert results.bars[0].time == 5000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_partial_cache_fills_gaps_only(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test partial cache hit fetches only missing ranges."""
        # Arrange: First request covers 0-10000
        first_bars = [
            Bar(
                time=5000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            ),
        ]
        mock_provider.return_values["get_historical_bars"] = first_bars

        await cached_service.get_bars(
            ticker="PARTIAL",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=10000,
            count_back=None,
        )
        assert len(mock_provider.calls["get_historical_bars"]) == 1

        # Arrange: Second request extends range to 20000
        second_bars = [
            Bar(
                time=15000,
                open=101.0,
                high=102.0,
                low=100.5,
                close=101.5,
                volume=1200,
                count=None,
            ),
        ]
        mock_provider.return_values["get_historical_bars"] = second_bars

        # Act: Request 0-20000 (0-10000 cached, 10000-20000 gap)
        results = await cached_service.get_bars(
            ticker="PARTIAL",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=20000,
            count_back=None,
        )

        # Assert: Provider called for gap only
        assert len(mock_provider.calls["get_historical_bars"]) == 2
        second_call = mock_provider.calls["get_historical_bars"][1]
        # Gap should start at 10000 (exclusive of first range)
        assert second_call["start_time"].timestamp() * 1000 >= 10000

        # Assert: Combined results returned
        assert len(results.bars) == 2
        times = [bar.time for bar in results.bars]
        assert 5000 in times
        assert 15000 in times

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_count_back_applied_after_cache_retrieval(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test count_back filter applies to cached + fetched data."""
        # Arrange: Provider returns 10 bars
        mock_bars = [
            Bar(
                time=i * 1000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            )
            for i in range(10)
        ]
        mock_provider.return_values["get_historical_bars"] = mock_bars

        # Populate cache
        await cached_service.get_bars(
            ticker="COUNTBACK",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=10000,
            count_back=None,
        )

        # Act: Request with count_back=3 (from cache)
        results = await cached_service.get_bars(
            ticker="COUNTBACK",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=10000,
            count_back=3,
        )

        # Assert: Only 3 most recent bars returned
        assert len(results.bars) == 3
        # Last 3 bars: time 7000, 8000, 9000
        assert results.bars[0].time == 7000
        assert results.bars[1].time == 8000
        assert results.bars[2].time == 9000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_next_time_set_when_bars_empty_and_earlier_data_exists(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test next_time points to nearest previous bar for gap bridging."""
        # Arrange: Populate cache with bars in an earlier range
        early_bars = [
            Bar(
                time=1000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            ),
            Bar(
                time=2000,
                open=100.5,
                high=102.0,
                low=100.0,
                close=101.5,
                volume=1500,
                count=None,
            ),
        ]
        mock_provider.return_values["get_historical_bars"] = early_bars

        # Populate cache with early data
        await cached_service.get_bars(
            ticker="GAP_BRIDGE",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=5000,
            count_back=None,
        )

        # Now provider returns empty for a later range (simulating weekend gap)
        mock_provider.return_values["get_historical_bars"] = []

        # Act: Request bars in a range with no data (gap)
        results = await cached_service.get_bars(
            ticker="GAP_BRIDGE",
            resolution=Resolution.MIN_1,
            from_time=50000,
            to_time=100000,
            count_back=None,
        )

        # Assert: No bars returned, but next_time points to last known bar
        assert len(results.bars) == 0
        assert results.next_time == 2000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_next_time_none_when_no_earlier_data(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test next_time is None when no earlier data exists."""
        # Provider returns empty for the requested range
        mock_provider.return_values["get_historical_bars"] = []

        # Act: Request bars with no data anywhere
        results = await cached_service.get_bars(
            ticker="NO_DATA_ANYWHERE",
            resolution=Resolution.MIN_1,
            from_time=50000,
            to_time=100000,
            count_back=None,
        )

        # Assert: No bars and no next_time
        assert len(results.bars) == 0
        assert results.next_time is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_next_time_none_when_bars_returned(
        self, cached_service: DatafeedService, mock_provider: MockDatafeedProvider
    ) -> None:
        """Test next_time is not set when bars are returned (no gap)."""
        mock_bars = [
            Bar(
                time=5000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                count=None,
            ),
        ]
        mock_provider.return_values["get_historical_bars"] = mock_bars

        results = await cached_service.get_bars(
            ticker="HAS_DATA",
            resolution=Resolution.MIN_1,
            from_time=0,
            to_time=10000,
            count_back=None,
        )

        # Assert: Bars returned, no next_time needed
        assert len(results.bars) == 1
        assert results.next_time is None
