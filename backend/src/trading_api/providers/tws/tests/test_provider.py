"""Tests for TWSProvider - DatafeedCapability implementation.

Tests cover:
- Provider initialization and configuration
- Provider capabilities declaration
- Domain mappers (TWS → domain conversion)
- search_symbols async flow
- get_symbol_info async flow
- get_historical_bars async flow
- get_quotes_snapshot async flow (concurrent requests)
- Subscription methods

Note: All tests mock TWSClient to avoid real TWS connections.
Note: Helper method tests (_build_contract, _map_timeframe, _calculate_duration)
      have been moved to test_tws_mappers.py since they are now module functions.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.models.common import DatafeedError
from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.providers.tws import TWSProvider
from trading_api.providers.tws.tws_mappers import contract_description_to_search_result


class TestProviderInitialization:
    """Test TWSProvider initialization and configuration."""

    def test_provider_default_config(self) -> None:
        """Test TWSProvider uses default config when none provided."""
        with patch("trading_api.providers.tws.TWSClient"):
            provider = TWSProvider()

        assert provider.config.host == "127.0.0.1"
        assert provider.config.port == 7497
        assert provider.config.client_id == 1

    def test_provider_with_custom_config(self) -> None:
        """Test TWSProvider config is stored correctly."""
        config = TWSProviderConfig(host="192.168.1.1", port=4002, client_id=2)

        with patch("trading_api.providers.tws.TWSClient"):
            provider = TWSProvider(config=config)

        assert provider.config.host == "192.168.1.1"
        assert provider.config.port == 4002
        assert provider.config.client_id == 2

    def test_provider_capabilities(self) -> None:
        """Test provider capabilities declaration."""
        caps = TWSProvider.capabilities()

        assert len(caps) == 1
        assert caps[0].name == "datafeed"

    def test_provider_name(self) -> None:
        """Test provider name."""
        with patch("trading_api.providers.tws.TWSClient"):
            provider = TWSProvider()

        assert provider.name == "tws"

    def test_provider_creates_tws_client(self) -> None:
        """Test provider creates TWSClient with config."""
        with patch("trading_api.providers.tws.TWSClient") as MockClient:
            config = TWSProviderConfig(host="10.0.0.1", port=4001, client_id=10)
            TWSProvider(config=config)

        MockClient.assert_called_once_with("10.0.0.1", 4001, 10)


class TestDomainMappers:
    """Test TWS → domain conversion (tws_mappers.py)."""

    def test_contract_description_to_search_result(self) -> None:
        """Test TWS ContractDescription → SearchSymbolResultItem."""
        # Create TWS ContractDescription
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.primaryExchange = "NASDAQ"
        contract.description = "Apple Inc"

        desc = ContractDescription()
        desc.contract = contract
        desc.derivativeSecTypes = []

        # Convert using mapper
        result = contract_description_to_search_result(desc)

        assert isinstance(result, SearchSymbolResultItem)
        assert result.symbol == "AAPL"
        assert result.exchange == "NASDAQ"  # Uses primaryExchange
        assert result.type == "stock"  # STK → stock
        assert result.description == "Apple Inc"

    def test_contract_description_no_primary_exchange(self) -> None:
        """Test conversion when primaryExchange is not set."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.primaryExchange = ""  # Empty

        desc = ContractDescription()
        desc.contract = contract

        result = contract_description_to_search_result(desc)

        assert result.exchange == "SMART"  # Falls back to exchange

    def test_sec_type_mapping(self) -> None:
        """Test secType → type mapping covers common types."""
        test_cases = [
            ("STK", "stock"),
            ("OPT", "option"),
            ("FUT", "futures"),
            ("CASH", "forex"),
            ("IND", "index"),
            ("CRYPTO", "crypto"),
        ]

        for sec_type, expected_type in test_cases:
            contract = Contract()
            contract.symbol = "TEST"
            contract.exchange = "SMART"
            contract.secType = sec_type

            desc = ContractDescription()
            desc.contract = contract

            result = contract_description_to_search_result(desc)
            assert result.type == expected_type, f"Failed for {sec_type}"


class TestSearchSymbols:
    """Test search_symbols implementation."""

    @pytest.mark.asyncio
    async def test_search_symbols_returns_domain_models(self) -> None:
        """Test search_symbols returns SearchSymbolResultItem list."""
        # Create mock contract descriptions (TWS response)
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.exchange = "SMART"
        contract1.secType = "STK"
        contract1.primaryExchange = "NASDAQ"
        contract1.description = "Apple Inc"

        desc1 = ContractDescription()
        desc1.contract = contract1

        contract2 = Contract()
        contract2.symbol = "AAPL"
        contract2.exchange = "SMART"
        contract2.secType = "STK"
        contract2.primaryExchange = "NYSE"
        contract2.description = "Apple Inc"

        desc2 = ContractDescription()
        desc2.contract = contract2

        # Mock TWSClient.reqMatchingSymbols to return our test data
        mock_client = Mock()
        mock_client.reqMatchingSymbols = AsyncMock(return_value=[desc1, desc2])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            # Execute search
            results = await provider.search_symbols("AAPL")

        # Verify async method was called with pattern
        mock_client.reqMatchingSymbols.assert_called_once_with("AAPL")

        # Verify domain models returned
        assert len(results) == 2
        assert all(isinstance(r, SearchSymbolResultItem) for r in results)
        assert results[0].symbol == "AAPL"
        assert results[0].exchange == "NASDAQ"
        assert results[0].type == "stock"
        assert results[1].exchange == "NYSE"

    @pytest.mark.asyncio
    async def test_search_symbols_empty_results(self) -> None:
        """Test search_symbols with no matches."""
        mock_client = Mock()
        mock_client.reqMatchingSymbols = AsyncMock(return_value=[])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()
            results = await provider.search_symbols("NONEXISTENT")

        assert results == []


class TestGetSymbolInfo:
    """Test get_symbol_info implementation."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_returns_symbol_info(self) -> None:
        """Test get_symbol_info returns SymbolInfo domain model."""
        # Create mock contract details (TWS response)
        contract = Contract()
        contract.symbol = "MSFT"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.localSymbol = "MSFT"
        contract.currency = "USD"

        details = ContractDetails()
        details.contract = contract
        details.longName = "Microsoft Corporation"
        details.minTick = 0.01
        details.tradingHours = "20231120:0930-20231120:1600"
        details.timeZoneId = "America/New_York"

        # Mock TWSClient.reqContractDetails to return our test data
        mock_client = Mock()
        mock_client.reqContractDetails = AsyncMock(return_value=[details])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            # Execute get_symbol_info with composite ticker format
            result = await provider.get_symbol_info("MSFT:NASDAQ:STK-12345")

        # Verify async method was called with contract
        mock_client.reqContractDetails.assert_called_once()
        call_args = mock_client.reqContractDetails.call_args[0][0]
        assert call_args.symbol == "MSFT"
        assert call_args.primaryExchange == "NASDAQ"

        # Verify domain model returned
        assert isinstance(result, SymbolInfo)
        assert result.name == "MSFT"
        assert result.description == "Microsoft Corporation"
        assert result.type == "stock"
        assert result.exchange == "NASDAQ"
        assert result.pricescale == 100

    @pytest.mark.asyncio
    async def test_get_symbol_info_with_exchange(self) -> None:
        """Test get_symbol_info with specific exchange."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "NASDAQ"
        contract.primaryExchange = "NASDAQ"

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"
        details.minTick = 0.01

        mock_client = Mock()
        mock_client.reqContractDetails = AsyncMock(return_value=[details])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()
            # Use composite ticker format (exchange already in ticker)
            await provider.get_symbol_info("AAPL:NASDAQ:STK-12345")

        # Verify contract has correct exchange (from ticker)
        call_args = mock_client.reqContractDetails.call_args[0][0]
        assert call_args.primaryExchange == "NASDAQ"

    @pytest.mark.asyncio
    async def test_get_symbol_info_not_found_raises_error(self) -> None:
        """Test get_symbol_info raises DatafeedError when symbol not found."""
        mock_client = Mock()
        mock_client.reqContractDetails = AsyncMock(return_value=[])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            with pytest.raises(DatafeedError, match="Symbol not found"):
                # Use composite ticker format
                await provider.get_symbol_info("NONEXISTENT:SMART:STK-0")

    @pytest.mark.asyncio
    async def test_get_symbol_info_uses_first_result(self) -> None:
        """Test get_symbol_info uses first result when multiple returned."""
        # TWS may return multiple contract details for ambiguous queries
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.primaryExchange = "NASDAQ"
        details1 = ContractDetails()
        details1.contract = contract1
        details1.longName = "Apple Inc NASDAQ"
        details1.minTick = 0.01

        contract2 = Contract()
        contract2.symbol = "AAPL"
        contract2.primaryExchange = "NYSE"
        details2 = ContractDetails()
        details2.contract = contract2
        details2.longName = "Apple Inc NYSE"
        details2.minTick = 0.01

        mock_client = Mock()
        mock_client.reqContractDetails = AsyncMock(return_value=[details1, details2])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()
            # Use composite ticker format
            result = await provider.get_symbol_info("AAPL:NASDAQ:STK-12345")

        # Should use first result
        assert result.description == "Apple Inc NASDAQ"
        assert result.exchange == "NASDAQ"

    @pytest.mark.asyncio
    async def test_get_symbol_info_exception_wrapped(self) -> None:
        """Test get_symbol_info wraps exceptions in DatafeedError."""
        mock_client = Mock()
        mock_client.reqContractDetails = AsyncMock(
            side_effect=RuntimeError("TWS error")
        )

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            with pytest.raises(DatafeedError, match="Failed to get symbol info"):
                # Use composite ticker format
                await provider.get_symbol_info("AAPL:NASDAQ:STK-12345")


class TestGetHistoricalBars:
    """Test get_historical_bars DatafeedCapability method."""

    @pytest.mark.asyncio
    async def test_get_historical_bars_returns_bars(self) -> None:
        """Test get_historical_bars returns Bar list."""
        bar1 = BarData()
        bar1.date = "1702656000"  # Epoch format
        bar1.open = 150.0
        bar1.high = 151.0
        bar1.low = 149.5
        bar1.close = 150.5
        bar1.volume = Decimal("1000000")

        bar2 = BarData()
        bar2.date = "1702656060"
        bar2.open = 150.5
        bar2.high = 152.0
        bar2.low = 150.0
        bar2.close = 151.5
        bar2.volume = Decimal("800000")

        mock_client = Mock()
        mock_client.reqHistoricalData = AsyncMock(return_value=[bar1, bar2])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            results = await provider.get_historical_bars(
                ticker="AAPL:ARCA:STK-12345",  # Use ARCA (not in SMART_EXCHANGES) to avoid duplicate queries
                start_time=start,
                end_time=end,
                resolution=Resolution.MIN_1,
            )

        assert len(results) == 2
        assert all(isinstance(r, Bar) for r in results)
        assert results[0].open == 150.0
        assert results[0].close == 150.5
        assert results[1].close == 151.5

    @pytest.mark.asyncio
    async def test_get_historical_bars_maps_timeframe(self) -> None:
        """Test get_historical_bars maps timeframe to TWS bar size."""
        mock_client = Mock()
        mock_client.reqHistoricalData = AsyncMock(return_value=[])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            await provider.get_historical_bars(
                ticker="AAPL:NASDAQ:STK-12345",
                start_time=start,
                end_time=end,
                resolution=Resolution.MIN_5,
            )

        # Verify bar_size (4th positional arg) was passed correctly
        call_args = mock_client.reqHistoricalData.call_args
        # args: (contract, end_dt_str, duration_str, bar_size, ...)
        bar_size = call_args[0][3]
        assert bar_size == "5 mins"

    @pytest.mark.asyncio
    async def test_get_historical_bars_with_exchange(self) -> None:
        """Test get_historical_bars passes exchange to contract."""
        mock_client = Mock()
        mock_client.reqHistoricalData = AsyncMock(return_value=[])

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            await provider.get_historical_bars(
                ticker="AAPL:NASDAQ:STK-12345",
                start_time=start,
                end_time=end,
                resolution=Resolution.MIN_1,
            )

        # Verify contract has correct exchange (1st positional arg)
        call_args = mock_client.reqHistoricalData.call_args
        contract = call_args[0][0]
        assert contract.primaryExchange == "NASDAQ"

    @pytest.mark.asyncio
    async def test_get_historical_bars_wraps_exceptions(self) -> None:
        """Test get_historical_bars wraps exceptions in DatafeedError."""
        mock_client = Mock()
        mock_client.reqHistoricalData = AsyncMock(side_effect=RuntimeError("TWS error"))

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            with pytest.raises(DatafeedError, match="Failed to get historical bars"):
                await provider.get_historical_bars(
                    ticker="AAPL:NASDAQ:STK-12345",
                    start_time=start,
                    end_time=end,
                    resolution=Resolution.MIN_1,
                )


class TestGetQuotesSnapshot:
    """Test get_quotes_snapshot DatafeedCapability method."""

    @pytest.mark.asyncio
    async def test_get_quotes_snapshot_returns_quotes(self) -> None:
        """Test get_quotes_snapshot returns QuoteData list.

        Note: Current implementation returns basic quote data structures
        based on ticker names without actual market data.
        """
        mock_client = AsyncMock()
        mock_client.reqQuoteSnapshot.return_value = {}

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()
            # Use composite ticker format
            results = await provider.get_quotes_snapshot(
                ["AAPL:NASDAQ:STK-12345", "MSFT:NASDAQ:STK-67890"]
            )

        assert len(results) == 2
        assert all(isinstance(r, QuoteData) for r in results)

    @pytest.mark.asyncio
    async def test_get_quotes_snapshot_single_symbol(self) -> None:
        """Test get_quotes_snapshot with single symbol."""
        mock_client = AsyncMock()
        mock_client.reqQuoteSnapshot.return_value = {}

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()
            # Use composite ticker format
            results = await provider.get_quotes_snapshot(["AAPL:NASDAQ:STK-12345"])

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_quotes_snapshot_extracts_symbol_name(self) -> None:
        """Test get_quotes_snapshot extracts symbol name from ticker."""
        mock_client = AsyncMock()
        mock_client.reqQuoteSnapshot.return_value = {
            "ticker_name": "AAPL:NASDAQ:STK-12345"
        }

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()
            results = await provider.get_quotes_snapshot(["AAPL:NASDAQ:STK-12345"])

        # Verify the symbol name was extracted correctly
        assert results[0].n == "AAPL"


class TestSubscriptionMethods:
    """Test subscription methods using TWSClient stream APIs."""

    def test_subscribe_realtime_bars_returns_subscription_id(self) -> None:
        """Test subscribe_realtime_bars returns a subscription ID."""
        mock_client = Mock()
        mock_client.reqBarDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345@5 mins")

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            async def bar_callback(bar: object) -> None:
                pass

            sub_id = provider.subscribe_realtime_bars(
                "AAPL:NASDAQ:STK-12345", Resolution.MIN_5, bar_callback
            )

            assert isinstance(sub_id, str)
            mock_client.reqBarDataStream.assert_called_once()

    def test_subscribe_market_data_returns_subscription_ids(self) -> None:
        """Test subscribe_market_data returns list of subscription IDs."""
        mock_client = Mock()
        mock_client.reqMktDataStream = Mock(
            side_effect=[
                "AAPL:NASDAQ:STK-12345",
                "MSFT:NASDAQ:STK-67890",
                "GOOGL:NASDAQ:STK-99999",
            ]
        )

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            async def quote_callback(quote: object) -> None:
                pass

            sub_ids = provider.subscribe_market_data(
                [
                    "AAPL:NASDAQ:STK-12345",
                    "MSFT:NASDAQ:STK-67890",
                    "GOOGL:NASDAQ:STK-99999",
                ],
                quote_callback,
            )

            assert isinstance(sub_ids, list)
            assert len(sub_ids) == 3
            assert mock_client.reqMktDataStream.call_count == 3

    def test_unsubscribe_realtime_bars_calls_cancel(self) -> None:
        """Test unsubscribe_realtime_bars calls cancelBarDataStream."""
        mock_client = Mock()
        mock_client.reqBarDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345@5 mins")
        mock_client.cancelBarDataStream = Mock()

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            async def bar_callback(bar: object) -> None:
                pass

            sub_id = provider.subscribe_realtime_bars(
                "AAPL:NASDAQ:STK-12345", Resolution.MIN_5, bar_callback
            )

            # Unsubscribe
            provider.unsubscribe_realtime_bars(sub_id)

            # Verify cancel was called
            mock_client.cancelBarDataStream.assert_called_once_with(sub_id)

    def test_unsubscribe_market_data_calls_cancel(self) -> None:
        """Test unsubscribe_market_data calls cancelMktDataStream."""
        mock_client = Mock()
        mock_client.reqMktDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345")
        mock_client.cancelMktDataStream = Mock()

        with patch("trading_api.providers.tws.TWSClient", return_value=mock_client):
            provider = TWSProvider()

            async def quote_callback(quote: object) -> None:
                pass

            sub_ids = provider.subscribe_market_data(
                ["AAPL:NASDAQ:STK-12345"], quote_callback
            )

            provider.unsubscribe_market_data(sub_ids)

            mock_client.cancelMktDataStream.assert_called_once_with(sub_ids[0])
