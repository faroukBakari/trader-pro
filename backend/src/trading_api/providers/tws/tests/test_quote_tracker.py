"""Tests for quote_tracker module - TrackedQuote and QuoteTracker classes.

Tests cover:
- Snapshot pattern (request with timeout)
- Streaming pattern (subscribe/update/unsubscribe)
- Error routing and propagation
- Thread-safety (asyncio event loop dispatch)
- Auto-cleanup on unsubscribe
"""

import asyncio
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from ibapi.contract import Contract, ContractDetails

from trading_api.models.exceptions import ProviderException
from trading_api.models.market import QuoteData, QuoteValues
from trading_api.providers.tws.cached_contract import CachedContract
from trading_api.providers.tws.quote_tracker import QuoteTracker, TrackedQuote


@pytest.fixture
def sample_cached_contract() -> CachedContract:
    """Create a sample CachedContract for testing."""
    contract_details = ContractDetails()
    contract_details.contract = Contract()
    contract_details.contract.symbol = "AAPL"
    contract_details.contract.secType = "STK"
    contract_details.contract.exchange = "NASDAQ"
    contract_details.contract.currency = "USD"
    contract_details.contract.conId = 265598

    return CachedContract.from_contract_details(contract_details)


def _quote_values(quote_data: QuoteData) -> QuoteValues:
    return cast(QuoteValues, quote_data.v)


class TestTrackedQuoteInitialization:
    """Test TrackedQuote initialization and basic properties."""

    def test_tracked_quote_initializes_with_none_fields(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """All tick fields should initialize to None."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)

        assert quote.cached_contract == sample_cached_contract
        assert quote.req_id == 1
        assert isinstance(quote.last_update, float)
        assert quote.last_update > 0
        assert quote.bid is None
        assert quote.ask is None
        assert quote.last is None
        assert quote.volume is None

    def test_tracked_quote_is_not_ready_initially(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Quote should not be ready without price data."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        assert not quote.is_ready


class TestTrackedQuoteReadyState:
    """Test is_ready property logic."""

    def test_is_ready_with_real_time_data(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Quote is ready when it has bid, ask, and last price."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.bid = 150.0
        quote.ask = 150.5
        quote.last = 150.25

        assert quote.is_ready

    def test_is_ready_with_delayed_data(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Quote is ready when it has delayed bid, ask, and last."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.delayed_bid = 150.0
        quote.delayed_ask = 150.5
        quote.delayed_last = 150.25

        assert quote.is_ready

    def test_not_ready_with_partial_data(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Quote is not ready with incomplete data."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.bid = 150.0
        # Missing ask (and delayed bid/ask)

        assert not quote.is_ready


class TestTrackedQuoteUpdate:
    """Test update method and hook dispatch."""

    @pytest.mark.asyncio
    async def test_update_applies_tick_fields(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Update should apply tick field values."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)

        updates: dict[str, int | float | str] = {
            "bid": 150.0,
            "ask": 150.5,
            "last": 150.25,
            "volume": 1000,
        }
        quote.update(updates)

        assert quote.bid == 150.0
        assert quote.ask == 150.5
        assert quote.last == 150.25
        assert quote.volume == 1000
        assert quote.last_update > 0

    @pytest.mark.asyncio
    async def test_update_resolves_snapshot_hooks_when_ready(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Snapshot hooks should resolve when quote becomes ready via QuoteTracker.

        Note: Hook management is centralized in QuoteTracker, not per-TrackedQuote.
        This test verifies that QuoteTracker.update() resolves snapshot hooks.
        """
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote and register snapshot hook via tracker
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote
        tracker._requests[sample_cached_contract.ticker] = 1

        loop = asyncio.get_running_loop()
        future: asyncio.Future[QuoteData] = loop.create_future()
        tracker._snapshot_hooks[1] = {"test": (loop, future)}

        # Update via tracker with complete data
        updates: dict[str, int | float | str] = {
            "bid": 150.0,
            "ask": 150.5,
            "last": 150.25,
        }
        tracker.update(1, updates)

        # Give event loop time to dispatch
        await asyncio.sleep(0.01)

        assert future.done()
        quote_data = future.result()
        quote_values = _quote_values(quote_data)
        assert quote_values.bid == 150.0

    @pytest.mark.asyncio
    async def test_update_dispatches_to_stream_hooks(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Stream hooks should receive updates via QuoteTracker.

        Note: Hook management is centralized in QuoteTracker, not per-TrackedQuote.
        This test verifies that QuoteTracker.update() dispatches to stream hooks.
        """
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote and register stream hook via tracker
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote
        tracker._requests[sample_cached_contract.ticker] = 1

        updates_received: list[QuoteData] = []

        async def on_update(data: QuoteData) -> None:
            updates_received.append(data)

        async def on_error(exc: ProviderException) -> None:
            pass

        loop = asyncio.get_running_loop()
        tracker._stream_hooks[1] = {"test": (loop, on_update, on_error)}

        # Send update via tracker
        updates: dict[str, int | float | str] = {
            "bid": 150.0,
            "ask": 150.5,
            "last": 150.25,
        }
        tracker.update(1, updates)

        # Give event loop time to dispatch
        await asyncio.sleep(0.01)

        assert len(updates_received) == 1
        quote_values = _quote_values(updates_received[0])
        assert quote_values.bid == 150.0


class TestTrackedQuoteRaiseError:
    """Test error propagation to hooks via QuoteTracker.

    Note: Hook management and error dispatch is centralized in QuoteTracker.
    These tests verify that QuoteTracker.raise_error() propagates to hooks.
    """

    @pytest.mark.asyncio
    async def test_raise_error_resolves_snapshot_hooks(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Snapshot hooks should receive exceptions via QuoteTracker."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote and register snapshot hook via tracker
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote
        tracker._requests[sample_cached_contract.ticker] = 1

        loop = asyncio.get_running_loop()
        future: asyncio.Future[QuoteData] = loop.create_future()
        tracker._snapshot_hooks[1] = {"test": (loop, future)}

        # Raise error via tracker (provider, capability, code, message)
        error = ProviderException(
            "tws", "datafeed", "PROVIDER_DATAFEED_ERROR", "Test error"
        )
        tracker.raise_error(1, error)

        # Give event loop time to dispatch
        await asyncio.sleep(0.01)

        assert future.done()
        # Match the exception string format: "[code] message"
        with pytest.raises(
            ProviderException, match=r"\[PROVIDER_DATAFEED_ERROR\] Test error"
        ):
            future.result()

    @pytest.mark.asyncio
    async def test_raise_error_dispatches_to_stream_hooks(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Stream error hooks should receive exceptions via QuoteTracker."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote and register stream hook via tracker
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote
        tracker._requests[sample_cached_contract.ticker] = 1

        errors_received: list[ProviderException] = []

        async def on_update(data: QuoteData) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            errors_received.append(exc)

        loop = asyncio.get_running_loop()
        tracker._stream_hooks[1] = {"test": (loop, on_update, on_error)}

        # Raise error via tracker (provider, capability, code, message)
        error = ProviderException(
            "tws", "datafeed", "PROVIDER_DATAFEED_ERROR", "Test error"
        )
        tracker.raise_error(1, error)

        # Give event loop time to dispatch
        await asyncio.sleep(0.01)

        assert len(errors_received) == 1
        assert "[PROVIDER_DATAFEED_ERROR] Test error" in str(errors_received[0])


class TestTrackedQuoteSnapshot:
    """Test snapshot pattern (one-time fetch with timeout) via QuoteTracker.

    Note: The snapshot pattern is now implemented in QuoteTracker.request(),
    not as a method on TrackedQuote. These tests verify the snapshot behavior.
    """

    @pytest.mark.asyncio
    async def test_snapshot_resolves_immediately_when_ready(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Snapshot should resolve immediately if quote is already ready."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Pre-populate tracker with ready quote
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.bid = 150.0
        quote.ask = 150.5
        quote.last = 150.25
        tracker._quotes[1] = quote
        tracker._requests[sample_cached_contract.ticker] = 1

        quote_data = await tracker.request(sample_cached_contract, timeout=1.0)

        quote_values = _quote_values(quote_data)
        assert quote_values.bid == 150.0
        assert quote_values.ask == 150.5

    @pytest.mark.asyncio
    async def test_snapshot_wait_for_data(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Snapshot should wait for quote to become ready."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        async def request_task() -> QuoteData:
            return await tracker.request(sample_cached_contract, timeout=1.0)

        task = asyncio.create_task(request_task())

        # Allow request() to start
        await asyncio.sleep(0.01)

        # Schedule update after a small delay
        updates: dict[str, int | float | str] = {
            "bid": 150.0,
            "ask": 150.5,
            "last": 150.25,
        }
        tracker.update(1, updates)

        # Snapshot should wait and resolve
        quote_data = await task
        quote_values = _quote_values(quote_data)
        assert quote_values.lp == 150.25  # Use 'lp' (last price) instead of 'last'

    @pytest.mark.asyncio
    async def test_snapshot_times_out(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Snapshot should timeout if data not received."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        with pytest.raises(asyncio.TimeoutError):
            await tracker.request(sample_cached_contract, timeout=0.05)


class TestTrackedQuoteToDomain:
    """Test domain conversion logic."""

    def test_to_domain_uses_real_time_data(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """to_domain should prefer real-time data."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.bid = 150.0
        quote.ask = 150.5
        quote.last = 150.25
        quote.volume = 1000

        quote_data = quote.to_domain()

        quote_values = _quote_values(quote_data)
        assert quote_values.bid == 150.0
        assert quote_values.ask == 150.5
        assert quote_values.lp == 150.25
        assert quote_values.volume == 1000

    def test_to_domain_falls_back_to_delayed_data(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """to_domain should fall back to delayed data."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.delayed_bid = 149.0
        quote.delayed_ask = 149.5
        quote.delayed_last = 149.25

        quote_data = quote.to_domain()

        quote_values = _quote_values(quote_data)
        assert quote_values.bid == 149.0
        assert quote_values.ask == 149.5
        assert quote_values.lp == 149.25

    def test_to_domain_calculates_spread(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """to_domain should calculate bid-ask spread."""
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.bid = 150.0
        quote.ask = 150.5
        quote.last = 150.25

        quote_data = quote.to_domain()

        quote_values = _quote_values(quote_data)
        assert quote_values.spread == 0.5


class TestQuoteTrackerInitialization:
    """Test QuoteTracker initialization."""

    def test_quote_tracker_initializes(self) -> None:
        """QuoteTracker should initialize with hooks."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()

        tracker = QuoteTracker(request_hook, cancel_hook, timeout=5.0)

        assert tracker._timeout == 5.0
        assert len(tracker._quotes) == 0
        assert len(tracker._requests) == 0


class TestQuoteTrackerRequest:
    """Test request method (snapshot pattern)."""

    @pytest.mark.asyncio
    async def test_request_creates_new_quote(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Request should create TrackedQuote if not exists."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        async def request_task() -> QuoteData:
            return await tracker.request(sample_cached_contract, timeout=1.0)

        task = asyncio.create_task(request_task())

        # Allow request() to create the quote and register snapshot hook
        await asyncio.sleep(0.01)

        # Update via tracker (not directly on quote) to dispatch hooks
        updates: dict[str, int | float | str] = {
            "bid": 150.0,
            "ask": 150.5,
            "last": 150.25,
        }
        tracker.update(1, updates)

        quote_data = await task

        quote_values = _quote_values(quote_data)
        assert quote_values.bid == 150.0
        request_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_reuses_existing_quote(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Request should reuse existing TrackedQuote."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Pre-populate tracker
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        quote.update({"bid": 150.0, "ask": 150.5, "last": 150.25})
        tracker._quotes[1] = quote
        tracker._requests[sample_cached_contract.ticker] = 1

        # Second request should reuse
        quote_data = await tracker.request(sample_cached_contract, timeout=1.0)
        quote_values = _quote_values(quote_data)

        assert quote_values.bid == 150.0
        request_hook.assert_not_called()  # Not called again


class TestQuoteTrackerSubscribe:
    """Test subscribe method (streaming pattern)."""

    @pytest.mark.asyncio
    async def test_subscribe_creates_new_quote(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Subscribe should create TrackedQuote if not exists."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        async def on_update(data: QuoteData) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        sub_key = tracker.subscribe(sample_cached_contract, on_update, on_error)

        assert isinstance(sub_key, str)
        assert f"{sample_cached_contract.ticker}#" in sub_key
        request_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_reuses_existing_quote(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Multiple subscriptions should reuse same TrackedQuote."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        async def on_update(data: QuoteData) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        # First subscription
        sub_key1 = tracker.subscribe(sample_cached_contract, on_update, on_error)
        # Second subscription
        sub_key2 = tracker.subscribe(sample_cached_contract, on_update, on_error)

        assert sub_key1 != sub_key2
        request_hook.assert_called_once()  # Only called once


class TestQuoteTrackerUnsubscribe:
    """Test unsubscribe method."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Unsubscribe should remove subscription from TrackedQuote."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        async def on_update(data: QuoteData) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        sub_key = tracker.subscribe(sample_cached_contract, on_update, on_error)

        loop = asyncio.get_running_loop()
        with patch.object(
            loop, "call_later", side_effect=lambda _delay, cb, *args: cb(*args)
        ):
            tracker.unsubscribe(sub_key)

        # Quote should be cancelled and removed
        cancel_hook.assert_called_once_with(1)
        assert len(tracker._quotes) == 0
        assert len(tracker._requests) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_keeps_quote_with_multiple_subscribers(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Unsubscribe should not cancel if other subscribers exist."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        async def on_update(data: QuoteData) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        # Two subscriptions
        sub_key1 = tracker.subscribe(sample_cached_contract, on_update, on_error)
        sub_key2 = tracker.subscribe(sample_cached_contract, on_update, on_error)

        assert sub_key1 != sub_key2

        # Unsubscribe one
        loop = asyncio.get_running_loop()
        with patch.object(
            loop, "call_later", side_effect=lambda _delay, cb, *args: cb(*args)
        ):
            tracker.unsubscribe(sub_key1)

        # Quote should still exist
        cancel_hook.assert_not_called()
        assert len(tracker._quotes) == 1


class TestQuoteTrackerUpdate:
    """Test update method (called from reader thread)."""

    @pytest.mark.asyncio
    async def test_update_dispatches_to_tracked_quote(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Update should dispatch to TrackedQuote."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote

        # Send update
        updates: dict[str, int | float | str] = {"bid": 150.0, "ask": 150.5}
        tracker.update(1, updates)

        assert quote.bid == 150.0
        assert quote.ask == 150.5

    def test_update_ignores_unknown_req_id(self) -> None:
        """Update should silently ignore unknown req_id."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Send update for non-existent quote
        tracker.update(999, {"bid": 150.0})

        # Should not raise


class TestQuoteTrackerRaiseError:
    """Test raise_error method (called from reader thread)."""

    def test_raise_error_returns_true_when_quote_exists(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """raise_error should return True if req_id found."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote

        error = ProviderException(
            "tws", "datafeed", "PROVIDER_DATAFEED_ERROR", "Test error"
        )
        result = tracker.raise_error(1, error)

        assert result is True

    def test_raise_error_returns_false_when_quote_not_found(self) -> None:
        """raise_error should return False if req_id not found."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        error = ProviderException(
            "tws", "datafeed", "PROVIDER_DATAFEED_ERROR", "Test error"
        )
        result = tracker.raise_error(999, error)

        assert result is False


class TestQuoteTrackerReset:
    """Test reset method."""

    def test_reset_clears_all_quotes(
        self, sample_cached_contract: CachedContract
    ) -> None:
        """Reset should clear all quotes and requests."""
        request_hook = MagicMock(return_value=1)
        cancel_hook = MagicMock()
        tracker = QuoteTracker(request_hook, cancel_hook)

        # Create quote
        quote = TrackedQuote(sample_cached_contract, req_id=1)
        tracker._quotes[1] = quote
        tracker._requests["NASDAQ:AAPL:STK"] = 1

        tracker.reset()

        assert len(tracker._quotes) == 0
        assert len(tracker._requests) == 0
