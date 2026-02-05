import hashlib
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from authlib.integrations.starlette_client import OAuth
from jose import jwt

from trading_api.capabilities.auth import AuthCapability
from trading_api.models.auth import (
    DeviceInfo,
    JWTPayload,
    TokenResponse,
    User,
    UserCreate,
)
from trading_api.models.common import ProviderCapabilitySpec
from trading_api.models.exceptions import ServiceException
from trading_api.modules.auth.repository import RefreshTokenRepository, UserRepository
from trading_api.shared import settings
from trading_api.shared.service_interface import ServiceInterface


class AuthServiceInterface(ABC):
    """Abstract interface for authentication service"""

    @abstractmethod
    async def verify_google_id_token(self, id_token: str) -> dict[str, Any]:
        """
        Verify Google ID token and return claims.
        Raises HTTPException(401) if invalid.
        """

    @abstractmethod
    async def authenticate_google_user(
        self, id_token: str, device_info: DeviceInfo
    ) -> TokenResponse:
        """
        Authenticate user with Google ID token.
        Returns access token and refresh token.
        """

    @abstractmethod
    async def refresh_access_token(
        self, refresh_token: str, device_info: DeviceInfo
    ) -> TokenResponse:
        """
        Refresh access token using refresh token.
        Implements token rotation: issues new tokens, revokes old one.
        """

    @abstractmethod
    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token (logout)"""


class AuthService(AuthServiceInterface, ServiceInterface):
    """Authentication service implementation"""

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        """Return required provider capabilities for this service.

        Returns:
            List containing auth capability requirement
        """
        return [ProviderCapabilitySpec(name="auth")]

    def __init__(self, module_dir: Path, **kwargs: Any) -> None:
        super().__init__(module_dir, **kwargs)
        # Auth doesn't need special datastore capabilities - use first available
        user_datastore = next(iter(self.datastores))
        self.user_repository = UserRepository(user_datastore)
        self.token_repository = RefreshTokenRepository(user_datastore)
        self._oauth: OAuth | None = None

    @property
    def auth_provider(self) -> AuthCapability:  # Return type will be AuthCapability
        """Get auth capability provider.

        Returns:
            Provider implementing AuthCapability

        Raises:
            TypeError: If provider doesn't implement AuthCapability
        """

        provider = self.get_capability_provider("auth")

        # Type narrowing
        if not isinstance(provider, AuthCapability):
            raise TypeError(f"Expected AuthCapability, got {type(provider).__name__}")

        return provider

    @property
    def oauth(self) -> OAuth:
        """Lazy initialization of OAuth instance for testability"""
        if self._oauth is None:
            self._oauth = OAuth()
            self._oauth.register(
                name="google",
                client_id=settings.GOOGLE_CLIENT_ID,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            )
        return self._oauth

    async def verify_google_id_token(self, id_token: str) -> dict[str, Any]:
        """
        Verify Google ID token and return claims.
        Raises HTTPException(401) if invalid.

        .. deprecated::
            Use auth_provider.verify_token() instead.
            This method will be removed in a future version.
        """
        claims = await self.auth_provider.verify_token(id_token)
        return claims

    async def authenticate_google_user(
        self, id_token: str, device_info: DeviceInfo
    ) -> TokenResponse:
        """
        Authenticate user with Google ID token.
        Returns access token and refresh token.
        """
        # Use injected auth provider instead of direct Google API call
        claims = await self.auth_provider.verify_token(id_token)

        google_id = claims["sub"]
        email = claims["email"]
        full_name = claims.get("name", "")
        picture = claims.get("picture", "")

        user = await self.user_repository.get_by_google_id(google_id)

        if user is None:
            user_data = UserCreate(
                email=email,
                google_id=google_id,
                full_name=full_name,
                picture=picture,
            )
            user = await self.user_repository.create(user_data)
        else:
            await self.user_repository.update_last_login(user.id)

        access_token = self._create_access_token(user)
        refresh_token = self._generate_refresh_token()
        token_hash = self._hash_token(refresh_token)

        token_id = f"TOKEN-{secrets.token_urlsafe(16)}"
        await self.token_repository.store_token(
            token_id=token_id,
            user_id=user.id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=datetime.now(),
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_access_token(
        self, refresh_token: str, device_info: DeviceInfo
    ) -> TokenResponse:
        """
        Refresh access token using refresh token.
        Implements token rotation: issues new tokens, revokes old one.
        """
        token_hash = self._hash_token(refresh_token)

        token_data = await self.token_repository.get_token(
            token_hash, device_info.fingerprint
        )

        if token_data is None:
            raise ServiceException(
                code="SERVICE_AUTH_INVALID_REFRESH_TOKEN",
                message="Invalid refresh token",
                module="auth",
            )

        user = await self.user_repository.get_by_id(token_data["user_id"])
        if user is None:
            raise ServiceException(
                code="SERVICE_AUTH_USER_NOT_FOUND",
                message="User not found",
                module="auth",
            )

        new_access_token = self._create_access_token(user)
        new_refresh_token = self._generate_refresh_token()
        new_token_hash = self._hash_token(new_refresh_token)

        new_token_id = f"TOKEN-{secrets.token_urlsafe(16)}"
        await self.token_repository.store_token(
            token_id=new_token_id,
            user_id=user.id,
            token_hash=new_token_hash,
            device_info=device_info,
            created_at=datetime.now(),
        )

        await self.token_repository.revoke_token(token_hash)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token (logout)"""
        token_hash = self._hash_token(refresh_token)
        await self.token_repository.revoke_token(token_hash)

    def _create_access_token(self, user: User) -> str:
        """Create RS256 JWT access token with full user data"""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = JWTPayload(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            picture=user.picture,
            exp=int(expire.timestamp()),
            iat=int(now.timestamp()),
        )
        encoded_jwt = jwt.encode(
            payload.model_dump(mode="json"),
            settings.jwt_private_key,
            algorithm=settings.JWT_ALGORITHM,
        )
        return encoded_jwt

    def _generate_refresh_token(self) -> str:
        """Generate opaque refresh token"""
        return secrets.token_urlsafe(64)

    def _hash_token(self, token: str) -> str:
        """
        Hash token using SHA256.
        Note: For production, consider using bcrypt/argon2 for better security.
        SHA256 is used here to avoid bcrypt 72-byte limit and passlib/bcrypt compatibility issues.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
