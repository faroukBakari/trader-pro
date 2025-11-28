"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, SymbolInfo, Bar, QuoteData, etc.).
"""

from datetime import datetime
from decimal import Decimal

from ibapi.common import BarData
from ibapi.contract import ContractDescription, ContractDetails
from ibapi.ticktype import TickTypeEnum

from trading_api.models.market import (
    Bar,
    QuoteData,
    QuoteValues,
    SearchSymbolResultItem,
    SymbolInfo,
)

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

get_tick_type_name_ = TickTypeEnum.idx2name.get


def get_tick_type_name(tick_type: int) -> str:
    """Get the string name for a TickTypeEnum value.
    Args:
        tick_type: TickTypeEnum value
    Returns:
        String name of the tick type
    """
    return get_tick_type_name_(tick_type, f"UNKNOWN_{tick_type}")


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


def _convert_tws_trading_hours_to_session(trading_hours: str) -> str:
    """Convert TWS tradingHours to TradingView session format.

    TWS format: "20251128:0400-20251128:1700;20251129:CLOSED;..."
    TradingView format: "0400-1700" (simple time range, no dates)

    Strategy: Extract first valid non-CLOSED session's time portion.

    Args:
        trading_hours: TWS tradingHours string

    Returns:
        TradingView-compatible session string (e.g., "0930-1600")
    """
    if not trading_hours:
        return "0930-1600"  # Default US equity hours

    for segment in trading_hours.split(";"):
        if "CLOSED" in segment:
            continue
        # Parse "YYYYMMDD:HHMM-YYYYMMDDHHMM" → "HHMM-HHMM"
        if ":" in segment:
            _, times = segment.split(":", 1)
            if "-" in times:
                start_datetime, end_datetime = times.split("-", 1)
                # Extract just HHMM from YYYYMMDDHHMM (last 4 chars after date prefix)
                start_time = start_datetime[-4:]
                end_time = end_datetime[-4:] if len(end_datetime) >= 4 else end_datetime
                return f"{start_time}-{end_time}"

    return "0930-1600"  # Fallback


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
        session=_convert_tws_trading_hours_to_session(details.tradingHours),
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


def tws_bar_to_domain_bar(tws_bar: BarData) -> Bar:
    """Map TWS BarData → domain Bar.

    Args:
        tws_bar: TWS BarData object

    Returns:
        Domain Bar model
    """
    # Parse TWS date format: "yyyyMMdd  HH:mm:ss", "yyyyMMdd", or epoch
    # TWS returns string dates like "20231215  16:00:00" (note: two spaces)
    # Daily bars return just "20231215" without time component
    date_str = tws_bar.date.strip()
    time_ms: int = 0

    # Try datetime with timezone (two spaces)
    try:
        dt = datetime.strptime(date_str, "%Y%m%d  %H:%M:%S US/Eastern")
        time_ms = int(dt.timestamp() * 1000)
    except ValueError:
        # Try single space UTC format
        try:
            dt = datetime.strptime(date_str, "%Y%m%d %H:%M:%S UTC")
            time_ms = int(dt.timestamp() * 1000)
        except ValueError:
            # Try daily bar format (date only, no time)
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
                time_ms = int(dt.timestamp() * 1000)
            except ValueError:
                # Fall back to epoch format (if formatDate=2 was used)
                time_ms = int(date_str) * 1000

    return Bar(
        time=time_ms,
        open=float(tws_bar.open),
        high=float(tws_bar.high),
        low=float(tws_bar.low),
        close=float(tws_bar.close),
        volume=(
            int(tws_bar.volume)
            if isinstance(tws_bar.volume, Decimal)
            else tws_bar.volume
        ),
        count=tws_bar.barCount,
    )


def tws_rt_bar_to_domain_bar(
    time: int = 0,
    open_: float = 0.0,
    high: float = 0.0,
    low: float = 0.0,
    close: float = 0.0,
    volume: Decimal = Decimal(0),
    _: Decimal = Decimal(0),
    count: int = 0,
) -> Bar:
    """Map TWS BarData → domain Bar.

    Args:
        bar.time  - start of bar in unix (or 'epoch') time
        bar.endTime - for synthetic bars, the end time (requires TWS v964). Otherwise -1.
        bar.open_  - the bar's open value
        bar.high  - the bar's high value
        bar.low   - the bar's low value
        bar.close - the bar's closing value
        bar.volume - the bar's traded volume if available
        bar.WAP   - the bar's Weighted Average Price
        bar.count - the number of trades during the bar's timespan (only available

    Returns:
        Domain Bar model
    """
    # Parse TWS date format: "yyyyMMdd  HH:mm:ss" or epoch
    # TWS returns string dates like "20231215  16:00:00" (note: two spaces)
    time = int(time) * 1000
    return Bar(
        time=time,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=(int(volume) if isinstance(volume, Decimal) else volume),
        count=count,
    )


def tws_ticks_to_quote_data(
    symbol: str,
    ticks: dict[str, float | int],
) -> QuoteData:
    """Convert TWS tick data → domain QuoteData.

    Args:
        symbol: Symbol name
        ticks: Dictionary with "prices" and "sizes" from TWS callbacks
               Example: {"prices": {1: 150.25, 2: 150.30}, "sizes": {0: 100}}

    Returns:
        QuoteData with status="ok" and QuoteValues populated from ticks
    """

    # Extract tick values (None if not present)
    bid = ticks.get(get_tick_type_name(TickTypeEnum.BID))
    ask = ticks.get(get_tick_type_name(TickTypeEnum.ASK))
    last = ticks.get(get_tick_type_name(TickTypeEnum.LAST))
    open_price = ticks.get(get_tick_type_name(TickTypeEnum.OPEN))
    high_price = ticks.get(get_tick_type_name(TickTypeEnum.HIGH))
    low_price = ticks.get(get_tick_type_name(TickTypeEnum.LOW))
    close_price = ticks.get(get_tick_type_name(TickTypeEnum.CLOSE))

    ticks.get(get_tick_type_name(TickTypeEnum.BID_SIZE))
    ticks.get(get_tick_type_name(TickTypeEnum.ASK_SIZE))
    volume = ticks.get(get_tick_type_name(TickTypeEnum.VOLUME))

    # Calculate spread (if both bid and ask available)
    spread = (ask - bid) if (ask is not None and bid is not None) else 0.0

    # Calculate change and change percent (if last and close available)
    if last is not None and close_price is not None and close_price != 0:
        change = last - close_price
        change_percent = (change / close_price) * 100
    else:
        change = 0.0
        change_percent = 0.0

    # Build QuoteValues with available data (use 0.0 for missing prices)
    quote_values = QuoteValues(
        lp=last or 0.0,
        ask=ask or 0.0,
        bid=bid or 0.0,
        spread=spread,
        open_price=open_price or 0.0,
        high_price=high_price or 0.0,
        low_price=low_price or 0.0,
        prev_close_price=close_price or 0.0,
        volume=int(volume) if volume is not None else 0,
        ch=change,
        chp=change_percent,
        short_name=symbol,
        exchange="",  # Not provided in tick data
        description=f"Quote for {symbol}",
        original_name=symbol,
    )

    return QuoteData(s="ok", n=symbol, v=quote_values)


__all__ = [
    "SEC_TYPE_MAP",
    "DEFAULT_SUPPORTED_RESOLUTIONS",
    "contract_description_to_search_result",
    "contract_details_to_symbol_info",
    "tws_bar_to_domain_bar",
    "tws_ticks_to_quote_data",
]
