"""Unified TWS real-time data structure.

Combines realtime bars and market data (quotes) into a single typed dataclass.
Handles all TickTypeEnum values with proper typing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Bar Size Constants
# =============================================================================
# Maps TWS bar size strings to duration in seconds.
# Used for calculating historical data duration requests.
# =============================================================================

BAR_SIZE_TO_SECONDS: dict[str, int] = {
    "1 secs": 1,
    "5 secs": 5,
    "10 secs": 10,
    "15 secs": 15,
    "30 secs": 30,
    "1 min": 60,
    "2 mins": 120,
    "3 mins": 180,
    "5 mins": 300,
    "10 mins": 600,
    "15 mins": 900,
    "20 mins": 1200,
    "30 mins": 1800,
    "1 hour": 3600,
    "2 hours": 7200,
    "3 hours": 10800,
    "4 hours": 14400,
    "8 hours": 28800,
    "1 day": 86400,
    "1 week": 604800,
    "1 month": 2592000,
}


def get_bar_duration_seconds(bar_size: str) -> int:
    """Get duration in seconds for a bar size.

    Args:
        bar_size: TWS bar size string (e.g., "1 min", "1 hour", "1 day")

    Returns:
        Duration in seconds. Defaults to 86400 (1 day) for unknown sizes.
    """
    return BAR_SIZE_TO_SECONDS.get(bar_size, 86400)


# =============================================================================
# Tick Type Field Mapping
# =============================================================================

# Mapping from TickTypeEnum name → TwsRTData attribute name
# Only includes ticks that map to dedicated fields (not extended dict)
TICK_TYPE_TO_FIELD: dict[str, str] = {
    # Core prices
    "BID": "bid",
    "ASK": "ask",
    "LAST": "last",
    "HIGH": "high",
    "LOW": "low",
    "CLOSE": "close",
    "OPEN": "open",
    # Core sizes
    "BID_SIZE": "bid_size",
    "ASK_SIZE": "ask_size",
    "LAST_SIZE": "last_size",
    "VOLUME": "volume",
    # Historical ranges
    "LOW_13_WEEK": "low_13_week",
    "HIGH_13_WEEK": "high_13_week",
    "LOW_26_WEEK": "low_26_week",
    "HIGH_26_WEEK": "high_26_week",
    "LOW_52_WEEK": "low_52_week",
    "HIGH_52_WEEK": "high_52_week",
    "AVG_VOLUME": "avg_volume",
    # Options
    "OPEN_INTEREST": "open_interest",
    "OPTION_HISTORICAL_VOL": "option_historical_vol",
    "OPTION_IMPLIED_VOL": "option_implied_vol",
    "OPTION_BID_EXCH": "option_bid_exch",
    "OPTION_ASK_EXCH": "option_ask_exch",
    "OPTION_CALL_OPEN_INTEREST": "option_call_open_interest",
    "OPTION_PUT_OPEN_INTEREST": "option_put_open_interest",
    "OPTION_CALL_VOLUME": "option_call_volume",
    "OPTION_PUT_VOLUME": "option_put_volume",
    # Index/futures
    "INDEX_FUTURE_PREMIUM": "index_future_premium",
    # Exchange info
    "BID_EXCH": "bid_exch",
    "ASK_EXCH": "ask_exch",
    # Auction
    "AUCTION_VOLUME": "auction_volume",
    "AUCTION_PRICE": "auction_price",
    "AUCTION_IMBALANCE": "auction_imbalance",
    # Mark price
    "MARK_PRICE": "mark_price",
    # Timestamp
    "LAST_TIMESTAMP": "last_timestamp",
    # Shortability
    "SHORTABLE": "shortable",
    "SHORTABLE_SHARES": "shortable_shares",
    # Fundamental
    "FUNDAMENTAL_RATIOS": "fundamental_ratios",
    # Real-time volume
    "RT_VOLUME": "rt_volume",
    "RT_TRD_VOLUME": "rt_trd_volume",
    # Trading status
    "HALTED": "halted",
    # Yield
    "BID_YIELD": "bid_yield",
    "ASK_YIELD": "ask_yield",
    "LAST_YIELD": "last_yield",
    # Trade stats
    "TRADE_COUNT": "trade_count",
    "TRADE_RATE": "trade_rate",
    "VOLUME_RATE": "volume_rate",
    "LAST_RTH_TRADE": "last_rth_trade",
    # Volatility
    "RT_HISTORICAL_VOL": "rt_historical_vol",
    # Dividends
    "IB_DIVIDENDS": "ib_dividends",
    # Bond
    "BOND_FACTOR_MULTIPLIER": "bond_factor_multiplier",
    # Regulatory
    "REGULATORY_IMBALANCE": "regulatory_imbalance",
    # News
    "NEWS_TICK": "news_tick",
    # Short-term volume
    "SHORT_TERM_VOLUME_3_MIN": "short_term_volume_3_min",
    "SHORT_TERM_VOLUME_5_MIN": "short_term_volume_5_min",
    "SHORT_TERM_VOLUME_10_MIN": "short_term_volume_10_min",
    # Delayed data
    "DELAYED_BID": "delayed_bid",
    "DELAYED_ASK": "delayed_ask",
    "DELAYED_LAST": "delayed_last",
    "DELAYED_BID_SIZE": "delayed_bid_size",
    "DELAYED_ASK_SIZE": "delayed_ask_size",
    "DELAYED_LAST_SIZE": "delayed_last_size",
    "DELAYED_HIGH": "delayed_high",
    "DELAYED_LOW": "delayed_low",
    "DELAYED_VOLUME": "delayed_volume",
    "DELAYED_CLOSE": "delayed_close",
    "DELAYED_OPEN": "delayed_open",
    "DELAYED_LAST_TIMESTAMP": "delayed_last_timestamp",
    "DELAYED_HALTED": "delayed_halted",
    # Credit manager
    "CREDITMAN_MARK_PRICE": "creditman_mark_price",
    "CREDITMAN_SLOW_MARK_PRICE": "creditman_slow_mark_price",
    # Exchange
    "LAST_EXCH": "last_exch",
    "LAST_REG_TIME": "last_reg_time",
    # Futures
    "FUTURES_OPEN_INTEREST": "futures_open_interest",
    # Options avg volume
    "AVG_OPT_VOLUME": "avg_opt_volume",
    # ETF NAV
    "ETF_NAV_CLOSE": "etf_nav_close",
    "ETF_NAV_PRIOR_CLOSE": "etf_nav_prior_close",
    "ETF_NAV_BID": "etf_nav_bid",
    "ETF_NAV_ASK": "etf_nav_ask",
    "ETF_NAV_LAST": "etf_nav_last",
    "ETF_FROZEN_NAV_LAST": "etf_frozen_nav_last",
    "ETF_NAV_HIGH": "etf_nav_high",
    "ETF_NAV_LOW": "etf_nav_low",
    # Social
    "SOCIAL_MARKET_ANALYTICS": "social_market_analytics",
    # IPO
    "ESTIMATED_IPO_MIDPOINT": "estimated_ipo_midpoint",
    "FINAL_IPO_LAST": "final_ipo_last",
    # Delayed yield
    "DELAYED_YIELD_BID": "delayed_yield_bid",
    "DELAYED_YIELD_ASK": "delayed_yield_ask",
}

# Tick types that are sizes (int) vs prices (float)
SIZE_TICK_TYPES: frozenset[str] = frozenset(
    {
        "BID_SIZE",
        "ASK_SIZE",
        "LAST_SIZE",
        "VOLUME",
        "AVG_VOLUME",
        "OPEN_INTEREST",
        "OPTION_CALL_OPEN_INTEREST",
        "OPTION_PUT_OPEN_INTEREST",
        "OPTION_CALL_VOLUME",
        "OPTION_PUT_VOLUME",
        "AUCTION_VOLUME",
        "AUCTION_IMBALANCE",
        "SHORTABLE_SHARES",
        "RT_TRD_VOLUME",
        "HALTED",
        "TRADE_COUNT",
        "REGULATORY_IMBALANCE",
        "SHORT_TERM_VOLUME_3_MIN",
        "SHORT_TERM_VOLUME_5_MIN",
        "SHORT_TERM_VOLUME_10_MIN",
        "DELAYED_BID_SIZE",
        "DELAYED_ASK_SIZE",
        "DELAYED_LAST_SIZE",
        "DELAYED_VOLUME",
        "DELAYED_HALTED",
        "FUTURES_OPEN_INTEREST",
        "AVG_OPT_VOLUME",
    }
)

# Tick types that are strings
STRING_TICK_TYPES: frozenset[str] = frozenset(
    {
        "OPTION_BID_EXCH",
        "OPTION_ASK_EXCH",
        "BID_EXCH",
        "ASK_EXCH",
        "LAST_TIMESTAMP",
        "FUNDAMENTAL_RATIOS",
        "RT_VOLUME",
        "IB_DIVIDENDS",
        "NEWS_TICK",
        "DELAYED_LAST_TIMESTAMP",
        "LAST_EXCH",
        "LAST_REG_TIME",
        "SOCIAL_MARKET_ANALYTICS",
    }
)


# =============================================================================
# TWS Asset Type Configuration
# =============================================================================
# Configuration for whatToShow and genericTickList per security type.
# Based on TWS API documentation: https://interactivebrokers.github.io/tws-api/
#
# whatToShow: Historical data type parameter for reqHistoricalData
# genericTickList: Comma-separated tick types for reqMktData
# =============================================================================


@dataclass(frozen=True)
class AssetTypeConfig:
    """Configuration for TWS API parameters per security type.

    TWS API has different whatToShow restrictions:
    - Historical data (keepUpToDate=False): Supports all types per product
    - Live updates (keepUpToDate=True): Only TRADES, MIDPOINT, BID, ASK

    Reference: https://interactivebrokers.github.io/tws-api/historical_bars.html
    """

    what_to_show_hist: str
    """Historical data type for reqHistoricalData with keepUpToDate=False.
    Can be: TRADES, MIDPOINT, BID, ASK, BID_ASK, AGGTRADES, ADJUSTED_LAST, etc.
    """

    what_to_show_live: str
    """Historical data type for reqHistoricalData with keepUpToDate=True.
    Must be one of: TRADES, MIDPOINT, BID, ASK (TWS API restriction).
    """

    generic_tick_list: tuple[str, ...]
    """Generic tick types for market data subscription."""

    @property
    def generic_tick_list_str(self) -> list[str]:
        """Return generic tick list as a list for TWS API."""
        return list(self.generic_tick_list)


# Security type → API configuration mapping
# Reference: https://interactivebrokers.github.io/tws-api/historical_bars.html
#
# keepUpToDate=True only supports: TRADES, MIDPOINT, BID, ASK
# Historical data supports additional types per product (see Available Data per Product)
ASSET_TYPE_CONFIG: dict[str, AssetTypeConfig] = {
    # Cryptocurrency
    # - Historical: AGGTRADES recommended (aggregated trades for crypto)
    # - Live: TRADES (AGGTRADES not supported with keepUpToDate=True)
    "CRYPTO": AssetTypeConfig(
        what_to_show_hist="AGGTRADES",
        what_to_show_live="MIDPOINT",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
            "595",  # Short-term volume
        ),
    ),
    # Stocks - Full tick support
    "STK": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
            "456",  # Dividends
            "595",  # Short-term volume
        ),
    ),
    # Options
    "OPT": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
            "456",  # Dividends
        ),
    ),
    # Futures - No dividends, has futures OI
    "FUT": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
            "588",  # Futures Open Interest
        ),
    ),
    # Futures Options
    "FOP": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
        ),
    ),
    # Forex (CASH) - No TRADES support, use MIDPOINT
    "CASH": AssetTypeConfig(
        what_to_show_hist="MIDPOINT",
        what_to_show_live="MIDPOINT",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
        ),
    ),
    # CFDs - No TRADES support, use MIDPOINT
    "CFD": AssetTypeConfig(
        what_to_show_hist="MIDPOINT",
        what_to_show_live="MIDPOINT",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
        ),
    ),
    # Commodities - No TRADES support, use MIDPOINT
    "CMDTY": AssetTypeConfig(
        what_to_show_hist="MIDPOINT",
        what_to_show_live="MIDPOINT",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
        ),
    ),
    # Mutual Funds - No TRADES support, use MIDPOINT
    "FUND": AssetTypeConfig(
        what_to_show_hist="MIDPOINT",
        what_to_show_live="MIDPOINT",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
        ),
    ),
    # Index - Limited tick support, TRADES for historical only
    "IND": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "232",  # Mark price
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
        ),
    ),
    # Bonds - Has bond factor tick
    "BOND": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
            "460",  # Bond factor multiplier
        ),
    ),
    # Warrants
    "WAR": AssetTypeConfig(
        what_to_show_hist="TRADES",
        what_to_show_live="TRADES",
        generic_tick_list=(
            "165",  # 52-week data
            "225",  # Auction
            "232",  # Mark price
            # "233",  # RT Volume
            "236",  # Shortable
            "293",  # Trade count
            "294",  # Trade rate
            "295",  # Volume rate
            "318",  # Last RTH trade
            "375",  # RT Trade Volume
            "411",  # RT Historical Vol
        ),
    ),
}

# Default configuration for unknown security types
DEFAULT_ASSET_CONFIG = AssetTypeConfig(
    what_to_show_hist="TRADES",
    what_to_show_live="TRADES",
    generic_tick_list=(
        "165",  # 52-week data
        "225",  # Auction
        "232",  # Mark price
        # "233",  # RT Volume
        "236",  # Shortable
        "293",  # Trade count
        "294",  # Trade rate
        "295",  # Volume rate
        "318",  # Last RTH trade
        "375",  # RT Trade Volume
        "411",  # RT Historical Vol
    ),
)


def get_asset_config(sec_type: str) -> AssetTypeConfig:
    """Get TWS API configuration for a security type.

    Args:
        sec_type: Security type string (STK, OPT, FUT, CRYPTO, etc.)

    Returns:
        AssetTypeConfig with whatToShow and genericTickList for the security type.
        Falls back to DEFAULT_ASSET_CONFIG for unknown types.
    """
    return ASSET_TYPE_CONFIG.get(sec_type, DEFAULT_ASSET_CONFIG)


# =============================================================================
# TWS Error Code Classification
# =============================================================================
# Classifies TWS error codes by category and recoverability.
# Based on: https://interactivebrokers.github.io/tws-api/message_codes.html
#
# Categories:
# - INFO: Not errors, just status notifications (2104, 2106, 2158, etc.)
# - CONNECTION: Connection state changes (1100, 1101, 1102, 502, 504)
# - PACING: Rate limiting (100) - recoverable with throttling
# - DUPLICATE: ID conflicts (102, 326, 385, 386, 501) - use different ID
# - SUBSCRIPTION: Market data permissions (354, 10090, 10186) - requires action
# - VALIDATION: Invalid request params (200, 201, 203) - fix request
# - FATAL: Protocol/system errors (503, 505-509, 520) - cannot recover
# - WARNING: Non-critical issues (2xxx range)
# - SYSTEM: System messages (1xxx range)
# - ERROR: Unclassified errors
# =============================================================================


class TWSErrorClassification:
    """TWS error classification categories (from TWS error codes).

    Note: This is separate from TWSErrorCategory in tws_connection.py which
    categorizes error sources (CONN, API, CALLBACK). This class categorizes
    the specific TWS error code meanings.
    """

    INFO = "INFO"  # Not errors - status notifications
    CONNECTION = "CONNECTION"  # Connection state changes
    PACING = "PACING"  # Rate limiting errors
    DUPLICATE = "DUPLICATE"  # Duplicate ID errors
    SUBSCRIPTION = "SUBSCRIPTION"  # Market data subscription issues
    VALIDATION = "VALIDATION"  # Invalid request/contract
    FATAL = "FATAL"  # Unrecoverable system errors
    WARNING = "WARNING"  # Non-critical warnings
    SYSTEM = "SYSTEM"  # System state messages
    ERROR = "ERROR"  # Unclassified errors


# Informational status messages - not real errors
_INFO_CODES: frozenset[int] = frozenset(
    {
        2104,  # Market data farm connection is OK
        2106,  # Historical data farm is connected
        2107,  # Historical data farm connection inactive (dormant)
        2108,  # Market data farm connection inactive (dormant)
        2158,  # Sec-def data farm connection is OK
    }
)

# Connection state changes - recoverable via reconnect/wait
_CONNECTION_RECOVERABLE: frozenset[int] = frozenset(
    {
        502,  # Couldn't connect to TWS - retry
        504,  # Not connected - reconnect
        1100,  # Connectivity lost - wait for 1101/1102
        1101,  # Connectivity restored, data lost - resubscribe
        1102,  # Connectivity restored, data maintained
        1300,  # Socket port reset - reconnect on new port
        2103,  # Market data farm disconnected - temporary
        2105,  # Historical data farm disconnected - temporary
        2110,  # TWS-server connection broken - auto-restores
    }
)

# Rate limiting - recoverable with throttling
_PACING_CODES: frozenset[int] = frozenset(
    {
        100,  # Max rate of messages exceeded (50/sec)
        420,  # Invalid real-time query (pacing violation)
    }
)

# Duplicate/conflict errors - use different ID and retry
_DUPLICATE_CODES: frozenset[int] = frozenset(
    {
        102,  # Duplicate ticker ID
        103,  # Duplicate order ID
        326,  # Client ID already in use
        385,  # Duplicate ticker ID for scanner
        386,  # Duplicate ticker ID for historical data
        501,  # Already connected (not really an error)
    }
)

# Subscription/permission issues - requires user action (not auto-recoverable)
_SUBSCRIPTION_CODES: frozenset[int] = frozenset(
    {
        354,  # Not subscribed to market data
        10090,  # Part of requested market data not subscribed
        10167,  # Requested market data requires subscription
        10186,  # Market data not subscribed, delayed not enabled
        10197,  # No market data during competing session
    }
)

# Invalid request/contract - not recoverable without fixing request
_VALIDATION_CODES: frozenset[int] = frozenset(
    {
        200,  # No security definition found
        201,  # Order rejected
        202,  # Order cancelled (may be expected)
        203,  # Security not available for account
        300,  # Can't find ticker ID
        321,  # Server error validating request
        322,  # Server error processing request
        323,  # Server error
        399,  # Order message error
        400,  # Algo order error
    }
)

# Fatal protocol/system errors - cannot recover
_FATAL_CODES: frozenset[int] = frozenset(
    {
        503,  # TWS out of date - must upgrade
        505,  # Unknown message ID
        506,  # Unsupported version
        507,  # Bad message length
        508,  # Bad message
        509,  # Socket exception
        520,  # Failed to create socket
        530,  # SSL error
    }
)

# Request not found - usually means already cancelled/completed (informational)
_NOT_FOUND_CODES: frozenset[int] = frozenset(
    {
        135,  # Can't find order with ID
        162,  # HMDS query returned no data (valid empty response)
        300,  # Can't find ticker ID
        366,  # No historical data query found
        365,  # No scanner subscription found
        10148,  # Order cannot be cancelled, wrong state
    }
)


def classify_error(error_code: int) -> tuple[str, bool]:
    """Classify TWS error code by category and recoverability.

    Based on TWS API documentation:
    https://interactivebrokers.github.io/tws-api/message_codes.html

    Args:
        error_code: TWS error code from error() callback

    Returns:
        Tuple of (category, is_recoverable):
        - category: TWSErrorClassification string (INFO, CONNECTION, PACING, etc.)
        - is_recoverable: True if error can be recovered from automatically

    Examples:
        >>> classify_error(2104)  # Market data farm OK
        ('INFO', True)
        >>> classify_error(1100)  # Connectivity lost
        ('CONNECTION', True)
        >>> classify_error(200)   # No security definition
        ('VALIDATION', False)
        >>> classify_error(503)   # TWS out of date
        ('FATAL', False)
    """
    # Informational/Status messages - not real errors
    if error_code in _INFO_CODES:
        return (TWSErrorClassification.INFO, True)

    # Connection recoverable - wait/retry
    if error_code in _CONNECTION_RECOVERABLE:
        return (TWSErrorClassification.CONNECTION, True)

    # Rate limiting - throttle and retry
    if error_code in _PACING_CODES:
        return (TWSErrorClassification.PACING, True)

    # Duplicate/already exists - use different ID and retry
    if error_code in _DUPLICATE_CODES:
        return (TWSErrorClassification.DUPLICATE, True)

    # Data subscription issues - requires user action
    if error_code in _SUBSCRIPTION_CODES:
        return (TWSErrorClassification.SUBSCRIPTION, False)

    # Invalid contract/request - not recoverable without fixing request
    if error_code in _VALIDATION_CODES:
        return (TWSErrorClassification.VALIDATION, False)

    # System/protocol errors - not recoverable
    if error_code in _FATAL_CODES:
        return (TWSErrorClassification.FATAL, False)

    # Request not found - informational (already cancelled/completed)
    if error_code in _NOT_FOUND_CODES:
        return (TWSErrorClassification.INFO, True)

    # Warnings (2xxx range, excluding handled above)
    if 2000 <= error_code < 3000:
        return (TWSErrorClassification.WARNING, True)

    # System messages (1xxx range, excluding handled above)
    if 1000 <= error_code < 2000:
        return (TWSErrorClassification.SYSTEM, True)

    # Default for unclassified errors (conservative: non-recoverable)
    return (TWSErrorClassification.ERROR, False)


@dataclass
class StreamData(list[dict[str, Any]]):
    business_key: str
    snapshot_complete: bool = False
    index_key: str | None = None
    updated_fields: list[str] = field(default_factory=list)
    last_updated: int = 0
    last_dispatched: int = 0
