"""
Market data search functionality models.

This module contains models related to symbol search
requests and search result handling.
"""

from pydantic import BaseModel, Field


class SearchSymbolsRequest(BaseModel):
    """Request model for searchSymbols endpoint"""

    user_input: str = Field(..., description="User search input")
    exchange: str = Field(default="", description="Exchange filter")
    symbol_type: str = Field(default="", description="Symbol type filter")
    max_results: int = Field(default=50, description="Maximum results")


__all__ = [
    "SearchSymbolsRequest",
]
