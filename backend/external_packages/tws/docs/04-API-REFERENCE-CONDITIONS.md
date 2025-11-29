# TWS API Reference - Order Conditions

<!-- METADATA: scope=order-conditions, priority=advanced, dependencies=[02-CONTRACTS-ORDERS] -->

> **Source:** [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)  
> **Last Updated:** November 19, 2025

This document contains comprehensive reference information for TWS API order condition classes.

**[ADVANCED]** Complete technical reference for conditional orders that activate or cancel based on market conditions.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section     | Condition Type                                               | Trigger                    | Jump To          |
| ----------- | ------------------------------------------------------------ | -------------------------- | ---------------- |
| **1.0**     | [Overview](#10-overview)                                     | -                          | Concepts         |
| **2.0**     | [OrderCondition Base](#20-ordercondition-base-class)         | -                          | Base class       |
| **3.0**     | [Condition Types](#30-condition-types)                       | -                          | All types        |
| **3.1**     | [PriceCondition](#31-pricecondition)                         | [CONDITION-TYPE] Price     | Price threshold  |
| **3.2**     | [TimeCondition](#32-timecondition)                           | [CONDITION-TYPE] Time      | Specific time    |
| **3.3**     | [MarginCondition](#33-margincondition)                       | [CONDITION-TYPE] Margin    | Margin cushion   |
| **3.4**     | [ExecutionCondition](#34-executioncondition)                 | [CONDITION-TYPE] Execution | Trade execution  |
| **3.5**     | [VolumeCondition](#35-volumecondition)                       | [CONDITION-TYPE] Volume    | Volume threshold |
| **3.6**     | [PercentChangeCondition](#36-percentchangecondition)         | [CONDITION-TYPE] Percent   | Price change %   |
| **4.0**     | [Combining Conditions](#40-combining-multiple-conditions)    | -                          | AND/OR logic     |
| **5.0**     | [Best Practices](#50-best-practices)                         | -                          | Guidelines       |
| **Related** | [Main Navigation](./README.md)                               | -                          | Back to index    |
| **Related** | [Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md) | -                          | Order class      |
| **Related** | [Core Classes](./01-API-REFERENCE-CLASSES.md)                | -                          | Contract class   |

---

## Table of Contents

- [1.0 Overview](#10-overview)
- [2.0 OrderCondition Base Class](#20-ordercondition-base-class)
- [3.0 Condition Types](#30-condition-types)
  - [3.1 PriceCondition](#31-pricecondition)
  - [3.2 TimeCondition](#32-timecondition)
  - [3.3 MarginCondition](#33-margincondition)
  - [3.4 ExecutionCondition](#34-executioncondition)
  - [3.5 VolumeCondition](#35-volumecondition)
  - [3.6 PercentChangeCondition](#36-percentchangecondition)
- [4.0 Combining Multiple Conditions](#40-combining-multiple-conditions)
- [5.0 Best Practices](#50-best-practices)
- [6.0 Quick Reference Card](#60-quick-reference-card)
- [7.0 Next Steps](#70-next-steps)

---

## 1.0 Overview

<!-- METADATA: scope=conditional-orders-overview, priority=high, dependencies=[] -->

**[ADVANCED]** Order conditions allow you to create orders that only activate or cancel when specific market conditions are met. Conditions can be applied to price, time, margin, execution, volume, or percent change metrics.

**[PATTERN]** Key Concepts:

- Conditions are evaluated continuously when market data is available
- Multiple conditions can be combined using the `Order.Conditions` list
- `Order.ConditionsIgnoreRth` determines if conditions are valid outside regular trading hours
- `Order.ConditionsCancelOrder` determines if conditions activate (false) or cancel (true) the order

**[DECISION]**: Conditions use builder pattern [fluent API design, chainable configuration] [alternative: constructor parameters] [TWS API design]

---

## 2.0 OrderCondition Base Class

<!-- METADATA: scope=condition-base-class, priority=reference, dependencies=[] -->

**[PATTERN]** Abstract base class for all order condition types.

### 2.1 Public Attributes

| Name                      | Type               | Description                                                               |
| ------------------------- | ------------------ | ------------------------------------------------------------------------- |
| `Type`                    | OrderConditionType | Type of condition (Price, Time, Margin, Execution, Volume, PercentChange) |
| `IsConjunctionConnection` | bool               | True = AND conjunction with next condition, False = OR conjunction        |

### Public Member Functions

| Name                 | Type            | Description                                                    |
| -------------------- | --------------- | -------------------------------------------------------------- |
| `Equals(object obj)` | abstract bool   | Equality comparison (must be implemented by derived classes)   |
| `GetHashCode()`      | abstract int    | Hash code generation (must be implemented by derived classes)  |
| `ToString()`         | abstract string | String representation (must be implemented by derived classes) |

### Static Public Member Functions

| Name                         | Type                  | Description                                |
| ---------------------------- | --------------------- | ------------------------------------------ |
| `Create(OrderConditionType)` | static OrderCondition | Factory method to create condition by type |

---

## 3.0 Condition Types

<!-- METADATA: scope=condition-implementations, priority=critical, dependencies=[OrderCondition] -->

### 3.1 PriceCondition

**[CONDITION-TYPE]** Trigger order based on instrument price.

#### 3.1.1 Public Attributes

| Name            | Type   | Description                                                                                                            |
| --------------- | ------ | ---------------------------------------------------------------------------------------------------------------------- |
| `Price`         | double | Price threshold for condition                                                                                          |
| `TriggerMethod` | int    | Price comparison method (0=Default, 1=Double bid/ask, 2=Last, 3=Double last, 4=Bid/ask, 7=Last or bid/ask, 8=Midpoint) |
| `ConId`         | int    | Contract ID for price observation                                                                                      |
| `Exchange`      | string | Exchange where price is observed                                                                                       |
| `IsMore`        | bool   | True = trigger when price goes above threshold, False = trigger when below                                             |

#### Example Usage

```python
# Create price condition: activate order when AAPL bid > $150
price_cond = OrderCondition.Create(OrderConditionType.Price)
price_cond.ConId = 265598  # AAPL contract ID
price_cond.Exchange = "SMART"
price_cond.Price = 150.0
price_cond.TriggerMethod = 4  # Bid/ask
price_cond.IsMore = True  # Trigger when above threshold

order.Conditions.append(price_cond)
```

---

### 3.2 TimeCondition

**[CONDITION-TYPE]** Trigger order at specific time.

#### 3.2.1 Public Attributes

| Name     | Type   | Description                                            |
| -------- | ------ | ------------------------------------------------------ |
| `Time`   | string | Time threshold (yyyymmdd HH:mm:ss {TZ})                |
| `IsMore` | bool   | True = trigger after time, False = trigger before time |

#### Example Usage

```python
# Create time condition: activate order after market open
time_cond = OrderCondition.Create(OrderConditionType.Time)
time_cond.Time = "20231215 09:30:00 US/Eastern"
time_cond.IsMore = True  # Trigger after this time

order.Conditions.append(time_cond)
```

---

### 3.3 MarginCondition

**[CONDITION-TYPE]** Trigger order based on margin cushion.

#### 3.3.1 Public Attributes

| Name      | Type | Description                                                     |
| --------- | ---- | --------------------------------------------------------------- |
| `Percent` | int  | Margin cushion percentage threshold (0-100)                     |
| `IsMore`  | bool | True = trigger when above threshold, False = trigger when below |

#### Example Usage

```python
# Create margin condition: cancel order if margin cushion drops below 20%
margin_cond = OrderCondition.Create(OrderConditionType.Margin)
margin_cond.Percent = 20
margin_cond.IsMore = False  # Trigger when below threshold

order.Conditions.append(margin_cond)
order.ConditionsCancelOrder = True  # Cancel instead of activate
```

---

### 3.4 ExecutionCondition

**[CONDITION-TYPE]** Trigger order based on trade execution.

#### 3.4.1 Public Attributes

| Name       | Type   | Description                         |
| ---------- | ------ | ----------------------------------- |
| `SecType`  | string | Security type (STK, OPT, FUT, etc.) |
| `Exchange` | string | Exchange where execution must occur |
| `Symbol`   | string | Symbol to monitor for executions    |

#### Example Usage

```python
# Create execution condition: activate order when SPY is executed
exec_cond = OrderCondition.Create(OrderConditionType.Execution)
exec_cond.Symbol = "SPY"
exec_cond.SecType = "STK"
exec_cond.Exchange = "SMART"

order.Conditions.append(exec_cond)
```

---

### 3.5 VolumeCondition

**[CONDITION-TYPE]** Trigger order based on volume threshold.

#### 3.5.1 Public Attributes

| Name       | Type   | Description                                                            |
| ---------- | ------ | ---------------------------------------------------------------------- |
| `Volume`   | int    | Volume threshold                                                       |
| `ConId`    | int    | Contract ID for volume observation                                     |
| `Exchange` | string | Exchange where volume is observed                                      |
| `IsMore`   | bool   | True = trigger when volume above threshold, False = trigger when below |

#### Example Usage

```python
# Create volume condition: activate order when daily volume exceeds 50M shares
vol_cond = OrderCondition.Create(OrderConditionType.Volume)
vol_cond.ConId = 265598  # AAPL contract ID
vol_cond.Exchange = "SMART"
vol_cond.Volume = 50000000
vol_cond.IsMore = True  # Trigger when above threshold

order.Conditions.append(vol_cond)
```

---

### 3.6 PercentChangeCondition

**[CONDITION-TYPE]** Trigger order based on percent price change.

#### 3.6.1 Public Attributes

| Name            | Type   | Description                                                            |
| --------------- | ------ | ---------------------------------------------------------------------- |
| `ChangePercent` | double | Percent change threshold                                               |
| `ConId`         | int    | Contract ID for price observation                                      |
| `Exchange`      | string | Exchange where price is observed                                       |
| `IsMore`        | bool   | True = trigger when change above threshold, False = trigger when below |

#### Example Usage

```python
# Create percent change condition: activate order if stock moves up 5%
pct_cond = OrderCondition.Create(OrderConditionType.PercentChange)
pct_cond.ConId = 265598  # AAPL contract ID
pct_cond.Exchange = "SMART"
pct_cond.ChangePercent = 5.0
pct_cond.IsMore = True  # Trigger when above threshold

order.Conditions.append(pct_cond)
```

---

## 4.0 Combining Multiple Conditions

<!-- METADATA: scope=condition-logic, priority=high, dependencies=[OrderCondition] -->

### 4.1 Using Conjunction (AND)

**[PATTERN]** Both conditions must be met:

```python
# Both conditions must be met
price_cond = OrderCondition.Create(OrderConditionType.Price)
price_cond.ConId = 265598
price_cond.Price = 150.0
price_cond.IsMore = True
price_cond.IsConjunctionConnection = True  # AND with next condition

vol_cond = OrderCondition.Create(OrderConditionType.Volume)
vol_cond.ConId = 265598
vol_cond.Volume = 10000000
vol_cond.IsMore = True

order.Conditions.append(price_cond)
order.Conditions.append(vol_cond)
```

### 4.2 Using Disjunction (OR)

**[PATTERN]** Either condition can trigger:

```python
# Either condition can trigger
time_cond = OrderCondition.Create(OrderConditionType.Time)
time_cond.Time = "20231215 15:30:00 US/Eastern"
time_cond.IsMore = True
time_cond.IsConjunctionConnection = False  # OR with next condition

exec_cond = OrderCondition.Create(OrderConditionType.Execution)
exec_cond.Symbol = "SPY"
exec_cond.SecType = "STK"
exec_cond.Exchange = "SMART"

order.Conditions.append(time_cond)
order.Conditions.append(exec_cond)
```

---

## 5.0 Best Practices

<!-- METADATA: scope=condition-best-practices, priority=high, dependencies=[OrderCondition] -->

**[PITFALL]** Common mistakes and recommendations:

1. **Contract ID Resolution:** Always resolve contract IDs using `reqContractDetails` before creating conditions that require `ConId`.

2. **Exchange Selection:** Use "SMART" exchange for most conditions to get aggregated market data.

3. **Time Formatting:** Use format `yyyymmdd HH:mm:ss {TZ}` for TimeCondition, including timezone.

4. **RTH vs Extended Hours:** Set `Order.ConditionsIgnoreRth = True` if conditions should be evaluated outside regular trading hours.

5. **Activation vs Cancellation:**

   - `Order.ConditionsCancelOrder = False` → Conditions activate order (default)
   - `Order.ConditionsCancelOrder = True` → Conditions cancel order

6. **Condition Testing:** Always test conditional orders with small quantities first to verify behavior.

---

## 6.0 Quick Reference Card

### Condition Types at a Glance

| Condition Type    | Trigger When             | Key Attributes                  | Example Use Case     |
| ----------------- | ------------------------ | ------------------------------- | -------------------- |
| **Price**         | Price crosses threshold  | Price, ConId, Exchange, IsMore  | Stop-loss trigger    |
| **Time**          | Specific time reached    | Time, IsMore                    | Market open/close    |
| **Margin**        | Margin cushion threshold | Percent, IsMore                 | Risk management      |
| **Execution**     | Trade executes           | Symbol, SecType, Exchange       | Hedging trigger      |
| **Volume**        | Volume crosses threshold | Volume, ConId, Exchange, IsMore | High-volume breakout |
| **PercentChange** | Price change % threshold | ChangePercent, ConId, IsMore    | Momentum trigger     |

### Conjunction vs Disjunction

| Logic   | IsConjunctionConnection | Behavior                    |
| ------- | ----------------------- | --------------------------- |
| **AND** | True                    | Both conditions must be met |
| **OR**  | False                   | Either condition triggers   |

**[EXAMPLE]** Complex condition (Price AND Volume):

```python
price_cond.IsConjunctionConnection = True  # AND
vol_cond.IsConjunctionConnection = False   # Last condition
```

---

## 7.0 Next Steps

**[WORKFLOW]** Continue to related references:

- **[Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md)** - Order class, order types
- **[Core Classes](./01-API-REFERENCE-CLASSES.md)** - Contract class, EClient.placeOrder()
- **[Executions & Data](./03-API-REFERENCE-EXECUTIONS.md)** - Execution data
- **[Data Types](./05-API-REFERENCE-DATA-TYPES.md)** - Helper classes

**[WORKFLOW]** Implementation guides:

- **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** - Conditional order examples _(Coming Soon)_
- **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - Connection patterns
- **[Setup Guide](./06-SETUP-GUIDE.md)** - Installation

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index

---

**[REFERENCE]** External resources:

- [TWS API Reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)
- [Conditional Orders Guide](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/#conditional-orders)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)

---

**Referenced by:**

- [Main Navigation](./README.md#11-api-reference-classes--methods) - Conditions (Ref-04)
- [Contracts & Orders](./02-API-REFERENCE-CONTRACTS-ORDERS.md) - Conditional orders use Order.Conditions
