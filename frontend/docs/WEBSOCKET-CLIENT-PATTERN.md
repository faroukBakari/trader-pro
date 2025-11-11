# WebSocket Client Implementation Pattern

**Date**: November 11, 2025  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Design Patterns](#design-patterns)
5. [Implementation Guide](#implementation-guide)
6. [Usage Examples](#usage-examples)
7. [Modular Backend Integration](#modular-backend-integration)
8. [Testing Approach](#testing-approach)
9. [Best Practices](#best-practices)

---

## Overview

This document describes the **WebSocket Client Pattern** implemented in the Trading Pro frontend. The pattern provides a robust, type-safe foundation for real-time data streaming that integrates with the modular FastAPI/FastWS backend architecture.

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

---

## Architecture

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                           │
│  (DatafeedService, BrokerTerminalService, etc.)                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ Uses WsAdapterType interface
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     Adapter Layer                               │
│  WsAdapter (Real) or WsFallback (Mock)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ bars: WebSocketClient<BarsSubReq, Bar_Backend, Bar>     │   │
│  │ quotes: WebSocketClient<QuoteSubReq, Quote_Backend, Quote>│ │
│  │ orders: WebSocketClient<OrderSubReq, Order_Backend, Order>│ │
│  │ positions: WebSocketClient<PosSubReq, Pos_Backend, Pos> │   │
│  │ executions: WebSocketClient<ExecSubReq, Exec_Backend, Exec>│ │
│  │ equity: WebSocketClient<EquitySubReq, Equity_Backend, Equity>│
│  │ brokerConnection: WebSocketClient<ConnSubReq, Conn_Backend, Conn>│
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ Uses mappers for data transformation
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     Mapper Layer                                │
│  (mappers.ts)                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ mapQuoteData(backend) → frontend                         │   │
│  │ mapOrder(backend) → frontend                             │   │
│  │ mapPosition(backend) → frontend                          │   │
│  │ mapExecution(backend) → frontend                         │   │
│  │ mapEquityData(backend) → frontend                        │   │
│  │ mapBrokerConnectionStatus(backend) → frontend            │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ Extends/Uses
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     Client Layer                                │
│  WebSocketClient<TParams, TBackendData, TData>                 │
│  - Generic WebSocket client                                     │
│  - Topic building via buildTopicParams()                        │
│  - Data transformation via mapper function                      │
│  - Subscription lifecycle management                            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ Uses singleton
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     Base Layer                                  │
│  WebSocketBase (Singleton per URL)                             │
│  - WebSocket protocol handling                                  │
│  - Connection management                                        │
│  - Message routing to subscribers                               │
│  - Subscription state tracking                                  │
│  - Auto-reconnection with resubscription                        │
└─────────────────────────────────────────────────────────────────┘
```

### Modular Backend Integration

```
Frontend Modules → Backend Modules (Separate WebSocket Endpoints)

┌──────────────────────┐
│  WsAdapter           │
│  ┌────────────────┐  │
│  │ Datafeed       │  │ ──→ ws://host/v1/datafeed/ws
│  │ - bars         │  │       │
│  │ - quotes       │  │       └─→ WebSocketBase (singleton)
│  └────────────────┘  │
│  ┌────────────────┐  │
│  │ Broker         │  │ ──→ ws://host/v1/broker/ws
│  │ - orders       │  │       │
│  │ - positions    │  │       └─→ WebSocketBase (singleton)
│  │ - executions   │  │
│  │ - equity       │  │
│  │ - connection   │  │
│  └────────────────┘  │
└──────────────────────┘
```

**Key Architectural Pattern**:

- Each backend module has its own WebSocket endpoint
- Frontend maintains one `WebSocketBase` singleton per module endpoint
- All clients for a module share the same WebSocket connection
- Mappers isolate backend types to single layer

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
  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  orders: WebSocketInterface<OrderSubscriptionRequest, PlacedOrder>
  // ... other clients

  constructor() {
    // Datafeed module WebSocket URL
    const datafeedWsUrl = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + '/v1/datafeed/ws'

    // Create datafeed clients with mappers
    this.bars = new WebSocketClient<BarsSubscriptionRequest, Bar_Ws_Backend, Bar>(
      datafeedWsUrl,
      'bars',
      (data) => data, // Identity mapper for bars
    )

    this.quotes = new WebSocketClient<
      QuoteDataSubscriptionRequest,
      QuoteData_Ws_Backend,
      QuoteData
    >(
      datafeedWsUrl,
      'quotes',
      mapQuoteData, // Mapper function
    )

    // Broker module WebSocket URL
    const brokerWsUrl = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + '/v1/broker/ws'

    // Create broker clients with mappers
    this.orders = new WebSocketClient<
      OrderSubscriptionRequest,
      PlacedOrder_Ws_Backend,
      PlacedOrder
    >(brokerWsUrl, 'orders', mapOrder)

    // ... other broker clients
  }
}
```

**Benefits**:

- Single import point for services
- Centralized WebSocket configuration
- Type-safe client access
- Easy to swap implementations (real ↔ mock)

### 3. Fallback Adapter (`WsFallback`)

**Responsibility**: Mock WebSocket clients for offline development

**Key Features**:

- Implements same `WsAdapterType` interface
- Uses `WebSocketFallback` clients that generate mock data
- Configurable mock data generators
- Useful for development without backend

**Implementation**:

```typescript
export interface wsMocker {
  barsMocker?: () => Bar | undefined
  quotesMocker?: () => QuoteData | undefined
  ordersMocker?: () => PlacedOrder | undefined
  // ... more mockers
}

export class WsFallback implements Partial<WsAdapterType> {
  bars?: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes?: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  // ... other clients

  constructor(wsMocker: wsMocker) {
    // Only create clients for provided mockers
    if (wsMocker.barsMocker) {
      this.bars = new WebSocketFallback<BarsSubscriptionRequest, Bar>(
        wsMocker.barsMocker.bind(wsMocker),
      )
    }

    if (wsMocker.quotesMocker) {
      this.quotes = new WebSocketFallback<QuoteDataSubscriptionRequest, QuoteData>(
        wsMocker.quotesMocker.bind(wsMocker),
      )
    }
    // ... more clients
  }
}
```

### 4. Base WebSocket Client (`WebSocketBase`)

**Responsibility**: Singleton WebSocket connection per URL with centralized subscription management

**Key Features**:

- Singleton pattern (one instance per WebSocket URL)
- Connection lifecycle management
- Message routing to subscribers
- Centralized subscription state (services don't track)
- Auto-reconnection with resubscription
- Server-confirmed subscriptions

**Critical Pattern**: Services **never** track subscription state locally. All subscription management happens in `WebSocketBase`.

**Implementation** (see [WEBSOCKET-CLIENT-BASE.md](./WEBSOCKET-CLIENT-BASE.md) for details):

```typescript
export class WebSocketBase {
  private static instances = new Map<string, WebSocketBase>()
  protected subscriptions = new Map<string, SubscriptionState>()

  // Singleton per URL
  static getInstance(wsUrl: string): WebSocketBase {
    if (!WebSocketBase.instances.has(wsUrl)) {
      WebSocketBase.instances.set(wsUrl, new WebSocketBase(wsUrl))
    }
    return WebSocketBase.instances.get(wsUrl)!
  }

  // Subscribe with server confirmation
  async subscribe(
    topic: string,
    subscriptionType: string,
    subscriptionParams: object,
    listenerId: string,
    onUpdate: (data: object) => void
  ): Promise<SubscriptionState> {
    // Create or reuse subscription
    let subscription = this.subscriptions.get(topic)
    if (subscription) {
      subscription.listeners.set(listenerId, onUpdate)
      return subscription
    }

    // Create new subscription
    subscription = {
      topic,
      subscriptionParams,
      subscriptionType,
      confirmed: false,
      listeners: new Map([[listenerId, onUpdate]])
    }
    this.subscriptions.set(topic, subscription)

    // Send subscribe request and wait for confirmation
    const response = await this.sendRequestWithTimeout(...)
    if (response.status === 'ok') {
      subscription.confirmed = true
    }

    return subscription
  }

  // Auto-cleanup when last listener unsubscribes
  async unsubscribe(listenerId: string, topic: string): Promise<void> {
    const subscription = this.subscriptions.get(topic)
    if (!subscription) return

    subscription.listeners.delete(listenerId)

    // Cleanup if no more listeners
    if (subscription.listeners.size === 0) {
      await this.sendRequest(unsubscribeType, params)
      this.subscriptions.delete(topic)
    }
  }
}
```

### 5. Generic WebSocket Client (`WebSocketClient<TParams, TBackendData, TData>`)

**Responsibility**: Generic WebSocket client with mapper integration

**Type Parameters**:

- `TParams`: Subscription parameters (frontend types)
- `TBackendData`: Backend data type (from generated types)
- `TData`: Frontend data type (after mapper transformation)

**Key Features**:

- Uses `WebSocketBase` singleton
- Topic building via `buildTopicParams()`
- Data transformation via mapper function
- Listener tracking per subscription

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
    // Build topic from params
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

  async unsubscribe(listenerId: string, topic?: string): Promise<void> {
    if (!this.listeners.has(listenerId)) return
    this.listeners.delete(listenerId)
    await this.ws.unsubscribe(listenerId, topic)
  }
}
```

**Benefits**:

- Type-safe at every layer
- Mapper function applied automatically
- Backend types never leak to services
- Reference counting built-in

---

## Design Patterns

### 1. Singleton Pattern ⭐

**Problem**: Multiple WebSocket connections to the same backend module waste resources.

**Solution**: One `WebSocketBase` instance per WebSocket URL.

**Implementation**:

```typescript
class WebSocketBase {
  private static instances = new Map<string, WebSocketBase>()

  static getInstance(wsUrl: string): WebSocketBase {
    if (!WebSocketBase.instances.has(wsUrl)) {
      WebSocketBase.instances.set(wsUrl, new WebSocketBase(wsUrl))
    }
    return WebSocketBase.instances.get(wsUrl)!
  }
}
```

**Benefits**:

- One connection per backend module
- Automatic connection sharing
- Resource efficiency

### 2. Facade Pattern ⭐

**Problem**: Services need simple, unified API for multiple WebSocket clients.

**Solution**: `WsAdapter` provides clean interface hiding complexity.

**Implementation**:

```typescript
export class WsAdapter implements WsAdapterType {
  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  // ... all clients

  constructor() {
    // Internal: creates all clients with proper mappers
  }
}

// Service usage - simple!
const adapter = new WsAdapter()
await adapter.bars.subscribe(listenerId, params, callback)
```

**Benefits**:

- Single import point
- Clean service code
- Easy to swap implementations

### 3. Strategy Pattern (Mappers) ⭐

**Problem**: Backend and frontend use different type definitions.

**Solution**: Mapper functions as transformation strategy.

**Implementation**:

```typescript
// Define mapper strategy
type DataMapper<TBackend, TFrontend> = (data: TBackend) => TFrontend

// Use in client
new WebSocketClient(url, route, mapQuoteData) // Strategy injected
```

**Benefits**:

- Type-safe transformations
- Centralized conversion logic
- Reusable across REST and WebSocket

### 4. Observer Pattern ⭐

**Problem**: Multiple consumers need to react to data updates.

**Solution**: Callback-based subscription system with reference counting.

**Implementation**:

```typescript
interface SubscriptionState {
  topic: string
  listeners: Map<string, (data: object) => void> // Multiple observers
  confirmed: boolean
}

// Subscribe adds listener
subscription.listeners.set(listenerId, onUpdate)

// Broadcast to all listeners
for (const onUpdate of subscription.listeners.values()) {
  onUpdate(data)
}
```

**Benefits**:

- Multiple subscribers per topic
- Automatic cleanup
- Decoupled communication

### 5. Adapter Pattern ⭐

**Problem**: Need to support both real and mock WebSocket clients.

**Solution**: Common `WebSocketInterface` implemented by both.

**Implementation**:

```typescript
export interface WebSocketInterface<TParams, TData> {
  subscribe(id: string, params: TParams, onUpdate: (data: TData) => void): Promise<string>
  unsubscribe(id: string): Promise<void>
}

// Real implementation
export class WebSocketClient<TParams, TBackendData, TData>
  implements WebSocketInterface<TParams, TData> { ... }

// Mock implementation
export class WebSocketFallback<TParams, TData>
  implements WebSocketInterface<TParams, TData> { ... }

// Service doesn't care which!
constructor(adapter: WsAdapterType) {
  this.adapter = adapter
}
```

**Benefits**:

- Seamless real ↔ mock switching
- Easy testing
- Offline development support

---

## Implementation Guide

### Step 1: Generate Backend Types

Backend types are auto-generated from AsyncAPI specs:

```bash
# Generate WebSocket types from backend specs
cd frontend
make generate-asyncapi-types
```

**Output**: `src/clients_generated/ws-types-{module}_v{version}/`

### Step 2: Create Mapper Functions

Add mappers in `mappers.ts` for any new data types:

```typescript
// Import backend type with strict naming
import type { NewDataType as NewDataType_Ws_Backend } from '@clients/ws-types-broker_v1'

// Import frontend type
import type { NewDataType } from '@public/trading_terminal'

// Create mapper
export function mapNewData(data: NewDataType_Ws_Backend): NewDataType {
  return {
    field1: data.field1,
    field2: data.field2 as unknown as NewDataType['field2'], // Enum conversion
    field3: data.field3 ?? undefined, // Null handling
  }
}
```

### Step 3: Update WsAdapter

Add new client to `WsAdapter`:

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
  quotesMocker: () => ({
    s: 'ok',
    n: 'AAPL',
    v: { lp: 150.0, bid: 149.9, ask: 150.1 /* ... */ },
  }),
})

// Use same interface as real adapter!
await mockAdapter.bars?.subscribe('test', params, callback)
```

### Error Handling

```typescript
try {
  await adapter.orders.subscribe(listenerId, params, (order) => {
    console.log('Order update:', order)
  })
} catch (error) {
  if (error.message.includes('timeout')) {
    console.error('Server did not respond in time')
  } else if (error.message.includes('Topic mismatch')) {
    console.error('Server returned unexpected topic')
  } else {
    console.error('Subscription failed:', error)
  }
}
```

---

## Modular Backend Integration

### Backend Module Structure

```
backend/src/trading_api/modules/
├── datafeed/
│   └── ws/v1/  → WebSocket endpoint: /v1/datafeed/ws
│       ├── bars router
│       └── quotes router
└── broker/
    └── ws/v1/  → WebSocket endpoint: /v1/broker/ws
        ├── orders router
        ├── positions router
        ├── executions router
        ├── equity router
        └── broker-connection router
```

### Frontend Adapter Mapping

```typescript
// WsAdapter constructor maps to backend modules

// Datafeed module clients
const datafeedWsUrl = '/v1/datafeed/ws'
this.bars = new WebSocketClient(datafeedWsUrl, 'bars', mapper)
this.quotes = new WebSocketClient(datafeedWsUrl, 'quotes', mapper)

// Broker module clients
const brokerWsUrl = '/v1/broker/ws'
this.orders = new WebSocketClient(brokerWsUrl, 'orders', mapper)
this.positions = new WebSocketClient(brokerWsUrl, 'positions', mapper)
this.executions = new WebSocketClient(brokerWsUrl, 'executions', mapper)
this.equity = new WebSocketClient(brokerWsUrl, 'equity', mapper)
this.brokerConnection = new WebSocketClient(brokerWsUrl, 'broker-connection', mapper)
```

### Connection Pooling

```
Frontend maintains 2 WebSocket connections:

ws://host/v1/datafeed/ws  →  WebSocketBase singleton
  ├─ bars client
  └─ quotes client

ws://host/v1/broker/ws    →  WebSocketBase singleton
  ├─ orders client
  ├─ positions client
  ├─ executions client
  ├─ equity client
  └─ brokerConnection client
```

**Benefits**:

- Efficient resource usage (2 connections for all features)
- Module independence (datafeed can deploy separately)
- Clean separation of concerns

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

    await wait(200) // Wait for mock updates
    expect(bars.length).toBeGreaterThan(0)
  })
})
```

### Integration Tests

**Test with Real Backend**:

```typescript
describe('WebSocket Integration', () => {
  it('should receive real-time updates', async () => {
    const adapter = new WsAdapter()
    const bars: Bar[] = []

    await adapter.bars.subscribe('test', { symbol: 'AAPL', resolution: '1' }, (bar) => {
      bars.push(bar)
    })

    await wait(5000) // Wait for updates from backend
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
// Configure base path via env
const basePath = import.meta.env.VITE_TRADER_API_BASE_PATH || ''
const wsUrl = basePath + '/v1/datafeed/ws'
```

### 7. Monitor Connection State

```typescript
// Log important events for debugging
adapter.bars.subscribe(id, params, (bar) => {
  console.debug('[Datafeed] Bar received:', bar)
})
```

---

## Conclusion

The WebSocket client pattern provides a robust, type-safe foundation for real-time data streaming in Trading Pro. Key strengths:

- ✅ **Modular Architecture** - Separate connections per backend module
- ✅ **Mapper Isolation** - Backend types confined to single layer
- ✅ **Facade Simplicity** - Clean service code via WsAdapter
- ✅ **Singleton Efficiency** - One connection per module
- ✅ **Type Safety** - Full TypeScript support with generated types
- ✅ **Fallback Support** - Seamless offline development

### Next Steps

1. **Add New Clients** - Extend WsAdapter for new data types
2. **Enhance Mappers** - Add transformations for new backend types
3. **Monitor Performance** - Track connection metrics and latency
4. **Improve Error Handling** - Add retry strategies and fallbacks

---

**Version**: 2.0.0  
**Date**: November 11, 2025  
**Status**: ✅ Production Ready  
**Maintainers**: Development Team
