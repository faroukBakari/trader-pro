"""
Broker account models matching TradingView broker API types
"""

from typing import Optional

from pydantic import BaseModel, Field


class AccountMetainfo(BaseModel):
    """
    Account metadata (matching TradingView AccountMetainfo)

    Attributes:
        id: Unique account identifier (e.g., "DU123456")
        name: Display name for account (typically same as id for TWS)
        currency: Base account currency code (e.g., "USD", "EUR")
        currencySign: Display symbol for currency (e.g., "$", "€")
    """

    id: str = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")
    currency: Optional[str] = Field(default="USD", description="Account currency")
    currencySign: Optional[str] = Field(
        default="$", description="Account currency sign"
    )


# WebSocket models


class EquityData(BaseModel):
    """
    Equity and balance data for account

    Represents the current financial state of an account including
    balance, equity, and profit/loss values.
    """

    equity: float = Field(..., description="Total account equity")
    balance: float = Field(..., description="Account balance")
    unrealizedPL: float = Field(..., description="Unrealized profit/loss")
    realizedPL: float = Field(..., description="Realized profit/loss")


class EquitySubscriptionRequest(BaseModel):
    """WebSocket subscription request for equity/balance updates"""

    accountId: str = Field(..., description="Account ID to subscribe to")
