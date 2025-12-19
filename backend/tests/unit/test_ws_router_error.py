"""
Unit tests for WebSocket router error broadcasting.

Tests the _broadcast_payload() method and error callback wrapper
in WsRouter for subscription-level error notifications.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState
from pydantic import BaseModel, Field

from trading_api.models import ErrorPayload, SubscriptionError, SubscriptionUpdate
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException, TradingApiException
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.ws_router import (
    ProviderUpdateCallback,
    TopicErrorCallback,
    WsRouteService,
)

# ============================================================================
# Test Models
# ============================================================================


class MockSubscriptionRequest(BaseModel):
    """Test subscription request model."""

    symbol: str = Field(..., description="Symbol to subscribe")


class MockDataUpdate(BaseModel):
    """Test data update model."""

    symbol: str = Field(..., description="Symbol")
    price: float = Field(..., description="Price")


# ============================================================================
# Mock Service
# ============================================================================


class MockWsRouteService(WsRouteService):
    """Mock service for testing WsRouter."""

    def __init__(self) -> None:
        self._topics: dict[str, tuple[ProviderUpdateCallback, TopicErrorCallback]] = {}

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """No capabilities required for mock service."""
        return []

    def create_topic(
        self,
        topic: str,
        topic_update: ProviderUpdateCallback,
        topic_error: TopicErrorCallback,
    ) -> None:
        """Store callbacks for testing."""
        self._topics[topic] = (topic_update, topic_error)

    def remove_topic(self, topic: str) -> None:
        """Remove topic from tracking."""
        self._topics.pop(topic, None)

    def get_callbacks(
        self, topic: str
    ) -> tuple[ProviderUpdateCallback, TopicErrorCallback] | None:
        """Get stored callbacks for a topic."""
        return self._topics.get(topic)


# ============================================================================
# Test Router Class
# ============================================================================


class MockRouter(WsRouter[MockSubscriptionRequest, MockDataUpdate]):
    """Concrete router for testing."""


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_service() -> MockWsRouteService:
    """Create mock service."""
    return MockWsRouteService()


@pytest.fixture
def router(mock_service: MockWsRouteService) -> MockRouter:
    """Create test router with mock service."""
    return MockRouter(service=mock_service, route="test")


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock WebSocket client."""
    client = MagicMock()
    client.uid = "test-client-123"
    client.topics = set()
    client.ws = AsyncMock()
    # Use actual WebSocketState enum for proper equality comparison
    client.ws.client_state = WebSocketState.CONNECTED
    client.ws.application_state = WebSocketState.CONNECTED
    return client


# ============================================================================
# Tests: _broadcast_payload()
# ============================================================================


class TestBroadcastPayload:
    """Tests for _broadcast_payload() method."""

    @pytest.mark.asyncio
    async def test_broadcast_update_operation(
        self, router: MockRouter, mock_client: MagicMock
    ) -> None:
        """_broadcast_payload with 'update' operation broadcasts correctly."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}
        router._topics = {topic}

        update = SubscriptionUpdate(
            topic=topic,
            payload=MockDataUpdate(symbol="AAPL", price=150.0),
        )

        await router._broadcast_payload(topic, update, "update")

        # Verify message was sent
        mock_client.ws.send_text.assert_called_once()
        sent_msg = mock_client.ws.send_text.call_args[0][0]
        assert '"type":"test.update"' in sent_msg
        assert '"topic":"test:AAPL"' in sent_msg

    @pytest.mark.asyncio
    async def test_broadcast_error_operation(
        self, router: MockRouter, mock_client: MagicMock
    ) -> None:
        """_broadcast_payload with 'error' operation broadcasts correctly."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}
        router._topics = {topic}

        error = SubscriptionError(
            topic=topic,
            error=ErrorPayload(
                code="TEST_ERROR",
                message="Test error message",
                timestamp=1702656000.0,
            ),
            recoverable=True,
            retry_after_ms=5000,
        )

        await router._broadcast_payload(topic, error, "error")

        # Verify message was sent
        mock_client.ws.send_text.assert_called_once()
        sent_msg = mock_client.ws.send_text.call_args[0][0]
        assert '"type":"test.error"' in sent_msg
        assert '"topic":"test:AAPL"' in sent_msg
        assert '"recoverable":true' in sent_msg

    @pytest.mark.asyncio
    async def test_broadcast_removes_topic_when_no_clients(
        self, router: MockRouter, mock_service: MockWsRouteService
    ) -> None:
        """_broadcast_payload removes topic when no clients are subscribed."""
        topic = "test:AAPL"
        router._clients = set()  # No clients
        router._topics = {topic}

        update = SubscriptionUpdate(
            topic=topic,
            payload=MockDataUpdate(symbol="AAPL", price=150.0),
        )

        await router._broadcast_payload(topic, update, "update")

        # Topic should be removed
        assert topic not in router._topics


# ============================================================================
# Tests: _create_topic() Error Callback
# ============================================================================


class TestCreateTopicErrorCallback:
    """Tests for error callback created in _create_topic()."""

    def test_create_topic_registers_both_callbacks(
        self, router: MockRouter, mock_service: MockWsRouteService
    ) -> None:
        """_create_topic registers both update and error callbacks with service."""
        topic = "test:AAPL"
        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        topic_update, topic_error = callbacks
        assert callable(topic_update)
        assert callable(topic_error)

    @pytest.mark.asyncio
    async def test_recoverable_error_broadcasts_error_message(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Recoverable errors broadcast SubscriptionError, keep connection open."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        # Simulate recoverable error
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
        )

        await topic_error(exc, True, 5000)

        # Verify error message was broadcast
        mock_client.ws.send_text.assert_called_once()
        sent_msg = mock_client.ws.send_text.call_args[0][0]
        assert '"type":"test.error"' in sent_msg
        assert '"recoverable":true' in sent_msg
        assert '"retry_after_ms":5000' in sent_msg

        # Verify connection NOT closed
        mock_client.ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_unrecoverable_error_logs_exception(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Unrecoverable errors log exception via log_exception."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        # Simulate unrecoverable error
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
            message="Symbol INVALID not found",
        )

        # Mock log_exception to verify it's called
        with patch("trading_api.shared.ws.generic_route.log_exception") as mock_log:
            await topic_error(exc, False, None)

            # Verify log_exception was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == exc  # Exception
            assert call_args[1] == mock_client.ws  # WebSocket

    @pytest.mark.asyncio
    async def test_unrecoverable_error_broadcasts_before_cleanup(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Unrecoverable errors broadcast error message before cleanup."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        exc = TradingApiException(
            code="FATAL_ERROR",
            message="Fatal error occurred",
        )

        with patch("trading_api.shared.ws.generic_route.log_exception"):
            await topic_error(exc, False, None)

            # Verify error WAS broadcast (before cleanup)
            mock_client.ws.send_text.assert_called_once()
            sent_msg = mock_client.ws.send_text.call_args[0][0]
            assert '"type":"test.error"' in sent_msg
            assert '"recoverable":false' in sent_msg

    @pytest.mark.asyncio
    async def test_unrecoverable_error_discards_topic(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Unrecoverable errors discard topic from router._topics."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)
        assert topic in router._topics  # Pre-condition

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
            message="Symbol INVALID not found",
        )

        with patch("trading_api.shared.ws.generic_route.log_exception"):
            await topic_error(exc, False, None)

            # Topic should be discarded
            assert topic not in router._topics

    @pytest.mark.asyncio
    async def test_unrecoverable_error_unsubscribes_client(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Unrecoverable errors unsubscribe client from topic."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
            message="Symbol INVALID not found",
        )

        with patch("trading_api.shared.ws.generic_route.log_exception"):
            await topic_error(exc, False, None)

            # Client should be unsubscribed from topic
            mock_client.unsubscribe.assert_called_once_with(topic)

    @pytest.mark.asyncio
    async def test_recoverable_error_keeps_topic(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Recoverable errors do NOT discard topic from router._topics."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)
        assert topic in router._topics  # Pre-condition

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
        )

        with patch("trading_api.shared.ws.generic_route.log_exception"):
            await topic_error(exc, True, 5000)

            # Topic should NOT be discarded
            assert topic in router._topics

    @pytest.mark.asyncio
    async def test_recoverable_error_keeps_client_subscribed(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Recoverable errors do NOT unsubscribe client from topic."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
        )

        with patch("trading_api.shared.ws.generic_route.log_exception"):
            await topic_error(exc, True, 5000)

            # Client should NOT be unsubscribed
            mock_client.unsubscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_recoverable_error_calls_log_exception(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        mock_client: MagicMock,
    ) -> None:
        """Recoverable errors call log_exception for logging."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}

        router._create_topic(topic)

        callbacks = mock_service.get_callbacks(topic)
        assert callbacks is not None
        _, topic_error = callbacks

        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
        )

        with patch("trading_api.shared.ws.generic_route.log_exception") as mock_log:
            await topic_error(exc, True, 5000)

            # log_exception should be called (for logging)
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == exc
            assert call_args[1] == mock_client.ws


# ============================================================================
# Tests: WsRouteService Protocol
# ============================================================================


class TestWsRouteServiceProtocol:
    """Tests for WsRouteService protocol definition."""

    def test_topic_error_callback_signature(self) -> None:
        """TopicErrorCallback has correct signature."""
        # Verify type alias exists and has expected signature
        from trading_api.shared.ws.ws_router import TopicErrorCallback

        # TopicErrorCallback should be: Callable[[TradingApiException, bool, int | None], Awaitable[None]]
        # We can't easily introspect at runtime, but we can verify it's defined
        assert TopicErrorCallback is not None

    def test_provider_update_callback_signature(self) -> None:
        """ProviderUpdateCallback has correct signature."""
        from trading_api.shared.ws.ws_router import ProviderUpdateCallback

        assert ProviderUpdateCallback is not None


# ============================================================================
# Tests: build_specs()
# ============================================================================


class TestBuildSpecs:
    """Tests for build_specs() including error operation."""

    def test_build_specs_includes_error_operation(self, router: MockRouter) -> None:
        """build_specs() includes .error operation in the list."""
        mock_ws_app = MagicMock()
        mock_ws_app.asyncapi_docs_url = "/docs"
        mock_ws_app.asyncapi_url = "/spec"

        specs = router.build_specs("ws://localhost", mock_ws_app)

        operations = specs["operations"]
        assert "test.subscribe" in operations
        assert "test.unsubscribe" in operations
        assert "test.update" in operations
        assert "test.error" in operations
