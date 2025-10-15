# WebSocket Client Implementation Pattern

**Date**: October 13, 2025
**Status**: ✅ Production Ready
**Version**: 1.0.0

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Design Patterns](#design-patterns)
5. [Implementation Details](#implementation-details)
6. [Usage Examples](#usage-examples)
7. [Auto-Generation Strategy](#auto-generation-strategy)
8. [Integration Guide](#integration-guide)
9. [Testing Approach](#testing-approach)
10. [Best Practices](#best-practices)

---

## Overview

This document describes the **WebSocket Client Pattern** implemented in the Trading Pro frontend. The pattern provides a robust, type-safe, and reusable foundation for creating WebSocket clients that integrate seamlessly with FastAPI's FastWS-based backend.

### Key Features

- ✅ **Singleton Pattern** - One WebSocket connection per URL
- ✅ **Auto-Connection** - Automatic connection with exponential backoff retry
- ✅ **Type Safety** - Full TypeScript generics support
- ✅ **Server Confirmation** - Waits for subscription acknowledgment before routing messages
- ✅ **Topic-Based Routing** - Filters messages to relevant subscribers
- ✅ **Reference Counting** - Automatic cleanup when no longer needed
- ✅ **Reconnection Logic** - Automatic resubscription on reconnect
- ✅ **Zero Dependencies** - Uses native WebSocket API
- ✅ **Factory Pattern** - Clean instantiation API
- ✅ **Interface-Based** - Easy to mock and test

---

## Architecture

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                           │
│  (DatafeedService, OrderService, AccountService, etc.)          │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ Uses interface
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     Client Layer                                │
│  (BarsWebSocketClient, QuotesWebSocketClient, etc.)            │
│  - Domain-specific logic                                        │
│  - Topic building                                               │
│  - Factory method                                               │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ Extends/Composes
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                     Base Layer                                  │
│  (WebSocketClientBase)                                          │
│  - WebSocket protocol handling                                  │
│  - Connection management                                        │
│  - Message routing                                              │
│  - Singleton management                                         │
│  - Subscription tracking                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                      Message Flow                                │
└──────────────────────────────────────────────────────────────────┘

1. SUBSCRIPTION REQUEST
   ┌──────────────┐
   │ DatafeedSvc  │
   └──────┬───────┘
          │ subscribeToBars('AAPL', '1', callback)
          ▼
   ┌──────────────────┐
   │ BarsWSClient     │  topic = 'bars:AAPL:1'
   └──────┬───────────┘
          │ subscribe<BarsSubReq, Bar>(...)
          ▼
   ┌──────────────────┐
   │ WSClientBase     │  Create subscription state (unconfirmed)
   └──────┬───────────┘
          │ sendRequest('bars.subscribe', {...})
          ▼
   ┌──────────────────┐
   │ WebSocket        │
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │ Backend (FastWS) │
   └──────┬───────────┘
          │
          ▼ { type: 'bars.subscribe.response', payload: { status: 'ok', topic: 'bars:AAPL:1' } }
   ┌──────────────────┐
   │ WSClientBase     │  Verify topic & status → Mark confirmed
   └──────┬───────────┘
          │ return subscriptionId
          ▼
   ┌──────────────────┐
   │ DatafeedSvc      │  Store subscriptionId
   └──────────────────┘


2. DATA UPDATE
   ┌──────────────────┐
   │ Backend          │  Broadcasts bar update
   └──────┬───────────┘
          │ { type: 'bars.update', payload: { time: ..., open: ..., ... } }
          ▼
   ┌──────────────────┐
   │ WebSocket        │
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │ WSClientBase     │  Route to confirmed subscriptions with matching updateType
   └──────┬───────────┘
          │ for each confirmed subscription with updateType === 'bars.update'
          ▼
   ┌──────────────────┐
   │ BarsWSClient     │  onTick(bar)
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │ DatafeedSvc      │  Forward to TradingView
   └──────────────────┘
```

---

## Core Components

## Pattern Components

### 1. Base Client (`wsClientBase.ts`)

**Responsibility**: Generic WebSocket connection and **centralized subscription management**

**Key Features**:
- Singleton pattern (one connection per URL)
- Generic types: `WebSocketClientBase<TRequest, TData>`
- Connection lifecycle management
- Message routing
- **Centralized subscription state** - single source of truth ⭐
- Auto-reconnection with exponential backoff
- **Services don't track subscriptions** - base client handles it all ⭐

### 2. BarsWebSocketClient (`barsClient.ts`)

**Purpose**: Bars-specific WebSocket client implementation.

**Key Responsibilities**:
- Topic building for bars: `bars:{SYMBOL}:{RESOLUTION}`
- Factory method for client creation
- Type mapping: `BarsSubscriptionRequest` → `Bar`
- Implements `IBarDataSource` interface

**Implementation**:
```typescript
export class BarsWebSocketClient implements IBarDataSource {
  private instance: WebSocketClientBase

  private constructor(instance: WebSocketClientBase) {
    this.instance = instance
  }

  // Factory method with auto-connection
  static async create(config: WebSocketClientConfig): Promise<BarsWebSocketClient> {
    const instance = await WebSocketClientBase.getInstance(config)
    return new BarsWebSocketClient(instance)
  }

  async subscribeToBars(
    symbol: string,
    resolution: string,
    onTick: (bar: Bar) => void
  ): Promise<string> {
    const topic = `bars:${symbol}:${resolution}`
    return this.instance.subscribe<BarsSubscriptionRequest, Bar>(
      'bars.subscribe',
      { symbol, resolution },
      topic,
      'bars.update',
      onTick
    )
  }
}
```

### 3. Factory Interface Pattern (`barsClient.ts`)

**Purpose**: Clean, type-safe factory for creating WebSocket clients.

**Benefits**:
- Hides complex instantiation logic
- Enforces singleton pattern
- Provides a clean API surface
- Easy to mock for testing

**Pattern**:
```typescript
// Export interface for type safety
export type BarsWebSocketInterface = WebSocketInterface<BarsSubscriptionRequest, Bar>

// Export factory function
export function BarsWebSocketClientFactory(): BarsWebSocketInterface {
  return new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
}
```

### 4. Integration Pattern (`datafeedService.ts`)

**Purpose**: How services use WebSocket clients.

**Pattern**:
```typescript
export class DatafeedService implements IBasicDataFeed, IDatafeedQuotesApi {
  private wsClient: BarsWebSocketInterface | null = null

  constructor() {
    // Initialize WebSocket client using factory
    this.wsClient = BarsWebSocketClientFactory()
  }

  async subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    onTick: SubscribeBarsCallback,
    listenerGuid: string,
    onResetCacheNeededCallback?: () => void,
  ): void {
    if (!this.wsClient) {
      console.error('[Datafeed] WebSocket client not initialized')
      return
    }

    // Subscribe via WebSocket
    this.wsClient
      .subscribe({ symbol: symbolInfo.name, resolution }, (bar) => {
        onTick(bar)
      })
      .then((wsSubscriptionId) => {
        // Store subscription info
        this.subscriptions.set(listenerGuid, {
          symbolInfo,
          resolution,
          onTick,
          onResetCacheNeeded: onResetCacheNeededCallback,
          wsSubscriptionId,
        })
      })
      .catch((error) => {
        console.error('[Datafeed] WebSocket subscription failed:', error)
      })
  }
}
```

---

## Design Patterns

### 1. Singleton Pattern ⭐

**Problem**: Multiple WebSocket connections to the same server waste resources.

**Solution**: Singleton ensures one WebSocket connection per URL.

**Implementation**:
```typescript
class WebSocketClientBase {
  private static instances = new Map<string, WebSocketClientBase>()
  private referenceCount = 0

  static async getInstance(config: WebSocketClientConfig): Promise<WebSocketClientBase> {
    const url = config.url
    let instance = WebSocketClientBase.instances.get(url)

    if (!instance) {
      instance = new WebSocketClientBase(config)
      WebSocketClientBase.instances.set(url, instance)
      await instance.connectWithRetries() // Auto-connect
    }

    instance.referenceCount++
    return instance
  }

  async releaseInstance(): Promise<void> {
    this.referenceCount--
    if (this.referenceCount <= 0) {
      // Cleanup: close connection, remove from instances
      await this.disconnect()
      WebSocketClientBase.instances.delete(this.config.url)
    }
  }
}
```

**Benefits**:
- Resource efficiency (one connection per URL)
- Automatic connection sharing
- Reference counting for safe cleanup
- No duplicate handshakes or heartbeats

### 2. Factory Pattern ⭐

**Problem**: Complex instantiation logic should be hidden from consumers.

**Solution**: Factory method encapsulates creation and auto-connection.

**Implementation**:
```typescript
// Public factory API
export function BarsWebSocketClientFactory(): BarsWebSocketInterface {
  return new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
}

// Usage
const wsClient = BarsWebSocketClientFactory()
```

**Benefits**:
- Simple, clean API
- Hides complexity
- Easy to swap implementations
- Testability (mock factory)

### 3. Repository Pattern ⭐

**Problem**: Services shouldn't depend on concrete implementations.

**Solution**: Interface-based design allows swapping data sources.

**Implementation**:
```typescript
// Interface
export interface IBarDataSource {
  subscribe(params: BarsSubscriptionRequest, onUpdate: (data: Bar) => void): Promise<string>
  unsubscribe(listenerGuid: string): Promise<void>
}

// Real implementation
class BarsWebSocketClient implements IBarDataSource { ... }

// Mock implementation (for testing)
class MockBarDataSource implements IBarDataSource { ... }

// Service depends on interface
class DatafeedService {
  constructor(private dataSource: IBarDataSource) {}
}
```

**Benefits**:
- Dependency inversion
- Easy to mock for testing
- Supports multiple implementations
- Gradual migration (mock → WebSocket)

### 4. Observer Pattern ⭐

**Problem**: Multiple consumers need to react to data updates.

**Solution**: Callback-based subscription system.

**Implementation**:
```typescript
interface SubscriptionState<TParams, TData> {
  id: string
  topic: string
  onUpdate: (data: TData) => void  // Observer callback
  confirmed: boolean
  subscriptionType: string
  subscriptionParams: TParams
  updateMessageType: string
}

// Subscribe with callback
await client.subscribe(params, (bar: Bar) => {
  console.log('New bar:', bar)  // Observer gets notified
})
```

**Benefits**:
- Decoupled communication
- Multiple observers per topic
- Type-safe callbacks
- Easy to unsubscribe

### 5. Promise-Based Async API ⭐

**Problem**: WebSocket operations are asynchronous.

**Solution**: Promises for subscription confirmation.

**Implementation**:
```typescript
async subscribe(...): Promise<string> {
  // Send request
  await this.sendRequest(subscriptionType, subscriptionParams)

  // Wait for server confirmation
  const response = await new Promise<SubscriptionResponse>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Timeout')), 5000)
    this.pendingRequests.set(requestId, { resolve, reject, timeout })
  })

  // Verify response
  if (response.status !== 'ok') {
    throw new Error(response.message)
  }

  return subscriptionId
}
```

**Benefits**:
- Modern async/await syntax
- Proper error handling
- Server confirmation guaranteed
- Timeout protection

---

## Implementation Details

### Message Protocol

All WebSocket messages follow this structure:

```typescript
interface WebSocketMessage<T = unknown> {
  type: string      // Operation identifier
  payload?: T       // Optional payload
}
```

**Example Messages**:

**Subscribe Request** (Client → Server):
```json
{
  "type": "bars.subscribe",
  "payload": {
    "symbol": "AAPL",
    "resolution": "1"
  }
}
```

**Subscribe Response** (Server → Client):
```json
{
  "type": "bars.subscribe.response",
  "payload": {
    "status": "ok",
    "message": "Subscribed to AAPL",
    "topic": "bars:AAPL:1"
  }
}
```

**Data Update** (Server → Client):
```json
{
  "type": "bars.update",
  "payload": {
    "time": 1697097600000,
    "open": 150.0,
    "high": 151.0,
    "low": 149.5,
    "close": 150.5,
    "volume": 1000000
  }
}
```

### Topic Structure

Topics follow the pattern: `{domain}:{key1}:{key2}:...`

**Examples**:
- `bars:AAPL:1` - Apple, 1-minute bars
- `bars:GOOGL:5` - Alphabet, 5-minute bars
- `quotes:TSLA` - Tesla quotes
- `trades:MSFT` - Microsoft trades

**Topic Builder Pattern**:
```typescript
function bars_topic_builder(params: BarsSubscriptionRequest): string {
  return `bars:${params.symbol}:${params.resolution}`
}
```

### Subscription Lifecycle

```
┌────────────────────────────────────────────────────────────────┐
│                   Subscription State Machine                    │
└────────────────────────────────────────────────────────────────┘

   [CREATED]
       │
       │ sendRequest('bars.subscribe', ...)
       ▼
   [PENDING]  ←──────────────────┐
       │                         │ Retry on timeout
       │ Receive response        │
       ▼                         │
   [CONFIRMED] ──────────────────┘
       │
       │ Receive 'bars.update' messages
       │ Route to callback
       │
       │ User calls unsubscribe()
       ▼
   [UNSUBSCRIBING]
       │
       │ sendRequest('bars.unsubscribe', ...)
       ▼
   [DELETED]
```

### Connection Management

**State Transitions**:
```
[DISCONNECTED]
    │
    │ getInstance(config)
    ▼
[CONNECTING]  ←─────────┐
    │                   │ Retry with exponential backoff
    │ WebSocket.open    │ (max 5 attempts by default)
    ▼                   │
[CONNECTED] ────────────┘
    │
    │ WebSocket.close or error
    ▼
[RECONNECTING] ─────┐
    │               │ Resubscribe all confirmed subscriptions
    │ connect()     │
    └───────────────┘
```

**Retry Strategy**:
```typescript
// Exponential backoff
Attempt 1: Wait 0ms
Attempt 2: Wait 1000ms
Attempt 3: Wait 2000ms
Attempt 4: Wait 4000ms
Attempt 5: Wait 8000ms (max attempts = 5)
```

### Reference Counting

```
┌────────────────────────────────────────────────────────────────┐
│                    Reference Counting                           │
└────────────────────────────────────────────────────────────────┘

Time: t0
  instances = {}

Time: t1 - Client1.create({ url: 'ws://server' })
  instances = {
    'ws://server': { refCount: 1, ws: WebSocket(connected) }
  }

Time: t2 - Client2.create({ url: 'ws://server' })  // Same URL!
  instances = {
    'ws://server': { refCount: 2, ws: WebSocket(connected) }  // Reused!
  }

Time: t3 - Client1.dispose()
  instances = {
    'ws://server': { refCount: 1, ws: WebSocket(connected) }  // Still open
  }

Time: t4 - Client2.dispose()
  instances = {}  // Cleaned up, WebSocket closed
```

---

## Usage Examples

### Basic Usage

```typescript
import { BarsWebSocketClientFactory } from '@/plugins/barsClient'
import type { Bar } from '@/plugins/ws-types'

// Create client
const wsClient = BarsWebSocketClientFactory()

// Subscribe to bars
const subscriptionId = await wsClient.subscribe(
  { symbol: 'AAPL', resolution: '1' },
  (bar: Bar) => {
    console.log('New bar:', bar)
  }
)

// Later: unsubscribe
await wsClient.unsubscribe(subscriptionId)
```

### Multiple Subscriptions

```typescript
const wsClient = BarsWebSocketClientFactory()

// Subscribe to multiple symbols/resolutions
const subs = await Promise.all([
  wsClient.subscribe({ symbol: 'AAPL', resolution: '1' }, onAAPL1min),
  wsClient.subscribe({ symbol: 'AAPL', resolution: 'D' }, onAAPLDaily),
  wsClient.subscribe({ symbol: 'GOOGL', resolution: '5' }, onGOOGL5min),
])

// All share the same WebSocket connection!
```

### Error Handling

```typescript
try {
  const wsClient = BarsWebSocketClientFactory()
  const subId = await wsClient.subscribe(params, callback)
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

### Service Integration

```typescript
export class DatafeedService implements IBasicDataFeed {
  private wsClient: BarsWebSocketInterface | null = null
  private subscriptions = new Map<string, { wsSubscriptionId: string }>()

  constructor() {
    this.wsClient = BarsWebSocketClientFactory()
  }

  async subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    onTick: SubscribeBarsCallback,
    listenerGuid: string,
  ): void {
    if (!this.wsClient) return

    const wsSubscriptionId = await this.wsClient.subscribe(
      { symbol: symbolInfo.name, resolution },
      (bar) => onTick(bar)
    )

    this.subscriptions.set(listenerGuid, { wsSubscriptionId })
  }

  async unsubscribeBars(listenerGuid: string): void {
    const subscription = this.subscriptions.get(listenerGuid)
    if (subscription?.wsSubscriptionId && this.wsClient) {
      await this.wsClient.unsubscribe(subscription.wsSubscriptionId)
      this.subscriptions.delete(listenerGuid)
    }
  }
}
```

---

## Auto-Generation Strategy

### Overview

The pattern is designed to support **automatic client generation** from backend AsyncAPI specification.

### Generation Targets

1. **Type Definitions** (`ws-types.ts`)
   - Request/response models
   - Update data models
   - Shared interfaces

2. **Client Factory** (`{domain}Client.ts`)
   - Factory function
   - Type aliases
   - Domain-specific interface

3. **Integration Helpers** (optional)
   - Mock implementations
   - Test utilities
   - Documentation

### Generation Process

```
┌─────────────────────────────────────────────────────────────────┐
│              WebSocket Client Generation Flow                    │
└─────────────────────────────────────────────────────────────────┘

1. Backend AsyncAPI Spec (asyncapi.json)
   │
   │ Parse channels, messages, schemas
   ▼
2. Extract Operations
   │ - Subscribe operations (SEND with reply)
   │ - Unsubscribe operations (SEND with reply)
   │ - Update operations (RECEIVE)
   ▼
3. Generate Types (ws-types.ts)
   │ - BarsSubscriptionRequest
   │ - Bar
   │ - SubscriptionResponse
   ▼
4. Generate Client ({domain}Client.ts)
   │ - {Domain}WebSocketInterface
   │ - {Domain}WebSocketClientFactory()
   ▼
5. Generate Tests (optional)
   │ - Mock implementations
   │ - Integration tests
   ▼
6. Generate Documentation (README.md)
   │ - Usage examples
   │ - API reference
```

### Generation Template

**Target**: `src/plugins/{domain}Client.ts`

```typescript
import type { {Request}, {Data} } from './ws-types'
import type { WebSocketInterface } from './wsClientBase'
import { WebSocketClientBase } from './wsClientBase'

export type {Domain}WebSocketInterface = WebSocketInterface<{Request}, {Data}>

export function {Domain}WebSocketClientFactory(): {Domain}WebSocketInterface {
  return new WebSocketClientBase<{Request}, {Data}>('{topic}')
}
```

**Example**: Quotes Client

```typescript
// Generated from AsyncAPI spec
import type { QuotesSubscriptionRequest, Quote } from './ws-types'
import type { WebSocketInterface } from './wsClientBase'
import { WebSocketClientBase } from './wsClientBase'

export type QuotesWebSocketInterface = WebSocketInterface<QuotesSubscriptionRequest, Quote>

export function QuotesWebSocketClientFactory(): QuotesWebSocketInterface {
  return new WebSocketClientBase<QuotesSubscriptionRequest, Quote>('quotes')
}
```

### Code Generation Steps

1. **Parse AsyncAPI**
   ```javascript
   const spec = JSON.parse(fs.readFileSync('asyncapi.json', 'utf-8'))
   const channels = spec.channels
   ```

2. **Extract Operations**
   ```javascript
   for (const [channelName, channel] of Object.entries(channels)) {
     const subscribeOp = channel.subscribe
     const publishOp = channel.publish
     // Extract message schemas, topic, etc.
   }
   ```

3. **Generate Types**
   ```javascript
   const requestType = subscribeOp.message.payload.$ref
   const dataType = publishOp.message.payload.$ref
   // Generate TypeScript interfaces
   ```

4. **Generate Factory**
   ```javascript
   const domain = extractDomain(channelName)
   const factory = `
   export function ${domain}WebSocketClientFactory(): ${domain}WebSocketInterface {
     return new WebSocketClientBase<${requestType}, ${dataType}>('${topic}')
   }
   `
   ```

5. **Write Files**
   ```javascript
   fs.writeFileSync(`src/plugins/${domain}Client.ts`, factory)
   ```

### Generator Configuration

```json
{
  "input": "backend/asyncapi.json",
  "output": "frontend/src/plugins",
  "baseClass": "wsClientBase.ts",
  "template": "factory",
  "options": {
    "generateTypes": true,
    "generateMocks": true,
    "generateTests": false,
    "generateDocs": true
  }
}
```

---

## Integration Guide

### Step 1: Create WebSocket Client

```typescript
// src/plugins/barsClient.ts
import type { BarsSubscriptionRequest, Bar } from './ws-types'
import type { WebSocketInterface } from './wsClientBase'
import { WebSocketClientBase } from './wsClientBase'

export type BarsWebSocketInterface = WebSocketInterface<BarsSubscriptionRequest, Bar>

export function BarsWebSocketClientFactory(): BarsWebSocketInterface {
  return new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
}
```

### Step 2: Add to Service

```typescript
// src/services/datafeedService.ts
import { BarsWebSocketClientFactory, type BarsWebSocketInterface } from '@/plugins/barsClient'

export class DatafeedService implements IBasicDataFeed {
  private wsClient: BarsWebSocketInterface | null = null

  constructor() {
    this.wsClient = BarsWebSocketClientFactory()
  }

  async subscribeBars(...) {
    if (!this.wsClient) return

    const wsSubscriptionId = await this.wsClient.subscribe(
      { symbol: symbolInfo.name, resolution },
      (bar) => onTick(bar)
    )

    // Store subscription info
    this.subscriptions.set(listenerGuid, {
      symbolInfo,
      resolution,
      onTick,
      wsSubscriptionId,
    })
  }

  async unsubscribeBars(listenerGuid: string) {
    const subscription = this.subscriptions.get(listenerGuid)
    if (subscription?.wsSubscriptionId && this.wsClient) {
      await this.wsClient.unsubscribe(subscription.wsSubscriptionId)
      this.subscriptions.delete(listenerGuid)
    }
  }
}
```

### Step 3: Configure Environment

```env
# .env
VITE_WS_URL=ws://localhost:8000/api/v1/ws
```

### Step 4: Handle Cleanup

```typescript
// Cleanup on component unmount
onUnmounted(() => {
  datafeedService.cleanup()
})
```

---

## Testing Approach

### Unit Tests

**Test WebSocket Base**:
```typescript
import { WebSocketClientBase } from '@/plugins/wsClientBase'

describe('WebSocketClientBase', () => {
  it('should create singleton instance', async () => {
    const client1 = await WebSocketClientBase.getInstance(config)
    const client2 = await WebSocketClientBase.getInstance(config)
    expect(client1).toBe(client2) // Same instance
  })

  it('should handle subscription', async () => {
    const client = await WebSocketClientBase.getInstance(config)
    const callback = vi.fn()
    const subId = await client.subscribe(params, callback)
    expect(subId).toBeDefined()
  })
})
```

### Integration Tests

**Test with Mock WebSocket**:
```typescript
import { BarsWebSocketClientFactory } from '@/plugins/barsClient'

describe('BarsWebSocketClient', () => {
  let mockWs: MockWebSocket

  beforeEach(() => {
    mockWs = new MockWebSocket()
  })

  it('should subscribe to bars', async () => {
    const client = BarsWebSocketClientFactory()
    const callback = vi.fn()

    const subId = await client.subscribe(
      { symbol: 'AAPL', resolution: '1' },
      callback
    )

    // Simulate server response
    mockWs.receiveMessage({
      type: 'bars.subscribe.response',
      payload: { status: 'ok', topic: 'bars:AAPL:1' }
    })

    // Simulate update
    mockWs.receiveMessage({
      type: 'bars.update',
      payload: { time: 123, open: 150, ... }
    })

    expect(callback).toHaveBeenCalledWith({ time: 123, open: 150, ... })
  })
})
```

### E2E Tests

**Test with Real Backend**:
```typescript
describe('DatafeedService E2E', () => {
  it('should receive real-time bar updates', async () => {
    const service = new DatafeedService()
    const bars: Bar[] = []

    await service.subscribeBars(
      symbolInfo,
      '1',
      (bar) => bars.push(bar),
      'test-guid'
    )

    // Wait for updates
    await new Promise(resolve => setTimeout(resolve, 5000))

    expect(bars.length).toBeGreaterThan(0)
    expect(bars[0]).toHaveProperty('time')
    expect(bars[0]).toHaveProperty('open')
  })
})
```

---

## Best Practices

### 1. Always Use Factory Pattern

```typescript
// ✅ Good
const client = BarsWebSocketClientFactory()

// ❌ Bad
const client = new WebSocketClientBase(...)
```

### 2. Handle Errors Gracefully

```typescript
try {
  const subId = await client.subscribe(params, callback)
} catch (error) {
  console.error('Subscription failed:', error)
  // Fallback to mock data or show error to user
}
```

### 3. Clean Up Subscriptions

```typescript
// Store subscription IDs
const subscriptions = new Set<string>()

// Subscribe
const subId = await client.subscribe(params, callback)
subscriptions.add(subId)

// Cleanup on unmount/destroy
async function cleanup() {
  for (const subId of subscriptions) {
    await client.unsubscribe(subId)
  }
  subscriptions.clear()
}
```

### 4. Use TypeScript Strict Mode

```typescript
// Enable strict type checking
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true
  }
}
```

### 5. Implement Retry Logic

```typescript
async function subscribeWithRetry(params, callback, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await client.subscribe(params, callback)
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)))
    }
  }
}
```

### 6. Log Important Events

```typescript
client.subscribe(params, (bar) => {
  console.debug('[DatafeedService] Bar received:', {
    symbol: params.symbol,
    resolution: params.resolution,
    bar,
  })
})
```

### 7. Monitor Connection State

```typescript
setInterval(() => {
  if (!client.isConnected()) {
    console.warn('[WebSocket] Connection lost, attempting reconnect...')
  }
}, 5000)
```

### 8. Use Environment Variables

```typescript
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/v1/ws'
const client = BarsWebSocketClientFactory()
```

---

## Conclusion

This WebSocket client pattern provides a robust, scalable foundation for real-time data streaming in the Trading Pro frontend. The combination of:

- ✅ Singleton pattern (resource efficiency)
- ✅ Factory pattern (clean API)
- ✅ Repository pattern (testability)
- ✅ Type safety (reliability)
- ✅ Auto-generation support (scalability)

...makes it ideal for building production-ready WebSocket clients that integrate seamlessly with FastAPI/FastWS backends.

### Next Steps

1. **Implement Additional Clients** - Create quotes, trades, orders clients
2. **Generate from AsyncAPI** - Automate client generation
3. **Add Mock Implementations** - Support offline development
4. **Enhance Error Handling** - Add user-friendly error messages
5. **Monitor Performance** - Track connection metrics

---

**Version**: 1.0.0
**Date**: October 13, 2025
**Status**: ✅ Production Ready
**Maintainers**: Development Team
