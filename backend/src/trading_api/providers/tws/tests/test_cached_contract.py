"""Tests for CachedContract - contract caching utility.

Tests cover:
- Factory methods (from_contract_details, from_contract_description)
- Conversion methods (to_contract_details, to_contract_description)
- Cache update (update_from_details)
- Ticker matching (matches)
"""

from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.cached_contract import CachedContract


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


class TestCachedContractFromContractDetails:
    """Test CachedContract.from_contract_details factory method."""

    def test_creates_cached_contract_with_full_details(self) -> None:
        """Test from_contract_details creates CachedContract with has_full_details=True."""
        details = ContractDetails()
        details.contract = _make_contract()
        details.longName = "Apple Inc"
        details.minTick = 0.01

        cached = CachedContract.from_contract_details(details)

        assert cached.has_full_details is True
        assert cached.contract.symbol == "AAPL"
        assert cached.longName == "Apple Inc"
        assert cached.minTick == 0.01

    def test_generates_ticker_from_contract(self) -> None:
        """Test from_contract_details generates ticker string."""
        details = ContractDetails()
        details.contract = _make_contract()

        cached = CachedContract.from_contract_details(details)

        assert cached.ticker == "AAPL:NASDAQ:STK"

    def test_con_id_property_returns_contract_conid(self) -> None:
        """Test con_id property returns contract.conId."""
        details = ContractDetails()
        details.contract = _make_contract(con_id=12345)

        cached = CachedContract.from_contract_details(details)

        assert cached.con_id == 12345


class TestCachedContractFromContractDescription:
    """Test CachedContract.from_contract_description factory method."""

    def test_creates_cached_contract_without_full_details(self) -> None:
        """Test from_contract_description creates CachedContract with has_full_details=False."""
        desc = ContractDescription()
        desc.contract = _make_contract()
        desc.derivativeSecTypes = ["OPT", "FUT"]

        cached = CachedContract.from_contract_description(desc)

        assert cached.has_full_details is False
        assert cached.contract.symbol == "AAPL"
        assert cached.derivativeSecTypes == ["OPT", "FUT"]

    def test_partial_entry_has_default_details_fields(self) -> None:
        """Test from_contract_description leaves ContractDetails fields at defaults."""
        desc = ContractDescription()
        desc.contract = _make_contract()

        cached = CachedContract.from_contract_description(desc)

        # Partial entries only have contract and derivativeSecTypes
        # Other ContractDetails fields are not present
        assert cached.has_full_details is False
        assert cached.derivativeSecTypes == []


class TestCachedContractToContractDetails:
    """Test CachedContract.to_contract_details conversion method."""

    def test_exports_as_contract_details(self) -> None:
        """Test to_contract_details creates ContractDetails instance."""
        details = ContractDetails()
        details.contract = _make_contract()
        details.longName = "Apple Inc"

        cached = CachedContract.from_contract_details(details)
        exported = cached.to_contract_details()

        assert isinstance(exported, ContractDetails)
        assert exported.contract.symbol == "AAPL"
        assert exported.longName == "Apple Inc"

    def test_excludes_cached_contract_specific_fields(self) -> None:
        """Test to_contract_details excludes derivativeSecTypes and has_full_details."""
        details = ContractDetails()
        details.contract = _make_contract()

        cached = CachedContract.from_contract_details(details)
        cached.derivativeSecTypes = ["OPT"]
        exported = cached.to_contract_details()

        assert (
            not hasattr(exported, "derivativeSecTypes")
            or getattr(exported, "derivativeSecTypes", []) == []
        )
        assert not hasattr(exported, "has_full_details")


class TestCachedContractToContractDescription:
    """Test CachedContract.to_contract_description conversion method."""

    def test_exports_as_contract_description(self) -> None:
        """Test to_contract_description creates ContractDescription instance."""
        desc = ContractDescription()
        desc.contract = _make_contract()
        desc.derivativeSecTypes = ["OPT", "FUT"]

        cached = CachedContract.from_contract_description(desc)
        exported = cached.to_contract_description()

        assert isinstance(exported, ContractDescription)
        assert exported.contract.symbol == "AAPL"
        assert exported.derivativeSecTypes == ["OPT", "FUT"]


class TestCachedContractUpdateFromDetails:
    """Test CachedContract.update_from_details method."""

    def test_upgrades_partial_to_full_details(self) -> None:
        """Test update_from_details upgrades partial cache entry to full."""
        # Start with partial entry from description
        desc = ContractDescription()
        desc.contract = _make_contract()
        desc.derivativeSecTypes = ["OPT"]

        cached = CachedContract.from_contract_description(desc)
        # Partial entries have has_full_details=False and no longName attribute
        initial_has_details = cached.has_full_details
        assert initial_has_details is False

        # Update with full details
        details = ContractDetails()
        details.contract = _make_contract()
        details.longName = "Apple Inc"
        details.minTick = 0.01

        cached.update_from_details(details)

        # After update, the cached entry should have full details
        final_has_details = cached.has_full_details
        assert final_has_details is True
        assert cached.longName == "Apple Inc"
        assert cached.minTick == 0.01

    def test_preserves_derivative_sec_types(self) -> None:
        """Test update_from_details preserves derivativeSecTypes from description."""
        desc = ContractDescription()
        desc.contract = _make_contract()
        desc.derivativeSecTypes = ["OPT", "FUT"]

        cached = CachedContract.from_contract_description(desc)

        details = ContractDetails()
        details.contract = _make_contract()
        details.longName = "Apple Inc"

        cached.update_from_details(details)

        # derivativeSecTypes should be preserved
        assert cached.derivativeSecTypes == ["OPT", "FUT"]


class TestCachedContractMatches:
    """Test CachedContract.matches method."""

    def test_matches_exact_ticker(self) -> None:
        """Test matches returns True for exact ticker match."""
        details = ContractDetails()
        details.contract = _make_contract()

        cached = CachedContract.from_contract_details(details)

        assert cached.matches("AAPL:NASDAQ:STK") is True

    def test_matches_ticker_prefix(self) -> None:
        """Test matches returns True when ticker starts with cached ticker."""
        details = ContractDetails()
        details.contract = _make_contract()

        cached = CachedContract.from_contract_details(details)

        # With bar size suffix
        assert cached.matches("AAPL:NASDAQ:STK@5 mins") is True

    def test_no_match_different_symbol(self) -> None:
        """Test matches returns False for different symbol."""
        details = ContractDetails()
        details.contract = _make_contract()

        cached = CachedContract.from_contract_details(details)

        assert cached.matches("MSFT:NASDAQ:STK") is False

    def test_no_match_different_exchange(self) -> None:
        """Test matches returns False for different exchange."""
        details = ContractDetails()
        details.contract = _make_contract()

        cached = CachedContract.from_contract_details(details)

        assert cached.matches("AAPL:NYSE:STK") is False
