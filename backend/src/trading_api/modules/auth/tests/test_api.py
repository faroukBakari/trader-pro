"""API tests for auth endpoints.

Tests the REST API layer of the auth module, including:
- Google OAuth login
- Token refresh with rotation
- Logout (token revocation)
- Get current user info
"""

import time
from collections.abc import AsyncGenerator
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from trading_api.app_factory import ModularApp
from trading_api.shared import (
    DatastoreRegistry,
    ModuleApp,
    ModuleRegistry,
    ProviderRegistry,
    settings,
)


@pytest.fixture
async def auth_app() -> ModularApp:
    """Create app with only auth module enabled (function-scoped for test isolation)"""
    # Create registries directly for test isolation
    modules_dir = Path(__file__).parents[2]
    providers_dir = Path(__file__).parents[3] / "providers"
    datastores_dir = Path(__file__).parents[3] / "datastores"

    module_registry = ModuleRegistry(modules_dir)
    provider_registry = ProviderRegistry(providers_dir)
    datastore_registry = DatastoreRegistry(datastores_dir)

    # Auto-discover only auth module with google provider
    module_registry.auto_discover(enabled_modules=["auth"])
    provider_registry.auto_discover(enabled_names=["google"])
    datastore_registry.auto_discover(enabled_names=["inmemory"])

    # Create datastore using async/await (avoid asyncio.get_event_loop() for Python 3.10+)
    datastores = await datastore_registry.get_datastores()

    # Get providers
    required_capabilities = module_registry.required_provider_capabilities()
    providers = await provider_registry.get_providers(required_capabilities)

    # Get modules with providers and datastores
    enabled_modules = module_registry.get_modules(
        providers=providers,
        datastores=datastores,
    )

    # Create ModularApp without lifespan (simpler for tests)
    app = ModularApp(
        base_url=settings.API_PREFIX,
        enabled_modules=["auth"],
        enabled_providers=["google"],
        enabled_datastores=["inmemory"],
        title="Trading API (Test)",
        version="1.0.0",
    )

    # Manually set runtime state (normally done in build_modules)
    app._modules = enabled_modules
    app._modules_apps = [ModuleApp(module) for module in enabled_modules]

    # Mount module routes (normally done in _start)
    for module_app in app._modules_apps:
        for api_app in module_app.api_versions:
            mount_path = f"{app.base_url}/{api_app.version}/{module_app.module.name}"
            app.mount(mount_path, api_app)

        # Start module
        module_app.start()

    return app


@pytest.fixture
async def client(auth_app: ModularApp) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for auth API.

    Uses ASGITransport with raise_app_exceptions=False so that exceptions
    are handled by FastAPI's exception handlers and return proper HTTP responses
    instead of bubbling up to the test.

    CRITICAL: Uses async client to avoid event loop mismatch with async pool.
    """
    transport = ASGITransport(
        app=auth_app,  # type: ignore[arg-type]
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_google_claims() -> dict[str, Any]:
    """Mock Google ID token claims"""
    from trading_api.shared.config import Settings

    settings = Settings()

    return {
        "sub": "google-user-123",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://example.com/photo.jpg",
        "iss": "https://accounts.google.com",
        "aud": settings.GOOGLE_CLIENT_ID,  # Use actual client ID from settings
    }


def extract_cookie(response: httpx.Response, cookie_name: str) -> str | None:
    """Extract cookie value from response"""
    cookies = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookies.load(header)
    if cookie_name in cookies:
        return cookies[cookie_name].value
    return None


class TestLoginEndpoint:
    """Tests for POST /login endpoint"""

    @pytest.mark.asyncio
    async def test_login_with_valid_google_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test successful login with valid Google ID token"""
        # Mock the GoogleProvider's verify_token method
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure (tokens still in JSON for backward compatibility)
            assert "access_token" in data
            assert "refresh_token" in data
            assert "token_type" in data
            assert "expires_in" in data

            assert data["token_type"] == "bearer"
            assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

            # Verify tokens are non-empty
            assert len(data["access_token"]) > 0
            assert len(data["refresh_token"]) > 0

            # Verify access token is also set as cookie
            cookie_token = extract_cookie(response, "access_token")
            assert cookie_token is not None
            assert cookie_token == data["access_token"]

    @pytest.mark.asyncio
    async def test_login_with_invalid_google_token(self, client: AsyncClient) -> None:
        """Test login fails with invalid Google ID token"""
        # Mock GoogleProvider to raise authentication error
        from trading_api.models.exceptions import ProviderException

        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.side_effect = ProviderException(
                provider="google",
                capability="auth",
                code="PROVIDER_AUTH_TOKEN_INVALID",
                message='Invalid Google token: {"error": "invalid_token"}',
            )

            response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "invalid_token"},
            )

            assert response.status_code == 401
            assert "Invalid Google token" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_login_with_unverified_email(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test login fails when Google email is not verified"""
        # Mock GoogleProvider to raise error for unverified email
        from trading_api.models.exceptions import ProviderException

        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.side_effect = ProviderException(
                provider="google",
                capability="auth",
                code="PROVIDER_AUTH_EMAIL_NOT_VERIFIED",
                message="Email not verified",
            )

            response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )

            assert response.status_code == 403
            assert "Email not verified" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_login_missing_google_token(self, client: AsyncClient) -> None:
        """Test login fails when google_token is missing"""
        response = await client.post("/api/v1/auth/login", json={})

        assert response.status_code == 422  # Validation error


class TestRefreshTokenEndpoint:
    """Tests for POST /refresh-token endpoint"""

    @pytest.mark.asyncio
    async def test_refresh_with_valid_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test token refresh with valid refresh token"""
        # First, login to get tokens
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            assert login_response.status_code == 200
            login_data = login_response.json()
            refresh_token = login_data["refresh_token"]

        # Wait to ensure different timestamp in JWT (iat claim has 1-second precision)
        # Using 2s to handle edge cases where 1.1s might still land in the same second
        time.sleep(2)

        # Now refresh the token
        refresh_response = await client.post(
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

        # Verify new access token is set as cookie
        cookie_token = extract_cookie(refresh_response, "access_token")
        assert cookie_token is not None
        assert cookie_token == refresh_data["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, client: AsyncClient) -> None:
        """Test refresh fails with invalid refresh token"""
        response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": "invalid_token"},
        )

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_refresh_with_revoked_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test refresh fails after token is revoked (logout)"""
        # Login
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            login_data = login_response.json()
            refresh_token = login_data["refresh_token"]

        # Logout (revoke token)
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_response.status_code == 200

        # Try to refresh with revoked token
        refresh_response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == 401
        assert "Invalid refresh token" in refresh_response.json()["message"]

    @pytest.mark.asyncio
    async def test_refresh_missing_token(self, client: AsyncClient) -> None:
        """Test refresh fails when refresh_token is missing"""
        response = await client.post("/api/v1/auth/refresh-token", json={})

        assert response.status_code == 422  # Validation error


class TestLogoutEndpoint:
    """Tests for POST /logout endpoint"""

    @pytest.mark.asyncio
    async def test_logout_with_valid_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test successful logout with valid refresh token"""
        # Login first
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            login_data = login_response.json()
            refresh_token = login_data["refresh_token"]

        # Logout
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )

        assert logout_response.status_code == 200
        assert logout_response.json()["message"] == "Logged out successfully"

        # Verify access token cookie is cleared
        cookie_token = extract_cookie(logout_response, "access_token")
        # Cookie should be empty or have max_age=0 to clear it
        assert cookie_token == "" or cookie_token is None

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token(self, client: AsyncClient) -> None:
        """Test logout succeeds even with invalid token (silent failure)"""
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "invalid_token"},
        )

        # Logout always succeeds (silent failure for security)
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_missing_token(self, client: AsyncClient) -> None:
        """Test logout fails when refresh_token is missing"""
        response = await client.post("/api/v1/auth/logout", json={})

        assert response.status_code == 422  # Validation error


class TestGetMeEndpoint:
    """Tests for GET /me endpoint"""

    @pytest.mark.asyncio
    async def test_get_me_with_valid_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test getting current user info with valid JWT token"""
        # Login first
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            login_data = login_response.json()
            access_token = login_data["access_token"]

        # Get current user - test both cookie and header auth
        # Test with Authorization header
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        user = response.json()

        # Verify user data
        assert user["email"] == "test@example.com"
        assert user["full_name"] == "Test User"
        assert user["google_id"] == "google-user-123"

    @pytest.mark.asyncio
    async def test_get_me_without_token(self, client: AsyncClient) -> None:
        """Test /me fails without Authorization header or cookie"""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401  # Unauthorized (no auth)

    @pytest.mark.asyncio
    async def test_get_me_with_invalid_token(self, client: AsyncClient) -> None:
        """Test /me fails with invalid JWT token"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_get_me_with_expired_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test /me fails with expired JWT token in cookie"""
        from datetime import datetime, timedelta, timezone

        from trading_api.shared.config import Settings

        settings = Settings()

        # Create expired token (expired 1 minute ago)
        expired_claims = {
            "user_id": "USER-1",
            "email": "test@example.com",
            "full_name": "Test User",
            "picture": "https://example.com/photo.jpg",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=6),
        }

        expired_token = jwt.encode(
            expired_claims,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )

        # Set expired token as cookie on the client instance
        client.cookies.set("access_token", expired_token)

        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()


class TestTokenRotation:
    """Tests for token rotation behavior"""

    @pytest.mark.asyncio
    async def test_old_refresh_token_invalid_after_rotation(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test old refresh token cannot be reused after rotation"""
        # Login
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )
            old_refresh_token = login_response.json()["refresh_token"]

        # Refresh (should rotate tokens)
        refresh_response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token},
        )
        assert refresh_response.status_code == 200

        # Try to use old refresh token again
        reuse_response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token},
        )

        assert reuse_response.status_code == 401
        assert "Invalid refresh token" in reuse_response.json()["message"]


class TestAccessTokenStructure:
    """Tests for JWT access token structure and claims"""

    @pytest.mark.asyncio
    async def test_access_token_is_valid_jwt(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test access token is a valid JWT with correct structure"""
        # Login
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
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

    @pytest.mark.asyncio
    async def test_access_token_expires_in_5_minutes(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test access token expiration is 5 minutes"""
        from datetime import datetime, timezone

        # Login
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            before_login = datetime.now(timezone.utc)
            login_response = await client.post(
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

        # Verify expiration matches configured ACCESS_TOKEN_EXPIRE_MINUTES
        time_to_expiry = (exp_datetime - before_login).total_seconds()
        expected_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert (
            expected_seconds - 10 <= time_to_expiry <= expected_seconds + 10
        )  # Allow 10s margin


class TestIntrospectEndpoint:
    """Tests for GET /introspect endpoint"""

    @pytest.mark.asyncio
    async def test_introspect_with_valid_token(
        self, client: AsyncClient, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test introspect returns valid status for valid token"""
        # First, login to get a valid token
        with patch(
            "trading_api.providers.google.GoogleProvider.verify_token"
        ) as mock_verify:
            mock_verify.return_value = mock_google_claims

            login_response = await client.post(
                "/api/v1/auth/login",
                json={"google_token": "valid_google_id_token"},
            )

        assert login_response.status_code == 200
        access_token = extract_cookie(login_response, "access_token")
        assert access_token is not None

        # Set the cookie for introspect request
        client.cookies.set("access_token", access_token)

        # Introspect the token
        response = await client.get("/api/v1/auth/introspect")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "valid"
        assert "exp" in data
        assert data["exp"] is not None
        assert data.get("error") is None

    @pytest.mark.asyncio
    async def test_introspect_with_expired_token(self, client: AsyncClient) -> None:
        """Test introspect returns expired status for expired token"""
        from trading_api.shared.config import Settings

        settings = Settings()

        # Create an expired token manually
        expired_payload = {
            "user_id": "USER-123",
            "email": "test@example.com",
            "full_name": "Test User",
            "picture": None,
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 3660,
        }

        expired_token = jwt.encode(
            expired_payload,
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )

        # Set the expired cookie
        client.cookies.set("access_token", expired_token)

        # Introspect the expired token
        response = await client.get("/api/v1/auth/introspect")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "expired"
        assert "error" in data
        assert data["error"] is not None
        assert "expired" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_introspect_with_missing_token(self, client: AsyncClient) -> None:
        """Test introspect returns error status when token is missing"""
        # Clear any cookies
        client.cookies.clear()

        # Introspect without token
        response = await client.get("/api/v1/auth/introspect")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "error"
        assert data["error"] == "Missing access token"
        assert data.get("exp") is None

    @pytest.mark.asyncio
    async def test_introspect_with_invalid_token(self, client: AsyncClient) -> None:
        """Test introspect returns error status for invalid token"""
        # Set an invalid token
        client.cookies.set("access_token", "invalid.token.string")

        # Introspect the invalid token
        response = await client.get("/api/v1/auth/introspect")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "error"
        assert "error" in data
        assert data["error"] is not None

    @pytest.mark.asyncio
    async def test_introspect_with_malformed_token(self, client: AsyncClient) -> None:
        """Test introspect returns error status for malformed token"""
        # Set a malformed token
        client.cookies.set("access_token", "not-a-jwt-token")

        # Introspect the malformed token
        response = await client.get("/api/v1/auth/introspect")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "error"
        assert "error" in data
        assert data["error"] is not None
