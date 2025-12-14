"""Unified TWS real-time data structure.

Combines realtime bars and market data (quotes) into a single typed dataclass.
Handles all TickTypeEnum values with proper typing.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

# =============================================================================
# TWS Message ID to Capability Mapping
# =============================================================================
# Maps incoming message IDs (IN class from ibapi.message) to provider capabilities.
# Used for routing errors and responses to the correct capability handler.
# =============================================================================


class TWSCapability(str, Enum):
    """TWS provider capability types."""

    DATAFEED = "datafeed"
    BROKER = "broker"
    SHARED = "shared"  # Used by both capabilities


# Incoming message ID → Capability mapping
# Reference: ibapi/message.py IN class
IN_MSG_CAPABILITY: dict[int, TWSCapability] = {
    # =========================================================================
    # Market Data (datafeed capability)
    # =========================================================================
    1: TWSCapability.DATAFEED,  # TICK_PRICE
    2: TWSCapability.DATAFEED,  # TICK_SIZE
    12: TWSCapability.DATAFEED,  # MARKET_DEPTH
    13: TWSCapability.DATAFEED,  # MARKET_DEPTH_L2
    14: TWSCapability.DATAFEED,  # NEWS_BULLETINS
    17: TWSCapability.DATAFEED,  # HISTORICAL_DATA
    19: TWSCapability.DATAFEED,  # SCANNER_PARAMETERS
    20: TWSCapability.DATAFEED,  # SCANNER_DATA
    21: TWSCapability.DATAFEED,  # TICK_OPTION_COMPUTATION
    45: TWSCapability.DATAFEED,  # TICK_GENERIC
    46: TWSCapability.DATAFEED,  # TICK_STRING
    47: TWSCapability.DATAFEED,  # TICK_EFP
    50: TWSCapability.DATAFEED,  # REAL_TIME_BARS
    51: TWSCapability.DATAFEED,  # FUNDAMENTAL_DATA
    57: TWSCapability.DATAFEED,  # TICK_SNAPSHOT_END
    58: TWSCapability.DATAFEED,  # MARKET_DATA_TYPE
    75: TWSCapability.DATAFEED,  # SECURITY_DEFINITION_OPTION_PARAMETER
    76: TWSCapability.DATAFEED,  # SECURITY_DEFINITION_OPTION_PARAMETER_END
    80: TWSCapability.DATAFEED,  # MKT_DEPTH_EXCHANGES
    81: TWSCapability.DATAFEED,  # TICK_REQ_PARAMS
    82: TWSCapability.DATAFEED,  # SMART_COMPONENTS
    83: TWSCapability.DATAFEED,  # NEWS_ARTICLE
    84: TWSCapability.DATAFEED,  # TICK_NEWS
    85: TWSCapability.DATAFEED,  # NEWS_PROVIDERS
    86: TWSCapability.DATAFEED,  # HISTORICAL_NEWS
    87: TWSCapability.DATAFEED,  # HISTORICAL_NEWS_END
    88: TWSCapability.DATAFEED,  # HEAD_TIMESTAMP
    89: TWSCapability.DATAFEED,  # HISTOGRAM_DATA
    90: TWSCapability.DATAFEED,  # HISTORICAL_DATA_UPDATE
    91: TWSCapability.DATAFEED,  # REROUTE_MKT_DATA_REQ
    92: TWSCapability.DATAFEED,  # REROUTE_MKT_DEPTH_REQ
    93: TWSCapability.DATAFEED,  # MARKET_RULE
    96: TWSCapability.DATAFEED,  # HISTORICAL_TICKS
    97: TWSCapability.DATAFEED,  # HISTORICAL_TICKS_BID_ASK
    98: TWSCapability.DATAFEED,  # HISTORICAL_TICKS_LAST
    99: TWSCapability.DATAFEED,  # TICK_BY_TICK
    104: TWSCapability.DATAFEED,  # WSH_META_DATA
    105: TWSCapability.DATAFEED,  # WSH_EVENT_DATA
    106: TWSCapability.DATAFEED,  # HISTORICAL_SCHEDULE
    108: TWSCapability.DATAFEED,  # HISTORICAL_DATA_END
    # =========================================================================
    # Order/Account (broker capability)
    # =========================================================================
    3: TWSCapability.BROKER,  # ORDER_STATUS
    5: TWSCapability.BROKER,  # OPEN_ORDER
    6: TWSCapability.BROKER,  # ACCT_VALUE
    7: TWSCapability.BROKER,  # PORTFOLIO_VALUE
    8: TWSCapability.BROKER,  # ACCT_UPDATE_TIME
    11: TWSCapability.BROKER,  # EXECUTION_DATA
    15: TWSCapability.BROKER,  # MANAGED_ACCTS
    16: TWSCapability.BROKER,  # RECEIVE_FA
    53: TWSCapability.BROKER,  # OPEN_ORDER_END
    54: TWSCapability.BROKER,  # ACCT_DOWNLOAD_END
    55: TWSCapability.BROKER,  # EXECUTION_DATA_END
    56: TWSCapability.BROKER,  # DELTA_NEUTRAL_VALIDATION
    59: TWSCapability.BROKER,  # COMMISSION_AND_FEES_REPORT
    61: TWSCapability.BROKER,  # POSITION_DATA
    62: TWSCapability.BROKER,  # POSITION_END
    63: TWSCapability.BROKER,  # ACCOUNT_SUMMARY
    64: TWSCapability.BROKER,  # ACCOUNT_SUMMARY_END
    71: TWSCapability.BROKER,  # POSITION_MULTI
    72: TWSCapability.BROKER,  # POSITION_MULTI_END
    73: TWSCapability.BROKER,  # ACCOUNT_UPDATE_MULTI
    74: TWSCapability.BROKER,  # ACCOUNT_UPDATE_MULTI_END
    77: TWSCapability.BROKER,  # SOFT_DOLLAR_TIERS
    78: TWSCapability.BROKER,  # FAMILY_CODES
    94: TWSCapability.BROKER,  # PNL
    95: TWSCapability.BROKER,  # PNL_SINGLE
    100: TWSCapability.BROKER,  # ORDER_BOUND
    101: TWSCapability.BROKER,  # COMPLETED_ORDER
    102: TWSCapability.BROKER,  # COMPLETED_ORDERS_END
    103: TWSCapability.BROKER,  # REPLACE_FA_END
    # =========================================================================
    # Shared (both capabilities)
    # =========================================================================
    4: TWSCapability.SHARED,  # ERR_MSG
    9: TWSCapability.SHARED,  # NEXT_VALID_ID
    10: TWSCapability.SHARED,  # CONTRACT_DATA
    18: TWSCapability.SHARED,  # BOND_CONTRACT_DATA
    49: TWSCapability.SHARED,  # CURRENT_TIME
    52: TWSCapability.SHARED,  # CONTRACT_DATA_END
    65: TWSCapability.SHARED,  # VERIFY_MESSAGE_API
    66: TWSCapability.SHARED,  # VERIFY_COMPLETED
    67: TWSCapability.SHARED,  # DISPLAY_GROUP_LIST
    68: TWSCapability.SHARED,  # DISPLAY_GROUP_UPDATED
    69: TWSCapability.SHARED,  # VERIFY_AND_AUTH_MESSAGE_API
    70: TWSCapability.SHARED,  # VERIFY_AND_AUTH_COMPLETED
    79: TWSCapability.SHARED,  # SYMBOL_SAMPLES
    107: TWSCapability.SHARED,  # USER_INFO
    109: TWSCapability.SHARED,  # CURRENT_TIME_IN_MILLIS
}

# Message ID → Name mapping (reverse lookup from IN class constants)
# Used to generate error codes like "TICK_PRICE_ERROR"
IN_MSG_ID_TO_NAME: dict[int, str] = {
    1: "TICK_PRICE",
    2: "TICK_SIZE",
    3: "ORDER_STATUS",
    4: "ERR_MSG",
    5: "OPEN_ORDER",
    6: "ACCT_VALUE",
    7: "PORTFOLIO_VALUE",
    8: "ACCT_UPDATE_TIME",
    9: "NEXT_VALID_ID",
    10: "CONTRACT_DATA",
    11: "EXECUTION_DATA",
    12: "MARKET_DEPTH",
    13: "MARKET_DEPTH_L2",
    14: "NEWS_BULLETINS",
    15: "MANAGED_ACCTS",
    16: "RECEIVE_FA",
    17: "HISTORICAL_DATA",
    18: "BOND_CONTRACT_DATA",
    19: "SCANNER_PARAMETERS",
    20: "SCANNER_DATA",
    21: "TICK_OPTION_COMPUTATION",
    45: "TICK_GENERIC",
    46: "TICK_STRING",
    47: "TICK_EFP",
    49: "CURRENT_TIME",
    50: "REAL_TIME_BARS",
    51: "FUNDAMENTAL_DATA",
    52: "CONTRACT_DATA_END",
    53: "OPEN_ORDER_END",
    54: "ACCT_DOWNLOAD_END",
    55: "EXECUTION_DATA_END",
    56: "DELTA_NEUTRAL_VALIDATION",
    57: "TICK_SNAPSHOT_END",
    58: "MARKET_DATA_TYPE",
    59: "COMMISSION_AND_FEES_REPORT",
    61: "POSITION_DATA",
    62: "POSITION_END",
    63: "ACCOUNT_SUMMARY",
    64: "ACCOUNT_SUMMARY_END",
    65: "VERIFY_MESSAGE_API",
    66: "VERIFY_COMPLETED",
    67: "DISPLAY_GROUP_LIST",
    68: "DISPLAY_GROUP_UPDATED",
    69: "VERIFY_AND_AUTH_MESSAGE_API",
    70: "VERIFY_AND_AUTH_COMPLETED",
    71: "POSITION_MULTI",
    72: "POSITION_MULTI_END",
    73: "ACCOUNT_UPDATE_MULTI",
    74: "ACCOUNT_UPDATE_MULTI_END",
    75: "SECURITY_DEFINITION_OPTION_PARAMETER",
    76: "SECURITY_DEFINITION_OPTION_PARAMETER_END",
    77: "SOFT_DOLLAR_TIERS",
    78: "FAMILY_CODES",
    79: "SYMBOL_SAMPLES",
    80: "MKT_DEPTH_EXCHANGES",
    81: "TICK_REQ_PARAMS",
    82: "SMART_COMPONENTS",
    83: "NEWS_ARTICLE",
    84: "TICK_NEWS",
    85: "NEWS_PROVIDERS",
    86: "HISTORICAL_NEWS",
    87: "HISTORICAL_NEWS_END",
    88: "HEAD_TIMESTAMP",
    89: "HISTOGRAM_DATA",
    90: "HISTORICAL_DATA_UPDATE",
    91: "REROUTE_MKT_DATA_REQ",
    92: "REROUTE_MKT_DEPTH_REQ",
    93: "MARKET_RULE",
    94: "PNL",
    95: "PNL_SINGLE",
    96: "HISTORICAL_TICKS",
    97: "HISTORICAL_TICKS_BID_ASK",
    98: "HISTORICAL_TICKS_LAST",
    99: "TICK_BY_TICK",
    100: "ORDER_BOUND",
    101: "COMPLETED_ORDER",
    102: "COMPLETED_ORDERS_END",
    103: "REPLACE_FA_END",
    104: "WSH_META_DATA",
    105: "WSH_EVENT_DATA",
    106: "HISTORICAL_SCHEDULE",
    107: "USER_INFO",
    108: "HISTORICAL_DATA_END",
    109: "CURRENT_TIME_IN_MILLIS",
}


def get_msg_capability(msg_id: int) -> TWSCapability:
    """Get capability for a given msgId.

    Args:
        msg_id: TWS incoming message ID (from IN class)

    Returns:
        TWSCapability enum value. Defaults to SHARED for unknown msgIds.
    """
    return IN_MSG_CAPABILITY.get(msg_id, TWSCapability.SHARED)


def get_msg_name(msg_id: int) -> str:
    """Get the IN class constant name for a message ID.

    Args:
        msg_id: TWS incoming message ID

    Returns:
        Message name string (e.g., "TICK_PRICE", "ORDER_STATUS").
        Returns "UNKNOWN_{msg_id}" for unmapped IDs.
    """
    return IN_MSG_ID_TO_NAME.get(msg_id, f"UNKNOWN_{msg_id}")


def get_error_code(msg_id: int, tws_error_code: int) -> str:
    """Generate error code string for ProviderException.

    Args:
        msg_id: TWS incoming message ID
        tws_error_code: TWS-specific error code

    Returns:
        Error code string like "PROVIDER_TWS_TICK_PRICE_2106"
    """
    msg_name = get_msg_name(msg_id)
    return f"PROVIDER_TWS_{msg_name}_{tws_error_code}"


def get_capability_str(msg_id: int) -> Literal["datafeed", "broker", "shared"]:
    """Get capability string for ProviderException.

    Args:
        msg_id: TWS incoming message ID

    Returns:
        Capability string ("datafeed", "broker", or "" for shared).
    """
    cap = get_msg_capability(msg_id)
    if cap == TWSCapability.SHARED:
        return "shared"
    return cap.value  # type: ignore[no-any-return]


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
