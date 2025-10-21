"""
Broker leverage and brackets models matching TradingView broker API types
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .orders import OrderType, Side


class Brackets(BaseModel):
    """
    Position bracket orders (stop-loss, take-profit)
    Matching TradingView Brackets interface
    """

    stopLoss: Optional[float] = Field(None, description="Stop loss price")
    guaranteedStop: Optional[float] = Field(None, description="Guaranteed stop price")
    takeProfit: Optional[float] = Field(None, description="Take profit price")
    trailingStopPips: Optional[float] = Field(
        None, description="Trailing stop pips value"
    )


class LeverageInfoParams(BaseModel):
    """
    Parameters for requesting leverage information
    Matching TradingView LeverageInfoParams interface
    """

    symbol: str = Field(..., description="Symbol identifier")
    orderType: OrderType = Field(..., description="Order type")
    side: Side = Field(..., description="Order side (buy or sell)")
    customFields: Optional[Dict[str, Any]] = Field(
        None, description="Custom data for the broker"
    )

    model_config = {"use_enum_values": True}


class LeverageInfo(BaseModel):
    """
    Leverage information for a symbol
    Matching TradingView LeverageInfo interface
    """

    title: str = Field(..., description="Title for leverage dialogs")
    leverage: float = Field(..., description="Current leverage value")
    min: float = Field(..., description="Minimum leverage value")
    max: float = Field(..., description="Maximum leverage value")
    step: float = Field(..., description="Minimum change between leverage values")


class LeverageSetParams(LeverageInfoParams):
    """
    Parameters for setting leverage (extends LeverageInfoParams)
    Matching TradingView LeverageSetParams interface
    """

    leverage: float = Field(..., description="Requested leverage value")


class LeverageSetResult(BaseModel):
    """
    Result of setting leverage
    Matching TradingView LeverageSetResult interface
    """

    leverage: float = Field(..., description="Confirmed leverage value")


class LeveragePreviewResult(BaseModel):
    """
    Preview messages for leverage changes
    Matching TradingView LeveragePreviewResult interface
    """

    infos: Optional[list[str]] = Field(
        None, description="Informative messages about the leverage value"
    )
    warnings: Optional[list[str]] = Field(
        None, description="Warnings about the leverage value"
    )
    errors: Optional[list[str]] = Field(
        None, description="Errors about the leverage value"
    )
