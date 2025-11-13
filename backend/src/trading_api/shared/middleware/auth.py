"""
Authentication middleware for validating JWT tokens.

⚠️ CRITICAL: This module is INDEPENDENT of the auth module.
- NO database queries
- NO private key access (public key only)
- Stateless validation only
"""

import hashlib
from typing import Annotated

from fastapi import (
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import ValidationError

from trading_api.models.auth import JWTPayload, UserData
from trading_api.shared import settings

# HTTPBearer security scheme for extracting Bearer tokens from REST endpoints
_http_bearer = HTTPBearer(auto_error=False)


def extract_device_fingerprint(request: Request | WebSocket) -> str:
    """
    Generate device fingerprint from request metadata.

    Args:
        request: FastAPI Request or WebSocket object

    Returns:
        SHA256 hash (32 chars) of IP + User-Agent
    """
    components = [
        request.client.host if request.client else "unknown",
        request.headers.get("user-agent", "unknown"),
    ]
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]


async def get_current_user_ws(websocket: WebSocket) -> UserData:
    """
    Validate JWT token from WebSocket query parameter and return user data.

    WebSocket-specific auth dependency that extracts token from query parameter.
    Browser WebSocket connections cannot send Authorization header.

    Args:
        websocket: FastAPI WebSocket object (auto-injected by FastAPI)

    Returns:
        UserData object with user_id, email, full_name, picture, device_fingerprint

    Raises:
        WebSocketException: 1008 if token is invalid, expired, or missing
    """
    token = websocket.query_params.get("token")

    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing authentication token",
        )

    try:
        # Validate JWT signature with public key
        payload_dict = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Validate payload structure with Pydantic
        payload = JWTPayload.model_validate(payload_dict)

        device_fingerprint = extract_device_fingerprint(websocket)

        return UserData(
            user_id=payload.user_id,
            email=payload.email,
            full_name=payload.full_name,
            picture=payload.picture,
            device_fingerprint=device_fingerprint,
        )

    except JWTError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Invalid token: {str(e)}",
        )
    except ValidationError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Invalid token payload: {str(e)}",
        )


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
) -> UserData:
    """
    Validate JWT token and return user data.

    Supports two token extraction methods:
    1. REST: Authorization header (Bearer token) - handled by HTTPBearer
    2. WebSocket: Query parameter (?token=<jwt>) - fallback when credentials is None

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials (None for WebSocket)

    Returns:
        UserData object with user_id, email, full_name, picture, device_fingerprint

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
        payload_dict = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Validate payload structure with Pydantic
        payload = JWTPayload.model_validate(payload_dict)

        device_fingerprint = extract_device_fingerprint(request)

        return UserData(
            user_id=payload.user_id,
            email=payload.email,
            full_name=payload.full_name,
            picture=payload.picture,
            device_fingerprint=device_fingerprint,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token payload: {str(e)}",
        )
