"""Tests for TWSDatafeedProvider - DatafeedCapability implementation.

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
Note: Helper method tests (_map_timeframe, _calculate_duration)
      have been moved to test_tws_mappers.py since they are now module functions.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.models.exceptions import ProviderException
from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.providers.tws_configs import TWSDatafeedProviderConfig
from trading_api.providers.tws import TWSDatafeedProvider
from trading_api.providers.tws.tws_mappers import contract_description_to_search_result


def _make_contract(
    symbol: str = "AAPL",
    sec_type: str = "STK",
    exchange: str = "SMART",
    primary_exchange: str = "NASDAQ",
    con_id: int = 265598,
) -> Contract:
    """Helper to create a Contract with required fields."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.primaryExchange = primary_exchange
    contract.conId = con_id
    return contract


def _setup_mock_client_with_contracts(
    mock_client: Mock, ticker: str = "AAPL:NASDAQ:STK"
) -> None:
    """Setup mock_client methods to return valid contracts.

    Sets up cache_contracts and reqContractDetails since the implementation
    calls cache_contracts which is now on TWSClient.

    Note: Does NOT overwrite cache_contracts or reqContractDetails if already
    explicitly configured with a tuple/list return_value (for custom test cases).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    parts = ticker.split(":")
    symbol = parts[0] if len(parts) > 0 else "AAPL"
    exchange = parts[1] if len(parts) > 1 else "NASDAQ"
    sec_type = parts[2].split("-")[0] if len(parts) > 2 else "STK"

    contract = _make_contract(
        symbol=symbol,
        sec_type=sec_type,
        exchange="SMART",
        primary_exchange=exchange,
    )

    # Build default contract_details
    contract_details = ContractDetails()
    contract_details.contract = contract
    contract_details.validExchanges = "SMART,NASDAQ"
    # Generate trading hours for today that cover 24 hours to ensure market is "open"
    now = datetime.now(ZoneInfo("US/Eastern"))
    today_str = now.strftime("%Y%m%d")
    contract_details.tradingHours = f"{today_str}:0000-{today_str}:2359"
    contract_details.timeZoneId = "US/Eastern"

    # Setup cache_contracts (returns tuple[ContractDetails, ContractDetails | None])
    # Only if not already configured with an explicit tuple return_value
    existing_cache_mock = getattr(mock_client, "cache_contracts", None)
    should_setup_cache = True
    if existing_cache_mock is not None and isinstance(existing_cache_mock, AsyncMock):
        if isinstance(existing_cache_mock.return_value, tuple):
            should_setup_cache = False

    if should_setup_cache:
        mock_client.cache_contracts = AsyncMock(return_value=(contract_details, None))

    # Setup reqContractDetails for any direct calls
    # Only if not already configured with an explicit list return_value
    existing_mock = getattr(mock_client, "reqContractDetails", None)
    should_setup = True
    if existing_mock is not None and isinstance(existing_mock, AsyncMock):
        # Check if it has been explicitly configured with a list return_value
        # (AsyncMock default return_value is a new AsyncMock, not a list)
        if isinstance(existing_mock.return_value, list):
            should_setup = False

    if should_setup:
        mock_client.reqContractDetails = AsyncMock(return_value=[contract_details])


class TestProviderInitialization:
    """Test TWSDatafeedProvider initialization and configuration."""

    def test_provider_default_config(self) -> None:
        """Test TWSDatafeedProvider uses default config when none provided."""
        with patch("trading_api.providers.tws.datafeed_provider.TWSClient"):
            provider = TWSDatafeedProvider()

        assert provider.config.host == "127.0.0.1"
        assert provider.config.port == 7497
        assert provider.config.client_id == 1

    def test_provider_with_custom_config(self) -> None:
        """Test TWSDatafeedProvider config is stored correctly."""
        config = TWSDatafeedProviderConfig(host="192.168.1.1", port=4002, client_id=2)

        with patch("trading_api.providers.tws.datafeed_provider.TWSClient"):
            provider = TWSDatafeedProvider(config=config)

        assert provider.config.host == "192.168.1.1"
        assert provider.config.port == 4002
        assert provider.config.client_id == 2

    def test_provider_capabilities(self) -> None:
        """Test provider capabilities declaration."""
        caps = TWSDatafeedProvider.capabilities()

        assert len(caps) == 1
        assert caps[0].name == "datafeed"

    def test_provider_name(self) -> None:
        """Test provider name."""
        with patch("trading_api.providers.tws.datafeed_provider.TWSClient"):
            provider = TWSDatafeedProvider()

        assert provider.name == "tws"

    def test_provider_creates_tws_client(self) -> None:
        """Test provider creates TWSClient with config."""
        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient"
        ) as MockClient:
            config = TWSDatafeedProviderConfig(host="10.0.0.1", port=4001, client_id=10)
            TWSDatafeedProvider(config=config)

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

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

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

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()
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
        contract.conId = 272093  # Required for filter check

        details = ContractDetails()
        details.contract = contract
        details.longName = "Microsoft Corporation"
        details.minTick = 0.01
        details.tradingHours = "20231120:0930-20231120:1600"
        details.timeZoneId = "America/New_York"

        # Mock TWSClient.cache_contracts to return our test data
        mock_client = Mock()
        mock_client.cache_contracts = AsyncMock(return_value=(details, None))

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            # Execute get_symbol_info with composite ticker format
            result = await provider.get_symbol_info("MSFT:NASDAQ:STK-12345")

        # Verify async method was called with ticker
        mock_client.cache_contracts.assert_called_once_with("MSFT:NASDAQ:STK-12345")

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
        contract.exchange = (
            "SMART"  # Must be SMART for STK with primaryExchange in SMART_EXCHANGES
        )
        contract.primaryExchange = "NASDAQ"
        contract.conId = 265598  # Required for filter check

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"
        details.minTick = 0.01

        mock_client = Mock()
        mock_client.cache_contracts = AsyncMock(return_value=(details, None))

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()
            # Use composite ticker format (exchange already in ticker)
            await provider.get_symbol_info("AAPL:NASDAQ:STK-12345")

        # Verify cache_contracts was called with correct ticker
        mock_client.cache_contracts.assert_called_once_with("AAPL:NASDAQ:STK-12345")

    @pytest.mark.asyncio
    async def test_get_symbol_info_not_found_raises_error(self) -> None:
        """Test get_symbol_info raises ProviderException when symbol not found."""
        mock_client = Mock()
        # cache_contracts raises ProviderException when symbol not found
        mock_client.cache_contracts = AsyncMock(
            side_effect=ProviderException(
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
                message="Symbol not found: NONEXISTENT:SMART:STK-0",
                provider="tws",
                capability="datafeed",
            )
        )

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            with pytest.raises(ProviderException, match="Symbol not found"):
                # Use composite ticker format
                await provider.get_symbol_info("NONEXISTENT:SMART:STK-0")

    @pytest.mark.asyncio
    async def test_get_symbol_info_uses_first_result(self) -> None:
        """Test get_symbol_info uses first (session) result from cache_contracts."""
        # cache_contracts returns (session_details, darkpool_details)
        # get_symbol_info uses session_details for the result
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.secType = "STK"
        contract1.exchange = "SMART"
        contract1.primaryExchange = "NASDAQ"
        contract1.conId = 265598  # Required for filter check
        details1 = ContractDetails()
        details1.contract = contract1
        details1.longName = "Apple Inc NASDAQ"
        details1.minTick = 0.01

        mock_client = Mock()
        # cache_contracts returns tuple (session_details, darkpool_details)
        mock_client.cache_contracts = AsyncMock(return_value=(details1, None))

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()
            # Use composite ticker format
            result = await provider.get_symbol_info("AAPL:NASDAQ:STK-12345")

        # Should use session_details (first in tuple)
        assert result.description == "Apple Inc NASDAQ"
        assert result.exchange == "NASDAQ"


class TestGetHistoricalBars:
    """Test get_historical_bars DatafeedCapability method."""

    @pytest.mark.asyncio
    async def test_get_historical_bars_returns_bars(self) -> None:
        """Test get_historical_bars returns Bar list."""
        # Return dicts matching the StreamData format from create_snapshot
        bar1 = {
            "date": "1702656000",  # Epoch format
            "open": 150.0,
            "high": 151.0,
            "low": 149.5,
            "close": 150.5,
            "volume": Decimal("1000000"),
        }

        bar2 = {
            "date": "1702656060",
            "open": 150.5,
            "high": 152.0,
            "low": 150.0,
            "close": 151.5,
            "volume": Decimal("800000"),
        }

        mock_client = Mock()
        mock_client.reqHistoricalData = AsyncMock(return_value=[bar1, bar2])
        _setup_mock_client_with_contracts(mock_client, "AAPL:ARCA:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            results = await provider.get_historical_bars(
                ticker_name="AAPL:ARCA:STK-12345",  # Use ARCA (not in SMART_EXCHANGES) to avoid duplicate queries
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
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            await provider.get_historical_bars(
                ticker_name="AAPL:NASDAQ:STK-12345",
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
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            start = datetime(2023, 12, 15, 9, 30, 0, tzinfo=timezone.utc)
            end = datetime(2023, 12, 15, 16, 0, 0, tzinfo=timezone.utc)

            await provider.get_historical_bars(
                ticker_name="AAPL:NASDAQ:STK-12345",
                start_time=start,
                end_time=end,
                resolution=Resolution.MIN_1,
            )

        # Verify contract has correct exchange (1st positional arg)
        call_args = mock_client.reqHistoricalData.call_args
        contract = call_args[0][0]
        assert contract.primaryExchange == "NASDAQ"


class TestGetQuotesSnapshot:
    """Test get_quotes_snapshot DatafeedCapability method."""

    @pytest.mark.asyncio
    async def test_get_quotes_snapshot_returns_quotes(self) -> None:
        """Test get_quotes_snapshot returns QuoteData list.

        Note: Current implementation returns basic quote data structures
        based on ticker names without actual market data.
        """
        mock_client = AsyncMock()
        # Return proper business_key for each call
        mock_client.reqQuoteSnapshot.side_effect = [
            {"business_key": "datafeed:Quote:NASDAQ:AAPL:NASDAQ:STK-12345"},
            {"business_key": "datafeed:Quote:NASDAQ:MSFT:NASDAQ:STK-67890"},
        ]
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()
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
        mock_client.reqQuoteSnapshot.return_value = {
            "business_key": "datafeed:Quote:NASDAQ:AAPL:NASDAQ:STK-12345"
        }
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()
            # Use composite ticker format
            results = await provider.get_quotes_snapshot(["AAPL:NASDAQ:STK-12345"])

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_quotes_snapshot_uses_ticker_name_as_symbol(self) -> None:
        """Test get_quotes_snapshot uses full ticker_name as symbol."""
        mock_client = AsyncMock()
        # Mock returns dict with business_key field used by tws_ticks_to_quote_data
        mock_client.reqQuoteSnapshot.return_value = {
            "business_key": "datafeed:Quote:NASDAQ:AAPL:NASDAQ:STK-12345"
        }
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()
            results = await provider.get_quotes_snapshot(["AAPL:NASDAQ:STK-12345"])

        # Verify the symbol name is the full ticker_name (extracted from business_key)
        assert results[0].n == "AAPL:NASDAQ:STK-12345"


class TestSubscriptionMethods:
    """Test subscription methods using TWSClient stream APIs."""

    @pytest.mark.asyncio
    async def test_subscribe_realtime_bars_returns_subscription_id(self) -> None:
        """Test subscribe_realtime_bars returns a subscription ID."""
        from trading_api.models.exceptions import TradingApiException

        mock_client = Mock()
        mock_client.reqBarDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345@5 mins")
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            async def bar_callback(bar: object) -> None:
                pass

            async def on_error(exc: TradingApiException) -> None:
                pass

            sub_id = await provider.subscribe_realtime_bars(
                "AAPL:NASDAQ:STK-12345", Resolution.MIN_5, bar_callback, on_error
            )

            assert isinstance(sub_id, str)
            mock_client.reqBarDataStream.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_market_data_returns_subscription_id(self) -> None:
        """Test subscribe_market_data returns a single subscription ID."""
        from trading_api.models.exceptions import TradingApiException

        mock_client = Mock()
        mock_client.reqMktDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345")
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            async def quote_callback(quote: object) -> None:
                pass

            async def on_error(exc: TradingApiException) -> None:
                pass

            sub_id = await provider.subscribe_market_data(
                "AAPL:NASDAQ:STK-12345",
                quote_callback,
                on_error,
            )

            assert isinstance(sub_id, str)
            assert sub_id == "AAPL:NASDAQ:STK-12345"
            mock_client.reqMktDataStream.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe_realtime_bars_calls_cancel(self) -> None:
        """Test unsubscribe_realtime_bars calls cancel_data_stream."""
        from trading_api.models.exceptions import TradingApiException

        mock_client = Mock()
        mock_client.reqBarDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345@5 mins")
        mock_client.cancel_data_stream = Mock()
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            async def bar_callback(bar: object) -> None:
                pass

            async def on_error(exc: TradingApiException) -> None:
                pass

            sub_id = await provider.subscribe_realtime_bars(
                "AAPL:NASDAQ:STK-12345", Resolution.MIN_5, bar_callback, on_error
            )

            # Unsubscribe
            provider.unsubscribe_realtime_bars(sub_id)

            # Verify cancel was called
            mock_client.cancel_data_stream.assert_called_once_with(sub_id)

    @pytest.mark.asyncio
    async def test_unsubscribe_market_data_calls_cancel(self) -> None:
        """Test unsubscribe_market_data calls cancel_data_stream."""
        from trading_api.models.exceptions import TradingApiException

        mock_client = Mock()
        mock_client.reqMktDataStream = Mock(return_value="AAPL:NASDAQ:STK-12345")
        mock_client.cancel_data_stream = Mock()
        _setup_mock_client_with_contracts(mock_client, "AAPL:NASDAQ:STK")

        with patch(
            "trading_api.providers.tws.datafeed_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSDatafeedProvider()

            async def quote_callback(quote: object) -> None:
                pass

            async def on_error(exc: TradingApiException) -> None:
                pass

            sub_id = await provider.subscribe_market_data(
                "AAPL:NASDAQ:STK-12345", quote_callback, on_error
            )

            provider.unsubscribe_market_data(sub_id)

            mock_client.cancel_data_stream.assert_called_once_with(sub_id)
