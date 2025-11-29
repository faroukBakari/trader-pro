# TWS API Generic Tick List Reference

Complete reference for the `genericTickList` parameter used in `reqMktData` and related market data functions.

---

## Overview

The `genericTickList` parameter is a **comma-delimited string** of numeric codes requesting additional tick types beyond the default market data (bid/ask/last/volume).

**Syntax:**

```python
genericTickList: str = "100,101,106,233,236"
```

**Default ticks** (always returned without request): Bid Size (0), Bid Price (1), Ask Price (2), Ask Size (3), Last Price (4), Last Size (5), High (6), Low (7), Volume (8), Close (9), Open (14).

---

## Complete Generic Tick Types

| Generic Tick | Tick ID(s) | Tick Name                | Description                                    | Callback Method          |
| :----------: | :--------: | ------------------------ | ---------------------------------------------- | ------------------------ |
|   **100**    |   29, 30   | Option Volume            | Call/Put option volume for the day             | `tickSize`               |
|   **101**    |   27, 28   | Option Open Interest     | Call/Put option open interest                  | `tickSize`               |
|   **104**    |     23     | Historical Volatility    | 30-day historical volatility (stocks)          | `tickGeneric`            |
|   **105**    |     87     | Average Option Volume    | Average option volume (TWS 970+)               | `tickSize`               |
|   **106**    |     24     | Implied Volatility       | IB 30-day implied volatility estimate          | `tickGeneric`            |
|   **162**    |     31     | Index Future Premium     | Points index is over cash index                | `tickGeneric`            |
|   **165**    |   15-21    | 52-Week Data             | Low/High for 13/26/52 weeks + Avg Volume       | `tickPrice`/`tickSize`   |
|   **225**    | 34-36, 61  | Auction Data             | Volume, Price, Imbalance, Regulatory Imbalance | `tickPrice`/`tickSize`   |
|   **232**    |     37     | Mark Price               | Current theoretical calculated value           | `tickPrice`              |
|   **233**    |     48     | RT Volume (Time & Sales) | Last trade details (includes unreportable)     | `tickString`             |
|   **236**    |   46, 89   | Shortable                | Shortability indicator + shares available      | `tickGeneric`/`tickSize` |
|   **258**    |     —      | Fundamental Ratios       | Reuters fundamental data                       | `tickGeneric`            |
|   **292**    |     62     | News                     | Contract-specific news headlines               | `tickNews`               |
|   **293**    |     54     | Trade Count              | Trade count for the day                        | `tickGeneric`            |
|   **294**    |     55     | Trade Rate               | Trades per minute                              | `tickGeneric`            |
|   **295**    |     56     | Volume Rate              | Volume per minute                              | `tickGeneric`            |
|   **318**    |     57     | Last RTH Trade           | Last Regular Trading Hours price               | `tickPrice`              |
|   **375**    |     77     | RT Trade Volume          | Last trade (excludes unreportable)             | `tickString`             |
|   **411**    |     58     | RT Historical Volatility | 30-day real-time historical volatility         | `tickGeneric`            |
|   **456**    |     59     | IB Dividends             | Dividend information (12-month sums, dates)    | `tickString`             |
|   **460**    |     60     | Bond Factor Multiplier   | Current/original principal ratio               | `tickGeneric`            |
|   **576**    |   94, 95   | ETF Nav Bid/Ask          | ETF NAV bid/ask prices                         | `tickPrice`              |
|   **577**    |     96     | ETF Nav Last             | ETF NAV last price                             | `tickPrice`              |
|   **578**    |   92, 93   | ETF Nav Close            | Today's/Yesterday's ETF NAV close              | `tickPrice`              |
|   **586**    |  101, 102  | IPO Price                | Estimated midpoint & final IPO price           | `tickGeneric`            |
|   **588**    |     86     | Futures Open Interest    | Outstanding futures contracts (TWS 965+)       | `tickSize`               |
|   **595**    |   63-65    | Short-Term Volume        | 3/5/10 minute volume (stocks only)             | `tickSize`               |
|   **614**    |   98, 99   | ETF Nav High/Low         | ETF NAV high/low for day                       | `tickPrice`              |
|   **619**    |     79     | Creditman Slow Mark      | Slower mark price for system calcs             | `tickPrice`              |
|   **623**    |     97     | ETF Frozen Nav Last      | Frozen ETF NAV last                            | `tickPrice`              |

---

## The `mdoff` Prefix

**Purpose:** Prevents top-of-book market data from streaming (no bid/ask/last updates).

### Use Cases

- Request **only** the specified generic tick without streaming market data
- Reduce bandwidth and data usage
- Focus on specific data (e.g., news) without full market data overhead

### Syntax

```python
# Request news only - no streaming bid/ask/last
genericTickList = "mdoff,292"

# Request futures open interest only
genericTickList = "mdoff,588"

# Multiple generic ticks without streaming data
genericTickList = "mdoff,577,623,614"  # ETF NAV ticks
```

---

## News Source Postfix Syntax

**Format:** `292:SOURCE` or `292:SOURCE1+SOURCE2`

### Available News Providers

| Code        | Provider                            | Subscription Type         |
| ----------- | ----------------------------------- | ------------------------- |
| **BRFG**    | Briefing.com General Market Columns | Free (enabled by default) |
| **BRFUPDN** | Briefing.com Analyst Actions        | Free (enabled by default) |
| **DJNL**    | Dow Jones Newsletters               | Free (enabled by default) |
| **BT**      | Briefing Trader                     | API-specific subscription |
| **BZ**      | Benzinga Pro                        | API-specific subscription |
| **FLY**     | Fly on the Wall                     | API-specific subscription |
| **DJ-RT**   | Dow Jones Real-Time                 | API-specific subscription |

### News Examples

```python
# Single stock with Benzinga news
"mdoff,292:BZ"

# Multiple news sources combined
"mdoff,292:FLY+BRF"

# Dow Jones Real-Time
"mdoff,292:DJ-RT"

# Free news sources (no subscription required)
"mdoff,292:BRFG+DJNL"
```

---

## Common Use Case Examples

```python
# Standard stocks - RTVolume and shortable data
genericTickList = "233,236"

# Options analysis - Volume, OI, Greeks
genericTickList = "100,101,104,106"

# Full stock analysis
genericTickList = "100,101,104,106,165,225,236"

# News headlines for a stock (Benzinga + Fly)
genericTickList = "mdoff,292:BZ+FLY"

# ETF analysis - all NAV ticks
genericTickList = "577,623,614"

# Futures open interest only
genericTickList = "mdoff,588"

# Dividends information
genericTickList = "456"

# Short-term volume analysis (3/5/10 min)
genericTickList = "595"

# Real-time historical volatility
genericTickList = "411"
```

---

## Special Data Formats

### RT Volume (Tick 48, Generic 233)

Format: `price;size;timestamp;totalVolume;vwap;singleMM`

```
Example: 701.28;1;1348075471534;67854;701.46918464;true
```

| Field       | Description                           |
| ----------- | ------------------------------------- |
| price       | Last trade price                      |
| size        | Trade size                            |
| timestamp   | Unix timestamp (ms)                   |
| totalVolume | Cumulative day volume                 |
| vwap        | Volume-weighted average price         |
| singleMM    | True if filled by single market maker |

> **Note:** Volume of 0 in US stocks typically indicates an odd lot (<100 shares).

### RT Trade Volume (Tick 77, Generic 375)

Similar to RT Volume but **excludes unreportable trades** (odd lots, average price, derivative trades).

### IB Dividends (Tick 59, Generic 456)

Format: `past12m,next12m,nextDate,nextAmount`

```
Example: 0.83,0.92,20130219,0.23
```

| Field      | Description                         |
| ---------- | ----------------------------------- |
| past12m    | Sum of dividends for past 12 months |
| next12m    | Sum of dividends for next 12 months |
| nextDate   | Next dividend date (YYYYMMDD)       |
| nextAmount | Next single dividend amount         |

> **Note:** May require direct-routing rather than SMART-routing to receive dividend data.

### Shortable (Tick 46, Generic 236)

| Value Range | Meaning                                   |
| ----------- | ----------------------------------------- |
| > 2.5       | 1000+ shares available for shorting       |
| > 1.5       | May be available if shares can be located |
| ≤ 1.5       | Not available for shorting                |

> **Note:** Actual share count requires TWS 974+ (Tick 89, `SHORTABLE_SHARES`).

### Halted (Tick 49)

| Value | Description                                     |
| ----- | ----------------------------------------------- |
| -1    | Halted status not available (frozen data)       |
| 0     | Not halted (requires contract in TWS watchlist) |
| 1     | General regulatory halt                         |
| 2     | Volatility halt                                 |

---

## Important Notes

1. **Snapshot Limitations:** Generic ticks **cannot** be requested with `snapshot=True` in `reqMktData`

2. **Subscription Required:** Some tick types require specific market data subscriptions. Check TWS subscription settings.

3. **"Invalid tick type" Error:** Usually indicates missing API news subscription for tick 292

4. **HSI Special Case:** Hang Seng Index open interest uses generic tick **101**, not 588

5. **TWS Version Requirements:**

   - Tick 87 (Avg Option Volume): TWS 970+
   - Tick 86 (Futures Open Interest): TWS 965+
   - Tick 89 (Shortable Shares): TWS 974+

6. **Data Availability:** Not all tick types are available for all instruments. If a tick type isn't returned, verify availability in TWS itself first.

---

## TickTypeEnum Reference

The `ibapi.ticktype.TickTypeEnum` provides constants for all tick IDs:

```python
from ibapi.ticktype import TickTypeEnum

# Common tick type IDs
TickTypeEnum.BID         # 1
TickTypeEnum.ASK         # 2
TickTypeEnum.LAST        # 4
TickTypeEnum.VOLUME      # 8
TickTypeEnum.RT_VOLUME   # 48 (Generic 233)
TickTypeEnum.SHORTABLE   # 46 (Generic 236)
TickTypeEnum.NEWS_TICK   # 62 (Generic 292)
```

Use `TickTypeEnum.idx2name.get(tickId)` to convert tick ID to name.

---

## Related Documentation

- [01-API-REFERENCE-CLASSES.md](./01-API-REFERENCE-CLASSES.md) - EWrapper callback methods
- [Official TWS API Tick Types](https://interactivebrokers.github.io/tws-api/tick_types.html)
- [Official News Documentation](https://interactivebrokers.github.io/tws-api/news.html)

---

**Last Updated:** November 27, 2025
