import hashlib
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException
from jose import jwt

from trading_api.models.auth import (
    DeviceInfo,
    JWTPayload,
    TokenResponse,
    User,
    UserCreate,
)
from trading_api.modules.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
    RefreshTokenRepositoryInterface,
    UserRepositoryInterface,
)
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

    def __init__(self, module_dir: Path) -> None:
        super().__init__(module_dir)
        self.user_repository: UserRepositoryInterface = InMemoryUserRepository()
        self.token_repository: RefreshTokenRepositoryInterface = (
            InMemoryRefreshTokenRepository()
        )
        self._oauth: OAuth | None = None

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
        """
        try:
            # Use Google's tokeninfo endpoint to verify the token
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"id_token": id_token},
                )

                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=401, detail=f"Invalid Google token: {resp.text}"
                    )

                claims: dict[str, Any] = resp.json()

                # Verify audience
                if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
                    raise HTTPException(
                        status_code=401, detail="Invalid token audience"
                    )

                # Verify email is verified
                email_verified = claims.get("email_verified")
                # Google returns string "true" or boolean True
                if email_verified not in (True, "true"):
                    raise HTTPException(
                        status_code=401, detail="Email not verified by Google"
                    )

                return claims
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Token verification error: {str(e)}"
            )

    async def authenticate_google_user(
        self, id_token: str, device_info: DeviceInfo
    ) -> TokenResponse:
        """
        Authenticate user with Google ID token.
        Returns access token and refresh token.
        """
        claims = await self.verify_google_id_token(id_token)

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
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = await self.user_repository.get_by_id(token_data["user_id"])
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

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
