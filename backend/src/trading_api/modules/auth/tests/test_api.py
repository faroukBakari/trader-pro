"""API tests for auth endpoints.

Tests the REST API layer of the auth module, including:
- Google OAuth login
- Token refresh with rotation
- Logout (token revocation)
- Get current user info
"""

import time
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from trading_api.app_factory import AppFactory, ModularApp


@pytest.fixture
def auth_app() -> ModularApp:
    """Create app with only auth module enabled (function-scoped for test isolation)"""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["auth"])


@pytest.fixture
def client(auth_app: ModularApp) -> Generator[TestClient, None, None]:
    """Test client for auth API"""
    with TestClient(auth_app) as c:
        yield c


@pytest.fixture
def mock_google_claims() -> dict[str, Any]:
    """Mock Google ID token claims"""
    return {
        "sub": "google-user-123",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://example.com/photo.jpg",
        "iss": "https://accounts.google.com",
        "aud": "test-client-id",
    }


class TestLoginEndpoint:
    """Tests for POST /login endpoint"""

    def test_login_with_valid_google_token(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test successful login with valid Google ID token"""
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "access_token" in data
            assert "refresh_token" in data
            assert "token_type" in data
            assert "expires_in" in data

            assert data["token_type"] == "bearer"
            assert data["expires_in"] == 300  # 5 minutes

            # Verify tokens are non-empty
            assert len(data["access_token"]) > 0
            assert len(data["refresh_token"]) > 0

    def test_login_with_invalid_google_token(self, client: TestClient) -> None:
        """Test login fails with invalid Google ID token"""
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            from authlib.integrations.base_client import OAuthError

            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(
                side_effect=OAuthError(description="Invalid token")
            )
            mock_oauth.return_value.google = mock_google

            response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "invalid_token"},
            )

            assert response.status_code == 401
            assert "Invalid Google token" in response.json()["detail"]

    def test_login_with_unverified_email(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test login fails when Google email is not verified"""
        mock_google_claims["email_verified"] = False

        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )

            assert response.status_code == 401
            assert "Email not verified" in response.json()["detail"]

    def test_login_missing_google_token(self, client: TestClient) -> None:
        """Test login fails when google_token is missing"""
        response = client.post("/api/v1/auth/login", json={})

        assert response.status_code == 422  # Validation error


class TestRefreshTokenEndpoint:
    """Tests for POST /refresh-token endpoint"""

    def test_refresh_with_valid_token(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test token refresh with valid refresh token"""
        # First, login to get tokens
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            assert login_response.status_code == 200
            login_data = login_response.json()
            refresh_token = login_data["refresh_token"]

        # Wait a moment to ensure different timestamp in JWT (exp claim has 1-second precision)
        time.sleep(1.1)

        # Now refresh the token
        refresh_response = client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()

        # Verify new tokens are returned
        assert "access_token" in refresh_data
        assert "refresh_token" in refresh_data
        assert refresh_data["token_type"] == "bearer"

        # Verify tokens are different from original
        assert refresh_data["access_token"] != login_data["access_token"]
        assert refresh_data["refresh_token"] != refresh_token

    def test_refresh_with_invalid_token(self, client: TestClient) -> None:
        """Test refresh fails with invalid refresh token"""
        response = client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": "invalid_token"},
        )

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_with_revoked_token(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test refresh fails after token is revoked (logout)"""
        # Login
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            login_data = login_response.json()
            refresh_token = login_data["refresh_token"]

        # Logout (revoke token)
        logout_response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_response.status_code == 200

        # Try to refresh with revoked token
        refresh_response = client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == 401
        assert "Invalid refresh token" in refresh_response.json()["detail"]

    def test_refresh_missing_token(self, client: TestClient) -> None:
        """Test refresh fails when refresh_token is missing"""
        response = client.post("/api/v1/auth/refresh-token", json={})

        assert response.status_code == 422  # Validation error


class TestLogoutEndpoint:
    """Tests for POST /logout endpoint"""

    def test_logout_with_valid_token(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test successful logout with valid refresh token"""
        # Login first
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            login_data = login_response.json()
            refresh_token = login_data["refresh_token"]

        # Logout
        logout_response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )

        assert logout_response.status_code == 200
        assert logout_response.json()["message"] == "Logged out successfully"

    def test_logout_with_invalid_token(self, client: TestClient) -> None:
        """Test logout succeeds even with invalid token (silent failure)"""
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "invalid_token"},
        )

        # Logout always succeeds (silent failure for security)
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    def test_logout_missing_token(self, client: TestClient) -> None:
        """Test logout fails when refresh_token is missing"""
        response = client.post("/api/v1/auth/logout", json={})

        assert response.status_code == 422  # Validation error


class TestGetMeEndpoint:
    """Tests for GET /me endpoint"""

    def test_get_me_with_valid_token(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test getting current user info with valid JWT token"""
        # Login first
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            login_data = login_response.json()
            access_token = login_data["access_token"]

        # Get current user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        user = response.json()

        # Verify user data
        assert user["email"] == "test@example.com"
        assert user["full_name"] == "Test User"
        assert user["google_id"] == "google-user-123"

    def test_get_me_without_token(self, client: TestClient) -> None:
        """Test /me fails without Authorization header"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401  # Unauthorized (no auth)

    def test_get_me_with_invalid_token(self, client: TestClient) -> None:
        """Test /me fails with invalid JWT token"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401  # Unauthorized

    def test_get_me_with_expired_token(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test /me fails with expired JWT token"""
        from datetime import datetime, timedelta, timezone

        from trading_api.shared.config import Settings

        settings = Settings()

        # Create expired token (expired 1 minute ago)
        expired_claims = {
            "sub": "USER-1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=6),
        }

        expired_token = jwt.encode(
            expired_claims,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


class TestTokenRotation:
    """Tests for token rotation behavior"""

    def test_old_refresh_token_invalid_after_rotation(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test old refresh token cannot be reused after rotation"""
        # Login
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            old_refresh_token = login_response.json()["refresh_token"]

        # Refresh (should rotate tokens)
        refresh_response = client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token},
        )
        assert refresh_response.status_code == 200

        # Try to use old refresh token again
        reuse_response = client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token},
        )

        assert reuse_response.status_code == 401
        assert "Invalid refresh token" in reuse_response.json()["detail"]


class TestAccessTokenStructure:
    """Tests for JWT access token structure and claims"""

    def test_access_token_is_valid_jwt(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test access token is a valid JWT with correct structure"""
        # Login
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            access_token = login_response.json()["access_token"]

        # Decode token (without verification, just checking structure)
        from jose import jwt

        claims = jwt.get_unverified_claims(access_token)

        # Verify required claims exist
        assert "user_id" in claims  # User ID (custom claim)
        assert "exp" in claims  # Expiration

        # Verify user ID format
        assert claims["user_id"].startswith("USER-")

    def test_access_token_expires_in_5_minutes(
        self, client: TestClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test access token expiration is 5 minutes"""
        from datetime import datetime, timezone

        # Login
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            before_login = datetime.now(timezone.utc)
            login_response = client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            datetime.now(timezone.utc)
            access_token = login_response.json()["access_token"]

        # Decode token
        from jose import jwt

        claims = jwt.get_unverified_claims(access_token)
        exp_timestamp = claims["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, timezone.utc)

        # Verify expiration is ~5 minutes from issue time
        time_to_expiry = (exp_datetime - before_login).total_seconds()
        assert 290 <= time_to_expiry <= 310  # Allow 10s margin for test execution
