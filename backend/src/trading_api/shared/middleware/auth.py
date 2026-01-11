"""
Authentication middleware for validating JWT tokens.

⚠️ CRITICAL: This module is INDEPENDENT of the auth module.
- NO database queries
- NO private key access (public key only)
- Stateless validation only
"""

import hashlib
import hmac
import time

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from jose import JWTError, jwt
from pydantic import ValidationError

from trading_api.models.auth import JWTPayload, UserData
from trading_api.shared import settings


def compute_signature(
    hmac_key: bytes,
    timestamp: str,
    caller_id: str,
    method: str,
    url: str,
    body: bytes | None,
) -> str:
    """Compute HMAC-SHA256 signature for internal request.

    Args:
        hmac_key: Secret key for HMAC
        timestamp: Unix timestamp as string
        caller_id: Identifier of the calling module
        method: HTTP method (GET, POST, etc.)
        url: Full request URL
        body: Request body bytes (or None)

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    body_hash = hashlib.sha256(body or b"").hexdigest()
    message = f"{timestamp}|{caller_id}|{method}|{url}|{body_hash}"
    return hmac.new(hmac_key, message.encode(), hashlib.sha256).hexdigest()


def verify_signature(
    hmac_key: bytes,
    signature: str,
    timestamp: str,
    caller_id: str,
    method: str,
    url: str,
    body: bytes | None,
    ttl_seconds: int = 30,
) -> bool:
    """Verify signature and check timestamp freshness.

    Args:
        hmac_key: Secret key for HMAC
        signature: Signature to verify
        timestamp: Unix timestamp as string
        caller_id: Identifier of the calling module
        method: HTTP method (GET, POST, etc.)
        url: Full request URL
        body: Request body bytes (or None)
        ttl_seconds: Maximum age of request in seconds

    Returns:
        True if signature is valid and timestamp within TTL window
    """
    # 1. Check timestamp is within TTL window
    try:
        request_time = int(timestamp)
        if abs(time.time() - request_time) > ttl_seconds:
            return False
    except ValueError:
        return False

    # 2. Compute expected signature
    expected = compute_signature(hmac_key, timestamp, caller_id, method, url, body)

    # 3. Timing-safe comparison
    return hmac.compare_digest(signature, expected)


# Pre-defined user for internal service-to-service calls
INTERNAL_USER = UserData(
    user_id="INTERNAL-SERVICE",
    email="internal@system",
    full_name="Internal Service",
    picture=None,
    device_fingerprint="internal",
)


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

    Supports two authentication methods:
    1. Internal HMAC signature (for inter-module calls)
    2. Cookie-based JWT (for user requests)

    Args:
        request: FastAPI request object

    Returns:
        UserData object with user_id, email, full_name, picture, device_fingerprint

    Raises:
        HTTPException: 401 if token is invalid, expired, or missing
    """
    # Check for internal signature headers first
    signature = request.headers.get("X-Internal-Signature")
    timestamp = request.headers.get("X-Internal-Timestamp")
    caller_id = request.headers.get("X-Internal-Caller")

    if signature and timestamp and caller_id and settings.internal_hmac_key:
        body = await request.body()
        if verify_signature(
            settings.internal_hmac_key,
            signature,
            timestamp,
            caller_id,
            request.method,
            str(request.url),
            body,
            settings.INTERNAL_SIGNATURE_TTL_SECONDS,
        ):
            return INTERNAL_USER

    # Cookie-based authentication for user requests
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
