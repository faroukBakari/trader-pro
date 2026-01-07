"""
Market data configuration and health models.

This module contains models related to datafeed configuration,
health checks, and system status.
"""

from typing import List

from pydantic import BaseModel, Field

from .bars import Resolution
from .instruments import DatafeedSymbolType, Exchange


class DatafeedConfiguration(BaseModel):
    """Datafeed configuration model matching DatafeedConfiguration interface"""

    supported_resolutions: List[Resolution] = Field(
        default_factory=lambda: [Resolution.MIN_5, Resolution.DAY_1, Resolution.WEEK_1],
        description="Supported resolutions",
    )
    supports_marks: bool = Field(default=False, description="Supports marks")
    supports_timescale_marks: bool = Field(
        default=False, description="Supports timescale marks"
    )
    supports_time: bool = Field(default=False, description="Supports time")

    exchanges: List[Exchange] = Field(
        default_factory=lambda: [
            Exchange(value="", name="All Exchanges", desc=""),
            Exchange(value="NASDAQ", name="NASDAQ", desc="NASDAQ"),
            Exchange(value="NYSE", name="NYSE", desc="NYSE"),
        ],
        description="Available exchanges",
    )
    symbols_types: List[DatafeedSymbolType] = Field(
        default_factory=lambda: [
            DatafeedSymbolType(name="All types", value=""),
            DatafeedSymbolType(name="Stock", value="stock"),
            DatafeedSymbolType(name="Crypto", value="crypto"),
            DatafeedSymbolType(name="Forex", value="forex"),
        ],
        description="Available symbol types",
    )

    currency_codes: List[str] = Field(
        default_factory=lambda: [
            "USD",  # US Dollar
            "EUR",  # Euro
            "GBP",  # British Pound
            "JPY",  # Japanese Yen
            "CNH",  # Chinese Yuan (offshore)
            "CHF",  # Swiss Franc
            "CAD",  # Canadian Dollar
            "AUD",  # Australian Dollar
            "HKD",  # Hong Kong Dollar
            "SGD",  # Singapore Dollar
            "KRW",  # South Korean Won
            "INR",  # Indian Rupee
            "MXN",  # Mexican Peso
            "BRL",  # Brazilian Real
            "SEK",  # Swedish Krona
            "NOK",  # Norwegian Krone
            "DKK",  # Danish Krone
            "NZD",  # New Zealand Dollar
            "ZAR",  # South African Rand
            "RUB",  # Russian Ruble
        ],
        description="Supported currencies for price conversion",
    )


__all__ = [
    "DatafeedConfiguration",
]
