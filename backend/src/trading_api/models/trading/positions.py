"""
Trading position management models.

This module contains models related to position tracking,
position updates, and position management.
"""

from typing import Literal

from pydantic import Field

from ..common import WebSocketMessage


class PositionUpdate(WebSocketMessage):
    """Position update message"""

    type: Literal["position_update"] = "position_update"
    channel: Literal["positions"] = "positions"
    symbol: str = Field(..., description="Symbol name")
    side: Literal["long", "short"] = Field(..., description="Position side")
    size: float = Field(..., description="Position size")
    entry_price: float = Field(..., description="Average entry price")
    mark_price: float = Field(..., description="Current mark price")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    realized_pnl: float = Field(..., description="Realized P&L")


__all__ = [
    "PositionUpdate",
]
