"""
System and notification models.

This module contains models for system messages, notifications,
heartbeats, and general system communications.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import Field

from ..common import WebSocketMessage


class TradingNotification(WebSocketMessage):
    """Trading notification message"""

    type: Literal["notification"] = "notification"
    channel: Literal["notifications"] = "notifications"
    category: Literal["info", "warning", "error", "success"] = Field(
        ..., description="Notification category"
    )
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    data: Optional[Dict[str, Any]] = Field(
        None, description="Additional notification data"
    )


class SystemMessage(WebSocketMessage):
    """System status or maintenance message"""

    type: Literal["system"] = "system"
    channel: Literal["system"] = "system"
    event: Literal["maintenance", "service_update", "market_hours"] = Field(
        ..., description="System event type"
    )
    message: str = Field(..., description="System message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional system data")


class HeartbeatMessage(WebSocketMessage):
    """Heartbeat/ping message for connection health"""

    type: Literal["heartbeat"] = "heartbeat"
    channel: Literal["heartbeat"] = "heartbeat"
    server_time: datetime = Field(
        default_factory=datetime.now, description="Server timestamp"
    )


__all__ = [
    "TradingNotification",
    "SystemMessage",
    "HeartbeatMessage",
]
