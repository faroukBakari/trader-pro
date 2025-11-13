"""
Authentication middleware for validating JWT tokens.

⚠️ CRITICAL: This module is INDEPENDENT of the auth module.
- NO database queries
- NO private key access (public key only)
- Stateless validation only
"""

import hashlib
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from trading_api.shared import settings

# HTTPBearer security scheme for extracting Bearer tokens
_http_bearer = HTTPBearer()


def extract_device_fingerprint(request: Request) -> str:
    """
    Generate device fingerprint from request metadata.

    Args:
        request: FastAPI request object

    Returns:
        SHA256 hash (32 chars) of IP + User-Agent
    """
    components = [
        request.client.host if request.client else "unknown",
        request.headers.get("user-agent", "unknown"),
    ]
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]


async def get_current_user(
    request: Request,
    credentials: (
        Annotated[HTTPAuthorizationCredentials, Depends(_http_bearer)] | None
    ) = None,
) -> dict[str, str]:
    """
    Validate JWT token and return user data.

    Supports two token extraction methods:
    1. REST: Authorization header (Bearer token) - handled by HTTPBearer
    2. WebSocket: Query parameter (?token=<jwt>)

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials (None for WebSocket)

    Returns:
        dict with 'user_id' and 'device_fingerprint'

    Raises:
        HTTPException: 401 if token is invalid, expired, or missing
    """
    token: str | None = None

    # Extract token from Authorization header (REST)
    if credentials is not None:
        token = credentials.credentials
    # Extract token from query parameter (WebSocket)
    else:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
        )

    try:
        # Validate JWT signature with public key
        payload = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )

        user_id = payload.get("user_id")
        if not user_id or not isinstance(user_id, str):
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user_id",
            )

        device_fingerprint = extract_device_fingerprint(request)

        return {
            "user_id": user_id,
            "device_fingerprint": device_fingerprint,
        }

    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}",
        )
