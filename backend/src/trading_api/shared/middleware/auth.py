"""
Authentication middleware for validating JWT tokens.

⚠️ CRITICAL: This module is INDEPENDENT of the auth module.
- NO database queries
- NO private key access (public key only)
- Stateless validation only
"""

import hashlib

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from jose import JWTError, jwt
from pydantic import ValidationError

from trading_api.models.auth import JWTPayload, UserData
from trading_api.shared import settings


def extract_device_fingerprint(request: Request | WebSocket) -> str:
    """
    Generate device fingerprint from request metadata.

    Args:
        request: FastAPI Request or WebSocket object

    Returns:
        SHA256 hash (32 chars) of IP + User-Agent
    """
    host = (request.client.host or "unknown") if request.client else "unknown"
    user_agent = request.headers.get("user-agent") or "unknown"

    components = [host, user_agent]
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]


async def get_current_user_ws(websocket: WebSocket) -> UserData:
    """
    Validate JWT token from WebSocket cookie and return user data.

    Cookie-only authentication for enhanced security.
    Token must be in access_token cookie.

    Args:
        websocket: FastAPI WebSocket object (auto-injected by FastAPI)

    Returns:
        UserData object with user_id, email, full_name, picture, device_fingerprint

    Raises:
        WebSocketException: 1008 if token is invalid, expired, or missing
    """
    # Extract token from cookie only
    token = websocket.cookies.get("access_token")

    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing authentication token in cookie",
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
) -> UserData:
    """
    Validate JWT token from cookie and return user data.

    Cookie-only authentication for enhanced security.
    Token must be in access_token cookie (HttpOnly, Secure, SameSite=Strict).

    Args:
        request: FastAPI request object

    Returns:
        UserData object with user_id, email, full_name, picture, device_fingerprint

    Raises:
        HTTPException: 401 if token is invalid, expired, or missing
    """
    # Extract token from cookie only
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token in cookie",
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
