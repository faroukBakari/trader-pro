"""
Authentication and security models.

This module contains models related to user authentication,
authorization, and security-related messaging.
"""

from typing import List, Literal, Optional

from pydantic import Field

from ..common import WebSocketMessage, WebSocketResponse


class AuthenticationMessage(WebSocketMessage):
    """WebSocket authentication message"""

    type: Literal["auth"] = "auth"
    channel: Literal["auth"] = "auth"
    token: str = Field(..., description="JWT authentication token")


class AuthenticationResponse(WebSocketResponse):
    """WebSocket authentication response"""

    type: Literal["auth_response"] = "auth_response"
    channel: Literal["auth"] = "auth"
    user_id: Optional[str] = Field(None, description="Authenticated user ID")
    permissions: Optional[List[str]] = Field(None, description="User permissions")


__all__ = [
    "AuthenticationMessage",
    "AuthenticationResponse",
]
