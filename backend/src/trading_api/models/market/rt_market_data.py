"""Unified TWS real-time data structure.

Combines realtime bars and market data (quotes) into a single typed dataclass.
Handles all TickTypeEnum values with proper typing.
"""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class RTMarketData:
    """Unified real-time market data from TWS.

    Consolidates:
    - Real-time 5-second bars (realtimeBar callback)
    - Market data ticks (tickPrice, tickSize, tickString, tickGeneric callbacks)

    All fields are optional (None = not received yet).
    """

    # tracking flags
    tick_name: str = ""  # Symbol:Exchange identifier
    rt_bars_reqId: int | None = None  # Whether real-time bars are active
    market_data_reqId: int | None = None  # Whether market data subscription is active
    reqId_callback_map: (
        tuple[
            asyncio.AbstractEventLoop,
            Callable[
                ["RTMarketData", list[str] | None],
                Awaitable[None],
            ],
        ]
        | None
    ) = None

    # === Real-time bar fields (from realtimeBar callback) ===
    bar_time: int | None = None  # Unix timestamp of bar
    bar_open: float | None = None
    bar_high: float | None = None
    bar_low: float | None = None
    bar_close: float | None = None
    bar_volume: int | None = None
    bar_wap: float | None = None  # Weighted average price
    bar_count: int | None = None  # Trade count in bar

    # === Core price ticks (tickPrice callback) ===
    # TickTypeEnum indices: BID=1, ASK=2, LAST=4, HIGH=6, LOW=7, CLOSE=9, OPEN=14
    bid: float | None = None  # 1
    ask: float | None = None  # 2
    last: float | None = None  # 4
    high: float | None = None  # 6
    low: float | None = None  # 7
    close: float | None = None  # 9
    open: float | None = None  # 14

    # === Core size ticks (tickSize callback) ===
    # TickTypeEnum indices: BID_SIZE=0, ASK_SIZE=3, LAST_SIZE=5, VOLUME=8
    bid_size: int | None = None  # 0
    ask_size: int | None = None  # 3
    last_size: int | None = None  # 5
    volume: int | None = None  # 8

    # === Historical range ticks ===
    low_13_week: float | None = None  # 15
    high_13_week: float | None = None  # 16
    low_26_week: float | None = None  # 17
    high_26_week: float | None = None  # 18
    low_52_week: float | None = None  # 19
    high_52_week: float | None = None  # 20
    avg_volume: int | None = None  # 21

    # === Option ticks ===
    open_interest: int | None = None  # 22
    option_historical_vol: float | None = None  # 23
    option_implied_vol: float | None = None  # 24
    option_bid_exch: str | None = None  # 25
    option_ask_exch: str | None = None  # 26
    option_call_open_interest: int | None = None  # 27
    option_put_open_interest: int | None = None  # 28
    option_call_volume: int | None = None  # 29
    option_put_volume: int | None = None  # 30

    # === Index/futures ticks ===
    index_future_premium: float | None = None  # 31

    # === Exchange info ticks ===
    bid_exch: str | None = None  # 32
    ask_exch: str | None = None  # 33

    # === Auction ticks ===
    auction_volume: int | None = None  # 34
    auction_price: float | None = None  # 35
    auction_imbalance: int | None = None  # 36

    # === Mark price ===
    mark_price: float | None = None  # 37

    # === Timestamp ticks ===
    last_timestamp: str | None = None  # 45

    # === Shortability ticks ===
    shortable: float | None = None  # 46
    shortable_shares: int | None = None  # 89

    # === Fundamental data ===
    fundamental_ratios: str | None = None  # 47

    # === Real-time volume ===
    rt_volume: str | None = None  # 48
    rt_trd_volume: int | None = None  # 77

    # === Trading status ===
    halted: int | None = None  # 49

    # === Yield ticks ===
    bid_yield: float | None = None  # 50
    ask_yield: float | None = None  # 51
    last_yield: float | None = None  # 52

    # === Trade statistics ===
    trade_count: int | None = None  # 54
    trade_rate: float | None = None  # 55
    volume_rate: float | None = None  # 56
    last_rth_trade: float | None = None  # 57

    # === Volatility ===
    rt_historical_vol: float | None = None  # 58

    # === Dividends ===
    ib_dividends: str | None = None  # 59

    # === Bond specific ===
    bond_factor_multiplier: float | None = None  # 60

    # === Regulatory ===
    regulatory_imbalance: int | None = None  # 61

    # === News ===
    news_tick: str | None = None  # 62

    # === Short-term volume ===
    short_term_volume_3_min: int | None = None  # 63
    short_term_volume_5_min: int | None = None  # 64
    short_term_volume_10_min: int | None = None  # 65

    # === Delayed data ticks (for non-professional subscribers) ===
    delayed_bid: float | None = None  # 66
    delayed_ask: float | None = None  # 67
    delayed_last: float | None = None  # 68
    delayed_bid_size: int | None = None  # 69
    delayed_ask_size: int | None = None  # 70
    delayed_last_size: int | None = None  # 71
    delayed_high: float | None = None  # 72
    delayed_low: float | None = None  # 73
    delayed_volume: int | None = None  # 74
    delayed_close: float | None = None  # 75
    delayed_open: float | None = None  # 76
    delayed_last_timestamp: str | None = None  # 88
    delayed_halted: int | None = None  # 90

    # === Credit manager ===
    creditman_mark_price: float | None = None  # 78
    creditman_slow_mark_price: float | None = None  # 79

    # === Exchange info ===
    last_exch: str | None = None  # 84
    last_reg_time: str | None = None  # 85

    # === Futures ===
    futures_open_interest: int | None = None  # 86

    # === Options average volume ===
    avg_opt_volume: int | None = None  # 87

    # === ETF NAV ticks ===
    etf_nav_close: float | None = None  # 92
    etf_nav_prior_close: float | None = None  # 93
    etf_nav_bid: float | None = None  # 94
    etf_nav_ask: float | None = None  # 95
    etf_nav_last: float | None = None  # 96
    etf_frozen_nav_last: float | None = None  # 97
    etf_nav_high: float | None = None  # 98
    etf_nav_low: float | None = None  # 99

    # === Social/sentiment ===
    social_market_analytics: str | None = None  # 100

    # === IPO ticks ===
    estimated_ipo_midpoint: float | None = None  # 101
    final_ipo_last: float | None = None  # 102

    # === Delayed yield ===
    delayed_yield_bid: float | None = None  # 103
    delayed_yield_ask: float | None = None  # 104

    # === Metadata (from tickReqParams / marketDataType callbacks) ===
    market_data_type: int | None = None
    min_tick: float | None = None
    bbo_exchange: str | None = None
    snapshot_permissions: int | None = None


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
