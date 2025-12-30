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
        assert result.ticker == "AAPL:NASDAQ:STK"  # Composite format without conId
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
        assert result.ticker == "EUR:IDEALPRO:CASH"  # Composite format without conId
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
        assert result.listed_exchange == "NASDAQ"  # Uses primaryExchange
        assert result.ticker == "MSFT:NASDAQ:STK"  # Composite format without conId
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
        assert result.exchange == ""  # Uses primaryExchange (empty)
        assert result.ticker == "TEST::STK"  # Composite format with empty exchange
        assert result.session == "0000-2359"  # Default session (24h fallback)
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
        assert result.ticker == "EUR::CASH"  # Composite format, primaryExchange empty

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
        assert result.ticker == "ES::FUT"  # Composite format, primaryExchange empty


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

        result = tws_bar_to_domain_bar(tws_bar)

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

        result = tws_bar_to_domain_bar(tws_bar)

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

        result = tws_bar_to_domain_bar(tws_bar)

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

        result = tws_bar_to_domain_bar(tws_bar)

        assert isinstance(result.volume, int)
        assert result.volume == 12345678


class TestTwsTicksToQuoteDataMapper:
    """Test tws_ticks_to_quote_data mapper."""

    def test_basic_quote_mapping(self) -> None:
        """Test mapping dict ticker data to QuoteData."""
        from trading_api.models.market import QuoteValues

        rt_data = {
            "business_key": "datafeed:Quote:SMART:AAPL:NASDAQ:STK-12345",
            "bid": 150.25,
            "ask": 150.30,
            "last": 150.28,
            "bar_open": 149.00,
            "bar_high": 151.00,
            "bar_low": 148.50,
            "bar_close": 149.50,
            "bar_volume": 1000000,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert result.s == "ok"
        assert (
            result.n == "AAPL:NASDAQ:STK-12345"
        )  # Full ticker name for identification
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

        rt_data = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
            "bid": 100.00,
            "ask": 100.10,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.spread == pytest.approx(0.10)

    def test_change_calculation(self) -> None:
        """Test change and change percent are calculated."""
        from trading_api.models.market import QuoteValues

        rt_data = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
            "last": 105.00,
            "bar_close": 100.00,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.ch == 5.0
        assert result.v.chp == 5.0  # 5% change

    def test_missing_values_default_to_zero(self) -> None:
        """Test missing tick values default to zero."""
        from trading_api.models.market import QuoteValues

        rt_data: dict[str, object] = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
        }

        result = tws_ticks_to_quote_data(rt_data)

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

        rt_data = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
            "last": 150.00,
            "bar_volume": 500000,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 150.00
        assert result.v.volume == 500000
        assert result.v.bid == 0.0  # Missing defaults to 0
        assert result.v.ask == 0.0

    def test_rt_trd_volume_fallback_for_last_price(self) -> None:
        """Test rt_trd_volume provides fallback for last price when direct tick missing."""
        from trading_api.models.market import QuoteValues

        # Simulates STK market data stream where 'last' tick doesn't arrive
        # but rt_trd_volume does (Generic 375)
        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.55,
            "ask": 320.78,
            # No "last" field - this is the bug we're fixing
            "rt_trd_volume": "320.64;1.0;1765200318856;4027.0;320.359;true",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 320.64  # Parsed from rt_trd_volume
        assert result.v.bid == 320.55
        assert result.v.ask == 320.78
        assert result.v.volume == 4027  # totalVolume from rt_trd_volume

    def test_rt_volume_fallback_when_rt_trd_volume_missing(self) -> None:
        """Test rt_volume provides fallback when rt_trd_volume is missing."""
        from trading_api.models.market import QuoteValues

        rt_data = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
            "bid": 100.00,
            "ask": 100.05,
            "rt_volume": "99.95;100.0;1765200318856;5000.0;99.90;false",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 99.95  # Parsed from rt_volume
        assert result.v.volume == 5000

    def test_rt_volume_with_empty_price_ignored(self) -> None:
        """Test rt_volume with empty price (odd lot) doesn't override zero."""
        from trading_api.models.market import QuoteValues

        # Odd lot trades have empty price field
        rt_data = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
            "bid": 100.00,
            "ask": 100.05,
            "rt_volume": ";0E-16;1765200320968;4026.0;320.95;true",  # Empty price
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 0.0  # Should remain 0, not parsed from empty

    def test_direct_last_takes_priority_over_rt_volume(self) -> None:
        """Test direct 'last' tick takes priority over rt_trd_volume."""
        from trading_api.models.market import QuoteValues

        rt_data = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
            "last": 150.00,  # Direct tick
            "rt_trd_volume": "149.50;1.0;1765200318856;1000.0;149.00;true",  # Different
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 150.00  # Direct 'last' wins


class TestTwsTicksToQuoteDataRealWorldScenarios:
    """Tests using real production data sampled from api-traces.log."""

    def test_googl_stock_stream_without_last_tick(self) -> None:
        """Test GOOGL STK stream - real scenario where 'last' tick doesn't arrive.

        From logs: reqId=23 GOOGL subscription receives bid/ask but no 'last' tick.
        The rt_trd_volume field provides the last trade price as fallback.
        """
        from trading_api.models.market import QuoteValues

        # Real data from api-traces.log - GOOGL market data stream
        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.55,
            "ask": 320.78,
            # No "last" - this is the actual bug scenario
            "rt_trd_volume": "320.64;1.0000000000000000;1765200318856;363.0000000000000000;320.35900826;true",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 320.64  # From rt_trd_volume
        assert result.v.bid == 320.55
        assert result.v.ask == 320.78
        assert result.v.spread == 0.23
        assert result.v.volume == 363
        assert result.v.short_name == "GOOGL"
        assert result.v.exchange == "NASDAQ"

    def test_googl_stock_rt_volume_with_empty_price(self) -> None:
        """Test GOOGL with rt_volume odd lot (empty price field).

        From logs: rt_volume sometimes has empty price for odd lot trades.
        Format: ";0E-16;timestamp;totalVolume;vwap;singleMM"

        When price field is empty (starts with ";"), we skip the entire rt_volume
        parsing to avoid using potentially stale/irrelevant data.
        """
        from trading_api.models.market import QuoteValues

        # Real data - odd lot update with empty price
        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.51,
            "ask": 320.88,
            "rt_volume": ";0E-16;1765200320968;4026.0000000000000000;320.95565875;true",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 0.0  # Empty price - entire rt_volume skipped
        assert result.v.bid == 320.51
        assert result.v.ask == 320.88
        # Volume also 0 since rt_volume was skipped (no bar_volume provided)
        assert result.v.volume == 0

    def test_googl_stock_rt_volume_with_valid_price(self) -> None:
        """Test GOOGL with rt_volume containing valid trade price.

        From logs: rt_volume with actual trade data.
        """
        from trading_api.models.market import QuoteValues

        # Real data - rt_volume with trade
        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.51,
            "ask": 320.60,
            "rt_volume": "320.58;4.0000000000000000;1765200301083;4015.0000000000000000;320.95659154;false",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 320.58  # Parsed from rt_volume
        assert result.v.volume == 4015

    def test_btc_crypto_with_all_ticks(self) -> None:
        """Test BTC CRYPTO with complete tick data.

        From logs: BTC subscription receives all standard ticks including 'last'.
        """
        from trading_api.models.market import QuoteValues

        # Real data from api-traces.log - BTC complete tick data
        rt_data = {
            "business_key": "datafeed:Quote:PAXOS:BTC:PAXOS:CRYPTO-479624278",
            "bid": 91588.25,
            "ask": 91588.5,
            "last": 91608.75,
            "high": 92460.0,
            "low": 89032.5,
            "close": 91434.75,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 91608.75
        assert result.v.bid == 91588.25
        assert result.v.ask == 91588.5
        assert result.v.spread == 0.25
        assert result.v.short_name == "BTC"
        assert result.v.exchange == "PAXOS"

    def test_btc_crypto_initial_zero_values(self) -> None:
        """Test BTC CRYPTO with initial zero values before data arrives.

        From logs: Initial subscription may receive 0.0 for all prices.
        """
        from trading_api.models.market import QuoteValues

        # Real data - initial state with zeros
        rt_data = {
            "business_key": "datafeed:Quote:PAXOS:BTC:PAXOS:CRYPTO-479624278",
            "bid": 0.0,
            "ask": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 0.0
        assert result.v.bid == 0.0
        assert result.v.ask == 0.0
        assert result.v.spread == 0.0  # No spread when bid/ask are 0

    def test_stock_snapshot_with_complete_data(self) -> None:
        """Test stock snapshot request - receives all standard ticks.

        From logs: Snapshot requests (reqId=1,3,4,5) receive complete data.
        """
        from trading_api.models.market import QuoteValues

        # Real data from snapshot request
        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.55,
            "ask": 320.6,
            "last": 320.56,
            "bar_volume": 4011,
            "bar_close": 321.06,
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 320.56
        assert result.v.bid == 320.55
        assert result.v.ask == 320.6
        assert result.v.spread == 0.05
        assert result.v.volume == 4011
        assert result.v.prev_close_price == 321.06
        # Change calculation: last - close = 320.56 - 321.06 = -0.50
        assert result.v.ch == -0.5
        # Change percent: -0.50 / 321.06 * 100 = -0.16%
        assert result.v.chp == -0.16

    def test_rt_trd_volume_preferred_over_rt_volume(self) -> None:
        """Test that rt_trd_volume is preferred over rt_volume when both present.

        rt_trd_volume excludes unreportable trades (odd lots) so is more reliable.
        """
        from trading_api.models.market import QuoteValues

        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.55,
            "ask": 320.78,
            # Both present - rt_trd_volume should win
            "rt_trd_volume": "320.64;1.0;1765200318856;363.0;320.36;true",
            "rt_volume": "320.58;4.0;1765200301083;4015.0;320.96;false",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 320.64  # From rt_trd_volume, not rt_volume
        assert result.v.volume == 363  # From rt_trd_volume

    def test_high_precision_rt_volume_values(self) -> None:
        """Test parsing rt_volume with high precision decimal values.

        TWS sends values like "4.0000000000000000" which should parse correctly.
        """
        from trading_api.models.market import QuoteValues

        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.51,
            "ask": 320.60,
            # High precision values from actual logs
            "rt_volume": "320.60;3.0000000000000000;1765200301942;4018.0000000000000000;320.95632843;false",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)
        assert result.v.lp == 320.60
        assert result.v.volume == 4018
