"""Test DatafeedService delegates to provider correctly.

Uses shared MockDatafeedProvider from conftest.py for provider-agnostic testing.
"""

from datetime import datetime
from pathlib import Path

import pytest

from trading_api.models.market import Bar, Resolution, SearchSymbolResultItem
from trading_api.modules.datafeed.service import DatafeedService

from .conftest import MockDatafeedProvider


@pytest.fixture
def mock_provider() -> MockDatafeedProvider:
    """Create a fresh mock provider for each test."""
    return MockDatafeedProvider()


@pytest.fixture
def service(mock_provider: MockDatafeedProvider) -> DatafeedService:
    """Create DatafeedService with mock provider."""
    module_dir = Path(__file__).parent.parent
    return DatafeedService(module_dir, providers=[mock_provider])


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
    assert len(results) == 3
    assert results[0].time == 1609459200000


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
    assert len(results) == 3
    assert results == mock_bars[-3:]
