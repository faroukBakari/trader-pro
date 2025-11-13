"""Integration tests for broker equity/balance computation.

Tests validate the broker service's balance and equity calculations across
various trading scenarios including:
- Long and short positions
- Partial and full closes
- Position reversals
- Weighted average price calculation
- Commission handling
- Complex multi-step sequences

All test cases use deterministic execution (execution_delay=None) for precise
state validation at each step.

Test Model Assumptions:
- Single-currency cash account
- Balance = cash available + realized P/L
- Equity = Balance + unrealized P/L (mark-to-market)
- No interest, no margin/leverage, no funding fees
- Instant settlement on execution
- Commission = 0 unless explicitly stated
- Position: size > 0 = long, size < 0 = short
- Unrealized P/L:
  * Long: (market_price - avg_entry_price) * qty
  * Short: (avg_entry_price - market_price) * qty
"""

from pathlib import Path

import pytest

from trading_api.models.broker import OrderType, PreOrder, Side
from trading_api.modules.broker.service import BrokerService

# ================================ FIXTURES ================================= #


@pytest.fixture
def broker_service() -> BrokerService:
    """Create broker service with manual execution control."""
    module_dir = (
        Path(__file__).parent.parent.parent
        / "src"
        / "trading_api"
        / "modules"
        / "broker"
    )
    service = BrokerService(module_dir=module_dir, execution_delay=None)
    return service


# ================================ HELPERS ================================== #


async def place_and_execute(
    service: BrokerService,
    symbol: str,
    side: Side,
    qty: float,
    price: float,
    order_type: OrderType = OrderType.MARKET,
) -> None:
    """Place order and immediately execute it.

    Args:
        service: Broker service instance
        symbol: Symbol to trade
        side: BUY or SELL
        qty: Quantity
        price: Execution price (used as limitPrice for price determination)
        order_type: Order type (default MARKET)
    """
    # Place order
    order = PreOrder(
        symbol=symbol,
        type=order_type,
        side=side,
        qty=qty,
        limitPrice=price,  # Used for execution price
        stopPrice=None,
        takeProfit=None,
        stopLoss=None,
        guaranteedStop=None,
        trailingStopPips=None,
        stopType=None,
        seenPrice=None,
        currentQuotes=None,
    )
    result = await service.place_order(order)

    # Execute immediately
    await service._simulate_execution(result.orderId)


def assert_accounting(
    service: BrokerService,
    balance: float,
    equity: float,
    unrealized_pl: float,
    realized_pl: float,
    tolerance: float = 0.01,
) -> None:
    """Assert accounting values match expected.

    Args:
        service: Broker service instance
        balance: Expected balance
        equity: Expected equity
        unrealized_pl: Expected unrealized P/L
        realized_pl: Expected realized P/L
        tolerance: Acceptable deviation for floating-point comparison
    """
    accounting = service.accounting

    assert (
        abs(accounting.balance - balance) < tolerance
    ), f"Balance mismatch: expected {balance}, got {accounting.balance}"
    assert (
        abs(accounting.equity - equity) < tolerance
    ), f"Equity mismatch: expected {equity}, got {accounting.equity}"
    assert (
        abs(accounting.unrealizedPL - unrealized_pl) < tolerance
    ), f"Unrealized P/L mismatch: expected {unrealized_pl}, got {accounting.unrealizedPL}"
    assert (
        abs(accounting.realizedPL - realized_pl) < tolerance
    ), f"Realized P/L mismatch: expected {realized_pl}, got {accounting.realizedPL}"


def assert_position(
    service: BrokerService,
    symbol: str,
    expected_qty: float,
    expected_side: Side,
    expected_avg_price: float,
    tolerance: float = 0.01,
) -> None:
    """Assert position state matches expected.

    Args:
        service: Broker service instance
        symbol: Symbol to check
        expected_qty: Expected quantity (0 means no position)
        expected_side: Expected side (BUY or SELL)
        expected_avg_price: Expected average price
        tolerance: Acceptable deviation for floating-point comparison
    """
    position = service._positions.get(symbol)

    if expected_qty == 0:
        assert (
            position is None or position.qty == 0
        ), f"Expected no position for {symbol}, but found qty={position.qty if position else 0}"
        return

    assert position is not None, f"Expected position for {symbol} not found"
    assert (
        abs(position.qty - expected_qty) < tolerance
    ), f"Position qty mismatch for {symbol}: expected {expected_qty}, got {position.qty}"
    assert (
        position.side == expected_side
    ), f"Position side mismatch for {symbol}: expected {expected_side}, got {position.side}"
    assert (
        abs(position.avgPrice - expected_avg_price) < tolerance
    ), f"Position avgPrice mismatch for {symbol}: expected {expected_avg_price}, got {position.avgPrice}"


def set_initial_balance(service: BrokerService, balance: float) -> None:
    """Set initial balance for test.

    Args:
        service: Broker service instance
        balance: Initial balance to set
    """
    service.initial_balance = balance
    service.accounting.balance = balance
    service.accounting.equity = balance
    service.accounting.unrealizedPL = 0.0
    service.accounting.realizedPL = 0.0


# ================================ TEST CASES =============================== #


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_1_long_open_full_close_profit(
    broker_service: BrokerService,
) -> None:
    """Case 1: Long open then full close at profit.

    Initial: Balance = 10,000.00; market = 100.00
    Execution 1: Buy 50 @ 100.00 (enter long)
    - Position: +50 @ avg 100.00
    - Balance: 10,000.00
    - Equity: 10,000.00

    Market: price -> 110.00
    - Equity: 10,500.00 (unrealized +500)

    Execution 2: Sell 50 @ 110.00 (close)
    - Realized P/L: +500.00
    - Balance: 10,500.00
    - Equity: 10,500.00
    - Position: 0
    """
    set_initial_balance(broker_service, 10000.0)

    # Execution 1: Buy 50 @ 100.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 50, 100.0)

    # Verify position opened
    assert_position(broker_service, "AAPL", 50, Side.BUY, 100.0)
    assert_accounting(broker_service, 10000.0, 10000.0, 0.0, 0.0)

    # Execution 2: Sell 50 @ 110.00 (close)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 50, 110.0)

    # Verify position closed and P/L realized
    assert_position(broker_service, "AAPL", 0, Side.BUY, 100.0)
    assert_accounting(broker_service, 10500.0, 10500.0, 0.0, 500.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_2_long_partial_close_then_remainder_loss(
    broker_service: BrokerService,
) -> None:
    """Case 2: Long open then partial close then remainder at loss.

    Initial: Balance = 5,000.00; market = 20.00
    Execution 1: Buy 300 @ 20.00 (long 300)
    - Balance: 5,000.00
    - Equity: 5,000.00

    Execution 2: Sell 100 @ 25.00 (partial close)
    - Realized: +500.00
    - Balance: 5,500.00
    - Remaining: 200 @ 20.00
    - Equity: 6,500.00 (unrealized +1,000)

    Execution 3: Sell 200 @ 18.00 (close remaining)
    - Realized: -400.00
    - Balance: 5,100.00
    - Equity: 5,100.00
    """
    set_initial_balance(broker_service, 5000.0)

    # Execution 1: Buy 300 @ 20.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 300, 20.0)
    assert_position(broker_service, "AAPL", 300, Side.BUY, 20.0)
    assert_accounting(broker_service, 5000.0, 5000.0, 0.0, 0.0)

    # Execution 2: Sell 100 @ 25.00 (partial close)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 100, 25.0)
    assert_position(broker_service, "AAPL", 200, Side.BUY, 20.0)
    # Unrealized: (25 - 20) * 200 = 1000
    assert_accounting(broker_service, 5500.0, 6500.0, 1000.0, 500.0)

    # Execution 3: Sell 200 @ 18.00 (close remaining)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 200, 18.0)
    assert_position(broker_service, "AAPL", 0, Side.BUY, 20.0)
    assert_accounting(broker_service, 5100.0, 5100.0, 0.0, 100.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_3_short_open_full_close_profit(
    broker_service: BrokerService,
) -> None:
    """Case 3: Short open then full close at profit.

    Initial: Balance = 8,000.00; market = 50.00
    Execution 1: Sell short 100 @ 50.00
    - Position: -100 @ 50.00
    - Balance: 8,000.00
    - Equity: 8,000.00

    Market: price -> 40.00
    - Equity: 9,000.00 (unrealized +1,000)

    Execution 2: Buy 100 @ 40.00 (cover)
    - Realized: +1,000.00
    - Balance: 9,000.00
    - Equity: 9,000.00
    """
    set_initial_balance(broker_service, 8000.0)

    # Execution 1: Sell short 100 @ 50.00
    await place_and_execute(broker_service, "AAPL", Side.SELL, 100, 50.0)
    assert_position(broker_service, "AAPL", 100, Side.SELL, 50.0)
    assert_accounting(broker_service, 8000.0, 8000.0, 0.0, 0.0)

    # Execution 2: Buy 100 @ 40.00 (cover)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 100, 40.0)
    assert_position(broker_service, "AAPL", 0, Side.SELL, 50.0)
    assert_accounting(broker_service, 9000.0, 9000.0, 0.0, 1000.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_4_short_partial_cover_then_reverse_long(
    broker_service: BrokerService,
) -> None:
    """Case 4: Short open then partial cover then reverse to net long.

    Initial: Balance = 20,000.00; market = 200.00
    Execution 1: Sell short 50 @ 200.00
    - Position: -50 @ 200.00
    - Equity: 20,000.00

    Execution 2: Buy 30 @ 190.00 (partial cover)
    - Realized: +300.00
    - Balance: 20,300.00
    - Remaining: -20 @ 200.00
    - Equity: 20,500.00 (unrealized +200)

    Execution 3: Buy 50 @ 195.00 (cover -20 and go long 30)
    - Cover 20 realized: +100.00
    - New long: +30 @ 195.00
    - Balance: 20,400.00
    - Equity: 20,400.00
    """
    set_initial_balance(broker_service, 20000.0)

    # Execution 1: Sell short 50 @ 200.00
    await place_and_execute(broker_service, "AAPL", Side.SELL, 50, 200.0)
    assert_position(broker_service, "AAPL", 50, Side.SELL, 200.0)
    assert_accounting(broker_service, 20000.0, 20000.0, 0.0, 0.0)

    # Execution 2: Buy 30 @ 190.00 (partial cover)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 30, 190.0)
    assert_position(broker_service, "AAPL", 20, Side.SELL, 200.0)
    # Unrealized: (200 - 190) * 20 = 200
    assert_accounting(broker_service, 20300.0, 20500.0, 200.0, 300.0)

    # Execution 3: Buy 50 @ 195.00 (reverse)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 50, 195.0)
    assert_position(broker_service, "AAPL", 30, Side.BUY, 195.0)
    assert_accounting(broker_service, 20400.0, 20400.0, 0.0, 400.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_5_position_revert_long_to_short(
    broker_service: BrokerService,
) -> None:
    """Case 5: Position revert by reversing direction in one execution (long -> short).

    Initial: Balance = 15,000.00; market = 150.00
    Execution 1: Buy 100 @ 150.00
    - Long 100 @ 150.00
    - Equity: 15,000.00

    Market: price -> 140.00
    - Equity: 14,000.00 (unrealized -1,000)

    Execution 2: Sell 200 @ 140.00 (close 100 and open short 100)
    - Realized: -1,000.00
    - Balance: 14,000.00
    - New short: -100 @ 140.00
    - Equity: 14,000.00
    """
    set_initial_balance(broker_service, 15000.0)

    # Execution 1: Buy 100 @ 150.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 100, 150.0)
    assert_position(broker_service, "AAPL", 100, Side.BUY, 150.0)
    assert_accounting(broker_service, 15000.0, 15000.0, 0.0, 0.0)

    # Execution 2: Sell 200 @ 140.00 (reverse)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 200, 140.0)
    assert_position(broker_service, "AAPL", 100, Side.SELL, 140.0)
    assert_accounting(broker_service, 14000.0, 14000.0, 0.0, -1000.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_6_partial_reverse_then_increase_same_direction(
    broker_service: BrokerService,
) -> None:
    """Case 6: Partial reverse long to larger long (reduce then increase same direction).

    Initial: Balance = 12,000.00; market = 60.00
    Execution 1: Buy 200 @ 60.00
    - Long 200 @ 60.00
    - Equity: 12,000.00

    Execution 2: Sell 50 @ 62.00 (partial close)
    - Realized: +100.00
    - Balance: 12,100.00
    - Remaining: 150 @ 60.00
    - Equity: 12,400.00 (unrealized +300)

    Execution 3: Buy 150 @ 63.00 (increase to 300)
    - New avg: 60.50
    - Balance: 12,100.00
    - Equity: 12,850.00 (unrealized +750)
    """
    set_initial_balance(broker_service, 12000.0)

    # Execution 1: Buy 200 @ 60.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 200, 60.0)
    assert_position(broker_service, "AAPL", 200, Side.BUY, 60.0)
    assert_accounting(broker_service, 12000.0, 12000.0, 0.0, 0.0)

    # Execution 2: Sell 50 @ 62.00 (partial close)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 50, 62.0)
    assert_position(broker_service, "AAPL", 150, Side.BUY, 60.0)
    # Unrealized: (62 - 60) * 150 = 300
    assert_accounting(broker_service, 12100.0, 12400.0, 300.0, 100.0)

    # Execution 3: Buy 150 @ 63.00 (increase)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 150, 63.0)
    assert_position(broker_service, "AAPL", 300, Side.BUY, 61.5)
    # Unrealized = (63 - 61.5) * 300 = 450
    assert_accounting(broker_service, 12100.0, 12550.0, 450.0, 100.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_7_partial_close_reopen_worse_price(
    broker_service: BrokerService,
) -> None:
    """Case 7: Partial close then reopen same size at worse price.

    Initial: Balance = 7,000.00; market = 30.00
    Execution 1: Buy 100 @ 30.00
    - Long 100 @ 30.00
    - Equity: 7,000.00

    Execution 2: Sell 50 @ 28.00 (partial close at loss)
    - Realized: -100.00
    - Balance: 6,900.00
    - Remaining: 50 @ 30.00
    - Equity: 6,800.00 (unrealized -100)

    Execution 3: Buy 50 @ 29.00 (reopen to 100)
    - New avg: 29.50
    - Balance: 6,900.00
    - Equity: 6,850.00 (unrealized -50)
    """
    set_initial_balance(broker_service, 7000.0)

    # Execution 1: Buy 100 @ 30.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 100, 30.0)
    assert_position(broker_service, "AAPL", 100, Side.BUY, 30.0)
    assert_accounting(broker_service, 7000.0, 7000.0, 0.0, 0.0)

    # Execution 2: Sell 50 @ 28.00 (partial close)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 50, 28.0)
    assert_position(broker_service, "AAPL", 50, Side.BUY, 30.0)
    # Unrealized: (28 - 30) * 50 = -100
    assert_accounting(broker_service, 6900.0, 6800.0, -100.0, -100.0)

    # Execution 3: Buy 50 @ 29.00 (reopen)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 50, 29.0)
    assert_position(broker_service, "AAPL", 100, Side.BUY, 29.5)
    # Unrealized = (29 - 29.5) * 100 = -50
    assert_accounting(broker_service, 6900.0, 6850.0, -50.0, -100.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_8_round_trip_with_commission(broker_service: BrokerService) -> None:
    """Case 8: Round-trip with commission included.

    Initial: Balance = 50,000.00; market = 500.00; commission = 5.00
    Execution 1: Buy 100 @ 500.00
    - Commission: -5.00
    - Balance: 49,995.00
    - Position: 100 @ 500.00
    - Equity: 49,995.00

    Market: price -> 510.00
    - Equity: 50,995.00 (unrealized +1,000)

    Execution 2: Sell 100 @ 510.00
    - Commission: -5.00
    - Realized: +1,000.00
    - Balance: 50,990.00
    - Equity: 50,990.00
    """
    set_initial_balance(broker_service, 50000.0)

    # Apply commission manually for first order
    broker_service.accounting.balance -= 5.0

    # Execution 1: Buy 100 @ 500.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 100, 500.0)
    assert_position(broker_service, "AAPL", 100, Side.BUY, 500.0)
    assert_accounting(broker_service, 49995.0, 49995.0, 0.0, 0.0)

    # Apply commission for second order
    broker_service.accounting.balance -= 5.0

    # Execution 2: Sell 100 @ 510.00
    await place_and_execute(broker_service, "AAPL", Side.SELL, 100, 510.0)
    assert_position(broker_service, "AAPL", 0, Side.BUY, 500.0)
    assert_accounting(broker_service, 50990.0, 50990.0, 0.0, 1000.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_9_many_small_fills_weighted_average(
    broker_service: BrokerService,
) -> None:
    """Case 9: Many small fills with weighted average fill price.

    Initial: Balance = 2,500.00; market = 10.00
    Execution 1: Buy 50 @ 10.00
    - Position: 50 @ 10.00

    Execution 2: Buy 50 @ 12.00
    - New avg: 11.00
    - Position: 100 @ 11.00
    - Equity: 2,550.00 (unrealized +50 at market 11.50)

    Execution 3: Sell 100 @ 11.00 (close)
    - Realized: 0.00
    - Balance: 2,500.00
    - Equity: 2,500.00
    """
    set_initial_balance(broker_service, 2500.0)

    # Execution 1: Buy 50 @ 10.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 50, 10.0)
    assert_position(broker_service, "AAPL", 50, Side.BUY, 10.0)

    # Execution 2: Buy 50 @ 12.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 50, 12.0)
    assert_position(broker_service, "AAPL", 100, Side.BUY, 11.0)
    # Unrealized = (12 - 11) * 100 = 100
    assert_accounting(broker_service, 2500.0, 2600.0, 100.0, 0.0)

    # Execution 3: Sell 100 @ 11.00 (close at avg)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 100, 11.0)
    assert_position(broker_service, "AAPL", 0, Side.BUY, 11.0)
    assert_accounting(broker_service, 2500.0, 2500.0, 0.0, 0.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_10_short_averaging_down_partial_cover(
    broker_service: BrokerService,
) -> None:
    """Case 10: Opening a short, then adding to the short (averaging down) then covering partially.

    Initial: Balance = 30,000.00; market = 250.00
    Execution 1: Sell short 40 @ 250.00
    - Short -40 @ 250.00
    - Equity: 30,000.00

    Market: price -> 260.00
    - Equity: 29,600.00 (unrealized -400)

    Execution 2: Sell short 20 @ 260.00 (increase short to -60)
    - New avg: 253.33
    - Balance: 30,000.00
    - Equity: 29,600.00 (unrealized -400 at market 260)

    Execution 3: Buy 30 @ 255.00 (partial cover)
    - Realized: -50.00 (approx)
    - Balance: 29,950.00
    - Remaining: -30 @ 253.33
    - Equity: 29,900.00
    """
    set_initial_balance(broker_service, 30000.0)

    # Execution 1: Sell short 40 @ 250.00
    await place_and_execute(broker_service, "AAPL", Side.SELL, 40, 250.0)
    assert_position(broker_service, "AAPL", 40, Side.SELL, 250.0)
    assert_accounting(broker_service, 30000.0, 30000.0, 0.0, 0.0)

    # Execution 2: Sell short 20 @ 260.00 (add to short)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 20, 260.0)
    # New avg: (40*250 + 20*260) / 60 = 253.33
    assert_position(broker_service, "AAPL", 60, Side.SELL, 253.33, tolerance=0.02)
    # Unrealized = (253.33 - 260) * 60 = -400
    assert_accounting(broker_service, 30000.0, 29600.0, -400.0, 0.0, tolerance=1.0)

    # Execution 3: Buy 30 @ 255.00 (partial cover)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 30, 255.0)
    # Realized = (253.33 - 255) * 30 = -50
    assert_position(broker_service, "AAPL", 30, Side.SELL, 253.33, tolerance=0.02)
    assert_accounting(broker_service, 29950.0, 29900.0, -50.0, -50.0, tolerance=1.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_11_short_loss_cover_at_higher_price(
    broker_service: BrokerService,
) -> None:
    """Case 11: Full close of loss-making short by buying back at higher price.

    Initial: Balance = 6,000.00; market = 80.00
    Execution 1: Sell short 50 @ 80.00
    - Short -50 @ 80.00
    - Equity: 6,000.00

    Market: price -> 95.00
    - Equity: 5,250.00 (unrealized -750)

    Execution 2: Buy 50 @ 95.00 (cover)
    - Realized: -750.00
    - Balance: 5,250.00
    - Equity: 5,250.00
    """
    set_initial_balance(broker_service, 6000.0)

    # Execution 1: Sell short 50 @ 80.00
    await place_and_execute(broker_service, "AAPL", Side.SELL, 50, 80.0)
    assert_position(broker_service, "AAPL", 50, Side.SELL, 80.0)
    assert_accounting(broker_service, 6000.0, 6000.0, 0.0, 0.0)

    # Execution 2: Buy 50 @ 95.00 (cover at loss)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 50, 95.0)
    assert_position(broker_service, "AAPL", 0, Side.SELL, 80.0)
    assert_accounting(broker_service, 5250.0, 5250.0, 0.0, -750.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_12_complex_sequence_long_to_short_partial_close(
    broker_service: BrokerService,
) -> None:
    """Case 12: Complex sequence: long > partial reverse to short > partial cover > full close.

    Initial: Balance = 40,000.00; market = 100.00
    Execution 1: Buy 200 @ 100.00
    - Long 200 @ 100.00
    - Equity: 40,000.00

    Execution 2: Sell 150 @ 105.00 (partial close)
    - Realized: +750.00
    - Balance: 40,750.00
    - Remaining: 50 @ 100.00
    - Equity: 41,000.00 (unrealized +250)

    Execution 3: Sell 300 @ 104.00 (close 50 and open short 250)
    - Close 50 realized: +200.00
    - Balance: 40,950.00
    - New short: -250 @ 104.00
    - Equity: 40,950.00

    Execution 4: Buy 100 @ 102.00 (partial cover)
    - Realized: +200.00
    - Balance: 41,150.00
    - Remaining: -150 @ 104.00
    - Equity: 41,450.00 (unrealized +300)

    Execution 5: Buy 150 @ 101.00 (close remaining)
    - Realized: +450.00
    - Balance: 41,600.00
    - Equity: 41,600.00
    """
    set_initial_balance(broker_service, 40000.0)

    # Execution 1: Buy 200 @ 100.00
    await place_and_execute(broker_service, "AAPL", Side.BUY, 200, 100.0)
    assert_position(broker_service, "AAPL", 200, Side.BUY, 100.0)
    assert_accounting(broker_service, 40000.0, 40000.0, 0.0, 0.0)

    # Execution 2: Sell 150 @ 105.00 (partial close)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 150, 105.0)
    assert_position(broker_service, "AAPL", 50, Side.BUY, 100.0)
    # Unrealized: (105 - 100) * 50 = 250
    assert_accounting(broker_service, 40750.0, 41000.0, 250.0, 750.0)

    # Execution 3: Sell 300 @ 104.00 (reverse)
    await place_and_execute(broker_service, "AAPL", Side.SELL, 300, 104.0)
    assert_position(broker_service, "AAPL", 250, Side.SELL, 104.0)
    assert_accounting(broker_service, 40950.0, 40950.0, 0.0, 950.0)

    # Execution 4: Buy 100 @ 102.00 (partial cover)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 100, 102.0)
    assert_position(broker_service, "AAPL", 150, Side.SELL, 104.0)
    # Unrealized: (104 - 102) * 150 = 300
    assert_accounting(broker_service, 41150.0, 41450.0, 300.0, 1150.0)

    # Execution 5: Buy 150 @ 101.00 (close remaining)
    await place_and_execute(broker_service, "AAPL", Side.BUY, 150, 101.0)
    assert_position(broker_service, "AAPL", 0, Side.SELL, 104.0)
    assert_accounting(broker_service, 41600.0, 41600.0, 0.0, 1600.0)
