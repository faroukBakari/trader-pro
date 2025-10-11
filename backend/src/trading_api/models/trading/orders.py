"""
Trading order management models.

This module contains models related to order management,
order updates, and order status tracking.
"""

from typing import Literal, Optional

from pydantic import Field

from ..common import WebSocketMessage


class OrderUpdate(WebSocketMessage):
    """Order status update"""

    type: Literal["order_update"] = "order_update"
    channel: Literal["orders"] = "orders"
    order_id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Symbol name")
    side: Literal["buy", "sell"] = Field(..., description="Order side")
    order_type: Literal["market", "limit", "stop", "stop_limit"] = Field(
        ..., description="Order type"
    )
    status: Literal["pending", "open", "filled", "cancelled", "rejected"] = Field(
        ..., description="Order status"
    )
    quantity: float = Field(..., description="Order quantity")
    filled_quantity: float = Field(..., description="Filled quantity")
    price: Optional[float] = Field(None, description="Order price (for limit orders)")
    average_fill_price: Optional[float] = Field(None, description="Average fill price")


__all__ = [
    "OrderUpdate",
]
