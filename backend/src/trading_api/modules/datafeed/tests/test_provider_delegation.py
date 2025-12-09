"""Test DatafeedService delegates to provider correctly."""

from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, Mock

import pytest

from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.modules.datafeed.service import DatafeedService
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.shared import Provider


class MockDatafeedProvider(Provider, DatafeedCapability):
    """Mock datafeed provider for testing."""

    def __init__(self) -> None:
        self._search_symbols_mock = AsyncMock()
        self._get_symbol_info_mock = AsyncMock()
        self._get_historical_bars_mock = AsyncMock()
        self._get_quotes_snapshot_mock = AsyncMock()
        self._subscribe_realtime_bars_mock = Mock()
        self._subscribe_market_data_mock = Mock()
        self._unsubscribe_realtime_bars_mock = Mock()
        self._unsubscribe_market_data_mock = Mock()

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "mock"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="datafeed")]

    @property
    def config(self) -> ProviderConfig:
        return Mock(spec=ProviderConfig)

    # Implement DatafeedCapability abstract methods
    async def search_symbols(
        self, pattern: str, **kwargs: Any
    ) -> list[SearchSymbolResultItem]:
        return await self._search_symbols_mock(pattern=pattern, **kwargs)  # type: ignore[no-any-return]

    async def get_symbol_info(self, ticker: str, **kwargs: Any) -> SymbolInfo:
        return await self._get_symbol_info_mock(  # type: ignore[no-any-return]
            ticker=ticker, **kwargs
        )

    async def get_historical_bars(
        self,
        ticker: str,
        start_time: datetime,
        end_time: datetime,
        resolution: Resolution,
        **kwargs: Any,
    ) -> list[Bar]:
        return await self._get_historical_bars_mock(  # type: ignore[no-any-return]
            ticker=ticker,
            start_time=start_time,
            end_time=end_time,
            resolution=resolution,
            **kwargs,
        )

    def subscribe_realtime_bars(
        self,
        ticker: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        **kwargs: Any,
    ) -> str:
        return self._subscribe_realtime_bars_mock(  # type: ignore[no-any-return]
            ticker=ticker, resolution=resolution, callback=callback, **kwargs
        )

    def subscribe_market_data(
        self,
        tickers: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        **kwargs: Any,
    ) -> list[str]:
        return self._subscribe_market_data_mock(  # type: ignore[no-any-return]
            tickers=tickers, callback=callback, **kwargs
        )

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        self._unsubscribe_realtime_bars_mock(subscription_id)

    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None:
        self._unsubscribe_market_data_mock(subscription_ids)

    async def get_quotes_snapshot(
        self,
        tickers: list[str],
        **kwargs: Any,
    ) -> list[QuoteData]:
        return await self._get_quotes_snapshot_mock(  # type: ignore[no-any-return]
            tickers=tickers, **kwargs
        )


@pytest.mark.asyncio
async def test_search_symbols_delegates_to_provider() -> None:
    """Test search_symbols delegates to datafeed provider."""
    # Create mock provider with required interface
    mock_provider = MockDatafeedProvider()
    mock_provider._search_symbols_mock.return_value = [
        SearchSymbolResultItem(
            symbol="AAPL",
            exchange="NASDAQ",
            type="stock",
            description="Apple Inc.",
            ticker="AAPL:NASDAQ",
        )
    ]

    # Create service with mock provider
    module_dir = Path(__file__).parent.parent
    service = DatafeedService(module_dir, providers=[mock_provider])

    # Call service method (no need to patch - provider properly injected)
    results = await service.search_symbols(
        user_input="AAPL", exchange="", symbol_type="", max_results=50
    )

    # Verify provider was called with correct pattern
    mock_provider._search_symbols_mock.assert_called_once()
    call_kwargs = mock_provider._search_symbols_mock.call_args.kwargs
    assert call_kwargs["pattern"] == "AAPL"
    assert "timeout" in call_kwargs  # timeout is passed, value may change

    # Verify results
    assert len(results) == 1
    assert results[0].symbol == "AAPL"
    assert results[0].exchange == "NASDAQ"
    assert results[0].ticker == "AAPL:NASDAQ"


@pytest.mark.asyncio
async def test_search_symbols_filters_results() -> None:
    """Test search_symbols applies business logic filters after provider call."""
    # Mock provider returns multiple results
    mock_provider = MockDatafeedProvider()
    mock_provider._search_symbols_mock.return_value = [
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

    module_dir = Path(__file__).parent.parent
    service = DatafeedService(module_dir, providers=[mock_provider])

    # Filter by exchange
    results = await service.search_symbols(
        user_input="", exchange="NASDAQ", symbol_type="", max_results=50
    )

    # Should filter to only NASDAQ
    assert len(results) == 2
    assert all(r.exchange == "NASDAQ" for r in results)


@pytest.mark.asyncio
async def test_search_symbols_respects_max_results() -> None:
    """Test search_symbols limits results to max_results."""
    # Mock provider returns many results
    mock_results = [
        SearchSymbolResultItem(
            symbol=f"SYM{i}",
            exchange="NASDAQ",
            type="stock",
            description=f"Symbol {i}",
            ticker=f"SYM{i}:NASDAQ",
        )
        for i in range(100)
    ]

    mock_provider = MockDatafeedProvider()
    mock_provider._search_symbols_mock.return_value = mock_results

    module_dir = Path(__file__).parent.parent
    service = DatafeedService(module_dir, providers=[mock_provider])

    # Request only 10 results
    results = await service.search_symbols(
        user_input="", exchange="", symbol_type="", max_results=10
    )

    # Should limit to 10
    assert len(results) == 10


@pytest.mark.asyncio
async def test_get_bars_delegates_to_provider() -> None:
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

    mock_provider = MockDatafeedProvider()
    mock_provider._get_historical_bars_mock.return_value = mock_bars

    module_dir = Path(__file__).parent.parent
    service = DatafeedService(module_dir, providers=[mock_provider])

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
    mock_provider._get_historical_bars_mock.assert_called_once()
    call_kwargs = mock_provider._get_historical_bars_mock.call_args.kwargs

    # Verify ticker passed through
    assert call_kwargs["ticker"] == "AAPL:NASDAQ"

    # Verify resolution passed through
    assert call_kwargs["resolution"] == Resolution.DAY_1

    # Verify timestamp conversion (milliseconds → datetime)
    assert isinstance(call_kwargs["start_time"], datetime)
    assert isinstance(call_kwargs["end_time"], datetime)
    assert call_kwargs["start_time"].timestamp() == from_time / 1000
    assert call_kwargs["end_time"].timestamp() == to_time / 1000

    # Verify results returned
    assert len(results) == 3
    assert results[0].time == 1609459200000


@pytest.mark.asyncio
async def test_get_bars_applies_count_back_filter() -> None:
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

    mock_provider = MockDatafeedProvider()
    mock_provider._get_historical_bars_mock.return_value = mock_bars

    module_dir = Path(__file__).parent.parent
    service = DatafeedService(module_dir, providers=[mock_provider])

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


@pytest.mark.asyncio
async def test_get_bars_handles_provider_exception() -> None:
    """Test get_bars handles provider exceptions gracefully."""
    mock_provider = MockDatafeedProvider()
    mock_provider._get_historical_bars_mock.side_effect = Exception("Provider error")

    module_dir = Path(__file__).parent.parent
    service = DatafeedService(module_dir, providers=[mock_provider])

    # Call get_bars
    results = await service.get_bars(
        ticker="AAPL",
        resolution=Resolution.DAY_1,
        from_time=0,
        to_time=999999999999,
        count_back=None,
    )

    # Should return empty list on error
    assert results == []
