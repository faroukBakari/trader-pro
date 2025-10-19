"""
Broker account models matching TradingView broker API types
"""

from pydantic import BaseModel, Field


class AccountMetainfo(BaseModel):
    """
    Account metadata (matching TradingView AccountMetainfo)
    """

    id: str = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")
