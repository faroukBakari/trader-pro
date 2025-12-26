"""TWS domain mappers.

Converts TWS API types to domain models (SearchSymbolResultItem, SymbolInfo, Bar, QuoteData, etc.).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.ticktype import TickTypeEnum

from trading_api.models.broker import AccountMetainfo
from trading_api.models.market import (
    Bar,
    QuoteData,
    QuoteValues,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)

if TYPE_CHECKING:
    from ibapi.order import Order

    from trading_api.models.broker import EquityData, PlacedOrder, Position, PreOrder

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
    ticker_name = rt_data.get("ticker_name", "UNKNOWN")
    symbol, exchange, _, _, _ = parse_ticker(ticker_name)
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
    currency: str = "USD",
) -> Contract:
    """Build TWS Contract object from domain parameters.

    Args:
        ticker: Ticker string (e.g., "AAPL:NASDAQ:STK-123456")
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
    contract.currency = currency
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


def preorder_to_tws(
    preorder: "PreOrder", account: str = ""
) -> tuple[Contract, "Order"]:
    """Convert domain PreOrder to TWS Contract and Order objects.

    Args:
        preorder: Domain PreOrder with symbol, type, side, qty, prices
        account: Optional account ID for order routing

    Returns:
        Tuple of (Contract, Order) ready for TWSClient.placeOrder()
    """
    from ibapi.order import Order as TWSOrder

    from trading_api.models.broker import PreOrder as PreOrderModel

    # Type assertion for IDE
    _preorder: PreOrderModel = preorder  # noqa: F841

    # Build contract from ticker
    contract = build_contract(preorder.symbol)

    # Build order
    order = TWSOrder()
    order.action = SIDE_TO_TWS_ACTION.get(int(preorder.side), "BUY")
    order.totalQuantity = Decimal(str(preorder.qty))
    order.orderType = ORDER_TYPE_TO_TWS.get(int(preorder.type), "MKT")

    # Set prices based on order type
    if preorder.limitPrice is not None:
        order.lmtPrice = preorder.limitPrice
    if preorder.stopPrice is not None:
        order.auxPrice = preorder.stopPrice

    # Set TIF (Time In Force) - default to GTC
    order.tif = "GTC"

    # Account - required for order routing
    order.account = account  # Empty string is valid if only one account

    # Transmit immediately
    order.transmit = True

    # Handle bracket orders (stopLoss, takeProfit)
    # Note: TWS bracket orders require parent order to be placed first,
    # then child orders with parentId set. This is handled at provider level.

    return contract, order


def tws_order_to_placed_order(order_data: dict[str, Any]) -> "PlacedOrder":
    """Convert TWS order data dict to domain PlacedOrder.

    Args:
        order_data: Dict from IBSocket order callbacks containing:
            - orderId: TWS order ID
            - contract: TWS Contract object
            - order: TWS Order object
            - orderState: TWS OrderState object
            - status: Current status string
            - filled: Filled quantity
            - avgFillPrice: Average fill price

    Returns:
        Domain PlacedOrder model
    """
    from trading_api.models.broker import OrderStatus, OrderType
    from trading_api.models.broker import PlacedOrder as PlacedOrderModel
    from trading_api.models.broker import Side

    # Extract from nested objects or flattened dict
    order_id = str(order_data.get("orderId", ""))
    contract = order_data.get("contract")
    order = order_data.get("order")
    order_state = order_data.get("orderState")

    # Symbol from contract or flattened field
    if contract is not None:
        symbol = ticker_name(contract)
    else:
        sym = order_data.get("symbol", "")
        exc = order_data.get("exchange", "")
        sec = order_data.get("secType", "STK")
        con = order_data.get("conId", 0)
        symbol = f"{sym}:{exc}:{sec}-{con}"

    # Order type from order object or flattened
    if order is not None:
        order_type_str = order.orderType
    else:
        order_type_str = order_data.get("orderType", "MKT")
    order_type = OrderType(TWS_TO_ORDER_TYPE.get(order_type_str, 2))

    # Side from action
    if order is not None:
        action = order.action
    else:
        action = order_data.get("action", "BUY")
    side = Side(TWS_ACTION_TO_SIDE.get(action, 1))

    # Quantity
    if order is not None:
        qty = float(order.totalQuantity)
    else:
        qty = float(order_data.get("totalQuantity", 0))

    # Status
    if order_state is not None:
        status_str = order_state.status
    else:
        status_str = order_data.get("status", "Submitted")
    status = OrderStatus(TWS_STATUS_TO_ORDER_STATUS.get(status_str, 6))

    # Prices
    limit_price: float | None = None
    stop_price: float | None = None
    if order is not None:
        if order.lmtPrice and order.lmtPrice > 0:
            limit_price = order.lmtPrice
        if order.auxPrice and order.auxPrice > 0:
            stop_price = order.auxPrice
    else:
        lmt = order_data.get("lmtPrice")
        if lmt and float(lmt) > 0:
            limit_price = float(lmt)
        aux = order_data.get("auxPrice")
        if aux and float(aux) > 0:
            stop_price = float(aux)

    # Filled quantity and avg price
    filled_qty = float(order_data.get("filled", 0))
    avg_price = float(order_data.get("avgFillPrice", 0)) if filled_qty > 0 else None

    # Filled quantity from order object (alternative source)
    if filled_qty == 0 and order is not None:
        fq = order.filledQuantity
        if fq:
            filled_qty = float(fq)

    return PlacedOrderModel(
        id=order_id,
        symbol=symbol,
        type=order_type,
        side=side,
        qty=qty if qty > 0 else 1,  # Ensure positive qty
        status=status,
        limitPrice=limit_price,
        stopPrice=stop_price,
        takeProfit=None,  # Not directly available from TWS
        stopLoss=None,  # Not directly available from TWS
        guaranteedStop=None,  # Not supported by TWS
        trailingStopPips=None,  # Would need separate logic
        stopType=None,  # Not directly available
        filledQty=filled_qty if filled_qty > 0 else None,
        avgPrice=avg_price,
        updateTime=None,  # Could add timestamp if available
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
            - symbol, exchange, secType, conId: Flattened contract fields

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
        con = position_data.get("conId", 0)
        symbol = f"{sym}:{exc}:{sec}-{con}"

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
            [acc for acc in summary_data.keys() if acc not in ("reqId", "ticker_name")]
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
    "tws_rt_bar_to_domain_bar",
    "tws_ticks_to_bar",
    "tws_ticks_to_quote_data",
    "parse_ticker",
    "build_contract",
    "map_resolution_to_tws_bar_size",
    "calculate_tws_duration",
    # Order mappers
    "ORDER_TYPE_TO_TWS",
    "TWS_TO_ORDER_TYPE",
    "SIDE_TO_TWS_ACTION",
    "TWS_ACTION_TO_SIDE",
    "TWS_STATUS_TO_ORDER_STATUS",
    "preorder_to_tws",
    "tws_order_to_placed_order",
    # Position/Account mappers
    "tws_position_to_domain",
    "tws_account_summary_to_equity",
    "tws_account_summary_to_account_info",
]
