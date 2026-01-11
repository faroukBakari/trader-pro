"""
Tests for authentication middleware.

Tests stateless JWT validation with public key only.
Cookie-only authentication for REST endpoints.
Follows strict typing rules - no type: ignore comments.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.datastructures import Address, Headers, QueryParams

from trading_api.shared import settings
from trading_api.shared.middleware.auth import (
    INTERNAL_USER,
    compute_signature,
    extract_device_fingerprint,
    get_current_user,
    verify_signature,
)


def create_mock_request(
    host: str = "192.168.1.100",
    user_agent: str = "TestBrowser/1.0",
    query_params: list[tuple[str, str]] | None = None,
    cookies: dict[str, str] | None = None,
) -> MagicMock:
    """
    Create properly-typed mock request for testing.

    Uses MagicMock without spec to allow property assignment.
    All attributes use proper Starlette types (immutable).

    Args:
        host: Client IP address
        user_agent: User-Agent header value
        query_params: List of (key, value) tuples for query parameters
        cookies: Dictionary of cookie name/value pairs

    Returns:
        MagicMock configured as a Request with proper Starlette types
    """
    mock = MagicMock()
    mock.client = Address(host=host, port=443)
    mock.headers = Headers({"user-agent": user_agent})
    mock.query_params = QueryParams(query_params or [])
    mock.cookies = cookies or {}
    return mock


@pytest.fixture
def mock_request() -> MagicMock:
    """Create default mock request for testing"""
    return create_mock_request()


@pytest.fixture
def valid_jwt_token() -> str:
    """Create valid JWT token for testing"""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": "USER-123",
        "email": "test@example.com",
        "full_name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


@pytest.fixture
def expired_jwt_token() -> str:
    """Create expired JWT token for testing"""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": "USER-123",
        "email": "test@example.com",
        "full_name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int((now - timedelta(minutes=5)).timestamp()),
        "iat": int((now - timedelta(minutes=10)).timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


class TestExtractDeviceFingerprint:
    """Tests for device fingerprint extraction"""

    def test_extract_fingerprint_from_request(self) -> None:
        """Test extracting device fingerprint from request metadata"""
        mock_request = create_mock_request()
        fingerprint = extract_device_fingerprint(mock_request)

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 32
        assert fingerprint.isalnum()

    def test_same_request_produces_same_fingerprint(self) -> None:
        """Test that same request produces consistent fingerprint"""
        mock_request = create_mock_request()
        fingerprint1 = extract_device_fingerprint(mock_request)
        fingerprint2 = extract_device_fingerprint(mock_request)

        assert fingerprint1 == fingerprint2

    def test_different_ip_produces_different_fingerprint(self) -> None:
        """Test that different IP produces different fingerprint"""
        mock_request1 = create_mock_request(host="192.168.1.100")
        mock_request2 = create_mock_request(host="192.168.1.101")

        fingerprint1 = extract_device_fingerprint(mock_request1)
        fingerprint2 = extract_device_fingerprint(mock_request2)

        assert fingerprint1 != fingerprint2

    def test_different_user_agent_produces_different_fingerprint(self) -> None:
        """Test that different User-Agent produces different fingerprint"""
        mock_request1 = create_mock_request(user_agent="TestBrowser/1.0")
        mock_request2 = create_mock_request(user_agent="DifferentBrowser/2.0")

        fingerprint1 = extract_device_fingerprint(mock_request1)
        fingerprint2 = extract_device_fingerprint(mock_request2)

        assert fingerprint1 != fingerprint2

    def test_handles_missing_client(self) -> None:
        """Test fingerprint generation when client is None"""
        mock = MagicMock()
        mock.client = None
        mock.headers = Headers({"user-agent": "TestBrowser/1.0"})

        fingerprint = extract_device_fingerprint(mock)

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 32

    def test_handles_missing_user_agent(self) -> None:
        """Test fingerprint generation when user-agent header is missing"""
        mock_request = create_mock_request(user_agent="")
        # Override headers with empty headers
        mock_request.headers = Headers({})

        fingerprint = extract_device_fingerprint(mock_request)

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 32


class TestGetCurrentUserCookieAuth:
    """Tests for cookie-based authentication (REST endpoints)"""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_data(self, valid_jwt_token: str) -> None:
        """Test that valid token in cookie returns user_id and fingerprint"""
        mock_request = create_mock_request(cookies={"access_token": valid_jwt_token})

        result = await get_current_user(mock_request)

        assert result.user_id == "USER-123"
        assert result.email == "test@example.com"
        assert hasattr(result, "device_fingerprint")
        assert len(result.device_fingerprint) == 32

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self, expired_jwt_token: str) -> None:
        """Test that expired token raises HTTPException 401"""
        mock_request = create_mock_request(cookies={"access_token": expired_jwt_token})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_raises_401(self) -> None:
        """Test that token with invalid signature raises 401"""
        payload = {
            "user_id": "USER-123",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        invalid_token = jwt.encode(payload, "wrong-key", algorithm="HS256")
        mock_request = create_mock_request(cookies={"access_token": invalid_token})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_user_id_raises_401(self) -> None:
        """Test that token without user_id raises 401"""
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        token = jwt.encode(
            payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )
        mock_request = create_mock_request(cookies={"access_token": token})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "user_id" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_user_id_type_raises_401(self) -> None:
        """Test that token with non-string user_id raises 401"""
        payload = {
            "user_id": 12345,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        token = jwt.encode(
            payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )
        mock_request = create_mock_request(cookies={"access_token": token})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "user_id" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_missing_cookie_raises_401(self) -> None:
        """Test that missing cookie raises 401"""
        mock_request = create_mock_request(cookies={})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_empty_cookie_raises_401(self) -> None:
        """Test that empty cookie value raises 401"""
        mock_request = create_mock_request(cookies={"access_token": ""})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()


class TestMiddlewareIndependence:
    """Tests verifying middleware has no auth module dependencies"""

    def test_no_auth_module_imports(self) -> None:
        """Test that middleware does not import from auth module"""
        import inspect

        from trading_api.shared.middleware import auth as auth_middleware

        source = inspect.getsource(auth_middleware)

        assert "from trading_api.modules.auth" not in source
        assert "import trading_api.modules.auth" not in source

    def test_only_uses_public_key(self) -> None:
        """Test that middleware only uses public key, not private"""
        import inspect

        from trading_api.shared.middleware import auth as auth_middleware

        source = inspect.getsource(auth_middleware)

        assert "jwt_public_key" in source
        assert "jwt_private_key" not in source


class TestTokenValidationEdgeCases:
    """Tests for edge cases in token validation"""

    @pytest.mark.asyncio
    async def test_malformed_token_raises_401(self) -> None:
        """Test that malformed JWT raises 401"""
        mock_request = create_mock_request(
            cookies={"access_token": "not.a.valid.jwt.token"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_without_expiration_raises_401(self) -> None:
        """Test that token without exp claim raises 401"""
        payload = {
            "user_id": "USER-123",
        }
        token = jwt.encode(
            payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )
        mock_request = create_mock_request(cookies={"access_token": token})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "Invalid token payload" in exc_info.value.detail


class TestComputeSignature:
    """Tests for HMAC signature computation"""

    def test_compute_signature_deterministic(self) -> None:
        """Test that same inputs produce same signature"""
        hmac_key = b"test-secret-key"
        timestamp = "1234567890"
        caller_id = "broker"
        method = "POST"
        url = "http://localhost:8000/api/v1/datafeed/symbols"
        body = b'{"symbol": "AAPL"}'

        sig1 = compute_signature(hmac_key, timestamp, caller_id, method, url, body)
        sig2 = compute_signature(hmac_key, timestamp, caller_id, method, url, body)

        assert sig1 == sig2
        assert len(sig1) == 64  # SHA256 hex = 64 chars

    def test_compute_signature_different_body_produces_different_signature(
        self,
    ) -> None:
        """Test that different body produces different signature"""
        hmac_key = b"test-secret-key"
        timestamp = "1234567890"
        caller_id = "broker"
        method = "POST"
        url = "http://localhost:8000/api/v1/datafeed/symbols"

        sig1 = compute_signature(
            hmac_key, timestamp, caller_id, method, url, b'{"symbol": "AAPL"}'
        )
        sig2 = compute_signature(
            hmac_key, timestamp, caller_id, method, url, b'{"symbol": "GOOGL"}'
        )

        assert sig1 != sig2

    def test_compute_signature_handles_none_body(self) -> None:
        """Test that None body is handled correctly"""
        hmac_key = b"test-secret-key"
        sig = compute_signature(
            hmac_key, "1234567890", "broker", "GET", "http://localhost/", None
        )
        assert len(sig) == 64


class TestVerifySignature:
    """Tests for HMAC signature verification"""

    def test_verify_signature_valid(self) -> None:
        """Test that valid signature verifies successfully"""
        hmac_key = b"test-secret-key"
        timestamp = str(int(time.time()))
        caller_id = "broker"
        method = "POST"
        url = "http://localhost:8000/api/v1/datafeed/symbols"
        body = b'{"symbol": "AAPL"}'

        signature = compute_signature(hmac_key, timestamp, caller_id, method, url, body)
        result = verify_signature(
            hmac_key, signature, timestamp, caller_id, method, url, body, ttl_seconds=30
        )

        assert result is True

    def test_verify_signature_invalid_tampered(self) -> None:
        """Test that tampered signature fails verification"""
        hmac_key = b"test-secret-key"
        timestamp = str(int(time.time()))
        caller_id = "broker"
        method = "POST"
        url = "http://localhost:8000/api/v1/datafeed/symbols"
        body = b'{"symbol": "AAPL"}'

        signature = compute_signature(hmac_key, timestamp, caller_id, method, url, body)
        # Tamper with signature
        tampered_sig = signature[:-4] + "0000"

        result = verify_signature(
            hmac_key,
            tampered_sig,
            timestamp,
            caller_id,
            method,
            url,
            body,
            ttl_seconds=30,
        )

        assert result is False

    def test_verify_signature_expired_timestamp(self) -> None:
        """Test that expired timestamp fails verification (replay protection)"""
        hmac_key = b"test-secret-key"
        old_timestamp = str(int(time.time()) - 60)  # 60 seconds ago
        caller_id = "broker"
        method = "GET"
        url = "http://localhost:8000/api/v1/datafeed/symbols"
        body = None

        signature = compute_signature(
            hmac_key, old_timestamp, caller_id, method, url, body
        )
        result = verify_signature(
            hmac_key,
            signature,
            old_timestamp,
            caller_id,
            method,
            url,
            body,
            ttl_seconds=30,
        )

        assert result is False

    def test_verify_signature_invalid_timestamp_format(self) -> None:
        """Test that invalid timestamp format fails verification"""
        hmac_key = b"test-secret-key"
        result = verify_signature(
            hmac_key,
            "somesignature",
            "not-a-number",
            "broker",
            "GET",
            "http://localhost/",
            None,
            ttl_seconds=30,
        )

        assert result is False


class TestInternalSignatureAuth:
    """Tests for internal HMAC signature authentication in get_current_user"""

    @pytest.fixture
    def hmac_key(self) -> bytes:
        """HMAC key for testing"""
        return settings.internal_hmac_key

    def _create_signed_request(
        self,
        hmac_key: bytes,
        method: str = "GET",
        url: str = "http://localhost:8000/api/v1/broker/orders",
        body: bytes = b"",
        timestamp: str | None = None,
    ) -> MagicMock:
        """Create a mock request with valid HMAC signature headers"""
        if timestamp is None:
            timestamp = str(int(time.time()))
        caller_id = "broker"

        signature = compute_signature(hmac_key, timestamp, caller_id, method, url, body)

        mock = MagicMock()
        mock.client = Address(host="127.0.0.1", port=443)
        mock.headers = Headers(
            {
                "x-internal-signature": signature,
                "x-internal-timestamp": timestamp,
                "x-internal-caller": caller_id,
            }
        )
        mock.cookies = {}
        mock.method = method
        mock.url = url
        mock.body = AsyncMock(return_value=body)
        return mock

    @pytest.mark.asyncio
    async def test_internal_signature_valid_returns_internal_user(
        self, hmac_key: bytes
    ) -> None:
        """Test that valid internal signature returns INTERNAL_USER"""
        if not hmac_key:
            pytest.skip("HMAC key not configured")

        mock_request = self._create_signed_request(hmac_key)

        result = await get_current_user(mock_request)

        assert result.user_id == INTERNAL_USER.user_id
        assert result.email == INTERNAL_USER.email
        assert result.device_fingerprint == "internal"

    @pytest.mark.asyncio
    async def test_internal_signature_missing_key_disables_feature(self) -> None:
        """Test that missing HMAC key falls back to cookie auth (401 without cookie)"""
        # Create request with signature headers but assume empty HMAC key
        mock = MagicMock()
        mock.client = Address(host="127.0.0.1", port=443)
        mock.headers = Headers(
            {
                "x-internal-signature": "somesig",
                "x-internal-timestamp": str(int(time.time())),
                "x-internal-caller": "broker",
            }
        )
        mock.cookies = {}  # No cookie = should fail
        mock.method = "GET"
        mock.url = "http://localhost/"
        mock.body = AsyncMock(return_value=b"")

        # If HMAC key exists, signature will fail (invalid), falling back to cookie
        # If HMAC key is empty, feature is disabled, falls back to cookie
        # Either way, no cookie = 401
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock)

        assert exc_info.value.status_code == 401
