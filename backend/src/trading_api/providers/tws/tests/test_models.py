"""Tests for TWS models and error classification.

Tests cover:
- classify_error() - TWS error code categorization and nature classification
- TWSErrorClassification constants
- TWSErrorNature constants
- Error code recoverability classification
"""

import pytest

from trading_api.providers.tws.tws_models import (
    TWSErrorClassification,
    TWSErrorNature,
    classify_error,
)


class TestClassifyError:
    """Test classify_error() TWS error code categorization."""

    # =========================================================================
    # INFO Codes - Status notifications, not real errors
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            202,  # Order cancellation acknowledged
            2104,  # Market data farm connection is OK
            2106,  # Historical data farm is connected
            2107,  # Historical data farm connection inactive (dormant)
            2108,  # Market data farm connection inactive (dormant)
            2158,  # Sec-def data farm connection is OK
        ],
    )
    def test_info_codes_are_recoverable(self, error_code: int) -> None:
        """Test INFO status codes are classified correctly."""
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

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
        nature, category, recoverable = classify_error(error_code)

        assert category == TWSErrorClassification.INFO
        assert recoverable is True

    # =========================================================================
    # Range-based Classification
    # =========================================================================

    def test_warning_range_2xxx(self) -> None:
        """Test 2xxx range (excluding handled codes) is WARNING."""
        # Pick a code in 2xxx range that's not in INFO or CONNECTION
        nature, category, recoverable = classify_error(2001)

        assert category == TWSErrorClassification.WARNING
        assert recoverable is True

    def test_system_range_1xxx(self) -> None:
        """Test 1xxx range (excluding handled codes) is SYSTEM."""
        # Pick a code in 1xxx range that's not in CONNECTION
        nature, category, recoverable = classify_error(1001)

        assert category == TWSErrorClassification.SYSTEM
        assert recoverable is True

    # =========================================================================
    # Default Classification
    # =========================================================================

    def test_unknown_code_defaults_to_error(self) -> None:
        """Test unknown codes default to ERROR, non-recoverable."""
        # Pick a random unknown code
        nature, category, recoverable = classify_error(99999)

        assert category == TWSErrorClassification.ERROR
        assert recoverable is False

    def test_negative_code_defaults_to_error(self) -> None:
        """Test negative codes default to ERROR, non-recoverable."""
        nature, category, recoverable = classify_error(-1)

        assert category == TWSErrorClassification.ERROR
        assert recoverable is False


class TestClassifyErrorNature:
    """Test classify_error() returns correct error nature (req/order/system)."""

    # =========================================================================
    # ORDER Nature - Error ID represents an order ID
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            103,  # Duplicate order ID
            104,  # Can't modify a filled order
            105,  # Order being modified does not match
            133,  # Submit new order failed
            134,  # Modify order failed
            135,  # Can't find order with ID
            136,  # Order cannot be cancelled
            161,  # Cancel attempted when not cancellable
            201,  # Order rejected
            202,  # Order cancelled
            399,  # Order message error
            400,  # Algo order error
            10006,  # Missing parent order
            10148,  # Order cannot be cancelled, wrong state
        ],
    )
    def test_order_nature_codes(self, error_code: int) -> None:
        """Test order-related error codes return ORDER nature."""
        nature, category, recoverable = classify_error(error_code)
        assert nature == TWSErrorNature.ORDER

    # =========================================================================
    # REQUEST Nature - Error ID represents a request ID
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            100,  # Max rate of messages exceeded
            101,  # Max number of tickers reached
            102,  # Duplicate ticker ID
            162,  # Historical market data service error
            200,  # No security definition found
            300,  # Can't find ticker ID
            309,  # Max market depth requests reached
            354,  # Not subscribed to market data
            365,  # No scanner subscription found
            366,  # No historical data query found
            385,  # Duplicate ticker ID for scanner
            386,  # Duplicate ticker ID for historical data
            420,  # Invalid real-time query (pacing)
            10090,  # Part of requested market data not subscribed
            10186,  # Market data not subscribed, delayed not enabled
            10197,  # No market data during competing session
        ],
    )
    def test_request_nature_codes(self, error_code: int) -> None:
        """Test request-related error codes return REQUEST nature."""
        nature, category, recoverable = classify_error(error_code)
        assert nature == TWSErrorNature.REQUEST

    # =========================================================================
    # SYSTEM Nature - Error is system-wide (no specific req/order ID)
    # =========================================================================

    @pytest.mark.parametrize(
        "error_code",
        [
            501,  # Already connected
            502,  # Couldn't connect to TWS
            503,  # TWS out of date
            504,  # Not connected
            505,  # Unknown message ID
            506,  # Unsupported version
            507,  # Bad message length
            326,  # Client ID already in use
            1100,  # Connectivity lost
            1101,  # Connectivity restored, data lost
            1102,  # Connectivity restored, data maintained
            2103,  # Market data farm disconnected
            2104,  # Market data farm connection OK
            2105,  # Historical data farm disconnected
            2106,  # Historical data farm connected
            2158,  # Sec-def data farm connection OK
        ],
    )
    def test_system_nature_codes(self, error_code: int) -> None:
        """Test system-wide error codes return SYSTEM nature."""
        nature, category, recoverable = classify_error(error_code)
        assert nature == TWSErrorNature.SYSTEM

    # =========================================================================
    # Range-based Nature Heuristics
    # =========================================================================

    def test_1xxx_range_is_system_nature(self) -> None:
        """Test 1xxx range defaults to SYSTEM nature."""
        # Pick a code in 1xxx range that's not explicitly classified
        nature, category, recoverable = classify_error(1001)
        assert nature == TWSErrorNature.SYSTEM

    def test_2xxx_range_is_system_nature(self) -> None:
        """Test 2xxx range defaults to SYSTEM nature."""
        # Pick a code in 2xxx range that's not explicitly classified
        nature, category, recoverable = classify_error(2001)
        assert nature == TWSErrorNature.SYSTEM

    def test_10xxx_range_defaults_to_order_nature(self) -> None:
        """Test 10xxx range (non-subscription) defaults to ORDER nature."""
        # Pick a code in 10xxx range that's not in subscription codes
        nature, category, recoverable = classify_error(10001)
        assert nature == TWSErrorNature.ORDER

    def test_400_range_is_order_nature(self) -> None:
        """Test 400-499 range (algo orders) is ORDER nature."""
        # Pick a code in 400 range
        nature, category, recoverable = classify_error(401)
        assert nature == TWSErrorNature.ORDER


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


class TestTWSErrorNatureConstants:
    """Test TWSErrorNature constants exist and are strings."""

    def test_all_nature_constants_exist(self) -> None:
        """Test all nature constants are defined."""
        assert TWSErrorNature.REQUEST == "req"
        assert TWSErrorNature.ORDER == "order"
        assert TWSErrorNature.SYSTEM == "system"
