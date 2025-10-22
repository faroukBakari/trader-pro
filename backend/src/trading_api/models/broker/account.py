"""
Broker account models matching TradingView broker API types
"""

from typing import Optional

from pydantic import BaseModel, Field


class AccountMetainfo(BaseModel):
    """
    Account metadata (matching TradingView AccountMetainfo)
    """

    id: str = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")


# WebSocket models


class EquityData(BaseModel):
    """
    Equity and balance data for account

    Represents the current financial state of an account including
    balance, equity, and profit/loss values.
    """

    equity: float = Field(..., description="Total account equity")
    balance: Optional[float] = Field(None, description="Account balance")
    unrealizedPL: Optional[float] = Field(None, description="Unrealized profit/loss")
    realizedPL: Optional[float] = Field(None, description="Realized profit/loss")


class EquitySubscriptionRequest(BaseModel):
    """WebSocket subscription request for equity/balance updates"""

    accountId: str = Field(..., description="Account ID to subscribe to")
