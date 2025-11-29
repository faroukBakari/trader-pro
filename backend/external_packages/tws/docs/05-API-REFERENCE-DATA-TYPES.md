# TWS API Reference - Data Types & Helper Classes

<!-- METADATA: scope=helper-data-types, priority=reference, dependencies=[01-CLASSES] -->

> **Source:** [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)  
> **Last Updated:** November 19, 2025

This document contains comprehensive reference information for TWS API data types and helper classes.

**[REFERENCE]** Complete technical reference for helper classes, market data structures, and utility types.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section     | Class/Type                                                   | Purpose      | Jump To             |
| ----------- | ------------------------------------------------------------ | ------------ | ------------------- |
| **1.0**     | [DepthMktDataDescription](#10-depthmktdatadescription-class) | Market Depth | Exchange depth data |
| **2.0**     | [FamilyCode](#20-familycode-class)                           | Contract     | Contract families   |
| **3.0**     | [HistogramEntry](#30-histogramentry-class)                   | Data         | Price distribution  |
| **4.0**     | [NewsProvider](#40-newsprovider-class)                       | News         | News feeds          |
| **5.0**     | [PriceIncrement](#50-priceincrement-class)                   | Trading      | Tick size rules     |
| **6.0**     | [SmartComponent](#60-smartcomponent-class)                   | Routing      | Smart routing       |
| **7.0**     | [WshEventData](#70-wsheventdata-class)                       | Calendar     | Corporate events    |
| **8.0**     | [Helper Functions](#80-helper-functions--constants)          | Utility      | Encoding/decoding   |
| **9.0**     | [Common Patterns](#90-common-data-patterns)                  | Reference    | Data conventions    |
| **Related** | [Main Navigation](./README.md)                               | -            | Back to index       |
| **Related** | [Core Classes](./01-API-REFERENCE-CLASSES.md)                | -            | EClient, EWrapper   |

---

## Table of Contents

- [1.0 DepthMktDataDescription Class](#10-depthmktdatadescription-class)
- [2.0 FamilyCode Class](#20-familycode-class)
- [3.0 HistogramEntry Class](#30-histogramentry-class)
- [4.0 NewsProvider Class](#40-newsprovider-class)
- [5.0 PriceIncrement Class](#50-priceincrement-class)
- [6.0 SmartComponent Class](#60-smartcomponent-class)
- [7.0 WshEventData Class](#70-wsheventdata-class)
- [8.0 Helper Functions & Constants](#80-helper-functions--constants)
- [9.0 Common Data Patterns](#90-common-data-patterns)
- [10.0 Next Steps](#100-next-steps)

---

## 1.0 DepthMktDataDescription Class

<!-- METADATA: scope=market-depth-exchanges, priority=reference, dependencies=[] -->

**[REFERENCE]** Describes available market depth exchanges for a contract.

### 1.1 Public Attributes

| Name              | Type   | Description                                              |
| ----------------- | ------ | -------------------------------------------------------- |
| `Exchange`        | string | Exchange offering market depth data                      |
| `SecType`         | string | Security type at this exchange                           |
| `ListingExch`     | string | Exchange where contract is listed (if different)         |
| `ServiceDataType` | string | Type of market depth service (typically "Deep", "Deep2") |
| `AggGroup`        | int    | Aggregation group (if applicable)                        |

### Example

```python
# Market depth description for AAPL on NASDAQ
depth_desc = DepthMktDataDescription()
depth_desc.Exchange = "NASDAQ"
depth_desc.SecType = "STK"
depth_desc.ServiceDataType = "Deep"
```

---

## 2.0 FamilyCode Class

<!-- METADATA: scope=contract-families, priority=reference, dependencies=[] -->

**[REFERENCE]** Represents a contract family (options/futures with same underlying).

### 2.1 Public Attributes

| Name            | Type   | Description                     |
| --------------- | ------ | ------------------------------- |
| `AccountID`     | string | Account to which family applies |
| `FamilyCodeStr` | string | Family code identifier          |

### Example

```python
# Family code for index options
family = FamilyCode()
family.AccountID = "DU123456"
family.FamilyCodeStr = "SPX"  # S&P 500 Index options
```

---

## 3.0 HistogramEntry Class

<!-- METADATA: scope=price-histogram, priority=reference, dependencies=[] -->

**[REFERENCE]** Single entry in a price histogram for an instrument.

### 3.1 Public Attributes

| Name    | Type    | Description                |
| ------- | ------- | -------------------------- |
| `Price` | double  | Price level                |
| `Size`  | decimal | Volume at this price level |

### Usage Context

Used with `EClient.reqHistogramData()` and `EWrapper.histogramData()` to analyze price distribution.

### Example

```python
# Histogram showing volume distribution
entry = HistogramEntry()
entry.Price = 150.50
entry.Size = 125000  # 125K shares traded at this price
```

---

## 4.0 NewsProvider Class

<!-- METADATA: scope=news-providers, priority=reference, dependencies=[] -->

**[REFERENCE]** Describes a news provider available through the API.

### 4.1 Public Attributes

| Name   | Type   | Description                                            |
| ------ | ------ | ------------------------------------------------------ |
| `Code` | string | News provider code (e.g., "BRFUPDN", "DJNL")           |
| `Name` | string | News provider name (e.g., "Briefing.com", "Dow Jones") |

### Common News Providers

| Code           | Name                 |
| -------------- | -------------------- |
| `BRFG`         | Briefing General     |
| `BRFUPDN`      | Briefing Update      |
| `DJNL`         | Dow Jones Newsletter |
| `FLY`          | FlyOnTheWall         |
| `MT_NEWSWIRES` | MT Newswires         |

### Example

```python
# News provider configuration
provider = NewsProvider()
provider.Code = "DJNL"
provider.Name = "Dow Jones Newsletter"
```

---

## 5.0 PriceIncrement Class

<!-- METADATA: scope=tick-size-rules, priority=reference, dependencies=[] -->

**[REFERENCE]** Describes price increment rules for an order type on a contract.

### 5.1 Public Attributes

| Name        | Type   | Description                               |
| ----------- | ------ | ----------------------------------------- |
| `LowEdge`   | double | Lower price bound for this increment      |
| `Increment` | double | Minimum price increment within this range |

### Usage Context

Some exchanges have different tick sizes for different price ranges. This class defines those ranges.

### Example

```python
# Price increment rules for a stock
# $0.01 increments for prices >= $1.00
increment1 = PriceIncrement()
increment1.LowEdge = 1.00
increment1.Increment = 0.01

# $0.0001 increments for prices < $1.00
increment2 = PriceIncrement()
increment2.LowEdge = 0.0
increment2.Increment = 0.0001
```

---

## 6.0 SmartComponent Class

<!-- METADATA: scope=smart-routing-components, priority=reference, dependencies=[] -->

**[REFERENCE]** Describes a component of a smart-routed order's execution.

### 6.1 Public Attributes

| Name             | Type   | Description                       |
| ---------------- | ------ | --------------------------------- |
| `BitNumber`      | int    | Bit position in smart routing map |
| `Exchange`       | string | Exchange identifier               |
| `ExchangeLetter` | char   | Single-character exchange code    |

### Usage Context

Used with `EClient.reqSmartComponents()` to understand how smart-routed orders are broken across exchanges.

### Example

```python
# Smart component for NASDAQ routing
component = SmartComponent()
component.BitNumber = 1
component.Exchange = "NASDAQ"
component.ExchangeLetter = 'Q'
```

---

## 7.0 WshEventData Class

<!-- METADATA: scope=calendar-events, priority=reference, dependencies=[] -->

**[REFERENCE]** Contains data for a calendar event from the Wall Street Horizon feed.

### 7.1 Public Attributes

| Name              | Type   | Description                             |
| ----------------- | ------ | --------------------------------------- |
| `ConId`           | int    | Contract ID for the event               |
| `FillWatchlist`   | bool   | Whether event should populate watchlist |
| `FillPortfolio`   | bool   | Whether event should populate portfolio |
| `FillCompetitors` | bool   | Whether to include competitor events    |
| `StartDate`       | string | Event start date (YYYYMMDD format)      |
| `EndDate`         | string | Event end date (YYYYMMDD format)        |
| `TotalLimit`      | int    | Maximum total events to return          |

### Event Types

Wall Street Horizon provides corporate events including:

- Earnings announcements
- Dividend dates (ex-date, payment date)
- Stock splits
- FDA announcements
- Corporate actions

### Example

```python
# Request earnings events for AAPL
wsh_data = WshEventData()
wsh_data.ConId = 265598  # AAPL
wsh_data.FillWatchlist = True
wsh_data.FillPortfolio = False
wsh_data.FillCompetitors = False
wsh_data.StartDate = "20231201"
wsh_data.EndDate = "20231231"
wsh_data.TotalLimit = 10

# Use with EClient.reqWshMetaData() and EClient.reqWshEventData()
```

---

## 8.0 Helper Functions & Constants

<!-- METADATA: scope=utility-functions, priority=reference, dependencies=[] -->

### 8.1 OrderDecoder

**[UTILITY]** Utility class for decoding order fields from API messages (internal use).

### 8.2 Util Class

**[UTILITY]** Contains utility functions for encoding/decoding API messages (internal use).

**Key Methods:**

- `IntMaxString(int value)` - Converts int to string, handling max values
- `DoubleMaxString(double value)` - Converts double to string, handling max values
- `UnixMillisecondsToString(long milliseconds, string format)` - Converts Unix time to formatted string

---

## 9.0 Common Data Patterns

<!-- METADATA: scope=data-conventions, priority=reference, dependencies=[] -->

### 9.1 Price & Size Representation

**[PATTERN]** Data type conventions:

- **Prices:** `double` type, typically to 2-4 decimal places
- **Sizes:** `decimal` type for precise quantity representation
- **Volume:** `int` or `long` for whole share quantities

### 9.2 Time Representation

**[PATTERN]** Time format conventions:

- **Unix Time:** `long` milliseconds since epoch (1970-01-01 00:00:00 UTC)
- **Formatted Time:** `string` in format `yyyymmdd HH:mm:ss {TZ}`
- **Date Only:** `string` in format `yyyymmdd` or `int` YYYYMMDD

### 9.3 Contract Identification

**[PATTERN]** Contract lookup methods:

- **ConId:** `int` unique contract identifier across all IB systems
- **Symbol + SecType + Exchange:** Alternative identification method
- **LocalSymbol:** Exchange-specific symbol notation

---

## 10.0 Next Steps

**[WORKFLOW]** Continue to related references:

- **[Core Classes](./01-API-REFERENCE-CLASSES.md)** - EClient, EWrapper, Contract
- **[Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** - Order class
- **[Executions & Data](./03-API-REFERENCE-EXECUTIONS.md)** - Execution reporting
- **[Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Conditional orders

**[WORKFLOW]** Implementation guides:

- **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** - Market data subscriptions _(Coming Soon)_
- **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection patterns
- **[Setup Guide](./06-SETUP-GUIDE.md)** - Installation

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index

---

**[REFERENCE]** External resources:

- [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)
- [TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)

---

**Referenced by:**

- [Main Navigation](./README.md#11-api-reference-classes--methods) - Data Types (Ref-05)
- [Core Classes](./01-API-REFERENCE-CLASSES.md) - Helper classes usage
