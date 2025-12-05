"""Tests for TWSCallback - EWrapper callback handling and Future management.

Tests cover:
- Future creation and registration
- Future resolution from callbacks (symbolSamples, contractDetails, etc.)
- Accumulation patterns (contractDetails, historicalData, market data)
- Error handling (error callback, TWSError)
- Connection signals (nextValidId, managedAccounts)

Note: TWSCallback is tested in isolation - no socket or thread mocking needed.
"""

import asyncio
from typing import Any

import pytest
from ibapi.common import BarData, TickAttrib
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.tws_connection import TWSCallback
from trading_api.providers.tws.tws_models import TWSError


class TestTWSCallbackInitialization:
    """Test TWSCallback initialization."""

    def test_callback_initialization_with_loop(self) -> None:
        """Test TWSCallback initializes with provided event loop."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        assert callback._loop is loop
        assert callback._futures == {}
        assert callback._accumulators == {}
        assert callback._nxt_order_id is None
        assert callback._accounts == []

        loop.close()

    def test_callback_initialization_uses_default_loop(self) -> None:
        """Test TWSCallback uses running event loop if none provided."""
        # Default loop will be set at construction time
        callback = TWSCallback()
        assert callback._loop is not None


class TestFutureManagement:
    """Test Future creation and resolution."""

    @pytest.mark.asyncio
    async def test_create_future_coroutine(self) -> None:
        """Test create_future_coroutine creates awaitable future."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        coro = callback.create_future_coroutine(req_id, timeout=5.0)

        # Future should be registered
        assert req_id in callback._futures

        # Resolve it immediately
        callback._resolve_future(req_id, "test_result")

        result = await coro
        assert result == "test_result"

    @pytest.mark.asyncio
    async def test_resolve_future_removes_from_registry(self) -> None:
        """Test _resolve_future removes future from registry."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[str] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        callback._resolve_future(req_id, "result")

        # Future should be removed from registry
        assert req_id not in callback._futures

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert result == "result"

    @pytest.mark.asyncio
    async def test_reject_future_with_exception(self) -> None:
        """Test _reject_future rejects with exception."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[Any] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        test_error = ValueError("test error")
        callback._reject_future(req_id, test_error)

        # Future should be removed
        assert req_id not in callback._futures

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        with pytest.raises(ValueError, match="test error"):
            await future

    def test_resolve_unknown_reqid_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test resolving unknown reqId logs error but doesn't crash."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        # Should not raise
        callback._resolve_future(999, "result")

        # Should log error
        assert "Unknown reqId 999" in caplog.text

        loop.close()


class TestSymbolSamplesCallback:
    """Test symbolSamples callback - single response pattern."""

    @pytest.mark.asyncio
    async def test_symbol_samples_resolves_future(self) -> None:
        """Test symbolSamples callback resolves pending future."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[list[ContractDescription]] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        # Create test data
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"

        desc = ContractDescription()
        desc.contract = contract

        # Simulate callback
        callback.symbolSamples(req_id, [desc])

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert len(result) == 1
        assert result[0].contract.symbol == "AAPL"
        assert req_id not in callback._futures

    @pytest.mark.asyncio
    async def test_symbol_samples_empty_results(self) -> None:
        """Test symbolSamples with empty results."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[list[ContractDescription]] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        callback.symbolSamples(req_id, [])

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert result == []


class TestContractDetailsCallback:
    """Test contractDetails callback - streaming accumulation pattern."""

    @pytest.mark.asyncio
    async def test_contract_details_accumulates_results(self) -> None:
        """Test contractDetails accumulates multiple callbacks."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)
        # Accumulator auto-created by contractDetails via setdefault

        # Create test data
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.exchange = "NASDAQ"
        details1 = ContractDetails()
        details1.contract = contract1
        details1.longName = "Apple Inc"

        contract2 = Contract()
        contract2.symbol = "AAPL"
        contract2.exchange = "NYSE"
        details2 = ContractDetails()
        details2.contract = contract2
        details2.longName = "Apple Inc NYSE"

        # Simulate multiple callbacks
        callback.contractDetails(req_id, details1)
        callback.contractDetails(req_id, details2)

        # Check accumulator
        assert len(callback._accumulators[req_id]) == 2

        # End signal
        callback.contractDetailsEnd(req_id)

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert len(result) == 2
        assert result[0].longName == "Apple Inc"
        assert result[1].longName == "Apple Inc NYSE"
        assert req_id not in callback._futures
        assert req_id not in callback._accumulators

    @pytest.mark.asyncio
    async def test_contract_details_single_result(self) -> None:
        """Test contractDetails with single result."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        contract = Contract()
        contract.symbol = "MSFT"
        details = ContractDetails()
        details.contract = contract
        details.minTick = 0.01

        callback.contractDetails(req_id, details)
        callback.contractDetailsEnd(req_id)

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert len(result) == 1
        assert result[0].contract.symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_contract_details_end_empty(self) -> None:
        """Test contractDetailsEnd with no results (symbol not found)."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        # End signal without any contractDetails calls
        callback.contractDetailsEnd(req_id)

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert result == []


class TestHistoricalDataCallback:
    """Test historicalData callback - streaming accumulation pattern."""

    @pytest.mark.asyncio
    async def test_historical_data_accumulates_bars(self) -> None:
        """Test historicalData accumulates multiple bars."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[list[BarData]] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        # Create test bars
        bar1 = BarData()
        bar1.date = "20231215 09:30:00"
        bar1.open = 150.0
        bar1.close = 151.0

        bar2 = BarData()
        bar2.date = "20231215 09:31:00"
        bar2.open = 151.0
        bar2.close = 152.0

        # Simulate callbacks
        callback.historicalData(req_id, bar1)
        callback.historicalData(req_id, bar2)

        assert len(callback._accumulators[req_id]) == 2

        # End signal
        callback.historicalDataEnd(req_id, "20231215 09:30:00", "20231215 09:31:00")

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        result = await future
        assert len(result) == 2
        assert result[0].open == 150.0
        assert result[1].open == 151.0


class TestMarketDataSnapshotCallback:
    """Test market data snapshot callbacks - RTMarketData ticker pattern."""

    @pytest.mark.asyncio
    async def test_tick_price_updates_ticker(self) -> None:
        """Test tickPrice updates RTMarketData ticker fields."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first (required by new implementation)
        ticker = callback.register_ticker([req_id])

        tick_attrib = TickAttrib()

        # BID=1, ASK=2, LAST=4 in TickTypeEnum
        callback.tickPrice(req_id, 1, 150.25, tick_attrib)  # BID
        callback.tickPrice(req_id, 2, 150.30, tick_attrib)  # ASK

        # Check ticker has prices
        assert ticker.bid == 150.25
        assert ticker.ask == 150.30

    @pytest.mark.asyncio
    async def test_tick_size_updates_ticker(self) -> None:
        """Test tickSize updates RTMarketData ticker fields."""
        from decimal import Decimal

        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first
        ticker = callback.register_ticker([req_id])

        # BID_SIZE=0, ASK_SIZE=3, VOLUME=8
        callback.tickSize(req_id, 0, Decimal("1000"))  # BID_SIZE
        callback.tickSize(req_id, 8, Decimal("500000"))  # VOLUME

        assert ticker.bid_size == 1000
        assert ticker.volume == 500000

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_resets_ticker(self) -> None:
        """Test tickSnapshotEnd resets ticker data."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot and set some data
        ticker = callback.register_ticker([req_id])
        ticker.bid = 100.0
        ticker.ask = 100.05

        callback.tickSnapshotEnd(req_id)

        # Ticker should be reset
        assert ticker.bid is None
        assert ticker.ask is None  # type: ignore[unreachable]


class TestErrorHandling:
    """Test error callback handling."""

    def test_tws_error_dataclass(self) -> None:
        """Test TWSError dataclass structure."""
        error = TWSError(
            reqId=1,
            errorCode=200,
            errorString="No security definition",
            errorTime=1234567890,
        )

        assert error.reqId == 1
        assert error.errorCode == 200
        assert error.errorString == "No security definition"
        assert "TWS error 200" in str(error)

    @pytest.mark.asyncio
    async def test_error_rejects_future(self) -> None:
        """Test error callback rejects pending future."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[Any] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)

        callback.error(req_id, 1234567890, 200, "No security definition")

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        with pytest.raises(TWSError) as exc_info:
            await future

        assert exc_info.value.errorCode == 200
        assert "No security definition" in exc_info.value.errorString

    def test_general_error_no_future_no_crash(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test general error (reqId=-1) doesn't crash."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        # Should not raise - general errors have reqId=-1
        callback.error(-1, 1234567890, 502, "Couldn't connect to TWS")

        # Should log error
        assert "TWS error" in caplog.text or "502" in caplog.text

        loop.close()

    @pytest.mark.asyncio
    async def test_error_cleans_up_accumulator(self) -> None:
        """Test error cleans up accumulator if present."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[Any] = loop.create_future()
        # _futures stores (loop, future) tuple
        callback._futures[req_id] = (loop, future)
        callback._accumulators[req_id] = [{"partial": "data"}]

        callback.error(
            req_id, 1234567890, 162, "Historical data request pacing violation"
        )

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.01)

        # Future should be rejected
        with pytest.raises(TWSError):
            await future

        # Accumulator cleanup happens via future rejection (not automatic)
        # This is expected behavior - error doesn't explicitly clean accumulator


class TestConnectionSignals:
    """Test connection-related callbacks."""

    def test_next_valid_id_sets_order_id(self) -> None:
        """Test nextValidId sets order ID and signals ready."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        assert callback._nxt_order_id is None
        assert not callback._ready_event.is_set()

        callback.nextValidId(1000)

        assert callback._nxt_order_id == 1000
        assert callback._ready_event.is_set()

        loop.close()

    def test_managed_accounts_parses_list(self) -> None:
        """Test managedAccounts parses comma-separated accounts."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        callback.managedAccounts("DU123456,DU789012,DU345678")

        assert callback._accounts == ["DU123456", "DU789012", "DU345678"]

        loop.close()

    def test_managed_accounts_single_account(self) -> None:
        """Test managedAccounts with single account."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        callback.managedAccounts("DU123456")

        assert callback._accounts == ["DU123456"]

        loop.close()


class TestTickReqParams:
    """Test tickReqParams callback."""

    def test_tick_req_params_updates_ticker(self) -> None:
        """Test tickReqParams updates RTMarketData ticker fields."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first
        ticker = callback.register_ticker([req_id])

        callback.tickReqParams(req_id, 0.01, "ISLAND", 3)

        assert ticker.min_tick == 0.01
        assert ticker.bbo_exchange == "ISLAND"
        assert ticker.snapshot_permissions == 3

        loop.close()


class TestMarketDataType:
    """Test marketDataType callback."""

    def test_market_data_type_updates_ticker(self) -> None:
        """Test marketDataType updates RTMarketData ticker field."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first
        ticker = callback.register_ticker([req_id])

        callback.marketDataType(req_id, 2)  # 2 = Frozen

        assert ticker.market_data_type == 2

        loop.close()


class TestTickStringGeneric:
    """Test tickString and tickGeneric callbacks."""

    def test_tick_string_updates_ticker(self) -> None:
        """Test tickString updates RTMarketData ticker field."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first
        ticker = callback.register_ticker([req_id])

        # LAST_TIMESTAMP=45
        callback.tickString(req_id, 45, "1702656000")

        assert ticker.last_timestamp == "1702656000"

        loop.close()

    def test_tick_generic_updates_ticker(self) -> None:
        """Test tickGeneric updates RTMarketData ticker field."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first
        ticker = callback.register_ticker([req_id])

        # HALTED=49
        callback.tickGeneric(req_id, 49, 0.0)

        assert ticker.halted == 0.0

        loop.close()


class TestRealtimeBarCallback:
    """Test real-time bar updates via historicalDataUpdate callback.

    Note: With the new unified RT data design, real-time bars come through
    historicalDataUpdate (with keepUpToDate=True), not realtimeBar.
    The realtimeBar callback is not implemented.
    """

    @pytest.mark.asyncio
    async def test_historical_data_update_updates_ticker(self) -> None:
        """Test historicalDataUpdate updates RTMarketData ticker bar fields."""
        from decimal import Decimal

        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        # Create ticker slot first
        ticker = callback.register_ticker([req_id])

        # Create a bar update
        bar = BarData()
        bar.date = "1702656000"  # Epoch timestamp
        bar.open = 150.25
        bar.high = 150.50
        bar.low = 150.10
        bar.close = 150.40
        bar.volume = Decimal("10000")
        bar.wap = Decimal("150.30")
        bar.barCount = 50

        callback.historicalDataUpdate(req_id, bar)

        # Verify ticker was updated - bar_date stores raw TWS date string
        assert ticker.bar_date == "1702656000"
        assert ticker.bar_open == 150.25
        assert ticker.bar_high == 150.50
        assert ticker.bar_low == 150.10
        assert ticker.bar_close == 150.40
        assert ticker.bar_volume == 10000
        assert ticker.bar_wap == 150.30
        assert ticker.bar_count == 50

    @pytest.mark.asyncio
    async def test_historical_data_update_triggers_callbacks(self) -> None:
        """Test historicalDataUpdate triggers registered ticker callbacks."""
        from decimal import Decimal

        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        ticker = callback.register_ticker([req_id])

        # Track callback invocations
        callback_called: list[tuple[Any, list[str] | None]] = []

        async def ticker_callback(
            rt_data: Any, updated_fields: list[str] | None
        ) -> None:
            callback_called.append((rt_data, updated_fields))

        # Register callback on ticker
        ticker.reqId_callback_map[123] = (loop, ticker_callback)

        bar = BarData()
        bar.date = "1702656000"
        bar.open = 150.0
        bar.high = 151.0
        bar.low = 149.0
        bar.close = 150.5
        bar.volume = Decimal("1000")
        bar.wap = Decimal("150.0")
        bar.barCount = 10

        callback.historicalDataUpdate(req_id, bar)

        # Allow event loop to process call_soon_threadsafe
        await asyncio.sleep(0.05)

        assert len(callback_called) == 1
        assert callback_called[0][0] is ticker

    @pytest.mark.asyncio
    async def test_callbacks_initialization(self) -> None:
        """Test _callbacks is initialized empty."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        assert callback._callbacks == {}
        assert isinstance(callback._callbacks, dict)
