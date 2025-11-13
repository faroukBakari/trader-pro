"""
Tests for authentication middleware.

Tests stateless JWT validation with public key only.
Follows strict typing rules - no type: ignore comments.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from starlette.datastructures import Address, Headers, QueryParams
from starlette.requests import Request

from trading_api.shared import settings
from trading_api.shared.middleware.auth import (
    extract_device_fingerprint,
    get_current_user,
)


def create_mock_request(
    host: str = "192.168.1.100",
    user_agent: str = "TestBrowser/1.0",
    query_params: list[tuple[str, str]] | None = None,
) -> MagicMock:
    """
    Create properly-typed mock request for testing.

    Uses MagicMock without spec to allow property assignment.
    All attributes use proper Starlette types (immutable).

    Args:
        host: Client IP address
        user_agent: User-Agent header value
        query_params: List of (key, value) tuples for query parameters

    Returns:
        MagicMock configured as a Request with proper Starlette types
    """
    mock = MagicMock()
    mock.client = Address(host=host, port=443)
    mock.headers = Headers({"user-agent": user_agent})
    mock.query_params = QueryParams(query_params or [])
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


class TestGetCurrentUserREST:
    """Tests for REST API authentication (Authorization header)"""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_data(
        self, mock_request: Request, valid_jwt_token: str
    ) -> None:
        """Test that valid token returns user_id and fingerprint"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_jwt_token
        )

        result = await get_current_user(mock_request, credentials)

        assert result.user_id == "USER-123"
        assert hasattr(result, "device_fingerprint")
        assert len(result.device_fingerprint) == 32

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(
        self, mock_request: Request, expired_jwt_token: str
    ) -> None:
        """Test that expired token raises HTTPException 401"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=expired_jwt_token
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_raises_401(self, mock_request: Request) -> None:
        """Test that token with invalid signature raises 401"""
        payload = {
            "user_id": "USER-123",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        # Sign with wrong key
        invalid_token = jwt.encode(payload, "wrong-key", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=invalid_token
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_user_id_raises_401(self, mock_request: Request) -> None:
        """Test that token without user_id raises 401"""
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        token = jwt.encode(
            payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401
        assert "user_id" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_user_id_type_raises_401(self, mock_request: Request) -> None:
        """Test that token with non-string user_id raises 401"""
        payload = {
            "user_id": 12345,  # Integer instead of string
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        token = jwt.encode(
            payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401
        assert "user_id" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self, mock_request: Request) -> None:
        """Test that missing token raises 401"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, None)

        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()


class TestGetCurrentUserWebSocket:
    """Tests for WebSocket authentication (query parameter)"""

    @pytest.mark.asyncio
    async def test_valid_token_from_query_param(self, valid_jwt_token: str) -> None:
        """Test WebSocket auth with token in query parameter"""
        mock_request = create_mock_request(query_params=[("token", valid_jwt_token)])

        result = await get_current_user(mock_request, None)

        assert result.user_id == "USER-123"
        assert hasattr(result, "device_fingerprint")

    @pytest.mark.asyncio
    async def test_expired_token_from_query_param_raises_401(
        self, expired_jwt_token: str
    ) -> None:
        """Test WebSocket auth rejects expired token"""
        mock_request = create_mock_request(query_params=[("token", expired_jwt_token)])

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_query_param_raises_401(self) -> None:
        """Test WebSocket auth fails without token query param"""
        mock_request = create_mock_request(query_params=[])

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, None)

        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_from_query_param_raises_401(self) -> None:
        """Test WebSocket auth rejects invalid signature"""
        payload = {
            "user_id": "USER-123",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        invalid_token = jwt.encode(payload, "wrong-key", algorithm="HS256")

        mock_request = create_mock_request(query_params=[("token", invalid_token)])

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, None)

        assert exc_info.value.status_code == 401


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
    async def test_malformed_token_raises_401(self, mock_request: Request) -> None:
        """Test that malformed JWT raises 401"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="not.a.valid.jwt.token"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token_raises_401(self, mock_request: Request) -> None:
        """Test that empty token raises 401"""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_without_expiration_raises_401(
        self, mock_request: MagicMock
    ) -> None:
        """Test that token without exp claim raises 401 (Pydantic validation enforces required fields)"""
        payload = {
            "user_id": "USER-123",
            # No 'exp' field - Pydantic validation should reject this
        }
        token = jwt.encode(
            payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Should fail - Pydantic validation requires exp field
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid token payload" in exc_info.value.detail
