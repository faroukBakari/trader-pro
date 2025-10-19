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

    symbol: str = Field(..., description="Symbol name")
    price: float = Field(..., description="Execution price")
    qty: float = Field(..., description="Execution quantity", gt=0)
    side: Side = Field(..., description="Execution side")
    time: int = Field(..., description="Time (unix timestamp in milliseconds)")

    model_config = {"use_enum_values": True}
