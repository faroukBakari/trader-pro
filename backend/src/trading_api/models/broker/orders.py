"""
Broker order models matching TradingView broker API types
"""

from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, Field


class OrderStatus(IntEnum):
    """Order status enumeration matching TradingView OrderStatus"""

    CANCELED = 1
    FILLED = 2
    INACTIVE = 3
    PLACING = 4
    REJECTED = 5
    WORKING = 6


class OrderType(IntEnum):
    """Order type enumeration matching TradingView OrderType"""

    LIMIT = 1
    MARKET = 2
    STOP = 3
    STOP_LIMIT = 4


class Side(IntEnum):
    """Order/Position side enumeration matching TradingView Side"""

    BUY = 1
    SELL = -1


class StopType(IntEnum):
    """Stop type enumeration matching TradingView StopType"""

    STOP_LOSS = 0
    TRAILING_STOP = 1
    GUARANTEED_STOP = 2


class PreOrder(BaseModel):
    """
    Order request from client (matching TradingView PreOrder)
    Input value of broker's place order command
    """

    symbol: str = Field(..., description="Symbol identifier")
    type: OrderType = Field(..., description="Order type")
    side: Side = Field(..., description="Order/execution side")
    qty: float = Field(..., description="Order quantity", gt=0)
    limitPrice: Optional[float] = Field(None, description="Order limit price")
    stopPrice: Optional[float] = Field(None, description="Order stop price")
    takeProfit: Optional[float] = Field(
        None, description="Order take profit (Brackets)"
    )
    stopLoss: Optional[float] = Field(None, description="Order stop loss (Brackets)")
    guaranteedStop: Optional[float] = Field(
        None, description="Order guaranteed stop loss (Brackets)"
    )
    trailingStopPips: Optional[float] = Field(
        None, description="Order trailing stop (Brackets)"
    )
    stopType: Optional[StopType] = Field(None, description="Type of stop order")

    model_config = {"use_enum_values": True}


class PlacedOrder(BaseModel):
    """
    Complete order with status (matching TradingView PlacedOrder/PlacedOrderBase)
    Contains information about a placed order
    """

    id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Symbol name")
    type: OrderType = Field(..., description="Order type")
    side: Side = Field(..., description="Order side (buy or sell)")
    qty: float = Field(..., description="Order quantity", gt=0)
    status: OrderStatus = Field(..., description="Order status")
    limitPrice: Optional[float] = Field(None, description="Price for the limit order")
    stopPrice: Optional[float] = Field(None, description="Price for the stop order")
    takeProfit: Optional[float] = Field(
        None, description="Take profit price (Brackets)"
    )
    stopLoss: Optional[float] = Field(None, description="Stop loss price (Brackets)")
    guaranteedStop: Optional[float] = Field(
        None, description="Guaranteed stop loss price (Brackets)"
    )
    trailingStopPips: Optional[float] = Field(
        None, description="Trailing stop pips value (Brackets)"
    )
    stopType: Optional[StopType] = Field(None, description="Stop loss type")
    filledQty: Optional[float] = Field(None, description="Filled order quantity")
    avgPrice: Optional[float] = Field(
        None, description="Average fulfilled price for the order"
    )
    updateTime: Optional[int] = Field(
        None, description="Last update time (unix timestamp in milliseconds)"
    )

    model_config = {"use_enum_values": True}


class PlaceOrderResult(BaseModel):
    """
    Result of placing an order (matching TradingView PlaceOrderResult)
    """

    orderId: str = Field(..., description="Order ID (mainly for debugging)")

    model_config = {"use_enum_values": True}


class OrderPreviewSectionRow(BaseModel):
    """Single row in order preview section table (matching TradingView OrderPreviewSectionRow)"""

    title: str = Field(..., description="Description of the item")
    value: str = Field(..., description="Formatted value of the item")


class OrderPreviewSection(BaseModel):
    """Single section in order preview (matching TradingView OrderPreviewSection)"""

    rows: list[OrderPreviewSectionRow] = Field(..., description="Section rows")
    header: Optional[str] = Field(None, description="Optional section title")


class OrderPreviewResult(BaseModel):
    """
    Order preview result (matching TradingView OrderPreviewResult)
    Shows estimated costs, fees, margin before placing order
    """

    sections: list[OrderPreviewSection] = Field(..., description="Preview sections")
    confirmId: Optional[str] = Field(None, description="Confirmation ID for placeOrder")
    warnings: Optional[list[str]] = Field(None, description="Warning messages")
    errors: Optional[list[str]] = Field(None, description="Error messages")

    model_config = {"use_enum_values": True}


# WebSocket models


class OrderSubscriptionRequest(BaseModel):
    """WebSocket subscription request for order updates"""

    accountId: str = Field(..., description="Account ID to subscribe to")
