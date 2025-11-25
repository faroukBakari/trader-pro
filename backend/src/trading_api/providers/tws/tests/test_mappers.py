"""Tests for TWS domain mappers.

Tests cover:
- contract_description_to_search_result (search_symbols)
- contract_details_to_symbol_info (get_symbol_info)
"""

from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.tws_mappers import (
    SEC_TYPE_MAP,
    contract_description_to_search_result,
    contract_details_to_symbol_info,
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
