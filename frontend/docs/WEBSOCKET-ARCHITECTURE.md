# WebSocket Architecture

**Date**: November 12, 2025  
**Status**: ✅ Production Ready  
**Version**: 3.0.0 (Consolidated)

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Core Components](#core-components)
4. [Design Patterns](#design-patterns)
5. [Implementation Reference](#implementation-reference)
6. [Implementation Guide](#implementation-guide)
7. [Usage Examples](#usage-examples)
8. [Testing Approach](#testing-approach)
9. [Best Practices](#best-practices)

---

## Overview

This document describes the complete **WebSocket Architecture** implemented in the Trading Pro frontend. The architecture provides a robust, type-safe foundation for real-time data streaming that integrates with the modular FastAPI/FastWS backend architecture.

### Key Features

- ✅ **Singleton Pattern** - One WebSocket connection per backend module
- ✅ **Modular Architecture** - Separate connections for broker and datafeed modules
- ✅ **Mapper-Based Transformations** - Type-safe data conversions (backend ↔ frontend)
- ✅ **Adapter Facade** - Clean, unified API via `WsAdapter`
- ✅ **Fallback Support** - Seamless mock data for offline development
- ✅ **Type Safety** - Full TypeScript generics support with generated types
- ✅ **Auto-Reconnection** - Automatic resubscription on disconnect
- ✅ **Reference Counting** - Automatic cleanup when last subscriber disconnects
- ✅ **Server Confirmation** - Waits for subscription acknowledgment
- ✅ **Topic-Based Routing** - Filters messages to relevant subscribers

### Design Philosophy

**Services Never Track State** ⭐

The fundamental design principle is that services (like `DatafeedService` or `BrokerTerminalService`) **never** track subscription state. All subscription management happens centrally in `WebSocketBase`.

```typescript
// ✅ Good - Service just passes through
class DatafeedService {
  subscribeBars(listenerId, params, callback) {
    // No subscription Map needed!
    return this.wsAdapter.bars.subscribe(listenerId, params, callback)
  }
}

// ❌ Bad - Don't duplicate state
class DatafeedService {
  private subscriptions = new Map() // NO! Base client handles this
}
```

---

## Architecture Diagrams

### 1. Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Application Layer                                  │
│  (Vue Components, TradingView Integration)                                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 │ Uses services
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                          Service Layer                                      │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────────┐  │
│  │ DatafeedService     │  │ BrokerTerminalService                       │  │
│  │                     │  │                                             │  │
│  │ - subscribeBars()   │  │ - subscribeOrders()                         │  │
│  │ - subscribeQuotes() │  │ - subscribePositions()                      │  │
│  │ - unsubscribeBars() │  │ - subscribeExecutions()                     │  │
│  └──────────┬──────────┘  └──────────┬──────────────────────────────────┘  │
└─────────────┼────────────────────────┼─────────────────────────────────────┘
              │                        │
              │ Uses wsAdapter         │
              │                        │
┌─────────────▼────────────────────────▼─────────────────────────────────────┐
│                          Adapter Layer (Facade)                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ WsAdapter implements WsAdapterType                                    │ │
│  │ ┌───────────────────────┐  ┌───────────────────────────────────────┐ │ │
│  │ │ Datafeed Clients      │  │ Broker Clients                        │ │ │
│  │ │ ─────────────────────  │  │ ──────────────────────────────────────│ │ │
│  │ │ bars: WsClient        │  │ orders: WsClient                      │ │ │
│  │ │ quotes: WsClient      │  │ positions: WsClient                   │ │ │
│  │ │                       │  │ executions: WsClient                  │ │ │
│  │ │                       │  │ equity: WsClient                      │ │ │
│  │ │                       │  │ brokerConnection: WsClient            │ │ │
│  │ └───────┬───────────────┘  └───────┬───────────────────────────────┘ │ │
│  └──────────┼──────────────────────────┼─────────────────────────────────┘ │
└─────────────┼──────────────────────────┼─────────────────────────────────┘
              │                          │
              │ All clients use          │
              │                          │
┌─────────────▼──────────────────────────▼─────────────────────────────────────┐
│                          Client Layer                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ WebSocketClient<TParams, TBackendData, TData>                          │ │
│  │                                                                         │ │
│  │ - ws: WebSocketBase (singleton reference)                              │ │
│  │ - wsRoute: string (e.g., 'bars', 'orders')                             │ │
│  │ - dataMapper: (TBackendData) => TData                                  │ │
│  │ - listeners: Map<listenerId, Set<topic>>                               │ │
│  │                                                                         │ │
│  │ Methods:                                                                │ │
│  │ - subscribe(listenerId, params, callback): Promise<topic>              │ │
│  │ - unsubscribe(listenerId, topic?): Promise<void>                       │ │
│  └────────────────────────────────┬───────────────────────────────────────┘ │
└───────────────────────────────────┼───────────────────────────────────────┘
                                    │
                                    │ Uses singleton + mapper
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                          Base + Mapper Layers                               │
│  ┌───────────────────────────┐  ┌───────────────────────────────────────┐  │
│  │ WebSocketBase (Singleton) │  │ Mappers (mappers.ts)                  │  │
│  │ ───────────────────────── │  │ ──────────────────────────────────────│  │
│  │ Per URL singleton         │  │ mapQuoteData(backend) → frontend      │  │
│  │                           │  │ mapOrder(backend) → frontend          │  │
│  │ - getInstance(url)        │  │ mapPosition(backend) → frontend       │  │
│  │ - subscriptions: Map      │  │ mapExecution(backend) → frontend      │  │
│  │ - pendingRequests: Map    │  │ mapEquityData(backend) → frontend     │  │
│  │ - ws: WebSocket           │  │ mapBrokerConnectionStatus(...)        │  │
│  │                           │  │                                       │  │
│  │ - subscribe(...)          │  │ Type isolation:                       │  │
│  │ - unsubscribe(...)        │  │ Backend types ONLY in mappers.ts      │  │
│  │ - sendRequest(...)        │  │ Services NEVER import backend types   │  │
│  │ - handleMessage(...)      │  │                                       │  │
│  │ - resubscribeAll()        │  │                                       │  │
│  └───────────┬───────────────┘  └───────────────────────────────────────┘  │
└───────────────┼─────────────────────────────────────────────────────────────┘
                │
                │ Uses native API
                │
┌───────────────▼─────────────────────────────────────────────────────────────┐
│                          Native Browser API                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ WebSocket (Browser Native)                                            │ │
│  │ - send(message)                                                        │ │
│  │ - close()                                                              │ │
│  │ - onopen, onmessage, onerror, onclose                                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Modular Backend Integration

```
Frontend WsAdapter                 Backend Modules
──────────────────────             ───────────────

┌─────────────────────┐
│ WsAdapter           │
│                     │
│ Datafeed Clients    │  ─────────────────────────┐
│ ─────────────────── │                           │
│ • bars              │  ──┐                      │
│ • quotes            │    │                      │
└─────────────────────┘    │  WebSocketBase       │
                           │  singleton for:      │
                           │  /v1/datafeed/ws     │
                           └──────────────────────┼──────────┐
                                                  │          │
                                                  ▼          │
                           ┌──────────────────────────────┐  │
                           │ Backend: datafeed module     │  │
                           │ /v1/datafeed/ws              │  │
                           │                              │  │
                           │ Routers:                     │  │
                           │ • bars.subscribe             │  │
                           │ • bars.unsubscribe           │  │
                           │ • bars.update (pub-sub)      │  │
                           │ • quotes.subscribe           │  │
                           │ • quotes.unsubscribe         │  │
                           │ • quotes.update (pub-sub)    │  │
                           └──────────────────────────────┘  │
                                                              │
┌─────────────────────┐                                      │
│ WsAdapter           │                                      │
│                     │                                      │
│ Broker Clients      │  ─────────────────────────┐         │
│ ─────────────────── │                           │         │
│ • orders            │  ──┐                      │         │
│ • positions         │    │                      │         │
│ • executions        │    │  WebSocketBase       │         │
│ • equity            │    │  singleton for:      │         │
│ • brokerConnection  │    │  /v1/broker/ws       │         │
└─────────────────────┘    └──────────────────────┼─────────┼─────┐
                                                  │         │     │
                                                  ▼         │     │
                           ┌──────────────────────────────┐  │     │
                           │ Backend: broker module       │  │     │
                           │ /v1/broker/ws                │  │     │
                           │                              │  │     │
                           │ Routers:                     │  │     │
                           │ • orders.subscribe           │  │     │
                           │ • orders.update (pub-sub)    │  │     │
                           │ • positions.subscribe        │  │     │
                           │ • positions.update           │  │     │
                           │ • executions.subscribe       │  │     │
                           │ • executions.update          │  │     │
                           │ • equity.subscribe           │  │     │
                           │ • equity.update              │  │     │
                           │ • broker-connection.subscribe│  │     │
                           │ • broker-connection.update   │  │     │
                           └──────────────────────────────┘  │     │
                                                              │     │
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓     │
┃ Result: 2 WebSocket Connections Total                     ┃     │
┃ - One per backend module                                  ┃     │
┃ - Efficient resource usage                                ┃     │
┃ - Module independence (deploy separately)                 ┃     │
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛     │
       │                                                            │
       └────────────────────────────────────────────────────────────┘
                       Both connections active simultaneously
```

**Key Architectural Pattern**:

- Each backend module has its own WebSocket endpoint
- Frontend maintains one `WebSocketBase` singleton per module endpoint
- All clients for a module share the same WebSocket connection
- Mappers isolate backend types to single layer

### 3. Singleton Pattern per URL

```
Initial State:
┌───────────────────────────────────────┐
│ WebSocketBase.instances = Map()       │
│ (empty)                               │
└───────────────────────────────────────┘

Step 1: bars client created (URL: /v1/datafeed/ws)
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase { ... }  ◄── NEW INSTANCE      │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
         │ Returns reference to singleton
         ▼
┌──────────────────┐
│ bars client      │ ──> uses WebSocketBase('/v1/datafeed/ws')
└──────────────────┘

Step 2: quotes client created (URL: /v1/datafeed/ws)
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase { ... }  ◄── SAME INSTANCE!    │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
         │ Returns reference to SAME singleton
         ▼
┌──────────────────┐    ┌──────────────────┐
│ bars client      │    │ quotes client    │
└──────────────────┘    └──────────────────┘
         │                       │
         └───────────┬───────────┘
                     │ Both use SAME WebSocket connection
                     ▼
          WebSocketBase('/v1/datafeed/ws')

Final State: 2 Singleton Instances
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase { ... },   ◄── Shared by 2     │
│   '/v1/broker/ws' => WebSocketBase { ... }      ◄── Shared by 5     │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 4. Subscription Lifecycle

```
Service Call:
┌────────────────────────────────────────────────────────────────────┐
│ datafeedService.subscribeBars('listener-1', 'AAPL', '1', callback) │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ wsAdapter.bars.subscribe('listener-1', {symbol:'AAPL',res:'1'}, cb)│
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketClient.subscribe()                                        │
│ 1. Build topic: "bars:AAPL:1"                                      │
│ 2. Track listener in local map                                     │
│ 3. Wrap callback with mapper                                       │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.subscribe()                                          │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Check if subscription exists?                                  │ │
│ │ ┌───────────┐         ┌──────────────────┐                    │ │
│ │ │ Yes:      │         │ No:              │                    │ │
│ │ │ Add       │         │ Create new       │                    │ │
│ │ │ listener  │         │ subscription     │                    │ │
│ │ │ to        │         │ state            │                    │ │
│ │ │ existing  │         └──────┬───────────┘                    │ │
│ │ │ (ref      │                │                                │ │
│ │ │ counting) │                ▼                                │ │
│ │ └───────────┘         Send subscribe request to server        │ │
│ │      │                       │                                │ │
│ │      │                       ▼                                │ │
│ │      │                Wait for confirmation (5s timeout)      │ │
│ │      │                       │                                │ │
│ │      │              ┌────────▼────────┐                       │ │
│ │      │              │ Success?        │                       │ │
│ │      │         Yes ─┤                 ├─ No                   │ │
│ │      │              │                 │                       │ │
│ │      ▼              ▼                 ▼                       │ │
│ │   Mark subscription            Delete subscription            │ │
│ │   as confirmed                 Throw error                    │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ Result: Subscription active, listener registered                   │
└────────────────────────────────────────────────────────────────────┘
```

### 5. Message Routing

```
Backend sends update:
┌────────────────────────────────────────────────────────────────────┐
│ {                                                                  │
│   "type": "bars.update",                                           │
│   "topic": "bars:AAPL:1",                                          │
│   "data": { time: 1234567890, open: 150.0, ... }                  │
│ }                                                                  │
└────────────┬───────────────────────────────────────────────────────┘
             │ WebSocket.onmessage
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.handleMessage()                                      │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Parse message                                                  │ │
│ │                                                                │ │
│ │ Is response to request? (has request_id)                      │ │
│ │ ┌─────────┐              ┌───────────┐                        │ │
│ │ │ Yes:    │              │ No:       │                        │ │
│ │ │ Resolve │              │ Is update?│                        │ │
│ │ │ pending │              │ (*.update)│                        │ │
│ │ │ request │              └────┬──────┘                        │ │
│ │ └─────────┘                   │                               │ │
│ │                               ▼                               │ │
│ │                        Find subscription by topic             │ │
│ │                               │                               │ │
│ │                        ┌──────▼──────┐                        │ │
│ │                        │ Confirmed?  │                        │ │
│ │                        │             │                        │ │
│ │                   Yes ─┤             ├─ No (ignore)           │ │
│ │                        └──────┬──────┘                        │ │
│ │                               ▼                               │ │
│ │                   Broadcast to all listeners                  │ │
│ │                               │                               │ │
│ │                    ┌──────────┴──────────┐                   │ │
│ │                    ▼                      ▼                   │ │
│ │              listener1(data)        listener2(data)           │ │
│ │              (with error isolation)                           │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketClient applies mapper: backendData → frontendData         │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ Service callback executes (frontend types only)                    │
└────────────────────────────────────────────────────────────────────┘
```

### 6. Reference Counting

```
Initial State: 2 listeners for "bars:AAPL:1"
┌────────────────────────────────────────────────────────────────────┐
│ subscriptions.get("bars:AAPL:1") = {                               │
│   topic: "bars:AAPL:1",                                            │
│   confirmed: true,                                                 │
│   listeners: Map {                                                 │
│     'listener-1' => callback1,                                     │
│     'listener-2' => callback2                                      │
│   }                                                                │
│ }                                                                  │
└────────────────────────────────────────────────────────────────────┘

Event: listener-1 unsubscribes
→ Remove listener-1
→ listeners.size > 0? YES → Keep subscription active

Updated State: 1 listener remains
┌────────────────────────────────────────────────────────────────────┐
│ subscriptions.get("bars:AAPL:1") = {                               │
│   topic: "bars:AAPL:1",                                            │
│   confirmed: true,                                                 │
│   listeners: Map { 'listener-2' => callback2 }                    │
│ }                                                                  │
└────────────────────────────────────────────────────────────────────┘

Event: listener-2 unsubscribes (last listener!)
→ Remove listener-2
→ listeners.size = 0 → Send unsubscribe to server + delete subscription

Final State: Subscription removed
┌────────────────────────────────────────────────────────────────────┐
│ subscriptions.has("bars:AAPL:1") = false  ◄── Cleaned up!         │
└────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Data Mappers (`mappers.ts`)

**Responsibility**: Type-safe data transformations between backend and frontend types

**Key Features**:

- Strict naming conventions (`_Api_Backend`, `_Ws_Backend` suffixes)
- Centralized mapper functions for reuse
- Handles backend → frontend type conversions
- Enum mapping (order types, sides, statuses)
- Null/undefined handling
- Only place where backend types are imported

**Example Mappers**:

```typescript
// Per-module backend types with strict naming
import type { QuoteData as QuoteData_Ws_Backend } from '@clients/ws-types-datafeed_v1'
import type {
  PlacedOrder as PlacedOrder_Ws_Backend,
  Position as Position_Ws_Backend,
} from '@clients/ws-types-broker_v1'

// Frontend types
import type { QuoteData, PlacedOrder, Position } from '@public/trading_terminal/charting_library'

// Mapper functions
export function mapQuoteData(quote: QuoteData_Ws_Backend): QuoteData {
  if (quote.s === 'error') {
    return { s: 'error', n: quote.n, v: quote.v }
  }
  return { s: 'ok', n: quote.n, v: { ...quote.v } }
}

export function mapOrder(order: PlacedOrder_Ws_Backend): PlacedOrder {
  return {
    id: order.id,
    symbol: order.symbol,
    type: order.type as unknown as PlacedOrder['type'],
    side: order.side as unknown as PlacedOrder['side'],
    qty: order.qty,
    status: order.status as unknown as PlacedOrder['status'],
    // ... more fields
  }
}
```

**Critical Pattern**: Backend types are **only** imported in `mappers.ts`. Services never import them directly.

### 2. WebSocket Adapter (`wsAdapter.ts`)

**Responsibility**: Unified facade for all WebSocket clients

**Key Features**:

- Type-safe client access via `WsAdapterType` interface
- Per-module WebSocket URLs
- Mapper functions passed to clients at construction
- Clean separation between datafeed and broker clients

**Implementation**:

```typescript
export type WsAdapterType = {
  // Datafeed module clients
  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>

  // Broker module clients
  orders: WebSocketInterface<OrderSubscriptionRequest, PlacedOrder>
  positions: WebSocketInterface<PositionSubscriptionRequest, Position>
  executions: WebSocketInterface<ExecutionSubscriptionRequest, Execution>
  equity: WebSocketInterface<EquitySubscriptionRequest, EquityData>
  brokerConnection: WebSocketInterface<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>
}

export class WsAdapter implements WsAdapterType {
  constructor() {
    // Datafeed module WebSocket URL
    const datafeedWsUrl = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + '/v1/datafeed/ws'

    // Create datafeed clients with mappers
    this.bars = new WebSocketClient<BarsSubscriptionRequest, Bar_Ws_Backend, Bar>(
      datafeedWsUrl,
      'bars',
      (data) => data, // Identity mapper
    )

    this.quotes = new WebSocketClient<
      QuoteDataSubscriptionRequest,
      QuoteData_Ws_Backend,
      QuoteData
    >(datafeedWsUrl, 'quotes', mapQuoteData)

    // Broker module WebSocket URL
    const brokerWsUrl = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + '/v1/broker/ws'

    // Create broker clients with mappers
    this.orders = new WebSocketClient<
      OrderSubscriptionRequest,
      PlacedOrder_Ws_Backend,
      PlacedOrder
    >(brokerWsUrl, 'orders', mapOrder)
    // ... other clients
  }
}
```

### 3. Fallback Adapter (`WsFallback`)

**Responsibility**: Mock WebSocket clients for offline development

**Key Features**:

- Implements same `WsAdapterType` interface
- Uses `WebSocketFallback` clients that generate mock data
- Configurable mock data generators
- Useful for development without backend

### 4. Base WebSocket Client (`WebSocketBase`)

**File**: `frontend/src/plugins/wsClientBase.ts`

**Responsibility**: Singleton WebSocket connection per URL with centralized subscription management

**Key Features**:

- Singleton pattern (one instance per WebSocket URL)
- Connection lifecycle management
- Message routing to subscribers
- Centralized subscription state (services don't track)
- Auto-reconnection with resubscription
- Server-confirmed subscriptions

**Critical Pattern**: Services **never** track subscription state locally. All subscription management happens in `WebSocketBase`.

**Class Definition**:

```typescript
export class WebSocketBase {
  // Singleton management
  private static instances = new Map<string, WebSocketBase>()

  // Connection state
  protected ws: WebSocket | null = null
  protected wsUrl: string
  protected isReconnecting: boolean = false
  protected reconnectAttempts: number = 0

  // Subscription state (centralized!)
  protected subscriptions = new Map<string, SubscriptionState>()

  // Message handling
  protected pendingRequests = new Map<string, PendingRequest>()

  // Singleton accessor
  static getInstance(wsUrl: string): WebSocketBase {
    if (!WebSocketBase.instances.has(wsUrl)) {
      WebSocketBase.instances.set(wsUrl, new WebSocketBase(wsUrl))
    }
    return WebSocketBase.instances.get(wsUrl)!
  }

  // Private constructor
  private constructor(wsUrl: string) {
    this.wsUrl = wsUrl
    this.connect()
  }
}
```

**Key Interfaces**:

```typescript
export interface SubscriptionState {
  topic: string // e.g., "bars:AAPL:1"
  subscriptionType: string // e.g., "bars.subscribe"
  subscriptionParams: object // Original params
  confirmed: boolean // Server confirmed?
  listeners: Map<string, (data: object) => void> // All callbacks
}
```

### 5. Generic WebSocket Client (`WebSocketClient<TParams, TBackendData, TData>`)

**Responsibility**: Generic WebSocket client with mapper integration

**Type Parameters**:

- `TParams`: Subscription parameters (frontend types)
- `TBackendData`: Backend data type (from generated types)
- `TData`: Frontend data type (after mapper transformation)

**Implementation**:

```typescript
export class WebSocketClient<
  TParams extends object,
  TBackendData extends object,
  TData extends object,
> implements WebSocketInterface<TParams, TData>
{
  protected ws: WebSocketBase
  protected listeners: Map<string, Set<string>>
  private wsRoute: string
  private dataMapper: (data: TBackendData) => TData

  constructor(wsUrl: string, wsRoute: string, dataMapper: (data: TBackendData) => TData) {
    this.wsRoute = wsRoute
    this.dataMapper = dataMapper
    this.ws = WebSocketBase.getInstance(wsUrl) // Singleton!
    this.listeners = new Map()
  }

  async subscribe(
    listenerId: string,
    subscriptionParams: TParams,
    onUpdate: (data: TData) => void,
  ): Promise<string> {
    const topic = `${this.wsRoute}:${buildTopicParams(subscriptionParams)}`

    // Track listener
    if (this.listeners.has(listenerId)) {
      this.listeners.get(listenerId)!.add(topic)
    } else {
      this.listeners.set(listenerId, new Set([topic]))
    }

    // Subscribe via base with mapper
    await this.ws.subscribe(
      topic,
      this.wsRoute + '.subscribe',
      subscriptionParams,
      listenerId,
      (backendData: object) => {
        onUpdate(this.dataMapper(backendData as TBackendData))
      },
    )

    return topic
  }
}
```

---

## Design Patterns

### 1. Singleton Pattern ⭐

**Problem**: Multiple WebSocket connections to the same backend module waste resources.

**Solution**: One `WebSocketBase` instance per WebSocket URL.

**Benefits**:

- One connection per backend module
- Automatic connection sharing
- Resource efficiency

### 2. Facade Pattern ⭐

**Problem**: Services need simple, unified API for multiple WebSocket clients.

**Solution**: `WsAdapter` provides clean interface hiding complexity.

**Benefits**:

- Single import point
- Clean service code
- Easy to swap implementations

### 3. Strategy Pattern (Mappers) ⭐

**Problem**: Backend and frontend use different type definitions.

**Solution**: Mapper functions as transformation strategy.

**Benefits**:

- Type-safe transformations
- Centralized conversion logic
- Reusable across REST and WebSocket

### 4. Observer Pattern ⭐

**Problem**: Multiple consumers need to react to data updates.

**Solution**: Callback-based subscription system with reference counting.

**Benefits**:

- Multiple subscribers per topic
- Automatic cleanup
- Decoupled communication

### 5. Adapter Pattern ⭐

**Problem**: Need to support both real and mock WebSocket clients.

**Solution**: Common `WebSocketInterface` implemented by both.

**Benefits**:

- Seamless real ↔ mock switching
- Easy testing
- Offline development support

---

## Implementation Reference

### Subscription Lifecycle

**Subscribe Flow**:

```typescript
async subscribe(
  topic: string,
  subscriptionType: string,
  subscriptionParams: object,
  listenerId: string,
  onUpdate: (data: object) => void
): Promise<SubscriptionState> {
  // Step 1: Check if subscription exists
  let subscription = this.subscriptions.get(topic)

  if (subscription) {
    // Reuse existing subscription - just add listener
    subscription.listeners.set(listenerId, onUpdate)
    return subscription
  }

  // Step 2: Create new subscription (unconfirmed)
  subscription = {
    topic,
    subscriptionParams,
    subscriptionType,
    confirmed: false,
    listeners: new Map([[listenerId, onUpdate]])
  }
  this.subscriptions.set(topic, subscription)

  // Step 3: Send subscribe request to server
  try {
    const response = await this.sendRequestWithTimeout(
      subscriptionType,
      subscriptionParams,
      5000 // 5 second timeout
    )

    // Step 4: Verify server response
    if (response.status === 'ok') {
      subscription.confirmed = true
    } else {
      throw new Error(`Subscription failed: ${response.message}`)
    }

    return subscription
  } catch (error) {
    // Cleanup on failure
    this.subscriptions.delete(topic)
    throw error
  }
}
```

**Unsubscribe Flow**:

```typescript
async unsubscribe(listenerId: string, topic?: string): Promise<void> {
  if (!topic) {
    // Unsubscribe from all topics for this listener
    for (const [currentTopic, subscription] of this.subscriptions) {
      if (subscription.listeners.has(listenerId)) {
        await this.unsubscribeFromTopic(listenerId, currentTopic)
      }
    }
    return
  }

  await this.unsubscribeFromTopic(listenerId, topic)
}

private async unsubscribeFromTopic(listenerId: string, topic: string): Promise<void> {
  const subscription = this.subscriptions.get(topic)
  if (!subscription) return

  // Remove listener
  subscription.listeners.delete(listenerId)

  // If no more listeners, unsubscribe from server
  if (subscription.listeners.size === 0) {
    try {
      await this.sendRequestWithTimeout(
        subscription.subscriptionType.replace('.subscribe', '.unsubscribe'),
        subscription.subscriptionParams,
        5000
      )
    } finally {
      this.subscriptions.delete(topic)
    }
  }
}
```

### Connection Management

**Automatic Reconnection**:

```typescript
protected handleClose(event: CloseEvent): void {
  console.log(`[WebSocketBase] Connection closed: ${event.code}`)

  if (!this.isReconnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
    this.scheduleReconnect()
  }
}

protected scheduleReconnect(): void {
  if (this.isReconnecting) return

  this.isReconnecting = true
  this.reconnectAttempts++

  // Exponential backoff: 1s, 2s, 4s, 8s, 16s
  const delay = Math.min(
    this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
    16000
  )

  setTimeout(() => {
    this.connect()
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.resubscribeAll()
    }
  }, delay)
}
```

**Resubscription on Reconnect**:

```typescript
protected async resubscribeAll(): Promise<void> {
  console.log(`[WebSocketBase] Resubscribing to ${this.subscriptions.size} topics`)

  for (const [topic, subscription] of this.subscriptions) {
    try {
      const response = await this.sendRequestWithTimeout(
        subscription.subscriptionType,
        subscription.subscriptionParams,
        5000
      )

      if (response.status === 'ok') {
        subscription.confirmed = true
      } else {
        subscription.confirmed = false
      }
    } catch (error) {
      console.error(`[WebSocketBase] Resubscription error for ${topic}:`, error)
      subscription.confirmed = false
    }
  }
}
```

---

## Implementation Guide

### Step 1: Generate Backend Types

```bash
cd frontend
make generate-asyncapi-types
```

**Output**: `src/clients_generated/ws-types-{module}_v{version}/`

### Step 2: Create Mapper Functions

Add mappers in `mappers.ts`:

```typescript
import type { NewDataType as NewDataType_Ws_Backend } from '@clients/ws-types-broker_v1'
import type { NewDataType } from '@public/trading_terminal'

export function mapNewData(data: NewDataType_Ws_Backend): NewDataType {
  return {
    field1: data.field1,
    field2: data.field2 as unknown as NewDataType['field2'],
    field3: data.field3 ?? undefined,
  }
}
```

### Step 3: Update WsAdapter

```typescript
export type WsAdapterType = {
  // ... existing clients
  newData: WebSocketInterface<NewDataSubscriptionRequest, NewDataType>
}

export class WsAdapter implements WsAdapterType {
  newData: WebSocketInterface<NewDataSubscriptionRequest, NewDataType>

  constructor() {
    // ... existing clients

    const moduleWsUrl = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + '/v1/module/ws'
    this.newData = new WebSocketClient<
      NewDataSubscriptionRequest,
      NewDataType_Ws_Backend,
      NewDataType
    >(moduleWsUrl, 'new-data', mapNewData)
  }
}
```

### Step 4: Use in Service

```typescript
export class MyService {
  private wsAdapter: WsAdapterType

  constructor() {
    this.wsAdapter = new WsAdapter()
  }

  async subscribeToNewData(
    id: string,
    params: NewDataSubscriptionRequest,
    callback: (data: NewDataType) => void,
  ) {
    try {
      await this.wsAdapter.newData.subscribe(id, params, callback)
    } catch (error) {
      console.error('Subscription failed:', error)
    }
  }

  async unsubscribe(id: string) {
    await this.wsAdapter.newData.unsubscribe(id)
  }
}
```

---

## Usage Examples

### Basic Subscription

```typescript
import { WsAdapter } from '@/plugins/wsAdapter'

const adapter = new WsAdapter()

// Subscribe to bars
const topic = await adapter.bars.subscribe(
  'listener-1',
  { symbol: 'AAPL', resolution: '1' },
  (bar) => {
    console.log('Bar received:', bar)
  },
)

// Later: unsubscribe
await adapter.bars.unsubscribe('listener-1')
```

### Service Integration Pattern

```typescript
export class DatafeedService {
  private wsAdapter: WsAdapterType

  constructor() {
    this.wsAdapter = new WsAdapter()
  }

  subscribeBars(
    listenerGuid: string,
    symbolInfo: LibrarySymbolInfo,
    resolution: ResolutionString,
    onRealtimeCallback: SubscribeBarsCallback,
  ): void {
    // Services don't track subscriptions - base client handles it!
    this.wsAdapter.bars.subscribe(
      listenerGuid,
      { symbol: symbolInfo.name, resolution },
      (bar: Bar) => {
        onRealtimeCallback(bar)
      },
    )
  }

  unsubscribeBars(listenerGuid: string): void {
    // Just pass through - base client handles cleanup
    this.wsAdapter.bars.unsubscribe(listenerGuid)
  }
}
```

### Mock Data for Testing

```typescript
import { WsFallback } from '@/plugins/wsAdapter'

const mockAdapter = new WsFallback({
  barsMocker: () => ({
    time: Date.now() / 1000,
    open: 150.0,
    high: 151.0,
    low: 149.5,
    close: 150.5,
    volume: 1000000,
  }),
})

// Use same interface as real adapter!
await mockAdapter.bars?.subscribe('test', params, callback)
```

---

## Testing Approach

### Unit Tests

**Test Mappers**:

```typescript
import { mapQuoteData } from '@/plugins/mappers'

describe('mapQuoteData', () => {
  it('should map success quote', () => {
    const backend = {
      s: 'ok',
      n: 'AAPL',
      v: { lp: 150.0, bid: 149.9, ask: 150.1 },
    }
    const frontend = mapQuoteData(backend)
    expect(frontend.s).toBe('ok')
    expect(frontend.v.lp).toBe(150.0)
  })
})
```

**Test with Mock Adapter**:

```typescript
import { WsFallback } from '@/plugins/wsAdapter'

describe('DatafeedService', () => {
  it('should handle bar updates', async () => {
    const mockAdapter = new WsFallback({
      barsMocker: () => ({ time: 123, open: 150 /* ... */ }),
    })

    const service = new DatafeedService()
    service.setAdapter(mockAdapter) // Inject mock

    const bars: Bar[] = []
    service.subscribeBars('test', symbolInfo, '1', (bar) => bars.push(bar))

    await wait(200)
    expect(bars.length).toBeGreaterThan(0)
  })
})
```

### Integration Tests

```typescript
describe('WebSocket Integration', () => {
  it('should receive real-time updates', async () => {
    const adapter = new WsAdapter()
    const bars: Bar[] = []

    await adapter.bars.subscribe('test', { symbol: 'AAPL', resolution: '1' }, (bar) => {
      bars.push(bar)
    })

    await wait(5000)
    expect(bars.length).toBeGreaterThan(0)
  })
})
```

---

## Best Practices

### 1. Always Use WsAdapter

```typescript
// ✅ Good
const adapter = new WsAdapter()
await adapter.bars.subscribe(...)

// ❌ Bad - don't instantiate WebSocketClient directly
const client = new WebSocketClient(...)
```

### 2. Never Import Backend Types in Services

```typescript
// ✅ Good - use frontend types
import type { QuoteData } from '@public/trading_terminal'

// ❌ Bad - backend types only in mappers.ts
import type { QuoteData } from '@clients/ws-types-datafeed_v1'
```

### 3. Use Mappers for All Data Transformations

```typescript
// ✅ Good - mapper handles conversion
export function mapOrder(order: Order_Ws_Backend): Order { ... }

// ❌ Bad - inline conversion
const frontendOrder = { ...backendOrder, type: backendOrder.type as any }
```

### 4. Handle Errors Gracefully

```typescript
try {
  await adapter.orders.subscribe(id, params, callback)
} catch (error) {
  console.error('Subscription failed:', error)
  // Fall back to mock data or show error to user
}
```

### 5. Clean Up Subscriptions

```typescript
// Unsubscribe when no longer needed
onUnmounted(() => {
  adapter.bars.unsubscribe(listenerId)
})
```

### 6. Use Environment Variables for URLs

```typescript
const basePath = import.meta.env.VITE_TRADER_API_BASE_PATH || ''
const wsUrl = basePath + '/v1/datafeed/ws'
```

### 7. Monitor Connection State

```typescript
adapter.bars.subscribe(id, params, (bar) => {
  console.debug('[Datafeed] Bar received:', bar)
})
```

---

## Conclusion

The WebSocket architecture provides a robust, type-safe foundation for real-time data streaming in Trading Pro. Key strengths:

- ✅ **Modular Architecture** - Separate connections per backend module
- ✅ **Mapper Isolation** - Backend types confined to single layer
- ✅ **Facade Simplicity** - Clean service code via WsAdapter
- ✅ **Singleton Efficiency** - One connection per module
- ✅ **Type Safety** - Full TypeScript support with generated types
- ✅ **Fallback Support** - Seamless offline development
- ✅ **Automatic Reconnection** - Zero-impact failover
- ✅ **Reference Counting** - Automatic resource cleanup

---

**Version**: 3.0.0 (Consolidated)  
**Date**: November 12, 2025  
**Status**: ✅ Production Ready  
**Maintainers**: Development Team

**Note**: This document consolidates the previous separate documents:

- `WEBSOCKET-CLIENT-PATTERN.md` (v2.0.0)
- `WEBSOCKET-CLIENT-BASE.md` (v2.0.0)
- `WEBSOCKET-ARCHITECTURE-DIAGRAMS.md` (v2.0.0)
