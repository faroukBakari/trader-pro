"""
Unit tests for error models.

Tests ErrorPayload and SubscriptionError models used for WebSocket
subscription-level error notifications.
"""

from trading_api.models import ErrorPayload, SubscriptionError
from trading_api.models.exceptions import (
    CommonException,
    ProviderException,
    ServiceException,
    TradingApiException,
)


class TestErrorPayload:
    """Tests for ErrorPayload model."""

    def test_from_base_exception(self) -> None:
        """ErrorPayload correctly converts TradingApiException."""
        exc = TradingApiException(
            code="TEST_ERROR",
            message="Test error message",
        )

        payload = ErrorPayload.from_exception(exc)

        assert payload.code == "TEST_ERROR"
        assert payload.message == "Test error message"
        assert payload.timestamp == exc.timestamp
        assert payload.details is None  # Base exception has no extra fields

    def test_from_service_exception_includes_module(self) -> None:
        """ErrorPayload includes module in details for ServiceException."""
        exc = ServiceException(
            module="datafeed",
            code="SERVICE_DATAFEED_INVALID_TOPIC",
            message="Invalid topic format",
        )

        payload = ErrorPayload.from_exception(exc)

        assert payload.code == "SERVICE_DATAFEED_INVALID_TOPIC"
        assert payload.message == "Invalid topic format"
        assert payload.details == {"module": "datafeed"}

    def test_from_provider_exception_includes_provider_and_capability(self) -> None:
        """ErrorPayload includes provider and capability in details for ProviderException."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
        )

        payload = ErrorPayload.from_exception(exc)

        assert payload.code == "PROVIDER_DATAFEED_TIMEOUT"
        assert payload.message == "Request timed out"
        assert payload.details == {"provider": "tws", "capability": "datafeed"}

    def test_from_common_exception(self) -> None:
        """ErrorPayload correctly converts CommonException (no extra details)."""
        exc = CommonException(
            code="COMMON_AUTH_TOKEN_EXPIRED",
            message="Token has expired",
        )

        payload = ErrorPayload.from_exception(exc)

        assert payload.code == "COMMON_AUTH_TOKEN_EXPIRED"
        assert payload.message == "Token has expired"
        assert payload.details is None  # CommonException has no extra fields

    def test_backtrace_excluded(self) -> None:
        """ErrorPayload does not include backtrace (backend-only concern)."""
        exc = TradingApiException(
            code="TEST_ERROR",
            message="Test error",
        )

        payload = ErrorPayload.from_exception(exc)

        # Verify backtrace is not in the serialized output
        payload_dict = payload.model_dump()
        assert "backtrace" not in payload_dict
        assert "backtrace" not in (payload.details or {})

    def test_serialization_to_json(self) -> None:
        """ErrorPayload can be serialized to JSON."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_CONNECTION_LOST",
            message="Connection to TWS lost",
        )

        payload = ErrorPayload.from_exception(exc)
        json_str = payload.model_dump_json()

        # Verify it's valid JSON that can be parsed
        import json

        parsed = json.loads(json_str)
        assert parsed["code"] == "PROVIDER_DATAFEED_CONNECTION_LOST"
        assert parsed["message"] == "Connection to TWS lost"
        assert parsed["details"]["provider"] == "tws"
        assert parsed["details"]["capability"] == "datafeed"

    def test_direct_construction(self) -> None:
        """ErrorPayload can be constructed directly with all fields."""
        payload = ErrorPayload(
            code="CUSTOM_ERROR",
            message="Custom error message",
            timestamp=1702656000.0,
            details={"custom_field": "custom_value"},
        )

        assert payload.code == "CUSTOM_ERROR"
        assert payload.message == "Custom error message"
        assert payload.timestamp == 1702656000.0
        assert payload.details == {"custom_field": "custom_value"}


class TestSubscriptionError:
    """Tests for SubscriptionError model."""

    def test_basic_construction(self) -> None:
        """SubscriptionError can be constructed with required fields."""
        error_payload = ErrorPayload(
            code="TEST_ERROR",
            message="Test error",
            timestamp=1702656000.0,
        )

        sub_error = SubscriptionError(
            topic="bars:AAPL:1",
            error=error_payload,
        )

        assert sub_error.topic == "bars:AAPL:1"
        assert sub_error.error.code == "TEST_ERROR"
        assert sub_error.recoverable is True  # Default value
        assert sub_error.retry_after_ms is None  # Default value

    def test_recoverable_error_with_retry(self) -> None:
        """SubscriptionError can specify recoverable with retry delay."""
        error_payload = ErrorPayload(
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
            timestamp=1702656000.0,
        )

        sub_error = SubscriptionError(
            topic="bars:AAPL:1",
            error=error_payload,
            recoverable=True,
            retry_after_ms=5000,
        )

        assert sub_error.recoverable is True
        assert sub_error.retry_after_ms == 5000

    def test_unrecoverable_error(self) -> None:
        """SubscriptionError can represent unrecoverable errors."""
        error_payload = ErrorPayload(
            code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
            message="Symbol INVALID not found",
            timestamp=1702656000.0,
        )

        sub_error = SubscriptionError(
            topic="bars:INVALID:1",
            error=error_payload,
            recoverable=False,
            retry_after_ms=None,
        )

        assert sub_error.recoverable is False
        assert sub_error.retry_after_ms is None

    def test_serialization_to_json(self) -> None:
        """SubscriptionError can be serialized to JSON for WebSocket transmission."""
        error_payload = ErrorPayload(
            code="PROVIDER_DATAFEED_DATA_GAP",
            message="Gap detected in data stream",
            timestamp=1702656000.0,
            details={"provider": "tws", "capability": "datafeed"},
        )

        sub_error = SubscriptionError(
            topic="bars:AAPL:1",
            error=error_payload,
            recoverable=True,
            retry_after_ms=3000,
        )

        json_str = sub_error.model_dump_json()

        import json

        parsed = json.loads(json_str)
        assert parsed["topic"] == "bars:AAPL:1"
        assert parsed["error"]["code"] == "PROVIDER_DATAFEED_DATA_GAP"
        assert parsed["recoverable"] is True
        assert parsed["retry_after_ms"] == 3000

    def test_integration_with_exception(self) -> None:
        """Full integration: exception → ErrorPayload → SubscriptionError."""
        # Simulate provider error
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_RATE_LIMIT",
            message="Rate limit exceeded, please wait",
        )

        # Convert to payload
        error_payload = ErrorPayload.from_exception(exc)

        # Wrap in subscription error
        sub_error = SubscriptionError(
            topic="quotes:AAPL",
            error=error_payload,
            recoverable=True,
            retry_after_ms=10000,
        )

        # Verify full chain
        assert sub_error.topic == "quotes:AAPL"
        assert sub_error.error.code == "PROVIDER_DATAFEED_RATE_LIMIT"
        assert sub_error.error.details == {"provider": "tws", "capability": "datafeed"}
        assert sub_error.recoverable is True
        assert sub_error.retry_after_ms == 10000


class TestExceptionToDict:
    """Tests for TradingApiException.to_dict() timestamp inclusion."""

    def test_to_dict_includes_timestamp(self) -> None:
        """Verify to_dict() includes timestamp field."""
        exc = TradingApiException(
            code="TEST_ERROR",
            message="Test message",
        )

        exc_dict = exc.to_dict()

        assert "timestamp" in exc_dict
        assert exc_dict["timestamp"] == exc.timestamp
        assert isinstance(exc_dict["timestamp"], int)

    def test_service_exception_to_dict_includes_timestamp(self) -> None:
        """ServiceException.to_dict() includes timestamp from base."""
        exc = ServiceException(
            module="broker",
            code="SERVICE_BROKER_ORDER_FAILED",
            message="Order validation failed",
        )

        exc_dict = exc.to_dict()

        assert "timestamp" in exc_dict
        assert "module" in exc_dict
        assert exc_dict["module"] == "broker"

    def test_provider_exception_to_dict_includes_timestamp(self) -> None:
        """ProviderException.to_dict() includes timestamp from base."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_ERROR",
            message="Provider error",
        )

        exc_dict = exc.to_dict()

        assert "timestamp" in exc_dict
        assert "provider" in exc_dict
        assert "capability" in exc_dict
