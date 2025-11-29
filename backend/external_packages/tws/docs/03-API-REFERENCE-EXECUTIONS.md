# TWS API Reference - Executions & Trade Data

<!-- METADATA: scope=execution-reporting, priority=reference, dependencies=[02-CONTRACTS-ORDERS] -->

> **Source:** [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)  
> **Last Updated:** November 19, 2025

This document contains comprehensive reference information for TWS API execution and trade-related data structures.

**[REFERENCE]** Complete technical reference for execution reporting, commission data, and historical tick structures.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section     | Class/Enum                                                   | Type              | Jump To         |
| ----------- | ------------------------------------------------------------ | ----------------- | --------------- |
| **1.0**     | [CommissionAndFeesReport](#10-commissionandfeesreport-class) | Trade             | Commission data |
| **2.0**     | [Liquidity](#20-liquidity-enum)                              | Enum              | Liquidity types |
| **3.0**     | [HistoricalTick Classes](#30-historicaltick-classes)         | [HISTORICAL] Data | Tick data       |
| **4.0**     | [TickAttrib Classes](#40-tickattrib-classes)                 | Data              | Tick attributes |
| **Related** | [Main Navigation](./README.md)                               | -                 | Back to index   |
| **Related** | [Core Classes](./01-API-REFERENCE-CLASSES.md)                | -                 | Execution class |
| **Related** | [Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md) | -                 | Order class     |

---

## Table of Contents

- [1.0 CommissionAndFeesReport Class](#10-commissionandfeesreport-class)
- [2.0 Liquidity Enum](#20-liquidity-enum)
- [3.0 HistoricalTick Classes](#30-historicaltick-classes)
  - [3.1 HistoricalTick](#31-historicaltick)
  - [3.2 HistoricalTickBidAsk](#32-historicaltickbidask)
  - [3.3 HistoricalTickLast](#33-historicalticklast)
- [4.0 TickAttrib Classes](#40-tickattrib-classes)
  - [4.1 TickAttrib](#41-tickattrib)
  - [4.2 TickAttribBidAsk](#42-tickattribbidask)
  - [4.3 TickAttribLast](#43-tickattriblast)
- [5.0 Quick Reference Card](#50-quick-reference-card)
- [6.0 Next Steps](#60-next-steps)

---

## 1.0 CommissionAndFeesReport Class

<!-- METADATA: scope=commission-fees, priority=reference, dependencies=[Execution] -->

**[REFERENCE]** Class documenting an order's commission, basis, and fees.

### 1.1 Public Attributes

| Name                  | Type   | Description                                             |
| --------------------- | ------ | ------------------------------------------------------- |
| `ExecId`              | string | Execution identifier to which commission report relates |
| `Commission`          | double | Total commissions charged                               |
| `Currency`            | string | Currency of commission report                           |
| `RealizedPNL`         | double | Realized PnL from trade                                 |
| `Yield`               | double | Trade's yield                                           |
| `YieldRedemptionDate` | int    | Trade's yield redemption date (YYYYMMDD)                |

### Public Member Functions

| Name                 | Type          | Description          |
| -------------------- | ------------- | -------------------- |
| `Equals(object obj)` | override bool | Equality comparison  |
| `GetHashCode()`      | override int  | Hash code generation |

---

## 2.0 Liquidity Enum

<!-- METADATA: scope=liquidity-types, priority=reference, dependencies=[] -->

**[REFERENCE]** Enum for types of liquidity provided by execution.

**[REQUIRED]** Requires TWS 968+ and API v973.05+

### 2.1 Enum Values

**[TICK-TYPE]** Liquidity classifications:

| Value | Name        | Description                   |
| ----- | ----------- | ----------------------------- |
| `0`   | `None`      | No liquidity flag information |
| `1`   | `Added`     | Added liquidity to market     |
| `2`   | `Removed`   | Removed liquidity from market |
| `3`   | `RoudedOut` | Liquidity routed out          |

### Public Member Functions

| Name                 | Type            | Description           |
| -------------------- | --------------- | --------------------- |
| `GetHashCode()`      | override int    | Hash code generation  |
| `ToString()`         | override string | String representation |
| `Equals(object obj)` | override bool   | Equality comparison   |

---

## 3.0 HistoricalTick Classes

<!-- METADATA: scope=historical-tick-data, priority=reference, dependencies=[] -->

**[HISTORICAL]** Classes representing historical tick data with different granularity and content.

### 3.1 HistoricalTick

**[HISTORICAL]** Historical tick for MIDPOINT data.

#### 3.1.1 Public Attributes

| Name    | Type    | Description                          |
| ------- | ------- | ------------------------------------ |
| `Time`  | long    | Tick's timestamp (UTC time_t format) |
| `Price` | double  | Tick's midpoint price                |
| `Size`  | decimal | Tick size                            |

---

### 3.2 HistoricalTickBidAsk

**[HISTORICAL]** Historical tick containing bid/ask prices.

#### 3.2.1 Public Attributes

| Name               | Type             | Description                                  |
| ------------------ | ---------------- | -------------------------------------------- |
| `Time`             | long             | Tick's timestamp (UTC time_t format)         |
| `TickAttribBidAsk` | TickAttribBidAsk | Tick attribute object (see TickAttribBidAsk) |
| `PriceBid`         | double           | Tick's bid price                             |
| `PriceAsk`         | double           | Tick's ask price                             |
| `SizeBid`          | decimal          | Tick's bid size                              |
| `SizeAsk`          | decimal          | Tick's ask size                              |

---

### 3.3 HistoricalTickLast

**[HISTORICAL]** Historical tick containing last trade price and details.

#### 3.3.1 Public Attributes

| Name                | Type           | Description                                |
| ------------------- | -------------- | ------------------------------------------ |
| `Time`              | long           | Tick's timestamp (UTC time_t format)       |
| `TickAttribLast`    | TickAttribLast | Tick attribute object (see TickAttribLast) |
| `Price`             | double         | Tick's last trade price                    |
| `Size`              | decimal        | Tick's last trade size                     |
| `Exchange`          | string         | Tick's exchange where last trade occurred  |
| `SpecialConditions` | string         | Special conditions for the tick            |

---

## 4.0 TickAttrib Classes

<!-- METADATA: scope=tick-attributes, priority=reference, dependencies=[] -->

**[REAL-TIME]** Classes containing tick attribute flags for different tick types.

### 4.1 TickAttrib

**[REAL-TIME]** Tick attributes for general ticks.

#### 4.1.1 Public Attributes

| Name             | Type | Description                         |
| ---------------- | ---- | ----------------------------------- |
| `CanAutoExecute` | bool | Whether tick can auto-execute       |
| `PastLimit`      | bool | Whether tick is past the limit      |
| `PreOpen`        | bool | Whether market is in pre-open state |

---

### 4.2 TickAttribBidAsk

**[REAL-TIME]** Tick attributes for bid/ask ticks.

#### 4.2.1 Public Attributes

| Name          | Type | Description                   |
| ------------- | ---- | ----------------------------- |
| `BidPastLow`  | bool | Bid is lower than day's low   |
| `AskPastHigh` | bool | Ask is higher than day's high |

---

### 4.3 TickAttribLast

**[REAL-TIME]** Tick attributes for last trade ticks.

#### 4.3.1 Public Attributes

| Name         | Type | Description                      |
| ------------ | ---- | -------------------------------- |
| `PastLimit`  | bool | Whether tick is past the limit   |
| `Unreported` | bool | Whether last trade is unreported |

---

## 5.0 Quick Reference Card

### Tick Types Decoder

**[TICK-TYPE]** Understanding tick data types:

| Tick Type    | Class                | Data Points                    | Use Case                |
| ------------ | -------------------- | ------------------------------ | ----------------------- |
| **MIDPOINT** | HistoricalTick       | Time, Price, Size              | General price history   |
| **BID_ASK**  | HistoricalTickBidAsk | Time, Bid, Ask, Sizes, Attribs | Spread analysis         |
| **TRADES**   | HistoricalTickLast   | Time, Price, Size, Exchange    | Trade execution history |

### Liquidity Types

| Value | Type      | Meaning                        |
| ----- | --------- | ------------------------------ |
| 0     | None      | No liquidity information       |
| 1     | Added     | Market maker added liquidity   |
| 2     | Removed   | Market taker removed liquidity |
| 3     | RoudedOut | Liquidity routed out           |

**[PERFORMANCE]** Liquidity rebates: Adding liquidity often receives rebates, removing liquidity incurs fees.

---

## 6.0 Next Steps

**[WORKFLOW]** Continue to related references:

- **[Core Classes](./01-API-REFERENCE-CLASSES.md)** - Execution class, EClient methods
- **[Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** - Order class, order types
- **[Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Conditional orders
- **[Data Types](./05-API-REFERENCE-DATA-TYPES.md)** - Helper classes

**[WORKFLOW]** Implementation guides:

- **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** - Historical tick data requests _(Coming Soon)_
- **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** - Execution reporting _(Coming Soon)_
- **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection patterns

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index

---

**[REFERENCE]** External resources:

- [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)
- [Market Data Guide](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/#market-data)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)

---

**Referenced by:**

- [Main Navigation](./README.md#11-api-reference-classes--methods) - Executions & Data (Ref-03)
- [Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md) - Execution class usage
