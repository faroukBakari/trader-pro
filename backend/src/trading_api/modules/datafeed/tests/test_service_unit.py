"""Unit tests for DatafeedService.

Pure unit tests that test service methods directly without HTTP/WS stack.
Uses MockDatafeedProvider from conftest.py for provider-agnostic testing.

Tests cover:
- REST endpoint delegation (get_configuration, resolve_ticker, get_quotes)
- WebSocket topic management (create_topic, remove_topic for quotes)
- Error handling and recoverability classification
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from trading_api.datastores import create_memory_datastore
from trading_api.models import Bar
from trading_api.models.exceptions import ProviderException, ServiceException
from trading_api.models.market.quotes import QuoteValues
from trading_api.modules.datafeed.service import DatafeedService

from .conftest import MockDatafeedProvider

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_provider() -> MockDatafeedProvider:
    """Create a fresh mock provider for each test."""
    return MockDatafeedProvider()


@pytest.fixture
def service(mock_provider: MockDatafeedProvider) -> DatafeedService:
    """Create DatafeedService with mock provider."""
    module_dir = Path(__file__).parent.parent
    datastore = create_memory_datastore()
    return DatafeedService(
        module_dir, providers=[mock_provider], datastores=[datastore]
    )


# ============================================================================
# get_configuration Tests
# ============================================================================


def test_get_configuration_returns_defaults(service: DatafeedService) -> None:
    """Test get_configuration returns default DatafeedConfiguration."""
    config = service.get_configuration()

    # Verify configuration has expected fields
    assert config is not None
    assert hasattr(config, "supported_resolutions")
    assert hasattr(config, "exchanges")


# ============================================================================
# resolve_ticker Tests
# ============================================================================


@pytest.mark.asyncio
async def test_resolve_ticker_delegates_to_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test resolve_ticker delegates to datafeed provider."""
    result = await service.resolve_ticker("AAPL:NASDAQ")

    # Verify provider was called
    assert len(mock_provider.calls["get_symbol_info"]) == 1
    call = mock_provider.calls["get_symbol_info"][0]
    assert call["ticker_name"] == "AAPL:NASDAQ"
    assert "timeout" in call

    # Verify result
    assert result is not None
    assert result.name == "AAPL"
    assert result.ticker == "AAPL:NASDAQ"


@pytest.mark.asyncio
async def test_resolve_ticker_returns_none_when_provider_raises(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test resolve_ticker handles provider exception gracefully."""
    # Configure mock to raise exception (symbol not found)
    mock_provider.raise_exception["get_symbol_info"] = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
        message="Symbol not found",
    )

    # Should raise the exception
    with pytest.raises(ProviderException) as exc_info:
        await service.resolve_ticker("UNKNOWN")

    assert exc_info.value.code == "PROVIDER_DATAFEED_SYMBOL_NOT_FOUND"


# ============================================================================
# get_quotes Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_quotes_delegates_to_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test get_quotes delegates to datafeed provider."""
    tickers = ["AAPL", "GOOGL"]

    results = await service.get_quotes(tickers)

    # Verify provider was called with correct tickers
    assert len(mock_provider.calls["get_quotes_snapshot"]) == 1
    call = mock_provider.calls["get_quotes_snapshot"][0]
    assert call["ticker_names"] == tickers
    assert "timeout" in call

    # Verify results
    assert len(results) == 2


@pytest.mark.asyncio
async def test_get_quotes_fallback_uses_cached_bars(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test get_quotes uses cached bars as fallback when provider fails."""
    # First, populate cache by calling get_bars
    mock_bars = [
        Bar(
            time=1700000000000,
            open=150.0,
            high=151.0,
            low=149.0,
            close=150.5,
            volume=1000,
            count=10,
        )
    ]
    mock_provider.return_values["get_historical_bars"] = mock_bars

    # Get bars to populate cache
    from trading_api.models.market import Resolution

    await service.get_bars(
        ticker="AAPL",
        resolution=Resolution.DAY_1,
        from_time=1700000000000,
        to_time=1700100000000,
        count_back=None,
    )

    # Now configure provider to raise exception on get_quotes
    mock_provider.raise_exception["get_quotes_snapshot"] = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="PROVIDER_DATAFEED_TIMEOUT",
        message="Connection timeout",
    )

    # get_quotes should fallback to cached data
    results = await service.get_quotes(["AAPL"])

    assert len(results) == 1
    assert results[0].n == "AAPL"
    assert isinstance(results[0].v, QuoteValues)
    assert results[0].v.lp == 150.5  # close price from cached bar


@pytest.mark.asyncio
async def test_get_quotes_reraises_when_no_cached_data(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test get_quotes reraises exception when no cached data available."""
    # Configure provider to raise exception
    mock_provider.raise_exception["get_quotes_snapshot"] = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="PROVIDER_DATAFEED_TIMEOUT",
        message="Connection timeout",
    )

    # Should reraise since no cached data for UNKNOWN ticker
    with pytest.raises(ProviderException) as exc_info:
        await service.get_quotes(["UNKNOWN"])

    assert exc_info.value.code == "PROVIDER_DATAFEED_TIMEOUT"


# ============================================================================
# create_topic (quotes) Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_topic_quotes_subscribes_to_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test create_topic for quotes subscribes to market data via provider."""
    topic = 'quotes:{"fast_symbols":[],"symbols":["AAPL","GOOGL"]}'
    topic_update = AsyncMock()
    topic_error = AsyncMock()

    await service.create_topic(topic, topic_update, topic_error, user_id="test-user")

    # Verify provider was called for each symbol
    assert len(mock_provider.calls["subscribe_market_data"]) == 2
    subscribed_tickers = [
        call["ticker_name"] for call in mock_provider.calls["subscribe_market_data"]
    ]
    assert set(subscribed_tickers) == {"AAPL", "GOOGL"}


@pytest.mark.asyncio
async def test_create_topic_quotes_multiple_topics_call_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test each topic subscribes via provider (mutualization delegated to tracker)."""
    # Create first topic with AAPL
    topic1 = 'quotes:{"fast_symbols":[],"symbols":["AAPL"]}'
    await service.create_topic(topic1, AsyncMock(), AsyncMock(), user_id="test-user")

    # Create second topic also with AAPL
    topic2 = 'quotes:{"fast_symbols":["AAPL"],"symbols":[]}'
    await service.create_topic(topic2, AsyncMock(), AsyncMock(), user_id="test-user")

    # Service calls provider for each topic - tracker handles mutualization
    assert len(mock_provider.calls["subscribe_market_data"]) == 2


@pytest.mark.asyncio
async def test_create_topic_quotes_no_symbols_raises_error(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test create_topic raises error when no symbols provided."""
    topic = 'quotes:{"fast_symbols":[],"symbols":[]}'

    with pytest.raises(ServiceException) as exc_info:
        await service.create_topic(topic, AsyncMock(), AsyncMock(), user_id="test-user")

    assert exc_info.value.code == "SERVICE_DATAFEED_NO_SYMBOLS"


# ============================================================================
# remove_topic (quotes) Tests
# ============================================================================


@pytest.mark.asyncio
async def test_remove_topic_quotes_unsubscribes_from_provider(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test remove_topic for quotes unsubscribes from provider."""
    topic = 'quotes:{"fast_symbols":[],"symbols":["AAPL"]}'
    await service.create_topic(topic, AsyncMock(), AsyncMock(), user_id="test-user")

    # Verify subscribed
    assert len(mock_provider.calls["subscribe_market_data"]) == 1

    # Remove topic
    service.remove_topic(topic)

    # Verify unsubscribed
    assert len(mock_provider.calls["unsubscribe_market_data"]) == 1


@pytest.mark.asyncio
async def test_remove_topic_quotes_unsubscribes_each_topic(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test each topic removal unsubscribes via provider (tracker handles refcount)."""
    # Create two topics with AAPL
    topic1 = 'quotes:{"fast_symbols":[],"symbols":["AAPL"]}'
    topic2 = 'quotes:{"fast_symbols":["AAPL"],"symbols":[]}'
    await service.create_topic(topic1, AsyncMock(), AsyncMock(), user_id="test-user")
    await service.create_topic(topic2, AsyncMock(), AsyncMock(), user_id="test-user")

    # Remove first topic - service unsubscribes (tracker handles actual cleanup)
    service.remove_topic(topic1)
    assert len(mock_provider.calls["unsubscribe_market_data"]) == 1

    # Remove second topic
    service.remove_topic(topic2)
    assert len(mock_provider.calls["unsubscribe_market_data"]) == 2


# ============================================================================
# create_topic Error Cases
# ============================================================================


@pytest.mark.asyncio
async def test_create_topic_duplicate_raises_error(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test create_topic raises error for duplicate topic."""
    topic = 'bars:{"resolution":"1","symbol":"AAPL"}'
    await service.create_topic(topic, AsyncMock(), AsyncMock(), user_id="test-user")

    # Try to create same topic again
    with pytest.raises(ServiceException) as exc_info:
        await service.create_topic(topic, AsyncMock(), AsyncMock(), user_id="test-user")

    assert exc_info.value.code == "SERVICE_DATAFEED_TOPIC_EXISTS"


@pytest.mark.asyncio
async def test_create_topic_invalid_format_raises_error(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test create_topic raises error for invalid topic format."""
    # Missing colon separator
    topic = "bars_invalid_no_colon"

    with pytest.raises(ServiceException) as exc_info:
        await service.create_topic(topic, AsyncMock(), AsyncMock(), user_id="test-user")

    assert exc_info.value.code == "SERVICE_DATAFEED_INVALID_TOPIC_FORMAT"


@pytest.mark.asyncio
async def test_create_topic_unknown_type_raises_error(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test create_topic raises error for unknown topic type."""
    topic = 'unknown:{"symbol":"AAPL"}'

    with pytest.raises(ServiceException) as exc_info:
        await service.create_topic(topic, AsyncMock(), AsyncMock(), user_id="test-user")

    assert exc_info.value.code == "SERVICE_DATAFEED_UNKNOWN_TOPIC_TYPE"


# ============================================================================
# Error Recoverability Tests (Step 4)
# ============================================================================


@pytest.mark.asyncio
async def test_error_recoverable_explicit_codes(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test explicit recoverable error codes keep connection open."""
    topic = 'bars:{"resolution":"1","symbol":"AAPL"}'
    topic_error = AsyncMock()

    await service.create_topic(topic, AsyncMock(), topic_error, user_id="test-user")

    # Get subscription ID from mock
    sub_id = mock_provider.calls["subscribe_realtime_bars"][0]["sub_id"]

    # Trigger recoverable error
    recoverable_exc = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="PROVIDER_DATAFEED_TIMEOUT",
        message="Request timeout",
    )
    await mock_provider.trigger_error(sub_id, recoverable_exc)

    # Verify topic_error was called with recoverable=True
    topic_error.assert_called_once()
    call_args = topic_error.call_args
    assert call_args[0][0] == recoverable_exc  # exception
    assert call_args[0][1] is True  # recoverable
    assert call_args[0][2] == 5000  # retry_after_ms


@pytest.mark.asyncio
async def test_error_non_recoverable_unknown_code(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test unknown error codes are non-recoverable."""
    topic = 'bars:{"resolution":"1","symbol":"AAPL"}'
    topic_error = AsyncMock()

    await service.create_topic(topic, AsyncMock(), topic_error, user_id="test-user")

    # Get subscription ID from mock
    sub_id = mock_provider.calls["subscribe_realtime_bars"][0]["sub_id"]

    # Trigger non-recoverable error (unknown code)
    non_recoverable_exc = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="UNKNOWN_ERROR_CODE",
        message="Something went wrong",
    )
    await mock_provider.trigger_error(sub_id, non_recoverable_exc)

    # Verify topic_error was called with recoverable=False
    topic_error.assert_called_once()
    call_args = topic_error.call_args
    assert call_args[0][0] == non_recoverable_exc  # exception
    assert call_args[0][1] is False  # recoverable
    assert call_args[0][2] is None  # retry_after_ms


@pytest.mark.asyncio
async def test_tws_api_error_suffix_classification(
    service: DatafeedService, mock_provider: MockDatafeedProvider
) -> None:
    """Test PROVIDER_TWS_API_* codes use suffix-based classification."""
    topic = 'bars:{"resolution":"1","symbol":"AAPL"}'
    topic_error = AsyncMock()

    await service.create_topic(topic, AsyncMock(), topic_error, user_id="test-user")
    sub_id = mock_provider.calls["subscribe_realtime_bars"][0]["sub_id"]

    # Test 1: TWS API error without _NON_RECOVERABLE suffix → recoverable
    tws_recoverable = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="PROVIDER_TWS_API_MARKET_DATA_123",
        message="TWS market data error",
    )
    await mock_provider.trigger_error(sub_id, tws_recoverable)

    assert topic_error.call_args[0][1] is True  # recoverable

    # Reset for next test
    topic_error.reset_mock()

    # Test 2: TWS API error WITH _NON_RECOVERABLE suffix → non-recoverable
    tws_non_recoverable = ProviderException(
        provider="mock_tws",
        capability="datafeed",
        code="PROVIDER_TWS_API_MARKET_DATA_123_NON_RECOVERABLE",
        message="TWS fatal error",
    )
    await mock_provider.trigger_error(sub_id, tws_non_recoverable)

    assert topic_error.call_args[0][1] is False  # non-recoverable
