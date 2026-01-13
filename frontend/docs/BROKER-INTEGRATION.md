# Broker Integration - Complete Implementation Guide

**Version**: 2.0.1  
**Last Updated**: November 30, 2025  
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
  this.accountId = "ACCOUNT-01"

  // Setup all 5 WebSocket subscriptions with error handling
  this.setupWebSocketHandlers()
    .then(() => {
      this.brokerConnectionStatus = ConnectionStatus.Connected
      this._hostAdapter.connectionStatusUpdate(this.brokerConnectionStatus, {
        message: 'Broker data subscriptions established'
      })
    }).catch((error) => {
      console.error('[BrokerTerminalService] Failed to setup WebSocket handlers:', error)
      this._hostAdapter.connectionStatusUpdate(ConnectionStatus.Error, {
        message: 'Failed to establish broker data subscriptions'
      })
    })
}
```

#### Error Handling in Setup

**Critical Pattern**: The constructor's promise chain includes `.catch()` to handle WebSocket initialization failures:

```typescript
this.setupWebSocketHandlers()
  .then(() => {
    // Success: Update connection status
    this.brokerConnectionStatus = ConnectionStatus.Connected
    this._hostAdapter.connectionStatusUpdate(this.brokerConnectionStatus, {
      message: 'Broker data subscriptions established',
    })
  })
  .catch((error) => {
    // Failure: Log error and update connection status
    console.error('[BrokerTerminalService] Failed to setup WebSocket handlers:', error)
    this._hostAdapter.connectionStatusUpdate(ConnectionStatus.Error, {
      message: 'Failed to establish broker data subscriptions',
    })
  })
```

**Why This Matters:**

- ✅ **Prevents Silent Failures**: Without `.catch()`, initialization errors are swallowed
- ✅ **Updates UI State**: Sets `ConnectionStatus.Error` to inform user of issues
- ✅ **Enables Debugging**: Logs error for developer diagnosis
- ✅ **Production Ready**: Critical for production deployments

**Source**: [brokerTerminalService.ts#L647-L660](../src/services/brokerTerminalService.ts#L647-L660)

````

### Smart Client Selection

The `_getWsAdapter()` method selects between fallback and real WebSocket:

```typescript
private _getWsAdapter(): WsAdapterType | Partial<WsAdapterType> {
  return this._wsFallback ?? this._wsAdapter
}
````

**Logic**:

- If `brokerMock` provided → Returns `WsFallback` (polling-based mock)
- If `brokerMock` absent → Returns `WsAdapter` (real WebSocket connection)

This mirrors the REST API pattern with `_getApiAdapter()`.

### Custom UI Hooks

TradingView's `customUI` configuration allows overriding default UI dialogs to fix bugs or add custom behavior.

**Purpose**: The `customUI.showPositionDialog` hook intercepts TradingView's position bracket editing to fix a bug where bracket values from chart drag operations aren't passed to the dialog.

**Implementation**:

```typescript
// frontend/src/components/TraderChartContainer.vue (lines 215-223)
customUI: {
  showPositionDialog: (
    position: Position | IndividualPosition,
    brackets: Brackets,
    focus?: OrderTicketFocusControl,
  ): Promise<boolean> => {
    // brokerService is populated by broker_factory before this is called
    return brokerService!.showPositionBracketsDialog(position, brackets, focus)
  },
}
```

**Flow**:

```
User drags TP/SL on chart
        ↓
TradingView detects bracket change
        ↓
Calls customUI.showPositionDialog(position, brackets, focus)
        ↓
TraderChartContainer hook
        ↓
BrokerTerminalService.showPositionBracketsDialog()
        ↓
_hostAdapter.showPositionBracketsDialog()
        ↓
TradingView displays native dialog with preset values ✓
```

**Without Hook**: TradingView would show empty brackets dialog, losing user's drag values.

**With Hook**: Brackets values are preserved and preset in the dialog.

#### showPositionBracketsDialog Method

The service implements a delegation method that handles the custom UI hook:

```typescript
/**
 * Delegates to host adapter's showPositionBracketsDialog.
 * Used by customUI.showPositionDialog hook to fix TradingView's bracket preset bug.
 */
showPositionBracketsDialog(
  position: Position | IndividualPosition,
  brackets: Brackets,
  focus?: OrderTicketFocusControl
): Promise<boolean> {
  // TradingView's showPositionBracketsDialog requires focus parameter (not optional)
  // Default to StopLoss if not provided
  return this._hostAdapter.showPositionBracketsDialog(
    position,
    brackets,
    focus ?? OrderTicketFocusControl.StopLoss
  )
}
```

**Key Points:**

- **Method Signature**: Accepts `Position | IndividualPosition` to support both position types
- **Focus Parameter**: TradingView requires focus control, defaults to `OrderTicketFocusControl.StopLoss`
- **Pure Delegation**: Passes through to host adapter without modification
- **Source**: [brokerTerminalService.ts#L1032-L1047](../src/services/brokerTerminalService.ts#L1032-L1047)
- **Hook Setup**: [TraderChartContainer.vue#L215-L223](../src/components/TraderChartContainer.vue#L215-L223)

### WebSocket Subscription Lifecycle

The `setupWebSocketHandlers()` method establishes 5 real-time subscriptions with error handling:

#### Subscription Pattern with Error Callbacks

```typescript
private handleSubscriptionError(
  subscriptionName: string,
  error: SubscriptionError
): void {
  throw WebSocketError.fromSubscription(error, { subscriptionName })
}

private async setupWebSocketHandlers(): Promise<(void | undefined)[]> {
  return Promise.all([
    // 1. Order updates (status changes, fills, cancellations)
    this._getWsAdapter().orders?.subscribe(
      'orders',
      { accountId: this.accountId },
      (order: PlacedOrder) => {
        this._hostAdapter.orderUpdate(omitNullish(order) as Order)

        // Show notification on fill
        if (order.status === OrderStatus.Filled) {
          this._hostAdapter.showNotification(
            'Order Filled',
            `${order.symbol} ${order.side === 1 ? 'Buy' : 'Sell'} ${order.qty} @ ${order.avgPrice ?? 'market'}`,
            NotificationType.Success
          )
        }
      },
      (error) => this.handleSubscriptionError('Orders', error)  // ← Error callback
    ),

    // 2. Position updates (new positions, quantity changes, closures)
    this._getWsAdapter().positions?.subscribe(
      'positions',
      { accountId: this.accountId },
      (position: Position) => {
        this._hostAdapter.positionUpdate(position)
      },
      (error) => this.handleSubscriptionError('Positions', error)  // ← Error callback
    ),

    // 3. Execution updates (trade confirmations)
    this._getWsAdapter().executions?.subscribe(
      'executions',
      { accountId: this.accountId },
      (execution: Execution) => {
        this._hostAdapter.executionUpdate(execution)
      },
      (error) => this.handleSubscriptionError('Executions', error)  // ← Error callback
    ),

    // 4. Equity updates (balance, equity, P&L changes)
    this._getWsAdapter().equity?.subscribe(
      'equity',
      { accountId: this.accountId },
      (data: EquityData) => {
        this._hostAdapter.equityUpdate(data.equity)

        // Update reactive balance/equity values
        if (data.balance !== undefined && data.balance !== null) {
          this.balance.setValue(data.balance)
        }
        if (data.equity !== undefined && data.equity !== null) {
          this.equity.setValue(data.equity)
        }
      },
      (error) => this.handleSubscriptionError('Equity', error)  // ← Error callback
    ),

    // 5. Broker connection status (backend ↔ real broker)
    this._getWsAdapter().brokerConnection?.subscribe(
      'broker-connection',
      { accountId: this.accountId },
      (data: BrokerConnectionStatus) => {
        this.brokerConnectionStatus = data.status
        this._hostAdapter.connectionStatusUpdate(data.status, {
          message: data.message ?? undefined,
          disconnectType: data.disconnectType ?? undefined,
        })

        // Notify user on connection changes
        if (data.status === ConnectionStatus.Disconnected) {
          this._hostAdapter.showNotification(
            'Broker Disconnected',
            data.message ?? 'Connection to broker lost',
            NotificationType.Error
          )
        } else if (data.status === ConnectionStatus.Connected) {
          this._hostAdapter.showNotification(
            'Broker Connected',
            data.message ?? 'Successfully connected to broker',
            NotificationType.Success
          )
        }
      },
      (error) => this.handleSubscriptionError('Broker Connection', error)  // ← Error callback
    ),
  ])
}
```

**Error Propagation Flow:**

```
Backend Subscription Error (e.g., provider timeout)
        ↓
WebSocket error message received
        ↓
Subscription error callback invoked
        ↓
handleSubscriptionError('Orders', error)
        ↓
WebSocketError.fromSubscription(error, { subscriptionName: 'Orders' })
        ↓
Throw WebSocketError (propagates to global handler)
        ↓
errorService.handle(error)
        ↓
Toast notification displayed to user ✓
```

**Source**: [brokerTerminalService.ts#L674-L680](../src/services/brokerTerminalService.ts#L674-L680) (error handler), [brokerTerminalService.ts#L689-L768](../src/services/brokerTerminalService.ts#L689-L768) (subscriptions)

### Subscription Details

| Subscription         | Topic                           | Purpose                         | Updates                                  |
| -------------------- | ------------------------------- | ------------------------------- | ---------------------------------------- |
| **orders**           | `orders:{accountId}`            | Real-time order status changes  | Working, Filled, Canceled, Rejected      |
| **positions**        | `positions:{accountId}`         | Position quantity/price updates | New positions, size changes, closures    |
| **executions**       | `executions:{accountId}`        | Trade confirmations             | Execution price, quantity, timestamp     |
| **equity**           | `equity:{accountId}`            | Account value changes           | Balance, equity, unrealized/realized P&L |
| **brokerConnection** | `broker-connection:{accountId}` | Connection health               | Connected, Disconnected, Error           |

**Related Documentation:**

- [WEBSOCKET-ARCHITECTURE.md#subscription-error-handling](./WEBSOCKET-ARCHITECTURE.md#subscription-error-handling) - WebSocket error handling architecture
- [ERROR-MANAGEMENT.md#websocketerror](./ERROR-MANAGEMENT.md#websocketerror) - WebSocketError class details

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
- ✅ **Backend Broadcasting**: WebSocket event broadcasting implemented

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
    positionColumns: [...], // Position panel: Symbol, Side, Qty, AvgPrice, Limit, Stop, PnL
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
    // Notify TradingView UI of the update
    this._hostAdapter.orderUpdate(order)
    console.log(`Order modified: ${order.id}`)
  }
}
```

**Critical:** The `orderUpdate()` call notifies TradingView's Trading Terminal to refresh the Order Panel UI. Without this, the UI won't reflect modifications until the next WebSocket event.

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

Modifies an existing order. **Must call `_hostAdapter.orderUpdate(order)`** after modification to sync TradingView UI.

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

##### Position Dialog Methods

###### `showPositionBracketsDialog(position: Position | IndividualPosition, brackets: Brackets, focus?: OrderTicketFocusControl): Promise<boolean>`

Display TradingView's native position brackets (SL/TP) dialog with preset values.

**Purpose**: Fix TradingView's bracket preset bug where TP/SL values from chart drag operations aren't passed to the edit dialog.

**Parameters**:

- `position`: Current position to edit
- `brackets`: Preset bracket values (stopLoss, takeProfit, trailingStopPips)
- `focus`: Optional control to focus ('stop-loss', 'take-profit', or 'trailing-stop')

**Returns**: Promise resolving to `true` if user confirmed changes, `false` if canceled

**Usage**: Called by `customUI.showPositionDialog` hook in TraderChartContainer when user drags TP/SL lines on chart.

**Implementation**:

```typescript
// frontend/src/services/brokerTerminalService.ts (lines 1027-1036)
showPositionBracketsDialog(
  position: Position | IndividualPosition,
  brackets: Brackets,
  focus?: OrderTicketFocusControl
): Promise<boolean> {
  console.log(`BrokerTerminalService.showPositionBracketsDialog[${position.id}]`)
  return this._hostAdapter.showPositionBracketsDialog(position, brackets, focus)
}
```

**Delegation Chain**:

1. User drags TP/SL line on chart
2. TradingView calls `customUI.showPositionDialog(position, brackets, focus)`
3. TraderChartContainer hook delegates to `brokerService.showPositionBracketsDialog()`
4. BrokerTerminalService delegates to `_hostAdapter.showPositionBracketsDialog()`
5. TradingView displays native dialog with preset values

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

### TradingView Order Type Discrimination: Nullish Fields Break Union Typing

**Issue**: After page refresh, bracket orders display incorrectly - parent orders appear disconnected from children, phantom orders appear with no price labels, and duplicate price labels on correct orders.

**Root Cause**: TradingView's `Order` type is a discriminated union: `type Order = PlacedOrder | BracketOrder`. The discrimination relies on **key presence**, not value truthiness:

- `PlacedOrder`: Does NOT have `parentId` or `parentType` fields
- `BracketOrder`: Has **required** `parentId: string` and `parentType: ParentType`

When backend sends `{ parentId: null, parentType: null }`, TypeScript structural typing sees the **presence** of these keys and treats the object as `BracketOrder`. But `null` is not a valid `string` or `ParentType`, causing TradingView's internal type guards to fail silently.

**Solution**: Use `omitNullish()` utility on frontend mappers to **remove** null/undefined fields entirely before passing orders to TradingView:

```typescript
// ❌ WRONG - TradingView sees parentId key, treats as BracketOrder
return { id: '123', parentId: null, parentType: null, ... }

// ✅ CORRECT - No parentId key, TradingView treats as PlacedOrder
return omitNullish({ id: '123', parentId: null, parentType: null, ... })
// Result: { id: '123', ... }
```

**Affected Areas**:

- `frontend/src/plugins/mappers.ts` - Order mapping functions
- `frontend/src/plugins/wsAdapter.ts` - WebSocket order event handlers
- Any code path that converts backend `PlacedOrder` to TradingView `Order`

**Priority**: High - Causes visual corruption in order display after refresh

**Date Identified**: January 12, 2026

---

### TradingView Bundle Issues

#### Position Bracket Pre-Population

**Issue**: Position edit dialog from Account Manager doesn't pre-fill Take Profit and Stop Loss fields, even though bracket orders exist on the position.

**Status**: ✅ RESOLVED (January 13, 2026)

**Root Cause**: TradingView passes empty `brackets` parameter to `customUI.showPositionDialog` hook when opening from Account Manager. The `Position` interface lacks `stopLoss`/`takeProfit` fields - bracket orders are stored separately with `parentId` and `parentType` fields.

**Solution**: Enhanced `customUI.showPositionDialog` hook to fetch bracket orders from `orders()` API and enrich the brackets parameter before showing the dialog.

**Implementation**: `frontend/src/components/TraderChartContainer.vue` (lines 217-252)

**Code Pattern**:

```typescript
customUI: {
  showPositionDialog: async (position, brackets, focus) => {
    let enrichedBrackets = brackets
    try {
      const orders = await brokerService.orders()
      const bracketOrders = orders.filter(
        (o) => o.parentId === position.id && o.parentType === ParentType.Position,
      )
      enrichedBrackets = {
        stopLoss: bracketOrders.find((o) => o.stopPrice)?.stopPrice,
        takeProfit: bracketOrders.find((o) => o.limitPrice && !o.stopPrice)?.limitPrice,
      }
    } catch (e) {
      console.warn('Failed to fetch bracket orders:', e)
    }
    return brokerService.showPositionBracketsDialog(position, enrichedBrackets, focus)
  }
}
```

**Documentation**: See [BUNDLE-MAINTENANCE.md](./tradingview/BUNDLE-MAINTENANCE.md) Case Study 1 for detailed analysis.

---

#### Position Dialog Field Sync

**Issue**: Fields don't auto-sync in position edit dialog - changing the **Price** field doesn't update **Ticks** and **$** fields (unlike order dialog which works correctly).

**Status**: ✅ RESOLVED (January 13, 2026)

**Root Cause**: Position dialog's `_equity$` and `_quotes$` observables created with `fromEventPattern()` **without** `startWith()` operators, causing them to never emit initial values. This blocks RxJS `combineLatest` from firing, preventing the sync handler from executing.

**Solution**: Added `.pipe(startWith(...))` to both observables in `Pt` class (PositionViewModel) to match the working pattern from `bt` class (OrderViewModel).

**Files Modified**: `frontend/public/trading_terminal/bundles/order-view-controller.4f3dc6de299e33f3954b.js`

**Changes**:

1. Line 5506-5513: Added `.pipe(startWith({ ask: position.avgPrice, bid: position.avgPrice }))` to `_quotes$`
2. Line 5515-5523: Added `.pipe(startWith(NaN))` to `_equity$`

**Code Pattern**:

```javascript
// Before (BROKEN): No initial emission
this._equity$ = T(fromEventPattern(subscribeEquity))

// After (FIXED): Emits immediately
this._equity$ = T(fromEventPattern(subscribeEquity).pipe((0, m.startWith)(NaN)))
```

**RxJS Pattern**: `combineLatest` requires **ALL** source observables to emit at least once before firing. Event-based observables from `fromEventPattern` must include `startWith()` to emit initial values.

**Documentation**: See [BUNDLE-MAINTENANCE.md](./tradingview/BUNDLE-MAINTENANCE.md) Case Study 2 for detailed technical analysis.

**Note**: All debug console logs preserved as comments for future reference.

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

- **Architecture Overview**: `../../docs/ARCHITECTURE.md`
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
