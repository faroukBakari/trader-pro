"""
Broker position models matching TradingView broker API types
"""

from pydantic import BaseModel, Field

# Import Side from orders module (shared enum)
from .orders import Side


class Position(BaseModel):
    """
    Position data (matching TradingView Position/PositionBase)
    Describes a single position
    """

    id: str = Field(..., description="Position ID (usually equal to symbol)")
    symbol: str = Field(..., description="Symbol name")
    qty: float = Field(..., description="Position quantity (positive number)", gt=0)
    side: Side = Field(..., description="Position side")
    avgPrice: float = Field(
        ...,
        description="Weighted average price of all positions for a symbol (used for position line on chart)",
    )

    model_config = {"use_enum_values": True}
