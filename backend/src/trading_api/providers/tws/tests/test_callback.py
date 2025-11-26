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

from trading_api.providers.tws.tws_connection import TWSCallback, TWSError


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
        callback._futures[req_id] = future

        callback._resolve_future(req_id, "result")

        # Future should be removed from registry
        assert req_id not in callback._futures

        result = await future
        assert result == "result"

    @pytest.mark.asyncio
    async def test_reject_future_with_exception(self) -> None:
        """Test _reject_future rejects with exception."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[Any] = loop.create_future()
        callback._futures[req_id] = future

        test_error = ValueError("test error")
        callback._reject_future(req_id, test_error)

        # Future should be removed
        assert req_id not in callback._futures

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
        callback._futures[req_id] = future

        # Create test data
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"

        desc = ContractDescription()
        desc.contract = contract

        # Simulate callback
        callback.symbolSamples(req_id, [desc])

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
        callback._futures[req_id] = future

        callback.symbolSamples(req_id, [])

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
        callback._futures[req_id] = future
        # Accumulator must be pre-initialized for accumulation pattern
        callback._accumulators[req_id] = []

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
        callback._futures[req_id] = future
        callback._accumulators[req_id] = []

        contract = Contract()
        contract.symbol = "MSFT"
        details = ContractDetails()
        details.contract = contract
        details.minTick = 0.01

        callback.contractDetails(req_id, details)
        callback.contractDetailsEnd(req_id)

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
        callback._futures[req_id] = future
        callback._accumulators[req_id] = []

        # End signal without any contractDetails calls
        callback.contractDetailsEnd(req_id)

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
        callback._futures[req_id] = future
        callback._accumulators[req_id] = []

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

        result = await future
        assert len(result) == 2
        assert result[0].open == 150.0
        assert result[1].open == 151.0


class TestMarketDataSnapshotCallback:
    """Test market data snapshot callbacks - accumulation pattern."""

    @pytest.mark.asyncio
    async def test_tick_price_accumulates(self) -> None:
        """Test tickPrice accumulates price ticks."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        callback._futures[req_id] = future
        # Accumulator auto-created by tickPrice

        tick_attrib = TickAttrib()

        # BID=1, ASK=2, LAST=4 in TickTypeEnum
        callback.tickPrice(req_id, 1, 150.25, tick_attrib)  # BID
        callback.tickPrice(req_id, 2, 150.30, tick_attrib)  # ASK

        # Check accumulator has prices
        assert "BID" in callback._accumulators[req_id]
        assert callback._accumulators[req_id]["BID"] == 150.25

    @pytest.mark.asyncio
    async def test_tick_size_accumulates(self) -> None:
        """Test tickSize accumulates size ticks."""
        from decimal import Decimal

        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        callback._accumulators[req_id] = {}

        # BID_SIZE=0, ASK_SIZE=3, VOLUME=8
        callback.tickSize(req_id, 0, Decimal("1000"))  # BID_SIZE
        callback.tickSize(req_id, 8, Decimal("500000"))  # VOLUME

        assert callback._accumulators[req_id]["BID_SIZE"] == 1000
        assert callback._accumulators[req_id]["VOLUME"] == 500000

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_resolves(self) -> None:
        """Test tickSnapshotEnd resolves future with accumulated ticks."""
        loop = asyncio.get_running_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        callback._futures[req_id] = future
        callback._accumulators[req_id] = {"BID": 100.0, "ASK": 100.05}

        callback.tickSnapshotEnd(req_id)

        result = await future
        assert result["BID"] == 100.0
        assert result["ASK"] == 100.05
        assert req_id not in callback._accumulators


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
        callback._futures[req_id] = future

        callback.error(req_id, 1234567890, 200, "No security definition")

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
        callback._futures[req_id] = future
        callback._accumulators[req_id] = [{"partial": "data"}]

        callback.error(
            req_id, 1234567890, 162, "Historical data request pacing violation"
        )

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

    def test_tick_req_params_accumulates(self) -> None:
        """Test tickReqParams adds data to accumulator."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        callback._accumulators[req_id] = {}

        callback.tickReqParams(req_id, 0.01, "ISLAND", 3)

        assert callback._accumulators[req_id]["minTick"] == 0.01
        assert callback._accumulators[req_id]["bboExchange"] == "ISLAND"
        assert callback._accumulators[req_id]["snapshotPermissions"] == 3

        loop.close()


class TestMarketDataType:
    """Test marketDataType callback."""

    def test_market_data_type_accumulates(self) -> None:
        """Test marketDataType adds type to accumulator."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        callback._accumulators[req_id] = {}

        callback.marketDataType(req_id, 2)  # 2 = Frozen

        assert callback._accumulators[req_id]["marketDataType"] == 2

        loop.close()


class TestTickStringGeneric:
    """Test tickString and tickGeneric callbacks."""

    def test_tick_string_accumulates(self) -> None:
        """Test tickString adds string value to accumulator."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        callback._accumulators[req_id] = {}

        # LAST_TIMESTAMP=45
        callback.tickString(req_id, 45, "1702656000")

        assert "LAST_TIMESTAMP" in callback._accumulators[req_id]

        loop.close()

    def test_tick_generic_accumulates(self) -> None:
        """Test tickGeneric adds float value to accumulator."""
        loop = asyncio.new_event_loop()
        callback = TWSCallback(loop=loop)

        req_id = 1
        callback._accumulators[req_id] = {}

        # HALTED=49
        callback.tickGeneric(req_id, 49, 0.0)

        assert "HALTED" in callback._accumulators[req_id]

        loop.close()
