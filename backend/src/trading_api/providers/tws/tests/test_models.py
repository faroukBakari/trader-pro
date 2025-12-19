"""Tests for TWS models and error classification.

Tests cover:
- classify_error() - TWS error code categorization
- TWSErrorClassification constants
- Error code recoverability classification
"""

import pytest

from trading_api.providers.tws.tws_models import TWSErrorClassification, classify_error


class TestClassifyError:
    """Test classify_error() TWS error code categorization."""

    # =========================================================================
    # INFO Codes - Status notifications, not real errors
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            2104,  # Market data farm connection is OK
            2106,  # Historical data farm is connected
            2107,  # Historical data farm connection inactive (dormant)
            2108,  # Market data farm connection inactive (dormant)
            2158,  # Sec-def data farm connection is OK
        ],
    )
    def test_info_codes_are_recoverable(self, error_code: int) -> None:
        """Test INFO status codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.INFO
        assert recoverable is True

    # =========================================================================
    # CONNECTION Codes - Recoverable connection issues
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            502,  # Couldn't connect to TWS - retry
            504,  # Not connected - reconnect
            1100,  # Connectivity lost - wait for 1101/1102
            1101,  # Connectivity restored, data lost - resubscribe
            1102,  # Connectivity restored, data maintained
            1300,  # Socket port reset - reconnect on new port
            2103,  # Market data farm disconnected - temporary
            2105,  # Historical data farm disconnected - temporary
            2110,  # TWS-server connection broken - auto-restores
        ],
    )
    def test_connection_codes_are_recoverable(self, error_code: int) -> None:
        """Test CONNECTION codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.CONNECTION
        assert recoverable is True

    # =========================================================================
    # PACING Codes - Rate limiting, recoverable with throttling
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            100,  # Max rate of messages exceeded (50/sec)
            420,  # Invalid real-time query (pacing violation)
        ],
    )
    def test_pacing_codes_are_recoverable(self, error_code: int) -> None:
        """Test PACING codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.PACING
        assert recoverable is True

    # =========================================================================
    # DUPLICATE Codes - Use different ID and retry
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            102,  # Duplicate ticker ID
            103,  # Duplicate order ID
            326,  # Client ID already in use
            385,  # Duplicate ticker ID for scanner
            386,  # Duplicate ticker ID for historical data
            501,  # Already connected (not really an error)
        ],
    )
    def test_duplicate_codes_are_recoverable(self, error_code: int) -> None:
        """Test DUPLICATE codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.DUPLICATE
        assert recoverable is True

    # =========================================================================
    # SUBSCRIPTION Codes - Requires user action (not auto-recoverable)
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            354,  # Not subscribed to market data
            10090,  # Part of requested market data not subscribed
            10167,  # Requested market data requires subscription
            10186,  # Market data not subscribed, delayed not enabled
            10197,  # No market data during competing session
        ],
    )
    def test_subscription_codes_not_recoverable(self, error_code: int) -> None:
        """Test SUBSCRIPTION codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.SUBSCRIPTION
        assert recoverable is False

    # =========================================================================
    # VALIDATION Codes - Invalid request, not recoverable without fix
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            200,  # No security definition found
            201,  # Order rejected
            202,  # Order cancelled (may be expected)
            203,  # Security not available for account
            300,  # Can't find ticker ID
            321,  # Server error validating request
            322,  # Server error processing request
            323,  # Server error
            399,  # Order message error
            400,  # Algo order error
        ],
    )
    def test_validation_codes_not_recoverable(self, error_code: int) -> None:
        """Test VALIDATION codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.VALIDATION
        assert recoverable is False

    # =========================================================================
    # FATAL Codes - Protocol/system errors, cannot recover
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            503,  # TWS out of date - must upgrade
            505,  # Unknown message ID
            506,  # Unsupported version
            507,  # Bad message length
            508,  # Bad message
            509,  # Socket exception
            520,  # Failed to create socket
            530,  # SSL error
        ],
    )
    def test_fatal_codes_not_recoverable(self, error_code: int) -> None:
        """Test FATAL codes are classified correctly."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.FATAL
        assert recoverable is False

    # =========================================================================
    # NOT_FOUND Codes - Informational (already cancelled/completed)
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            135,  # Can't find order with ID
            366,  # No historical data query found
            365,  # No scanner subscription found
            10148,  # Order cannot be cancelled, wrong state
        ],
    )
    def test_not_found_codes_are_recoverable(self, error_code: int) -> None:
        """Test NOT_FOUND codes are INFO (already handled)."""
        category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.INFO
        assert recoverable is True

    # =========================================================================
    # Range-based Classification
    # =========================================================================

    def test_warning_range_2xxx(self) -> None:
        """Test 2xxx range (excluding handled codes) is WARNING."""
        # Pick a code in 2xxx range that's not in INFO or CONNECTION
        category, recoverable = classify_error(2001)

        assert category == TWSErrorClassification.WARNING
        assert recoverable is True

    def test_system_range_1xxx(self) -> None:
        """Test 1xxx range (excluding handled codes) is SYSTEM."""
        # Pick a code in 1xxx range that's not in CONNECTION
        category, recoverable = classify_error(1001)

        assert category == TWSErrorClassification.SYSTEM
        assert recoverable is True

    # =========================================================================
    # Default Classification
    # =========================================================================

    def test_unknown_code_defaults_to_error(self) -> None:
        """Test unknown codes default to ERROR, non-recoverable."""
        # Pick a random unknown code
        category, recoverable = classify_error(99999)

        assert category == TWSErrorClassification.ERROR
        assert recoverable is False

    def test_negative_code_defaults_to_error(self) -> None:
        """Test negative codes default to ERROR, non-recoverable."""
        category, recoverable = classify_error(-1)

        assert category == TWSErrorClassification.ERROR
        assert recoverable is False


class TestTWSErrorClassificationConstants:
    """Test TWSErrorClassification constants exist and are strings."""

    def test_all_classification_constants_exist(self) -> None:
        """Test all classification constants are defined."""
        assert TWSErrorClassification.INFO == "INFO"
        assert TWSErrorClassification.CONNECTION == "CONNECTION"
        assert TWSErrorClassification.PACING == "PACING"
        assert TWSErrorClassification.DUPLICATE == "DUPLICATE"
        assert TWSErrorClassification.SUBSCRIPTION == "SUBSCRIPTION"
        assert TWSErrorClassification.VALIDATION == "VALIDATION"
        assert TWSErrorClassification.FATAL == "FATAL"
        assert TWSErrorClassification.WARNING == "WARNING"
        assert TWSErrorClassification.SYSTEM == "SYSTEM"
        assert TWSErrorClassification.ERROR == "ERROR"
