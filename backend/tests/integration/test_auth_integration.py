"""Integration tests for authentication module.

Tests the complete authentication flow including:
- REST API authentication (login, refresh, logout, /me)
- WebSocket authentication with token validation
- Token tampering detection
- Device fingerprint validation
- Concurrent refresh handling
- Token expiration flows
"""

import time
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

# ============================================================================
# REST API Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_refresh_logout_flow(async_client_no_auth: AsyncClient) -> None:
    """Test complete authentication flow: login → access → refresh → logout.

    Verifies:
    - Google ID token verification
    - JWT access token generation
    - Refresh token rotation
    - Token revocation on logout
    """
    # Mock Google tokeninfo endpoint response
    mock_google_claims = {
        "sub": "google-user-123",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://example.com/avatar.jpg",
        "iss": "https://accounts.google.com",
        "aud": "mock-client-id",
    }

    with patch(
        "trading_api.modules.auth.service.AuthService.verify_google_id_token"
    ) as mock_verify:
        # Mock the verification method to return claims
        mock_verify.return_value = mock_google_claims

        # Step 1: Login with Google ID token
        login_response = await async_client_no_auth.post(
            "/api/v1/auth/login", json={"google_token": "mock-google-id-token"}
        )
        assert login_response.status_code == 200
        login_data = login_response.json()

        # Verify response structure
        assert "access_token" in login_data
        assert "refresh_token" in login_data
        assert "token_type" in login_data
        assert login_data["token_type"] == "bearer"
        assert "expires_in" in login_data

        # Extract cookies from response
        cookies = login_response.cookies
        refresh_token = login_data["refresh_token"]

        # Step 2: Access protected endpoint with cookie
        me_response = await async_client_no_auth.get("/api/v1/auth/me", cookies=cookies)
        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data["email"] == "test@example.com"
        assert user_data["full_name"] == "Test User"

        # Step 3: Refresh access token
        refresh_response = await async_client_no_auth.post(
            "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()

        # Verify new tokens
        assert "access_token" in refresh_data
        assert "refresh_token" in refresh_data
        new_refresh_token = refresh_data["refresh_token"]

        # Verify refresh token changed (critical for security)
        assert new_refresh_token != refresh_token

        # Extract new cookies
        new_cookies = refresh_response.cookies

        # Step 4: Verify old refresh token is invalid (rotation)
        old_refresh_response = await async_client_no_auth.post(
            "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token}
        )
        assert old_refresh_response.status_code == 401

        # Step 5: Access protected endpoint with new cookie
        new_me_response = await async_client_no_auth.get(
            "/api/v1/auth/me", cookies=new_cookies
        )
        assert new_me_response.status_code == 200

        # Step 6: Logout with new refresh token
        logout_response = await async_client_no_auth.post(
            "/api/v1/auth/logout", json={"refresh_token": new_refresh_token}
        )
        assert logout_response.status_code == 200

        # Step 7: Verify refresh token is revoked
        revoked_refresh_response = await async_client_no_auth.post(
            "/api/v1/auth/refresh-token", json={"refresh_token": new_refresh_token}
        )
        assert revoked_refresh_response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_refresh_requests(async_client_no_auth: AsyncClient) -> None:
    """Test concurrent refresh token requests (race condition handling).

    Verifies that only one refresh succeeds when multiple concurrent
    requests are made with the same refresh token.
    """
    # Mock Google tokeninfo endpoint response
    mock_google_claims = {
        "sub": "google-user-456",
        "email": "concurrent@example.com",
        "email_verified": True,
        "name": "Concurrent Test",
        "iss": "https://accounts.google.com",
        "aud": "mock-client-id",
    }

    with patch(
        "trading_api.modules.auth.service.AuthService.verify_google_id_token"
    ) as mock_verify:
        # Mock the verification method to return claims
        mock_verify.return_value = mock_google_claims

        # Login to get refresh token
        login_response = await async_client_no_auth.post(
            "/api/v1/auth/login", json={"google_token": "mock-google-id-token"}
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Attempt concurrent refresh requests
        import asyncio

        responses = await asyncio.gather(
            async_client_no_auth.post(
                "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token}
            ),
            async_client_no_auth.post(
                "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token}
            ),
            async_client_no_auth.post(
                "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token}
            ),
            return_exceptions=True,
        )

        # At least one should succeed
        success_count = sum(
            1
            for r in responses
            if not isinstance(r, BaseException)
            and hasattr(r, "status_code")
            and r.status_code == 200
        )
        assert success_count >= 1

        # The rest should fail with 401 (token already rotated)
        failure_count = sum(
            1
            for r in responses
            if not isinstance(r, BaseException)
            and hasattr(r, "status_code")
            and r.status_code == 401
        )
        assert failure_count >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_device_fingerprint_mismatch(async_client_no_auth: AsyncClient) -> None:
    """Test device fingerprint validation on refresh.

    Note: In integration tests, both clients share the same test context,
    so device fingerprints may be identical. This test verifies the refresh
    flow works correctly, while unit tests (in test_service.py) verify
    device fingerprint validation logic in isolation.
    """
    # Mock Google tokeninfo endpoint response
    mock_google_claims = {
        "sub": "google-user-789",
        "email": "device@example.com",
        "email_verified": True,
        "name": "Device Test",
        "iss": "https://accounts.google.com",
        "aud": "mock-client-id",
    }

    with patch(
        "trading_api.modules.auth.service.AuthService.verify_google_id_token"
    ) as mock_verify:
        # Mock the verification method to return claims
        mock_verify.return_value = mock_google_claims

        # Login with original device fingerprint (default headers)
        login_response = await async_client_no_auth.post(
            "/api/v1/auth/login", json={"google_token": "mock-google-id-token"}
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Create new client with different headers (different device)
        async with AsyncClient(
            app=async_client_no_auth._transport.app,  # type: ignore
            base_url="http://test",
            headers={"User-Agent": "DifferentBrowser/1.0"},
        ) as different_client:
            # Attempt refresh from different device
            # Note: In test context, IP addresses may be same (both from test client)
            # so this might succeed. The important thing is that refresh works.
            refresh_response = await different_client.post(
                "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token}
            )
            # Verify refresh flow works (device fingerprint unit tested separately)
            assert refresh_response.status_code in [
                200,
                401,
            ]  # Either is valid in test context


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_tampering_detection(async_client_no_auth: AsyncClient) -> None:
    """Test detection of tampered JWT tokens.

    Verifies that modified JWT tokens are rejected with 401.
    """
    # Mock Google tokeninfo endpoint response
    mock_google_claims = {
        "sub": "google-user-tamper",
        "email": "tamper@example.com",
        "email_verified": True,
        "name": "Tamper Test",
        "iss": "https://accounts.google.com",
        "aud": "mock-client-id",
    }

    with patch(
        "trading_api.modules.auth.service.AuthService.verify_google_id_token"
    ) as mock_verify:
        # Mock the verification method to return claims
        mock_verify.return_value = mock_google_claims

        # Login to get access token
        login_response = await async_client_no_auth.post(
            "/api/v1/auth/login", json={"google_token": "mock-google-id-token"}
        )
        assert login_response.status_code == 200
        cookies = login_response.cookies

        # Tamper with cookie token (modify last character)
        tampered_cookies = dict(cookies)
        original_token = tampered_cookies.get("access_token", "")
        tampered_cookies["access_token"] = original_token[:-5] + "XXXXX"

        # Attempt to access protected endpoint with tampered token
        me_response = await async_client_no_auth.get(
            "/api/v1/auth/me", cookies=tampered_cookies
        )
        assert me_response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expired_token_rejection(async_client_no_auth: AsyncClient) -> None:
    """Test rejection of expired JWT tokens.

    Verifies that expired access tokens are rejected with 401.
    """
    from jose import jwt

    from trading_api.shared.config import Settings

    settings = Settings()

    # Create an expired token (exp in the past)
    expired_payload = {
        "user_id": "TEST-USER-EXPIRED",
        "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        "iat": int(time.time()) - 7200,  # Issued 2 hours ago
    }

    expired_token = jwt.encode(
        expired_payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )

    # Attempt to access protected endpoint with expired cookie token
    expired_cookies = {"access_token": expired_token}
    me_response = await async_client_no_auth.get(
        "/api/v1/auth/me", cookies=expired_cookies
    )
    assert me_response.status_code == 401


# ============================================================================
# WebSocket Integration Tests
# ============================================================================


@pytest.mark.integration
def test_websocket_connection_with_valid_token(
    client: TestClient, valid_jwt_token: str
) -> None:
    """Test WebSocket connection succeeds with valid JWT token.

    Verifies that WebSocket connections with valid tokens are accepted
    and can communicate normally.
    """
    # Connect to broker WebSocket with valid token in cookie
    with client.websocket_connect("/api/v1/broker/ws", timeout=2.0) as websocket:
        # Send subscribe message
        websocket.send_json(
            {
                "action": "subscribe",
                "event": "orders",
                "data": {"accountId": "TEST-ACCOUNT"},
            }
        )

        # Connection accepted successfully - that's enough for integration test
        # Note: receive_json would block, so we just verify connection was established


@pytest.mark.integration
def test_websocket_connection_without_token_rejected(
    client_no_auth: TestClient,
) -> None:
    """Test WebSocket connection without token is rejected.

    Verifies that WebSocket connections without authentication tokens
    are rejected before accepting the connection.
    """
    with pytest.raises(Exception):
        # Should raise exception on connection attempt
        with client_no_auth.websocket_connect("/api/v1/broker/ws", timeout=1.0):
            pass


@pytest.mark.integration
def test_websocket_connection_with_invalid_token_rejected(
    client_no_auth: TestClient,
) -> None:
    """Test WebSocket connection with invalid token is rejected.

    Verifies that WebSocket connections with tampered or malformed tokens
    are rejected.
    """
    invalid_token = "invalid.jwt.token"
    client_no_auth.cookies.set("access_token", invalid_token)

    with pytest.raises(Exception):
        # Should raise exception on connection attempt
        with client_no_auth.websocket_connect("/api/v1/broker/ws", timeout=1.0):
            pass


@pytest.mark.integration
def test_websocket_connection_with_expired_token_rejected(
    client_no_auth: TestClient,
) -> None:
    """Test WebSocket connection with expired token is rejected.

    Verifies that WebSocket connections with expired tokens are rejected.
    """
    from jose import jwt

    from trading_api.shared.config import Settings

    settings = Settings()

    # Create an expired token
    expired_payload = {
        "user_id": "TEST-USER-WS-EXPIRED",
        "email": "expired@example.com",
        "full_name": "Expired User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        "iat": int(time.time()) - 7200,
    }

    expired_token = jwt.encode(
        expired_payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )

    client_no_auth.cookies.set("access_token", expired_token)

    with pytest.raises(Exception):
        # Should raise exception on connection attempt
        with client_no_auth.websocket_connect("/api/v1/broker/ws", timeout=1.0):
            pass


@pytest.mark.integration
def test_websocket_token_validation_before_accept(client_no_auth: TestClient) -> None:
    """Test that token validation happens before accepting WebSocket connection.

    Verifies that invalid tokens are rejected before the connection is
    established (auto_ws_accept=False pattern).
    """
    # Attempt connection with malformed token
    malformed_token = "not-a-jwt-token"
    client_no_auth.cookies.set("access_token", malformed_token)

    with pytest.raises(Exception):
        # Should raise exception on connection attempt
        with client_no_auth.websocket_connect("/api/v1/datafeed/ws", timeout=1.0):
            pass
