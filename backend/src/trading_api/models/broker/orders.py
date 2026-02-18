"""
Broker order models matching TradingView broker API types
"""

from enum import Enum, IntEnum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


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
    TRAIL = 4


class Side(IntEnum):
    """Order/Position side enumeration matching TradingView Side"""

    BUY = 1
    SELL = -1


class StopType(IntEnum):
    """Stop type enumeration matching TradingView StopType"""

    STOP_LOSS = 0
    TRAILING_STOP = 1
    GUARANTEED_STOP = 2


class OrderOrPositionMessageType(str, Enum):
    """Message type for order/position state messages (matching TradingView)."""

    INFORMATION = "information"
    WARNING = "warning"
    ERROR = "error"


class ParentType(IntEnum):
    """Parent type enumeration matching TradingView ParentType.

    Used to identify the type of parent for bracket orders.
    """

    ORDER = 1
    POSITION = 2
    INDIVIDUAL_POSITION = 3


class CurrentQuotes(BaseModel):
    """
    Current market quotes (matching TradingView AskBid)
    Contains current ask and bid prices
    """

    ask: float = Field(..., description="Current ask price")
    bid: float = Field(..., description="Current bid price")

    model_config = {"use_enum_values": True}


class OrderDuration(BaseModel):
    """Order duration/expiration (matching TradingView OrderDuration)."""

    type: str = Field(..., description="Duration type (e.g., 'DAY', 'GTC', 'GTD')")
    datetime: Optional[int] = Field(
        default=None, description="Expiration timestamp for GTD orders"
    )

    model_config = {"use_enum_values": True}


class OrderOrPositionMessage(BaseModel):
    """Message describing order/position state (matching TradingView)."""

    type: OrderOrPositionMessageType = Field(..., description="Message type")
    text: str = Field(..., description="Message content")

    model_config = {"use_enum_values": True}


class PreOrder(BaseModel):
    """
    Order request from client (matching TradingView PreOrder)
    Input value of broker's place order command
    """

    symbol: str = Field(..., description="Symbol identifier")
    type: OrderType = Field(..., description="Order type")
    side: Side = Field(..., description="Order/execution side")
    qty: float = Field(..., description="Order quantity", gt=0)
    limitPrice: Optional[float] = Field(default=None, description="Order limit price")
    stopPrice: Optional[float] = Field(default=None, description="Order stop price")
    takeProfit: Optional[float] = Field(
        default=None, description="Order take profit (Brackets)"
    )
    stopLoss: Optional[float] = Field(
        default=None, description="Order stop loss (Brackets)"
    )
    guaranteedStop: Optional[float] = Field(
        default=None, description="Order guaranteed stop loss (Brackets)"
    )
    trailingStopPips: Optional[float] = Field(
        default=None, description="Order trailing stop (Brackets)"
    )
    stopType: Optional[StopType] = Field(default=None, description="Type of stop order")
    seenPrice: Optional[float] = Field(
        default=None, description="Price seen at order creation time"
    )
    currentQuotes: Optional[CurrentQuotes] = Field(
        default=None, description="Current market quotes (ask and bid)"
    )
    duration: Optional[OrderDuration] = Field(
        default=None, description="Order duration/expiration"
    )
    isClose: Optional[bool] = Field(
        default=None, description="True if order closes a position"
    )

    model_config = {"use_enum_values": True}


class PlacedOrder(SQLModel, table=True):
    """
    Complete order with status (matching TradingView PlacedOrder/PlacedOrderBase)
    Contains information about a placed order.

    DuckDB table with indexes for fast lookups:
    - Primary key: id (order ID)
    - Index: symbol (for symbol-based queries)
    - Index: parentId (for bracket order lookups)
    """

    __tablename__ = "placed_orders"  # pyright: ignore[reportAssignmentType]

    id: str = Field(primary_key=True, description="Order ID")
    symbol: str = Field(index=True, description="Symbol name")
    type: OrderType = Field(..., description="Order type")
    side: Side = Field(..., description="Order side (buy or sell)")
    qty: float = Field(..., description="Order quantity", gt=0)
    status: OrderStatus = Field(..., description="Order status")
    limitPrice: Optional[float] = Field(
        default=None, description="Price for the limit order"
    )
    stopPrice: Optional[float] = Field(
        default=None, description="Price for the stop order"
    )
    takeProfit: Optional[float] = Field(
        default=None, description="Take profit price (Brackets)"
    )
    stopLoss: Optional[float] = Field(None, description="Stop loss price (Brackets)")
    guaranteedStop: Optional[float] = Field(
        default=None, description="Guaranteed stop loss price (Brackets)"
    )
    trailingStopPips: Optional[float] = Field(
        default=None, description="Trailing stop pips value (Brackets)"
    )
    stopType: Optional[StopType] = Field(default=None, description="Stop loss type")
    filledQty: Optional[float] = Field(
        default=None, description="Filled order quantity"
    )
    avgPrice: Optional[float] = Field(
        default=None, description="Average fulfilled price for the order"
    )
    updateTime: Optional[int] = Field(
        default=None, description="Last update time (unix timestamp in milliseconds)"
    )
    parentId: Optional[str] = Field(
        default=None,
        index=True,
        description="Parent order/position ID for bracket orders",
    )
    parentType: Optional[ParentType] = Field(
        default=None, description="Type of parent (Order=1, Position=2)"
    )
    duration: Optional[OrderDuration] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Order duration/expiration",
    )
    message: Optional[OrderOrPositionMessage] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Order state message",
    )

    model_config = {"use_enum_values": True}  # pyright: ignore[reportAssignmentType]


class PlaceOrderResult(BaseModel):
    """
    Result of placing an order (matching TradingView PlaceOrderResult)
    """

    orderId: Optional[str] = Field(
        default=None, description="Order ID (mainly for debugging)"
    )

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
