"""Tests for TWSProvider - Layer 2 (AsyncIO Bridge & Domain Conversion)."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.models.market import Bar, SearchSymbolResultItem, SymbolInfo, TimeFrame
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.providers.tws import TWSProvider


class TestProviderInitialization:
    """Test TWSProvider initialization and configuration."""

    def test_provider_initialization(self) -> None:
        """Test TWSProvider initialization with default config."""
        provider = TWSProvider()

        assert provider.name == "tws"
        caps = provider.capabilities()
        assert len(caps) == 1
        assert caps[0].name == "datafeed"
        assert isinstance(provider.config, TWSProviderConfig)

    def test_provider_with_custom_config(self) -> None:
        """Test TWSProvider with custom config."""
        config = TWSProviderConfig(host="192.168.1.1", port=4002, client_id=2)
        provider = TWSProvider(config=config)

        assert provider.config.host == "192.168.1.1"
        assert provider.config.port == 4002
        assert provider.config.client_id == 2

    def test_provider_capabilities(self) -> None:
        """Test provider capabilities declaration."""
        caps = TWSProvider.capabilities()

        assert len(caps) == 1
        assert caps[0].name == "datafeed"


class TestDomainConversionRequestMappers:
    """Test domain → TWS conversion helpers."""

    def test_build_tws_contract(self) -> None:
        """Test Contract building from symbol/exchange."""
        provider = TWSProvider()

        contract = provider._build_tws_contract("AAPL", "NASDAQ")

        assert contract.symbol == "AAPL"
        assert contract.secType == "STK"
        assert contract.exchange == "NASDAQ"
        assert contract.currency == "USD"

    def test_build_tws_contract_default_exchange(self) -> None:
        """Test Contract building with default SMART exchange."""
        provider = TWSProvider()

        contract = provider._build_tws_contract("AAPL")

        assert contract.symbol == "AAPL"
        assert contract.exchange == "SMART"

    def test_map_timeframe_to_tws(self) -> None:
        """Test TimeFrame enum → TWS bar size string.

        Note: TimeFrame.MIN_5 is an alias for TimeFrame.SEC_5 (both have value "5"),
        so both resolve to "5 secs".
        """
        provider = TWSProvider()

        assert provider._map_timeframe_to_tws(TimeFrame.SEC_5) == "5 secs"
        assert provider._map_timeframe_to_tws(TimeFrame.SEC_10) == "10 secs"
        assert provider._map_timeframe_to_tws(TimeFrame.MIN_1) == "1 min"
        # TimeFrame.MIN_5 is alias of SEC_5, so it also maps to "5 secs"
        assert provider._map_timeframe_to_tws(TimeFrame.MIN_5) == "5 secs"
        assert provider._map_timeframe_to_tws(TimeFrame.MIN_15) == "15 mins"
        assert provider._map_timeframe_to_tws(TimeFrame.MIN_30) == "30 mins"
        assert provider._map_timeframe_to_tws(TimeFrame.HOUR_1) == "1 hour"
        assert provider._map_timeframe_to_tws(TimeFrame.DAY_1) == "1 day"
        assert provider._map_timeframe_to_tws(TimeFrame.WEEK_1) == "1 week"
        assert provider._map_timeframe_to_tws(TimeFrame.MONTH_1) == "1 month"

    def test_calculate_tws_duration_seconds(self) -> None:
        """Test datetime range → TWS duration (seconds)."""
        provider = TWSProvider()

        end = datetime.now()
        start = end - timedelta(hours=1)

        duration = provider._calculate_tws_duration(start, end)
        assert duration == "3600 S"

    def test_calculate_tws_duration_days(self) -> None:
        """Test datetime range → TWS duration (days)."""
        provider = TWSProvider()

        end = datetime.now()
        start = end - timedelta(days=30)

        duration = provider._calculate_tws_duration(start, end)
        assert duration == "30 D"


class TestDomainConversionResponseMappers:
    """Test TWS → domain conversion helpers."""

    def test_convert_tws_bar_to_domain(self) -> None:
        """Test TWS BarData → domain Bar."""
        provider = TWSProvider()

        # Create TWS BarData
        tws_bar = BarData()
        tws_bar.date = "1609459200"  # Unix timestamp as string
        tws_bar.open = 100.0
        tws_bar.high = 101.0
        tws_bar.low = 99.0
        tws_bar.close = 100.5
        tws_bar.volume = Decimal("1000")

        # Convert to domain
        domain_bar = provider._convert_tws_bar_to_domain(tws_bar, "AAPL")

        assert domain_bar.time == 1609459200000  # Converted to ms
        assert domain_bar.open == 100.0
        assert domain_bar.high == 101.0
        assert domain_bar.low == 99.0
        assert domain_bar.close == 100.5
        assert domain_bar.volume == 1000  # int, not Decimal

    def test_convert_tws_bar_zero_volume(self) -> None:
        """Test bar conversion with None volume."""
        provider = TWSProvider()

        tws_bar = BarData()
        tws_bar.date = "1609459200"
        tws_bar.open = 100.0
        tws_bar.high = 100.0
        tws_bar.low = 100.0
        tws_bar.close = 100.0
        tws_bar.volume = None  # type: ignore[assignment]

        domain_bar = provider._convert_tws_bar_to_domain(tws_bar)

        assert domain_bar.volume == 0

    def test_convert_contract_desc_to_search_result(self) -> None:
        """Test TWS ContractDescription → SearchSymbolResultItem."""
        provider = TWSProvider()

        # Create TWS ContractDescription
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.currency = "USD"
        contract.primaryExchange = "NASDAQ"  # type: ignore[attr-defined]

        desc = ContractDescription()
        desc.contract = contract
        desc.derivativeSecTypes = []

        # Convert
        result = provider._convert_contract_desc_to_search_result(desc)

        assert isinstance(result, SearchSymbolResultItem)
        assert result.symbol == "AAPL"
        assert result.exchange == "NASDAQ"  # Uses primaryExchange
        assert result.type == "stk"
        assert result.ticker == "AAPL:NASDAQ"

    def test_convert_contract_desc_no_primary_exchange(self) -> None:
        """Test conversion when primaryExchange is not set."""
        provider = TWSProvider()

        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"

        desc = ContractDescription()
        desc.contract = contract

        result = provider._convert_contract_desc_to_search_result(desc)

        assert result.exchange == "SMART"  # Falls back to exchange
        assert result.ticker == "AAPL:SMART"

    def test_convert_contract_details_to_symbol_info(self) -> None:
        """Test TWS ContractDetails → SymbolInfo."""
        provider = TWSProvider()

        # Create TWS ContractDetails
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.primaryExchange = "NASDAQ"  # type: ignore[attr-defined]

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc."
        details.timeZoneId = "America/New_York"

        # Convert
        info = provider._convert_contract_details_to_symbol_info(details)

        assert isinstance(info, SymbolInfo)
        assert info.name == "AAPL"
        assert info.description == "Apple Inc."
        assert info.type == "stk"
        assert info.exchange == "NASDAQ"
        assert info.timezone == "America/New_York"
        assert info.ticker == "AAPL:NASDAQ"
        assert info.has_intraday is True
        assert info.has_daily is True


class TestSearchSymbols:
    """Test search_symbols implementation."""

    @pytest.mark.asyncio
    async def test_search_symbols_success(self) -> None:
        """Test successful symbol search with mocked TWS."""
        provider = TWSProvider()

        # Mock TWS connection
        mock_tws = Mock()
        mock_tws.get_req_id = Mock(return_value=1)
        mock_tws.reqMatchingSymbols = Mock()
        provider.tws = mock_tws

        # Create mock contract description
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.primaryExchange = "NASDAQ"  # type: ignore[attr-defined]

        desc = ContractDescription()
        desc.contract = contract

        # Mock the callback wrapper to immediately resolve
        with patch.object(provider, "_get_next_req_id", return_value=1):
            # Create a completed future with results
            from concurrent.futures import Future

            future: Future[list[ContractDescription]] = Future()
            future.set_result([desc])

            # Patch pending requests
            provider._pending_requests[1] = future

            # Execute search
            results = await provider.search_symbols("AAPL", timeout=5.0)

        # Verify results
        assert len(results) == 1
        assert results[0].symbol == "AAPL"
        assert results[0].exchange == "NASDAQ"
        assert results[0].ticker == "AAPL:NASDAQ"

    @pytest.mark.asyncio
    async def test_search_symbols_timeout(self) -> None:
        """Test search_symbols timeout handling."""
        provider = TWSProvider()

        # Mock TWS connection
        mock_tws = Mock()
        mock_tws.get_req_id = Mock(return_value=1)
        mock_tws.reqMatchingSymbols = Mock()
        provider.tws = mock_tws

        with patch.object(provider, "_get_next_req_id", return_value=1):
            # Create a future that never completes
            from concurrent.futures import Future

            future: Future[list[ContractDescription]] = Future()
            provider._pending_requests[1] = future

            # Execute search (should timeout)
            with pytest.raises(TimeoutError, match="Symbol search timeout"):
                await provider.search_symbols("AAPL", timeout=0.1)


@pytest.mark.asyncio
class TestGetSymbolInfo:
    """Test get_symbol_info implementation."""

    async def test_get_symbol_info_success(self) -> None:
        """Test successful symbol info retrieval."""
        provider = TWSProvider()

        # Create mock contract details
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"  # type: ignore[attr-defined]

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc."
        details.timeZoneId = "America/New_York"

        with patch.object(provider, "_get_next_req_id", return_value=1):
            from concurrent.futures import Future

            future: Future[list[ContractDetails]] = Future()
            future.set_result([details])
            provider._pending_requests[1] = future

            # Execute
            info = await provider.get_symbol_info("AAPL")

        assert info.name == "AAPL"
        assert info.description == "Apple Inc."
        assert info.exchange == "NASDAQ"

    async def test_get_symbol_info_not_found(self) -> None:
        """Test symbol not found error."""
        provider = TWSProvider()

        with patch.object(provider, "_get_next_req_id", return_value=1):
            from concurrent.futures import Future

            future: Future[list[ContractDetails]] = Future()
            future.set_result([])  # Empty results
            provider._pending_requests[1] = future

            with pytest.raises(ValueError, match="Symbol not found"):
                await provider.get_symbol_info("INVALID")

    async def test_get_symbol_info_multiple_matches(self) -> None:
        """Test multiple matches error."""
        provider = TWSProvider()

        # Create two contract details (ambiguous symbol)
        details1 = ContractDetails()
        details1.contract = Contract()
        details2 = ContractDetails()
        details2.contract = Contract()

        with patch.object(provider, "_get_next_req_id", return_value=1):
            from concurrent.futures import Future

            future: Future[list[ContractDetails]] = Future()
            future.set_result([details1, details2])
            provider._pending_requests[1] = future

            with pytest.raises(ValueError, match="Multiple matches"):
                await provider.get_symbol_info("AAPL")


@pytest.mark.asyncio
class TestGetHistoricalBars:
    """Test get_historical_bars implementation."""

    async def test_get_historical_bars_success(self) -> None:
        """Test successful historical bars retrieval."""
        provider = TWSProvider()

        # Create mock bars
        bar1 = BarData()
        bar1.date = "1609459200"
        bar1.open = 100.0
        bar1.high = 101.0
        bar1.low = 99.0
        bar1.close = 100.5
        bar1.volume = Decimal("1000")

        bar2 = BarData()
        bar2.date = "1609459260"
        bar2.open = 100.5
        bar2.high = 102.0
        bar2.low = 100.0
        bar2.close = 101.5
        bar2.volume = Decimal("1500")

        with patch.object(provider, "_get_next_req_id", return_value=1):
            from concurrent.futures import Future

            future: Future[list[BarData]] = Future()
            future.set_result([bar1, bar2])
            provider._pending_requests[1] = future

            # Execute
            start = datetime(2021, 1, 1)
            end = datetime(2021, 1, 2)
            bars = await provider.get_historical_bars(
                "AAPL", start, end, TimeFrame.MIN_1
            )

        assert len(bars) == 2
        assert all(isinstance(bar, Bar) for bar in bars)
        assert bars[0].open == 100.0
        assert bars[1].open == 100.5


class TestRealtimeSubscriptions:
    """Test real-time subscription methods."""

    def test_subscribe_realtime_bars(self) -> None:
        """Test real-time bar subscription."""
        provider = TWSProvider()

        received_bars: list[Bar] = []

        def callback(bar: Bar) -> None:
            received_bars.append(bar)

        # Mock TWS methods
        with (
            patch.object(provider.tws, "get_req_id", return_value=1),
            patch.object(provider.tws, "reqRealTimeBars") as mock_req,
        ):
            # Subscribe
            sub_id = provider.subscribe_realtime_bars("AAPL", callback)

            assert sub_id == 1
            assert sub_id in provider._subscriptions
            assert mock_req.called

    def test_subscribe_realtime_bars_invalid_resolution(self) -> None:
        """Test real-time bars with invalid resolution."""
        provider = TWSProvider()

        def callback(bar: Bar) -> None:
            pass

        # Should raise error for non-5-second resolution
        with pytest.raises(ValueError, match="5-second resolution"):
            provider.subscribe_realtime_bars(
                "AAPL", callback, resolution=TimeFrame.MIN_1
            )

    def test_unsubscribe_realtime_bars(self) -> None:
        """Test unsubscribing from real-time bars."""
        provider = TWSProvider()

        def callback(bar: Bar) -> None:
            pass

        # Mock TWS methods
        with (
            patch.object(provider.tws, "get_req_id", return_value=1),
            patch.object(provider.tws, "reqRealTimeBars"),
            patch.object(provider.tws, "cancelRealTimeBars") as mock_cancel,
        ):
            # Subscribe then unsubscribe
            sub_id = provider.subscribe_realtime_bars("AAPL", callback)
            provider.unsubscribe_realtime_bars(sub_id)

            assert sub_id not in provider._subscriptions
            mock_cancel.assert_called_once_with(sub_id)

    def test_unsubscribe_invalid_id(self) -> None:
        """Test unsubscribing with invalid subscription ID."""
        provider = TWSProvider()

        with pytest.raises(ValueError, match="Subscription ID not found"):
            provider.unsubscribe_realtime_bars(999)

    def test_subscribe_market_data_not_implemented(self) -> None:
        """Test market data subscription (not yet implemented)."""
        provider = TWSProvider()

        def callback(quote: object) -> None:
            pass

        with pytest.raises(NotImplementedError):
            provider.subscribe_market_data("AAPL", callback)
