"""Tests for TWSProvider - Provider pattern and search_symbols POC.

Tests cover:
- Provider initialization and configuration
- Provider capabilities declaration
- Domain mappers (TWS → domain conversion)
- search_symbols async flow
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from ibapi.contract import Contract, ContractDescription

from trading_api.models.market import SearchSymbolResultItem
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.providers.tws import TWSProvider
from trading_api.providers.tws.tws_mappers import contract_description_to_search_result


class TestProviderInitialization:
    """Test TWSProvider initialization and configuration."""

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
    """Test search_symbols implementation (POC focus)."""

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
