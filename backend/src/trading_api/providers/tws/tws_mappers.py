"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, SymbolInfo, Bar, QuoteData, etc.).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.ticktype import TickTypeEnum

from trading_api.models.market import (
    Bar,
    QuoteData,
    QuoteValues,
    Resolution,
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
DEFAULT_SUPPORTED_RESOLUTIONS: list[Resolution] = [
    Resolution.MIN_1,
    Resolution.MIN_5,
    Resolution.MIN_15,
    Resolution.MIN_30,
    Resolution.HOUR_1,
    Resolution.DAY_1,
    Resolution.WEEK_1,
    Resolution.MONTH_1,
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


def ticker_name(contract: Contract, bar_size: str | None = None) -> str:
    ticker = (
        contract.symbol
        + ":"
        + (contract.primaryExchange or contract.exchange)
        + ":"
        + contract.secType
        + "-"
        + str(contract.conId)
    )
    if bar_size:
        ticker += "@" + bar_size
    return ticker


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
    symbol = contract.symbol
    description = contract.description or f"{contract.symbol} ({contract.secType})"
    exchange = contract.primaryExchange or contract.exchange
    type = SEC_TYPE_MAP.get(contract.secType, "stock")
    ticker = (
        symbol + ":" + exchange + ":" + contract.secType + "-" + str(contract.conId)
    )
    return SearchSymbolResultItem(
        symbol=contract.symbol,
        description=description,
        exchange=exchange,
        ticker=ticker,
        type=type,
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
        return "0000-2359"  # Default US equity hours

    # for segment in trading_hours.split(";"):
    #     if "CLOSED" in segment:
    #         continue
    #     # Parse "YYYYMMDD:HHMM-YYYYMMDDHHMM" → "HHMM-HHMM"
    #     if "-" in segment:
    #         start, end = segment.split("-", 1)
    #         start_time = start.split(":", 1)[1] if ":" in start else start
    #         end_time = end.split(":", 1)[1] if ":" in end else end
    #         if int(end_time) < int(start_time):
    #             current_hour = (
    #                 datetime.now().astimezone(ZoneInfo("US/Eastern")).time().hour
    #             )
    #             if int(end_time) / 100 < current_hour:
    #                 end_time = "2359"
    #             else:
    #                 start_time = "0000"

    #         return start_time + "-" + end_time

    return "0000-2359"  # Fallback


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

    symbol = contract.symbol
    exchange = contract.primaryExchange or contract.exchange
    symbol_type = SEC_TYPE_MAP.get(contract.secType, "stock")

    return SymbolInfo(
        name=symbol,
        description=details.longName or symbol,
        type=symbol_type,
        session=_convert_tws_trading_hours_to_session(details.tradingHours),
        timezone=_normalize_timezone(details.timeZoneId),
        ticker=(
            symbol + ":" + exchange + ":" + contract.secType + "-" + str(contract.conId)
        ),
        exchange=exchange,
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


def parse_tws_bar_date(date_str: str) -> int:
    """Parse TWS bar date string to milliseconds timestamp.

    Handles multiple TWS date formats:
    - "yyyyMMdd  HH:mm:ss US/Eastern" (two spaces, timezone)
    - "yyyyMMdd HH:mm:ss UTC" (single space, UTC)
    - "yyyyMMdd" (daily bars, date only)
    - epoch string (if formatDate=2 was used)

    Args:
        date_str: TWS date string

    Returns:
        Timestamp in milliseconds
    """
    date_str = date_str.strip()
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

    return time_ms


def tws_bar_to_domain_bar(tws_bar: BarData) -> Bar:
    """Map TWS BarData → domain Bar.

    Args:
        tws_bar: TWS BarData object

    Returns:
        Domain Bar model
    """
    return Bar(
        time=parse_tws_bar_date(tws_bar.date),
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


def tws_ticks_to_bar(rt_data: dict[str, Any]) -> Bar:
    # Prefer bar_date (string) over bar_time (legacy int)
    if rt_data.get("bar_date"):
        time_ms = parse_tws_bar_date(rt_data["bar_date"])
    elif rt_data.get("bar_time"):
        time_ms = rt_data["bar_time"] * 1000
    else:
        time_ms = 0
    return Bar(
        time=time_ms,
        open=float(rt_data.get("bar_open", 0.0)),
        high=float(rt_data.get("bar_high", 0.0)),
        low=float(rt_data.get("bar_low", 0.0)),
        close=float(rt_data.get("bar_close", 0.0)),
        volume=rt_data.get("bar_volume", 0),
        count=rt_data.get("bar_count", 0),
    )


def tws_ticks_to_quote_data(rt_data: dict[str, Any]) -> QuoteData:
    symbol, exchange, _, _, _ = parse_ticker(rt_data.get("ticker_name", "UNKNOWN"))

    # Extract values with defaults
    bid = round(rt_data.get("bid", 0.0), 2)
    ask = round(rt_data.get("ask", 0.0), 2)
    last = round(rt_data.get("last", 0.0), 2)
    open_price = round(rt_data.get("bar_open", last), 2)
    high_price = round(rt_data.get("bar_high", last), 2)
    low_price = round(rt_data.get("bar_low", last), 2)
    close_price = round(rt_data.get("bar_close", last), 2)
    volume = rt_data.get("bar_volume", 0)
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


def parse_ticker(ticker: str) -> tuple[str, str, str, str, str]:
    """Parse ticker string into components.
    Args:
        ticker: Ticker string in format "SYMBOL:EXCHANGE:SECTYPE-CONTRACTID"
    Returns:
        Tuple of (symbol_name, exchange, secType, contractId, bar_size)
    Examples:
        >>> self.parse_ticker('AAPL:NASDAQ:STK-12345@1D')
        ('AAPL', 'NASDAQ', 'STK', '12345', '1D')
        >>> self.parse_ticker('GOOGL:NASDAQ')
        ('GOOGL', 'NASDAQ', '', '', '')
    """

    ticker_parts = ticker.split(":")
    symbol_name = ticker_parts[0].strip()
    exchange = ""
    if len(ticker_parts) > 1:
        exchange = ticker_parts[1].strip()
    secType = ""
    contractId = ""
    bar_size = ""
    if len(ticker_parts) > 2:
        ticker_parts = ticker_parts[2].split("-")
        secType = ticker_parts[0].strip()
        if len(ticker_parts) > 1:
            ticker_parts = ticker_parts[1].split("@")
            contractId = ticker_parts[0].strip()
            if len(ticker_parts) > 1:
                bar_size = ticker_parts[1].strip()
    return symbol_name, exchange, secType, contractId, bar_size


def build_contract(
    ticker: str,
) -> Contract:
    """Build TWS Contract object from domain parameters.

    Args:
        symbol: Symbol name (e.g., "AAPL")
        exchange: Exchange name (default: "SMART" for smart routing)
        sec_type: Security type (default: "STK" for stocks)
        currency: Currency code (default: "USD")

    Returns:
        TWS Contract object ready for API calls
    """
    symbol, exchange, sec_type, conId, _ = parse_ticker(ticker)
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange if exchange else "SMART"
    contract.primaryExchange = exchange
    contract.conId = int(conId)
    return contract


def map_resolution_to_tws_bar_size(resolution: Resolution) -> str:
    """Map domain Resolution → TWS barSizeSetting.

    Args:
        resolution: Domain Resolution enum (TradingView format)

    Returns:
        TWS bar size string ("1 min", "5 mins", "1 hour", "1 day", etc.)

    Raises:
        DatafeedError: If resolution not supported
    """
    # Map Resolution enum members directly to TWS bar size strings
    # Resolution values are TradingView format: "1", "5", "60", "1D", "1W", "1M", "12M"
    mapping: dict[Resolution, str] = {
        Resolution.MIN_1: "1 min",
        Resolution.MIN_5: "5 mins",
        Resolution.MIN_15: "15 mins",
        Resolution.MIN_30: "30 mins",
        Resolution.HOUR_1: "1 hour",
        Resolution.DAY_1: "1 day",
        Resolution.WEEK_1: "1 week",
        Resolution.MONTH_1: "1 month",
        Resolution.YEAR_1: "1 month",  # TWS doesn't support year bars, use monthly
    }

    bar_size = mapping.get(resolution)
    if not bar_size:
        raise ValueError(
            f"Unsupported resolution: {resolution}. "
            f"Supported: {[r.name for r in mapping.keys()]}"
        )
    return bar_size


def calculate_tws_duration(
    start_time: datetime, end_time: datetime, resolution: Resolution
) -> str:
    """Calculate TWS duration string from time range.

    TWS requires duration in format: "n S|D|W|M|Y"
    Maximum durations depend on bar size (e.g., 1 sec bars max 2000 S)

    Args:
        start_time: Start datetime
        end_time: End datetime
        resolution: Bar resolution (used to select appropriate unit)

    Returns:
        TWS duration string (e.g., "1 D", "2 W", "86400 S")
    """
    delta = end_time - start_time

    # Select duration unit based on resolution and time range
    # TWS limits: seconds (max 2000 S), days (max 365 D), weeks, months, years

    # Intraday bars (1 min - 1 hour)
    if resolution in [
        Resolution.MIN_1,
        Resolution.MIN_5,
        Resolution.MIN_15,
        Resolution.MIN_30,
        Resolution.HOUR_1,
    ]:
        # Use days for intraday bars
        days = delta.days + 1
        if days <= 365:
            return f"{days} D"
        # Use years for very long ranges
        weeks = days // 365 + 1
        return f"{weeks} Y"

    # Daily and above
    else:
        days = delta.days + 1
        if days <= 365:
            return f"{days} D"
        # TWS: durations > 52 weeks must use years
        years = days // 365 + 1
        return f"{years} Y"


__all__ = [
    "SEC_TYPE_MAP",
    "DEFAULT_SUPPORTED_RESOLUTIONS",
    "parse_tws_bar_date",
    "contract_description_to_search_result",
    "contract_details_to_symbol_info",
    "tws_bar_to_domain_bar",
    "tws_rt_bar_to_domain_bar",
    "tws_ticks_to_bar",
    "tws_ticks_to_quote_data",
    "parse_ticker",
    "build_contract",
    "map_resolution_to_tws_bar_size",
    "calculate_tws_duration",
]
