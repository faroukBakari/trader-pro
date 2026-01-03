"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, SymbolInfo, Bar, QuoteData, etc.).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.order import Order
from ibapi.ticktype import TickTypeEnum

from trading_api.models.broker import (
    AccountMetainfo,
    EquityData,
    OrderStatus,
    OrderType,
    PlacedOrder,
    Position,
    PreOrder,
    Side,
    StopType,
)
from trading_api.models.exceptions import ProviderException
from trading_api.models.market import (
    Bar,
    QuoteData,
    QuoteValues,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.providers.tws.order_tracker import TrackedOrder

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
    if not (
        contract.symbol
        and contract.secType
        and (contract.primaryExchange or contract.exchange)
    ):
        raise ProviderException(
            code="TWS_PROVIDER_INVALID_CONTRACT",
            message=f"Invalid contract for ticker generation: {contract}",
            provider="tws",
            capability="shared",
        )
    ticker = (
        contract.symbol
        + ":"
        + (contract.primaryExchange or contract.exchange)
        + ":"
        + contract.secType
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
    if not (symbol and exchange and contract.secType):
        raise ProviderException(
            code="TWS_PROVIDER_INVALID_TICKER",
            message=f"Invalid contract description: {desc}",
            provider="tws",
            capability="shared",
        )
    ticker = symbol + ":" + exchange + ":" + contract.secType
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
    symbol_type = SEC_TYPE_MAP.get(contract.secType, "stock")

    return SymbolInfo(
        name=symbol,
        description=details.longName or symbol,
        type=symbol_type,
        session=_convert_tws_trading_hours_to_session(details.tradingHours),
        timezone=_normalize_timezone(details.timeZoneId),
        ticker=(
            symbol
            + ":"
            + (contract.primaryExchange or contract.exchange)
            + ":"
            + contract.secType
        ),
        exchange=contract.primaryExchange,
        listed_exchange=contract.primaryExchange,
        format="price",
        pricescale=pricescale,
        minmov=1,
        has_intraday=True,
        has_daily=True,
        supported_resolutions=DEFAULT_SUPPORTED_RESOLUTIONS,
        volume_precision=0,
        data_status="streaming",
    )


# Regex: "YYYYMMDD<1-2 spaces>HH:MM:SS <timezone>"
_TWS_DATE_TZ_PATTERN = re.compile(r"^(\d{8})\s{1,2}(\d{2}:\d{2}:\d{2})\s+(.+)$")


def parse_tws_bar_date(date_str: str) -> int:
    """Parse TWS bar date string to milliseconds timestamp.

    Handles multiple TWS date formats dynamically:
    - "yyyyMMdd  HH:mm:ss <timezone>" (1-2 spaces, any timezone like US/Eastern, US/Central, UTC)
    - "yyyyMMdd" (daily bars, date only)
    - epoch string (if formatDate=2 was used)

    Args:
        date_str: TWS date string

    Returns:
        Timestamp in milliseconds

    Raises:
        ProviderException: If date format is unrecognized
    """
    date_str = date_str.strip()

    # 1. Try datetime with timezone (US/Eastern, US/Central, UTC, etc.)
    if match := _TWS_DATE_TZ_PATTERN.match(date_str):
        date_part, time_part, tz_name = match.groups()
        dt_naive = datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H:%M:%S")
        dt = dt_naive.replace(tzinfo=ZoneInfo(tz_name))
        return int(dt.timestamp() * 1000)

    # 2. Try daily bar format (date only, 8 digits)
    if len(date_str) == 8 and date_str.isdigit():
        dt = datetime.strptime(date_str, "%Y%m%d")
        return int(dt.timestamp() * 1000)

    # 3. Try epoch format (formatDate=2)
    if date_str.isdigit():
        return int(date_str) * 1000

    # 4. Unrecognized format
    raise ProviderException(
        provider="tws",
        capability="datafeed",
        code="PROVIDER_TWS_INVALID_DATE_FORMAT",
        message=f"Cannot parse TWS bar date: '{date_str}'",
    )


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


def tws_ticks_to_bar(rt_data: dict[str, Any]) -> Bar:
    # Prefer bar_date (string) over bar_time (legacy int)
    if rt_data.get("date"):
        time_ms = parse_tws_bar_date(rt_data["date"])
    elif rt_data.get("time"):
        time_ms = rt_data["time"] * 1000
    else:
        time_ms = 0
    raw_vol = rt_data.get("volume", 0)
    volume = int(raw_vol) if isinstance(raw_vol, Decimal) else raw_vol
    return Bar(
        time=time_ms,
        open=float(rt_data.get("open", 0.0)),
        high=float(rt_data.get("high", 0.0)),
        low=float(rt_data.get("low", 0.0)),
        close=float(rt_data.get("close", 0.0)),
        volume=volume,
        count=rt_data.get("count", 0),
    )


def _parse_rt_volume(rt_volume_str: str | None) -> tuple[float, float, float]:
    """Parse RT Trade Volume string to extract last price, volume, and vwap.

    Format: "price;size;timestamp;totalVolume;vwap;singleMM"
    Example: "320.64;1.0;1765200318856;363.0;320.359;true"

    Args:
        rt_volume_str: RT Volume or RT Trade Volume string from TWS

    Returns:
        Tuple of (last_price, total_volume, vwap) - returns (0.0, 0, 0.0) if parsing fails
    """
    if not rt_volume_str or rt_volume_str.startswith(";"):
        # Empty string or starts with ";" (odd lot with no price)
        return 0.0, 0, 0.0

    parts = rt_volume_str.split(";")
    if len(parts) >= 5:
        last_price = float(parts[0]) if parts[0] else 0.0
        total_volume = int(float(parts[3])) if parts[3] else 0
        vwap = float(parts[4]) if parts[4] else 0.0
        return last_price, total_volume, vwap

    return 0.0, 0, 0.0


def tws_ticks_to_quote_data(rt_data: dict[str, Any]) -> QuoteData:
    business_key = rt_data.get("business_key", "UNKNOWN")
    ticker_name = business_key.split(":", 3)[-1] or "UNKNOWN"
    symbol, exchange, _, _ = parse_ticker(ticker_name)
    ticker_name = ticker_name.split("@")[0]

    # Parse RT Trade Volume as fallback source (more reliable than rt_volume)
    rt_trd_volume = rt_data.get("rt_trd_volume") or rt_data.get("rt_volume")
    rt_last, rt_volume, _ = _parse_rt_volume(rt_trd_volume)

    # Extract values with fallbacks: direct tick > rt_volume > 0
    bid = round(rt_data.get("bid", 0.0), 2)
    ask = round(rt_data.get("ask", 0.0), 2)
    last = round(rt_data.get("last") or rt_last or 0.0, 2)
    open_price = round(rt_data.get("bar_open") or last, 2)
    high_price = round(rt_data.get("bar_high") or last, 2)
    low_price = round(rt_data.get("bar_low") or last, 2)
    close_price = round(rt_data.get("bar_close") or last, 2)
    volume = int(rt_data.get("bar_volume") or rt_volume or 0)
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

    return QuoteData(s="ok", n=ticker_name, v=quote_values)


def parse_ticker(ticker: str) -> tuple[str, str, str, str]:
    """Parse ticker string into components.
    Args:
        ticker: Ticker string in format "SYMBOL:EXCHANGE:SECTYPE"
    Returns:
        Tuple of (symbol_name, exchange, secType, bar_size)
    Examples:
        >>> self.parse_ticker('AAPL:NASDAQ:STK@1D')
        ('AAPL', 'NASDAQ', 'STK', '1D')
        >>> self.parse_ticker('GOOGL:NASDAQ:STK')
        ('GOOGL', 'NASDAQ', 'STK', '', '')
    """

    ticker_parts = ticker.split(":")
    symbol_name = ticker_parts[0].strip()
    exchange = ""
    secType = ""
    bar_size = ""
    if len(ticker_parts) > 1:
        exchange = ticker_parts[1].strip()
    if len(ticker_parts) > 2:
        ticker_parts = ticker_parts[2].split("@")
        secType = ticker_parts[0].strip()
        if len(ticker_parts) > 1:
            bar_size = ticker_parts[1].strip()

    if not (symbol_name and exchange and secType):
        raise ProviderException(
            code="TWS_PROVIDER_INVALID_TICKER",
            message=f"Invalid ticker format: {ticker}",
            provider="tws",
            capability="shared",
        )
    return symbol_name, exchange, secType, bar_size


def build_contract(
    ticker: str,
) -> Contract:
    """Build TWS Contract object from domain parameters.

    Args:
        ticker: Ticker string (e.g., "AAPL:NASDAQ:STK-123456")
        currency: Currency code (default: "USD")

    Returns:
        TWS Contract object ready for API calls
    """
    symbol, primaryExchange, sec_type, _ = parse_ticker(ticker)
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.primaryExchange = primaryExchange
    return contract


def map_resolution_to_tws_bar_size(resolution: Resolution) -> str:
    """Map domain Resolution → TWS barSizeSetting.

    Args:
        resolution: Domain Resolution enum (TradingView format)

    Returns:
        TWS bar size string ("1 min", "5 mins", "1 hour", "1 day", etc.)

    Raises:
        ProviderException: If resolution not supported
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


# =============================================================================
# Order Mappers (Broker Capability)
# =============================================================================

# Domain OrderType → TWS orderType string
ORDER_TYPE_TO_TWS: dict[int, str] = {
    1: "LMT",  # LIMIT
    2: "MKT",  # MARKET
    3: "STP",  # STOP
    4: "STP LMT",  # STOP_LIMIT
}

# TWS orderType string → Domain OrderType
TWS_TO_ORDER_TYPE: dict[str, int] = {
    "LMT": 1,  # LIMIT
    "MKT": 2,  # MARKET
    "STP": 3,  # STOP
    "STP LMT": 4,  # STOP_LIMIT
    "STOP": 3,  # Alias
    "STOP_LIMIT": 4,  # Alias
}

# Domain Side → TWS action string
SIDE_TO_TWS_ACTION: dict[int, str] = {
    1: "BUY",  # Side.BUY
    -1: "SELL",  # Side.SELL
}

# TWS action → Domain Side
TWS_ACTION_TO_SIDE: dict[str, int] = {
    "BUY": 1,
    "SELL": -1,
    "BOT": 1,  # Historical action
    "SLD": -1,  # Historical action
}

# TWS order status → Domain OrderStatus
TWS_STATUS_TO_ORDER_STATUS: dict[str, int] = {
    "PendingSubmit": 4,  # PLACING
    "PendingCancel": 4,  # PLACING (transitional)
    "PreSubmitted": 4,  # PLACING
    "Submitted": 6,  # WORKING
    "ApiPending": 4,  # PLACING
    "ApiCancelled": 1,  # CANCELED
    "Cancelled": 1,  # CANCELED
    "Filled": 2,  # FILLED
    "Inactive": 3,  # INACTIVE
}


@dataclass
class BracketContext:
    """Context for bracket order information.

    Preserves original PreOrder bracket fields for PlacedOrder reconstruction.
    TWS doesn't return bracket prices in order callbacks, so we track them here.
    """

    take_profit: float | None = None
    stop_loss: float | None = None
    trailing_stop_pips: float | None = None
    stop_type: int | None = None
    child_order_ids: list[int] = field(default_factory=list)


def preorder_to_tws(
    preorder: PreOrder,
    account: str,
    parent_order_id: int = -1,
) -> tuple[Order, Order | None, Order | None]:
    """Convert domain PreOrder to TWS Order objects.

    Supports bracket orders (stopLoss, takeProfit, trailingStopPips) by returning
    multiple orders: parent + child orders linked via parentId and OCA group.

    Args:
        preorder: Domain PreOrder with symbol, type, side, qty, prices
        account: Account ID for order routing (required for multi-account)
        parent_order_id: Base order ID for parent; children use sequential IDs

    Returns:
        Tuple of (parent, stop_loss, take_profit) Order objects:
        - Simple order: (parent, None, None)
        - Bracket order: (parent, stop_loss, take_profit) with non-None children

    Raises:
        ProviderException: If guaranteedStop is set (not supported by TWS)
    """

    # Validate unsupported features
    if preorder.guaranteedStop is not None:
        raise ProviderException(
            code="PROVIDER_BROKER_UNSUPPORTED_FEATURE",
            message="Guaranteed stop orders are not supported by TWS/Interactive Brokers",
            provider="tws",
            capability="broker",
        )

    # Determine if this is a bracket order
    has_brackets = (
        preorder.stopLoss is not None
        or preorder.takeProfit is not None
        or preorder.trailingStopPips is not None
    )

    # Build parent order
    parent = Order()
    parent.orderId = parent_order_id
    parent.action = SIDE_TO_TWS_ACTION.get(int(preorder.side), "BUY")
    parent.totalQuantity = Decimal(str(preorder.qty))
    parent.orderType = ORDER_TYPE_TO_TWS.get(int(preorder.type), "MKT")
    parent.tif = "GTC"
    parent.account = account

    # Set prices based on order type
    if preorder.limitPrice is not None:
        parent.lmtPrice = preorder.limitPrice
    if preorder.stopPrice is not None:
        parent.auxPrice = preorder.stopPrice

    if not has_brackets:
        return parent, None, None

    # --- Bracket child orders ---
    # Child orders have opposite side to parent
    child_action = "SELL" if preorder.side == 1 else "BUY"  # Side.BUY=1, Side.SELL=-1
    oca_group = f"bracket_{parent_order_id}"

    stop_loss_order: Order | None = None
    take_profit_order: Order | None = None

    # Take-profit order (LIMIT) - created first to get sequential order ID
    if preorder.takeProfit is not None:
        take_profit_order = Order()
        take_profit_order.action = child_action
        take_profit_order.totalQuantity = Decimal(str(preorder.qty))
        take_profit_order.orderType = "LMT"
        take_profit_order.lmtPrice = preorder.takeProfit
        take_profit_order.tif = "GTC"
        take_profit_order.account = account
        take_profit_order.ocaGroup = oca_group
        take_profit_order.ocaType = 1  # CANCEL_WITH_BLOCK

    # Stop-loss or trailing stop order
    if preorder.stopLoss is not None or preorder.trailingStopPips is not None:
        stop_loss_order = Order()
        stop_loss_order.action = child_action
        stop_loss_order.totalQuantity = Decimal(str(preorder.qty))
        stop_loss_order.tif = "GTC"
        stop_loss_order.account = account
        stop_loss_order.ocaGroup = oca_group
        stop_loss_order.ocaType = 1  # CANCEL_WITH_BLOCK

        # Determine stop type: trailing vs regular stop
        use_trailing = preorder.trailingStopPips is not None or (
            preorder.stopType is not None
            and preorder.stopType == StopType.TRAILING_STOP
        )

        if use_trailing and preorder.trailingStopPips is not None:
            stop_loss_order.orderType = "TRAIL"
            stop_loss_order.auxPrice = preorder.trailingStopPips  # Trail amount
        elif preorder.stopLoss is not None:
            stop_loss_order.orderType = "STP"
            stop_loss_order.auxPrice = preorder.stopLoss

    return parent, stop_loss_order, take_profit_order


def tracked_order_to_placed_order(
    tracked: TrackedOrder,
    bracket_context: BracketContext | None = None,
) -> PlacedOrder:
    """Convert TrackedOrder to domain PlacedOrder.

    Extracts data directly from raw TWS objects (Contract, Order, OrderState)
    stored in TrackedOrder without relying on flattened dict fields.

    Args:
        tracked: TrackedOrder wrapping raw TWS objects
        bracket_context: Optional bracket info from original PreOrder.
            TWS doesn't return bracket prices in callbacks, so this
            preserves the original stopLoss/takeProfit/trailingStopPips.

    Returns:
        Domain PlacedOrder model
    """

    contract = tracked.contract
    order = tracked.order
    order_state = tracked.orderState

    # Build symbol from contract
    symbol = ticker_name(contract)

    # Order type
    order_type_str = order.orderType
    order_type = OrderType(TWS_TO_ORDER_TYPE.get(order_type_str, 2))

    # Side from action
    side = Side(TWS_ACTION_TO_SIDE.get(order.action, 1))

    # Quantity
    qty = float(order.totalQuantity)

    # Status from orderState
    status = OrderStatus(TWS_STATUS_TO_ORDER_STATUS.get(order_state.status, 6))

    # Prices
    limit_price: float | None = None
    stop_price: float | None = None
    if order.lmtPrice and order.lmtPrice > 0:
        limit_price = order.lmtPrice
    if order.auxPrice and order.auxPrice > 0:
        stop_price = order.auxPrice

    # Filled quantity from order object (mutated by orderStatus callback)
    filled_qty = float(order.filledQuantity) if order.filledQuantity else 0.0

    # Average fill price from fills history (last fill's avgFillPrice)
    avg_price: float | None = None
    if tracked.fills and filled_qty > 0:
        avg_price = tracked.fills[-1].avgFillPrice

    # Bracket fields from context (TWS doesn't return these in callbacks)
    take_profit: float | None = None
    stop_loss: float | None = None
    trailing_stop_pips: float | None = None
    stop_type: StopType | None = None

    if bracket_context:
        take_profit = bracket_context.take_profit
        stop_loss = bracket_context.stop_loss
        trailing_stop_pips = bracket_context.trailing_stop_pips
        if bracket_context.stop_type is not None:
            stop_type = StopType(bracket_context.stop_type)

    return PlacedOrder(
        id=str(tracked.orderId),
        symbol=symbol,
        type=order_type,
        side=side,
        qty=qty if qty > 0 else 1,  # Ensure positive qty
        status=status,
        limitPrice=limit_price,
        stopPrice=stop_price,
        takeProfit=take_profit,
        stopLoss=stop_loss,
        guaranteedStop=None,  # Not supported by TWS
        trailingStopPips=trailing_stop_pips,
        stopType=stop_type,
        filledQty=filled_qty if filled_qty > 0 else None,
        avgPrice=avg_price,
        updateTime=None,  # Could add timestamp from last fill
    )


# =============================================================================
# Position/Account Mappers (Broker Capability)
# =============================================================================


def tws_position_to_domain(position_data: dict[str, Any]) -> "Position":
    """Convert TWS position data dict to domain Position.

    Args:
        position_data: Dict from IBSocket position callback containing:
            - account: Account ID
            - contract: TWS Contract object
            - position: Position quantity (Decimal, can be negative for short)
            - avgCost: Average cost per unit
            - symbol, exchange, secType: Flattened contract fields

    Returns:
        Domain Position model
    """
    from trading_api.models.broker import Position as PositionModel
    from trading_api.models.broker import Side

    contract = position_data.get("contract")
    position_qty = position_data.get("position", 0)
    avg_cost = position_data.get("avgCost", 0.0)

    # Build symbol ticker from contract or flattened fields
    if contract is not None:
        symbol = ticker_name(contract)
    else:
        sym = position_data.get("symbol", "")
        exc = position_data.get("exchange", "")
        sec = position_data.get("secType", "STK")
        if not (sym and exc and sec):
            raise ProviderException(
                code="TWS_PROVIDER_INVALID_TICKER",
                message=f"Invalid ticker format: {sym}:{exc}:{sec}",
                provider="tws",
                capability="broker",
            )
        symbol = f"{sym}:{exc}:{sec}"

    # Determine side from position sign
    # Positive = long, Negative = short
    qty_float = float(position_qty)
    side = Side.BUY if qty_float >= 0 else Side.SELL

    # Position ID is typically the symbol
    position_id = symbol

    return PositionModel(
        id=position_id,
        symbol=symbol,
        qty=abs(qty_float),  # qty is always positive, side indicates direction
        side=side,
        avgPrice=float(avg_cost),
    )


def tws_account_summary_to_equity(
    summary_data: dict[str, dict[str, Any]],
) -> "EquityData":
    """Convert TWS account summary to domain EquityData.

    Args:
        summary_data: Dict from TWSClient.reqAccountSummary() mapping
            tag names to their value data:
            {
                "NetLiquidation": {"account": "DU123", "tag": "NetLiquidation",
                                   "value": "100000.00", "currency": "USD"},
                "TotalCashValue": {...},
                ...
            }

    Returns:
        Domain EquityData model

    Notes:
        - equity = NetLiquidation (total account value including positions)
        - balance = TotalCashValue (cash balance)
        - unrealizedPL = UnrealizedPnL (from account summary)
        - realizedPL = RealizedPnL (from account summary)
    """
    from trading_api.models.broker import EquityData as EquityDataModel

    def get_value(tag: str, default: float = 0.0) -> float:
        """Extract float value from summary data."""
        tag_data = summary_data.get(tag, {})
        value_str = tag_data.get("value", "")
        try:
            return float(value_str) if value_str else default
        except (ValueError, TypeError):
            return default

    return EquityDataModel(
        equity=get_value("NetLiquidation"),
        balance=get_value("TotalCashValue"),
        unrealizedPL=get_value("UnrealizedPnL"),
        realizedPL=get_value("RealizedPnL"),
    )


def tws_account_summary_to_account_info(
    summary_data: dict[str, dict[str, dict[str, Any]]], account_id: str
) -> AccountMetainfo:
    """Convert TWS account summary to domain AccountMetainfo.

    Args:
        summary_data: Dict from TWSClient.reqAccountSummary()
        account_id: Account ID (from config or first account in summary)

    Returns:
        Domain AccountMetainfo model
    """

    # Try to get account from summary data, fall back to provided account_id
    main_account = next(
        iter(
            [acc for acc in summary_data.keys() if acc not in ("reqId", "business_key")]
        ),
        None,
    )
    assert main_account is not None, "No account data in summary_data"

    main_account_data = summary_data[main_account]

    account = account_id
    for tag_data in main_account_data.values():
        if "account" in tag_data:
            account = tag_data["account"]
            break

    return AccountMetainfo(
        id=account,
        name=f"IBKR {account}",  # Simple name format
    )


__all__ = [
    "SEC_TYPE_MAP",
    "DEFAULT_SUPPORTED_RESOLUTIONS",
    "parse_tws_bar_date",
    "contract_description_to_search_result",
    "contract_details_to_symbol_info",
    "tws_bar_to_domain_bar",
    "tws_ticks_to_bar",
    "tws_ticks_to_quote_data",
    "parse_ticker",
    "build_contract",
    "map_resolution_to_tws_bar_size",
    "calculate_tws_duration",
    # Order mappers
    "BracketContext",
    "ORDER_TYPE_TO_TWS",
    "TWS_TO_ORDER_TYPE",
    "SIDE_TO_TWS_ACTION",
    "TWS_ACTION_TO_SIDE",
    "TWS_STATUS_TO_ORDER_STATUS",
    "preorder_to_tws",
    "tracked_order_to_placed_order",
    # Position/Account mappers
    "tws_position_to_domain",
    "tws_account_summary_to_equity",
    "tws_account_summary_to_account_info",
]
