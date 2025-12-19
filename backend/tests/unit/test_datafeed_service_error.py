"""
Unit tests for DatafeedService error handling.

Tests the _is_error_recoverable() method and error callback wrapping
in DatafeedService.
"""

import pytest

from trading_api.models.exceptions import (
    CommonException,
    ProviderException,
    ServiceException,
    TradingApiException,
)
from trading_api.modules.datafeed.service import (
    _DEFAULT_RETRY_AFTER_MS,
    _RECOVERABLE_ERROR_CODES,
    DatafeedService,
)


class TestIsErrorRecoverable:
    """Tests for DatafeedService._is_error_recoverable() method."""

    @pytest.fixture
    def service(self, tmp_path) -> DatafeedService:
        """Create DatafeedService without provider for testing error logic."""
        # DatafeedService requires module_dir for base class init
        # We're only testing _is_error_recoverable which doesn't use provider
        service = DatafeedService.__new__(DatafeedService)
        service._module_dir = tmp_path
        return service

    def test_recoverable_timeout_error(self, service: DatafeedService) -> None:
        """PROVIDER_DATAFEED_TIMEOUT is recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_TIMEOUT",
            message="Request timed out",
        )

        assert service._is_error_recoverable(exc) is True

    def test_recoverable_connection_lost_error(self, service: DatafeedService) -> None:
        """PROVIDER_DATAFEED_CONNECTION_LOST is recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_CONNECTION_LOST",
            message="Connection to provider lost",
        )

        assert service._is_error_recoverable(exc) is True

    def test_recoverable_rate_limit_error(self, service: DatafeedService) -> None:
        """PROVIDER_DATAFEED_RATE_LIMIT is recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_RATE_LIMIT",
            message="Rate limit exceeded",
        )

        assert service._is_error_recoverable(exc) is True

    def test_recoverable_data_gap_error(self, service: DatafeedService) -> None:
        """PROVIDER_DATAFEED_DATA_GAP is recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_DATA_GAP",
            message="Gap detected in data stream",
        )

        assert service._is_error_recoverable(exc) is True

    def test_unrecoverable_symbol_not_found(self, service: DatafeedService) -> None:
        """PROVIDER_DATAFEED_SYMBOL_NOT_FOUND is NOT recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
            message="Symbol INVALID not found",
        )

        assert service._is_error_recoverable(exc) is False

    def test_unrecoverable_symbol_delisted(self, service: DatafeedService) -> None:
        """Delisted symbol errors are NOT recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_SYMBOL_DELISTED",
            message="Symbol has been delisted",
        )

        assert service._is_error_recoverable(exc) is False

    def test_unrecoverable_resolution_not_supported(
        self, service: DatafeedService
    ) -> None:
        """Resolution not supported errors are NOT recoverable."""
        exc = ProviderException(
            provider="tws",
            capability="datafeed",
            code="PROVIDER_DATAFEED_RESOLUTION_NOT_SUPPORTED",
            message="1 second bars not supported",
        )

        assert service._is_error_recoverable(exc) is False

    def test_unrecoverable_service_exception(self, service: DatafeedService) -> None:
        """Service exceptions are NOT recoverable by default."""
        exc = ServiceException(
            module="datafeed",
            code="SERVICE_DATAFEED_INVALID_TOPIC",
            message="Invalid topic format",
        )

        assert service._is_error_recoverable(exc) is False

    def test_unrecoverable_common_exception(self, service: DatafeedService) -> None:
        """Common exceptions are NOT recoverable by default."""
        exc = CommonException(
            code="COMMON_AUTH_TOKEN_EXPIRED",
            message="Token has expired",
        )

        assert service._is_error_recoverable(exc) is False

    def test_unrecoverable_unknown_error(self, service: DatafeedService) -> None:
        """Unknown errors are NOT recoverable (strict default)."""
        exc = TradingApiException(
            code="UNKNOWN_ERROR",
            message="Some unknown error occurred",
        )

        assert service._is_error_recoverable(exc) is False


class TestRecoverableErrorCodesConfiguration:
    """Tests for recoverable error codes configuration."""

    def test_recoverable_codes_is_frozenset(self) -> None:
        """Recoverable codes should be immutable."""
        assert isinstance(_RECOVERABLE_ERROR_CODES, frozenset)

    def test_default_retry_after_ms_is_positive(self) -> None:
        """Default retry delay should be positive."""
        assert _DEFAULT_RETRY_AFTER_MS > 0

    def test_all_recoverable_codes_follow_naming_convention(self) -> None:
        """All recoverable codes should follow PROVIDER_DATAFEED_* pattern."""
        for code in _RECOVERABLE_ERROR_CODES:
            assert code.startswith(
                "PROVIDER_DATAFEED_"
            ), f"Code {code} doesn't follow naming convention"
