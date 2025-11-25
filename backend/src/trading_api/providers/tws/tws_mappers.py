"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, etc.).
"""

from ibapi.contract import ContractDescription

from trading_api.models.market import SearchSymbolResultItem

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


__all__ = ["SEC_TYPE_MAP", "contract_description_to_search_result"]
