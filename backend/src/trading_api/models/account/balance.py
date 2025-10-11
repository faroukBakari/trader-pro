"""
Account balance and portfolio models.

This module contains models related to account balances,
balance updates, and account financial information.
"""

from typing import Literal

from pydantic import Field

from ..common import WebSocketMessage


class BalanceUpdate(WebSocketMessage):
    """Account balance update"""

    type: Literal["balance_update"] = "balance_update"
    channel: Literal["account"] = "account"
    asset: str = Field(..., description="Asset symbol (USD, BTC, etc.)")
    available: float = Field(..., description="Available balance")
    locked: float = Field(..., description="Locked balance")
    total: float = Field(..., description="Total balance")


__all__ = [
    "BalanceUpdate",
]
