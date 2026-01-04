"""Tests for TWS domain mappers.

Covers core mapping functionality for:
- Contract descriptions → search results
- Contract details → symbol info
- Bars, ticks, quotes
- Orders (PreOrder → TWS, TrackedOrder → PlacedOrder)
- Positions and account data
"""

from decimal import Decimal

import pytest
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.order import Order as TWSOrder
from ibapi.order_state import OrderState

from trading_api.models.broker import (
    OrderStatus,
    OrderType,
    ParentType,
    PreOrder,
    Side,
    StopType,
)
from trading_api.models.exceptions import ProviderException
from trading_api.models.market import QuoteValues
from trading_api.providers.tws.order_tracker import OrderFill, TrackedOrder
from trading_api.providers.tws.tws_mappers import (
    SEC_TYPE_MAP,
    BracketContext,
    contract_description_to_search_result,
    contract_details_to_symbol_info,
    order_state_to_preview_result,
    parse_tws_bar_date,
    preorder_to_tws,
    tracked_order_to_placed_order,
    tws_account_summary_to_account_info,
    tws_account_summary_to_equity,
    tws_bar_to_domain_bar,
    tws_position_to_domain,
    tws_ticks_to_quote_data,
    tws_to_domain_status,
)

# =============================================================================
# Contract Mappers
# =============================================================================


class TestContractDescriptionMapper:
    """Test contract_description_to_search_result mapper."""

    def test_stock_mapping_and_ticker_format(self) -> None:
        """Test stock mapping with correct ticker format (SYMBOL:EXCHANGE:SECTYPE)."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.description = "Apple Inc"

        desc = ContractDescription()
        desc.contract = contract

        result = contract_description_to_search_result(desc)

        assert result.symbol == "AAPL"
        assert result.description == "Apple Inc"
        assert result.exchange == "NASDAQ"
        assert result.ticker == "AAPL:NASDAQ:STK"
        assert result.type == "stock"

    def test_fallback_to_exchange_when_primaryexchange_empty(self) -> None:
        """Test fallback to exchange when primaryExchange is empty."""
        contract = Contract()
        contract.symbol = "EUR"
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"
        contract.primaryExchange = ""

        desc = ContractDescription()
        desc.contract = contract

        result = contract_description_to_search_result(desc)

        assert result.exchange == "IDEALPRO"
        assert result.ticker == "EUR:IDEALPRO:CASH"
        assert result.type == "forex"

    def test_all_sec_type_mappings(self) -> None:
        """Test all secType mappings produce correct types."""
        for tws_type, expected_type in SEC_TYPE_MAP.items():
            contract = Contract()
            contract.symbol = "TEST"
            contract.secType = tws_type
            contract.exchange = "TEST"

            desc = ContractDescription()
            desc.contract = contract

            result = contract_description_to_search_result(desc)
            assert result.type == expected_type, f"Failed for {tws_type}"


class TestContractDetailsMapper:
    """Test contract_details_to_symbol_info mapper."""

    def test_stock_mapping_with_pricescale(self) -> None:
        """Test stock details mapping with pricescale calculation."""
        contract = Contract()
        contract.symbol = "MSFT"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        details = ContractDetails()
        details.contract = contract
        details.longName = "Microsoft Corporation"
        details.minTick = 0.01

        result = contract_details_to_symbol_info(details)

        assert result.name == "MSFT"
        assert result.description == "Microsoft Corporation"
        assert result.type == "stock"
        assert result.ticker == "MSFT:NASDAQ:STK"
        assert result.pricescale == 100  # 1/0.01

    @pytest.mark.parametrize(
        "min_tick,expected_pricescale",
        [(0.01, 100), (0.001, 1000), (0.0001, 10000), (0.05, 20), (1.0, 1), (0, 100)],
    )
    def test_pricescale_calculations(
        self, min_tick: float, expected_pricescale: int
    ) -> None:
        """Test pricescale correctly calculated from minTick."""
        contract = Contract()
        contract.symbol = "TEST"
        contract.secType = "STK"
        contract.exchange = "TEST"

        details = ContractDetails()
        details.contract = contract
        details.minTick = min_tick

        result = contract_details_to_symbol_info(details)
        assert result.pricescale == expected_pricescale


# =============================================================================
# Bar/Quote Mappers
# =============================================================================


class TestTwsBarMapper:
    """Test tws_bar_to_domain_bar mapper."""

    def test_bar_with_timezone_date(self) -> None:
        """Test bar parsing with timezone-aware date format."""
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
        assert result.time > 0

    def test_bar_with_epoch_date(self) -> None:
        """Test bar parsing with epoch timestamp format."""
        tws_bar = BarData()
        tws_bar.date = "1702656000"
        tws_bar.open = 200.0
        tws_bar.high = 210.0
        tws_bar.low = 195.0
        tws_bar.close = 205.0
        tws_bar.volume = Decimal("2500")

        result = tws_bar_to_domain_bar(tws_bar)

        assert result.time == 1702656000000  # Milliseconds


class TestTwsTicksToQuoteData:
    """Test tws_ticks_to_quote_data mapper."""

    def test_complete_quote_mapping(self) -> None:
        """Test mapping complete tick data to QuoteData."""
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
        assert result.n == "AAPL:NASDAQ:STK-12345"
        assert isinstance(result.v, QuoteValues)
        assert result.v.bid == 150.25
        assert result.v.ask == 150.30
        assert result.v.lp == 150.28
        assert result.v.spread == pytest.approx(0.05)
        assert result.v.volume == 1000000

    def test_rt_volume_fallback_for_last_price(self) -> None:
        """Test rt_trd_volume provides fallback when 'last' tick missing."""
        rt_data = {
            "business_key": "datafeed:Quote:SMART:GOOGL:NASDAQ:STK",
            "bid": 320.55,
            "ask": 320.78,
            "rt_trd_volume": "320.64;1.0;1765200318856;4027.0;320.359;true",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)

        assert result.v.lp == 320.64
        assert result.v.volume == 4027

    def test_missing_values_default_to_zero(self) -> None:
        """Test missing tick values default to zero."""
        rt_data: dict[str, object] = {
            "business_key": "datafeed:Quote:SMART:TEST:SMART:STK-0",
        }

        result = tws_ticks_to_quote_data(rt_data)

        assert isinstance(result.v, QuoteValues)

        assert result.v.lp == 0.0
        assert result.v.bid == 0.0
        assert result.v.volume == 0


class TestParseTwsBarDate:
    """Test parse_tws_bar_date function for various TWS date formats."""

    @pytest.mark.parametrize(
        "date_str",
        [
            "20251229 08:30:00 US/Central",
            "20251229  08:30:00 US/Eastern",
            "20251229 08:30:00 UTC",
            "20251229",
            "1735500600",
        ],
    )
    def test_valid_date_formats(self, date_str: str) -> None:
        """Test parsing various valid TWS date formats."""
        result = parse_tws_bar_date(date_str)
        assert result > 0
        assert isinstance(result, int)

    def test_invalid_format_raises_exception(self) -> None:
        """Test that invalid format raises ProviderException."""
        with pytest.raises(ProviderException) as exc_info:
            parse_tws_bar_date("invalid-date-format")
        assert "PROVIDER_TWS_INVALID_DATE_FORMAT" in str(exc_info.value)


# =============================================================================
# Order Mappers
# =============================================================================


class TestPreorderToTws:
    """Test preorder_to_tws mapper."""

    def test_market_order(self) -> None:
        """Test converting a market buy order."""
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
        assert stop_loss is None
        assert take_profit is None

    def test_limit_order_with_price(self) -> None:
        """Test converting a limit sell order."""
        preorder = PreOrder(
            symbol="MSFT:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.SELL,
            qty=50,
            limitPrice=350.50,
        )

        parent, _, _ = preorder_to_tws(preorder, "", 1)

        assert parent.action == "SELL"
        assert parent.orderType == "LMT"
        assert parent.lmtPrice == 350.50

    def test_stop_limit_order(self) -> None:
        """Test converting a stop-limit order."""
        preorder = PreOrder(
            symbol="TSLA:NASDAQ:STK",
            type=OrderType.STOP_LIMIT,
            side=Side.BUY,
            qty=10,
            limitPrice=250.00,
            stopPrice=245.00,
        )

        parent, _, _ = preorder_to_tws(preorder, "", 1)

        assert parent.orderType == "STP LMT"
        assert parent.lmtPrice == 250.00
        assert parent.auxPrice == 245.00

    def test_bracket_order_with_stop_and_take_profit(self) -> None:
        """Test converting order with both stop loss and take profit."""
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
        assert stop_loss.orderType == "STP"
        assert stop_loss.auxPrice == 145.00
        assert stop_loss.action == "SELL"
        assert take_profit is not None
        assert take_profit.orderType == "LMT"
        assert take_profit.lmtPrice == 160.00
        assert take_profit.action == "SELL"

    def test_trailing_stop_orde(self) -> None:
        """Test converting order with trailing stop."""
        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            trailingStopPips=5.00,
            stopType=StopType.TRAILING_STOP,
        )

        parent, stop_loss, _ = preorder_to_tws(preorder, "", 1)

        assert stop_loss is not None
        assert stop_loss.orderType == "TRAIL"
        assert stop_loss.auxPrice == 5.00

    def test_guaranteed_stop_raises_exception(self) -> None:
        """Test that guaranteed stop raises ProviderException."""
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


class TestTrackedOrderToPlacedOrder:
    """Test tracked_order_to_placed_order mapper."""

    def _make_tracked_order(
        self,
        order_id: int = 1,
        symbol: str = "AAPL",
        action: str = "BUY",
        qty: Decimal = Decimal("100"),
        order_type: str = "MKT",
        status: str = "Submitted",
        lmt_price: float = 0.0,
        aux_price: float = 0.0,
        filled_qty: Decimal = Decimal("0"),
        parent_id: int = 0,
    ) -> TrackedOrder:
        """Helper to create TrackedOrder for testing."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        order = TWSOrder()
        order.action = action
        order.totalQuantity = qty
        order.orderType = order_type
        order.lmtPrice = lmt_price
        order.auxPrice = aux_price
        order.filledQuantity = filled_qty
        order.parentId = parent_id

        order_state = OrderState()
        order_state.status = status

        return TrackedOrder(
            orderId=order_id,
            contract=contract,
            order=order,
            orderState=order_state,
        )

    def test_working_market_order(self) -> None:
        """Test mapping a working market order."""
        tracked = self._make_tracked_order()

        result = tracked_order_to_placed_order(tracked)

        assert result.id == "1"
        assert result.symbol == "AAPL:NASDAQ:STK"
        assert result.type == OrderType.MARKET
        assert result.side == Side.BUY
        assert result.qty == 100
        assert result.status == OrderStatus.WORKING

    def test_filled_limit_order(self) -> None:
        """Test mapping a filled limit order with fill info."""
        tracked = self._make_tracked_order(
            order_type="LMT",
            lmt_price=350.00,
            status="Filled",
            filled_qty=Decimal("50"),
        )
        fill = OrderFill(
            orderId=1,
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
        tracked.fills = [fill]

        result = tracked_order_to_placed_order(tracked)

        assert result.type == OrderType.LIMIT
        assert result.status == OrderStatus.FILLED
        assert result.limitPrice == 350.00
        assert result.filledQty == 50.0
        assert result.avgPrice == 350.25

    def test_cancelled_order(self) -> None:
        """Test mapping a cancelled order."""
        tracked = self._make_tracked_order(status="Cancelled")

        result = tracked_order_to_placed_order(tracked)

        assert result.status == OrderStatus.CANCELED

    def test_bracket_context_preserved(self) -> None:
        """Test that BracketContext fields are preserved."""
        tracked = self._make_tracked_order(order_type="LMT", lmt_price=150.00)
        bracket_context = BracketContext(
            take_profit=160.00,
            stop_loss=145.00,
            trailing_stop_pips=5.00,
            stop_type=int(StopType.TRAILING_STOP),
        )

        result = tracked_order_to_placed_order(tracked, bracket_context)

        assert result.takeProfit == 160.00
        assert result.stopLoss == 145.00
        assert result.trailingStopPips == 5.00
        assert result.stopType == StopType.TRAILING_STOP

    def test_child_order_has_parent_id(self) -> None:
        """Test that child bracket orders have parentId set."""
        tracked = self._make_tracked_order(
            order_id=101,
            action="SELL",
            order_type="LMT",
            lmt_price=160.00,
            parent_id=100,
        )

        result = tracked_order_to_placed_order(tracked)

        assert result.id == "101"
        assert result.parentId == "100"
        assert result.parentType == ParentType.ORDER


# =============================================================================
# Position/Account Mappers
# =============================================================================


class TestTwsPositionToDomain:
    """Test tws_position_to_domain mapper."""

    def test_long_position(self) -> None:
        """Test mapping a long position."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        position_data = {
            "account": "DU123456",
            "contract": contract,
            "position": Decimal("100"),
            "avgCost": 150.50,
        }

        result = tws_position_to_domain(position_data)

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
            "position": Decimal("-50"),
            "avgCost": 250.75,
        }

        result = tws_position_to_domain(position_data)

        assert result.qty == 50.0
        assert result.side == Side.SELL


class TestTwsAccountSummaryToEquity:
    """Test tws_account_summary_to_equity mapper."""

    def test_complete_summary(self) -> None:
        """Test mapping complete account summary data."""
        summary_data = {
            "NetLiquidation": {"value": "100000.00"},
            "TotalCashValue": {"value": "75000.50"},
            "UnrealizedPnL": {"value": "5000.25"},
            "RealizedPnL": {"value": "2500.00"},
        }

        result = tws_account_summary_to_equity(summary_data)

        assert result.equity == 100000.00
        assert result.balance == 75000.50
        assert result.unrealizedPL == 5000.25
        assert result.realizedPL == 2500.00

    def test_missing_tags_default_to_zero(self) -> None:
        """Test missing tags default to 0."""
        summary_data = {"NetLiquidation": {"value": "50000.00"}}

        result = tws_account_summary_to_equity(summary_data)

        assert result.equity == 50000.00
        assert result.balance == 0.0


class TestTwsAccountSummaryToAccountInfo:
    """Test tws_account_summary_to_account_info mapper."""

    def test_account_info_extraction(self) -> None:
        """Test account ID and name extraction."""
        summary_data = {
            "DU123456": {
                "NetLiquidation": {"account": "DU123456", "value": "100000.00"},
            },
        }

        result = tws_account_summary_to_account_info(summary_data, "DU123456")

        assert result.id == "DU123456"
        assert result.name == "IBKR DU123456"


# =============================================================================
# Order Preview Mapper
# =============================================================================


class TestOrderStateToPreviewResult:
    """Test order_state_to_preview_result mapper."""

    def _make_order_state(
        self,
        init_margin_change: str = "5000.00",
        commission: float = 1.0,
        warning_text: str = "",
        reject_reason: str = "",
    ) -> OrderState:
        """Create mock OrderState for testing."""
        order_state = OrderState()
        order_state.initMarginChange = init_margin_change
        order_state.maintMarginChange = "2500.00"
        order_state.equityWithLoanChange = "-5000.00"
        order_state.initMarginAfter = "10000.00"
        order_state.commissionAndFees = commission
        order_state.minCommissionAndFees = commission
        order_state.maxCommissionAndFees = commission
        order_state.marginCurrency = "USD"
        order_state.commissionAndFeesCurrency = "USD"
        order_state.warningText = warning_text
        order_state.rejectReason = reject_reason
        return order_state

    def test_preview_result_structure(self) -> None:
        """Test OrderPreviewResult has required sections."""
        order_state = self._make_order_state()
        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
        )

        result = order_state_to_preview_result(order_state, preorder, "test-123")

        section_headers = [s.header for s in result.sections]
        assert "Order Details" in section_headers
        assert "Margin Requirements" in section_headers
        assert "Commission & Fees" in section_headers
        assert result.confirmId == "test-123"

    def test_bracket_section_included(self) -> None:
        """Test Risk Management section included for bracket orders."""
        order_state = self._make_order_state()
        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=100,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        result = order_state_to_preview_result(order_state, preorder, "test-123")

        section_headers = [s.header for s in result.sections]
        assert "Risk Management" in section_headers

    def test_warnings_from_tws(self) -> None:
        """Test TWS warnings are included."""
        order_state = self._make_order_state(warning_text="Order requires margin")
        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK", type=OrderType.MARKET, side=Side.BUY, qty=100
        )

        result = order_state_to_preview_result(order_state, preorder, "test-123")

        assert result.warnings is not None
        assert any("Order requires margin" in w for w in result.warnings)

    def test_errors_from_tws(self) -> None:
        """Test TWS reject reasons are included as errors."""
        order_state = self._make_order_state(reject_reason="Insufficient funds")
        preorder = PreOrder(
            symbol="AAPL:NASDAQ:STK", type=OrderType.MARKET, side=Side.BUY, qty=100
        )

        result = order_state_to_preview_result(order_state, preorder, "test-123")

        assert result.errors is not None
        assert any("Insufficient funds" in e for e in result.errors)


# =============================================================================
# TWS Status Mapping
# =============================================================================


class TestTwsToDomainStatus:
    """Test tws_to_domain_status helper function.

    Covers:
    - Direct mapping for confirmed statuses
    - History-based resolution for cancel transitions
    - Fallback to PLACING for new orders
    """

    def _make_tracked_order(
        self,
        status: str = "Submitted",
        fills: list[OrderFill] | None = None,
    ) -> TrackedOrder:
        """Helper to create TrackedOrder with specific status and fills."""
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"

        order = TWSOrder()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "MKT"

        order_state = OrderState()
        order_state.status = status

        tracked = TrackedOrder(
            orderId=1,
            contract=contract,
            order=order,
            orderState=order_state,
        )
        if fills:
            tracked.fills = fills
        return tracked

    def _make_fill(self, status: str) -> OrderFill:
        """Helper to create OrderFill with specific status."""
        return OrderFill(
            orderId=1,
            status=status,
            filled=Decimal("0"),
            remaining=Decimal("100"),
            avgFillPrice=0.0,
            permId=12345,
            parentId=0,
            lastFillPrice=0.0,
            clientId=1,
            whyHeld="",
            mktCapPrice=0.0,
            timestamp=1234567890,
        )

    # --- Direct mapping tests ---

    def test_submitted_maps_to_working(self) -> None:
        """Submitted (active at exchange) → WORKING."""
        tracked = self._make_tracked_order(status="Submitted")
        assert tws_to_domain_status(tracked) == OrderStatus.WORKING

    def test_presubmitted_maps_to_inactive(self) -> None:
        """PreSubmitted (simulated order held by IB) → INACTIVE."""
        tracked = self._make_tracked_order(status="PreSubmitted")
        assert tws_to_domain_status(tracked) == OrderStatus.INACTIVE

    def test_filled_maps_to_filled(self) -> None:
        """Filled → FILLED."""
        tracked = self._make_tracked_order(status="Filled")
        assert tws_to_domain_status(tracked) == OrderStatus.FILLED

    def test_cancelled_maps_to_canceled(self) -> None:
        """Cancelled (confirmed) → CANCELED."""
        tracked = self._make_tracked_order(status="Cancelled")
        assert tws_to_domain_status(tracked) == OrderStatus.CANCELED

    def test_inactive_maps_to_inactive(self) -> None:
        """Inactive (error/held) → INACTIVE."""
        tracked = self._make_tracked_order(status="Inactive")
        assert tws_to_domain_status(tracked) == OrderStatus.INACTIVE

    # --- History-based resolution tests ---

    def test_pending_cancel_preserves_working_status(self) -> None:
        """PendingCancel with Submitted history → WORKING (not CANCELED).

        Critical for halt scenarios: order might still fill after cancel request.
        """
        fills = [self._make_fill("Submitted")]
        tracked = self._make_tracked_order(status="PendingCancel", fills=fills)

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.WORKING

    def test_api_cancelled_preserves_working_status(self) -> None:
        """ApiCancelled with Submitted history → WORKING.

        ApiCancelled means cancelled via API before ack - could still fill.
        """
        fills = [self._make_fill("Submitted")]
        tracked = self._make_tracked_order(status="ApiCancelled", fills=fills)

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.WORKING

    def test_pending_cancel_preserves_presubmitted_status(self) -> None:
        """PendingCancel with PreSubmitted history → INACTIVE."""
        fills = [self._make_fill("PreSubmitted")]
        tracked = self._make_tracked_order(status="PendingCancel", fills=fills)

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.INACTIVE

    def test_pending_submit_with_history_uses_last_confirmed(self) -> None:
        """PendingSubmit with prior Submitted history → WORKING."""
        fills = [self._make_fill("Submitted")]
        tracked = self._make_tracked_order(status="PendingSubmit", fills=fills)

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.WORKING

    def test_api_pending_with_history_uses_last_confirmed(self) -> None:
        """ApiPending with prior Submitted history → WORKING."""
        fills = [self._make_fill("Submitted")]
        tracked = self._make_tracked_order(status="ApiPending", fills=fills)

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.WORKING

    def test_history_resolution_walks_backwards(self) -> None:
        """History resolution finds last confirmed status (walks backwards)."""
        fills = [
            self._make_fill("PreSubmitted"),  # First
            self._make_fill("Submitted"),  # Last confirmed
        ]
        tracked = self._make_tracked_order(status="PendingCancel", fills=fills)

        result = tws_to_domain_status(tracked)

        # Should use Submitted (last in list), not PreSubmitted
        assert result == OrderStatus.WORKING

    def test_history_skips_transitional_statuses(self) -> None:
        """History resolution skips transitional statuses in history."""
        fills = [
            self._make_fill("Submitted"),
            self._make_fill("PendingCancel"),  # Transitional - skip
        ]
        tracked = self._make_tracked_order(status="ApiCancelled", fills=fills)

        result = tws_to_domain_status(tracked)

        # Should find Submitted, skipping PendingCancel
        assert result == OrderStatus.WORKING

    # --- Fallback tests ---

    def test_pending_cancel_no_history_falls_back_to_placing(self) -> None:
        """PendingCancel with no history → PLACING."""
        tracked = self._make_tracked_order(status="PendingCancel", fills=[])

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.PLACING

    def test_api_pending_no_history_falls_back_to_placing(self) -> None:
        """ApiPending (new order) with no history → PLACING."""
        tracked = self._make_tracked_order(status="ApiPending", fills=[])

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.PLACING

    def test_pending_submit_no_history_falls_back_to_placing(self) -> None:
        """PendingSubmit (new order) with no history → PLACING."""
        tracked = self._make_tracked_order(status="PendingSubmit", fills=[])

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.PLACING

    def test_unknown_status_falls_back_to_placing(self) -> None:
        """Unknown status with no history → PLACING."""
        tracked = self._make_tracked_order(status="UnknownTwsStatus", fills=[])

        result = tws_to_domain_status(tracked)

        assert result == OrderStatus.PLACING
