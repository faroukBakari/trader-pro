"""
Base models and common utilities for the trading API.

This module contains shared base classes and utilities
that are used across multiple domains.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BaseApiResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(..., description="Response success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )


class ErrorApiResponse(BaseModel):
    """Error response model"""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Error details")


class SubscriptionResponse(BaseModel):
    """Generic subscription response"""

    status: Literal["ok", "error"] = Field(..., description="Status")
    message: str = Field(..., description="Status message")
    topic: str = Field(..., description="Subscription topic")


__all__ = [
    "BaseApiResponse",
    "ErrorApiResponse",
    "SubscriptionResponse",
]
