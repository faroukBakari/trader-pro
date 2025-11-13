from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TokenStatus(str, Enum):
    """Token validation status"""

    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class DeviceInfo(BaseModel):
    """Device information for fingerprinting"""

    ip_address: str
    user_agent: str
    fingerprint: str = Field(..., description="Hash of IP + User-Agent")


class TokenResponse(BaseModel):
    """Response containing both access and refresh tokens"""

    access_token: str = Field(..., description="RS256 JWT access token (5-min expiry)")
    refresh_token: str = Field(..., description="Opaque refresh token (URL-safe)")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")


class RefreshRequest(BaseModel):
    """Request to refresh access token"""

    refresh_token: str = Field(..., description="Opaque refresh token")


class LogoutRequest(BaseModel):
    """Request to logout and revoke refresh token"""

    refresh_token: str = Field(..., description="Refresh token to revoke")


class GoogleLoginRequest(BaseModel):
    """Request containing Google OAuth token"""

    google_token: str = Field(..., description="Google OAuth ID token")


class TokenData(BaseModel):
    """Data extracted from JWT token"""

    user_id: str
    email: Optional[str] = None
    exp: Optional[int] = None


class RefreshTokenData(BaseModel):
    """Refresh token data stored in Redis"""

    token_id: str = Field(..., description="Unique token identifier")
    user_id: str = Field(..., description="User ID this token belongs to")
    token_hash: str = Field(..., description="Bcrypt hash of the token")
    created_at: datetime = Field(..., description="Token creation timestamp")
    ip_address: str = Field(..., description="IP address where token was issued")
    user_agent: str = Field(..., description="User agent string")
    fingerprint: str = Field(..., description="Device fingerprint hash")


class JWTPayload(BaseModel):
    """JWT access token payload structure"""

    user_id: str
    email: str
    full_name: str | None
    picture: str | None
    exp: int
    iat: int

    model_config = {"frozen": True}


class UserData(BaseModel):
    """Authenticated user data available in endpoints"""

    user_id: str
    email: str
    full_name: str | None
    picture: str | None
    device_fingerprint: str

    model_config = {"frozen": True}


class TokenIntrospectResponse(BaseModel):
    """Response from token introspection endpoint"""

    status: TokenStatus = Field(..., description="Token validation status")
    exp: Optional[int] = Field(
        None, description="Token expiration time (Unix timestamp)"
    )
    error: Optional[str] = Field(None, description="Error message if status is ERROR")
