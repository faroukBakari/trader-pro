"""
Broker connection models for real-time connection status
"""

from typing import Optional

from pydantic import BaseModel, Field


class BrokerConnectionStatus(BaseModel):
    """
    Broker connection status

    Represents the connection state between the backend and the real broker.
    Status values: 1 = Connected, 0 = Disconnected
    """

    status: int = Field(
        ..., description="Connection status (1 = Connected, 0 = Disconnected)"
    )
    message: Optional[str] = Field(None, description="Status message")
    disconnectType: Optional[int] = Field(None, description="Type of disconnection")
    timestamp: int = Field(..., description="Timestamp in milliseconds")


# WebSocket models


class BrokerConnectionSubscriptionRequest(BaseModel):
    """WebSocket subscription request for broker connection status updates"""

    accountId: str = Field(..., description="Account ID to subscribe to")
