# WebSocket Base Client - Implementation Reference

**Date**: November 11, 2025  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Classes](#core-classes)
4. [Subscription Lifecycle](#subscription-lifecycle)
5. [Connection Management](#connection-management)
6. [Message Routing](#message-routing)
7. [Error Handling](#error-handling)
8. [Advanced Features](#advanced-features)

---

## Overview

This document provides a detailed technical reference for the `WebSocketBase` singleton class, which powers all real-time WebSocket communication in the Trading Pro frontend.

### Key Features

- ✅ **Singleton Pattern** - One WebSocket connection per backend module URL
- ✅ **Centralized Subscription Management** - Single source of truth for all subscriptions
- ✅ **Server-Confirmed Subscriptions** - Waits for server acknowledgment
- ✅ **Automatic Reconnection** - Exponential backoff with full resubscription
- ✅ **Reference Counting** - Auto-cleanup when last listener disconnects
- ✅ **Topic-Based Routing** - Filters messages to relevant subscribers
- ✅ **Type-Safe Messages** - Full TypeScript support
- ✅ **Request-Response Pattern** - Async/await API for subscriptions
- ✅ **Message Deduplication** - Prevents duplicate messages

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

## Architecture

### Class Hierarchy

```
┌────────────────────────────────────────────────┐
│         WebSocketBase (Singleton)              │
│  - One instance per WebSocket URL             │
│  - Connection lifecycle management            │
│  - Centralized subscription state              │
│  - Message routing to subscribers              │
└────────────────┬───────────────────────────────┘
                 │
                 │ Used by (extends/uses)
                 │
┌────────────────▼───────────────────────────────┐
│  WebSocketClient<TParams, TBackendData, TData>│
│  - Generic client with mapper                  │
│  - Topic building from params                  │
│  - Type-safe data transformations              │
│  - Listener tracking per subscription          │
└────────────────┬───────────────────────────────┘
                 │
                 │ Used by
                 │
┌────────────────▼───────────────────────────────┐
│         WsAdapter (Facade)                     │
│  - bars, quotes, orders, positions, etc.       │
│  - Type-safe access to all WebSocket clients   │
└────────────────────────────────────────────────┘
```

### Singleton Pattern per URL

```
Frontend Components:
┌─────────────────────┐  ┌─────────────────────┐
│  DatafeedService    │  │  BrokerService      │
└──────────┬──────────┘  └──────────┬──────────┘
           │                         │
           │ Uses adapter            │
           │                         │
┌──────────▼─────────────────────────▼──────────┐
│            WsAdapter (Facade)                 │
│  ┌────────────┐    ┌─────────────────────┐   │
│  │bars,quotes │    │orders,positions,etc.│   │
│  └─────┬──────┘    └──────┬──────────────┘   │
└────────┼───────────────────┼──────────────────┘
         │                   │
         │ WebSocketClient   │ WebSocketClient
         │ instances         │ instances
         │                   │
┌────────▼───────┐  ┌────────▼───────────┐
│ WebSocketBase  │  │ WebSocketBase      │
│ (singleton)    │  │ (singleton)        │
│ /v1/datafeed/ws│  │ /v1/broker/ws      │
└────────┬───────┘  └────────┬───────────┘
         │                   │
         │ Native WebSocket  │ Native WebSocket
         │                   │
┌────────▼───────────────────▼───────────┐
│         Backend Modules                │
│  datafeed module     broker module     │
└────────────────────────────────────────┘
```

**Key Point**: Even though there are 7 `WebSocketClient` instances (bars, quotes, orders, etc.), there are only **2 actual WebSocket connections** - one per backend module URL.

---

## Core Classes

### WebSocketBase

**File**: `frontend/src/plugins/wsClientBase.ts`

The singleton WebSocket connection manager.

#### Class Definition

```typescript
export class WebSocketBase {
  // Singleton management
  private static instances = new Map<string, WebSocketBase>()

  // Connection state
  protected ws: WebSocket | null = null
  protected wsUrl: string
  protected isReconnecting: boolean = false
  protected reconnectAttempts: number = 0
  protected maxReconnectAttempts: number = 5
  protected reconnectDelay: number = 1000

  // Subscription state (centralized!)
  protected subscriptions = new Map<string, SubscriptionState>()

  // Message handling
  protected pendingRequests = new Map<string, PendingRequest>()
  protected requestIdCounter: number = 0

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

#### Key Interfaces

**`SubscriptionState`** - Tracks subscription metadata

```typescript
export interface SubscriptionState {
  topic: string // e.g., "bars:AAPL:1"
  subscriptionType: string // e.g., "bars.subscribe"
  subscriptionParams: object // Original params
  confirmed: boolean // Server confirmed?
  listeners: Map<string, (data: object) => void> // All callbacks
}
```

**`PendingRequest`** - Tracks request-response pairs

```typescript
interface PendingRequest {
  resolve: (response: object) => void
  reject: (error: Error) => void
  timeout: ReturnType<typeof setTimeout>
  expectedType?: string
}
```

---

## Subscription Lifecycle

### 1. Subscribe Flow

```typescript
// Service calls
await adapter.bars.subscribe(listenerId, params, callback)
  ↓
// WebSocketClient builds topic and calls
await ws.subscribe(topic, subscribeType, params, listenerId, callback)
  ↓
// WebSocketBase handles subscription
```

**Detailed Steps**:

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

**Key Features**:

- ✅ Reuses existing subscriptions (reference counting)
- ✅ Waits for server confirmation
- ✅ Cleans up on failure
- ✅ Returns subscription state to client

### 2. Message Routing

```typescript
protected handleMessage(event: MessageEvent): void {
  const message: WebSocketMessage = JSON.parse(event.data)

  // Route 1: Response to pending request (subscribe, unsubscribe)
  if (message.request_id !== undefined) {
    const pending = this.pendingRequests.get(message.request_id)
    if (pending) {
      clearTimeout(pending.timeout)
      this.pendingRequests.delete(message.request_id)

      if (message.status === 'error') {
        pending.reject(new Error(message.message || 'Request failed'))
      } else {
        pending.resolve(message)
      }
      return
    }
  }

  // Route 2: Data update (bars.update, orders.update, etc.)
  if (message.type && message.type.endsWith('.update')) {
    const topic = message.topic
    if (!topic) return

    const subscription = this.subscriptions.get(topic)
    if (subscription && subscription.confirmed) {
      // Broadcast to all listeners for this topic
      for (const [listenerId, callback] of subscription.listeners) {
        try {
          callback(message.data)
        } catch (error) {
          console.error(`[WebSocketBase] Listener ${listenerId} error:`, error)
        }
      }
    }
  }
}
```

**Key Features**:

- ✅ Handles both request-response and pub-sub patterns
- ✅ Only routes to confirmed subscriptions
- ✅ Broadcasts to all listeners for a topic
- ✅ Error isolation per listener

### 3. Unsubscribe Flow

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

**Key Features**:

- ✅ Reference counting (only unsubscribes when last listener gone)
- ✅ Supports unsubscribing from specific topic or all topics
- ✅ Automatic cleanup
- ✅ Handles server communication

---

## Connection Management

### Initial Connection

```typescript
protected connect(): void {
  if (this.ws?.readyState === WebSocket.OPEN) return

  try {
    this.ws = new WebSocket(this.wsUrl)

    this.ws.onopen = () => {
      console.log(`[WebSocketBase] Connected to ${this.wsUrl}`)
      this.reconnectAttempts = 0
      this.isReconnecting = false
    }

    this.ws.onmessage = (event) => this.handleMessage(event)
    this.ws.onerror = (error) => this.handleError(error)
    this.ws.onclose = (event) => this.handleClose(event)
  } catch (error) {
    console.error('[WebSocketBase] Connection error:', error)
    this.scheduleReconnect()
  }
}
```

### Automatic Reconnection

```typescript
protected handleClose(event: CloseEvent): void {
  console.log(`[WebSocketBase] Connection closed: ${event.code} ${event.reason}`)

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

  console.log(`[WebSocketBase] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

  setTimeout(() => {
    this.connect()
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.resubscribeAll()
    }
  }, delay)
}
```

### Resubscription on Reconnect

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
        console.error(`[WebSocketBase] Resubscription failed for ${topic}`)
        subscription.confirmed = false
      }
    } catch (error) {
      console.error(`[WebSocketBase] Resubscription error for ${topic}:`, error)
      subscription.confirmed = false
    }
  }
}
```

**Key Features**:

- ✅ Exponential backoff (1s → 2s → 4s → 8s → 16s max)
- ✅ Automatic resubscription after reconnect
- ✅ Preserves all subscription state
- ✅ Max 5 reconnect attempts
- ✅ Services don't need to handle reconnection

---

## Message Routing

### Request-Response Pattern

Used for subscribe/unsubscribe operations:

```typescript
protected async sendRequestWithTimeout<T = object>(
  type: string,
  payload: object,
  timeoutMs: number = 5000
): Promise<T> {
  return new Promise((resolve, reject) => {
    const requestId = `${++this.requestIdCounter}`

    // Create pending request
    const timeout = setTimeout(() => {
      this.pendingRequests.delete(requestId)
      reject(new Error(`Request timeout after ${timeoutMs}ms`))
    }, timeoutMs)

    this.pendingRequests.set(requestId, { resolve, reject, timeout })

    // Send request
    const message = {
      type,
      payload,
      request_id: requestId
    }
    this.ws?.send(JSON.stringify(message))
  })
}
```

### Publish-Subscribe Pattern

Used for data updates:

```typescript
// Server sends:
{
  "type": "bars.update",
  "topic": "bars:AAPL:1",
  "data": { time: 123456, open: 150, ... }
}

// WebSocketBase routes to all listeners:
const subscription = this.subscriptions.get("bars:AAPL:1")
for (const callback of subscription.listeners.values()) {
  callback(data) // Each listener gets the update
}
```

---

## Error Handling

### Connection Errors

```typescript
protected handleError(error: Event): void {
  console.error('[WebSocketBase] WebSocket error:', error)
  // Will trigger onclose → scheduleReconnect
}
```

### Subscription Errors

```typescript
async subscribe(...): Promise<SubscriptionState> {
  try {
    const response = await this.sendRequestWithTimeout(...)
    if (response.status !== 'ok') {
      throw new Error(`Subscription failed: ${response.message}`)
    }
  } catch (error) {
    // Cleanup failed subscription
    this.subscriptions.delete(topic)
    throw error // Propagate to caller
  }
}
```

### Listener Errors

```typescript
// Errors in one listener don't affect others
for (const [listenerId, callback] of subscription.listeners) {
  try {
    callback(message.data)
  } catch (error) {
    console.error(`[WebSocketBase] Listener ${listenerId} error:`, error)
    // Continue to next listener
  }
}
```

---

## Advanced Features

### 1. Topic Building

Topics are built from subscription parameters to ensure uniqueness:

```typescript
// In WebSocketClient
const topic = `${this.wsRoute}:${buildTopicParams(subscriptionParams)}`

// Example buildTopicParams:
function buildTopicParams(params: object): string {
  // bars: { symbol: "AAPL", resolution: "1" } → "AAPL:1"
  // orders: { account_id: "123" } → "123"
  return Object.values(params).join(':')
}
```

### 2. Connection State Inspection

```typescript
export class WebSocketBase {
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  getSubscriptionCount(): number {
    return this.subscriptions.size
  }

  getConfirmedSubscriptionCount(): number {
    return Array.from(this.subscriptions.values()).filter((sub) => sub.confirmed).length
  }
}
```

### 3. Multiple Listeners per Topic

```typescript
// Listener 1
await adapter.bars.subscribe('listener-1', { symbol: 'AAPL', resolution: '1' }, callback1)

// Listener 2 (same params → same topic)
await adapter.bars.subscribe('listener-2', { symbol: 'AAPL', resolution: '1' }, callback2)

// Result: ONE subscription to server, TWO listeners
// Both get updates when server sends bars.update
```

### 4. Graceful Cleanup

```typescript
// When last listener unsubscribes:
await adapter.bars.unsubscribe('listener-2')
// subscription.listeners.size = 1, keep subscription

await adapter.bars.unsubscribe('listener-1')
// subscription.listeners.size = 0, unsubscribe from server
```

---

## Usage Patterns

### Pattern 1: Service Integration

```typescript
export class DatafeedService {
  private wsAdapter: WsAdapterType

  constructor() {
    this.wsAdapter = new WsAdapter()
  }

  subscribeBars(
    listenerGuid: string,
    symbol: string,
    resolution: string,
    callback: (bar: Bar) => void,
  ): void {
    // Just pass through - base client handles everything!
    this.wsAdapter.bars.subscribe(listenerGuid, { symbol, resolution }, callback)
  }

  unsubscribeBars(listenerGuid: string): void {
    this.wsAdapter.bars.unsubscribe(listenerGuid)
  }
}
```

### Pattern 2: Vue Component Usage

```typescript
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { WsAdapter } from '@/plugins/wsAdapter'

const adapter = new WsAdapter()
const listenerId = 'my-component'

onMounted(() => {
  adapter.bars.subscribe(
    listenerId,
    { symbol: 'AAPL', resolution: '1' },
    (bar) => {
      console.log('Bar update:', bar)
    }
  )
})

onUnmounted(() => {
  adapter.bars.unsubscribe(listenerId)
})
</script>
```

### Pattern 3: Error Handling

```typescript
try {
  await adapter.orders.subscribe('order-listener', { account_id: '123' }, (order) =>
    console.log(order),
  )
} catch (error) {
  if (error.message.includes('timeout')) {
    console.error('Server did not respond in time')
  } else if (error.message.includes('Subscription failed')) {
    console.error('Server rejected subscription')
  } else {
    console.error('Unknown error:', error)
  }
}
```

---

## Testing Considerations

### Unit Testing

```typescript
import { WebSocketBase } from '@/plugins/wsClientBase'

describe('WebSocketBase', () => {
  it('should maintain singleton per URL', () => {
    const ws1 = WebSocketBase.getInstance('ws://localhost/v1/datafeed/ws')
    const ws2 = WebSocketBase.getInstance('ws://localhost/v1/datafeed/ws')
    expect(ws1).toBe(ws2) // Same instance
  })

  it('should handle multiple listeners', async () => {
    const ws = WebSocketBase.getInstance('ws://localhost/v1/datafeed/ws')
    const updates1: object[] = []
    const updates2: object[] = []

    await ws.subscribe('topic1', 'bars.subscribe', { symbol: 'AAPL' }, 'listener1', (data) =>
      updates1.push(data),
    )
    await ws.subscribe('topic1', 'bars.subscribe', { symbol: 'AAPL' }, 'listener2', (data) =>
      updates2.push(data),
    )

    // Simulate message
    ws['handleMessage']({
      data: JSON.stringify({ type: 'bars.update', topic: 'topic1', data: { price: 150 } }),
    })

    expect(updates1.length).toBe(1)
    expect(updates2.length).toBe(1)
  })
})
```

### Integration Testing

```typescript
describe('WebSocket Integration', () => {
  it('should connect and subscribe', async () => {
    const adapter = new WsAdapter()
    const bars: Bar[] = []

    await adapter.bars.subscribe('test', { symbol: 'AAPL', resolution: '1' }, (bar) => {
      bars.push(bar)
    })

    // Wait for updates
    await new Promise((resolve) => setTimeout(resolve, 5000))
    expect(bars.length).toBeGreaterThan(0)
  })
})
```

---

## Conclusion

The `WebSocketBase` singleton provides a robust, centralized foundation for WebSocket communication in Trading Pro. Key takeaways:

1. **Single Source of Truth** - All subscription state lives in base client
2. **Services Stay Simple** - No duplicate tracking, just pass-through calls
3. **Automatic Everything** - Connection, reconnection, resubscription all handled
4. **Type-Safe** - Full TypeScript support throughout
5. **Efficient** - One connection per module, reference counting

### Related Documentation

- [WEBSOCKET-CLIENT-PATTERN.md](./WEBSOCKET-CLIENT-PATTERN.md) - High-level pattern overview
- [WEBSOCKET-ARCHITECTURE-DIAGRAMS.md](./WEBSOCKET-ARCHITECTURE-DIAGRAMS.md) - Visual architecture reference

---

**Version**: 2.0.0  
**Date**: November 11, 2025  
**Status**: ✅ Production Ready  
**Maintainers**: Development Team
