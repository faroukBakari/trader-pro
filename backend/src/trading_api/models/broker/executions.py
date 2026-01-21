"""
Broker execution models matching TradingView broker API types
"""

from pydantic import BaseModel, Field

# Import Side from orders module (shared enum)
from .orders import Side


class Execution(BaseModel):
    """
    Trade execution record (matching TradingView Execution)
    """

    id: str = Field(..., description="Unique execution ID")
    symbol: str = Field(..., description="Symbol name")
    price: float = Field(..., description="Execution price")
    qty: float = Field(..., description="Execution quantity", gt=0)
    side: Side = Field(..., description="Execution side")
    time: int = Field(..., description="Time (unix timestamp in milliseconds)")
    commission: float | None = Field(
        default=None, description="Commission amount (from TWS commissionAndFeesReport)"
    )

    model_config = {"use_enum_values": True}


# WebSocket models


class ExecutionSubscriptionRequest(BaseModel):
    """WebSocket subscription request for execution updates"""

    accountId: str = Field(..., description="Account ID to subscribe to")
