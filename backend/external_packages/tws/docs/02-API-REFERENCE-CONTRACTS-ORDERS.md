# TWS API Reference - Contracts & Orders

<!-- METADATA: scope=contracts-orders, priority=reference, dependencies=[01-CLASSES] -->

> **Source:** [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)  
> **Last Updated:** November 19, 2025

This document contains comprehensive reference information for TWS API contract and order-related classes.

**[REFERENCE]** Complete technical reference for order placement, execution reporting, and contract filtering.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section     | Class                                                    | Type            | Jump To                 |
| ----------- | -------------------------------------------------------- | --------------- | ----------------------- |
| **1.0**     | [Execution](#10-execution-class)                         | Trade           | Execution details       |
| **2.0**     | [ExecutionFilter](#20-executionfilter-class)             | Filter          | Execution filtering     |
| **3.0**     | [Order](#30-order-class)                                 | [REQUIRED] Core | Order parameters (100+) |
| **4.0**     | [OrderAllocation](#40-orderallocation-class)             | Advanced        | FA allocations          |
| **5.0**     | [OrderCancel](#50-ordercancel-class)                     | Action          | Order cancellation      |
| **6.0**     | [OrderComboLeg](#60-ordercomboleg-class)                 | Order           | Combo order legs        |
| **7.0**     | [OrderState](#70-orderstate-class)                       | Status          | Order state info        |
| **8.0**     | [ScannerSubscription](#80-scannersubscription-class)     | Data            | Market scanner          |
| **9.0**     | [SoftDollarTier](#90-softdollartier-class)               | Advanced        | Soft dollar tiers       |
| **10.0**    | [TagValue](#100-tagvalue-class)                          | Utility         | Key-value pairs         |
| **Related** | [Main Navigation](./README.md)                           | -               | Back to index           |
| **Related** | [Core Classes](./01-API-REFERENCE-CLASSES.md)            | -               | EClient, Contract       |
| **Related** | [Conditions](./04-API-REFERENCE-CONDITIONS.md)           | -               | Conditional orders      |
| **Related** | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) | -               | _(Coming Soon)_         |

---

## Table of Contents

- [1.0 Execution Class](#10-execution-class)
- [2.0 ExecutionFilter Class](#20-executionfilter-class)
- [3.0 Order Class](#30-order-class)
- [4.0 OrderAllocation Class](#40-orderallocation-class)
- [5.0 OrderCancel Class](#50-ordercancel-class)
- [6.0 OrderComboLeg Class](#60-ordercomboleg-class)
- [7.0 OrderState Class](#70-orderstate-class)
- [8.0 ScannerSubscription Class](#80-scannersubscription-class)
- [9.0 SoftDollarTier Class](#90-softdollartier-class)
- [10.0 TagValue Class](#100-tagvalue-class)
- [11.0 Quick Reference Cards](#110-quick-reference-cards)
- [12.0 Next Steps](#120-next-steps)

---

## 1.0 Execution Class

<!-- METADATA: scope=execution-details, priority=reference, dependencies=[] -->

**[REFERENCE]** Class describing an order's execution.

### 1.1 Public Attributes

| Name                   | Type      | Description                                                                                                         |
| ---------------------- | --------- | ------------------------------------------------------------------------------------------------------------------- |
| `OrderId`              | int       | API client's order ID (may not be unique to account)                                                                |
| `ClientId`             | int       | API client identifier which placed the order                                                                        |
| `ExecId`               | string    | Execution's identifier. Each partial fill has separate ExecId. Corrections differ only in digits after final period |
| `Time`                 | string    | Execution's server time                                                                                             |
| `AcctNumber`           | string    | Account to which order was allocated                                                                                |
| `Exchange`             | string    | Exchange where execution took place                                                                                 |
| `Side`                 | string    | BOT (bought) or SLD (sold)                                                                                          |
| `Shares`               | decimal   | Number of shares filled                                                                                             |
| `Price`                | double    | Execution price excluding commissions                                                                               |
| `PermId`               | int       | TWS order identifier (can be 0 for trades from outside IB)                                                          |
| `Liquidation`          | int       | Identifies IB-initiated liquidation execution                                                                       |
| `CumQty`               | decimal   | Cumulative quantity for regular trades, average fill price for ODD lot                                              |
| `AvgPrice`             | double    | Average price for regular trades, cumulative quantity for ODD lot                                                   |
| `OrderRef`             | string    | User-customizable string associated with order for its lifetime                                                     |
| `EvRule`               | string    | Economic Value Rule name and optional argument (separated by colon)                                                 |
| `EvMultiplier`         | double    | Approximate market value change per 1 unit price change                                                             |
| `ModelCode`            | string    | Model code                                                                                                          |
| `LastLiquidity`        | Liquidity | Liquidity type (requires TWS 968+, API v973.05+)                                                                    |
| `PendingPriceRevision` | bool      | Pending price revision flag                                                                                         |

### Public Member Functions

| Name                 | Type          | Description          |
| -------------------- | ------------- | -------------------- |
| `Equals(object obj)` | override bool | Equality comparison  |
| `GetHashCode()`      | override int  | Hash code generation |

---

## 2.0 ExecutionFilter Class

<!-- METADATA: scope=execution-filter, priority=reference, dependencies=[Execution] -->

**[REFERENCE]** Filter for requesting executions - specifies subset of executions to receive.

### 2.1 Public Attributes

| Name       | Type   | Description                                             |
| ---------- | ------ | ------------------------------------------------------- |
| `ClientId` | int    | API client which placed the order                       |
| `AcctCode` | string | Account to which order was allocated                    |
| `Time`     | string | Time from which executions returned (yyyymmdd hh:mm:ss) |
| `Symbol`   | string | Instrument's symbol                                     |
| `SecType`  | string | Contract's security type (STK, OPT, FUT, etc.)          |
| `Exchange` | string | Exchange at which execution was produced                |
| `Side`     | string | Contract's side (BUY or SELL)                           |

### Public Member Functions

| Name                 | Type          | Description          |
| -------------------- | ------------- | -------------------- |
| `Equals(object obj)` | override bool | Equality comparison  |
| `GetHashCode()`      | override int  | Hash code generation |

---

## 3.0 Order Class

<!-- METADATA: scope=order-parameters, priority=critical, dependencies=[Contract] -->

**[REQUIRED]** **[CRITICAL]** Complete order definition with all available order parameters. This is one of the most comprehensive classes with 100+ attributes.

### 3.1 Public Attributes

#### 3.1.1 Basic Order Parameters

**[ORDER-TYPE]** Core order parameters:

| Name            | Type    | Description                                                          |
| --------------- | ------- | -------------------------------------------------------------------- |
| `OrderId`       | int     | API client's order ID                                                |
| `ClientId`      | int     | API client ID that placed the order                                  |
| `PermId`        | int     | Host order identifier                                                |
| `Action`        | string  | Order side: BUY, SELL, SSHORT (institutional), SLONG (institutional) |
| `TotalQuantity` | decimal | Number of positions being bought/sold                                |
| `OrderType`     | string  | Order's type                                                         |
| `LmtPrice`      | double  | LIMIT price for limit/stop-limit orders                              |
| `AuxPrice`      | double  | Stop price for STP LMT orders, trailing amount, etc.                 |
| `Tif`           | string  | Time in force (DAY, GTC, IOC, GTD, etc.)                             |

#### Account & Clearing

| Name              | Type   | Description                                             |
| ----------------- | ------ | ------------------------------------------------------- |
| `Account`         | string | Account the trade will be allocated to                  |
| `ClearingAccount` | string | True beneficiary for execution-only customers (FUT/FOP) |
| `ClearingIntent`  | string | Where shares cleared: IB, Away, PTA                     |
| `SettlingFirm`    | string | Firm which will settle the trade (institutions)         |

#### Order Routing

| Name                 | Type   | Description                                                      |
| -------------------- | ------ | ---------------------------------------------------------------- |
| `Exchange`           | string | Order destination exchange                                       |
| `PrimaryExch`        | string | Primary exchange (for smart-routed orders)                       |
| `OptOutSmartRouting` | bool   | Opt out of SmartRouting for ASX orders                           |
| `DesignatedLocation` | string | Location where shares to short come from (institutional, slot=2) |

#### Price & Size Modifiers

| Name                          | Type   | Description                                     |
| ----------------------------- | ------ | ----------------------------------------------- |
| `PercentOffset`               | double | Percent offset for relative orders              |
| `DiscretionaryAmt`            | double | Amount off limit price for discretionary orders |
| `DiscretionaryUpToLimitPrice` | bool   | Convert Primary Peg to D-Peg                    |
| `DisplaySize`                 | int    | Publicly disclosed order size (iceberg orders)  |
| `SweepToFill`                 | bool   | Attempt to fill entire order at best prices     |
| `AllOrNone`                   | bool   | All shares must fill on single execution        |
| `MinQty`                      | int    | Minimum quantity order type                     |
| `Hidden`                      | bool   | Order not visible in market depth (NASDAQ only) |

#### Time-Related

| Name              | Type         | Description                                           |
| ----------------- | ------------ | ----------------------------------------------------- |
| `GoodAfterTime`   | string       | Order active after this time (yyyymmdd hh:mm:ss {TZ}) |
| `GoodTillDate`    | string       | Order cancels if not filled by this time (GTD only)   |
| `Duration`        | int          | Order active for this many seconds (GTD alternative)  |
| `ActiveStartTime` | List<string> | Start time for GTC orders                             |
| `ActiveStopTime`  | string       | Stop time for GTC orders                              |
| `AutoCancelDate`  | string       | Date to auto-cancel order                             |

#### Financial Advisor

| Name           | Type   | Description                  |
| -------------- | ------ | ---------------------------- |
| `FaGroup`      | string | FA group for allocation      |
| `FaMethod`     | string | FA allocation method         |
| `FaPercentage` | string | FA percentage for allocation |
| `FaProfile`    | string | FA profile for allocation    |

#### Algorithmic Trading

| Name           | Type           | Description                                                 |
| -------------- | -------------- | ----------------------------------------------------------- |
| `AlgoStrategy` | string         | Algorithm strategy (ArrivalPx, DarkIce, PctVol, Twap, Vwap) |
| `AlgoParams`   | List<TagValue> | Parameters for IB algorithm                                 |
| `AlgoId`       | string         | Identifies orders from algorithmic trading                  |

#### Special Order Types - VOL Orders

| Name                             | Type   | Description                                   |
| -------------------------------- | ------ | --------------------------------------------- |
| `Volatility`                     | double | Option price in volatility                    |
| `VolatilityType`                 | int    | 1 = Daily, 2 = Annual volatility              |
| `ContinuousUpdate`               | int    | TWS auto-updates limit price (VOL orders)     |
| `ReferencePriceType`             | int    | How TWS calculates limit price for options    |
| `DeltaNeutralOrderType`          | string | Delta neutral hedge order type                |
| `DeltaNeutralAuxPrice`           | double | Aux price for delta neutral order type        |
| `DeltaNeutralConId`              | int    | Contract ID for delta neutral order           |
| `DeltaNeutralSettlingFirm`       | string | Delta neutral settling firm                   |
| `DeltaNeutralClearingAccount`    | string | Beneficiary of delta neutral order            |
| `DeltaNeutralClearingIntent`     | string | Where delta neutral shares cleared            |
| `DeltaNeutralOpenClose`          | string | Open or close for delta neutral CFD           |
| `DeltaNeutralShortSale`          | bool   | Delta neutral hedge involves stock short sale |
| `DeltaNeutralShortSaleSlot`      | int    | Delta neutral short sale slot (1 or 2)        |
| `DeltaNeutralDesignatedLocation` | string | Third party location for delta neutral short  |

#### Special Order Types - Scale Orders

| Name                       | Type   | Description                                         |
| -------------------------- | ------ | --------------------------------------------------- |
| `ScaleInitLevelSize`       | int    | Size of first (initial) order component             |
| `ScaleSubsLevelSize`       | int    | Size of subsequent scale order components           |
| `ScalePriceIncrement`      | double | Price increment between scale components (required) |
| `ScalePriceAdjustValue`    | double | Price adjustment for extended scale orders          |
| `ScalePriceAdjustInterval` | int    | Interval for price adjustment                       |
| `ScaleProfitOffset`        | double | Profit offset for extended scale orders             |
| `ScaleAutoReset`           | bool   | Restart scale if cancelled                          |
| `ScaleInitPosition`        | int    | Initial position for extended scale orders          |
| `ScaleInitFillQty`         | int    | Initial quantity to fill                            |
| `ScaleRandomPercent`       | bool   | Random percent adjustment                           |
| `ScaleTable`               | string | List of scale orders                                |

#### Special Order Types - Hedge Orders

| Name         | Type   | Description                           |
| ------------ | ------ | ------------------------------------- |
| `HedgeType`  | string | D (Delta), B (Beta), F (FX), P (Pair) |
| `HedgeParam` | string | Beta=x for Beta hedge, ratio for Pair |

#### Special Order Types - Combo Orders

| Name                      | Type                | Description                                   |
| ------------------------- | ------------------- | --------------------------------------------- |
| `OrderComboLegs`          | List<OrderComboLeg> | Per-leg prices (combo price left unspecified) |
| `SmartComboRoutingParams` | List<TagValue>      | Advanced smart combo routing parameters       |

#### Special Order Types - Box Orders (BOX Exchange)

| Name              | Type   | Description                           |
| ----------------- | ------ | ------------------------------------- |
| `StartingPrice`   | double | Auction starting price                |
| `StockRefPrice`   | double | Stock reference price for VOL orders  |
| `Delta`           | double | Stock's delta for BOX orders          |
| `StockRangeLower` | double | Lower acceptable stock price range    |
| `StockRangeUpper` | double | Upper acceptable stock price range    |
| `AuctionStrategy` | int    | 1=Match, 2=Improvement, 3=Transparent |

#### Special Order Types - Pegged Orders

| Name                           | Type   | Description                                           |
| ------------------------------ | ------ | ----------------------------------------------------- |
| `PeggedChangeAmount`           | double | Amount by which pegged price should move              |
| `IsPeggedChangeAmountDecrease` | bool   | Whether pegged price increases or decreases           |
| `ReferenceContractId`          | int    | Contract ID for pegged-to-benchmark                   |
| `ReferenceExchange`            | string | Exchange for reference contract observation           |
| `ReferenceChangeAmount`        | double | Reference contract move amount to adjust pegged order |
| `ReferencePriceType`           | int    | Price type for pegged-to-benchmark                    |

#### Special Order Types - Adjusted Orders

| Name                     | Type   | Description                                          |
| ------------------------ | ------ | ---------------------------------------------------- |
| `AdjustedOrderType`      | string | Parent adjusted to this type when trigger penetrated |
| `AdjustedStopPrice`      | double | Stop price for adjusted STP parent                   |
| `AdjustedStopLimitPrice` | double | Stop limit price for adjusted STPL LMT parent        |
| `AdjustedTrailingAmount` | double | Trailing amount for adjusted TRAIL parent            |
| `AdjustableTrailingUnit` | int    | 0=amount, 1=percentage                               |
| `LmtPriceOffset`         | double | Price offset for stop movement increments            |
| `TriggerPrice`           | double | Trigger price to execute adjusted stop orders        |

#### Special Order Types - IBKRATS Orders

| Name                       | Type   | Description                                                |
| -------------------------- | ------ | ---------------------------------------------------------- |
| `CompeteAgainstBestOffset` | double | Offset when spread is odd number of cents                  |
| `MidOffsetAtWhole`         | double | Offset when spread is even number of cents (whole pennies) |
| `MidOffsetAtHalf`          | double | Offset when spread is odd number of cents (half pennies)   |
| `MinCompeteSize`           | int    | Minimum size to compete                                    |
| `MinTradeQty`              | int    | Minimum trade quantity to fill                             |

#### Conditions

| Name                    | Type                 | Description                                                    |
| ----------------------- | -------------------- | -------------------------------------------------------------- |
| `Conditions`            | List<OrderCondition> | Conditions determining order activation/cancellation           |
| `ConditionsIgnoreRth`   | bool                 | Conditions valid outside regular trading hours                 |
| `ConditionsCancelOrder` | bool                 | Conditions determine activation (false) or cancellation (true) |

#### Extended Order Attributes

| Name                            | Type   | Description                                                     |
| ------------------------------- | ------ | --------------------------------------------------------------- |
| `Transmit`                      | bool   | Whether order transmitted by TWS (false = created but not sent) |
| `ParentId`                      | int    | Parent order ID for bracket/trailing stop                       |
| `ParentPermId`                  | long   | Parent order permanent ID                                       |
| `BlockOrder`                    | bool   | Order is block order                                            |
| `NotHeld`                       | bool   | Order tagged as "post only" (IBDARK)                            |
| `OutsideRth`                    | bool   | Allow trigger/fill outside regular trading hours                |
| `WhatIf`                        | bool   | Retrieve commissions/margin without placing order               |
| `OverridePercentageConstraints` | bool   | Override TWS precautionary constraints                          |
| `Rule80A`                       | string | Individual/Agency/AgentOtherMember variations                   |
| `ImbalanceOnly`                 | bool   | Imbalance only open/closing orders                              |
| `RouteMarketableToBbo`          | bool   | Route market order to best bid/offer                            |
| `Origin`                        | int    | 0=Customer, 1=Firm                                              |

#### Short Sale

| Name            | Type | Description                                         |
| --------------- | ---- | --------------------------------------------------- |
| `ShortSaleSlot` | int  | 1=broker holds shares, 2=shares from elsewhere      |
| `ExemptCode`    | int  | 0=does not apply, -1=applies short sale uptick rule |

#### Institutional

| Name          | Type   | Description                                |
| ------------- | ------ | ------------------------------------------ |
| `OpenClose`   | string | O (open) or C (close) - institutional only |
| `Shareholder` | string | Shareholder identifier                     |

#### MiFIR (European Regulations)

| Name                    | Type   | Description                                    |
| ----------------------- | ------ | ---------------------------------------------- |
| `Mifid2DecisionMaker`   | string | Person responsible for investment decisions    |
| `Mifid2DecisionAlgo`    | string | Algorithm responsible for investment decisions |
| `Mifid2ExecutionTrader` | string | Person responsible for execution               |
| `Mifid2ExecutionAlgo`   | string | Algorithm responsible for execution            |

#### Miscellaneous

| Name                       | Type           | Description                                                  |
| -------------------------- | -------------- | ------------------------------------------------------------ |
| `OrderRef`                 | string         | Order reference for institutional customers                  |
| `Tier`                     | SoftDollarTier | Soft dollar tier (advisors/funds)                            |
| `CashQty`                  | double         | Native cash quantity                                         |
| `DontUseAutoPriceForHedge` | bool           | Don't use auto price for hedge                               |
| `IsOmsContainer`           | bool           | Create tickets from API orders in TWS OMS mode               |
| `UsePriceMgmtAlgo`         | bool           | Use Price Management Algo (CTCI users)                       |
| `Solicited`                | bool           | Order initiated/recommended by broker and approved by client |
| `RandomizePrice`           | bool           | Randomize price (VOL/Pegged to VOL)                          |
| `RandomizeSize`            | bool           | Randomize size (VOL/Pegged to VOL)                           |
| `FilledQuantity`           | decimal        | Initial order quantity to be filled                          |
| `RefFuturesConId`          | int            | Reference futures contract ID                                |
| `AutoCancelParent`         | bool           | Cancel parent if child cancelled                             |
| `ModelCode`                | string         | Place order to model (e.g., "Technology")                    |
| `ExtOperator`              | string         | CME Rule 576: unique API operator identifier                 |
| `ManualOrderIndicator`     | int            | CME Rule 576: 1=manual, 0=automated                          |
| `ManualOrderTime`          | string         | Manual order entry time (YYYYMMDD-HH:mm:ss UTC)              |
| `PostToAts`                | int            | Post to ATS value (must be positive or empty)                |
| `AdvancedErrorOverride`    | string         | Parameters from advancedOrderRejectJson                      |
| `OrderMiscOptions`         | List<TagValue> | Internal use - use default value XYZ                         |

#### Nondisclosed Omnibus Accounts

| Name              | Type    | Description                                               |
| ----------------- | ------- | --------------------------------------------------------- |
| `customerAccount` | string  | Unique hashed identifier for account within Omnibus       |
| `isProCustomer`   | boolean | Subaccount classified as Professional or Non-Professional |

#### Trailing Stop

| Name              | Type   | Description                             |
| ----------------- | ------ | --------------------------------------- |
| `TrailStopPrice`  | double | Trail stop price for TRAIL LIMIT orders |
| `TrailingPercent` | double | Trailing amount as percentage           |

#### Price & Size Constraints

| Name              | Type   | Description                                         |
| ----------------- | ------ | --------------------------------------------------- |
| `BasisPoints`     | double | Basis points for EFP orders (0.01% = 1 basis point) |
| `BasisPointsType` | int    | Increment of basis points for EFP orders            |

### Public Member Functions

| Name                 | Type          | Description          |
| -------------------- | ------------- | -------------------- |
| `Equals(object obj)` | override bool | Equality comparison  |
| `GetHashCode()`      | override int  | Hash code generation |

### Static Public Member Functions (Constants)

| Name                                    | Type          | Value                   |
| --------------------------------------- | ------------- | ----------------------- |
| `CUSTOMER`                              | static int    | 0                       |
| `FIRM`                                  | static int    | 1                       |
| `OPT_UNKNOWN`                           | static char   | '?'                     |
| `OPT_BROKER_DEALER`                     | static char   | 'b'                     |
| `OPT_CUSTOMER`                          | static char   | 'c'                     |
| `OPT_FIRM`                              | static char   | 'f'                     |
| `OPT_ISEMM`                             | static char   | 'm'                     |
| `OPT_FARMM`                             | static char   | 'n'                     |
| `OPT_SPECIALIST`                        | static char   | 'y'                     |
| `AUCTION_MATCH`                         | static int    | 1                       |
| `AUCTION_IMPROVEMENT`                   | static int    | 2                       |
| `AUCTION_TRANSPARENT`                   | static int    | 3                       |
| `EMPTY_STR`                             | static string | ""                      |
| `COMPETE_AGAINST_BEST_OFFSET_UP_TO_MID` | static double | double.PositiveInfinity |

---

## 4.0 OrderAllocation Class

<!-- METADATA: scope=fa-allocations, priority=advanced, dependencies=[Order] -->

**[ADVANCED]** Financial Advisor order allocation.

Advisor's allocations while trading subaccounts.

### Public Attributes

| Name              | Type    | Description                                            |
| ----------------- | ------- | ------------------------------------------------------ |
| `Account`         | string  | Account ID being allocated to (e.g., U1234567)         |
| `Position`        | decimal | Current position of account being allocated to         |
| `PositionDesired` | decimal | Full position increase intended by current trade       |
| `PositionAfter`   | decimal | Position increase from current trade                   |
| `DesiredAllocQty` | decimal | Quantity to increase by based on allocation            |
| `AllowedAllocQty` | decimal | Maximum allowed quantity increase                      |
| `IsMonetary`      | boolean | True=monetary allocation, False=whole share allocation |

---

## 5.0 OrderCancel Class

<!-- METADATA: scope=order-cancellation, priority=reference, dependencies=[Order] -->

**[REFERENCE]** Order cancellation request.

Order cancellation parameters.

### Public Attributes

| Name                    | Type   | Description                                                     |
| ----------------------- | ------ | --------------------------------------------------------------- |
| `extOperator`           | string | CME Rule 576: unique API operator identifier at time of trading |
| `manualOrderIndicator`  | int    | CME Rule 576: 1=manual, 0=automated                             |
| `manualOrderCancelTime` | string | Manual cancellation time (YYYYMMDD-HH:mm:ss UTC)                |

---

## 6.0 OrderComboLeg Class

<!-- METADATA: scope=combo-order-legs, priority=advanced, dependencies=[Order, ComboLeg] -->

**[ADVANCED]** Leg-specific price for combo orders.

Specify price on an order's leg.

### Public Attributes

| Name    | Type   | Description       |
| ------- | ------ | ----------------- |
| `Price` | double | Order leg's price |

### Public Member Functions

| Name                    | Type          | Description           |
| ----------------------- | ------------- | --------------------- |
| `OrderComboLeg(double)` | constructor   | Initialize with price |
| `Equals(object obj)`    | override bool | Equality comparison   |
| `GetHashCode()`         | override int  | Hash code generation  |

---

## 7.0 OrderState Class

<!-- METADATA: scope=order-state, priority=reference, dependencies=[Order] -->

**[REFERENCE]** Provides state information for an order.

Active order's current state.

### Public Attributes

| Name                             | Type   | Description                                       |
| -------------------------------- | ------ | ------------------------------------------------- |
| `Status`                         | string | Order's current status                            |
| `InitMarginBefore`               | string | Account's current initial margin                  |
| `MaintMarginBefore`              | string | Account's current maintenance margin              |
| `EquityWithLoanBefore`           | string | Account's current equity with loan                |
| `InitMarginChange`               | string | Change of account's initial margin                |
| `MaintMarginChange`              | string | Change of account's maintenance margin            |
| `EquityWithLoanChange`           | string | Change of account's equity with loan              |
| `InitMarginAfter`                | string | Order's impact on initial margin                  |
| `MaintMarginAfter`               | string | Order's impact on maintenance margin              |
| `EquityWithLoanAfter`            | string | Order's impact on equity with loan                |
| `InitMarginBeforeOutsideRTH`     | float  | Expected initial margin outside RTH               |
| `MaintMarginBeforeOutsideRTH`    | float  | Expected maintenance margin outside RTH           |
| `EquityWithLoanBeforeOutsideRTH` | float  | Expected equity with loan outside RTH             |
| `InitMarginChangeOutsideRTH`     | float  | Expected initial margin change outside RTH        |
| `MaintMarginChangeOutsideRTH`    | float  | Expected maintenance margin change outside RTH    |
| `EquityWithLoanChangeOutsideRTH` | float  | Expected equity with loan change outside RTH      |
| `InitMarginAfterOutsideRTH`      | float  | Expected impact on initial margin outside RTH     |
| `MaintMarginAfterOutsideRTH`     | float  | Expected impact on maintenance margin outside RTH |
| `EquityWithLoanAfterOutsideRTH`  | float  | Expected impact on equity with loan outside RTH   |
| `Commission`                     | double | Order's generated commission                      |
| `MinCommission`                  | double | Execution's minimum commission                    |
| `MaxCommission`                  | double | Execution's maximum commission                    |
| `CommissionCurrency`             | string | Generated commission currency                     |
| `WarningText`                    | string | Warning message if order is warranted             |
| `CompletedTime`                  | string | Order completion time                             |
| `CompletedStatus`                | string | Order completion status                           |

### Public Member Functions

| Name                 | Type          | Description                    |
| -------------------- | ------------- | ------------------------------ |
| `OrderState(...)`    | constructor   | Initialize with all parameters |
| `Equals(object obj)` | override bool | Equality comparison            |
| `GetHashCode()`      | override int  | Hash code generation           |

---

## 8.0 ScannerSubscription Class

<!-- METADATA: scope=market-scanner, priority=reference, dependencies=[] -->

**[REFERENCE]** Market scanner subscription parameters.

Defines a market scanner request.

### Public Attributes

| Name                       | Type   | Description                                                   |
| -------------------------- | ------ | ------------------------------------------------------------- |
| `NumberOfRows`             | int    | Number of results to return (max 50, default 50)              |
| `Instrument`               | string | Instrument type to return (see scannerParameters XML)         |
| `LocationCode`             | string | Exchange regions to return (see scannerParameters XML)        |
| `ScanCode`                 | string | Code to sort results by (see scannerParameters XML)           |
| `AbovePrice`               | double | Maximum MARK price filter                                     |
| `BelowPrice`               | double | Minimum MARK price filter                                     |
| `AboveVolume`              | int    | Minimum trade volume of the day                               |
| `AverageOptionVolumeAbove` | int    | Minimum average option volume from underlying                 |
| `MarketCapAbove`           | double | Minimum market cap                                            |
| `MarketCapBelow`           | double | Maximum market cap                                            |
| `MoodyRatingAbove`         | string | Minimum Moody rating                                          |
| `MoodyRatingBelow`         | string | Maximum Moody rating                                          |
| `SpRatingAbove`            | string | Minimum S&P rating                                            |
| `SpRatingBelow`            | string | Maximum S&P rating                                            |
| `MaturityDateAbove`        | string | Minimum maturity date (YYYYMMDD)                              |
| `MaturityDateBelow`        | string | Maximum maturity date (YYYYMMDD)                              |
| `CouponRateAbove`          | double | Minimum coupon rate                                           |
| `CouponRateBelow`          | double | Maximum coupon rate                                           |
| `ExcludeConvertible`       | bool   | Exclude convertible bonds                                     |
| `ScannerSettingPairs`      | string | Scanner restrictions (currently only annualVolatility)        |
| `StockTypeFilter`          | string | Stock type: Common, CORP, ADR, ETF, ETN, REIT, CEF, ETMF, EFN |

---

## 9.0 SoftDollarTier Class

<!-- METADATA: scope=soft-dollar-tiers, priority=advanced, dependencies=[] -->

**[ADVANCED]** Soft dollar tier information.

Container for Soft Dollar Tier information.

### Public Attributes

| Name          | Type   | Description                   |
| ------------- | ------ | ----------------------------- |
| `Name`        | string | Soft Dollar Tier name         |
| `Value`       | string | Soft Dollar Tier value        |
| `DisplayName` | string | Soft Dollar Tier display name |

### Public Member Functions

| Name                 | Type            | Description           |
| -------------------- | --------------- | --------------------- |
| `Equals(object obj)` | override bool   | Equality comparison   |
| `GetHashCode()`      | override int    | Hash code generation  |
| `ToString()`         | override string | String representation |

### Static Public Member Functions

| Name                                         | Type        | Description         |
| -------------------------------------------- | ----------- | ------------------- |
| `operator==(SoftDollarTier, SoftDollarTier)` | static bool | Equality operator   |
| `operator!=(SoftDollarTier, SoftDollarTier)` | static bool | Inequality operator |

---

## 10.0 TagValue Class

<!-- METADATA: scope=key-value-pairs, priority=utility, dependencies=[] -->

**[UTILITY]** Simple key-value pair structure for various API operations.

Convenience class for key-value pairs.

### Public Attributes

| Name    | Type   | Description  |
| ------- | ------ | ------------ |
| `Tag`   | string | Tag/key name |
| `Value` | string | Tag value    |

### Public Member Functions

| Name                 | Type          | Description          |
| -------------------- | ------------- | -------------------- |
| `Equals(object obj)` | override bool | Equality comparison  |
| `GetHashCode()`      | override int  | Hash code generation |

---

## 11.0 Quick Reference Cards

### Order Types Quick Reference

**[ORDER-TYPE]** Common order types:

| Order Type  | Description       | Use Case                            |
| ----------- | ----------------- | ----------------------------------- |
| **MKT**     | Market            | Execute immediately at best price   |
| **LMT**     | Limit             | Execute at specific price or better |
| **STP**     | Stop              | Trigger market order at stop price  |
| **STP LMT** | Stop Limit        | Trigger limit order at stop price   |
| **TRAIL**   | Trailing Stop     | Dynamic stop follows market         |
| **REL**     | Relative          | Price relative to NBBO              |
| **MOC**     | Market on Close   | Execute at closing price            |
| **LOC**     | Limit on Close    | Limit order at close                |
| **MIT**     | Market if Touched | Market order when price reached     |
| **LIT**     | Limit if Touched  | Limit order when price reached      |

### Time in Force (TIF) Options

**[REQUIRED]** Time in force values:

| TIF     | Description         | Behavior                          |
| ------- | ------------------- | --------------------------------- |
| **DAY** | Day                 | Cancel at end of trading day      |
| **GTC** | Good Till Canceled  | Active until canceled             |
| **IOC** | Immediate or Cancel | Fill immediately, cancel unfilled |
| **GTD** | Good Till Date      | Active until specific date        |
| **OPG** | Market on Open      | Execute at market open            |
| **FOK** | Fill or Kill        | Fill entire order or cancel       |
| **DTC** | Day Till Canceled   | Day order with GTC behavior       |

### Order Parameter Validation Rules

**[PITFALL]** Common validation errors:

- **LmtPrice required:** LMT, STP LMT, REL, LOC, LIT orders
- **AuxPrice required:** STP, STP LMT, TRAIL orders
- **TotalQuantity > 0:** All orders must have positive quantity
- **Action required:** Must be BUY, SELL, SSHORT, or SLONG
- **OrderType required:** Must specify valid order type
- **Account required:** For multi-account users

**[EXAMPLE]** Market order (minimal):

```python
order = Order()
order.action = "BUY"
order.totalQuantity = 100
order.orderType = "MKT"
```

**[EXAMPLE]** Limit order:

```python
order = Order()
order.action = "BUY"
order.totalQuantity = 100
order.orderType = "LMT"
order.lmtPrice = 150.00
order.tif = "DAY"
```

**[EXAMPLE]** Stop-limit order:

```python
order = Order()
order.action = "SELL"
order.totalQuantity = 100
order.orderType = "STP LMT"
order.lmtPrice = 145.00  # Limit price
order.auxPrice = 148.00  # Stop trigger price
order.tif = "GTC"
```

---

## 12.0 Next Steps

**[WORKFLOW]** Continue to related references:

- **[Core Classes](./01-API-REFERENCE-CLASSES.md)** - EClient.placeOrder(), Contract class
- **[Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Conditional order triggers
- **[Executions & Data](./03-API-REFERENCE-EXECUTIONS.md)** - Execution reporting
- **[Data Types](./05-API-REFERENCE-DATA-TYPES.md)** - Helper classes

**[WORKFLOW]** Implementation guides:

- **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** - Place and manage orders _(Coming Soon)_
- **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection patterns
- **[Setup Guide](./06-SETUP-GUIDE.md)** - Installation

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index

---

**[REFERENCE]** External resources:

- [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)
- [Order Types Guide](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/#order-types)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)

---

**Referenced by:**

- [Main Navigation](./README.md#11-api-reference-classes--methods) - Contracts & Orders (Ref-02)
- [Core Classes](./01-API-REFERENCE-CLASSES.md) - Order class reference
- [Conditions](./04-API-REFERENCE-CONDITIONS.md) - Conditional orders use Order class
- [Execution & Trade Classes](./03-API-REFERENCE-EXECUTIONS.md)
- [Condition Classes](./04-API-REFERENCE-CONDITIONS.md)
- [Data Type Classes](./05-API-REFERENCE-DATA-TYPES.md)
