# Interactive Brokers TWS API Documentation

<!-- METADATA: scope=navigation-hub, priority=critical, dependencies=[] -->

> **Offline Documentation Collection**  
> **Source:** [TWS API Campus](https://ibkrcampus.com/campus/ibkr-api-page/)  
> **Last Updated:** November 26, 2025  
> **API Version:** 10.37.02

Complete offline reference documentation for developing applications with the Interactive Brokers TWS API for Python.

**[DECISION]**: Created offline documentation from TWS API Campus [enables development without internet dependency] [rejected: relying on online docs only] [Nov 2025]

---

## 📑 Quick Navigation - Cross-Reference Table

| Section      | Document                                                     | Purpose                          | Jump To                                    |
| ------------ | ------------------------------------------------------------ | -------------------------------- | ------------------------------------------ |
| **1.0**      | [Documentation Structure](#10-documentation-structure)       | Overview of all guides           | This file                                  |
| **2.0**      | [Quick Start](#20-quick-start)                               | First connection example         | This file                                  |
| **3.0**      | [Learning Paths](#30-learning-paths)                         | Guided learning sequences        | This file                                  |
| **4.0**      | [Common Tasks](#40-common-tasks)                             | Task-based quick reference       | This file                                  |
| **5.0**      | [API Reference Quick Links](#50-api-reference-quick-links)   | Jump to specific classes         | This file                                  |
| **6.0**      | [Cheat Sheets](#60-cheat-sheets)                             | Ports, errors, order types       | This file                                  |
| **7.0**      | [Code Examples](#70-code-examples)                           | Working code snippets            | This file                                  |
| **8.0**      | [Support & Resources](#80-support--resources)                | Help and troubleshooting         | This file                                  |
| **Ref-01**   | [Core API Classes](./01-API-REFERENCE-CLASSES.md)            | EClient, EWrapper, Contract      | [§1.1](#11-api-reference-classes--methods) |
| **Ref-02**   | [Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md) | Order class (100+ params)        | [§1.1](#11-api-reference-classes--methods) |
| **Ref-03**   | [Executions & Data](./03-API-REFERENCE-EXECUTIONS.md)        | Trade data structures            | [§1.1](#11-api-reference-classes--methods) |
| **Ref-04**   | [Conditions](./04-API-REFERENCE-CONDITIONS.md)               | Conditional orders               | [§1.1](#11-api-reference-classes--methods) |
| **Ref-05**   | [Data Types](./05-API-REFERENCE-DATA-TYPES.md)               | Helper classes                   | [§1.1](#11-api-reference-classes--methods) |
| **Guide-06** | [Setup Guide](./06-SETUP-GUIDE.md)                           | [CRITICAL] Installation & config | [§1.2](#12-implementation-guides)          |
| **Guide-07** | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)             | [CRITICAL] Connection management | [§1.2](#12-implementation-guides)          |
| **Ref-Tick** | [Generic Tick List](./TWS-GENERIC-TICK-LIST.md)              | genericTickList parameter ref    | [§1.1](#11-api-reference-classes--methods) |

---

## 1.0 Documentation Structure

This documentation is organized into three main sections:

### 1. API Reference (Classes & Methods)

Complete technical reference for all TWS API classes, methods, attributes, and data types.

| Document                                                                           | Description                                                                                                                               |
| ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **[01-API-REFERENCE-CLASSES.md](./01-API-REFERENCE-CLASSES.md)**                   | Core API classes: `EClient`, `EWrapper`, `Contract`, `ContractDetails`, `Bar`, Account structures                                         |
| **[02-API-REFERENCE-CONTRACTS-ORDERS.md](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** | Order and contract classes: `Order` (100+ attributes), `Execution`, `OrderState`, `ScannerSubscription`                                   |
| **[03-API-REFERENCE-EXECUTIONS.md](./03-API-REFERENCE-EXECUTIONS.md)**             | Trade data structures: `CommissionAndFeesReport`, `Liquidity`, Historical ticks, Tick attributes                                          |
| **[04-API-REFERENCE-CONDITIONS.md](./04-API-REFERENCE-CONDITIONS.md)**             | Order conditions: `PriceCondition`, `TimeCondition`, `MarginCondition`, `ExecutionCondition`, `VolumeCondition`, `PercentChangeCondition` |
| **[05-API-REFERENCE-DATA-TYPES.md](./05-API-REFERENCE-DATA-TYPES.md)**             | Helper classes: `DepthMktDataDescription`, `NewsProvider`, `PriceIncrement`, `SmartComponent`, `WshEventData`                             |
| **[TWS-GENERIC-TICK-LIST.md](./TWS-GENERIC-TICK-LIST.md)**                         | Complete reference for `genericTickList` parameter: tick types, `mdoff` prefix, news sources                                              |

### 2. Implementation Guides

Step-by-step guides for implementing common TWS API workflows.

| Document                                                             | Description                                                                        |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **[06-SETUP-GUIDE.md](./06-SETUP-GUIDE.md)**                         | Installation, configuration, TWS/Gateway setup, verification steps                 |
| **[07-CONNECTIVITY-GUIDE.md](./07-CONNECTIVITY-GUIDE.md)**           | Connection patterns, threading models (sync/async), error handling, auto-reconnect |
| **[08-MARKET-DATA-GUIDE.md](./08-MARKET-DATA-GUIDE.md)**             | Real-time data, historical data, market depth, tick types _(Coming Soon)_          |
| **[09-ORDER-MANAGEMENT-GUIDE.md](./09-ORDER-MANAGEMENT-GUIDE.md)**   | Order placement, modification, cancellation, status tracking _(Coming Soon)_       |
| **[10-ACCOUNT-PORTFOLIO-GUIDE.md](./10-ACCOUNT-PORTFOLIO-GUIDE.md)** | Account updates, positions, P&L, executions _(Coming Soon)_                        |
| **[11-ADVANCED-TOPICS.md](./11-ADVANCED-TOPICS.md)**                 | Financial advisors, scanners, news, complex strategies _(Coming Soon)_             |

### 3. External Resources

- **[TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)** - Online API reference (requires internet)
- **[TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)** - Online implementation guides (requires internet)
- **[TWS API GitHub](https://github.com/InteractiveBrokers/tws-api-public)** - Official API source code
- **[IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)** - Support articles

---

## 1.0 Documentation Structure

<!-- METADATA: scope=documentation-overview, priority=high, dependencies=[] -->

This documentation is organized into three main sections:

### 1.1 API Reference (Classes & Methods)

**[REFERENCE]** Complete technical reference for all TWS API classes, methods, attributes, and data types.

| Section    | Document                                                                           | Description                | Topics                                                                                                                  |
| ---------- | ---------------------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Ref-01** | **[01-API-REFERENCE-CLASSES.md](./01-API-REFERENCE-CLASSES.md)**                   | Core API classes           | `EClient` [REQUEST], `EWrapper` [CALLBACK], `Contract` [REQUIRED], `ContractDetails`, `Bar`, Account structures         |
| **Ref-02** | **[02-API-REFERENCE-CONTRACTS-ORDERS.md](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** | Order and contract classes | `Order` (100+ attributes), `Execution`, `OrderState`, `ScannerSubscription`                                             |
| **Ref-03** | **[03-API-REFERENCE-EXECUTIONS.md](./03-API-REFERENCE-EXECUTIONS.md)**             | Trade data structures      | `CommissionAndFeesReport`, `Liquidity`, Historical ticks, Tick attributes                                               |
| **Ref-04** | **[04-API-REFERENCE-CONDITIONS.md](./04-API-REFERENCE-CONDITIONS.md)**             | Order conditions           | `PriceCondition`, `TimeCondition`, `MarginCondition`, `ExecutionCondition`, `VolumeCondition`, `PercentChangeCondition` |
| **Ref-05** | **[05-API-REFERENCE-DATA-TYPES.md](./05-API-REFERENCE-DATA-TYPES.md)**             | Helper classes             | `DepthMktDataDescription`, `NewsProvider`, `PriceIncrement`, `SmartComponent`, `WshEventData`                           |
| **Ref-TL** | **[TWS-GENERIC-TICK-LIST.md](./TWS-GENERIC-TICK-LIST.md)**                         | Generic Tick List          | `genericTickList` param, tick type codes (100-623), `mdoff` prefix, news sources (BZ, FLY, DJNL, etc.)                  |

### 1.2 Implementation Guides

**[WORKFLOW]** Step-by-step guides for implementing common TWS API workflows.

| Section      | Document                                                             | Description                                                                                   | Status         |
| ------------ | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------- |
| **Guide-06** | **[06-SETUP-GUIDE.md](./06-SETUP-GUIDE.md)**                         | [CRITICAL] Installation, configuration, TWS/Gateway setup, verification steps                 | ✅ Complete    |
| **Guide-07** | **[07-CONNECTIVITY-GUIDE.md](./07-CONNECTIVITY-GUIDE.md)**           | [CRITICAL] Connection patterns, threading models (sync/async), error handling, auto-reconnect | ✅ Complete    |
| **Guide-08** | **[08-MARKET-DATA-GUIDE.md](./08-MARKET-DATA-GUIDE.md)**             | Real-time data, historical data, market depth, tick types                                     | 🚧 Coming Soon |
| **Guide-09** | **[09-ORDER-MANAGEMENT-GUIDE.md](./09-ORDER-MANAGEMENT-GUIDE.md)**   | Order placement, modification, cancellation, status tracking                                  | 🚧 Coming Soon |
| **Guide-10** | **[10-ACCOUNT-PORTFOLIO-GUIDE.md](./10-ACCOUNT-PORTFOLIO-GUIDE.md)** | Account updates, positions, P&L, executions                                                   | 🚧 Coming Soon |
| **Guide-11** | **[11-ADVANCED-TOPICS.md](./11-ADVANCED-TOPICS.md)**                 | Financial advisors, scanners, news, complex strategies                                        | 🚧 Coming Soon |

### 1.3 External Resources

**[EXTERNAL]** Online resources (require internet connection):

- **[TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)** - Online API reference
- **[TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)** - Online implementation guides
- **[TWS API GitHub](https://github.com/InteractiveBrokers/tws-api-public)** - Official API source code
- **[IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)** - Support articles

---

## 2.0 Quick Start

### Prerequisites

- Python 3.8+
- TWS Desktop or IB Gateway installed
- Interactive Brokers account (live or paper)
- API trading enabled in Account Management

### Installation

```bash
# Install TWS API client
pip install ibapi

# Verify installation
python -c "from ibapi.client import EClient; print('TWS API installed successfully')"
```

### First Connection

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from threading import Thread

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print(f"Connected! Next Order ID: {orderId}")

app = IBApp()
app.connect("127.0.0.1", 7497, clientId=1)  # Paper trading port

# Run in separate thread
Thread(target=app.run, daemon=True).start()

# Keep alive
input("Press Enter to disconnect...")
app.disconnect()
```

---

## 2.0 Quick Start

<!-- METADATA: scope=getting-started, priority=critical, dependencies=[06-SETUP] -->

### 2.1 Prerequisites

**[REQUIRED]** Before you begin:

- Python 3.8+
- TWS Desktop or IB Gateway installed
- Interactive Brokers account (live or paper)
- API trading enabled in Account Management

**[PITFALL]** Common mistake: Forgetting to enable API access in TWS settings causes connection error 504.

### 2.2 Installation

```bash
# Install TWS API client
pip install ibapi

# Verify installation
python -c "from ibapi.client import EClient; print('TWS API installed successfully')"
```

### 2.3 First Connection

**[EXAMPLE]** Minimal working connection:

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from threading import Thread

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print(f"Connected! Next Order ID: {orderId}")

app = IBApp()
app.connect("127.0.0.1", 7497, clientId=1)  # Paper trading port

# Run in separate thread
Thread(target=app.run, daemon=True).start()

# Keep alive
input("Press Enter to disconnect...")
app.disconnect()
```

**See:** [Setup Guide](./06-SETUP-GUIDE.md) for complete installation and configuration.

---

## 3.0 Learning Paths

### For New Developers

**Goal:** Get first application running

1. **[Setup Guide](./06-SETUP-GUIDE.md)** - Install TWS API and configure TWS/Gateway
2. **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Establish connection and understand threading
3. **[API Reference - Core Classes](./01-API-REFERENCE-CLASSES.md)** - Learn `EClient` and `EWrapper` basics
4. **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** _(Coming Soon)_ - Request your first market data

### For Market Data Applications

**Goal:** Build real-time data feeds

1. **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection management and auto-reconnect
2. **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** _(Coming Soon)_ - Real-time ticks, historical data, market depth
3. **[API Reference - Data Types](./05-API-REFERENCE-DATA-TYPES.md)** - Understand tick structures
4. **[API Reference - Executions](./03-API-REFERENCE-EXECUTIONS.md)** - Historical tick classes

### For Trading Applications

**Goal:** Automated order execution

1. **[Setup Guide](./06-SETUP-GUIDE.md)** - Configure for live trading
2. **[API Reference - Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** - Master `Order` class (100+ parameters)
3. **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** _(Coming Soon)_ - Place, modify, cancel orders
4. **[API Reference - Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Conditional orders
5. **[Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md)** _(Coming Soon)_ - Track positions and P&L

### For Advanced Developers

**Goal:** Complex trading systems

1. **[API Reference - Core Classes](./01-API-REFERENCE-CLASSES.md)** - Complete `EClient` method reference
2. **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Production threading patterns (EReader, asyncio)
3. **[API Reference - Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Build complex order logic

---

## 3.0 Learning Paths

<!-- METADATA: scope=guided-learning, priority=high, dependencies=[06-SETUP,07-CONNECTIVITY] -->

### 3.1 For New Developers

**[WORKFLOW]** Goal: Get first application running

1. **[Setup Guide](./06-SETUP-GUIDE.md)** - Install TWS API and configure TWS/Gateway
2. **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Establish connection and understand threading
3. **[API Reference - Core Classes](./01-API-REFERENCE-CLASSES.md)** - Learn `EClient` and `EWrapper` basics
4. **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** _(Coming Soon)_ - Request your first market data

### 3.2 For Market Data Applications

**[WORKFLOW]** Goal: Build real-time data feeds

1. **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection management and auto-reconnect
2. **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** _(Coming Soon)_ - Real-time ticks, historical data, market depth
3. **[API Reference - Data Types](./05-API-REFERENCE-DATA-TYPES.md)** - Understand tick structures
4. **[API Reference - Executions](./03-API-REFERENCE-EXECUTIONS.md)** - Historical tick classes

### 3.3 For Trading Applications

**[WORKFLOW]** Goal: Automated order execution

1. **[Setup Guide](./06-SETUP-GUIDE.md)** - Configure for live trading
2. **[API Reference - Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** - Master `Order` class (100+ parameters)
3. **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** _(Coming Soon)_ - Place, modify, cancel orders
4. **[API Reference - Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Conditional orders
5. **[Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md)** _(Coming Soon)_ - Track positions and P&L

### 3.4 For Advanced Developers

**[WORKFLOW]** Goal: Complex trading systems

1. **[API Reference - Core Classes](./01-API-REFERENCE-CLASSES.md)** - Complete `EClient` method reference
2. **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Production threading patterns (EReader, asyncio)
3. **[API Reference - Conditions](./04-API-REFERENCE-CONDITIONS.md)** - Build complex order logic
4. **[Advanced Topics Guide](./11-ADVANCED-TOPICS.md)** _(Coming Soon)_ - Scanners, news, financial advisor allocation

---

## 4.0 Common Tasks

### Market Data

| Task                       | See                                                                        |
| -------------------------- | -------------------------------------------------------------------------- |
| Get real-time stock quotes | [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_             |
| Request historical bars    | [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_             |
| Subscribe to market depth  | [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_             |
| Understand tick types      | [Executions Reference](./03-API-REFERENCE-EXECUTIONS.md)                   |
| Generic tick list param    | [Generic Tick List](./TWS-GENERIC-TICK-LIST.md)                            |
| Request news headlines     | [Generic Tick List](./TWS-GENERIC-TICK-LIST.md#news-source-postfix-syntax) |

### Orders

| Task                 | See                                                                      |
| -------------------- | ------------------------------------------------------------------------ |
| Place market order   | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Place limit order    | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Place stop order     | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Bracket orders       | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Conditional orders   | [Conditions Reference](./04-API-REFERENCE-CONDITIONS.md)                 |
| Modify open orders   | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Cancel all orders    | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| All order parameters | [Contracts & Orders Reference](./02-API-REFERENCE-CONTRACTS-ORDERS.md)   |

### Account & Portfolio

| Task                | See                                                                          |
| ------------------- | ---------------------------------------------------------------------------- |
| Get account summary | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |
| Monitor positions   | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |
| Track P&L           | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |
| Get executions      | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |

### Connection & Setup

| Task                  | See                                              |
| --------------------- | ------------------------------------------------ |
| Install TWS API       | [Setup Guide](./06-SETUP-GUIDE.md)               |
| Configure TWS/Gateway | [Setup Guide](./06-SETUP-GUIDE.md)               |
| Establish connection  | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Handle disconnections | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Auto-reconnect        | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Error handling        | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |

---

## 4.0 Common Tasks

<!-- METADATA: scope=task-reference, priority=high, dependencies=[all-guides] -->

### 4.1 Market Data

**[TASK-ORIENTED]** Quick links to market data operations:

| Task                       | See                                                                        |
| -------------------------- | -------------------------------------------------------------------------- |
| Get real-time stock quotes | [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_             |
| Request historical bars    | [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_             |
| Subscribe to market depth  | [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_             |
| Understand tick types      | [Executions Reference](./03-API-REFERENCE-EXECUTIONS.md)                   |
| Generic tick list param    | [Generic Tick List](./TWS-GENERIC-TICK-LIST.md)                            |
| Request news headlines     | [Generic Tick List](./TWS-GENERIC-TICK-LIST.md#news-source-postfix-syntax) |

### 4.2 Orders

**[TASK-ORIENTED]** Quick links to order operations:

| Task                 | See                                                                      |
| -------------------- | ------------------------------------------------------------------------ |
| Place market order   | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Place limit order    | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Place stop order     | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Bracket orders       | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Conditional orders   | [Conditions Reference](./04-API-REFERENCE-CONDITIONS.md)                 |
| Modify open orders   | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| Cancel all orders    | [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ |
| All order parameters | [Contracts & Orders Reference](./02-API-REFERENCE-CONTRACTS-ORDERS.md)   |

### 4.3 Account & Portfolio

**[TASK-ORIENTED]** Quick links to account operations:

| Task                | See                                                                          |
| ------------------- | ---------------------------------------------------------------------------- |
| Get account summary | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |
| Monitor positions   | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |
| Track P&L           | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |
| Get executions      | [Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md) _(Coming Soon)_ |

### 4.4 Connection & Setup

**[TASK-ORIENTED]** Quick links to connection operations:

| Task                  | See                                              |
| --------------------- | ------------------------------------------------ |
| Install TWS API       | [Setup Guide](./06-SETUP-GUIDE.md)               |
| Configure TWS/Gateway | [Setup Guide](./06-SETUP-GUIDE.md)               |
| Establish connection  | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Handle disconnections | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Auto-reconnect        | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Error handling        | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |
| Threading patterns    | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) |

---

## 5.0 API Reference Quick Links

### Core Classes

- **[EClient](./01-API-REFERENCE-CLASSES.md#eclient-class)** - API client with 50+ request methods
- **[EWrapper](./01-API-REFERENCE-CLASSES.md#ewrapper-interface)** - Callback interface with 70+ methods
- **[Contract](./01-API-REFERENCE-CLASSES.md#contract-class)** - Instrument definition (25+ attributes)
- **[ContractDetails](./01-API-REFERENCE-CLASSES.md#contractdetails-class)** - Extended contract info (40+ fields)

### Order Classes

- **[Order](./02-API-REFERENCE-CONTRACTS-ORDERS.md#order-class)** - Complete order definition (100+ parameters)
- **[OrderState](./02-API-REFERENCE-CONTRACTS-ORDERS.md#orderstate-class)** - Order status and margin impact
- **[Execution](./02-API-REFERENCE-CONTRACTS-ORDERS.md#execution-class)** - Order fill details
- **[ExecutionFilter](./02-API-REFERENCE-CONTRACTS-ORDERS.md#executionfilter-class)** - Filter for execution queries

### Condition Classes

- **[PriceCondition](./04-API-REFERENCE-CONDITIONS.md#pricecondition)** - Trigger on price levels
- **[TimeCondition](./04-API-REFERENCE-CONDITIONS.md#timecondition)** - Trigger at specific time
- **[VolumeCondition](./04-API-REFERENCE-CONDITIONS.md#volumecondition)** - Trigger on volume thresholds
- **[MarginCondition](./04-API-REFERENCE-CONDITIONS.md#margincondition)** - Trigger on margin changes
- **[ExecutionCondition](./04-API-REFERENCE-CONDITIONS.md#executioncondition)** - Trigger on symbol execution
- **[PercentChangeCondition](./04-API-REFERENCE-CONDITIONS.md#percentchangecondition)** - Trigger on price change %

### Data Types

- **[Bar](./01-API-REFERENCE-CLASSES.md#bar-class)** - Historical price bar (OHLCV)
- **[HistoricalTick](./03-API-REFERENCE-EXECUTIONS.md#historicaltick)** - Historical tick data
- **[TickAttrib](./03-API-REFERENCE-EXECUTIONS.md#tickattrib)** - Tick attribute flags

---

## 5.0 API Reference Quick Links

<!-- METADATA: scope=class-reference, priority=reference, dependencies=[Ref-01,Ref-02,Ref-04] -->

### 5.1 Core Classes

**[REFERENCE]** Essential API classes:

- **[EClient](./01-API-REFERENCE-CLASSES.md#eclient-class-reference)** [REQUEST] - API client with 50+ request methods
- **[EWrapper](./01-API-REFERENCE-CLASSES.md#ewrapper-interface-reference)** [CALLBACK] - Callback interface with 70+ methods
- **[Contract](./01-API-REFERENCE-CLASSES.md#contract-class-reference)** [REQUIRED] - Instrument definition (25+ attributes)
- **[ContractDetails](./01-API-REFERENCE-CLASSES.md#contractdetails-class-reference)** - Extended contract info (40+ fields)

### 5.2 Order Classes

**[REFERENCE]** Order-related classes:

- **[Order](./02-API-REFERENCE-CONTRACTS-ORDERS.md#order-class-reference)** - Complete order definition (100+ parameters)
- **[OrderState](./02-API-REFERENCE-CONTRACTS-ORDERS.md#orderstate-class-reference)** - Order status and margin impact
- **[Execution](./02-API-REFERENCE-CONTRACTS-ORDERS.md#execution-class-reference)** - Order fill details
- **[ExecutionFilter](./02-API-REFERENCE-CONTRACTS-ORDERS.md#executionfilter-class-reference)** - Filter for execution queries

### 5.3 Condition Classes

**[REFERENCE]** Conditional order classes:

- **[PriceCondition](./04-API-REFERENCE-CONDITIONS.md#pricecondition)** - Trigger on price levels
- **[TimeCondition](./04-API-REFERENCE-CONDITIONS.md#timecondition)** - Trigger at specific time
- **[VolumeCondition](./04-API-REFERENCE-CONDITIONS.md#volumecondition)** - Trigger on volume thresholds
- **[MarginCondition](./04-API-REFERENCE-CONDITIONS.md#margincondition)** - Trigger on margin changes
- **[ExecutionCondition](./04-API-REFERENCE-CONDITIONS.md#executioncondition)** - Trigger on symbol execution
- **[PercentChangeCondition](./04-API-REFERENCE-CONDITIONS.md#percentchangecondition)** - Trigger on price change %

### 5.4 Data Types

**[REFERENCE]** Helper data structures:

- **[Bar](./01-API-REFERENCE-CLASSES.md#bar-class-reference)** - Historical price bar (OHLCV)
- **[HistoricalTick](./03-API-REFERENCE-EXECUTIONS.md#historicaltick-class-reference)** - Historical tick data
- **[TickAttrib](./03-API-REFERENCE-EXECUTIONS.md#tickattrib-class-reference)** - Tick attribute flags
- **[CommissionAndFeesReport](./03-API-REFERENCE-EXECUTIONS.md#commissionandfeesreport-class)** - Execution costs

---

## 6.0 Cheat Sheets

### Connection Ports

| Application | Live Account | Paper Account |
| ----------- | ------------ | ------------- |
| TWS Desktop | 7496         | 7497          |
| IB Gateway  | 4001         | 4002          |

### Common Error Codes

| Code | Meaning                    | Action                            |
| ---- | -------------------------- | --------------------------------- |
| 502  | Couldn't connect to TWS    | Check TWS is running, verify port |
| 504  | Not connected              | Enable API in TWS settings        |
| 1100 | Connectivity lost          | Auto-reconnect, check network     |
| 200  | No security definition     | Invalid contract                  |
| 201  | Order rejected             | Check order parameters            |
| 354  | No market data permissions | Subscribe to exchange data        |

**See:** [Connectivity Guide - Error Handling](./07-CONNECTIVITY-GUIDE.md#error-handling) for complete list.

### Order Types

| Type    | Description   | Parameters                                                            |
| ------- | ------------- | --------------------------------------------------------------------- |
| MKT     | Market order  | `orderType="MKT"`                                                     |
| LMT     | Limit order   | `orderType="LMT"`, `lmtPrice=100.0`                                   |
| STP     | Stop order    | `orderType="STP"`, `auxPrice=100.0`                                   |
| STP LMT | Stop-limit    | `orderType="STP LMT"`, `lmtPrice=100.0`, `auxPrice=99.0`              |
| TRAIL   | Trailing stop | `orderType="TRAIL"`, `auxPrice=1.0` (amount) or `trailingPercent=1.0` |

**See:** [Contracts & Orders Reference - Order Class](./02-API-REFERENCE-CONTRACTS-ORDERS.md#order-class) for all order types.

### Time in Force (TIF)

| Code | Description                              |
| ---- | ---------------------------------------- |
| DAY  | Day order (expires at market close)      |
| GTC  | Good till canceled                       |
| IOC  | Immediate or cancel                      |
| GTD  | Good till date (requires `goodTillDate`) |
| OPG  | Market on open                           |
| FOK  | Fill or kill                             |
| DTC  | Day till canceled                        |

### Contract Security Types

| Code  | Description             |
| ----- | ----------------------- |
| STK   | Stock                   |
| OPT   | Option                  |
| FUT   | Future                  |
| CASH  | Forex                   |
| BOND  | Bond                    |
| CFD   | Contract for difference |
| FUND  | Mutual fund             |
| CMDTY | Commodity               |
| IND   | Index                   |

---

## 6.0 Cheat Sheets

<!-- METADATA: scope=quick-reference, priority=high, dependencies=[06-SETUP,07-CONNECTIVITY] -->

### 6.1 Connection Ports

**[CONFIGURATION]** Default port assignments:

| Application | Live Account | Paper Account |
| ----------- | ------------ | ------------- |
| TWS Desktop | 7496         | 7497          |
| IB Gateway  | 4001         | 4002          |

**[PITFALL]** Using wrong port is most common connection issue. Verify in TWS: Edit → Global Configuration → API → Settings.

### 6.2 Common Error Codes

**[TROUBLESHOOTING]** Frequent error codes and solutions:

| Code | Meaning                    | Action                            |
| ---- | -------------------------- | --------------------------------- |
| 502  | Couldn't connect to TWS    | Check TWS is running, verify port |
| 504  | Not connected              | Enable API in TWS settings        |
| 1100 | Connectivity lost          | Auto-reconnect, check network     |
| 200  | No security definition     | Invalid contract                  |
| 201  | Order rejected             | Check order parameters            |
| 354  | No market data permissions | Subscribe to exchange data        |

**See:** [Connectivity Guide - Error Handling](./07-CONNECTIVITY-GUIDE.md#error-handling) for complete list.

### 6.3 Order Types

**[ORDER-TYPE]** Common order type configurations:

| Type    | Description   | Parameters                                                            |
| ------- | ------------- | --------------------------------------------------------------------- |
| MKT     | Market order  | `orderType="MKT"`                                                     |
| LMT     | Limit order   | `orderType="LMT"`, `lmtPrice=100.0`                                   |
| STP     | Stop order    | `orderType="STP"`, `auxPrice=100.0`                                   |
| STP LMT | Stop-limit    | `orderType="STP LMT"`, `lmtPrice=100.0`, `auxPrice=99.0`              |
| TRAIL   | Trailing stop | `orderType="TRAIL"`, `auxPrice=1.0` (amount) or `trailingPercent=1.0` |

**See:** [Contracts & Orders Reference - Order Class](./02-API-REFERENCE-CONTRACTS-ORDERS.md#order-class-reference) for all order types.

### 6.4 Time in Force (TIF)

**[ORDER-TIF]** Time in force options:

| Code | Description                              |
| ---- | ---------------------------------------- |
| DAY  | Day order (expires at market close)      |
| GTC  | Good till canceled                       |
| IOC  | Immediate or cancel                      |
| GTD  | Good till date (requires `goodTillDate`) |
| OPG  | Market on open                           |
| FOK  | Fill or kill                             |
| DTC  | Day till canceled                        |

### 6.5 Contract Security Types

**[CONTRACT-TYPE]** Security type identifiers:

| Code  | Description             |
| ----- | ----------------------- |
| STK   | Stock                   |
| OPT   | Option                  |
| FUT   | Future                  |
| CASH  | Forex                   |
| BOND  | Bond                    |
| CFD   | Contract for difference |
| FUND  | Mutual fund             |
| CMDTY | Commodity               |
| IND   | Index                   |
| BAG   | Combo (multi-leg)       |

---

## 7.0 Code Examples

### Basic Market Data Request

```python
from ibapi.contract import Contract

# Create contract
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

# Request market data (reqId=1)
app.reqMktData(1, contract, "", False, False, [])

# Receive callbacks in EWrapper
def tickPrice(self, reqId, tickType, price, attrib):
    print(f"Price update: Tick {tickType} = ${price}")
```

**See:** [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_ for complete examples.

### Basic Order Placement

```python
from ibapi.contract import Contract
from ibapi.order import Order

# Create contract
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

# Create order
order = Order()
order.action = "BUY"
order.orderType = "LMT"
order.totalQuantity = 100
order.lmtPrice = 150.00

# Place order
app.placeOrder(app.nextOrderId, contract, order)

# Receive callbacks in EWrapper
def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, ...):
    print(f"Order {orderId} status: {status}, filled: {filled}/{filled+remaining}")
```

**See:** [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ for complete examples.

### Conditional Order

```python
from ibapi.order import Order
from ibapi.order_condition import OrderCondition, OrderConditionType

# Create price condition: activate when AAPL > $150
price_cond = OrderCondition.Create(OrderConditionType.Price)
price_cond.ConId = 265598  # AAPL contract ID
price_cond.Exchange = "SMART"
price_cond.Price = 150.0
price_cond.IsMore = True

# Attach to order
order = Order()
order.action = "BUY"
order.orderType = "MKT"
order.totalQuantity = 100
order.conditions.append(price_cond)
order.conditionsIgnoreRth = False  # Only during regular hours
order.conditionsCancelOrder = False  # Activate (not cancel)

app.placeOrder(app.nextOrderId, contract, order)
```

---

## 7.0 Code Examples

<!-- METADATA: scope=code-samples, priority=high, dependencies=[01-CLASSES,02-CONTRACTS-ORDERS,04-CONDITIONS] -->

### 7.1 Basic Market Data Request

**[EXAMPLE]** Request real-time market data:

```python
from ibapi.contract import Contract

# Create contract
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

# Request market data (reqId=1)
app.reqMktData(1, contract, "", False, False, [])

# Receive callbacks in EWrapper
def tickPrice(self, reqId, tickType, price, attrib):
    print(f"Price update: Tick {tickType} = ${price}")
```

**See:** [Market Data Guide](./08-MARKET-DATA-GUIDE.md) _(Coming Soon)_ for complete examples.

### 7.2 Basic Order Placement

**[EXAMPLE]** Place a limit order:

```python
from ibapi.contract import Contract
from ibapi.order import Order

# Create contract
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

# Create order
order = Order()
order.action = "BUY"
order.orderType = "LMT"
order.totalQuantity = 100
order.lmtPrice = 150.00

# Place order
app.placeOrder(app.nextOrderId, contract, order)

# Receive callbacks in EWrapper
def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, ...):
    print(f"Order {orderId} status: {status}, filled: {filled}/{filled+remaining}")
```

**See:** [Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md) _(Coming Soon)_ for complete examples.

### 7.3 Conditional Order

**[EXAMPLE]** Order activated when price condition met:

```python
from ibapi.order import Order
from ibapi.order_condition import OrderCondition, OrderConditionType

# Create price condition: activate when AAPL > $150
price_cond = OrderCondition.Create(OrderConditionType.Price)
price_cond.ConId = 265598  # AAPL contract ID
price_cond.Exchange = "SMART"
price_cond.Price = 150.0
price_cond.IsMore = True

# Attach to order
order = Order()
order.action = "BUY"
order.orderType = "MKT"
order.totalQuantity = 100
order.conditions.append(price_cond)
order.conditionsIgnoreRth = False  # Only during regular hours
order.conditionsCancelOrder = False  # Activate (not cancel)

app.placeOrder(app.nextOrderId, contract, order)
```

**See:** [Conditions Reference](./04-API-REFERENCE-CONDITIONS.md) for all condition types.

---

## 8.0 Support & Resources

### Official Resources

- **TWS API Reference:** https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/
- **TWS API Documentation:** https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/
- **GitHub Repository:** https://github.com/InteractiveBrokers/tws-api-public
- **IB Support:** https://www.interactivebrokers.com/en/support/contact.php

### Community

- **IB Community Forums:** https://www.interactivebrokers.com/en/community/index.php
- **TWS API Discussion:** https://groups.io/g/twsapi

### Troubleshooting

1. **Check TWS/Gateway is running and logged in**
2. **Verify API is enabled:** Edit → Global Configuration → API → Settings
3. **Confirm port number:** 7497 (paper) or 7496 (live) for TWS
4. **Check Client ID:** Must be unique per connection

---

## 8.0 Support & Resources

<!-- METADATA: scope=help-troubleshooting, priority=medium, dependencies=[07-CONNECTIVITY] -->

### 8.1 Official Resources

**[EXTERNAL]** Interactive Brokers official documentation:

- **TWS API Reference:** https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/
- **TWS API Documentation:** https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/
- **GitHub Repository:** https://github.com/InteractiveBrokers/tws-api-public
- **IB Support:** https://www.interactivebrokers.com/en/support/contact.php

### 8.2 Community

**[EXTERNAL]** Community forums and discussions:

- **IB Community Forums:** https://www.interactivebrokers.com/en/community/index.php
- **TWS API Discussion:** https://groups.io/g/twsapi

### 8.3 Troubleshooting

**[TROUBLESHOOTING]** Common connection issues checklist:

1. **Check TWS/Gateway is running and logged in**
2. **Verify API is enabled:** Edit → Global Configuration → API → Settings
3. **Confirm port number:** 7497 (paper) or 7496 (live) for TWS
4. **Check Client ID:** Must be unique per connection
5. **Review error codes:** See [Connectivity Guide - Error Handling](./07-CONNECTIVITY-GUIDE.md#error-handling)

**[PITFALL]** Most connection issues stem from incorrect API settings in TWS or mismatched port numbers.

---

## 9.0 Documentation Status

<!-- METADATA: scope=documentation-meta, priority=low, dependencies=[] -->

**[STATUS]** Current completion status:

| Section                            | Status         | Last Updated |
| ---------------------------------- | -------------- | ------------ |
| API Reference - Classes            | ✅ Complete    | Nov 19, 2025 |
| API Reference - Contracts & Orders | ✅ Complete    | Nov 19, 2025 |
| API Reference - Executions         | ✅ Complete    | Nov 19, 2025 |
| API Reference - Conditions         | ✅ Complete    | Nov 19, 2025 |
| API Reference - Data Types         | ✅ Complete    | Nov 19, 2025 |
| Setup Guide                        | ✅ Complete    | Nov 19, 2025 |
| Connectivity Guide                 | ✅ Complete    | Nov 19, 2025 |
| Market Data Guide                  | 🚧 Coming Soon | -            |
| Order Management Guide             | 🚧 Coming Soon | -            |
| Account & Portfolio Guide          | 🚧 Coming Soon | -            |
| Advanced Topics Guide              | 🚧 Coming Soon | -            |

---

## 10.0 Updates & Maintenance

<!-- METADATA: scope=maintenance, priority=low, dependencies=[] -->

This documentation is maintained alongside the TWS API library at `/home/farouk/trader-pro/backend/external_packages/tws/`.

**[MAINTENANCE]** Update workflow:

1. Check for API updates: `pip list --outdated | grep ibapi`
2. Review [TWS API Release Notes](https://interactivebrokers.github.io/tws-api/)
3. Update relevant documentation sections
4. Test code examples with new API version
5. Update "Last Updated" dates in modified files

---

## 11.0 Local Modifications & Project Integration

<!-- METADATA: scope=local-mods, priority=high, dependencies=[providers/tws/README] -->

This project includes local enhancements to the TWS API library for improved developer experience.

### 11.1 Type Stub Files (`.pyi`)

**Location:** `backend/external_packages/tws/source/pythonclient/ibapi/`

15 type stub files provide full Pylance/Pyright support:

| Stub File                  | Purpose                                              |
| -------------------------- | ---------------------------------------------------- |
| `client.pyi`               | `EClient` class with 50+ method signatures           |
| `wrapper.pyi`              | `EWrapper` class with 70+ callback signatures        |
| `contract.pyi`             | `Contract`, `ContractDetails`, `ContractDescription` |
| `order.pyi`                | `Order` class with 100+ typed parameters             |
| `execution.pyi`            | `Execution`, `ExecutionFilter`                       |
| `common.pyi`               | `BarData`, `TickAttrib`, `HistoricalTick` types      |
| `decoder.pyi`              | `Decoder` class for message parsing                  |
| `reader.pyi`               | `EReader` class (not used in our implementation)     |
| `connection.pyi`           | `Connection` class for raw socket operations         |
| `comm.pyi`                 | Low-level communication utilities                    |
| `order_condition.pyi`      | Order condition types                                |
| `tag_value.pyi`            | `TagValue` for scanner/FA parameters                 |
| `scanner.pyi`              | `ScannerSubscription` for market scanners            |
| `account_summary_tags.pyi` | Account summary tag constants                        |
| `softdollartier.pyi`       | Soft dollar tier configuration                       |

**Benefits:**

- IDE autocomplete for all EClient methods and EWrapper callbacks
- Type checking catches errors before runtime
- Hover documentation shows parameter types

### 11.2 Utility Modules

**`decoder_utils.py`** - Protobuf message decoding utilities  
**`client_utils.py`** - Client-side connection and configuration helpers

### 11.3 Protobuf Regeneration

**Script:** `backend/scripts/regenerate_tws_protobufs.sh`

Regenerates protobuf Python files from `.proto` definitions when:

- Protobuf compiler version changes
- Proto definitions are modified
- Files become corrupted

### 11.4 Related Documentation

**[CROSS-REFERENCE]** For implementation details, see:

- **[TWS Provider README](../../../src/trading_api/providers/tws/README.md)** - Three-layer architecture (TWSDatafeedProvider → TWSClient → IBSocket)
- **[Provider System Guide](../../docs/PROVIDER-SYSTEM.md)** - Capability-based provider architecture

---

**Generated from:** [TWS API Campus](https://ibkrcampus.com/campus/ibkr-api-page/)  
**For:** Trader Pro project offline documentation  
**Purpose:** Enable complete offline development with TWS API library

**[Back to Top ↑](#interactive-brokers-tws-api-documentation)**
