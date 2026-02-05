"""Token models for authentication module.

[ARCHITECTURE] Wave 2B: SQLModel migration
- RefreshTokenData has table=True for database persistence
- Other token DTOs are pure SQLModel (Pydantic-like) without table=True
"""

from datetime import datetime
from enum import Enum
from typing import Any, cast

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class TokenStatus(str, Enum):
    """Token validation status"""

    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class DeviceInfo(SQLModel):
    """Device information for fingerprinting"""

    ip_address: str
    user_agent: str
    fingerprint: str = Field(..., description="Hash of IP + User-Agent")


class TokenResponse(SQLModel):
    """Response containing both access and refresh tokens"""

    access_token: str = Field(..., description="RS256 JWT access token (5-min expiry)")
    refresh_token: str = Field(..., description="Opaque refresh token (URL-safe)")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")


class RefreshRequest(SQLModel):
    """Request to refresh access token"""

    refresh_token: str = Field(..., description="Opaque refresh token")


class LogoutRequest(SQLModel):
    """Request to logout and revoke refresh token"""

    refresh_token: str = Field(..., description="Refresh token to revoke")


class GoogleLoginRequest(SQLModel):
    """Request containing Google OAuth token"""

    google_token: str = Field(..., description="Google OAuth ID token")


class TokenData(SQLModel):
    """Data extracted from JWT token"""

    user_id: str
    email: str | None = None
    exp: int | None = None


class RefreshTokenData(SQLModel, table=True):
    """Refresh token stored in database.

    [ARCHITECTURE]: Primary key is token_hash (bcrypt hash).
    user_id indexed for efficient token lookups by user.
    """

    __tablename__ = cast(Any, "refresh_tokens")

    token_hash: str = Field(primary_key=True, description="Bcrypt hash of the token")
    token_id: str = Field(description="Unique token identifier")
    user_id: str = Field(index=True, description="User ID this token belongs to")
    created_at: datetime = Field(
        description="Token creation timestamp",
        sa_type=cast(type[Any], DateTime(timezone=True)),
    )
    ip_address: str = Field(description="IP address where token was issued")
    user_agent: str = Field(description="User agent string")
    fingerprint: str = Field(description="Device fingerprint hash")


class JWTPayload(SQLModel):
    """JWT access token payload structure"""

    user_id: str
    email: str
    full_name: str | None
    picture: str | None
    exp: int
    iat: int

    model_config = {"frozen": True}  # pyright: ignore[reportAssignmentType]


class UserData(SQLModel):
    """Authenticated user data available in endpoints"""

    user_id: str
    email: str
    full_name: str | None
    picture: str | None
    device_fingerprint: str

    model_config = {"frozen": True}  # pyright: ignore[reportAssignmentType]


class TokenIntrospectResponse(SQLModel):
    """Response from token introspection endpoint"""

    status: TokenStatus = Field(..., description="Token validation status")
    exp: int | None = Field(None, description="Token expiration time (Unix timestamp)")
    error: str | None = Field(None, description="Error message if status is ERROR")
