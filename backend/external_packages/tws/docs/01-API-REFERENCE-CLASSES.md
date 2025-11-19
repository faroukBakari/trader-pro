# TWS API Reference - Core Classes

<!-- METADATA: scope=core-api-classes, priority=reference, dependencies=[] -->

> **Source:** [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)  
> **Last Updated:** November 19, 2025

This document contains comprehensive reference information for all core TWS API classes.

**[REFERENCE]** Complete technical reference for core API classes, methods, and data structures.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section     | Class                                                        | Type            | Jump To                |
| ----------- | ------------------------------------------------------------ | --------------- | ---------------------- |
| **1.0**     | [AccountSummaryTags](#10-accountsummarytags-class)           | Account         | Tag definitions        |
| **2.0**     | [Bar](#20-bar-class-reference)                               | Data            | Historical bars        |
| **3.0**     | [ComboLeg](#30-comboleg-class-reference)                     | Order           | Combo orders           |
| **4.0**     | [CommissionAndFeesReport](#40-commissionandfeesreport-class) | Trade           | Commission data        |
| **5.0**     | [Contract](#50-contract-class-reference)                     | [REQUIRED] Core | Security definition    |
| **6.0**     | [ContractDetails](#60-contractdetails-class-reference)       | Data            | Extended contract info |
| **7.0**     | [CodeMsgPair](#70-codemsgpair-class-reference)               | Data            | Error codes            |
| **8.0**     | [DeltaNeutralContract](#80-deltaneutralcontract-class)       | Order           | Delta hedging          |
| **9.0**     | [EClient](#90-eclient-class-reference)                       | [REQUEST] Core  | Request methods        |
| **10.0**    | [EClientSocket](#100-eclientsocket-class-reference)          | Core            | Socket connection      |
| **11.0**    | [EReader](#110-ereader-class-reference)                      | Threading       | Message queue          |
| **12.0**    | [EReaderSignal](#120-ereadersignal-interface)                | Threading       | Thread signaling       |
| **13.0**    | [EWrapper](#130-ewrapper-interface-reference)                | [CALLBACK] Core | Event callbacks        |
| **Related** | [Main Navigation](./README.md)                               | -               | Back to index          |
| **Related** | [Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md) | -               | Order class            |
| **Related** | [Setup Guide](./06-SETUP-GUIDE.md)                           | -               | Installation           |
| **Related** | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)             | -               | Connection patterns    |

---

## Table of Contents

- [1.0 AccountSummaryTags Class](#10-accountsummarytags-class)
- [2.0 Bar Class Reference](#20-bar-class-reference)
- [3.0 ComboLeg Class Reference](#30-comboleg-class-reference)
- [4.0 CommissionAndFeesReport Class](#40-commissionandfeesreport-class)
- [5.0 Contract Class Reference](#50-contract-class-reference)
- [6.0 ContractDetails Class Reference](#60-contractdetails-class-reference)
- [7.0 CodeMsgPair Class Reference](#70-codemsgpair-class-reference)
- [8.0 DeltaNeutralContract Class](#80-deltaneutralcontract-class)
- [9.0 EClient Class Reference](#90-eclient-class-reference)
- [10.0 EClientSocket Class Reference](#100-eclientsocket-class-reference)
- [11.0 EReader Class Reference](#110-ereader-class-reference)
- [12.0 EReaderSignal Interface](#120-ereadersignal-interface)
- [13.0 EWrapper Interface Reference](#130-ewrapper-interface-reference)
- [14.0 Quick Reference Cards](#140-quick-reference-cards)
- [15.0 Next Steps](#150-next-steps)

---

## 1.0 AccountSummaryTags Class

<!-- METADATA: scope=account-summary-tags, priority=reference, dependencies=[] -->

**[REFERENCE]** Class containing all existing values being reported by `EClientSocket::reqAccountSummary`.

### 1.1 Public Attributes

| Name                                                                | Type   | Description                                                          |
| ------------------------------------------------------------------- | ------ | -------------------------------------------------------------------- |
| `AccountType = "AccountType"`                                       | string | Account type identifier                                              |
| `NetLiquidation = "NetLiquidation"`                                 | string | Net liquidation value                                                |
| `TotalCashValue = "TotalCashValue"`                                 | string | Total cash including futures pnl                                     |
| `SettledCash = "SettledCash"`                                       | string | For cash accounts, same as TotalCashValue                            |
| `AccruedCash = "AccruedCash"`                                       | string | Net accrued interest                                                 |
| `BuyingPower = "BuyingPower"`                                       | string | Maximum amount of marginable US stocks the account can buy           |
| `EquityWithLoanValue = "EquityWithLoanValue"`                       | string | Cash + stocks + bonds + mutual funds                                 |
| `PreviousDayEquityWithLoanValue = "PreviousDayEquityWithLoanValue"` | string | Previous day equity with loan value                                  |
| `GrossPositionValue = "GrossPositionValue"`                         | string | Sum of absolute value of all stock and equity option positions       |
| `ReqTEquity = "ReqTEquity"`                                         | string | Required T Equity                                                    |
| `ReqTMargin = "ReqTMargin"`                                         | string | Required T Margin                                                    |
| `SMA = "SMA"`                                                       | string | Special Memorandum Account                                           |
| `InitMarginReq = "InitMarginReq"`                                   | string | Initial margin requirement                                           |
| `MaintMarginReq = "MaintMarginReq"`                                 | string | Maintenance margin requirement                                       |
| `AvailableFunds = "AvailableFunds"`                                 | string | Available funds                                                      |
| `ExcessLiquidity = "ExcessLiquidity"`                               | string | Excess liquidity                                                     |
| `Cushion = "Cushion"`                                               | string | Excess liquidity as percentage of net liquidation value              |
| `FullInitMarginReq = "FullInitMarginReq"`                           | string | Full initial margin requirement                                      |
| `FullMaintMarginReq = "FullMaintMarginReq"`                         | string | Full maintenance margin requirement                                  |
| `FullAvailableFunds = "FullAvailableFunds"`                         | string | Full available funds                                                 |
| `FullExcessLiquidity = "FullExcessLiquidity"`                       | string | Full excess liquidity                                                |
| `LookAheadNextChange = "LookAheadNextChange"`                       | string | Time when look-ahead values take effect                              |
| `LookAheadInitMarginReq = "LookAheadInitMarginReq"`                 | string | Look-ahead initial margin requirement                                |
| `LookAheadMaintMarginReq = "LookAheadMaintMarginReq"`               | string | Look-ahead maintenance margin requirement                            |
| `LookAheadAvailableFunds = "LookAheadAvailableFunds"`               | string | Look-ahead available funds                                           |
| `LookAheadExcessLiquidity = "LookAheadExcessLiquidity"`             | string | Look-ahead excess liquidity                                          |
| `HighestSeverity = "HighestSeverity"`                               | string | Measure of how close account is to liquidation                       |
| `DayTradesRemaining = "DayTradesRemaining"`                         | string | Number of day trades remaining before PDT detection (-1 = unlimited) |
| `Leverage = "Leverage"`                                             | string | GrossPositionValue / NetLiquidation                                  |

### Static Public Member Functions

| Name           | Type          | Description                |
| -------------- | ------------- | -------------------------- |
| `GetAllTags()` | static string | Returns all available tags |

---

## 2.0 Bar Class Reference

<!-- METADATA: scope=historical-bar-data, priority=reference, dependencies=[] -->

**[REFERENCE]** The historical data bar's description.

### 2.1 Public Attributes

| Name     | Type    | Description                                                            |
| -------- | ------- | ---------------------------------------------------------------------- |
| `Time`   | string  | Bar's date and time (yyyymmss hh:mm:ss or system time) - TWS time zone |
| `Open`   | double  | Bar's open price                                                       |
| `High`   | double  | Bar's high price                                                       |
| `Low`    | double  | Bar's low price                                                        |
| `Close`  | double  | Bar's close price                                                      |
| `Volume` | decimal | Bar's traded volume (only available for TRADES)                        |
| `Count`  | int     | Number of trades during bar's timespan (only available for TRADES)     |
| `WAP`    | decimal | Bar's Weighted Average Price (only available for TRADES)               |

---

## 3.0 ComboLeg Class Reference

<!-- METADATA: scope=combo-order-legs, priority=reference, dependencies=[Contract] -->

**[REFERENCE]** Class representing a leg within combo orders.

### 3.1 Public Attributes

| Name                 | Type   | Description                                                                                                                             |
| -------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `ConId`              | int    | Contract's IB unique id                                                                                                                 |
| `Ratio`              | int    | Relative number of contracts for the leg                                                                                                |
| `Action`             | string | Side (BUY/SELL). SSHORT for institutions only                                                                                           |
| `Exchange`           | string | Destination exchange for order routing                                                                                                  |
| `OpenClose`          | int    | Open/close order indicator:<br>0 = Same as parent (retail only)<br>1 = Open (institutional)<br>2 = Close (institutional)<br>3 = Unknown |
| `ShortSaleSlot`      | int    | For stock legs short selling: 1 = clearing broker, 2 = third party                                                                      |
| `DesignatedLocation` | string | When ShortSaleSlot = 2, designated location                                                                                             |
| `ExemptCode`         | int    | Short sale uptick rule: 0 = does not apply, -1 = applies                                                                                |

### Public Member Functions

| Name          | Type       | Description                           |
| ------------- | ---------- | ------------------------------------- |
| `SAME = 0`    | static int | Same as parent security (retail only) |
| `OPEN = 1`    | static int | Open (institutional only)             |
| `CLOSE = 2`   | static int | Close (institutional only)            |
| `UNKNOWN = 3` | static int | Unknown                               |

---

## 4.0 CommissionAndFeesReport Class

<!-- METADATA: scope=commission-fees, priority=reference, dependencies=[] -->

**[REFERENCE]** Commission and fee information for executions.

Class representing commissions and fees generated by an execution.

### Public Attributes

| Name                  | Type   | Description                                   |
| --------------------- | ------ | --------------------------------------------- |
| `ExecId`              | string | Execution's id this commission belongs to     |
| `CommissionAndFees`   | double | Combined cost of commissions and fees         |
| `Currency`            | string | Currency denoting the commissionAndFees value |
| `RealizedPNL`         | double | Realized profit and loss                      |
| `Yield`               | double | Income return                                 |
| `YieldRedemptionDate` | int    | Date in yyyymmdd format                       |

### Public Member Functions

| Name                 | Type          | Description          |
| -------------------- | ------------- | -------------------- |
| `Equals(object obj)` | override bool | Equality comparison  |
| `GetHashCode()`      | override int  | Hash code generation |

---

## 5.0 Contract Class Reference

<!-- METADATA: scope=contract-definition, priority=critical, dependencies=[] -->

**[REQUIRED]** Class describing an instrument's definition.

Class describing an instrument's definition.

### Public Attributes

| Name                           | Type                 | Description                                                                     |
| ------------------------------ | -------------------- | ------------------------------------------------------------------------------- |
| `ConId`                        | int                  | Unique IB contract identifier                                                   |
| `Symbol`                       | string               | Underlying's asset symbol                                                       |
| `SecType`                      | string               | Security type: STK, OPT, FUT, IND, FOP, CASH, BAG, WAR, BOND, CMDTY, NEWS, FUND |
| `LastTradeDateOrContractMonth` | string               | Last trading day or contract month (YYYYMM or YYYYMMDD)                         |
| `LastTradeDate`                | string               | Contract's last trading day                                                     |
| `Strike`                       | double               | Option's strike price                                                           |
| `Right`                        | string               | Put or Call (P, PUT, C, CALL)                                                   |
| `Multiplier`                   | string               | Instrument's multiplier                                                         |
| `Exchange`                     | string               | Destination exchange                                                            |
| `Currency`                     | string               | Underlying's currency                                                           |
| `LocalSymbol`                  | string               | Contract's symbol within primary exchange (OCC symbol for options)              |
| `PrimaryExch`                  | string               | Contract's primary exchange (for smart routed contracts)                        |
| `TradingClass`                 | string               | Trading class name                                                              |
| `IncludeExpired`               | bool                 | Allow queries for expired contracts (futures/options only)                      |
| `SecIdType`                    | string               | Security identifier type (ISIN, CUSIP)                                          |
| `SecId`                        | string               | Security type identifier                                                        |
| `Description`                  | string               | Contract description                                                            |
| `IssuerId`                     | string               | Issuer identifier                                                               |
| `ComboLegsDescription`         | string               | Combo legs description                                                          |
| `ComboLegs`                    | List                 | Combined contract definition legs                                               |
| `DeltaNeutralContract`         | DeltaNeutralContract | Delta and underlying price for Delta-Neutral combos                             |

### Public Member Functions

| Name         | Type            | Description           |
| ------------ | --------------- | --------------------- |
| `ToString()` | override string | String representation |

---

## 6.0 ContractDetails Class Reference

<!-- METADATA: scope=contract-details, priority=reference, dependencies=[Contract] -->

**[REFERENCE]** Extended contract information.

Extended contract details.

### Public Attributes

| Name                 | Type     | Description                                                       |
| -------------------- | -------- | ----------------------------------------------------------------- |
| `Contract`           | Contract | Fully-defined Contract object                                     |
| `MarketName`         | string   | Market name for this product                                      |
| `MinTick`            | double   | Minimum allowed price variation (smallest tick size)              |
| `PriceMagnifier`     | int      | Allows consistent execution and strike prices with market data    |
| `OrderTypes`         | string   | Supported order types for this product                            |
| `ValidExchanges`     | string   | Valid exchange fields when placing orders                         |
| `UnderConId`         | int      | For derivatives, underlying contract id                           |
| `LongName`           | string   | Descriptive name of the product                                   |
| `ContractMonth`      | string   | Contract month of underlying (futures)                            |
| `Industry`           | string   | Industry classification                                           |
| `Category`           | string   | Industry category                                                 |
| `Subcategory`        | string   | Industry subcategory                                              |
| `TimeZoneId`         | string   | Time zone for trading hours                                       |
| `TradingHours`       | string   | Trading hours (current and next day)                              |
| `LiquidHours`        | string   | Liquid hours (regular trading hours)                              |
| `EvRule`             | string   | Economic Value Rule name and optional argument                    |
| `EvMultiplier`       | double   | Market value change approximation per 1 unit price change         |
| `AggGroup`           | int      | Smart-routing group (-1 = cannot be smart-routed)                 |
| `SecIdList`          | List     | Contract identifiers (CUSIP/ISIN/etc.)                            |
| `UnderSymbol`        | string   | For derivatives, underlying symbol                                |
| `UnderSecType`       | string   | For derivatives, underlying security type                         |
| `MarketRuleIds`      | string   | Market rule IDs (separated by comma) for minimum price increments |
| `RealExpirationDate` | string   | Real expiration date (TWS 968+, API v973.04+)                     |
| `LastTradeTime`      | string   | Last trade time                                                   |
| `StockType`          | string   | Stock type                                                        |

#### Bond-Specific Fields

| Name                | Type   | Description                                       |
| ------------------- | ------ | ------------------------------------------------- |
| `Cusip`             | string | Nine-character bond CUSIP (requires subscription) |
| `Ratings`           | string | Credit rating (not currently available via API)   |
| `DescAppend`        | string | Descriptive information about the bond            |
| `BondType`          | string | Type of bond                                      |
| `CouponType`        | string | Type of bond coupon (not currently available)     |
| `Callable`          | bool   | If true, bond is callable                         |
| `Putable`           | bool   | If true, bond is putable                          |
| `Coupon`            | double | Annual interest rate (not currently available)    |
| `Convertible`       | bool   | If true, bond is convertible                      |
| `Maturity`          | string | Bond maturity date (not currently available)      |
| `IssueDate`         | string | Bond issue date (not currently available)         |
| `NextOptionDate`    | string | Next option date for callable/putable bonds       |
| `NextOptionType`    | string | Type of embedded option                           |
| `NextOptionPartial` | bool   | Partial option flag                               |
| `Notes`             | string | Additional bond notes                             |

#### Fund-Specific Fields

| Name                              | Type                            | Description                        |
| --------------------------------- | ------------------------------- | ---------------------------------- |
| `MinSize`                         | decimal                         | Order's minimal size               |
| `SizeIncrement`                   | decimal                         | Order's size increment             |
| `SuggestedSizeIncrement`          | decimal                         | Order's suggested size increment   |
| `FundName`                        | string                          | Fund's name                        |
| `FundFamily`                      | string                          | Fund's family                      |
| `FundType`                        | string                          | Fund's type                        |
| `FundFrontLoad`                   | string                          | Fund's front load                  |
| `FundBackLoad`                    | string                          | Fund's back load                   |
| `FundBackLoadTimeInterval`        | string                          | Fund's back load time interval     |
| `FundManagementFee`               | string                          | Fund's management fee              |
| `FundClosed`                      | bool                            | Fund closed flag                   |
| `FundClosedForNewInvestors`       | bool                            | Fund closed for new investors      |
| `FundClosedForNewMoney`           | bool                            | Fund closed for new money          |
| `FundNotifyAmount`                | string                          | Fund's notify amount               |
| `FundMinimumInitialPurchase`      | string                          | Fund's minimum initial purchase    |
| `FundSubsequentMinimumPurchase`   | string                          | Fund's subsequent minimum purchase |
| `FundBlueSkyStates`               | string                          | Fund's blue sky states             |
| `FundBlueSkyTerritories`          | string                          | Fund's blue sky territories        |
| `FundDistributionPolicyIndicator` | FundDistributionPolicyIndicator | Fund's distribution policy         |
| `FundAssetType`                   | FundAssetType                   | Fund's asset type                  |

---

## 7.0 CodeMsgPair Class Reference

<!-- METADATA: scope=error-codes, priority=reference, dependencies=[] -->

**[REFERENCE]** Class for pairing error codes with messages.

Associates error code and error message as a pair.

### Public Attributes

| Name      | Type   | Description   |
| --------- | ------ | ------------- |
| `Code`    | int    | Error code    |
| `Message` | string | Error message |

---

## 8.0 DeltaNeutralContract Class

<!-- METADATA: scope=delta-neutral-hedging, priority=advanced, dependencies=[Contract] -->

**[ADVANCED]** Delta-Neutral Combo Contract. Used for spread trades.

Delta-Neutral Contract definition.

### Public Attributes

| Name    | Type   | Description                                                  |
| ------- | ------ | ------------------------------------------------------------ |
| `ConId` | int    | Unique contract identifier for delta-neutral combo contracts |
| `Delta` | double | Underlying stock or future delta                             |
| `Price` | double | Price of the underlying                                      |

---

## 9.0 EClient Class Reference

<!-- METADATA: scope=request-methods, priority=critical, dependencies=[] -->

**[REQUEST]** **[CRITICAL]** The EClient class is used to send requests to TWS/Gateway.

TWS/Gateway client class. This client class contains all available methods to communicate with IB. Up to 32 clients can connect to a single TWS/Gateway instance simultaneously.

### Public Attributes

| Name                   | Type   | Description                  |
| ---------------------- | ------ | ---------------------------- |
| `AllowRedirect`        | bool   | Allow connection redirection |
| `ServerTime`           | string | Server time                  |
| `optionalCapabilities` | string | Optional capabilities        |
| `AsyncEConnect`        | bool   | Asynchronous connection mode |
| `ServerVersion`        | int    | Host's version number        |

### Key Public Member Functions

#### Connection Management

| Method                      | Description                                             |
| --------------------------- | ------------------------------------------------------- |
| `SetConnectOptions(string)` | Internal use only                                       |
| `DisableUseV100Plus()`      | Switch between V100+ and previous connection mechanisms |
| `IsConnected()`             | Check if API-TWS connection is active                   |
| `startApi()`                | Initiate message exchange with TWS/Gateway              |
| `Close()`                   | Terminate connection and notify EWrapper                |
| `eDisconnect(bool)`         | Close socket and terminate thread                       |

#### Market Data

| Method                      | Description                                      |
| --------------------------- | ------------------------------------------------ |
| `reqMktData(...)`           | Request real-time market data                    |
| `cancelMktData(int)`        | Cancel market data subscription                  |
| `reqMarketDataType(int)`    | Switch between real-time and delayed/frozen data |
| `reqMktDepth(...)`          | Request market depth (Level 2)                   |
| `cancelMktDepth(...)`       | Cancel market depth subscription                 |
| `reqHistoricalData(...)`    | Request historical data bars                     |
| `cancelHistoricalData(int)` | Cancel historical data request                   |
| `reqRealTimeBars(...)`      | Request 5-second real-time bars                  |
| `cancelRealTimeBars(int)`   | Cancel real-time bars                            |
| `reqTickByTickData(...)`    | Request tick-by-tick data                        |
| `cancelTickByTickData(int)` | Cancel tick-by-tick data                         |
| `reqHistoricalTicks(...)`   | Request historical tick data                     |
| `reqHeadTimestamp(...)`     | Request earliest available data point            |
| `cancelHeadTimestamp(int)`  | Cancel head timestamp request                    |

#### Account & Portfolio

| Method                      | Description                         |
| --------------------------- | ----------------------------------- |
| `reqAccountSummary(...)`    | Subscribe to account summary        |
| `cancelAccountSummary(int)` | Cancel account summary subscription |
| `reqAccountUpdates(...)`    | Subscribe to account updates        |
| `reqPositions()`            | Subscribe to position updates       |
| `cancelPositions()`         | Cancel positions subscription       |
| `reqPnL(...)`               | Request account-level P&L           |
| `cancelPnL(int)`            | Cancel P&L subscription             |
| `reqPnLSingle(...)`         | Request position-level P&L          |
| `cancelPnLSingle(int)`      | Cancel single position P&L          |
| `reqManagedAccts()`         | Request managed accounts list       |

#### Orders

| Method                     | Description                         |
| -------------------------- | ----------------------------------- |
| `placeOrder(...)`          | Place or modify an order            |
| `cancelOrder(...)`         | Cancel an order                     |
| `reqGlobalCancel()`        | Cancel ALL open orders              |
| `reqOpenOrders()`          | Request open orders for this client |
| `reqAllOpenOrders()`       | Request all open orders             |
| `reqAutoOpenOrders(bool)`  | Auto-bind future TWS orders         |
| `reqCompletedOrders(bool)` | Request completed orders            |
| `exerciseOptions(...)`     | Exercise an options contract        |

#### Contract & Instruments

| Method                    | Description                            |
| ------------------------- | -------------------------------------- |
| `reqContractDetails(...)` | Request contract details               |
| `reqSecDefOptParams(...)` | Request option chain parameters        |
| `reqMatchingSymbols(...)` | Search for matching symbols            |
| `reqMarketRule(int)`      | Request market rule (price increments) |

#### News

| Method                   | Description                      |
| ------------------------ | -------------------------------- |
| `reqNewsProviders()`     | Request available news providers |
| `reqNewsArticle(...)`    | Request specific news article    |
| `reqHistoricalNews(...)` | Request historical news          |

#### Executions & Commissions

| Method               | Description               |
| -------------------- | ------------------------- |
| `reqExecutions(...)` | Request execution details |

#### Scanners

| Method                           | Description                    |
| -------------------------------- | ------------------------------ |
| `reqScannerParameters()`         | Request scanner parameters XML |
| `reqScannerSubscription(...)`    | Subscribe to market scanner    |
| `cancelScannerSubscription(int)` | Cancel scanner subscription    |

#### Financial Advisors

| Method           | Description              |
| ---------------- | ------------------------ |
| `requestFA(int)` | Request FA configuration |
| `replaceFA(...)` | Replace FA configuration |

#### Calculations

| Method                                  | Description                         |
| --------------------------------------- | ----------------------------------- |
| `calculateImpliedVolatility(...)`       | Calculate option implied volatility |
| `cancelCalculateImpliedVolatility(int)` | Cancel IV calculation               |
| `calculateOptionPrice(...)`             | Calculate option price              |
| `cancelCalculateOptionPrice(int)`       | Cancel option price calculation     |

#### Miscellaneous

| Method                   | Description                        |
| ------------------------ | ---------------------------------- |
| `reqCurrentTime()`       | Request TWS current time           |
| `reqIds(int)`            | Request next valid order ID        |
| `setServerLogLevel(int)` | Change TWS/Gateway log level (1-5) |
| `reqNewsBulletins(bool)` | Subscribe to IB news bulletins     |
| `cancelNewsBulletin()`   | Cancel news bulletin subscription  |

### Protected Member Functions

| Method                        | Description                         |
| ----------------------------- | ----------------------------------- |
| `prepareBuffer(BinaryWriter)` | Prepare message buffer              |
| `sendConnectRequest()`        | Send connection request             |
| `CheckServerVersion(...)`     | Verify server version compatibility |
| `CloseAndSend(...)`           | Close and send message              |
| `CheckConnection()`           | Check connection status             |
| `ReportError(...)`            | Report error to wrapper             |
| `ReportUpdateTWS(...)`        | Report TWS update needed            |
| `SendCancelRequest(...)`      | Send cancellation request           |
| `VerifyOrderContract(...)`    | Verify order contract               |
| `VerifyOrder(...)`            | Verify order parameters             |

### Protected Attributes

| Name              | Type          | Description            |
| ----------------- | ------------- | ---------------------- |
| `serverVersion`   | int           | Server version number  |
| `socketTransport` | ETransport    | Socket transport layer |
| `wrapper`         | EWrapper      | Wrapper implementation |
| `isConnected`     | volatile bool | Connection status      |
| `clientId`        | int           | Client identifier      |
| `extraAuth`       | bool          | Extra authentication   |
| `useV100Plus`     | bool          | Use V100+ protocol     |
| `allowRedirect`   | bool          | Allow redirection      |
| `tcpStream`       | Stream        | TCP stream             |

---

## 10.0 EClientSocket Class Reference

<!-- METADATA: scope=socket-connection, priority=critical, dependencies=[EClient] -->

**[CRITICAL]** Socket-based connection to TWS/Gateway.

TWS/Gateway client class extending EClient. Up to 32 clients can connect to a single TWS/Gateway instance.

### Public Member Functions

| Method                       | Description                           |
| ---------------------------- | ------------------------------------- |
| `serverVersion(int, string)` | Handle server version callback        |
| `eConnect(string, int, int)` | Connect to TWS/Gateway                |
| `redirect(string)`           | Redirect connection to different host |
| `eDisconnect(bool)`          | Close socket and terminate thread     |

### Protected Member Functions

| Method                             | Description            |
| ---------------------------------- | ---------------------- |
| `createClientStream(string, int)`  | Create client stream   |
| `prepareBuffer(BinaryWriter)`      | Prepare message buffer |
| `CloseAndSend(BinaryWriter, uint)` | Close and send message |

---

## 11.0 EReader Class Reference

<!-- METADATA: scope=message-queue, priority=advanced, dependencies=[EClient] -->

**[PERFORMANCE]** The EReader handles incoming messages in a separate thread.

Captures incoming messages from API and places them into a queue.

### Public Member Functions

| Method                | Description             |
| --------------------- | ----------------------- |
| `Start()`             | Start reading messages  |
| `processMsgs()`       | Process queued messages |
| `putMessageToQueue()` | Add message to queue    |

---

## 12.0 EReaderSignal Interface

<!-- METADATA: scope=thread-signaling, priority=advanced, dependencies=[EReader] -->

**[THREAD-SAFETY]** Interface for signaling message availability between threads.

Notifies the reading thread when messages are ready to be consumed. Not currently used in Python API.

### Public Member Functions

| Method            | Description                       |
| ----------------- | --------------------------------- |
| `issueSignal()`   | Issue signal when data available  |
| `waitForSignal()` | Wait for signal before processing |

---

## 13.0 EWrapper Interface Reference

<!-- METADATA: scope=callback-methods, priority=critical, dependencies=[] -->

**[CALLBACK]** **[CRITICAL]** The EWrapper interface receives callbacks from TWS/Gateway.

Interface for TWS/Gateway to communicate with API client. Every API client must implement this interface to handle all events generated by TWS/Gateway.

### Key Callback Methods

#### Error Handling

| Method                    | Description                                  |
| ------------------------- | -------------------------------------------- |
| `error(Exception)`        | Handle API internal errors/exceptions        |
| `error(string)`           | Handle error string                          |
| `error(int, int, string)` | Handle errors with request ID and error code |

#### Connection & System

| Method                    | Description                       |
| ------------------------- | --------------------------------- |
| `connectAck()`            | Acknowledge connection attempt    |
| `connectionClosed()`      | Socket connection closed callback |
| `currentTime(long)`       | Receive TWS current time          |
| `nextValidId(int)`        | Receive next valid order ID       |
| `managedAccounts(string)` | Receive managed accounts list     |

#### Market Data

| Method                                    | Description                    |
| ----------------------------------------- | ------------------------------ |
| `tickPrice(int, int, double, TickAttrib)` | Receive price tick             |
| `tickSize(int, int, decimal)`             | Receive size tick              |
| `tickString(int, int, string)`            | Receive string tick            |
| `tickGeneric(int, int, double)`           | Receive generic tick           |
| `tickEFP(...)`                            | Receive EFP tick               |
| `tickSnapshotEnd(int)`                    | Market data snapshot completed |
| `marketDataType(int, int)`                | Market data type notification  |
| `tickByTickAllLast(...)`                  | Tick-by-tick last trade        |
| `tickByTickBidAsk(...)`                   | Tick-by-tick bid/ask           |
| `tickByTickMidPoint(...)`                 | Tick-by-tick midpoint          |

#### Historical Data

| Method                                   | Description                       |
| ---------------------------------------- | --------------------------------- |
| `historicalData(int, Bar)`               | Receive historical bar            |
| `historicalDataUpdate(int, Bar)`         | Historical bar update             |
| `historicalDataEnd(int, string, string)` | Historical data completed         |
| `historicalTicks(...)`                   | Receive historical ticks          |
| `historicalTicksBidAsk(...)`             | Historical bid/ask ticks          |
| `historicalTicksLast(...)`               | Historical last ticks             |
| `headTimestamp(int, string)`             | Earliest available data timestamp |
| `histogramData(int, HistogramEntry[])`   | Histogram data                    |
| `historicalSchedule(...)`                | Historical schedule               |

#### Real-Time Bars

| Method             | Description          |
| ------------------ | -------------------- |
| `realtimeBar(...)` | Receive 5-second bar |

#### Market Depth

| Method                  | Description                 |
| ----------------------- | --------------------------- |
| `updateMktDepth(...)`   | Level 2 market depth update |
| `updateMktDepthL2(...)` | Level 2 market maker update |

#### Account & Portfolio

| Method                       | Description                     |
| ---------------------------- | ------------------------------- |
| `accountSummary(...)`        | Account summary value           |
| `accountSummaryEnd(int)`     | Account summary completed       |
| `updateAccountValue(...)`    | Account value update            |
| `updatePortfolio(...)`       | Portfolio position update       |
| `updateAccountTime(string)`  | Account update timestamp        |
| `accountDownloadEnd(string)` | Account data download completed |
| `position(...)`              | Position data                   |
| `positionEnd()`              | All positions transmitted       |
| `pnl(...)`                   | Account P&L                     |
| `pnlSingle(...)`             | Single position P&L             |

#### Orders

| Method                 | Description                      |
| ---------------------- | -------------------------------- |
| `orderStatus(...)`     | Order status update              |
| `openOrder(...)`       | Open order details               |
| `openOrderEnd()`       | All open orders transmitted      |
| `completedOrder(...)`  | Completed order details          |
| `completedOrdersEnd()` | All completed orders transmitted |
| `orderBound(...)`      | Order binding notification       |

#### Executions

| Method                               | Description                |
| ------------------------------------ | -------------------------- |
| `execDetails(...)`                   | Execution details          |
| `execDetailsEnd(int)`                | All executions transmitted |
| `commissionReport(CommissionReport)` | Commission report          |

#### Contract Details

| Method                                      | Description                      |
| ------------------------------------------- | -------------------------------- |
| `contractDetails(int, ContractDetails)`     | Contract details                 |
| `bondContractDetails(int, ContractDetails)` | Bond contract details            |
| `contractDetailsEnd(int)`                   | All contract details transmitted |
| `symbolSamples(...)`                        | Symbol search results            |

#### Options

| Method                                      | Description                 |
| ------------------------------------------- | --------------------------- |
| `tickOptionComputation(...)`                | Option Greeks computation   |
| `deltaNeutralValidation(...)`               | Delta-neutral validation    |
| `securityDefinitionOptionParameter(...)`    | Option chain parameters     |
| `securityDefinitionOptionParameterEnd(int)` | Option parameters completed |

#### News

| Method                          | Description               |
| ------------------------------- | ------------------------- |
| `tickNews(...)`                 | News tick                 |
| `newsProviders(NewsProvider[])` | Available news providers  |
| `newsArticle(...)`              | News article content      |
| `historicalNews(...)`           | Historical news headline  |
| `historicalNewsEnd(...)`        | Historical news completed |
| `updateNewsBulletin(...)`       | IB news bulletin          |

#### Market Scanner

| Method                      | Description               |
| --------------------------- | ------------------------- |
| `scannerParameters(string)` | Scanner parameters XML    |
| `scannerData(...)`          | Scanner result row        |
| `scannerDataEnd(int)`       | Scanner results completed |

#### Financial Advisor

| Method              | Description              |
| ------------------- | ------------------------ |
| `receiveFA(...)`    | FA configuration data    |
| `replaceFAEnd(...)` | FA replacement completed |

#### Fundamental Data

| Method                         | Description      |
| ------------------------------ | ---------------- |
| `fundamentalData(int, string)` | Fundamental data |

#### Display Groups

| Method                     | Description              |
| -------------------------- | ------------------------ |
| `displayGroupList(...)`    | Available display groups |
| `displayGroupUpdated(...)` | Display group updated    |

#### Account Multi

| Method                       | Description                       |
| ---------------------------- | --------------------------------- |
| `accountUpdateMulti(...)`    | Multi-account update              |
| `accountUpdateMultiEnd(int)` | Multi-account updates completed   |
| `positionMulti(...)`         | Multi-account position            |
| `positionMultiEnd(int)`      | Multi-account positions completed |

#### Miscellaneous

| Method                         | Description                     |
| ------------------------------ | ------------------------------- |
| `softDollarTiers(...)`         | Soft dollar tiers               |
| `familyCodes(FamilyCode[])`    | Family codes                    |
| `mktDepthExchanges(...)`       | Market depth exchanges          |
| `tickReqParams(...)`           | Tick request parameters         |
| `smartComponents(...)`         | Smart components mapping        |
| `marketRule(...)`              | Market rule price increments    |
| `rerouteMktDataReq(...)`       | CFD market data reroute         |
| `rerouteMktDepthReq(...)`      | CFD market depth reroute        |
| `wshMetaData(...)`             | Wall Street Horizon metadata    |
| `wshEventData(...)`            | Wall Street Horizon event data  |
| `userInfo(...)`                | User white branding info        |
| `verifyMessageAPI(string)`     | API verification message        |
| `verifyCompleted(...)`         | Verification completed          |
| `verifyAndAuthMessageAPI(...)` | Verification and auth message   |
| `verifyAndAuthCompleted(...)`  | Verification and auth completed |

---

## 14.0 Quick Reference Cards

### EClient Methods by Category

| Category        | Common Methods                                           | Use Case                      |
| --------------- | -------------------------------------------------------- | ----------------------------- |
| **Connection**  | `connect()`, `disconnect()`, `isConnected()`             | Establish/close connection    |
| **Market Data** | `reqMktData()`, `cancelMktData()`, `reqHistoricalData()` | Real-time & historical prices |
| **Orders**      | `placeOrder()`, `cancelOrder()`, `reqOpenOrders()`       | Order management              |
| **Account**     | `reqAccountSummary()`, `reqPositions()`, `reqPnL()`      | Account monitoring            |
| **Contract**    | `reqContractDetails()`, `reqMatchingSymbols()`           | Contract lookup               |

### EWrapper Callbacks by Event Type

| Event Type      | Key Callbacks                                    | Triggered By              |
| --------------- | ------------------------------------------------ | ------------------------- |
| **Connection**  | `nextValidId()`, `error()`, `connectionClosed()` | Connection state changes  |
| **Market Data** | `tickPrice()`, `tickSize()`, `historicalData()`  | Market data subscriptions |
| **Orders**      | `orderStatus()`, `openOrder()`, `execDetails()`  | Order state changes       |
| **Account**     | `accountSummary()`, `position()`, `pnl()`        | Account updates           |
| **Errors**      | `error()`                                        | Any error condition       |

### Contract Definition Examples

**[EXAMPLE]** Stock contract:

```python
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"
```

**[EXAMPLE]** Option contract:

```python
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "OPT"
contract.exchange = "SMART"
contract.currency = "USD"
contract.lastTradeDateOrContractMonth = "20240119"  # YYYYMMDD
contract.strike = 150.0
contract.right = "C"  # Call
contract.multiplier = "100"
```

**[EXAMPLE]** Future contract:

```python
contract = Contract()
contract.symbol = "ES"
contract.secType = "FUT"
contract.exchange = "CME"
contract.currency = "USD"
contract.lastTradeDateOrContractMonth = "202403"  # YYYYMM
```

---

## 15.0 Next Steps

**[WORKFLOW]** Continue to related references:

- **[Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** - `Order` class (100+ parameters), order types, TIF options
- **[Executions & Data](./03-API-REFERENCE-EXECUTIONS.md)** - Trade data structures, tick types, historical data
- **[Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Conditional order triggers (price, time, margin, volume)
- **[Data Types](./05-API-REFERENCE-DATA-TYPES.md)** - Helper classes and data structures

**[WORKFLOW]** Implementation guides:

- **[Setup Guide](./06-SETUP-GUIDE.md)** - Installation and configuration
- **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection patterns, threading, error handling
- **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** - Request market data _(Coming Soon)_
- **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** - Place and manage orders _(Coming Soon)_

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index

---

**[REFERENCE]** External resources:

- [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)
- [TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)

---

**Referenced by:**

- [Main Navigation](./README.md#11-api-reference-classes--methods) - Core API Classes (Ref-01)
- [Setup Guide](./06-SETUP-GUIDE.md) - EClient/EWrapper basics
- [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) - Threading patterns with EClient/EWrapper
