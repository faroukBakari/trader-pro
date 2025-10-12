"""Generic WebSocket message wrappers"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SubscriptionRequest(BaseModel):
    """Generic subscription request"""

    symbol: str = Field(..., description="Symbol to subscribe to")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Additional subscription parameters"
    )


class SubscriptionResponse(BaseModel):
    """Generic subscription response"""

    status: Literal["ok", "error"] = Field(..., description="Status")
    symbol: str = Field(..., description="Symbol")
    message: str = Field(..., description="Status message")
    topic: str = Field(..., description="Subscription topic")
