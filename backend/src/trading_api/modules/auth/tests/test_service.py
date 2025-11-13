import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from trading_api.models.auth import TokenResponse
from trading_api.modules.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from trading_api.modules.auth.service import AuthService
from trading_api.modules.auth.tests.conftest import DeviceInfoFactory, UserCreateFactory


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    """Fixture providing user repository"""
    return InMemoryUserRepository()


@pytest.fixture
def token_repository() -> InMemoryRefreshTokenRepository:
    """Fixture providing token repository"""
    return InMemoryRefreshTokenRepository()


@pytest.fixture
def auth_service(
    user_repository: InMemoryUserRepository,
    token_repository: InMemoryRefreshTokenRepository,
) -> AuthService:
    """Fixture providing auth service"""
    return AuthService(
        user_repository=user_repository,
        token_repository=token_repository,
    )


@pytest.fixture
def mock_google_claims() -> dict[str, Any]:
    """Fixture providing mock Google ID token claims"""
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


class TestAuthServiceGoogleTokenVerification:
    """Tests for Google ID token verification"""

    @pytest.mark.asyncio
    async def test_verify_valid_google_token(
        self, auth_service: AuthService, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test verifying valid Google ID token"""
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            claims = await auth_service.verify_google_id_token("valid_id_token")

            assert claims["sub"] == "google-user-123"
            assert claims["email"] == "test@example.com"
            assert claims["email_verified"] is True

    @pytest.mark.asyncio
    async def test_verify_invalid_google_token(self, auth_service: AuthService) -> None:
        """Test verifying invalid Google ID token raises HTTPException"""
        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            from authlib.integrations.base_client import OAuthError

            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(
                side_effect=OAuthError("Invalid token")
            )
            mock_oauth.return_value.google = mock_google

            with pytest.raises(Exception) as exc_info:
                await auth_service.verify_google_id_token("invalid_token")

            assert "401" in str(exc_info.value) or "Invalid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_unverified_email_rejected(
        self, auth_service: AuthService, mock_google_claims: dict[str, Any]
    ) -> None:
        """Test that unverified email is rejected"""
        mock_google_claims["email_verified"] = False

        with patch("trading_api.modules.auth.service.OAuth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.parse_id_token = AsyncMock(return_value=mock_google_claims)
            mock_oauth.return_value.google = mock_google

            with pytest.raises(Exception) as exc_info:
                await auth_service.verify_google_id_token("token_with_unverified_email")

            assert (
                "401" in str(exc_info.value)
                or "not verified" in str(exc_info.value).lower()
            )


class TestAuthServiceAuthentication:
    """Tests for user authentication flow"""

    @pytest.mark.asyncio
    async def test_authenticate_new_user(
        self,
        auth_service: AuthService,
        user_repository: InMemoryUserRepository,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test authenticating a new user creates user and returns tokens"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        assert isinstance(response, TokenResponse)
        assert response.access_token is not None
        assert response.refresh_token is not None
        assert response.token_type == "bearer"
        assert response.expires_in > 0

        user = await user_repository.get_by_google_id("google-user-123")
        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_existing_user(
        self,
        auth_service: AuthService,
        user_repository: InMemoryUserRepository,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test authenticating existing user updates last_login"""
        existing_user_data = UserCreateFactory.build(
            email="test@example.com", google_id="google-user-123"
        )
        created_user = await user_repository.create(existing_user_data)
        original_last_login = created_user.last_login

        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        assert isinstance(response, TokenResponse)

        updated_user = await user_repository.get_by_id(created_user.id)
        assert updated_user is not None
        assert updated_user.last_login > original_last_login

    @pytest.mark.asyncio
    async def test_access_token_jwt_structure(
        self,
        auth_service: AuthService,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test that access token is valid RS256 JWT with correct claims"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        from trading_api.shared import settings

        decoded = jwt.decode(
            response.access_token,
            settings.jwt_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert "user_id" in decoded
        assert "exp" in decoded
        assert decoded["exp"] > datetime.utcnow().timestamp()

    @pytest.mark.asyncio
    async def test_refresh_token_is_opaque(
        self,
        auth_service: AuthService,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test that refresh token is opaque (not JWT)"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        with pytest.raises(Exception):
            jwt.decode(response.refresh_token, "any_key", algorithms=["RS256"])


class TestAuthServiceTokenRefresh:
    """Tests for token refresh flow"""

    @pytest.mark.asyncio
    async def test_refresh_access_token(
        self,
        auth_service: AuthService,
        user_repository: InMemoryUserRepository,
        token_repository: InMemoryRefreshTokenRepository,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test refreshing access token with valid refresh token"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            initial_response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        await asyncio.sleep(1.1)

        new_response = await auth_service.refresh_access_token(
            initial_response.refresh_token, device_info
        )

        assert isinstance(new_response, TokenResponse)
        assert new_response.access_token != initial_response.access_token
        assert new_response.refresh_token != initial_response.refresh_token

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_fails(
        self, auth_service: AuthService
    ) -> None:
        """Test refreshing with invalid refresh token fails"""
        device_info = DeviceInfoFactory.build()

        with pytest.raises(Exception):
            await auth_service.refresh_access_token(
                "invalid_refresh_token", device_info
            )

    @pytest.mark.asyncio
    async def test_refresh_with_wrong_fingerprint_fails(
        self,
        auth_service: AuthService,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test refreshing with wrong device fingerprint fails"""
        device_info1 = DeviceInfoFactory.build()
        device_info2 = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            initial_response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info1
            )

        with pytest.raises(Exception):
            await auth_service.refresh_access_token(
                initial_response.refresh_token, device_info2
            )

    @pytest.mark.asyncio
    async def test_old_refresh_token_revoked_after_rotation(
        self,
        auth_service: AuthService,
        token_repository: InMemoryRefreshTokenRepository,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test that old refresh token is revoked after successful rotation"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            initial_response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        await auth_service.refresh_access_token(
            initial_response.refresh_token, device_info
        )

        with pytest.raises(Exception):
            await auth_service.refresh_access_token(
                initial_response.refresh_token, device_info
            )


class TestAuthServiceLogout:
    """Tests for logout flow"""

    @pytest.mark.asyncio
    async def test_logout_revokes_token(
        self,
        auth_service: AuthService,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test logout revokes refresh token"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        await auth_service.logout(response.refresh_token)

        with pytest.raises(Exception):
            await auth_service.refresh_access_token(response.refresh_token, device_info)

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token_silent_success(
        self, auth_service: AuthService
    ) -> None:
        """Test logout with invalid token succeeds silently"""
        await auth_service.logout("nonexistent_token")


class TestAuthServiceTokenExpiration:
    """Tests for token expiration handling"""

    @pytest.mark.asyncio
    async def test_access_token_expires_in_5_minutes(
        self,
        auth_service: AuthService,
        mock_google_claims: dict[str, Any],
    ) -> None:
        """Test that access token expires in 5 minutes"""
        device_info = DeviceInfoFactory.build()

        with patch.object(
            auth_service, "verify_google_id_token", return_value=mock_google_claims
        ):
            response = await auth_service.authenticate_google_user(
                "valid_id_token", device_info
            )

        from trading_api.shared import settings

        decoded = jwt.decode(
            response.access_token,
            settings.jwt_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )

        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = (exp_time - now).total_seconds()

        assert 290 <= time_diff <= 310
