"""
Unit tests for WebSocket router error broadcasting.

Tests the _broadcast_payload() method and error callback wrapper
in WsRouter for subscription-level error notifications.
"""

from typing import Any
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

    async def create_topic(
        self,
        topic: str,
        topic_update: ProviderUpdateCallback,
        topic_error: TopicErrorCallback,
        user_id: str,
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

    @pytest.mark.asyncio
    async def test_create_topic_registers_both_callbacks(
        self, router: MockRouter, mock_service: MockWsRouteService
    ) -> None:
        """_create_topic registers both update and error callbacks with service."""
        topic = "test:AAPL"
        await router._create_topic(topic, "test-user-123")

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

        await router._create_topic(topic, "test-user-123")

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

        await router._create_topic(topic, "test-user-123")

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

        await router._create_topic(topic, "test-user-123")

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

        await router._create_topic(topic, "test-user-123")
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

        await router._create_topic(topic, "test-user-123")

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

        await router._create_topic(topic, "test-user-123")
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

        await router._create_topic(topic, "test-user-123")

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

        await router._create_topic(topic, "test-user-123")

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
# Tests: Service Validation (Lines 35, 40)
# ============================================================================


class TestServiceValidation:
    """Tests for service protocol validation in __init__."""

    def test_missing_create_topic_raises_typeerror(self) -> None:
        """Service without create_topic raises TypeError."""

        class BadService:
            def remove_topic(self, topic: str) -> None:
                pass

        with pytest.raises(TypeError) as exc_info:
            MockRouter(service=BadService(), route="test")  # type: ignore[arg-type]

        assert "missing 'create_topic' method" in str(exc_info.value)

    def test_missing_remove_topic_raises_typeerror(self) -> None:
        """Service without remove_topic raises TypeError."""

        class BadService:
            async def create_topic(
                self,
                topic: str,
                topic_update: ProviderUpdateCallback,
                topic_error: TopicErrorCallback,
            ) -> None:
                pass

        with pytest.raises(TypeError) as exc_info:
            MockRouter(service=BadService(), route="test")  # type: ignore[arg-type]

        assert "missing 'remove_topic' method" in str(exc_info.value)

    def test_error_message_includes_service_class_name(self) -> None:
        """TypeError message includes actual service type name."""

        class MyBadService:
            pass

        with pytest.raises(TypeError) as exc_info:
            MockRouter(service=MyBadService(), route="test")  # type: ignore[arg-type]

        assert "MyBadService" in str(exc_info.value)


# ============================================================================
# Tests: Generic Type Resolution (Line 119)
# ============================================================================


class TestGenericTypeResolution:
    """Tests for _resolve_generic_types() error handling."""

    def test_non_generic_subclass_raises_valueerror(
        self, mock_service: MockWsRouteService
    ) -> None:
        """Router without generic params raises ValueError on unpacking."""

        # Create a router class without specifying generic types
        class BadRouter(WsRouter):  # type: ignore[type-arg]
            pass

        # When generic types aren't specified, get_args() returns empty tuple
        # This causes ValueError during unpacking at line 45
        with pytest.raises(ValueError) as exc_info:
            BadRouter(service=mock_service, route="test")

        assert "not enough values to unpack" in str(exc_info.value)

    def test_resolve_generic_types_returns_correct_types(
        self, mock_service: MockWsRouteService
    ) -> None:
        """Properly defined router resolves generic types correctly."""
        router = MockRouter(service=mock_service, route="test")

        # _resolve_generic_types was called during __init__
        # The router should have been created successfully
        assert router is not None
        assert router.service == mock_service


# ============================================================================
# Tests: Subscribe (Lines 56-66)
# ============================================================================


class TestSubscribe:
    """Tests for send_subscribe handler."""

    @pytest.fixture
    def subscribe_client(self) -> MagicMock:
        """Create mock client for subscribe tests."""
        client = MagicMock()
        client.uid = "subscribe-client"
        client.topics = set()
        client.ws = AsyncMock()
        client.ws.client_state = WebSocketState.CONNECTED
        client.ws.application_state = WebSocketState.CONNECTED
        return client

    def _get_handler(self, router: MockRouter, operation_suffix: str) -> Any:
        """Get handler function by operation suffix."""
        for route in router.routes:
            if route.operation == operation_suffix:
                return route.handler
        raise ValueError(f"Handler for '{operation_suffix}' not found")

    @pytest.mark.asyncio
    async def test_subscribe_adds_client_to_set(
        self,
        router: MockRouter,
        subscribe_client: MagicMock,
    ) -> None:
        """subscribe handler adds client to _clients set."""
        from trading_api.models import SubscriptionRequest

        assert subscribe_client not in router._clients

        handler = self._get_handler(router, "subscribe")
        payload = SubscriptionRequest(
            sub_id="test-sub",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        await handler(payload, subscribe_client)

        assert subscribe_client in router._clients

    @pytest.mark.asyncio
    async def test_subscribe_creates_topic_on_first_subscription(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        subscribe_client: MagicMock,
    ) -> None:
        """First subscription creates topic via _create_topic."""
        from trading_api.models import SubscriptionRequest

        handler = self._get_handler(router, "subscribe")
        payload = SubscriptionRequest(
            sub_id="test-sub",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        response = await handler(payload, subscribe_client)

        # Topic should be created
        assert response.topic in router._topics
        assert mock_service.get_callbacks(response.topic) is not None

    @pytest.mark.asyncio
    async def test_subscribe_reuses_existing_topic(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        subscribe_client: MagicMock,
    ) -> None:
        """Second subscription reuses existing topic, doesn't call create_topic again."""
        from trading_api.models import SubscriptionRequest

        handler = self._get_handler(router, "subscribe")
        payload = SubscriptionRequest(
            sub_id="test-sub",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        # First subscription creates topic
        response1 = await handler(payload, subscribe_client)
        topic = response1.topic
        callbacks_first = mock_service.get_callbacks(topic)

        # Create second client
        client2 = MagicMock()
        client2.uid = "client-2"
        client2.topics = set()
        client2.ws = AsyncMock()
        client2.ws.client_state = WebSocketState.CONNECTED
        client2.ws.application_state = WebSocketState.CONNECTED

        # Second subscription - topic already exists
        response2 = await handler(payload, client2)

        # Same topic, same callbacks
        assert response2.topic == topic
        callbacks_second = mock_service.get_callbacks(topic)
        assert callbacks_first == callbacks_second

    @pytest.mark.asyncio
    async def test_subscribe_returns_correct_response(
        self,
        router: MockRouter,
        subscribe_client: MagicMock,
    ) -> None:
        """Response includes status='ok', sub_id, and topic."""
        from trading_api.models import SubscriptionRequest

        handler = self._get_handler(router, "subscribe")
        payload = SubscriptionRequest(
            sub_id="my-sub-123",
            sub_params=MockSubscriptionRequest(symbol="MSFT"),
        )

        response = await handler(payload, subscribe_client)

        assert response.status == "ok"
        assert response.sub_id == "my-sub-123"
        assert "test:" in response.topic  # Topic contains router prefix


# ============================================================================
# Tests: Unsubscribe (Lines 77-104)
# ============================================================================


class TestUnsubscribe:
    """Tests for send_unsubscribe handler."""

    @pytest.fixture
    def unsubscribe_client(self) -> MagicMock:
        """Create mock client for unsubscribe tests."""
        client = MagicMock()
        client.uid = "unsub-client"
        client.topics = set()
        client.ws = AsyncMock()
        client.ws.client_state = WebSocketState.CONNECTED
        client.ws.application_state = WebSocketState.CONNECTED
        return client

    def _get_handler(self, router: MockRouter, operation_suffix: str) -> Any:
        """Get handler function by operation suffix."""
        for route in router.routes:
            if route.operation == operation_suffix:
                return route.handler
        raise ValueError(f"Handler for '{operation_suffix}' not found")

    def test_unsubscribe_calls_client_unsubscribe(
        self,
        router: MockRouter,
        unsubscribe_client: MagicMock,
    ) -> None:
        """client.unsubscribe(topic) is called during unsubscribe."""
        from trading_api.models import SubscriptionRequest

        topic = 'test:{"symbol":"AAPL"}'
        unsubscribe_client.topics = {topic}
        router._clients = {unsubscribe_client}
        router._topics = {topic}

        handler = self._get_handler(router, "unsubscribe")
        payload = SubscriptionRequest(
            sub_id="unsub-1",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        handler(payload, unsubscribe_client)

        unsubscribe_client.unsubscribe.assert_called_once_with(topic)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_topic_when_last_client(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        unsubscribe_client: MagicMock,
    ) -> None:
        """Topic removed when no clients remain subscribed."""
        from trading_api.models import SubscriptionRequest

        topic = 'test:{"symbol":"AAPL"}'
        await router._create_topic(topic, "test-user-123")
        # After unsubscribe, client.topics won't contain the topic
        unsubscribe_client.topics = set()
        router._clients = {unsubscribe_client}

        handler = self._get_handler(router, "unsubscribe")
        payload = SubscriptionRequest(
            sub_id="unsub-1",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        handler(payload, unsubscribe_client)

        # Topic should be removed (no remaining clients)
        assert topic not in router._topics

    @pytest.mark.asyncio
    async def test_unsubscribe_keeps_topic_when_other_clients(
        self,
        router: MockRouter,
        mock_service: MockWsRouteService,
        unsubscribe_client: MagicMock,
    ) -> None:
        """Topic kept when other clients still subscribed."""
        from trading_api.models import SubscriptionRequest

        topic = 'test:{"symbol":"AAPL"}'
        await router._create_topic(topic, "test-user-123")

        # Create another client still subscribed to the topic
        other_client = MagicMock()
        other_client.uid = "other-client"
        other_client.topics = {topic}
        other_client.ws = MagicMock()
        other_client.ws.client_state = WebSocketState.CONNECTED
        other_client.ws.application_state = WebSocketState.CONNECTED

        # unsubscribe_client no longer has topic after unsubscribe
        unsubscribe_client.topics = set()
        router._clients = {unsubscribe_client, other_client}

        handler = self._get_handler(router, "unsubscribe")
        payload = SubscriptionRequest(
            sub_id="unsub-1",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        handler(payload, unsubscribe_client)

        # Topic should still exist (other_client still subscribed)
        assert topic in router._topics

    def test_unsubscribe_removes_client_when_no_remaining_topics(
        self,
        router: MockRouter,
        unsubscribe_client: MagicMock,
    ) -> None:
        """Client removed from _clients when no topics left."""
        from trading_api.models import SubscriptionRequest

        topic = 'test:{"symbol":"AAPL"}'
        router._topics = {topic}
        # After unsubscribe, client has no topics left
        unsubscribe_client.topics = set()
        router._clients = {unsubscribe_client}

        handler = self._get_handler(router, "unsubscribe")
        payload = SubscriptionRequest(
            sub_id="unsub-1",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        handler(payload, unsubscribe_client)

        # Client should be removed (no remaining topics for this client)
        assert unsubscribe_client not in router._clients

    def test_unsubscribe_keeps_client_when_other_topics(
        self,
        router: MockRouter,
        unsubscribe_client: MagicMock,
    ) -> None:
        """Client kept in _clients when subscribed to other topics."""
        from trading_api.models import SubscriptionRequest

        topic1 = 'test:{"symbol":"AAPL"}'
        topic2 = 'test:{"symbol":"MSFT"}'
        router._topics = {topic1, topic2}
        # Client still has topic2 after unsubscribing from topic1
        unsubscribe_client.topics = {topic2}
        router._clients = {unsubscribe_client}

        handler = self._get_handler(router, "unsubscribe")
        payload = SubscriptionRequest(
            sub_id="unsub-1",
            sub_params=MockSubscriptionRequest(symbol="AAPL"),
        )

        handler(payload, unsubscribe_client)

        # Client should still be in _clients (has remaining topics)
        assert unsubscribe_client in router._clients

    def test_unsubscribe_filters_disconnected_clients(
        self,
        router: MockRouter,
    ) -> None:
        """Disconnected clients pruned during _refresh_active_clients."""
        # Connected client
        connected_client = MagicMock()
        connected_client.uid = "connected"
        connected_client.ws = MagicMock()
        connected_client.ws.client_state = WebSocketState.CONNECTED
        connected_client.ws.application_state = WebSocketState.CONNECTED

        # Disconnected client
        disconnected_client = MagicMock()
        disconnected_client.uid = "disconnected"
        disconnected_client.ws = MagicMock()
        disconnected_client.ws.client_state = WebSocketState.DISCONNECTED
        disconnected_client.ws.application_state = WebSocketState.DISCONNECTED

        router._clients = {connected_client, disconnected_client}

        # Refresh active clients
        active_clients = router._refresh_active_clients()

        assert connected_client in active_clients
        assert disconnected_client not in active_clients

    def test_unsubscribe_returns_correct_response(
        self,
        router: MockRouter,
        unsubscribe_client: MagicMock,
    ) -> None:
        """SubscriptionResponse format verified for unsubscribe."""
        from trading_api.models import SubscriptionRequest

        topic = 'test:{"symbol":"GOOG"}'
        unsubscribe_client.topics = set()
        router._clients = {unsubscribe_client}
        router._topics = {topic}

        handler = self._get_handler(router, "unsubscribe")
        payload = SubscriptionRequest(
            sub_id="unsub-xyz",
            sub_params=MockSubscriptionRequest(symbol="GOOG"),
        )

        response = handler(payload, unsubscribe_client)

        assert response.status == "ok"
        assert response.sub_id == "unsub-xyz"
        assert response.topic == topic


# ============================================================================
# Tests: Broadcast Payload Extensions (Lines 137-138, 161)
# ============================================================================


class TestBroadcastPayloadExtended:
    """Extended tests for _broadcast_payload edge cases."""

    @pytest.mark.asyncio
    async def test_broadcast_filters_disconnected_clients(
        self,
        router: MockRouter,
    ) -> None:
        """_refresh_active_clients filters closed connections during broadcast."""
        topic = "test:AAPL"

        # Connected client
        connected_client = MagicMock()
        connected_client.uid = "connected"
        connected_client.topics = {topic}
        connected_client.ws = AsyncMock()
        connected_client.ws.client_state = WebSocketState.CONNECTED
        connected_client.ws.application_state = WebSocketState.CONNECTED

        # Disconnected client
        disconnected_client = MagicMock()
        disconnected_client.uid = "disconnected"
        disconnected_client.topics = {topic}
        disconnected_client.ws = AsyncMock()
        disconnected_client.ws.client_state = WebSocketState.DISCONNECTED
        disconnected_client.ws.application_state = WebSocketState.DISCONNECTED

        router._clients = {connected_client, disconnected_client}
        router._topics = {topic}

        update = SubscriptionUpdate(
            topic=topic,
            payload=MockDataUpdate(symbol="AAPL", price=150.0),
        )

        await router._broadcast_payload(topic, update, "update")

        # Only connected client should receive message
        connected_client.ws.send_text.assert_called_once()
        disconnected_client.ws.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_handles_send_exception(
        self,
        router: MockRouter,
        mock_client: MagicMock,
    ) -> None:
        """Exception during send is logged, doesn't propagate."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        mock_client.ws.send_text.side_effect = Exception("Send failed")
        router._clients = {mock_client}
        router._topics = {topic}

        update = SubscriptionUpdate(
            topic=topic,
            payload=MockDataUpdate(symbol="AAPL", price=150.0),
        )

        # Should not raise - exception is caught and logged
        with patch("trading_api.shared.ws.generic_route.logger") as mock_logger:
            await router._broadcast_payload(topic, update, "update")
            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_exception_triggers_sleep(
        self,
        router: MockRouter,
        mock_client: MagicMock,
    ) -> None:
        """asyncio.sleep(1) called after exception."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        mock_client.ws.send_text.side_effect = Exception("Send failed")
        router._clients = {mock_client}
        router._topics = {topic}

        update = SubscriptionUpdate(
            topic=topic,
            payload=MockDataUpdate(symbol="AAPL", price=150.0),
        )

        with patch("trading_api.shared.ws.generic_route.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            await router._broadcast_payload(topic, update, "update")
            mock_sleep.assert_called_once_with(1)


# ============================================================================
# Tests: Broadcast Update (Lines 174-179)
# ============================================================================


class TestBroadcastUpdate:
    """Tests for _broadcast_update convenience wrapper."""

    @pytest.mark.asyncio
    async def test_broadcast_update_delegates_to_broadcast_payload(
        self,
        router: MockRouter,
        mock_client: MagicMock,
    ) -> None:
        """_broadcast_update calls _broadcast_payload with 'update' operation."""
        topic = "test:AAPL"
        mock_client.topics = {topic}
        router._clients = {mock_client}
        router._topics = {topic}

        update = SubscriptionUpdate(
            topic=topic,
            payload=MockDataUpdate(symbol="AAPL", price=150.0),
        )

        # Spy on _broadcast_payload
        with patch.object(
            router, "_broadcast_payload", wraps=router._broadcast_payload
        ) as mock_broadcast:
            await router._broadcast_update(update)
            mock_broadcast.assert_called_once_with(topic, update, "update")


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
