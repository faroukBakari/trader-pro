# Broker Terminal Service - Implementation Documentation

**Version**: 2.0.0  
**Last Updated**: November 11, 2025  
**Status**: ✅ Full Implementation - Backend Integration Complete

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Implementation Status](#implementation-status)
- [WebSocket Integration](#websocket-integration)
- [TradingView Integration](#tradingview-integration)
- [Data Flow](#data-flow)
- [Core Features](#core-features)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Testing Strategy](#testing-strategy)
- [Future Enhancements](#future-enhancements)
- [Known Issues](#known-issues)
- [References](#references)

## Overview

The **BrokerTerminalService** is a TypeScript class that implements the TradingView Trading Terminal's broker interface (`IBrokerWithoutRealtime`). It provides a complete mock trading environment for development and testing, simulating real broker functionality including order placement, position management, and execution tracking.

### Purpose

- **Production Trading**: Full-featured broker implementation with backend integration
- **Smart Client Selection**: Seamlessly switches between mock fallback and real backend
- **TradingView Integration**: Enables full Trading Terminal features (order panels, position tracking, account management)
- **Type Safety**: Uses official TradingView TypeScript types for compile-time validation
- **Flexible Testing**: Supports both fallback mock and real backend testing

### Key Characteristics

- 🔌 **Dual Mode**: Smart client selection (fallback mock or real backend)
- 🛡️ **Type-Safe**: Uses official TradingView types from `@public/trading_terminal`
- 🔄 **Backend Integration**: Full REST API integration via ApiAdapter
- 📊 **Advanced Features**: Order preview, position management, leverage control
- ⚡ **Event-Driven**: Follows TradingView's event-based architecture
- 🧪 **Test-Friendly**: ApiInterface pattern enables seamless testing

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
│  │  Client Selection (_getApiAdapter)                        │  │
│  │  • brokerMock provided → ApiFallback(brokerMock)         │  │
│  │  • brokerMock absent   → ApiAdapter (real backend)       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Core Operations (delegates to ApiInterface)             │  │
│  │  • previewOrder()         - Preview order costs          │  │
│  │  • placeOrder()           - Create new orders            │  │
│  │  • modifyOrder()          - Update existing orders       │  │
│  │  • cancelOrder()          - Cancel orders                │  │
│  │  • orders()               - Query orders                 │  │
│  │  • positions()            - Query positions              │  │
│  │  • executions()           - Query trade history          │  │
│  │  • closePosition()        - Close positions              │  │
│  │  • editPositionBrackets() - Update SL/TP                │  │
│  │  • leverageInfo()         - Get leverage settings        │  │
│  │  • setLeverage()          - Update leverage              │  │
│  │  • previewLeverage()      - Preview leverage changes     │  │
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
└─────────────────────────────────────────────────────────────────┘
         │                                          │
         │ ApiInterface                             │ IDatafeedQuotesApi
         ▼                                          ▼
┌──────────────────────┐              ┌──────────────────────────┐
│   ApiFallback        │              │    DatafeedService       │
│   (Mock Client)      │              │  • Market data           │
│  • Local state       │              │  • Symbol search         │
│  • Instant execution │              └──────────────────────────┘
└──────────────────────┘
         │ ApiInterface
         ▼
┌──────────────────────┐
│   ApiAdapter         │
│   (Backend Client)   │
│  • REST API calls    │
│  • Type conversion   │
│  • Error handling    │
└──────────┬───────────┘
           │ HTTP/REST
           ▼
┌──────────────────────┐
│  Backend Broker API  │
│  /api/v1/broker/*    │
└──────────────────────┘
```

### Component Integration

The BrokerTerminalService integrates with TradingView through the `broker_factory` option:

```typescript
// TraderChartContainer.vue
const widgetOptions: TradingTerminalWidgetOptions = {
  // ... other options
  broker_factory: (host: IBrokerConnectionAdapterHost) => {
    // Smart client selection via optional BrokerMock instance
    // Pass undefined or omit third parameter to use real backend
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

## WebSocket Integration

The BrokerTerminalService uses **dual-mode WebSocket integration** to support both mock fallback and real backend communication. This allows seamless development and testing without backend dependencies while enabling production-ready real-time updates.

### Architecture Pattern

The service uses a **smart client selection pattern** similar to the REST API layer:

```typescript
export interface WsAdapterType {
  orders: {
    subscribe(
      listenerId: string,
      params: { accountId: string },
      callback: (order: Order) => void,
    ): void
    unsubscribe(listenerId: string): void
  }
  positions: {
    subscribe(
      listenerId: string,
      params: { accountId: string },
      callback: (position: Position) => void,
    ): void
    unsubscribe(listenerId: string): void
  }
  executions: {
    subscribe(
      listenerId: string,
      params: { accountId: string },
      callback: (execution: Execution) => void,
    ): void
    unsubscribe(listenerId: string): void
  }
  equity: {
    subscribe(
      listenerId: string,
      params: { accountId: string },
      callback: (data: EquityData) => void,
    ): void
    unsubscribe(listenerId: string): void
  }
  brokerConnectionStatus: {
    subscribe(
      listenerId: string,
      params: { accountId: string },
      callback: (status: BrokerConnectionStatus) => void,
    ): void
    unsubscribe(listenerId: string): void
  }
}

class WsFallback implements Partial<WsAdapterType> {
  // Mock implementation with polling simulation
  // Checks BrokerMock state every 100ms and emits updates
}

class WsAdapter implements WsAdapterType {
  // Real WebSocket via backend connection
  // Subscribes to server-confirmed topic subscriptions
}
```

### WebSocket Setup

The service initializes WebSocket subscriptions during construction:

```typescript
constructor(
  host: IBrokerConnectionAdapterHost,
  quotesProvider: IDatafeedQuotesApi,
  brokerMock?: BrokerMock,
) {
  this._hostAdapter = host
  this._quotesProvider = quotesProvider
  this.apiAdapter = new ApiAdapter()
  this._wsAdapter = new WsAdapter()

  if (brokerMock) {
    this._apiFallback = new ApiFallback(brokerMock)
    this._wsFallback = new WsFallback(brokerMock)  // 👈 WebSocket fallback
  }

  // Initialize reactive values
  this.balance = this._hostAdapter.factory.createWatchedValue(this.startingBalance)
  this.equity = this._hostAdapter.factory.createWatchedValue(this.startingBalance)

  // Generate unique listener ID for WebSocket subscriptions
  this.listenerId = `ACCOUNT-${Math.random().toString(36).substring(2, 15)}`

  // Setup all 5 WebSocket subscriptions
  this.setupWebSocketHandlers()  // 👈 Key initialization
}
```

### Smart Client Selection

The `_getWsAdapter()` method selects between fallback and real WebSocket:

```typescript
private _getWsAdapter(): WsAdapterType | Partial<WsAdapterType> {
  return this._wsFallback ?? this._wsAdapter
}
```

**Logic**:

- If `brokerMock` provided → Returns `WsFallback` (polling-based mock)
- If `brokerMock` absent → Returns `WsAdapter` (real WebSocket connection)

This mirrors the REST API pattern with `_getApiAdapter()`.

### WebSocket Subscription Lifecycle

The `setupWebSocketHandlers()` method establishes 5 real-time subscriptions:

```typescript
private setupWebSocketHandlers(): void {
  // 1. Order updates (status changes, fills, cancellations)
  this._getWsAdapter().orders?.subscribe(
    'broker-orders',
    { accountId: this.listenerId },
    (order: Order) => {
      this._hostAdapter.orderUpdate(order)

      // Show notification on fill
      if (order.status === OrderStatus.Filled) {
        this._hostAdapter.showNotification(
          'Order Filled',
          `${order.symbol} ${order.side === 1 ? 'Buy' : 'Sell'} ${order.qty} @ ${order.avgPrice ?? 'market'}`,
          NotificationType.Success
        )
      }
    }
  )

  // 2. Position updates (new positions, quantity changes, closures)
  this._getWsAdapter().positions?.subscribe(
    'broker-positions',
    { accountId: this.listenerId },
    (position: Position) => {
      this._hostAdapter.positionUpdate(position)
    }
  )

  // 3. Execution updates (trade confirmations)
  this._getWsAdapter().executions?.subscribe(
    'broker-executions',
    { accountId: this.listenerId },
    (execution: Execution) => {
      this._hostAdapter.executionUpdate(execution)
    }
  )

  // 4. Equity updates (balance, equity, P&L changes)
  this._getWsAdapter().equity?.subscribe(
    'broker-equity',
    { accountId: this.listenerId },
    (data: EquityData) => {
      this._hostAdapter.equityUpdate(data.equity)

      // Update reactive balance/equity values
      if (data.balance !== undefined && data.balance !== null) {
        this.balance.setValue(data.balance)
      }
      if (data.equity !== undefined && data.equity !== null) {
        this.equity.setValue(data.equity)
      }
    }
  )

  // 5. Broker connection status (connected, disconnected, errors)
  this._getWsAdapter().brokerConnectionStatus?.subscribe(
    'broker-connection-status',
    { accountId: this.listenerId },
    (status: BrokerConnectionStatus) => {
      this._hostAdapter.showNotification(
        'Broker Status',
        status.message || 'Connection status changed',
        status.status === ConnectionStatus.Connected
          ? NotificationType.Success
          : NotificationType.Error
      )
    }
  )
}
```

### Subscription Details

| Subscription               | Topic                                  | Purpose                         | Updates                                  |
| -------------------------- | -------------------------------------- | ------------------------------- | ---------------------------------------- |
| **orders**                 | `orders:{accountId}`                   | Real-time order status changes  | Working, Filled, Canceled, Rejected      |
| **positions**              | `positions:{accountId}`                | Position quantity/price updates | New positions, size changes, closures    |
| **executions**             | `executions:{accountId}`               | Trade confirmations             | Execution price, quantity, timestamp     |
| **equity**                 | `equity:{accountId}`                   | Account value changes           | Balance, equity, unrealized/realized P&L |
| **brokerConnectionStatus** | `broker-connection-status:{accountId}` | Connection health               | Connected, Disconnected, Error           |

### Mock vs Real WebSocket Behavior

#### WsFallback (Mock Mode)

**Polling Simulation**:

```typescript
// Checks BrokerMock state every 100ms
setInterval(() => {
  const newOrders = brokerMock.getOrderUpdates()
  newOrders.forEach((order) => callback(order))
}, 100)
```

**Characteristics**:

- No server dependency
- Deterministic behavior for testing
- Instant updates (no network latency)
- Predictable execution timing

**When Used**:

- Unit tests with `BrokerMock` instance
- Offline development
- UI testing without backend

#### WsAdapter (Real Mode)

**WebSocket Connection**:

```typescript
// Subscribes to backend WebSocket server
wsClient.subscribe('orders:ACCOUNT-abc123', (message) => {
  const order = mapper.toOrder(message)
  callback(order)
})
```

**Characteristics**:

- Real server-confirmed subscriptions
- Network latency and connection handling
- Server-side validation
- Production-ready reliability

**When Used**:

- Production deployment
- Integration testing with backend
- Backend development workflow

### TradingView Integration Callbacks

The WebSocket handlers use TradingView's `IBrokerConnectionAdapterHost` interface to push updates:

| Method                               | Purpose                           | When Called                                 |
| ------------------------------------ | --------------------------------- | ------------------------------------------- |
| `orderUpdate(order)`                 | Update order in Order Panel       | Order status changes (Working→Filled, etc.) |
| `positionUpdate(position)`           | Update position in Position Panel | Position changes (new, modified, closed)    |
| `executionUpdate(execution)`         | Add to Executions tab             | Trade execution confirmation                |
| `equityUpdate(equity)`               | Update account equity             | P&L changes, balance updates                |
| `showNotification(title, msg, type)` | Display UI notification           | Order fills, connection changes             |

### Event Flow Example

**Order Placement with WebSocket Updates**:

```
1. User clicks "Buy" on chart
   ↓
2. BrokerTerminalService.placeOrder() (REST API)
   ↓
3. Backend creates order, broadcasts update
   ↓
4. WsAdapter receives message on orders:{accountId}
   ↓
5. setupWebSocketHandlers() callback triggered
   ↓
6. this._hostAdapter.orderUpdate(order)
   ↓
7. TradingView Order Panel updates (Working status)
   ↓
8. Backend fills order, broadcasts update
   ↓
9. WsAdapter receives fill message
   ↓
10. Callback updates UI + shows notification
    ↓
11. Position/Execution updates follow same flow
```

### Testing WebSocket Integration

#### Unit Tests with WsFallback

```typescript
// From brokerTerminalService.spec.ts
it('should receive order updates via WebSocket', async () => {
  const testBrokerMock = new BrokerMock()
  const broker = new BrokerTerminalService(mockHost, mockDatafeed, testBrokerMock)

  // Place order via REST
  await broker.placeOrder({ symbol: 'AAPL', qty: 100 })

  // Wait for WebSocket mocker chain (polling cycles)
  await waitForMockerChain(4) // 4 * 100ms polling

  // Verify WebSocket pushed update to TradingView
  expect(mockHost.orderUpdate).toHaveBeenCalled()
})

const waitForMockerChain = async (cycles = 4) => {
  // WsFallback polls every 100ms
  await new Promise((resolve) => setTimeout(resolve, cycles * 100 + 50))
}
```

#### Integration Tests with Real Backend

```bash
# Start backend with WebSocket support
make -f project.mk dev-backend

# Run frontend with real WsAdapter
make -f project.mk dev-frontend

# Frontend automatically connects to ws://localhost:8000/ws
```

### WebSocket Configuration

**Backend WebSocket Endpoint**:

```typescript
// WsAdapter connects to:
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/ws'
```

**Environment Variables**:

```env
# .env.development
VITE_WS_BASE_URL=ws://localhost:8000/ws

# .env.production
VITE_WS_BASE_URL=wss://api.trader-pro.com/ws
```

**Connection Lifecycle**:

1. WsAdapter initializes on service construction
2. WebSocket connects on first subscription
3. Sends server-confirmed subscription requests
4. Backend validates and confirms subscriptions
5. Broadcasts updates to confirmed subscriptions
6. Reconnects automatically on disconnection

### Current Limitations (Phase 4 Complete, Phase 5 Pending)

**✅ Frontend Implementation Complete**:

- All 5 WebSocket subscriptions implemented
- Smart client selection (`_getWsAdapter()`)
- TradingView integration callbacks
- Mock fallback for testing
- Type-safe WebSocket adapters

**⏳ Backend Implementation Pending (Phase 5)**:

- Backend broadcasting logic not yet implemented
- WebSocket tests in TDD Red Phase (expected failures)
- Server-confirmed subscriptions protocol defined
- AsyncAPI spec complete, broadcasting code pending

**Workaround**: Use `BrokerMock` for development until Phase 5 completes:

```typescript
// Development mode with mock
const brokerMock = new BrokerMock()
const broker = new BrokerTerminalService(host, datafeed, brokerMock)
```

See `WEBSOCKET-METHODOLOGY.md` for Phase 5 implementation roadmap.

## Component Integration

The BrokerTerminalService integrates with TradingView through the `broker_factory` option:

```typescript
// TraderChartContainer.vue
const widgetOptions: TradingTerminalWidgetOptions = {
  // ... other options
  broker_factory: (host: IBrokerConnectionAdapterHost) => {
    // Smart client selection via optional BrokerMock instance
    // Pass undefined or omit third parameter to use real backend
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

- ✅ **Preview Orders**: Cost, fee, and margin preview before placement
- ✅ **Place Orders**: Market and Limit orders with full type validation
- ✅ **Modify Orders**: Update order parameters (price, quantity, etc.)
- ✅ **Cancel Orders**: Cancel working orders
- ✅ **Order Status Tracking**: Working, Filled, Canceled states
- ✅ **Order Types**: Market, Limit, Stop, Stop-Limit
- ✅ **Order Sides**: Buy and Sell
- ✅ **Backend Integration**: Full REST API communication

#### Position Management

- ✅ **Position Tracking**: Automatic position creation and updates
- ✅ **Position Calculation**: Average price calculation for multiple fills
- ✅ **Long/Short Positions**: Proper side management
- ✅ **Position Consolidation**: Combines fills for same symbol
- ✅ **Position Reversals**: Automatic side switching on net position changes
- ✅ **Close Position**: Full or partial position closing
- ✅ **Position Brackets**: Stop-loss and take-profit management
- ✅ **Backend Synchronization**: Real-time sync with backend state

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

#### Leverage Management

- ✅ **Leverage Info**: Get current leverage settings and constraints
- ✅ **Set Leverage**: Update leverage for symbols
- ✅ **Preview Leverage**: Preview leverage changes with warnings
- ✅ **Validation**: Min/max leverage enforcement

### ⏳ Partially Implemented

#### Backend Integration (In Progress)

- ✅ **REST API Communication**: Full implementation via ApiAdapter
- ✅ **Type Conversion**: Enum casting in adapter layer
- ✅ **Error Handling**: HTTP error mapping
- ✅ **WebSocket Updates**: Real-time position/order updates via WsAdapter
- ✅ **WebSocket Subscriptions**: 5 broker event subscriptions (orders, positions, executions, equity, connection status)
- ✅ **Smart Client Selection**: `_getWsAdapter()` method for fallback/real WebSocket switching
- ⚠️ **Backend Broadcasting**: Phase 5 pending (backend WebSocket implementation)
- ⚠️ **Optimistic Updates**: UI updates before backend confirmation (planned)

### ❌ Not Implemented (Future)

#### Real-Time Data

- ❌ **Live Price Updates**: No real-time price subscriptions
- ❌ **P&L Calculation**: Real-time profit/loss updates
- ❌ **Mark-to-Market**: Position value updates based on market prices
- ❌ **Real-Time Balance**: Dynamic balance updates from P&L
- ❌ **WebSocket Notifications**: Real-time order/position updates from backend

#### Advanced Order Types

- ❌ **Bracket Orders**: Stop-loss and take-profit attached to orders
- ❌ **Trailing Stops**: Dynamic stop-loss updates
- ❌ **OCO Orders**: One-cancels-other order pairs

#### Advanced Features

- ❌ **Order Depth (DOM)**: Level 2 market data
- ❌ **Order History**: Historical filled/canceled orders
- ❌ **Multiple Accounts**: Multi-account support
- ❌ **Risk Management**: Margin calculations, leverage limits
- ❌ **Real-time Subscriptions**: `subscribeRealtime()` / `unsubscribeRealtime()`

## TradingView Integration

### Architecture Pattern

The service uses a **delegation pattern** with smart client selection:

```typescript
export interface ApiInterface {
  // Contract that both ApiFallback and ApiAdapter implement
  previewOrder(order: PreOrder): ApiPromise<OrderPreviewResult>
  placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult>
  // ... all broker operations
}

class ApiFallback implements ApiInterface {
  // Mock implementation with local state
}

class ApiAdapter implements ApiInterface {
  // Real backend via REST API
}
```

### IBrokerWithoutRealtime Interface

The service implements the `IBrokerWithoutRealtime` interface from TradingView's Broker API:

```typescript
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly apiFallback: ApiInterface
  private readonly apiAdapter: ApiInterface
  private readonly mock: boolean

  private _getApiAdapter(mock: boolean = this.mock): ApiInterface {
    return mock ? this.apiFallback : this.apiAdapter
  }
  // Core broker methods (all delegate to ApiInterface client)
  accountManagerInfo(): AccountManagerInfo
  async accountsMetainfo(): Promise<AccountMetainfo[]>
  async orders(): Promise<Order[]>
  async positions(): Promise<Position[]>
  async executions(symbol: string): Promise<Execution[]>
  async symbolInfo(symbol: string): Promise<InstrumentInfo>
  async previewOrder(order: PreOrder): Promise<OrderPreviewResult>
  async placeOrder(order: PreOrder): Promise<PlaceOrderResult>
  async modifyOrder(order: Order, confirmId?: string): Promise<void>
  async cancelOrder(orderId: string): Promise<void>
  async closePosition(positionId: string, amount?: number): Promise<void>
  async editPositionBrackets(positionId: string, brackets: Brackets): Promise<void>
  async leverageInfo(params: LeverageInfoParams): Promise<LeverageInfo>
  async setLeverage(params: LeverageSetParams): Promise<LeverageSetResult>
  async previewLeverage(params: LeverageSetParams): Promise<LeveragePreviewResult>
  async chartContextMenuActions(context: TradeContext): Promise<ActionMetaInfo[]>
  async isTradable(): Promise<IsTradableResult>
  async formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter>
  currentAccount(): AccountId
  connectionStatus(): ConnectionStatusType
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
| `supportPLUpdate`              | ✅ Enabled  | Support P&L updates               |
| `supportExecutions`            | ✅ Enabled  | Show execution history            |
| `supportPositions`             | ✅ Enabled  | Show position panel               |
| `supportOrderPreview`          | ✅ Enabled  | Preview orders before placement   |
| `supportPositionBrackets`      | ✅ Enabled  | Edit SL/TP for positions          |
| `supportLeverage`              | ✅ Enabled  | Leverage management               |
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
// For production/real backend (default)
const datafeed = new DatafeedService()

const widgetOptions: TradingTerminalWidgetOptions = {
  symbol: 'AAPL',
  datafeed,
  interval: '1D' as ResolutionString,
  container: chartContainer.value,
  library_path: '/trading_terminal/',
  theme: 'dark',

  // Debug modes
  debug: false, // General debugging
  debug_broker: 'all', // Broker API debugging (logs all broker calls)

  // Broker integration (real backend)
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

// For testing with mock data
import { BrokerMock, DatafeedMock } from '@/services'

const datafeedMock = new DatafeedMock()
const datafeed = new DatafeedService(datafeedMock)
const brokerMock = new BrokerMock()

const widgetOptions: TradingTerminalWidgetOptions = {
// ... same options as above
broker_factory: (host: IBrokerConnectionAdapterHost) => {
return new BrokerTerminalService(host, datafeed, brokerMock)
},
// ... broker_config
}

````

### Debug Modes

#### General Debug Mode

```typescript
debug: true // Logs widget lifecycle and general events
````

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

### Comprehensive Testing (Implemented)

#### Unit Tests with BrokerMock

```typescript
// Actual test structure from brokerTerminalService.spec.ts
import { BrokerMock } from '../brokerTerminalService'

describe('BrokerTerminalService', () => {
  let broker: BrokerTerminalService
  let mockHost: IBrokerConnectionAdapterHost
  let mockDatafeed: IDatafeedQuotesApi
  let testBrokerMock: BrokerMock

  beforeEach(() => {
    // Create fresh BrokerMock instance for each test
    testBrokerMock = new BrokerMock()
    mockHost = createMockHost()
    mockDatafeed = createMockDatafeed()

    // Service uses fallback client with test BrokerMock instance
    broker = new BrokerTerminalService(mockHost, mockDatafeed, testBrokerMock)
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
      expect(result.orderId).toMatch(/^ORDER-/)

      const orders = await broker.orders()
      expect(orders[0].status).toBe(OrderStatus.Working)
      expect(orders[0].symbol).toBe('AAPL')
    })

    it('should place multiple orders independently', async () => {
      await broker.placeOrder({ symbol: 'AAPL', qty: 100 })
      await broker.placeOrder({ symbol: 'GOOGL', qty: 50 })

      const orders = await broker.orders()
      expect(orders.length).toBe(2)
    })
  })

  describe('positions', () => {
    it('should create position via mocker chain', async () => {
      await broker.placeOrder({ symbol: 'AAPL', qty: 100 })

      // Wait for mocker chain: order → execution → position
      await waitForMockerChain()

      const positions = await broker.positions()
      expect(positions[0].symbol).toBe('AAPL')
    })

    it('should handle position closing', async () => {
      // Create position first
      await broker.placeOrder({ symbol: 'AAPL', qty: 100 })
      await waitForMockerChain()

      // Close position
      await broker.closePosition('AAPL')

      const orders = await broker.orders()
      const closingOrder = orders.find((o) => o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrder).toBeDefined()
    })
  })
})

// Helper for WebSocket mocker chain
const waitForMockerChain = async (cycles = 4) => {
  // WebSocket fallback polls every 100ms
  await new Promise((resolve) => setTimeout(resolve, cycles * 100 + 50))
}
```

#### Integration Tests

```typescript
// DatafeedService tests (datafeedService.spec.ts)
import { DatafeedMock, DatafeedService } from '../datafeedService'

describe('DatafeedService', () => {
  let datafeedService: DatafeedService
  let testDatafeedMock: DatafeedMock

  beforeEach(() => {
    // Create fresh DatafeedMock instance
    testDatafeedMock = new DatafeedMock()

    // Use fallback client with test DatafeedMock instance
    datafeedService = new DatafeedService(testDatafeedMock)
  })

  it('should return datafeed configuration', async () => {
    const config = await onReadyPromise()
    expect(config.supported_resolutions).toContain('1D')
  })

  it('should generate deterministic mock bars', () => {
    const bars = testDatafeedMock.getMockedBars()
    expect(bars.length).toBe(401) // 400 days + today
    expect(bars[0].time).toBeLessThan(bars[bars.length - 1].time)
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

### Test Coverage Summary

#### BrokerTerminalService Tests (`brokerTerminalService.spec.ts`)

✅ **Comprehensive Coverage (28+ tests)**:

- Order preview with detailed sections
- Order placement (Market, Limit, Stop, StopLimit)
- Order modification and cancellation
- Position management via mocker chain
- Position closing (full/partial)
- Position bracket editing (SL/TP)
- Execution tracking
- Account information
- Leverage operations
- Multiple concurrent orders
- Edge cases and error handling

#### DatafeedService Tests (`datafeedService.spec.ts`)

✅ **Full Coverage (20+ tests)**:

- Configuration loading
- Symbol search and resolution
- Historical bars fetching
- Real-time bar subscriptions
- Quote data generation
- WebSocket subscriptions
- DatafeedMock deterministic data

### Testing Best Practices

The project uses **no external mocking** - services have built-in fallback clients:

```typescript
// ❌ Traditional mocking (NOT used)
vi.mock('@/services/apiService')

// ✅ Built-in fallback (actually used)
const brokerMock = new BrokerMock()
const broker = new BrokerTerminalService(host, datafeed, brokerMock)
```

Benefits:

- Tests use real service logic
- Deterministic mock data
- No brittle mock setups
- Runtime flexibility (can switch mock/backend)

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

## Known Issues

### AccountId Mismatch: currentAccount() vs WebSocket Subscriptions

**Issue**: `Error: Value is undefined` in TradingView Account Manager rendering

**Root Cause**: The `currentAccount()` method returns a hardcoded `'DEMO-ACCOUNT'` AccountId, but WebSocket subscriptions use a dynamically generated `listenerId` (e.g., `'ACCOUNT-abc123def456'`). This mismatch causes WebSocket updates to be sent with the wrong AccountId, preventing the Account Manager from receiving proper updates.

**Symptoms**:

- Browser console error: `Uncaught (in promise) Error: Value is undefined`
- Error occurs in `trading-account-manager` during `_render` / `_createAccountManager`
- Account Manager fails to display balance, equity, orders, or positions
- WebSocket subscriptions work but updates don't reach the UI

**Code Location**:

```typescript
// brokerTerminalService.ts - Line ~630
this.listenerId = `ACCOUNT-${Math.random().toString(36).substring(2, 15)}`
this.setupWebSocketHandlers()  // Uses listenerId for subscriptions

// brokerTerminalService.ts - Line ~878
currentAccount(): AccountId {
  return 'DEMO-ACCOUNT' as AccountId  // ❌ Mismatch!
}
```

**Why It Happens**:

1. TradingView calls `currentAccount()` to get the AccountId for UI rendering
2. The service subscribes to WebSocket events using `listenerId` as `accountId`
3. Backend sends updates with the subscription's `accountId` (listenerId)
4. TradingView expects updates for `'DEMO-ACCOUNT'` but receives them for `'ACCOUNT-abc123def456'`
5. Account Manager cannot match the AccountId and shows "Value is undefined"

**Temporary Workaround**:

```typescript
// Make currentAccount() return the same value as listenerId
private readonly accountId: AccountId = 'DEMO-ACCOUNT' as AccountId

constructor(...) {
  // Use consistent AccountId everywhere
  this.listenerId = this.accountId  // or vice versa
  this.setupWebSocketHandlers()
}

currentAccount(): AccountId {
  return this.accountId
}
```

**Proper Solution** (requires backend coordination):

1. Backend should provide the AccountId during authentication
2. Frontend should fetch AccountId asynchronously during initialization
3. Store AccountId and use it consistently for:
   - `currentAccount()` return value
   - WebSocket subscription `accountId` parameter
   - All broker API calls

**Constraints**:

- `currentAccount()` must be **synchronous** (TradingView requirement)
- Cannot `await` backend API call in `currentAccount()`
- AccountId must be known before broker initialization completes

**Related Files**:

- `frontend/src/services/brokerTerminalService.ts` (lines 630, 878)
- `frontend/src/plugins/wsAdapter.ts` (WebSocket subscription handlers)
- `backend/src/trading_api/modules/broker/service.py` (BrokerService WebSocket implementation)

**Priority**: High - Blocks Account Manager functionality

**Last Encountered**: October 22, 2025

---

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

- **Architecture Overview**: `../../ARCHITECTURE.md`
- **TradingView Types Guide**: `./TRADINGVIEW-TYPES.md`
- **Frontend README**: `../README.md`
- **Development Guide**: `../../docs/DEVELOPMENT.md`

### Source Files

- **Service Implementation**: `../src/services/brokerTerminalService.ts`
- **Chart Container**: `../src/components/TraderChartContainer.vue`
- **Datafeed Service**: `../src/services/datafeedService.ts`

---

**Maintained by**: Development Team
**Review Schedule**: Updated as features are implemented
**Last Review**: November 11, 2025

```

```
