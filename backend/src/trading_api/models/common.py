"""
Base models and common utilities for the trading API.

This module contains shared base classes and utilities
that are used across multiple domains.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(..., description="Response success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Error details")


# WebSocket Base Models (moved here to avoid circular imports)
class WebSocketMessage(BaseModel):
    """Base WebSocket message with common fields"""

    type: str = Field(..., description="Message type")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp"
    )
    channel: str = Field(..., description="WebSocket channel name")
    request_id: Optional[str] = Field(None, description="Request ID for correlation")


class WebSocketResponse(WebSocketMessage):
    """Base WebSocket response message"""

    success: bool = Field(..., description="Response success status")
    error: Optional[str] = Field(None, description="Error message if failed")


class WebSocketSubscription(BaseModel):
    """WebSocket subscription request"""

    action: Literal["subscribe", "unsubscribe"] = Field(
        ..., description="Subscription action"
    )
    channel: str = Field(..., description="Channel to subscribe/unsubscribe")
    symbol: Optional[str] = Field(None, description="Symbol filter (if applicable)")
    params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")


__all__ = [
    "BaseResponse",
    "ErrorResponse",
    "WebSocketMessage",
    "WebSocketResponse",
    "WebSocketSubscription",
]
