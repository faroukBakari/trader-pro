"""
Datafeed API endpoints
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..core.datafeed_service import DatafeedService
from ..core.models import (
    Bar,
    DatafeedConfiguration,
    DatafeedHealthResponse,
    GetBarsResponse,
    GetQuotesRequest,
    QuoteData,
    SearchSymbolResultItem,
    SymbolInfo,
)

router = APIRouter(prefix="/datafeed", tags=["datafeed"])

# Initialize the datafeed service
# In production, you might want to inject this as a dependency
datafeed_service = DatafeedService()


@router.get(
    "/config",
    response_model=DatafeedConfiguration,
    summary="Get datafeed configuration",
)
async def get_config() -> DatafeedConfiguration:
    """
    Get datafeed configuration including supported resolutions, exchanges,
    and symbol types. This endpoint provides the configuration needed by
    TradingView charting library.
    """
    try:
        config = datafeed_service.get_configuration()
        return config
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting configuration: {str(e)}"
        )


@router.get(
    "/search", response_model=List[SearchSymbolResultItem], summary="Search symbols"
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
        results = datafeed_service.search_symbols(
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


@router.get("/resolve/{symbol}", response_model=SymbolInfo, summary="Resolve symbol")
async def resolve_symbol(symbol: str) -> SymbolInfo:
    """
    Resolve symbol information by name or ticker.

    - **symbol**: Symbol name or ticker to resolve
    """
    try:
        symbol_info = datafeed_service.resolve_symbol(symbol)
        if not symbol_info:
            raise HTTPException(status_code=404, detail="Symbol not found")
        return symbol_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resolving symbol: {str(e)}")


@router.get("/bars", response_model=GetBarsResponse, summary="Get historical bars")
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
        bars = datafeed_service.get_bars(
            symbol=symbol,
            resolution=resolution,
            from_time=from_time,
            to_time=to_time,
            count_back=count_back,
        )

        # Check if we have meaningful data (more than 1 bar to prevent
        # charting issues)
        if len(bars) < 2:
            return GetBarsResponse(bars=[], no_data=True)

        return GetBarsResponse(bars=bars, no_data=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting bars: {str(e)}")


@router.post(
    "/quotes", response_model=List[QuoteData], summary="Get quotes for symbols"
)
async def get_quotes(request: GetQuotesRequest) -> List[QuoteData]:
    """
    Get real-time quotes for multiple symbols.

    - **symbols**: Array of symbol names to get quotes for
    """
    try:
        quotes = datafeed_service.get_quotes(request.symbols)
        return quotes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting quotes: {str(e)}")


@router.get("/mock-bar/{symbol}", response_model=Bar, summary="Get mock real-time bar")
async def get_mock_bar(symbol: str) -> Bar:
    """
    \"\"\"\n    Get a mock real-time bar for simulation purposes.\n    This endpoint
    simulates real-time price updates by modifying the last\n    historical bar.\n\n
            - **symbol**: Symbol name or ticker\n    \"\"\"
    """
    try:
        mock_bar = datafeed_service.mock_last_bar(symbol)
        if not mock_bar:
            raise HTTPException(
                status_code=404, detail="Symbol not found or no historical data"
            )
        return mock_bar
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting mock bar: {str(e)}")


@router.get(
    "/health", response_model=DatafeedHealthResponse, summary="Datafeed health check"
)
async def datafeed_health() -> DatafeedHealthResponse:
    """
    Health check endpoint for the datafeed service.
    """
    try:
        # Simple health check - verify service can load symbols
        symbols_count = len(datafeed_service._symbols)
        bars_count = len(datafeed_service._sample_bars)

        return DatafeedHealthResponse(
            status="ok",
            message="Datafeed service is running",
            symbols_loaded=symbols_count,
            sample_bars_generated=bars_count,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Datafeed service error: {str(e)}")
