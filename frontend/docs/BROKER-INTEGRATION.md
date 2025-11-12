# Broker Integration - Complete Implementation Guide

**Version**: 2.0.0  
**Last Updated**: November 12, 2025  
**Status**: ✅ Full Implementation - Backend Integration Complete

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [WebSocket Integration](#websocket-integration)
4. [TradingView Integration](#tradingview-integration)
5. [Implementation Status](#implementation-status)
6. [Core Features](#core-features)
7. [API Reference](#api-reference)
8. [WebSocket Data Flows](#websocket-data-flows)
9. [Implementation Methodology](#implementation-methodology)
10. [Testing Strategy](#testing-strategy)
11. [Configuration](#configuration)
12. [Known Issues](#known-issues)
13. [References](#references)

---

## Overview

The **Broker Integration** provides a complete trading environment that connects the TradingView Trading Terminal with backend broker services. It implements TradingView's Broker API (`IBrokerWithoutRealtime`) and uses a **dual-mode architecture** with smart client selection between mock fallback and real backend integration.

### Purpose

- **Production Trading**: Full-featured broker implementation with backend integration
- **Smart Client Selection**: Seamlessly switches between mock fallback and real backend
- **TradingView Integration**: Enables full Trading Terminal features (order panels, position tracking, account management)
- **Type Safety**: Uses official TradingView TypeScript types for compile-time validation
- **Real-Time Updates**: WebSocket-driven event system for immediate UI updates

### Key Characteristics

- 🔌 **Dual Mode**: Smart client selection (fallback mock or real backend)
- 🛡️ **Type-Safe**: Uses official TradingView types from `@public/trading_terminal`
- 🔄 **Backend Integration**: Full REST + WebSocket integration
- 📊 **Event-Driven**: Backend WebSocket events drive all UI updates
- 🎯 **Backend Source of Truth**: All broker state lives on backend
- ⚡ **Real-Time**: Sub-second latency for broker events
- 🧪 **Test-Friendly**: ApiInterface pattern enables seamless testing

---

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
└─────────────────────────────────────────────────────────────────┘
         │                                          │
         │ ApiInterface                             │ WebSocket Events
         ▼                                          ▼
┌──────────────────────┐              ┌──────────────────────────┐
│   ApiFallback        │              │   WsAdapter (Broker)     │
│   (Mock Client)      │              │   • orders client        │
│  • Local state       │              │   • positions client     │
│  • Instant execution │              │   • executions client    │
└──────────────────────┘              │   • equity client        │
         │ ApiInterface                └──────────┬───────────────┘
         ▼                                        │
┌──────────────────────┐                         │ Type-safe callbacks
│   ApiAdapter         │                         ▼
│   (Backend Client)   │              ┌──────────────────────────┐
│  • REST API calls    │              │   setupWebSocketHandlers │
│  • Type conversion   │              │   • Relay to _host       │
│  • Error handling    │              └──────────────────────────┘
└──────────┬───────────┘
           │ HTTP/REST
           ▼
┌──────────────────────┐
│  Backend Broker API  │
│  /api/v1/broker/*    │
│  • Process commands  │
│  • Update state      │
│  • Broadcast events  │
└──────────────────────┘
```

### Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       USER ACTIONS                               │
│  (Place Order, Modify Order, Cancel Order, Close Position)       │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        │ REST API (Commands)
                        ▼
            ┌─────────────────────────────┐
            │   ApiAdapter (REST Client)  │
            │   • placeOrder()            │
            │   • modifyOrder()           │
            │   • cancelOrder()           │
            │   • closePosition()         │
            └─────────────┬───────────────┘
                          │
                          │ HTTP POST/PUT/DELETE
                          ▼
            ┌─────────────────────────────┐
            │   Backend Broker API        │
            │   /api/v1/broker/*          │
            │   • Process commands        │
            │   • Update state            │
            │   • Broadcast events        │
            └─────────────┬───────────────┘
                          │
                          │ WebSocket Events
                          ▼
            ┌─────────────────────────────┐
            │   WsAdapter (Broker)        │
            │   • orders client           │
            │   • positions client        │
            │   • executions client       │
            │   • equity client           │
            └─────────────┬───────────────┘
                          │
                          │ Type-safe callbacks
                          ▼
            ┌─────────────────────────────┐
            │   BrokerTerminalService     │
            │   • setupWebSocketHandlers()│
            │   • Relay to _host          │
            └─────────────┬───────────────┘
                          │
                          │ IBrokerConnectionAdapterHost
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│               IBrokerConnectionAdapterHost                       │
│   • orderUpdate()        - Push order changes to TradingView    │
│   • positionUpdate()     - Push position changes                │
│   • executionUpdate()    - Push trade executions                │
│   • plUpdate()           - Push P&L updates                     │
│   • equityUpdate()       - Push equity updates                  │
│   • showNotification()   - Show user notifications              │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        │ Auto UI Updates
                        ▼
            ┌─────────────────────────────┐
            │   TradingView Terminal UI   │
            │   • Order Panel             │
            │   • Position Panel          │
            │   • Account Manager         │
            │   • Execution History       │
            └─────────────────────────────┘
```

### Component Responsibilities

| Component                         | Responsibility                                        | Communication       |
| --------------------------------- | ----------------------------------------------------- | ------------------- |
| **TradingView Terminal**          | UI rendering, user interactions                       | Calls Broker API    |
| **BrokerTerminalService**         | Implements `IBrokerWithoutRealtime`, routes to client | Delegates           |
| **ApiAdapter (REST)**             | Send commands to backend                              | HTTP → Backend      |
| **WsAdapter (WebSocket)**         | Subscribe to broker events                            | WebSocket ← Backend |
| **IBrokerConnectionAdapterHost**  | Push updates to TradingView                           | Updates UI          |
| **Backend Broker Service**        | Business logic, state management                      | Source of truth     |
| **Backend WebSocket Broadcaster** | Broadcast events to subscribers                       | Publish events      |

---

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

### WebSocket Client Pattern

The broker WebSocket clients follow the **exact same pattern** as the existing bar/quote clients:

```typescript
// frontend/src/plugins/wsAdapter.ts
import { WebSocketClient } from './wsClientBase.js'
import { mapOrder, mapPosition, mapExecution } from './mappers.js'

export class WsAdapter {
  // Existing clients
  bars: WebSocketClient<BarsSubscriptionRequest, Bar_backend, Bar>
  quotes: WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_backend, QuoteData>

  // Broker clients (same pattern!)
  orders: WebSocketClient<OrderSubscriptionRequest, Order_backend, Order>
  positions: WebSocketClient<PositionSubscriptionRequest, Position_backend, Position>
  executions: WebSocketClient<ExecutionSubscriptionRequest, Execution_backend, Execution>
  equity: WebSocketClient<EquitySubscriptionRequest, EquityData_backend, EquityData>

  constructor() {
    // Existing
    this.bars = new WebSocketClient('bars', (data) => data)
    this.quotes = new WebSocketClient('quotes', mapQuoteData)

    // Broker
    this.orders = new WebSocketClient('orders', mapOrder)
    this.positions = new WebSocketClient('positions', mapPosition)
    this.executions = new WebSocketClient('executions', mapExecution)
    this.equity = new WebSocketClient('equity', (data) => data)
  }
}
```

### Key Benefits

✅ **Singleton Connection**: All broker clients share one WebSocket connection  
✅ **Server Confirmation**: Waits for `.subscribe.response` before routing  
✅ **Auto-Reconnection**: `WebSocketBase` handles reconnection + resubscription  
✅ **Topic-Based**: `orders:{accountId}`, `positions:{accountId}`  
✅ **Type-Safe Mappers**: Backend types → Frontend types via mappers  
✅ **Reference Counting**: Auto cleanup when no subscribers

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

---

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

---

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

---

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

---

## API Reference

### Class: BrokerTerminalService

#### Constructor

```typescript
constructor(
  host: IBrokerConnectionAdapterHost,
  datafeed: IDatafeedQuotesApi,
  brokerMock?: BrokerMock
)
```

**Parameters:**

- `host`: TradingView's broker adapter host interface
- `datafeed`: Market data provider for quotes and bars
- `brokerMock`: Optional mock instance for testing/offline mode

#### Methods

##### Account Methods

###### `accountManagerInfo(): AccountManagerInfo`

Returns account panel configuration including summary fields and column definitions.

###### `accountsMetainfo(): Promise<AccountMetainfo[]>`

Returns list of available accounts.

###### `currentAccount(): AccountId`

Returns the currently active account ID.

###### `connectionStatus(): ConnectionStatus`

Returns the current broker connection status.

##### Order Methods

###### `orders(): Promise<Order[]>`

Returns all orders (working, filled, canceled).

###### `placeOrder(order: PreOrder): Promise<PlaceOrderResult>`

Places a new order.

###### `modifyOrder(order: Order): Promise<void>`

Modifies an existing order.

###### `cancelOrder(orderId: string): Promise<void>`

Cancels an existing order.

##### Position Methods

###### `positions(): Promise<Position[]>`

Returns all open positions.

##### Execution Methods

###### `executions(symbol: string): Promise<Execution[]>`

Returns execution history for a specific symbol.

##### Symbol Methods

###### `symbolInfo(symbol: string): Promise<InstrumentInfo>`

Returns trading metadata for a symbol.

###### `isTradable(): Promise<boolean>`

Checks if a symbol is tradable.

##### UI Methods

###### `chartContextMenuActions(context: TradeContext): Promise<ActionMetaInfo[]>`

Returns context menu actions for chart.

###### `formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter>`

Returns number formatter for symbol.

---

## WebSocket Data Flows

### 1. Order Updates (`orders.*`)

**Topic Pattern**: `orders:{accountId}`

**Subscribe Request**:

```typescript
interface OrderSubscriptionRequest {
  accountId: string // "DEMO-001"
}
```

**Update Message** (Backend → Frontend):

```typescript
interface OrderUpdate {
  type: 'orders.update'
  payload: Order_backend // Complete order object
}
```

**When to Broadcast**:

- Order placed (status: Working)
- Order modified (price/qty changed)
- Order filled (status: Filled, filledQty updated)
- Order partially filled (filledQty incremented)
- Order canceled (status: Canceled)
- Order rejected (status: Rejected)

### 2. Position Updates (`positions.*`)

**Topic Pattern**: `positions:{accountId}`

**When to Broadcast**:

- Position opened (after order fill)
- Position quantity changed (additional fills)
- Position closed (qty → 0)
- Position brackets updated (SL/TP changed)
- Position reversed (side flipped)

### 3. Execution Updates (`executions.*`)

**Topic Pattern**: `executions:{accountId}`

**When to Broadcast**:

- Order filled (fully or partially)
- Trade executed

### 4. Equity/P&L Updates (`equity.*`)

**Topic Pattern**: `equity:{accountId}`

**When to Broadcast**:

- Market price changes (affects unrealized P&L)
- Position closed (realized P&L)
- Balance updated
- Regular intervals (e.g., every second)

### 5. Broker Connection Status (`broker-connection.*`)

**Topic Pattern**: `broker-connection:{accountId}`

**Purpose**: Track the real connection status between backend and the actual broker (e.g., Interactive Brokers, TD Ameritrade).

**When to Broadcast**:

- Backend connects to broker
- Backend loses connection to broker
- Backend is reconnecting to broker
- Broker authentication fails
- Broker session expires

---

## Implementation Methodology

### Implementation Phases

#### Phase 1: Backend WebSocket Operations (Backend Team)

**Goal**: Create broker WebSocket endpoints and message types

**Tasks**:

1. Define backend models in `backend/src/trading_api/models/broker/`
2. Create WebSocket router `backend/src/trading_api/ws/broker.py`
3. Implement broadcast logic in broker service
4. Update AsyncAPI spec (auto-generated)
5. Test WebSocket operations

#### Phase 2: Frontend Type Generation

**Goal**: Generate TypeScript types from backend AsyncAPI spec

**Tasks**:

1. Run type generator: `cd frontend && make generate-asyncapi-types`
2. Verify generated types
3. Create data mappers in `frontend/src/plugins/mappers.ts`

#### Phase 3: Extend WsAdapter

**Goal**: Add broker WebSocket clients to `WsAdapter`

**Tasks**:

1. Update `frontend/src/plugins/wsAdapter.ts`
2. Test WebSocket subscription

#### Phase 4: Wire to IBrokerConnectionAdapterHost

**Goal**: Connect WebSocket events to TradingView Trading Host

**Tasks**:

1. Update `BrokerTerminalService` constructor
2. Implement `setupWebSocketHandlers()`
3. Update REST API methods (remove redundant UI updates)

#### Phase 5: Handle Connection State

**Goal**: Sync WebSocket connection status with TradingView

**Tasks**:

1. Track WebSocket connection state
2. Call `_host.connectionStatusUpdate()` on connect/disconnect
3. Show user notifications on connection issues
4. Handle reconnection gracefully

#### Phase 6: Testing & Validation

**Goal**: End-to-end testing of WebSocket integration

**Tasks**:

1. Unit tests for mappers
2. Integration tests (frontend + backend)
3. Manual testing

---

## Testing Strategy

### Current Testing Approach

The BrokerTerminalService is currently tested through:

1. **Manual Testing**: Interactive testing via TradingView UI
2. **Integration Testing**: Full-stack smoke tests (Playwright)
3. **Console Logging**: Debug output for development

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
describe('Broker WebSocket Integration', () => {
  it('should receive order update after placing order', async () => {
    const broker = new BrokerTerminalService(mockHost, ...)
    const orderUpdates: Order[] = []

    // Spy on host.orderUpdate
    mockHost.orderUpdate = vi.fn((order) => orderUpdates.push(order))

    // Place order via REST
    await broker.placeOrder({
      symbol: 'AAPL',
      type: OrderType.Market,
      side: Side.Buy,
      qty: 100
    })

    // Wait for WebSocket update
    await new Promise(resolve => setTimeout(resolve, 1000))

    // Verify orderUpdate was called
    expect(orderUpdates.length).toBe(1)
    expect(orderUpdates[0].symbol).toBe('AAPL')
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

---

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

### Debug Modes

#### General Debug Mode

```typescript
debug: true // Logs widget lifecycle and general events
```

#### Broker Debug Mode

```typescript
debug_broker: 'all' // Logs all broker API calls and responses
```

---

## Known Issues

### AccountId Mismatch: currentAccount() vs WebSocket Subscriptions

**Issue**: `Error: Value is undefined` in TradingView Account Manager rendering

**Root Cause**: The `currentAccount()` method returns a hardcoded `'DEMO-ACCOUNT'` AccountId, but WebSocket subscriptions use a dynamically generated `listenerId` (e.g., `'ACCOUNT-abc123def456'`). This mismatch causes WebSocket updates to be sent with the wrong AccountId, preventing the Account Manager from receiving proper updates.

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

### Project Documentation

- **Architecture Overview**: `../../ARCHITECTURE.md`
- **TradingView Types Guide**: `./tradingview/TYPE-DEFINITIONS.md`
- **Frontend README**: `../README.md`
- **Development Guide**: `../../docs/DEVELOPMENT.md`

### Source Files

- **Service Implementation**: `../src/services/brokerTerminalService.ts`
- **Chart Container**: `../src/components/TraderChartContainer.vue`
- **Datafeed Service**: `../src/services/datafeedService.ts`

---

**Maintained by**: Development Team  
**Review Schedule**: Updated as features are implemented  
**Last Review**: November 12, 2025
