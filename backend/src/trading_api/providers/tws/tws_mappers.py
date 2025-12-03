"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, SymbolInfo, Bar, QuoteData, etc.).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from trading_api.providers.tws.tws_models import RTMarketData

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
        if "-" in segment:
            start, end = segment.split("-", 1)
            start_time = start.split(":", 1)[1] if ":" in start else start
            end_time = end.split(":", 1)[1] if ":" in end else end
            return start_time + "-" + end_time

    return "0930-1600"  # Fallback


TWS_TIMEZONE_MAP: dict[str, str] = {
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Mountain": "US/Mountain",  # TradingView supports this one
    "US/Pacific": "America/Los_Angeles",
    # Add more as encountered
}


def _normalize_timezone(tws_timezone: str) -> str:
    """Convert TWS timeZoneId to TradingView-compatible timezone."""
    return TWS_TIMEZONE_MAP.get(tws_timezone, tws_timezone) or "America/New_York"


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
        timezone=_normalize_timezone(details.timeZoneId),
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


def rt_market_data_to_bar(rt_data: "RTMarketData") -> Bar:
    """Convert RTMarketData bar fields → domain Bar.

    Args:
        rt_data: RTMarketData instance with bar fields populated

    Returns:
        Domain Bar model
    """
    return Bar(
        time=(rt_data.bar_time or 0) * 1000,
        open=float(rt_data.bar_open or 0.0),
        high=float(rt_data.bar_high or 0.0),
        low=float(rt_data.bar_low or 0.0),
        close=float(rt_data.bar_close or 0.0),
        volume=rt_data.bar_volume or 0,
        count=rt_data.bar_count or 0,
    )


def tws_ticks_to_quote_data(
    symbol: str,
    ticks: dict[str, float | int | str],
) -> QuoteData:
    """Convert TWS tick data → domain QuoteData.

    Args:
        symbol: Symbol name
        ticks: Dictionary with "prices" and "sizes" from TWS callbacks
               Example: {"prices": {1: 150.25, 2: 150.30}, "sizes": {0: 100}}

    Returns:
        QuoteData with status="ok" and QuoteValues populated from ticks
    """

    # Extract tick values (use sentinel for missing, convert to 0.0 for output)
    def get_price(tick_type: int) -> float:
        val = ticks.get(get_tick_type_name(tick_type))
        return round(float(val), 2) if val is not None else 0.0

    bid = get_price(TickTypeEnum.BID)
    ask = get_price(TickTypeEnum.ASK)
    last = get_price(TickTypeEnum.LAST)
    open_price = get_price(TickTypeEnum.OPEN) or last
    high_price = get_price(TickTypeEnum.HIGH) or last
    low_price = get_price(TickTypeEnum.LOW) or last
    close_price = get_price(TickTypeEnum.CLOSE) or last
    ticks.get(get_tick_type_name(TickTypeEnum.BID_SIZE))
    ticks.get(get_tick_type_name(TickTypeEnum.ASK_SIZE))
    volume = ticks.get(get_tick_type_name(TickTypeEnum.VOLUME))

    # Calculate spread (if both bid and ask available)
    spread = round(ask - bid, 2) if (ask > 0 and bid > 0) else 0.0

    # Calculate change and change percent (if last and close available)
    if last > 0 and close_price > 0:
        change = round(last - close_price, 2)
        change_percent = round((change / close_price) * 100, 2)
    else:
        change = 0.0
        change_percent = 0.0

    # Build QuoteValues with available data
    quote_values = QuoteValues(
        lp=last,
        ask=ask,
        bid=bid,
        spread=spread,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        prev_close_price=close_price,
        volume=int(volume) if volume is not None else 0,
        ch=change,
        chp=change_percent,
        short_name=symbol,
        exchange="",  # Not provided in tick data
        description=f"Quote for {symbol}",
        original_name=symbol,
    )

    return QuoteData(s="ok", n=symbol, v=quote_values)


def rt_market_data_to_quote_data(rt_data: "RTMarketData") -> QuoteData:
    """Convert RTMarketData tick fields → domain QuoteData.

    Args:
        rt_data: RTMarketData instance with tick fields populated

    Returns:
        QuoteData with status="ok" and QuoteValues populated from rt_data
    """
    symbol = rt_data.contract.symbol if rt_data.contract else "UNKNOWN"
    exchange = (
        rt_data.contract.primaryExchange or rt_data.contract.exchange
        if rt_data.contract
        else ""
    )

    # Extract values with defaults
    bid = round(rt_data.bid or 0.0, 2)
    ask = round(rt_data.ask or 0.0, 2)
    last = round(rt_data.last or 0.0, 2)
    open_price = round(rt_data.open or last, 2)
    high_price = round(rt_data.high or last, 2)
    low_price = round(rt_data.low or last, 2)
    close_price = round(rt_data.close or last, 2)
    volume = rt_data.volume or 0

    # Calculate spread
    spread = round(ask - bid, 2) if (ask > 0 and bid > 0) else 0.0

    # Calculate change and change percent
    if last > 0 and close_price > 0:
        change = round(last - close_price, 2)
        change_percent = round((change / close_price) * 100, 2)
    else:
        change = 0.0
        change_percent = 0.0

    quote_values = QuoteValues(
        lp=last,
        ask=ask,
        bid=bid,
        spread=spread,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        prev_close_price=close_price,
        volume=volume,
        ch=change,
        chp=change_percent,
        short_name=symbol,
        exchange=exchange,
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
    "tws_rt_bar_to_domain_bar",
    "rt_market_data_to_bar",
    "tws_ticks_to_quote_data",
    "rt_market_data_to_quote_data",
]
