"""Tests for TWS domain mappers.

Tests cover:
- contract_description_to_search_result (search_symbols)
- contract_details_to_symbol_info (get_symbol_info)
- tws_bar_to_domain_bar (historical bars)
- tws_ticks_to_quote_data (quote snapshots)
"""

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.tws_mappers import (
    SEC_TYPE_MAP,
    contract_description_to_search_result,
    contract_details_to_symbol_info,
    tws_bar_to_domain_bar,
    tws_ticks_to_quote_data,
)


class TestContractDescriptionMapper:
    """Test contract_description_to_search_result mapper."""

    def test_basic_stock_mapping(self) -> None:
        """Test mapping a basic stock contract description."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.localSymbol = "AAPL"
        contract.description = "Apple Inc"

        desc = ContractDescription()
        desc.contract = contract

        result = contract_description_to_search_result(desc)

        assert result.symbol == "AAPL"
        assert result.description == "Apple Inc"
        assert result.exchange == "NASDAQ"  # Uses primaryExchange
        assert result.ticker == "AAPL"
        assert result.type == "stock"

    def test_fallback_exchange(self) -> None:
        """Test fallback to exchange when primaryExchange is empty."""
        contract = Contract()
        contract.symbol = "EUR"
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"
        contract.primaryExchange = ""
        contract.localSymbol = "EUR.USD"

        desc = ContractDescription()
        desc.contract = contract

        result = contract_description_to_search_result(desc)

        assert result.exchange == "IDEALPRO"
        assert result.ticker == "EUR.USD"
        assert result.type == "forex"

    def test_sec_type_mapping(self) -> None:
        """Test all secType mappings."""
        for tws_type, expected_type in SEC_TYPE_MAP.items():
            contract = Contract()
            contract.symbol = "TEST"
            contract.secType = tws_type
            contract.exchange = "TEST"

            desc = ContractDescription()
            desc.contract = contract

            result = contract_description_to_search_result(desc)
            assert result.type == expected_type, f"Failed for {tws_type}"

    def test_unknown_sec_type_defaults_to_stock(self) -> None:
        """Test unknown secType defaults to 'stock'."""
        contract = Contract()
        contract.symbol = "TEST"
        contract.secType = "UNKNOWN"
        contract.exchange = "TEST"

        desc = ContractDescription()
        desc.contract = contract

        result = contract_description_to_search_result(desc)
        assert result.type == "stock"


class TestContractDetailsMapper:
    """Test contract_details_to_symbol_info mapper."""

    def test_basic_stock_mapping(self) -> None:
        """Test mapping a basic stock contract details."""
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

        result = contract_details_to_symbol_info(details)

        assert result.name == "MSFT"
        assert result.description == "Microsoft Corporation"
        assert result.type == "stock"
        assert result.exchange == "NASDAQ"
        assert result.listed_exchange == "SMART"
        assert result.ticker == "MSFT"
        assert result.pricescale == 100  # 1/0.01 = 100
        assert result.minmov == 1
        assert result.has_intraday is True
        assert result.has_daily is True
        assert result.data_status == "streaming"

    def test_pricescale_calculation(self) -> None:
        """Test pricescale is correctly calculated from minTick."""
        contract = Contract()
        contract.symbol = "TEST"
        contract.secType = "STK"
        contract.exchange = "TEST"

        # Test various minTick values
        test_cases = [
            (0.01, 100),
            (0.001, 1000),
            (0.0001, 10000),
            (0.05, 20),
            (1.0, 1),
        ]

        for min_tick, expected_pricescale in test_cases:
            details = ContractDetails()
            details.contract = contract
            details.minTick = min_tick

            result = contract_details_to_symbol_info(details)
            assert (
                result.pricescale == expected_pricescale
            ), f"Failed for minTick={min_tick}"

    def test_pricescale_zero_mintick_default(self) -> None:
        """Test pricescale defaults to 100 when minTick is 0 or None."""
        contract = Contract()
        contract.symbol = "TEST"
        contract.secType = "STK"
        contract.exchange = "TEST"

        details = ContractDetails()
        details.contract = contract
        details.minTick = 0

        result = contract_details_to_symbol_info(details)
        assert result.pricescale == 100

    def test_fallback_values(self) -> None:
        """Test fallback values when fields are empty."""
        contract = Contract()
        contract.symbol = "TEST"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = ""
        contract.localSymbol = ""

        details = ContractDetails()
        details.contract = contract
        details.longName = ""
        details.tradingHours = ""
        details.timeZoneId = ""

        result = contract_details_to_symbol_info(details)

        assert result.description == "TEST"  # Falls back to symbol
        assert result.exchange == "SMART"  # Falls back to exchange
        assert result.ticker == "TEST"  # Falls back to symbol
        assert result.session == "0930-1600"  # Default session
        assert result.timezone == "America/New_York"  # Default timezone

    def test_supported_resolutions(self) -> None:
        """Test supported resolutions are included."""
        contract = Contract()
        contract.symbol = "TEST"
        contract.secType = "STK"
        contract.exchange = "TEST"

        details = ContractDetails()
        details.contract = contract

        result = contract_details_to_symbol_info(details)

        expected_resolutions = ["1", "5", "15", "30", "60", "1D", "1W", "1M"]
        assert result.supported_resolutions == expected_resolutions

    def test_forex_mapping(self) -> None:
        """Test mapping forex contract details."""
        contract = Contract()
        contract.symbol = "EUR"
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"
        contract.primaryExchange = ""
        contract.localSymbol = "EUR.USD"

        details = ContractDetails()
        details.contract = contract
        details.longName = "Euro vs US Dollar"
        details.minTick = 0.00005

        result = contract_details_to_symbol_info(details)

        assert result.name == "EUR"
        assert result.type == "forex"
        assert result.pricescale == 20000  # 1/0.00005
        assert result.ticker == "EUR.USD"

    def test_futures_mapping(self) -> None:
        """Test mapping futures contract details."""
        contract = Contract()
        contract.symbol = "ES"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.localSymbol = "ESZ3"

        details = ContractDetails()
        details.contract = contract
        details.longName = "E-mini S&P 500"
        details.minTick = 0.25

        result = contract_details_to_symbol_info(details)

        assert result.name == "ES"
        assert result.type == "futures"
        assert result.pricescale == 4  # 1/0.25
        assert result.ticker == "ESZ3"


class TestTwsBarMapper:
    """Test tws_bar_to_domain_bar mapper."""

    def test_basic_bar_mapping(self) -> None:
        """Test mapping a basic TWS BarData to domain Bar."""
        from decimal import Decimal

        from ibapi.common import BarData

        tws_bar = BarData()
        tws_bar.date = "20231215  16:00:00 US/Eastern"
        tws_bar.open = 150.25
        tws_bar.high = 151.50
        tws_bar.low = 149.75
        tws_bar.close = 150.80
        tws_bar.volume = Decimal("1000000")

        result = tws_bar_to_domain_bar(tws_bar, "AAPL")

        assert result.open == 150.25
        assert result.high == 151.50
        assert result.low == 149.75
        assert result.close == 150.80
        assert result.volume == 1000000
        assert result.time > 0  # Valid timestamp

    def test_bar_with_single_space_date(self) -> None:
        """Test bar parsing with single space date format."""
        from decimal import Decimal

        from ibapi.common import BarData

        tws_bar = BarData()
        tws_bar.date = "20231215 16:00:00 UTC"
        tws_bar.open = 100.0
        tws_bar.high = 101.0
        tws_bar.low = 99.0
        tws_bar.close = 100.5
        tws_bar.volume = Decimal("500")

        result = tws_bar_to_domain_bar(tws_bar, "MSFT")

        assert result.open == 100.0
        assert result.close == 100.5
        assert result.volume == 500

    def test_bar_with_epoch_date(self) -> None:
        """Test bar parsing with epoch timestamp format."""
        from decimal import Decimal

        from ibapi.common import BarData

        tws_bar = BarData()
        tws_bar.date = "1702656000"  # Unix epoch timestamp
        tws_bar.open = 200.0
        tws_bar.high = 210.0
        tws_bar.low = 195.0
        tws_bar.close = 205.0
        tws_bar.volume = Decimal("2500")

        result = tws_bar_to_domain_bar(tws_bar, "GOOGL")

        assert result.time == 1702656000000  # Converted to milliseconds
        assert result.open == 200.0

    def test_bar_volume_conversion_from_decimal(self) -> None:
        """Test volume is correctly converted from Decimal to int."""
        from decimal import Decimal

        from ibapi.common import BarData

        tws_bar = BarData()
        tws_bar.date = "1702656000"
        tws_bar.open = 100.0
        tws_bar.high = 100.0
        tws_bar.low = 100.0
        tws_bar.close = 100.0
        tws_bar.volume = Decimal("12345678")

        result = tws_bar_to_domain_bar(tws_bar, "TEST")

        assert isinstance(result.volume, int)
        assert result.volume == 12345678


class TestTwsTicksToQuoteDataMapper:
    """Test tws_ticks_to_quote_data mapper."""

    def test_basic_quote_mapping(self) -> None:
        """Test mapping tick data to QuoteData."""
        from trading_api.models.market import QuoteValues

        ticks = {
            "BID": 150.25,
            "ASK": 150.30,
            "LAST": 150.28,
            "OPEN": 149.00,
            "HIGH": 151.00,
            "LOW": 148.50,
            "CLOSE": 149.50,
            "VOLUME": 1000000,
        }

        result = tws_ticks_to_quote_data("AAPL", ticks)

        assert result.s == "ok"
        assert result.n == "AAPL"
        assert isinstance(result.v, QuoteValues)
        assert result.v.bid == 150.25
        assert result.v.ask == 150.30
        assert result.v.lp == 150.28
        assert result.v.open_price == 149.00
        assert result.v.high_price == 151.00
        assert result.v.low_price == 148.50
        assert result.v.prev_close_price == 149.50
        assert result.v.volume == 1000000

    def test_spread_calculation(self) -> None:
        """Test spread is calculated from bid/ask."""
        from trading_api.models.market import QuoteValues

        ticks = {
            "BID": 100.00,
            "ASK": 100.10,
        }

        result = tws_ticks_to_quote_data("TEST", ticks)

        assert isinstance(result.v, QuoteValues)
        assert result.v.spread == pytest.approx(0.10)

    def test_change_calculation(self) -> None:
        """Test change and change percent are calculated."""
        from trading_api.models.market import QuoteValues

        ticks = {
            "LAST": 105.00,
            "CLOSE": 100.00,
        }

        result = tws_ticks_to_quote_data("TEST", ticks)

        assert isinstance(result.v, QuoteValues)
        assert result.v.ch == 5.0
        assert result.v.chp == 5.0  # 5% change

    def test_missing_values_default_to_zero(self) -> None:
        """Test missing tick values default to zero."""
        from trading_api.models.market import QuoteValues

        ticks: dict[str, float | int] = {}

        result = tws_ticks_to_quote_data("EMPTY", ticks)

        assert result.s == "ok"
        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 0.0
        assert result.v.bid == 0.0
        assert result.v.ask == 0.0
        assert result.v.volume == 0
        assert result.v.spread == 0.0

    def test_partial_tick_data(self) -> None:
        """Test handling of partial tick data."""
        from trading_api.models.market import QuoteValues

        ticks = {
            "LAST": 150.00,
            "VOLUME": 500000,
        }

        result = tws_ticks_to_quote_data("PARTIAL", ticks)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 150.00
        assert result.v.volume == 500000
        assert result.v.bid == 0.0  # Missing defaults to 0
        assert result.v.ask == 0.0
