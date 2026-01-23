"""
Broker account models matching TradingView broker API types
"""

from typing import Optional

from pydantic import BaseModel, Field, field_serializer


class AccountMetainfo(BaseModel):
    """
    Account metadata (matching TradingView AccountMetainfo)

    The equity/balance/unrealizedPL/realizedPL fields enable initial display
    before WebSocket streams connect. Frontend uses these for UI initialization,
    then switches to real-time WebSocket updates.

    All currency fields use @field_serializer for consistent 2-decimal precision.

    Attributes:
        id: Unique account identifier (e.g., "DU123456")
        name: Display name for account (typically same as id for TWS)
        currency: Base account currency code (e.g., "USD", "EUR")
        currencySign: Display symbol for currency (e.g., "$", "€")
        equity: Current account equity (optional, for initial display)
        balance: Current account balance (optional, for initial display)
        unrealizedPL: Unrealized profit/loss (optional)
        realizedPL: Realized profit/loss (optional)
    """

    id: str = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")
    currency: Optional[str] = Field(default="USD", description="Account currency")
    currencySign: Optional[str] = Field(
        default="$", description="Account currency sign"
    )
    equity: Optional[float] = Field(default=None, description="Current equity")
    balance: Optional[float] = Field(default=None, description="Current balance")
    unrealizedPL: Optional[float] = Field(default=None, description="Unrealized P&L")
    realizedPL: Optional[float] = Field(default=None, description="Realized P&L")

    @field_serializer("equity", "balance", "unrealizedPL", "realizedPL")
    def round_currency(self, v: float | None) -> float | None:
        return round(v, 2) if v is not None else None


# WebSocket models


class EquityData(BaseModel):
    """
    Equity and balance data for account

    Represents the current financial state of an account including
    balance, equity, and profit/loss values.
    """

    equity: Optional[float] = Field(default=None, description="Total account equity")
    balance: Optional[float] = Field(default=None, description="Account balance")
    unrealizedPL: Optional[float] = Field(
        default=None, description="Unrealized profit/loss"
    )
    realizedPL: Optional[float] = Field(
        default=None, description="Realized profit/loss"
    )

    @field_serializer("equity", "balance", "unrealizedPL", "realizedPL")
    def round_currency(self, v: float | None) -> float | None:
        return round(v, 2) if v is not None else None


class EquitySubscriptionRequest(BaseModel):
    """WebSocket subscription request for equity/balance updates"""

    accountId: str = Field(..., description="Account ID to subscribe to")
