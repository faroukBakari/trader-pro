"""Tests for TWS domain mappers.

Tests cover:
- contract_description_to_search_result (search_symbols)
- contract_details_to_symbol_info (get_symbol_info)
- tws_bar_to_domain_bar (historical bars)
- tws_ticks_to_quote_data (quote snapshots)
- preorder_to_tws (order placement)
- tracked_order_to_placed_order (order mapping)
- tws_position_to_domain (position mapping)
- tws_account_summary_to_equity (equity mapping)
- tws_account_summary_to_account_info (account info mapping)
"""

from decimal import Decimal

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.order import Order as TWSOrder
from ibapi.order_state import OrderState

from trading_api.models.broker import OrderStatus, OrderType, Side
from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.order_tracker import OrderFill, TrackedOrder
from trading_api.providers.tws.tws_mappers import (
    ORDER_TYPE_TO_TWS,
    SEC_TYPE_MAP,
    SIDE_TO_TWS_ACTION,
    TWS_ACTION_TO_SIDE,
    TWS_STATUS_TO_ORDER_STATUS,
    TWS_TO_ORDER_TYPE,
    contract_description_to_search_result,
    contract_details_to_symbol_info,
    parse_tws_bar_date,
    preorder_to_tws,
    tracked_order_to_placed_order,
    tws_account_summary_to_account_info,
    tws_account_summary_to_equity,
    tws_bar_to_domain_bar,
    tws_position_to_domain,
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
        assert result.exchange == ""  # exchange field uses only primaryExchange
        # ticker uses primaryExchange or exchange fallback, so SMART is used
        assert result.ticker == "TEST:SMART:STK"
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
        # ticker_name uses primaryExchange or exchange, so IDEALPRO is used
        assert result.ticker == "EUR:IDEALPRO:CASH"

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
        # ticker_name uses primaryExchange or exchange, so CME is used
        assert result.ticker == "ES:CME:FUT"


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


# =============================================================================
# Broker Mapper Tests
# =============================================================================


class TestOrderMappingConstants:
    """Test order mapping constant dictionaries."""

    def test_order_type_to_tws_mapping(self) -> None:
        """Test domain OrderType to TWS string mapping."""
        assert ORDER_TYPE_TO_TWS[1] == "LMT"  # LIMIT
        assert ORDER_TYPE_TO_TWS[2] == "MKT"  # MARKET
        assert ORDER_TYPE_TO_TWS[3] == "STP"  # STOP
        assert ORDER_TYPE_TO_TWS[4] == "STP LMT"  # STOP_LIMIT

    def test_tws_to_order_type_mapping(self) -> None:
        """Test TWS string to domain OrderType mapping."""
        assert TWS_TO_ORDER_TYPE["LMT"] == 1
        assert TWS_TO_ORDER_TYPE["MKT"] == 2
        assert TWS_TO_ORDER_TYPE["STP"] == 3
        assert TWS_TO_ORDER_TYPE["STP LMT"] == 4
        # Aliases
        assert TWS_TO_ORDER_TYPE["STOP"] == 3
        assert TWS_TO_ORDER_TYPE["STOP_LIMIT"] == 4

    def test_side_to_tws_action_mapping(self) -> None:
        """Test domain Side to TWS action string mapping."""
        assert SIDE_TO_TWS_ACTION[1] == "BUY"  # Side.BUY
        assert SIDE_TO_TWS_ACTION[-1] == "SELL"  # Side.SELL

    def test_tws_action_to_side_mapping(self) -> None:
        """Test TWS action to domain Side mapping."""
        assert TWS_ACTION_TO_SIDE["BUY"] == 1
        assert TWS_ACTION_TO_SIDE["SELL"] == -1
        # Historical actions
        assert TWS_ACTION_TO_SIDE["BOT"] == 1
        assert TWS_ACTION_TO_SIDE["SLD"] == -1

    def test_tws_status_to_order_status_mapping(self) -> None:
        """Test TWS order status to domain OrderStatus mapping."""
        # Placing states
        assert TWS_STATUS_TO_ORDER_STATUS["PendingSubmit"] == 4  # PLACING
        assert TWS_STATUS_TO_ORDER_STATUS["PendingCancel"] == 4
        assert TWS_STATUS_TO_ORDER_STATUS["PreSubmitted"] == 4
        assert TWS_STATUS_TO_ORDER_STATUS["ApiPending"] == 4
        # Working
        assert TWS_STATUS_TO_ORDER_STATUS["Submitted"] == 6  # WORKING
        # Cancelled
        assert TWS_STATUS_TO_ORDER_STATUS["ApiCancelled"] == 1  # CANCELED
        assert TWS_STATUS_TO_ORDER_STATUS["Cancelled"] == 1
        # Other
        assert TWS_STATUS_TO_ORDER_STATUS["Filled"] == 2  # FILLED
        assert TWS_STATUS_TO_ORDER_STATUS["Inactive"] == 3  # INACTIVE


class TestPreorderToTws:
    """Test preorder_to_tws mapper."""

    def test_basic_market_order(self) -> None:
        """Test converting a basic market buy order."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK-12345",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=100,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "DU123456", 1)

        assert parent.action == "BUY"
        assert parent.totalQuantity == Decimal("100")
        assert parent.orderType == "MKT"
        assert parent.account == "DU123456"
        assert parent.tif == "GTC"
        assert parent.transmit is True
        assert stop_loss is None
        assert take_profit is None

    def test_limit_order(self) -> None:
        """Test converting a limit sell order."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="MSFT:NASDAQ:STK-54321",
            type=OrderType.LIMIT,
            side=Side.SELL,
            qty=50,
            limitPrice=350.50,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.action == "SELL"
        assert parent.totalQuantity == Decimal("50")
        assert parent.orderType == "LMT"
        assert parent.lmtPrice == 350.50
        assert parent.account == ""  # Empty when not specified
        assert stop_loss is None
        assert take_profit is None

    def test_stop_order(self) -> None:
        """Test converting a stop order."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="GOOGL:NASDAQ:STK",
            type=OrderType.STOP,
            side=Side.SELL,
            qty=25,
            stopPrice=145.00,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "STP"
        assert parent.auxPrice == 145.00
        assert stop_loss is None
        assert take_profit is None

    def test_stop_limit_order(self) -> None:
        """Test converting a stop-limit order."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="TSLA:NASDAQ:STK",
            type=OrderType.STOP_LIMIT,
            side=Side.BUY,
            qty=10,
            limitPrice=250.00,
            stopPrice=245.00,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "STP LMT"
        assert parent.lmtPrice == 250.00
        assert parent.auxPrice == 245.00
        assert stop_loss is None
        assert take_profit is None

    def test_forex_order(self) -> None:
        """Test converting a forex order."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="EUR:IDEALPRO:CASH",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10000,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "MKT"
        assert stop_loss is None
        assert take_profit is None

    def test_futures_order(self) -> None:
        """Test converting a futures order."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="ES:CME:FUT",
            type=OrderType.LIMIT,
            side=Side.SELL,
            qty=1,
            limitPrice=5000.00,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "LMT"
        assert parent.lmtPrice == 5000.00
        assert stop_loss is None
        assert take_profit is None

    def test_order_with_take_profit_only(self) -> None:
        """Test converting order with only take profit bracket."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            takeProfit=160.00,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "LMT"
        assert stop_loss is None
        assert take_profit is not None
        assert take_profit.orderType == "LMT"
        assert take_profit.lmtPrice == 160.00
        assert take_profit.action == "SELL"  # Opposite side
        assert take_profit.totalQuantity == Decimal("100")

    def test_order_with_stop_loss_only(self) -> None:
        """Test converting order with only stop loss bracket."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            stopLoss=145.00,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "LMT"
        assert take_profit is None
        assert stop_loss is not None
        assert stop_loss.orderType == "STP"
        assert stop_loss.auxPrice == 145.00
        assert stop_loss.action == "SELL"  # Opposite side
        assert stop_loss.totalQuantity == Decimal("100")

    def test_order_with_full_brackets(self) -> None:
        """Test converting order with both stop loss and take profit."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "LMT"
        assert stop_loss is not None
        assert take_profit is not None
        # Both should be linked via OCA group
        assert stop_loss.ocaGroup == take_profit.ocaGroup
        assert stop_loss.ocaType == 1  # CANCEL_WITH_BLOCK
        assert take_profit.ocaType == 1

    def test_order_with_trailing_stop(self) -> None:
        """Test converting order with trailing stop bracket."""
        from trading_api.models.broker import PreOrder, StopType

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            trailingStopPips=5.00,
            stopType=StopType.TRAILING_STOP,
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "LMT"
        assert take_profit is None
        assert stop_loss is not None
        assert stop_loss.orderType == "TRAIL"
        assert stop_loss.auxPrice == 5.00  # Trail amount

    def test_guaranteed_stop_raises_exception(self) -> None:
        """Test that guaranteed stop raises ProviderException (not supported)."""
        from trading_api.models.broker import PreOrder
        from trading_api.models.exceptions import ProviderException

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            guaranteedStop=140.00,
        )

        with pytest.raises(ProviderException) as exc_info:
            preorder_to_tws(preorder, "", 1)

        assert "PROVIDER_BROKER_UNSUPPORTED_FEATURE" in str(exc_info.value.code)
        assert "Guaranteed stop" in str(exc_info.value.message)

    def test_sell_order_brackets_have_buy_children(self) -> None:
        """Test that sell order brackets create BUY child orders."""
        from trading_api.models.broker import PreOrder

        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.SELL,  # Parent is SELL
            qty=100,
            limitPrice=150.00,
            stopLoss=155.00,  # Stop above for short
            takeProfit=140.00,  # Take profit below for short
        )

        parent, stop_loss, take_profit = preorder_to_tws(preorder, "", 1)

        assert parent.action == "SELL"
        assert stop_loss is not None
        assert take_profit is not None
        # Children should be BUY (opposite of parent)
        assert stop_loss.action == "BUY"
        assert take_profit.action == "BUY"


class TestTrackedOrderToPlacedOrder:
    """Test tracked_order_to_placed_order mapper."""

    def test_basic_working_order(self) -> None:
        """Test mapping a basic working order."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.conId = 12345

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "MKT"
        order.filledQuantity = Decimal("0")
        order.lmtPrice = 0.0
        order.auxPrice = 0.0

        order_state = OrderState()
        order_state.status = "Submitted"

        tracked = TrackedOrder(
            orderId=1,
            contract=contract,
            order=order,
            orderState=order_state,
        )

        result = tracked_order_to_placed_order(tracked)

        assert result.id == "1"
        # ticker_name returns SYMBOL:primaryExchange:SECTYPE (no conId)
        assert result.symbol == "AAPL:NASDAQ:STK"
        assert result.type == OrderType.MARKET
        assert result.side == Side.BUY
        assert result.qty == 100
        assert result.status == OrderStatus.WORKING
        assert result.limitPrice is None
        assert result.stopPrice is None
        assert result.filledQty is None
        assert result.avgPrice is None

    def test_filled_order_with_price(self) -> None:
        """Test mapping a filled order with fill information."""
        contract = Contract()
        contract.symbol = "MSFT"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        order = TWSOrder()
        order.action = "SELL"
        order.totalQuantity = Decimal("50")
        order.orderType = "LMT"
        order.lmtPrice = 350.00
        order.auxPrice = 0.0
        order.filledQuantity = Decimal("50")

        order_state = OrderState()
        order_state.status = "Filled"

        fill = OrderFill(
            orderId=2,
            status="Filled",
            filled=Decimal("50"),
            remaining=Decimal("0"),
            avgFillPrice=350.25,
            permId=123456,
            parentId=0,
            lastFillPrice=350.25,
            clientId=1,
            whyHeld="",
            mktCapPrice=0.0,
            timestamp=1234567890,
        )

        tracked = TrackedOrder(
            orderId=2,
            contract=contract,
            order=order,
            orderState=order_state,
            fills=[fill],
        )

        result = tracked_order_to_placed_order(tracked)

        assert result.id == "2"
        assert result.type == OrderType.LIMIT
        assert result.side == Side.SELL
        assert result.status == OrderStatus.FILLED
        assert result.limitPrice == 350.00
        assert result.filledQty == 50.0
        assert result.avgPrice == 350.25

    def test_cancelled_order(self) -> None:
        """Test mapping a cancelled order."""
        contract = Contract()
        contract.symbol = "GOOGL"
        contract.secType = "STK"
        contract.exchange = "SMART"

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("25")
        order.orderType = "STP"
        order.lmtPrice = 0.0
        order.auxPrice = 150.00
        order.filledQuantity = Decimal("0")

        order_state = OrderState()
        order_state.status = "Cancelled"

        tracked = TrackedOrder(
            orderId=3,
            contract=contract,
            order=order,
            orderState=order_state,
        )

        result = tracked_order_to_placed_order(tracked)

        assert result.status == OrderStatus.CANCELED
        assert result.stopPrice == 150.00

    def test_stop_limit_order_mapping(self) -> None:
        """Test mapping a stop-limit order."""
        contract = Contract()
        contract.symbol = "TSLA"
        contract.secType = "STK"
        contract.exchange = "SMART"

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("10")
        order.orderType = "STP LMT"
        order.lmtPrice = 250.00
        order.auxPrice = 245.00
        order.filledQuantity = Decimal("0")

        order_state = OrderState()
        order_state.status = "PreSubmitted"

        tracked = TrackedOrder(
            orderId=4,
            contract=contract,
            order=order,
            orderState=order_state,
        )

        result = tracked_order_to_placed_order(tracked)

        assert result.type == OrderType.STOP_LIMIT
        assert result.limitPrice == 250.00
        assert result.stopPrice == 245.00
        assert result.status == OrderStatus.PLACING

    def test_partial_fill(self) -> None:
        """Test mapping a partially filled order."""
        contract = Contract()
        contract.symbol = "NVDA"
        contract.secType = "STK"
        contract.exchange = "SMART"

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "LMT"
        order.lmtPrice = 500.00
        order.auxPrice = 0.0
        order.filledQuantity = Decimal("60")

        order_state = OrderState()
        order_state.status = "Submitted"  # Still working

        fill1 = OrderFill(
            orderId=5,
            status="Submitted",
            filled=Decimal("30"),
            remaining=Decimal("70"),
            avgFillPrice=500.10,
            permId=123457,
            parentId=0,
            lastFillPrice=500.15,
            clientId=1,
            whyHeld="",
            mktCapPrice=0.0,
            timestamp=1234567890,
        )
        fill2 = OrderFill(
            orderId=5,
            status="Submitted",
            filled=Decimal("60"),
            remaining=Decimal("40"),
            avgFillPrice=500.08,
            permId=123457,
            parentId=0,
            lastFillPrice=500.05,
            clientId=1,
            whyHeld="",
            mktCapPrice=0.0,
            timestamp=1234567891,
        )

        tracked = TrackedOrder(
            orderId=5,
            contract=contract,
            order=order,
            orderState=order_state,
            fills=[fill1, fill2],
        )

        result = tracked_order_to_placed_order(tracked)

        assert result.qty == 100
        assert result.filledQty == 60.0
        assert result.avgPrice == 500.08  # Last fill's avgFillPrice
        assert result.status == OrderStatus.WORKING

    def test_bracket_context_preserved(self) -> None:
        """Test that BracketContext fields are preserved in PlacedOrder."""
        from trading_api.models.broker import StopType
        from trading_api.providers.tws.tws_mappers import BracketContext

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "LMT"
        order.lmtPrice = 150.00
        order.auxPrice = 0.0
        order.filledQuantity = Decimal("0")

        order_state = OrderState()
        order_state.status = "Submitted"

        tracked = TrackedOrder(
            orderId=100,
            contract=contract,
            order=order,
            orderState=order_state,
        )

        # Create bracket context with all fields
        bracket_context = BracketContext(
            take_profit=160.00,
            stop_loss=145.00,
            trailing_stop_pips=5.00,
            stop_type=int(StopType.TRAILING_STOP),
            child_order_ids=[101, 102],
        )

        result = tracked_order_to_placed_order(tracked, bracket_context)

        assert result.takeProfit == 160.00
        assert result.stopLoss == 145.00
        assert result.trailingStopPips == 5.00
        assert result.stopType == StopType.TRAILING_STOP

    def test_no_bracket_context_fields_are_none(self) -> None:
        """Test that bracket fields are None when no context provided."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "LMT"
        order.lmtPrice = 150.00
        order.auxPrice = 0.0
        order.filledQuantity = Decimal("0")

        order_state = OrderState()
        order_state.status = "Submitted"

        tracked = TrackedOrder(
            orderId=100,
            contract=contract,
            order=order,
            orderState=order_state,
        )

        result = tracked_order_to_placed_order(tracked, None)

        assert result.takeProfit is None
        assert result.stopLoss is None
        assert result.trailingStopPips is None
        assert result.stopType is None
        assert result.guaranteedStop is None  # Always None (not supported)


class TestTwsPositionToDomain:
    """Test tws_position_to_domain mapper."""

    def test_long_position_with_contract(self) -> None:
        """Test mapping a long position with contract object."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.conId = 12345

        position_data = {
            "account": "DU123456",
            "contract": contract,
            "position": Decimal("100"),
            "avgCost": 150.50,
        }

        result = tws_position_to_domain(position_data)

        # ticker_name returns SYMBOL:primaryExchange:SECTYPE (no conId)
        assert result.id == "AAPL:NASDAQ:STK"
        assert result.symbol == "AAPL:NASDAQ:STK"
        assert result.qty == 100.0
        assert result.side == Side.BUY
        assert result.avgPrice == 150.50

    def test_short_position(self) -> None:
        """Test mapping a short position (negative quantity)."""
        contract = Contract()
        contract.symbol = "TSLA"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        position_data = {
            "account": "DU123456",
            "contract": contract,
            "position": Decimal("-50"),  # Short position
            "avgCost": 250.75,
        }

        result = tws_position_to_domain(position_data)

        assert result.qty == 50.0  # Absolute value
        assert result.side == Side.SELL  # Short

    def test_position_without_contract_uses_flattened_fields(self) -> None:
        """Test mapping position using flattened fields when contract is None."""
        position_data = {
            "account": "DU123456",
            "contract": None,
            "position": Decimal("75"),
            "avgCost": 100.00,
            "symbol": "MSFT",
            "exchange": "NASDAQ",
            "secType": "STK",
        }

        result = tws_position_to_domain(position_data)

        assert result.symbol == "MSFT:NASDAQ:STK"
        assert result.qty == 75.0

    def test_forex_position(self) -> None:
        """Test mapping a forex position."""
        contract = Contract()
        contract.symbol = "EUR"
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"
        contract.primaryExchange = ""

        position_data = {
            "account": "DU123456",
            "contract": contract,
            "position": Decimal("10000"),
            "avgCost": 1.0850,
        }

        result = tws_position_to_domain(position_data)

        # ticker_name uses primaryExchange or exchange, so IDEALPRO is used
        assert result.symbol == "EUR:IDEALPRO:CASH"
        assert result.qty == 10000.0
        assert result.avgPrice == 1.0850


class TestTwsAccountSummaryToEquity:
    """Test tws_account_summary_to_equity mapper."""

    def test_complete_account_summary(self) -> None:
        """Test mapping complete account summary data."""
        summary_data = {
            "NetLiquidation": {
                "account": "DU123456",
                "tag": "NetLiquidation",
                "value": "100000.00",
                "currency": "USD",
            },
            "TotalCashValue": {
                "account": "DU123456",
                "tag": "TotalCashValue",
                "value": "75000.50",
                "currency": "USD",
            },
            "UnrealizedPnL": {
                "account": "DU123456",
                "tag": "UnrealizedPnL",
                "value": "5000.25",
                "currency": "USD",
            },
            "RealizedPnL": {
                "account": "DU123456",
                "tag": "RealizedPnL",
                "value": "2500.00",
                "currency": "USD",
            },
        }

        result = tws_account_summary_to_equity(summary_data)

        assert result.equity == 100000.00
        assert result.balance == 75000.50
        assert result.unrealizedPL == 5000.25
        assert result.realizedPL == 2500.00

    def test_partial_summary_missing_tags(self) -> None:
        """Test mapping summary with missing tags defaults to 0."""
        summary_data = {
            "NetLiquidation": {
                "account": "DU123456",
                "tag": "NetLiquidation",
                "value": "50000.00",
                "currency": "USD",
            },
        }

        result = tws_account_summary_to_equity(summary_data)

        assert result.equity == 50000.00
        assert result.balance == 0.0  # Missing
        assert result.unrealizedPL == 0.0  # Missing
        assert result.realizedPL == 0.0  # Missing

    def test_empty_value_string(self) -> None:
        """Test handling empty value strings."""
        summary_data = {
            "NetLiquidation": {
                "account": "DU123456",
                "tag": "NetLiquidation",
                "value": "",
                "currency": "USD",
            },
        }

        result = tws_account_summary_to_equity(summary_data)

        assert result.equity == 0.0

    def test_invalid_value_string(self) -> None:
        """Test handling invalid numeric value strings."""
        summary_data = {
            "NetLiquidation": {
                "account": "DU123456",
                "tag": "NetLiquidation",
                "value": "not_a_number",
                "currency": "USD",
            },
        }

        result = tws_account_summary_to_equity(summary_data)

        assert result.equity == 0.0


class TestTwsAccountSummaryToAccountInfo:
    """Test tws_account_summary_to_account_info mapper."""

    def test_basic_account_info(self) -> None:
        """Test mapping basic account info."""
        summary_data = {
            "DU123456": {
                "NetLiquidation": {
                    "account": "DU123456",
                    "tag": "NetLiquidation",
                    "value": "100000.00",
                    "currency": "USD",
                },
            },
        }

        result = tws_account_summary_to_account_info(summary_data, "DU123456")

        assert result.id == "DU123456"
        assert result.name == "IBKR DU123456"

    def test_account_info_extracts_account_from_data(self) -> None:
        """Test account ID extraction from nested data."""
        summary_data = {
            "U9876543": {
                "TotalCashValue": {
                    "account": "U9876543",
                    "tag": "TotalCashValue",
                    "value": "50000.00",
                    "currency": "USD",
                },
            },
        }

        result = tws_account_summary_to_account_info(summary_data, "DEFAULT")

        assert result.id == "U9876543"
        assert result.name == "IBKR U9876543"

    def test_skips_metadata_keys(self) -> None:
        """Test that reqId and business_key metadata keys are skipped."""
        from typing import Any

        summary_data: dict[str, Any] = {
            "reqId": {"value": "123"},
            "business_key": {"value": "broker:account"},
            "DU123456": {
                "NetLiquidation": {
                    "account": "DU123456",
                    "value": "100000.00",
                },
            },
        }

        result = tws_account_summary_to_account_info(summary_data, "DU123456")

        assert result.id == "DU123456"


class TestParseTwsBarDate:
    """Test parse_tws_bar_date function for various TWS date formats."""

    def test_us_central_timezone(self) -> None:
        """Test parsing US/Central timezone format (the bug case)."""
        date_str = "20251229 08:30:00 US/Central"
        result = parse_tws_bar_date(date_str)
        # 2025-12-29 08:30:00 US/Central = 2025-12-29 14:30:00 UTC
        assert result > 0
        assert isinstance(result, int)

    def test_us_eastern_timezone_two_spaces(self) -> None:
        """Test parsing US/Eastern timezone with two spaces."""
        date_str = "20251229  08:30:00 US/Eastern"
        result = parse_tws_bar_date(date_str)
        assert result > 0
        assert isinstance(result, int)

    def test_us_eastern_timezone_single_space(self) -> None:
        """Test parsing US/Eastern timezone with single space."""
        date_str = "20251229 08:30:00 US/Eastern"
        result = parse_tws_bar_date(date_str)
        assert result > 0
        assert isinstance(result, int)

    def test_utc_timezone(self) -> None:
        """Test parsing UTC timezone format."""
        date_str = "20251229 08:30:00 UTC"
        result = parse_tws_bar_date(date_str)
        assert result > 0
        assert isinstance(result, int)

    def test_daily_bar_date_only(self) -> None:
        """Test parsing daily bar format (date only)."""
        date_str = "20251229"
        result = parse_tws_bar_date(date_str)
        assert result > 0
        assert isinstance(result, int)

    def test_epoch_format(self) -> None:
        """Test parsing epoch seconds format."""
        date_str = "1735500600"  # Some epoch timestamp
        result = parse_tws_bar_date(date_str)
        assert result == 1735500600000  # Converted to milliseconds

    def test_invalid_format_raises_exception(self) -> None:
        """Test that invalid format raises ProviderException."""
        date_str = "invalid-date-format"
        with pytest.raises(ProviderException) as exc_info:
            parse_tws_bar_date(date_str)
        assert "PROVIDER_TWS_INVALID_DATE_FORMAT" in str(exc_info.value)

    def test_whitespace_stripped(self) -> None:
        """Test that leading/trailing whitespace is handled."""
        date_str = "  20251229  "
        result = parse_tws_bar_date(date_str)
        assert result > 0
