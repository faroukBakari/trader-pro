"""Unit tests for AccountTracker.

Tests tag name mapping (PascalCase → snake_case) and P&L update functionality.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trading_api.providers.tws.account_tracker import (
    TWS_TAG_TO_FIELD,
    AccountTracker,
    TrackedAccount,
)
from trading_api.providers.tws.wiring_interfaces import IbSocketWiringInterface


@pytest.fixture
def mock_ibsocket() -> IbSocketWiringInterface:
    """Provide a mock IbSocketWiringInterface for AccountTracker initialization.

    The mock implements the wiring interface methods needed by AccountTracker:
    - wire_account_tracker: stores the tracker reference
    - next_req_id: returns incrementing request IDs
    - send_message: no-op (captures outgoing TWS messages)
    """
    mock = MagicMock(spec=IbSocketWiringInterface)

    # Track request ID counter for unique IDs
    req_id_counter = {"value": 1}

    def get_next_req_id() -> int:
        """Return incrementing request IDs."""
        req_id = req_id_counter["value"]
        req_id_counter["value"] += 1
        return req_id

    # Configure mock properties and methods
    mock.wire_account_tracker = MagicMock()
    mock.send_message = MagicMock()
    # Use PropertyMock for next_req_id property
    type(mock).next_req_id = property(lambda self: get_next_req_id())

    return mock


@pytest.fixture
def mock_account_callbacks(
    mock_ibsocket: IbSocketWiringInterface,
) -> IbSocketWiringInterface:
    """Alias for backward compatibility - returns the mock IbSocketWiringInterface."""
    return mock_ibsocket


class TestTWSTagToFieldMapping:
    """Test TWS_TAG_TO_FIELD mapping dict."""

    def test_core_equity_tags_mapped(self) -> None:
        """Verify core equity tags are mapped correctly."""
        assert TWS_TAG_TO_FIELD["NetLiquidation"] == "net_liquidation"
        assert TWS_TAG_TO_FIELD["TotalCashValue"] == "total_cash_value"
        assert TWS_TAG_TO_FIELD["EquityWithLoanValue"] == "equity_with_loan_value"
        assert TWS_TAG_TO_FIELD["GrossPositionValue"] == "gross_position_value"
        assert TWS_TAG_TO_FIELD["BuyingPower"] == "buying_power"

    def test_margin_tags_mapped(self) -> None:
        """Verify margin/risk tags are mapped correctly."""
        assert TWS_TAG_TO_FIELD["AvailableFunds"] == "available_funds"
        assert TWS_TAG_TO_FIELD["ExcessLiquidity"] == "excess_liquidity"
        assert TWS_TAG_TO_FIELD["Cushion"] == "cushion"
        assert TWS_TAG_TO_FIELD["InitMarginReq"] == "init_margin_req"
        assert TWS_TAG_TO_FIELD["MaintMarginReq"] == "maint_margin_req"
        assert TWS_TAG_TO_FIELD["Leverage"] == "leverage"

    def test_pnl_tags_mapped(self) -> None:
        """Verify P&L tags are mapped correctly."""
        assert TWS_TAG_TO_FIELD["DailyPnL"] == "daily_pnl"
        assert TWS_TAG_TO_FIELD["UnrealizedPnL"] == "unrealized_pnl"
        assert TWS_TAG_TO_FIELD["RealizedPnL"] == "realized_pnl"

    def test_account_info_tags_mapped(self) -> None:
        """Verify account info tags are mapped correctly."""
        assert TWS_TAG_TO_FIELD["Currency"] == "currency"
        assert TWS_TAG_TO_FIELD["AccountType"] == "account_type"
        assert TWS_TAG_TO_FIELD["DayTradesRemaining"] == "day_trades_remaining"
        assert TWS_TAG_TO_FIELD["AccountReady"] == "account_ready"


class TestAccountTrackerUpdateAccount:
    """Test AccountTracker.update_account() method."""

    def test_update_account_creates_tracked_account(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify update_account creates TrackedAccount if not exists."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "NetLiquidation", "100000.50", "USD")
        assert "DU123" in tracker._accounts
        assert tracker._accounts["DU123"].net_liquidation == Decimal("100000.50")

    def test_update_account_updates_existing(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify update_account updates existing TrackedAccount."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.upsert_account("DU123")
        tracker.update_account("DU123", "NetLiquidation", "100000.50", "USD")
        assert tracker._accounts["DU123"].net_liquidation == Decimal("100000.50")

    def test_update_account_ignores_unknown_tags(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify unknown tags are silently ignored (no crash)."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.upsert_account("DU123")
        # Unknown tag should not raise
        tracker.update_account("DU123", "UnknownTag", "12345", "USD")
        # Account should still exist but no field should be modified
        assert "DU123" in tracker._accounts

    def test_update_account_sets_currency(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify currency is set from callback."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "NetLiquidation", "100000", "EUR")
        assert tracker._accounts["DU123"].currency == "EUR"

    def test_update_account_currency_only_if_provided(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify currency is not overwritten with empty string."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "NetLiquidation", "100000", "EUR")
        tracker.update_account("DU123", "AccountReady", "true", "")
        # Currency should still be EUR (not overwritten)
        assert tracker._accounts["DU123"].currency == "EUR"

    def test_update_account_parses_decimal_values(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify numeric values are parsed as Decimal."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "NetLiquidation", "123456.789", "USD")
        assert tracker._accounts["DU123"].net_liquidation == Decimal("123456.789")

    def test_update_account_parses_boolean_account_ready(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify AccountReady is parsed as boolean."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "AccountReady", "true", "")
        assert tracker._accounts["DU123"].account_ready is True

        tracker.update_account("DU123", "AccountReady", "false", "")
        assert tracker._accounts["DU123"].account_ready is False

    def test_update_account_parses_integer_day_trades(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify DayTradesRemaining is parsed as integer."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "DayTradesRemaining", "3", "")
        assert tracker._accounts["DU123"].day_trades_remaining == 3

        # -1 means unlimited
        tracker.update_account("DU123", "DayTradesRemaining", "-1", "")
        assert tracker._accounts["DU123"].day_trades_remaining == -1

    def test_update_account_string_values(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify string values are stored as strings."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.update_account("DU123", "AccountType", "INDIVIDUAL", "")
        assert tracker._accounts["DU123"].account_type == "INDIVIDUAL"


class TestAccountTrackerUpdatePnl:
    """Test AccountTracker.update_pnl() method."""

    def test_update_pnl_updates_account(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify update_pnl updates P&L fields on TrackedAccount."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.upsert_account("DU123")
        # upsert_account auto-assigns pnl_req_id via reqPnL (returns 1 for first account)
        req_id = tracker._accounts["DU123"].pnl_req_id
        assert req_id is not None

        tracker.update_pnl(req_id, 500.25, 1200.50, -300.00)

        assert tracker._accounts["DU123"].daily_pnl == Decimal("500.25")
        assert tracker._accounts["DU123"].unrealized_pnl == Decimal("1200.50")
        assert tracker._accounts["DU123"].realized_pnl == Decimal("-300.00")

    def test_update_pnl_uses_pnl_req_id(
        self, mock_ibsocket: IbSocketWiringInterface
    ) -> None:
        """Verify update_pnl matches account by pnl_req_id."""
        tracker = AccountTracker(mock_ibsocket)
        tracker.upsert_account("DU123")  # Gets req_id=1
        tracker.upsert_account("DU456")  # Gets req_id=2

        # Get the auto-assigned request IDs
        req_id_456 = tracker._accounts["DU456"].pnl_req_id
        assert req_id_456 is not None

        # Update using DU456's request ID
        tracker.update_pnl(req_id_456, 100.0, 200.0, 50.0)

        # DU456 should be updated
        assert tracker._accounts["DU456"].daily_pnl == Decimal("100.0")
        # DU123 should NOT be updated
        assert tracker._accounts["DU123"].daily_pnl is None


class TestTrackedAccountEquityData:
    """Test TrackedAccount.equity_data() conversion."""

    def test_equity_data_maps_fields(self) -> None:
        """Verify equity_data() converts to EquityData correctly."""
        tracked = TrackedAccount(
            id="DU123",
            net_liquidation=Decimal("100000"),
            total_cash_value=Decimal("50000"),
            unrealized_pnl=Decimal("1200"),
            realized_pnl=Decimal("-300"),
        )
        equity = tracked.equity_data()

        assert equity.equity == 100000.0
        assert equity.balance == 50000.0
        assert equity.unrealizedPL == 1200.0
        assert equity.realizedPL == -300.0

    def test_equity_data_handles_none_values(self) -> None:
        """Verify equity_data() handles None fields with defaults."""
        tracked = TrackedAccount(id="DU123")
        equity = tracked.equity_data()

        assert equity.equity == 0.0
        assert equity.balance == 0.0
        assert equity.unrealizedPL == 0.0
        assert equity.realizedPL == 0.0


class TestTrackedAccountMetainfo:
    """Test TrackedAccount.metainfo() conversion."""

    def test_metainfo_maps_fields(self) -> None:
        """Verify metainfo() converts to AccountMetainfo correctly."""
        tracked = TrackedAccount(id="DU123", currency="EUR")
        meta = tracked.metainfo()

        assert meta.id == "DU123"
        assert meta.name == "DU123"
        assert meta.currency == "EUR"
        assert meta.currencySign == "€"

    def test_metainfo_defaults_to_usd(self) -> None:
        """Verify metainfo() defaults to USD if currency is None."""
        tracked = TrackedAccount(id="DU123")
        meta = tracked.metainfo()

        assert meta.currency == "USD"
        assert meta.currencySign == "$"
