# Broker Terminal Service - Implementation Documentation

**Version**: 1.0.0  
**Last Updated**: October 18, 2025  
**Status**: ✅ Mock Implementation - Production Ready for Development

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Implementation Status](#implementation-status)
- [TradingView Integration](#tradingview-integration)
- [Data Flow](#data-flow)
- [Core Features](#core-features)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Testing Strategy](#testing-strategy)
- [Future Enhancements](#future-enhancements)
- [References](#references)

## Overview

The **BrokerTerminalService** is a TypeScript class that implements the TradingView Trading Terminal's broker interface (`IBrokerWithoutRealtime`). It provides a complete mock trading environment for development and testing, simulating real broker functionality including order placement, position management, and execution tracking.

### Purpose

- **Development Environment**: Provides a realistic trading interface without requiring a real broker connection
- **TradingView Integration**: Enables full Trading Terminal features (order panels, position tracking, account management)
- **Type Safety**: Uses official TradingView TypeScript types for compile-time validation
- **Testing**: Facilitates frontend testing of trading workflows without backend dependencies

### Key Characteristics

- 🎯 **Mock Implementation**: Simulates broker behavior with local state management
- 🛡️ **Type-Safe**: Uses official TradingView types from `@public/trading_terminal`
- 🔄 **Real-Time Updates**: Simulates order execution and position updates
- 📊 **Account Management**: Tracks balance, equity, orders, and positions
- ⚡ **Event-Driven**: Follows TradingView's event-based architecture

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TradingView Trading Terminal                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Chart Widget                                             │  │
│  │  • Order Ticket UI                                        │  │
│  │  • Account Panel                                          │  │
│  │  • Position Panel                                         │  │
│  │  • Order Panel                                            │  │
│  └───────────────────┬───────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────┘
                         │ IBrokerConnectionAdapterHost
                         │ (Bidirectional Interface)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              BrokerTerminalService                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  State Management                                         │  │
│  │  • Map<string, Order>     - Active orders                │  │
│  │  • Map<string, Position>  - Open positions               │  │
│  │  • Execution[]            - Trade history                │  │
│  │  • IWatchedValue<number>  - Balance & Equity             │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Core Operations                                          │  │
│  │  • placeOrder()           - Create new orders            │  │
│  │  • modifyOrder()          - Update existing orders       │  │
│  │  • cancelOrder()          - Cancel orders                │  │
│  │  • orders()               - Query orders                 │  │
│  │  • positions()            - Query positions              │  │
│  │  • executions()           - Query trade history          │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Account Information                                      │  │
│  │  • accountsMetainfo()     - Account details              │  │
│  │  • accountManagerInfo()   - UI configuration             │  │
│  │  • currentAccount()       - Active account ID            │  │
│  │  • connectionStatus()     - Connection state             │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Symbol Information                                       │  │
│  │  • symbolInfo()           - Instrument metadata          │  │
│  │  • isTradable()           - Trading availability         │  │
│  │  • formatter()            - Price formatting             │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Simulation Engine                                        │  │
│  │  • simulateOrderExecution()  - 3s delay → fill order     │  │
│  │  • updatePosition()          - Create/update positions   │  │
│  │  • initializeBrokerData()    - Sample data generation   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         │ IDatafeedQuotesApi
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DatafeedService                              │
│  • Market data (quotes, bars)                                   │
│  • Symbol search and resolution                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Integration

The BrokerTerminalService integrates with TradingView through the `broker_factory` option:

```typescript
// TraderChartContainer.vue
const widgetOptions: TradingTerminalWidgetOptions = {
  // ... other options
  broker_factory: (host: IBrokerConnectionAdapterHost) => {
    return new BrokerTerminalService(host, datafeed)
  },
  broker_config: {
    configFlags: {
      supportClosePosition: true,
      supportNativeReversePosition: true,
      supportPLUpdate: true,
      supportExecutions: true,
      supportPositions: true,
      showQuantityInsteadOfAmount: false,
      supportLevel2Data: false,
      supportOrdersHistory: false,
    },
  },
}
```

## Implementation Status

### ✅ Fully Implemented Features

#### Order Management

- ✅ **Place Orders**: Market and Limit orders with full type validation
- ✅ **Modify Orders**: Update order parameters (price, quantity, etc.)
- ✅ **Cancel Orders**: Cancel working orders
- ✅ **Order Status Tracking**: Working, Filled, Canceled states
- ✅ **Order Types**: Market, Limit, Stop, Stop-Limit
- ✅ **Order Sides**: Buy and Sell

#### Position Management

- ✅ **Position Tracking**: Automatic position creation and updates
- ✅ **Position Calculation**: Average price calculation for multiple fills
- ✅ **Long/Short Positions**: Proper side management
- ✅ **Position Consolidation**: Combines fills for same symbol
- ✅ **Position Reversals**: Automatic side switching on net position changes

#### Execution Tracking

- ✅ **Execution History**: Complete trade record with timestamps
- ✅ **Symbol Filtering**: Query executions by symbol
- ✅ **Execution Details**: Price, quantity, side, time for each trade

#### Account Information

- ✅ **Account Metadata**: Account ID, name, type
- ✅ **Balance Tracking**: Using TradingView's `IWatchedValue` for reactive updates
- ✅ **Equity Tracking**: Real-time equity display
- ✅ **Account Panel Configuration**: Custom summary and column definitions
- ✅ **Connection Status**: Connected state reporting

#### UI Integration

- ✅ **Account Manager Panel**: Balance and equity display
- ✅ **Order Panel Columns**: Symbol, Side, Quantity, Status
- ✅ **Position Panel Columns**: Symbol, Side, Quantity, Average Price
- ✅ **Chart Context Menu**: Standard trading actions from chart
- ✅ **Number Formatting**: Proper price and quantity formatters

#### Symbol Information

- ✅ **Instrument Metadata**: Description, currency, type
- ✅ **Trading Constraints**: Min/max quantities, tick sizes
- ✅ **Pip Configuration**: Pip size and value for forex-style calculations
- ✅ **Tradability Checks**: All symbols tradable in mock mode

### ⏳ Partially Implemented

#### Order Execution Simulation

- ✅ **Timed Execution**: 3-second delay before filling orders
- ✅ **Status Updates**: Automatic transition from Working → Filled
- ⚠️ **Price Simulation**: Uses limit price or default (not market price)
- ⚠️ **Partial Fills**: Not currently simulated
- ⚠️ **Reject Scenarios**: No rejection simulation

### ❌ Not Implemented (Future)

#### Real-Time Data

- ❌ **Live Price Updates**: No real-time price subscriptions
- ❌ **P&L Calculation**: Real-time profit/loss updates
- ❌ **Mark-to-Market**: Position value updates based on market prices
- ❌ **Real-Time Balance**: Dynamic balance updates from P&L

#### Advanced Order Types

- ❌ **Bracket Orders**: Stop-loss and take-profit attached to orders
- ❌ **Trailing Stops**: Dynamic stop-loss updates
- ❌ **OCO Orders**: One-cancels-other order pairs
- ❌ **Position Brackets**: Attached SL/TP to positions

#### Advanced Features

- ❌ **Order Depth (DOM)**: Level 2 market data
- ❌ **Order History**: Historical filled/canceled orders
- ❌ **Multiple Accounts**: Multi-account support
- ❌ **Risk Management**: Margin calculations, leverage limits
- ❌ **Real-time Subscriptions**: `subscribeRealtime()` / `unsubscribeRealtime()`

## TradingView Integration

### IBrokerWithoutRealtime Interface

The service implements the `IBrokerWithoutRealtime` interface from TradingView's Broker API:

```typescript
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  // Core broker methods
  accountManagerInfo(): AccountManagerInfo
  async accountsMetainfo(): Promise<AccountMetainfo[]>
  async orders(): Promise<Order[]>
  async positions(): Promise<Position[]>
  async executions(symbol: string): Promise<Execution[]>
  async symbolInfo(symbol: string): Promise<InstrumentInfo>
  async placeOrder(order: PreOrder): Promise<PlaceOrderResult>
  async modifyOrder(order: Order): Promise<void>
  async cancelOrder(orderId: string): Promise<void>
  async chartContextMenuActions(context: TradeContext): Promise<ActionMetaInfo[]>
  async isTradable(): Promise<boolean>
  async formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter>
  currentAccount(): AccountId
  connectionStatus(): ConnectionStatus
}
```

### Type Definitions

All types are imported from the official TradingView library:

```typescript
import type {
  AccountId, // Branded string type for account identification
  AccountManagerInfo, // Account panel configuration
  AccountMetainfo, // Account metadata (id, name)
  ActionMetaInfo, // Chart context menu actions
  ConnectionStatus, // Connection state enum
  Execution, // Trade execution record
  IBrokerConnectionAdapterHost, // Host interface for TradingView integration
  IBrokerWithoutRealtime, // Broker interface without real-time subscriptions
  IDatafeedQuotesApi, // Quote data interface
  InstrumentInfo, // Symbol metadata
  INumberFormatter, // Number formatting interface
  IWatchedValue, // Reactive value wrapper
  Order, // Order record
  PlaceOrderResult, // Result of placing an order
  Position, // Position record
  PreOrder, // Order request payload
  TradeContext, // Chart trading context
} from '@public/trading_terminal'

import {
  OrderStatus, // Enum: Canceled, Filled, Inactive, Placing, Rejected, Working
  OrderType, // Enum: Limit, Market, Stop, StopLimit
  Side, // Enum: Buy (1), Sell (-1)
  StandardFormatterName, // Enum: Price, quantity, currency formatters
} from '@public/trading_terminal'
```

### Configuration Flags

The broker's capabilities are defined via `broker_config.configFlags`:

| Flag                           | Status      | Description                       |
| ------------------------------ | ----------- | --------------------------------- |
| `supportClosePosition`         | ✅ Enabled  | Allow closing positions from UI   |
| `supportNativeReversePosition` | ✅ Enabled  | Support position reversal         |
| `supportPLUpdate`              | ✅ Enabled  | Support P&L updates (planned)     |
| `supportExecutions`            | ✅ Enabled  | Show execution history            |
| `supportPositions`             | ✅ Enabled  | Show position panel               |
| `showQuantityInsteadOfAmount`  | ❌ Disabled | Show quantity vs. monetary amount |
| `supportLevel2Data`            | ❌ Disabled | No DOM/Level 2 data               |
| `supportOrdersHistory`         | ❌ Disabled | No historical orders panel        |

## Data Flow

### Order Placement Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. User Action (Chart or Order Panel)                         │
└───────────────────────┬─────────────────────────────────────────┘
                        │ PreOrder object
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. BrokerTerminalService.placeOrder()                         │
│     • Generate unique order ID: ORDER-{counter}                 │
│     • Create Order object with status: Working                  │
│     • Store in _orders Map                                      │
│     • Schedule execution simulation (3s timeout)                │
└───────────────────────┬─────────────────────────────────────────┘
                        │ PlaceOrderResult { orderId }
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. TradingView UI Updates                                     │
│     • Order appears in Order Panel with "Working" status        │
│     • Order marker appears on chart                             │
└─────────────────────────────────────────────────────────────────┘
                        │ After 3 seconds...
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. simulateOrderExecution()                                   │
│     • Update order status: Working → Filled                     │
│     • Set filledQty = qty                                       │
│     • Set avgPrice = limitPrice or default                      │
│     • Create Execution record                                   │
│     • Update or create Position                                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │ Automatic UI refresh
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. TradingView UI Updates                                     │
│     • Order status changes to "Filled" in Order Panel           │
│     • Position appears/updates in Position Panel                │
│     • Chart markers update                                      │
│     • Execution appears in Executions tab                       │
└─────────────────────────────────────────────────────────────────┘
```

### Position Update Logic

```typescript
private updatePosition(order: Order): void {
  const positionId = `${order.symbol}-POS`
  const existingPosition = this._positions.get(positionId)

  if (existingPosition) {
    // Update existing position
    const orderQty = order.side === Side.Buy ? order.qty : -order.qty
    const totalQty = existingPosition.qty + orderQty

    const updatedPosition: Position = {
      ...existingPosition,
      qty: Math.abs(totalQty),
      side: totalQty >= 0 ? Side.Buy : Side.Sell,
    }
    this._positions.set(positionId, updatedPosition)
  } else {
    // Create new position
    const newPosition: Position = {
      id: positionId,
      symbol: order.symbol,
      qty: order.qty,
      side: order.side,
      avgPrice: order.avgPrice || order.limitPrice || 100.0,
    }
    this._positions.set(positionId, newPosition)
  }
}
```

### State Management

The service uses three primary data structures:

```typescript
// Order tracking
private readonly _orders = new Map<string, Order>()
// Key: "ORDER-1", "ORDER-2", etc.
// Value: Complete Order object with status, prices, quantities

// Position tracking
private readonly _positions = new Map<string, Position>()
// Key: "AAPL-POS", "TSLA-POS", etc.
// Value: Position object with qty, side, avgPrice

// Execution history
private readonly _executions: Execution[] = []
// Array of all trade executions (chronological order)

// Account values (reactive)
private readonly balance: IWatchedValue<number>  // Reactive balance
private readonly equity: IWatchedValue<number>   // Reactive equity
```

## Core Features

### 1. Account Management

#### Account Information

```typescript
accountManagerInfo(): AccountManagerInfo {
  return {
    accountTitle: 'Mock Trading Account',
    summary: [
      {
        text: 'Balance',
        wValue: this.balance,          // Reactive value: $100,000
        isDefault: true,
        formatter: StandardFormatterName.FixedInCurrency,
      },
      {
        text: 'Equity',
        wValue: this.equity,           // Reactive value: $100,000
        isDefault: true,
        formatter: StandardFormatterName.FixedInCurrency,
      },
    ],
    orderColumns: [...],  // Order panel column configuration
    positionColumns: [...], // Position panel column configuration
    pages: [],            // Custom account pages (empty)
  }
}
```

#### Account Details

```typescript
async accountsMetainfo(): Promise<AccountMetainfo[]> {
  return [
    {
      id: 'DEMO-001' as AccountId,
      name: 'Demo Trading Account',
    },
  ]
}
```

### 2. Order Operations

#### Place Order

```typescript
async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
  const orderId = `ORDER-${this.orderCounter++}`

  const newOrder: Order = {
    id: orderId,
    symbol: order.symbol,
    type: order.type || OrderType.Market,
    side: order.side || Side.Buy,
    qty: order.qty || 100,
    status: OrderStatus.Working,
    limitPrice: order.limitPrice,
    stopPrice: order.stopPrice,
    updateTime: Date.now(),
  }

  this._orders.set(orderId, newOrder)

  // Simulate execution after 3 seconds
  setTimeout(() => {
    this.simulateOrderExecution(orderId)
  }, 3000)

  return { orderId }
}
```

#### Modify Order

```typescript
async modifyOrder(order: Order): Promise<void> {
  if (this._orders.has(order.id)) {
    this._orders.set(order.id, { ...order, updateTime: Date.now() })
    console.log(`Order modified: ${order.id}`)
  }
}
```

#### Cancel Order

```typescript
async cancelOrder(orderId: string): Promise<void> {
  const order = this._orders.get(orderId)
  if (order) {
    const cancelledOrder: Order = {
      ...order,
      status: OrderStatus.Canceled,
      updateTime: Date.now(),
    }
    this._orders.set(orderId, cancelledOrder)
    console.log(`Order cancelled: ${orderId}`)
  }
}
```

### 3. Position Management

#### Query Positions

```typescript
async positions(): Promise<Position[]> {
  return Array.from(this._positions.values())
}
```

#### Initial Sample Position

```typescript
private initializeBrokerData(): void {
  // Create sample position
  const brokerPosition: Position = {
    id: 'AAPL-POS-1',
    symbol: 'AAPL',
    qty: 100,
    side: Side.Buy,
    avgPrice: 150.0,
  }
  this._positions.set(brokerPosition.id, brokerPosition)
}
```

### 4. Execution Tracking

```typescript
async executions(symbol: string): Promise<Execution[]> {
  return this._executions.filter((exec) => exec.symbol === symbol)
}
```

Each execution contains:

```typescript
interface Execution {
  symbol: string // Symbol traded
  price: number // Execution price
  qty: number // Quantity filled
  side: Side // Buy or Sell
  time: number // Timestamp
}
```

### 5. Symbol Information

```typescript
async symbolInfo(symbol: string): Promise<InstrumentInfo> {
  return {
    description: `Mock instrument for ${symbol}`,
    currency: 'USD',
    type: 'stock',
    minTick: 0.01,           // Minimum price movement
    pipSize: 1,              // Pip size for forex
    pipValue: 1,             // Pip value for P&L
    qty: {
      min: 1,                // Minimum order quantity
      max: 1000000,          // Maximum order quantity
      step: 1,               // Quantity increment
      default: 100,          // Default order quantity
    },
  }
}
```

## API Reference

### Class: BrokerTerminalService

#### Constructor

```typescript
constructor(
  host: IBrokerConnectionAdapterHost,
  datafeed: IDatafeedQuotesApi
)
```

**Parameters:**

- `host`: TradingView's broker adapter host interface
- `datafeed`: Market data provider for quotes and bars

#### Methods

##### Account Methods

###### `accountManagerInfo(): AccountManagerInfo`

Returns account panel configuration including summary fields and column definitions.

**Returns:** Configuration object for account manager UI

###### `accountsMetainfo(): Promise<AccountMetainfo[]>`

Returns list of available accounts.

**Returns:** Array of account metadata (currently single demo account)

###### `currentAccount(): AccountId`

Returns the currently active account ID.

**Returns:** `'DEMO-001'` (branded AccountId type)

###### `connectionStatus(): ConnectionStatus`

Returns the current broker connection status.

**Returns:** `1` (Connected status)

##### Order Methods

###### `orders(): Promise<Order[]>`

Returns all orders (working, filled, canceled).

**Returns:** Array of Order objects

###### `placeOrder(order: PreOrder): Promise<PlaceOrderResult>`

Places a new order.

**Parameters:**

- `order`: Order request with symbol, type, side, qty, prices

**Returns:** Object containing the generated `orderId`

**Behavior:**

- Generates unique order ID
- Sets initial status to `Working`
- Schedules execution simulation after 3 seconds

###### `modifyOrder(order: Order): Promise<void>`

Modifies an existing order.

**Parameters:**

- `order`: Complete order object with modifications

**Returns:** Void promise

###### `cancelOrder(orderId: string): Promise<void>`

Cancels an existing order.

**Parameters:**

- `orderId`: ID of order to cancel

**Returns:** Void promise

**Behavior:**

- Updates order status to `Canceled`
- Updates timestamp

##### Position Methods

###### `positions(): Promise<Position[]>`

Returns all open positions.

**Returns:** Array of Position objects

##### Execution Methods

###### `executions(symbol: string): Promise<Execution[]>`

Returns execution history for a specific symbol.

**Parameters:**

- `symbol`: Symbol to query (e.g., "AAPL")

**Returns:** Array of Execution records filtered by symbol

##### Symbol Methods

###### `symbolInfo(symbol: string): Promise<InstrumentInfo>`

Returns trading metadata for a symbol.

**Parameters:**

- `symbol`: Symbol to query

**Returns:** Instrument information including constraints and formatting

###### `isTradable(): Promise<boolean>`

Checks if a symbol is tradable.

**Returns:** Always `true` in mock mode

##### UI Methods

###### `chartContextMenuActions(context: TradeContext): Promise<ActionMetaInfo[]>`

Returns context menu actions for chart.

**Parameters:**

- `context`: Chart trading context

**Returns:** Default context menu actions from host

###### `formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter>`

Returns number formatter for symbol.

**Parameters:**

- `symbol`: Symbol for formatting
- `alignToMinMove`: Whether to align to minimum tick size

**Returns:** Formatter from host

##### Private Methods (Internal)

###### `initializeBrokerData(): void`

Initializes sample trading data (one position, one order).

###### `simulateOrderExecution(orderId: string): void`

Simulates order execution after 3-second delay:

1. Updates order status to Filled
2. Creates execution record
3. Updates or creates position

###### `updatePosition(order: Order): void`

Updates position based on order fill:

- Creates new position if none exists
- Updates existing position quantity and average price
- Handles position reversals (long ↔ short)

## Configuration

### Widget Configuration

To enable trading features, configure the TradingView widget with broker options:

```typescript
const widgetOptions: TradingTerminalWidgetOptions = {
  symbol: 'AAPL',
  datafeed: new DatafeedService(),
  interval: '1D' as ResolutionString,
  container: chartContainer.value,
  library_path: '/trading_terminal/',
  theme: 'dark',

  // Debug modes
  debug: false, // General debugging
  debug_broker: 'all', // Broker API debugging (logs all broker calls)

  // Broker integration
  broker_factory: (host: IBrokerConnectionAdapterHost) => {
    return new BrokerTerminalService(host, datafeed)
  },

  broker_config: {
    configFlags: {
      supportClosePosition: true,
      supportNativeReversePosition: true,
      supportPLUpdate: true,
      supportExecutions: true,
      supportPositions: true,
      showQuantityInsteadOfAmount: false,
      supportLevel2Data: false,
      supportOrdersHistory: false,
    },
  },
}
```

### Debug Modes

#### General Debug Mode

```typescript
debug: true // Logs widget lifecycle and general events
```

#### Broker Debug Mode

```typescript
debug_broker: 'all' // Logs all broker API calls and responses
```

Console output with `debug_broker: 'all'`:

```
[Broker] Attempting to place order: { symbol: 'AAPL', type: 2, side: 1, qty: 100 }
[Broker] Mock order placed: ORDER-2 { id: 'ORDER-2', status: 6, ... }
Order executed: ORDER-2 { symbol: 'AAPL', price: 150, qty: 100, side: 1, time: 1697... }
```

## Testing Strategy

### Current Testing Approach

The BrokerTerminalService is currently tested through:

1. **Manual Testing**: Interactive testing via TradingView UI
   - Place orders through chart and order panel
   - Monitor position updates
   - Verify execution history
   - Check account panel displays

2. **Integration Testing**: Full-stack smoke tests (Playwright)
   - Located in `smoke-tests/`
   - Tests chart initialization
   - Verifies trading UI elements render correctly

3. **Console Logging**: Debug output for development
   - Order placement and execution events
   - Position updates
   - Connection status changes

### Recommended Testing Expansion

#### Unit Tests (Planned)

```typescript
// Example unit test structure
describe('BrokerTerminalService', () => {
  let broker: BrokerTerminalService
  let mockHost: IBrokerConnectionAdapterHost
  let mockDatafeed: IDatafeedQuotesApi

  beforeEach(() => {
    mockHost = createMockHost()
    mockDatafeed = createMockDatafeed()
    broker = new BrokerTerminalService(mockHost, mockDatafeed)
  })

  describe('placeOrder', () => {
    it('should create order with Working status', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      }

      const result = await broker.placeOrder(preOrder)
      expect(result.orderId).toMatch(/^ORDER-\d+$/)

      const orders = await broker.orders()
      const order = orders.find((o) => o.id === result.orderId)
      expect(order?.status).toBe(OrderStatus.Working)
    })

    it('should execute order after delay', async () => {
      vi.useFakeTimers()

      const preOrder: PreOrder = { symbol: 'AAPL', qty: 100 }
      const result = await broker.placeOrder(preOrder)

      vi.advanceTimersByTime(3000)

      const orders = await broker.orders()
      const order = orders.find((o) => o.id === result.orderId)
      expect(order?.status).toBe(OrderStatus.Filled)
    })
  })

  describe('positions', () => {
    it('should create position on order fill', async () => {
      // Test position creation logic
    })

    it('should update position on multiple fills', async () => {
      // Test position consolidation
    })

    it('should reverse position side on opposite fills', async () => {
      // Test position reversal
    })
  })
})
```

#### Integration Tests (Planned)

```typescript
// Test with actual TradingView widget
describe('TradingView Integration', () => {
  it('should display broker status button', () => {
    // Verify Trading Status button appears
  })

  it('should show account panel with balance', () => {
    // Verify account summary displays
  })

  it('should enable order placement from chart', () => {
    // Test order ticket integration
  })
})
```

### Testing with Makefile Commands

```bash
# Frontend unit tests
make -f project.mk test-frontend

# Frontend tests with coverage
cd frontend && make test

# Smoke tests (E2E with Playwright)
make -f project.mk test-smoke

# Full test suite
make -f project.mk test-all
```

## Future Enhancements

### Phase 1: Real-Time Integration (Short Term)

#### Backend Integration

- [ ] Connect to real backend trading API
- [ ] WebSocket integration for real-time updates
- [ ] Replace mock execution with actual order routing
- [ ] Implement real position tracking from backend

#### Real-Time P&L

- [ ] Subscribe to market data for held positions
- [ ] Calculate real-time profit/loss
- [ ] Update equity based on position values
- [ ] Display unrealized P&L in position panel

#### Enhanced Order Types

- [ ] Stop orders with real trigger logic
- [ ] Stop-limit order execution
- [ ] Market order with real market prices
- [ ] Partial fills support

### Phase 2: Advanced Features (Medium Term)

#### Bracket Orders

- [ ] Implement `editPositionBrackets()` method
- [ ] Stop-loss and take-profit order creation
- [ ] Bracket order management UI
- [ ] OCO (One-Cancels-Other) logic

#### Multi-Account Support

- [ ] Support multiple trading accounts
- [ ] Account switching capability
- [ ] Per-account position and order tracking
- [ ] Account-specific configurations

#### Risk Management

- [ ] Margin calculation and display
- [ ] Leverage limits enforcement
- [ ] Position size limits
- [ ] Risk warnings and alerts

### Phase 3: Production Features (Long Term)

#### Real-Time Subscriptions

- [ ] Implement `IBrokerTerminal` interface (full version)
- [ ] Add `subscribeRealtime()` method
- [ ] Add `unsubscribeRealtime()` method
- [ ] Real-time quote subscriptions for positions

#### Order Depth / DOM

- [ ] Level 2 market data integration
- [ ] DOM widget support
- [ ] Set `supportLevel2Data: true` in config
- [ ] Depth of market visualization

#### Order History

- [ ] Persistent order history storage
- [ ] Historical order queries
- [ ] Set `supportOrdersHistory: true` in config
- [ ] Export order history functionality

#### Advanced Trading

- [ ] Trailing stop orders
- [ ] Conditional orders (if-then logic)
- [ ] Algorithmic order execution
- [ ] Smart order routing

### Architecture Evolution

```
Current: Mock Broker (Local State)
   ↓
Phase 1: Backend Integration (REST API)
   ↓
Phase 2: Real-Time Streaming (WebSockets)
   ↓
Phase 3: Production Broker (Full Features)
```

## References

### TradingView Documentation

- **Trading Concepts**: https://www.tradingview.com/charting-library-docs/latest/trading_terminal/trading-concepts/
- **Broker API Reference**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerTerminal/
- **Broker Without Realtime**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerWithoutRealtime/
- **Trading Host**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerConnectionAdapterHost/

### Type Definitions

- **Local Types**: `/frontend/public/trading_terminal/broker-api.d.ts`
- **Chart Library Types**: `/frontend/public/trading_terminal/charting_library.d.ts`

### Implementation Examples

- **Terminal Web (Reference)**: https://github.com/FarmaanElahi/terminal-web/blob/main/components/chart/terminal/broker_terminal.ts
- **Binance Broker Sample**: https://github.com/TargetHit/tradingview-binance/blob/master/broker-sample/src/broker.ts

### Project Documentation

- **Architecture Overview**: `/ARCHITECTURE.md`
- **TradingView Types Guide**: `/frontend/TRADINGVIEW-TYPES.md`
- **Frontend README**: `/frontend/README.md`
- **Development Guide**: `/docs/DEVELOPMENT.md`

### Source Files

- **Service Implementation**: `/frontend/src/services/brokerTerminalService.ts`
- **Chart Container**: `/frontend/src/components/TraderChartContainer.vue`
- **Datafeed Service**: `/frontend/src/services/datafeedService.ts`

---

**Maintained by**: Development Team  
**Review Schedule**: Updated as features are implemented  
**Last Review**: October 18, 2025
