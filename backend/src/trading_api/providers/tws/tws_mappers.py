"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, SymbolInfo, Bar, etc.).
"""

from ibapi.contract import ContractDescription, ContractDetails

from trading_api.models.market import SearchSymbolResultItem, SymbolInfo

# TWS secType → TradingView-style symbol type
SEC_TYPE_MAP: dict[str, str] = {
    "STK": "stock",
    "OPT": "option",
    "FUT": "futures",
    "FOP": "option",
    "CASH": "forex",
    "BOND": "bond",
    "FUND": "fund",
    "IND": "index",
    "CMDTY": "commodity",
    "WAR": "warrant",
    "CRYPTO": "crypto",
    "NEWS": "news",
    "BAG": "combo",
}

# Default supported resolutions for TWS datafeed
DEFAULT_SUPPORTED_RESOLUTIONS: list[str] = [
    "1",
    "5",
    "15",
    "30",
    "60",
    "1D",
    "1W",
    "1M",
]


def contract_description_to_search_result(
    desc: ContractDescription,
) -> SearchSymbolResultItem:
    """Map TWS ContractDescription → domain SearchSymbolResultItem.

    Args:
        desc: TWS ContractDescription from symbolSamples callback

    Returns:
        Domain SearchSymbolResultItem for frontend consumption
    """
    contract = desc.contract
    return SearchSymbolResultItem(
        symbol=contract.symbol,
        description=contract.description or f"{contract.symbol} ({contract.secType})",
        exchange=contract.primaryExchange or contract.exchange,
        ticker=contract.localSymbol or contract.symbol,
        type=SEC_TYPE_MAP.get(contract.secType, "stock"),
    )


def contract_details_to_symbol_info(details: ContractDetails) -> SymbolInfo:
    """Map TWS ContractDetails → domain SymbolInfo.

    Args:
        details: TWS ContractDetails from contractDetails callback

    Returns:
        Domain SymbolInfo for frontend consumption (TradingView LibrarySymbolInfo)
    """
    contract = details.contract

    # Calculate pricescale from minTick (e.g., minTick=0.01 → pricescale=100)
    pricescale = (
        int(1 / details.minTick) if details.minTick and details.minTick > 0 else 100
    )

    # Determine symbol type
    symbol_type = SEC_TYPE_MAP.get(contract.secType, "stock")

    return SymbolInfo(
        name=contract.symbol,
        description=details.longName or contract.symbol,
        type=symbol_type,
        session=details.tradingHours or "0930-1600",
        timezone=details.timeZoneId or "America/New_York",
        ticker=contract.localSymbol or contract.symbol,
        exchange=contract.primaryExchange or contract.exchange,
        listed_exchange=contract.exchange,
        format="price",
        pricescale=pricescale,
        minmov=1,
        has_intraday=True,
        has_daily=True,
        supported_resolutions=DEFAULT_SUPPORTED_RESOLUTIONS,
        volume_precision=0,
        data_status="streaming",
    )


__all__ = [
    "SEC_TYPE_MAP",
    "DEFAULT_SUPPORTED_RESOLUTIONS",
    "contract_description_to_search_result",
    "contract_details_to_symbol_info",
]
