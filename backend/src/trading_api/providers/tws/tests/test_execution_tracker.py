"""Unit tests for ExecutionTracker.

Tests TrackedExecution dataclass and ExecutionTracker thread-safe operations.
"""

import asyncio
from decimal import Decimal

import pytest
from ibapi.contract import Contract
from ibapi.execution import Execution as TWSExecution

from trading_api.models.broker import Side
from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.execution_tracker import (
    ExecutionTracker,
    TrackedExecution,
    _parse_tws_execution_time,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_contract() -> Contract:
    """Create a sample TWS Contract for testing."""
    contract = Contract()
    contract.symbol = "AAPL"
    contract.exchange = "NASDAQ"
    contract.conId = 265598
    contract.secType = "STK"
    contract.currency = "USD"
    return contract


@pytest.fixture
def sample_execution() -> TWSExecution:
    """Create a sample TWS Execution for testing."""
    execution = TWSExecution()
    execution.execId = "0001f4e8.65a12345.01.01"
    execution.time = "20240115 14:30:45"
    execution.acctNumber = "DU123456"
    execution.exchange = "NASDAQ"
    execution.side = "BOT"
    execution.shares = Decimal("100")
    execution.price = 185.50
    execution.permId = 123456789
    execution.orderId = 42
    execution.cumQty = Decimal("100")
    execution.avgPrice = 185.50
    return execution


@pytest.fixture
def sample_sell_execution() -> TWSExecution:
    """Create a sample TWS Execution for SELL side."""
    execution = TWSExecution()
    execution.execId = "0001f4e8.65a12345.01.02"
    execution.time = "20240115 14:35:00"
    execution.acctNumber = "DU123456"
    execution.exchange = "NASDAQ"
    execution.side = "SLD"
    execution.shares = Decimal("50")
    execution.price = 186.25
    execution.permId = 123456790
    execution.orderId = 43
    execution.cumQty = Decimal("50")
    execution.avgPrice = 186.25
    return execution


@pytest.fixture
def tracker() -> ExecutionTracker:
    """Create a fresh ExecutionTracker for testing."""
    return ExecutionTracker()


# =============================================================================
# _parse_tws_execution_time Tests
# =============================================================================


class TestParseTwsExecutionTime:
    """Test TWS execution time parsing utility."""

    def test_parse_standard_format(self) -> None:
        """Parse standard TWS format: YYYYMMDD HH:MM:SS."""
        result = _parse_tws_execution_time("20240115 14:30:45")
        # 2024-01-15 14:30:45 UTC in milliseconds
        assert result == 1705329045000

    def test_parse_dash_separator(self) -> None:
        """Parse dash-separated format: YYYYMMDD-HH:MM:SS."""
        result = _parse_tws_execution_time("20240115-14:30:45")
        assert result == 1705329045000

    def test_parse_invalid_format_returns_current_time(self) -> None:
        """Invalid format returns current time (graceful degradation)."""
        result = _parse_tws_execution_time("invalid-time")
        # Should return a reasonable timestamp (within last minute)
        import time

        now_ms = int(time.time() * 1000)
        assert abs(result - now_ms) < 60000  # Within 60 seconds


# =============================================================================
# TrackedExecution Tests
# =============================================================================


class TestTrackedExecution:
    """Test TrackedExecution dataclass."""

    def test_exec_id_property(
        self, sample_contract: Contract, sample_execution: TWSExecution
    ) -> None:
        """Verify exec_id returns execution.execId."""
        tracked = TrackedExecution(contract=sample_contract, execution=sample_execution)
        assert tracked.exec_id == "0001f4e8.65a12345.01.01"

    def test_symbol_property(
        self, sample_contract: Contract, sample_execution: TWSExecution
    ) -> None:
        """Verify symbol returns EXCHANGE:SYMBOL format."""
        tracked = TrackedExecution(contract=sample_contract, execution=sample_execution)
        assert tracked.symbol == "NASDAQ:AAPL"

    def test_commission_default_none(
        self, sample_contract: Contract, sample_execution: TWSExecution
    ) -> None:
        """Verify commission defaults to None."""
        tracked = TrackedExecution(contract=sample_contract, execution=sample_execution)
        assert tracked.commission is None

    def test_commission_can_be_set(
        self, sample_contract: Contract, sample_execution: TWSExecution
    ) -> None:
        """Verify commission can be set after creation."""
        tracked = TrackedExecution(contract=sample_contract, execution=sample_execution)
        tracked.commission = 1.25
        assert tracked.commission == 1.25

    def test_to_domain_buy_side(
        self, sample_contract: Contract, sample_execution: TWSExecution
    ) -> None:
        """Verify to_domain() converts BOT to Side.BUY."""
        tracked = TrackedExecution(
            contract=sample_contract, execution=sample_execution, commission=1.50
        )
        domain = tracked.to_domain()

        assert domain.symbol == "NASDAQ:AAPL"
        assert domain.price == 185.50
        assert domain.qty == 100.0
        assert domain.side == Side.BUY
        assert domain.commission == 1.50
        assert domain.time == 1705329045000  # 2024-01-15 14:30:45 UTC

    def test_to_domain_sell_side(
        self, sample_contract: Contract, sample_sell_execution: TWSExecution
    ) -> None:
        """Verify to_domain() converts SLD to Side.SELL."""
        tracked = TrackedExecution(
            contract=sample_contract, execution=sample_sell_execution
        )
        domain = tracked.to_domain()

        assert domain.side == Side.SELL
        assert domain.qty == 50.0
        assert domain.price == 186.25

    def test_to_domain_without_commission(
        self, sample_contract: Contract, sample_execution: TWSExecution
    ) -> None:
        """Verify to_domain() works with commission=None."""
        tracked = TrackedExecution(contract=sample_contract, execution=sample_execution)
        domain = tracked.to_domain()

        assert domain.commission is None


# =============================================================================
# ExecutionTracker Tests
# =============================================================================


class TestExecutionTrackerUpsert:
    """Test ExecutionTracker.upsert_execution() method."""

    def test_upsert_creates_new_execution(
        self,
        tracker: ExecutionTracker,
        sample_contract: Contract,
        sample_execution: TWSExecution,
    ) -> None:
        """Verify upsert creates new TrackedExecution."""
        tracker.upsert_execution(sample_contract, sample_execution)

        assert sample_execution.execId in tracker._executions
        tracked = tracker._executions[sample_execution.execId]
        assert tracked.contract is sample_contract
        assert tracked.execution is sample_execution
        assert tracked.commission is None

    def test_upsert_updates_existing_execution(
        self,
        tracker: ExecutionTracker,
        sample_contract: Contract,
        sample_execution: TWSExecution,
    ) -> None:
        """Verify upsert updates existing TrackedExecution."""
        # First upsert
        tracker.upsert_execution(sample_contract, sample_execution)

        # Modify execution and upsert again
        modified_execution = TWSExecution()
        modified_execution.execId = sample_execution.execId
        modified_execution.price = 186.00  # Different price
        modified_execution.shares = Decimal("100")
        modified_execution.side = "BOT"
        modified_execution.time = "20240115 14:31:00"

        new_contract = Contract()
        new_contract.symbol = "AAPL"
        new_contract.exchange = "NYSE"  # Different exchange

        tracker.upsert_execution(new_contract, modified_execution)

        # Should be updated, not duplicated
        assert len(tracker._executions) == 1
        tracked = tracker._executions[sample_execution.execId]
        assert tracked.execution.price == 186.00
        assert tracked.contract.exchange == "NYSE"


class TestExecutionTrackerCommission:
    """Test ExecutionTracker.update_commission() method."""

    def test_update_commission_enriches_execution(
        self,
        tracker: ExecutionTracker,
        sample_contract: Contract,
        sample_execution: TWSExecution,
    ) -> None:
        """Verify update_commission enriches existing execution."""
        tracker.upsert_execution(sample_contract, sample_execution)

        tracker.update_commission(sample_execution.execId, 1.25)

        tracked = tracker._executions[sample_execution.execId]
        assert tracked.commission == 1.25

    def test_update_commission_ignores_unknown_exec_id(
        self, tracker: ExecutionTracker
    ) -> None:
        """Verify update_commission ignores unknown exec_id (no crash)."""
        # Should not raise
        tracker.update_commission("unknown_exec_id", 1.25)
        assert len(tracker._executions) == 0


class TestExecutionTrackerSnapshot:
    """Test ExecutionTracker snapshot functionality."""

    def test_mark_snapshot_complete_sets_event(self, tracker: ExecutionTracker) -> None:
        """Verify mark_snapshot_complete sets the event."""
        assert not tracker._snapshot_complete.is_set()
        tracker.mark_snapshot_complete()
        assert tracker._snapshot_complete.is_set()

    def test_ensure_snapshot_requested_calls_callback_once(
        self, tracker: ExecutionTracker
    ) -> None:
        """Verify ensure_snapshot_requested calls callback only once."""
        call_count = 0

        def request_cb() -> None:
            nonlocal call_count
            call_count += 1

        tracker.ensure_snapshot_requested(request_cb)
        tracker.ensure_snapshot_requested(request_cb)
        tracker.ensure_snapshot_requested(request_cb)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_all_executions_returns_after_snapshot_complete(
        self,
        tracker: ExecutionTracker,
        sample_contract: Contract,
        sample_execution: TWSExecution,
    ) -> None:
        """Verify all_executions returns after snapshot is complete."""
        # Add execution and mark complete
        tracker.upsert_execution(sample_contract, sample_execution)
        tracker.mark_snapshot_complete()

        # Should return immediately
        executions = await asyncio.wait_for(tracker.all_executions(), timeout=1.0)

        assert len(executions) == 1
        assert executions[0].exec_id == sample_execution.execId

    @pytest.mark.asyncio
    async def test_all_executions_filters_by_symbol(
        self,
        tracker: ExecutionTracker,
        sample_contract: Contract,
        sample_execution: TWSExecution,
        sample_sell_execution: TWSExecution,
    ) -> None:
        """Verify all_executions filters by symbol."""
        # Add AAPL execution
        tracker.upsert_execution(sample_contract, sample_execution)

        # Add different symbol execution
        other_contract = Contract()
        other_contract.symbol = "MSFT"
        other_contract.exchange = "NASDAQ"
        tracker.upsert_execution(other_contract, sample_sell_execution)

        tracker.mark_snapshot_complete()

        # Filter by NASDAQ:AAPL
        executions = await tracker.all_executions(filter_symbol="NASDAQ:AAPL")
        assert len(executions) == 1
        assert executions[0].symbol == "NASDAQ:AAPL"

        # Filter by NASDAQ:MSFT
        executions = await tracker.all_executions(filter_symbol="NASDAQ:MSFT")
        assert len(executions) == 1
        assert executions[0].symbol == "NASDAQ:MSFT"


class TestExecutionTrackerStreamHooks:
    """Test ExecutionTracker stream hook functionality."""

    def test_create_stream_hook_returns_unique_key(
        self, tracker: ExecutionTracker
    ) -> None:
        """Verify create_stream_hook returns unique keys."""
        loop = asyncio.new_event_loop()

        async def callback(tracked: TrackedExecution) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        key1 = tracker.create_stream_hook(loop, callback, on_error)
        key2 = tracker.create_stream_hook(loop, callback, on_error)

        assert key1 != key2
        assert len(tracker._stream_hooks) == 2

        loop.close()

    def test_remove_stream_hook_removes_callback(
        self, tracker: ExecutionTracker
    ) -> None:
        """Verify remove_stream_hook removes the callback."""
        loop = asyncio.new_event_loop()

        async def callback(tracked: TrackedExecution) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        key = tracker.create_stream_hook(loop, callback, on_error)
        assert key in tracker._stream_hooks

        tracker.remove_stream_hook(key)
        assert key not in tracker._stream_hooks

        loop.close()

    def test_remove_stream_hook_ignores_unknown_key(
        self, tracker: ExecutionTracker
    ) -> None:
        """Verify remove_stream_hook ignores unknown keys (no crash)."""
        # Should not raise
        tracker.remove_stream_hook("unknown_key")


class TestExecutionTrackerReset:
    """Test ExecutionTracker.reset() method."""

    def test_reset_clears_all_state(
        self,
        tracker: ExecutionTracker,
        sample_contract: Contract,
        sample_execution: TWSExecution,
    ) -> None:
        """Verify reset clears all tracker state."""
        # Populate state
        tracker.upsert_execution(sample_contract, sample_execution)
        tracker.mark_snapshot_complete()

        loop = asyncio.new_event_loop()

        async def callback(tracked: TrackedExecution) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        tracker.create_stream_hook(loop, callback, on_error)

        # Reset
        tracker.reset()

        # Verify all state cleared
        assert len(tracker._executions) == 0
        assert not tracker._snapshot_requested.is_set()
        assert not tracker._snapshot_complete.is_set()
        assert len(tracker._snapshot_hooks) == 0
        assert len(tracker._stream_hooks) == 0

        loop.close()
