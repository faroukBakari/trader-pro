"""
Datafeed API endpoints
"""

from typing import Any, List, Optional

from fastapi import HTTPException, Query

from trading_api.models import (
    DatafeedConfiguration,
    GetBarsResponse,
    GetQuotesRequest,
    QuoteData,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.shared.api import APIRouterInterface

from ..service import DatafeedService


class DatafeedApi(APIRouterInterface):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        @self.get(
            "/config",
            response_model=DatafeedConfiguration,
            summary="Get datafeed configuration",
            operation_id="getConfig",
        )
        async def get_config() -> DatafeedConfiguration:
            """
            Get datafeed configuration including supported resolutions, exchanges,
            and symbol types. This endpoint provides the configuration needed by
            TradingView charting library.
            """
            try:
                config = self.service.get_configuration()
                return config
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error getting configuration: {str(e)}"
                )

        @self.get(
            "/search",
            response_model=List[SearchSymbolResultItem],
            summary="Search symbols",
            operation_id="searchSymbols",
        )
        async def search_symbols(
            user_input: str = Query(..., description="User search input"),
            exchange: str = Query("", description="Exchange filter"),
            symbol_type: str = Query("", description="Symbol type filter"),
            max_results: int = Query(50, description="Maximum results"),
        ) -> List[SearchSymbolResultItem]:
            """
            Search symbols based on user input and optional filters.

            - **user_input**: Text to search for in symbol name, description, or ticker
            - **exchange**: Filter by exchange (optional)
            - **symbol_type**: Filter by symbol type (optional)
            - **max_results**: Maximum number of results to return
            """

            try:
                results = self.service.search_symbols(
                    user_input=user_input,
                    exchange=exchange,
                    symbol_type=symbol_type,
                    max_results=max_results,
                )
                return results
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error searching symbols: {str(e)}"
                )

        @self.get(
            "/resolve/{symbol}",
            response_model=SymbolInfo,
            summary="Resolve symbol",
            operation_id="resolveSymbol",
        )
        async def resolve_symbol(symbol: str) -> SymbolInfo:
            """
            Resolve symbol information by name or ticker.

            - **symbol**: Symbol name or ticker to resolve
            """
            try:
                symbol_info = self.service.resolve_symbol(symbol)
                if not symbol_info:
                    raise HTTPException(status_code=404, detail="Symbol not found")
                return symbol_info
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error resolving symbol: {str(e)}"
                )

        @self.get(
            "/bars",
            response_model=GetBarsResponse,
            summary="Get historical bars",
            operation_id="getBars",
        )
        async def get_bars(
            symbol: str = Query(..., description="Symbol name"),
            resolution: str = Query(..., description="Resolution (e.g., '1D')"),
            from_time: int = Query(..., description="From timestamp (seconds)"),
            to_time: int = Query(..., description="To timestamp (seconds)"),
            count_back: Optional[int] = Query(None, description="Count back"),
        ) -> GetBarsResponse:
            """
            Get historical OHLC bars for a symbol.

            - **symbol**: Symbol name or ticker
            - **resolution**: Time resolution (currently only '1D' is supported)
            - **from_time**: Start timestamp in seconds
            - **to_time**: End timestamp in seconds
            - **count_back**: Number of bars to count back (optional)
            """
            try:
                bars = self.service.get_bars(
                    symbol=symbol,
                    resolution=resolution,
                    from_time=from_time,
                    to_time=to_time,
                    count_back=count_back,
                )
                return GetBarsResponse(bars=bars, no_data=len(bars) == 0)
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error getting bars: {str(e)}"
                )

        @self.post(
            "/quotes",
            response_model=List[QuoteData],
            summary="Get quotes for symbols",
            operation_id="getQuotes",
        )
        async def get_quotes(body: GetQuotesRequest) -> List[QuoteData]:
            """
            Get real-time quotes for multiple symbols.

            - **symbols**: Array of symbol names to get quotes for
            """
            try:
                quotes = self.service.get_quotes(body.symbols)
                return quotes
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error getting quotes: {str(e)}"
                )

    @property
    def service(self) -> DatafeedService:
        """Get the DatafeedService instance.

        Returns:
            DatafeedService: The datafeed service
        """
        if not isinstance(self._service, DatafeedService):
            raise ValueError("Service has not been initialized")
        return self._service


__all__ = ["DatafeedApi"]
