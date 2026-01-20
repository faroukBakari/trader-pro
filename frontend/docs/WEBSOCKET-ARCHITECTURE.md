# WebSocket Architecture

**Date**: December 19, 2025  
**Status**: ✅ Production Ready  
**Version**: 3.3.0 (Global Error Handler Integration)

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
10. [Topic Builder Compliance](#️-topic-builder-compliance-critical-contract)
11. [Subscription Error Handling](#subscription-error-handling)

---

## Overview

This document describes the complete **WebSocket Architecture** implemented in the Trading Pro frontend. The architecture provides a robust, type-safe foundation for real-time data streaming that integrates with the modular FastAPI/FastWS backend architecture.

### Key Features

- ✅ **Singleton Pattern** - One WebSocket connection per backend module
- ✅ **Modular Architecture** - Separate connections for broker and datafeed modules
- ✅ **Cookie-Based Authentication** - Automatic authentication via HttpOnly cookies
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

**Services Delegate Error Handling** ⭐

Services create error handlers that throw `WebSocketError` to propagate to the global error handler. Services never handle toasts directly - that's the global error handler's responsibility.

```typescript
// ✅ Good - Service delegates to global handler
private handleSubscriptionError(
  subscriptionName: string,
  error: SubscriptionError
): void {
  throw WebSocketError.fromSubscription(error, { subscriptionName })
}

// Use in subscription
await wsAdapter.orders.subscribe(
  'orders',
  params,
  (data) => handleData(data),
  (error) => this.handleSubscriptionError('Orders', error)  // ← Throw, don't log
)

// ❌ Bad - Don't handle notifications in services
private handleSubscriptionError(error: SubscriptionError): void {
  console.error('Error:', error)  // Only logging doesn't help user
  showToast(error.message)        // Service shouldn't manage toasts
}
```

**Key Points:**

- **Factory Pattern**: Use `WebSocketError.fromSubscription(error, context)` for conversion
- **Context Enrichment**: Add `subscriptionName` to error context for better error messages
- **Centralized Display**: Global error handler (`errorService`) shows toasts
- **Example**: [brokerTerminalService.ts#L674-L680](../../src/services/brokerTerminalService.ts#L674-L680)

**Related**: See [ERROR-MANAGEMENT.md#error-handling-philosophy](./ERROR-MANAGEMENT.md#error-handling-philosophy) for complete error handling architecture.

### WebSocket Authentication

WebSocket connections are **automatically authenticated** using cookies. No manual token management is required in the frontend.

**How It Works:**

1. **Login Flow**: User authenticates via `/login`, backend sets `access_token` HttpOnly cookie
2. **WebSocket Handshake**: Browser automatically includes cookies in WebSocket connection request
3. **Backend Validation**: Backend middleware extracts and validates JWT from cookie
4. **Connection Established**: If valid, WebSocket connection is established
5. **Transparent to Frontend**: Frontend code doesn't need to handle tokens

**Cookie Configuration:**

- **Name:** `access_token`
- **Flags:** `httponly=True, secure=True, samesite="strict"`
- **Expiry:** 5 minutes (matches JWT expiry)
- **Automatic Renewal:** Access token refreshed automatically by auth service

**Security Benefits:**

- ✅ **XSS Protection**: HttpOnly prevents JavaScript access to token
- ✅ **CSRF Protection**: SameSite=Strict blocks cross-site requests
- ✅ **Automatic Handling**: Browser manages cookies automatically
- ✅ **No Manual Token Passing**: WebSocket clients don't need authentication code

**Frontend Code:**

```typescript
// No authentication code needed!
const ws = new WebSocket('ws://localhost:8000/api/v1/broker/ws')

// Browser automatically sends cookies
// Backend validates token from cookie
// Connection established if authenticated
```

**What This Means for WebSocket Clients:**

- ✅ No `Authorization` header needed
- ✅ No token management in `WebSocketBase`
- ✅ No authentication in `WsAdapter`
- ✅ Connection fails gracefully if not authenticated (401/403)
- ✅ Auto-reconnection uses same cookie mechanism

**Authentication Flow:**

```
User Login
    ↓
Backend sets access_token cookie (HttpOnly)
    ↓
Frontend creates WebSocket connection
    ↓
Browser includes cookie in handshake
    ↓
Backend validates JWT from cookie
    ↓
Connection established (if valid)
    ↓
WebSocket messages flow
```

**Error Handling:**

```typescript
// WebSocketBase handles authentication errors
private handleError(event: Event): void {
  // Connection refused (401/403) triggers reconnection
  // Auth service handles token refresh if needed
  // Reconnection uses updated cookie automatically
}
```

See [Authentication Guide](../../backend/docs/AUTHENTICATION.md) for complete authentication system documentation.

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

**Error Types (Future Work)**:

The backend now supports subscription-level error notifications via `{route}.error` messages containing `ErrorPayload` and `SubscriptionError` types. These types will be auto-generated in `ws-types-{module}_v1` once client generation is updated. Frontend error handling integration is planned for a future iteration.

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

## ⚠️ Topic Builder Compliance (Critical Contract)

**MUST BE SHARED ACROSS BACKEND AND FRONTEND**

The topic builder algorithm is the **critical contract** between backend and frontend. Both implementations **MUST** produce identical topic strings for the same subscription parameters.

### Topic Format

```
{route}:{JSON-serialized-params}
```

**Examples**:

- `bars:{"resolution":"1","symbol":"AAPL"}` - Apple 1-minute bars
- `orders:{"accountId":"TEST-001"}` - Orders for account TEST-001

### Algorithm Requirements

**BOTH backend (Python) and frontend (TypeScript) MUST**:

1. **Sort object keys alphabetically** before serialization
2. **Use compact JSON format** with separators `(",", ":")` - no spaces
3. **Handle nested objects recursively** with sorted keys at all levels
4. **Handle null/undefined** by converting to empty string `""`

### Implementation Contract

#### Backend (Python)

```python
# backend/src/trading_api/shared/ws/ws_router.py
def buildTopicParams(obj: Any) -> str:
    def sort_recursive(item: Any) -> Any:
        if isinstance(item, dict):
            return {k: sort_recursive(v) for k, v in sorted(item.items())}
        elif isinstance(item, list):
            return [sort_recursive(element) for element in item]
        elif item is None:
            return ""
        else:
            return item
    sorted_obj = sort_recursive(obj)
    return json.dumps(sorted_obj, separators=(",", ":"))
```

#### Frontend (TypeScript)

```typescript
// frontend/src/plugins/wsClientBase.ts
function buildTopicParams(obj: unknown): string {
  if (obj === null || obj === undefined) return ''
  if (typeof obj !== 'object') return JSON.stringify(obj)
  if (Array.isArray(obj)) return `[${obj.map(buildTopicParams).join(',')}]`

  const sortedKeys = Object.keys(obj as Record<string, unknown>).sort()
  const pairs = sortedKeys.map(
    (key) => `${JSON.stringify(key)}:${buildTopicParams((obj as Record<string, unknown>)[key])}`,
  )
  return `{${pairs.join(',')}}`
}
```

### Why This Matters

**Topic string is the subscription identifier**:

- Backend uses it to route update messages to correct subscribers
- Frontend uses it to match incoming updates to callbacks
- **Mismatch = No updates received** even though subscription appears successful

---

## Subscription Error Handling

**Added**: December 19, 2025  
**Status**: ✅ Production Ready

### Overview

The WebSocket architecture supports subscription-level error notifications. When the backend encounters an error for an active subscription (e.g., data provider timeout, invalid parameters), it sends an error message to the frontend without closing the connection.

### Error Message Flow

```
Backend Error Occurs (e.g., provider timeout)
    ↓
Backend sends: { type: "{route}.error", payload: { topic, error, recoverable } }
    ↓
WebSocketBase.handleMessage() routes to routeErrorMessage()
    ↓
routeErrorMessage() finds matching subscription by topic
    ↓
Subscription's onError callback invoked (if provided)
    ↓
Or globalErrorHandler() logs warning (fallback)
```

### Error Message Format

```typescript
interface SubscriptionError {
  topic: string // Affected subscription (e.g., "orders:{"accountId":"TEST"}")
  error: {
    code: string // Error code (e.g., "PROVIDER_TIMEOUT")
    message: string // Human-readable message
    timestamp: number // Unix timestamp (seconds)
    details?: Record<string, unknown> | null // Optional context
  }
  recoverable?: boolean // If true, subscription may auto-recover
  retry_after_ms?: number | null // Suggested retry delay
}
```

### Subscribing with Error Handler

```typescript
// Option A: With error callback (recommended for critical subscriptions)
await wsAdapter.orders.subscribe(
  'orders',
  { accountId: 'TEST-001' },
  (order) => {
    // Handle order update
  },
  (error) => {
    // Handle subscription error
    console.error('Order subscription error:', error)
    if (!error.recoverable) {
      showNotification('Orders Error', error.error.message)
    }
  },
)

// Option B: Without error callback (uses global fallback)
await wsAdapter.positions.subscribe('positions', { accountId: 'TEST-001' }, (position) => {
  // Handle position update
  // Errors logged to console by globalErrorHandler
})
```

### Service Integration Example

Services implement error handlers that convert backend subscription errors to frontend error classes and throw them to the global handler:

```typescript
// brokerTerminalService.ts
private handleSubscriptionError(
  subscriptionName: string,
  error: SubscriptionError
): void {
  throw WebSocketError.fromSubscription(error, { subscriptionName })
}

// Usage in setupWebSocketHandlers()
private async setupWebSocketHandlers(): Promise<(void | undefined)[]> {
  return Promise.all([
    this._wsAdapter.orders.subscribe(
      'orders',
      { accountId: this.accountId },
      (order: PlacedOrder) => {
        // Handle order update
        this._hostAdapter.orderUpdate(order)
      },
      (error) => this.handleSubscriptionError('Orders', error)  // ← Error callback
    ),

    this._wsAdapter.positions.subscribe(
      'positions',
      { accountId: this.accountId },
      (position: Position) => {
        // Handle position update
        this._hostAdapter.positionUpdate(position)
      },
      (error) => this.handleSubscriptionError('Positions', error)  // ← Error callback
    ),
  ])
}
```

**Error Propagation:**

```
Backend error → WebSocket message → Subscription callback
    ↓
handleSubscriptionError('Orders', error)
    ↓
throw WebSocketError.fromSubscription(error, { subscriptionName: 'Orders' })
    ↓
Global error handler (errorService.handle)
    ↓
Toast notification displayed ✓
```

**Why Throw Instead of Log?**

- ✅ **Centralized Handling**: Global error handler manages all toast display
- ✅ **Context Enrichment**: `subscriptionName` added to error for better messages
- ✅ **Deduplication**: Global handler prevents duplicate toasts
- ✅ **Consistent UX**: All errors shown to user via same mechanism

**Real Implementation**: [brokerTerminalService.ts#L674-L680](../../src/services/brokerTerminalService.ts#L674-L680) (error handler), [brokerTerminalService.ts#L689-L706](../../src/services/brokerTerminalService.ts#L689-L706) (subscription with error callback)

**Related**: See [ERROR-MANAGEMENT.md#websocketerror](./ERROR-MANAGEMENT.md#websocketerror) for error class details

### Global Error Handler

When no `onError` callback is provided, errors are handled by `globalErrorHandler()`:

```typescript
// wsClientBase.ts
protected globalErrorHandler(error: SubscriptionError): void {
  // Propagate to global error system - displays toast and logs
  throw WebSocketError.fromSubscription(error, { source: 'WebSocket' })
}
```

> **Note**: The `globalErrorHandler` throws instead of logging because the error system follows the ["Only Catch What You Can Handle"](./ERROR-MANAGEMENT.md#error-handling-philosophy) philosophy. The thrown error propagates to `window.onunhandledrejection` which routes it to `errorService.handle()` for consistent toast display.

### Error Routing Logic

```typescript
protected routeErrorMessage(errorPayload: SubscriptionError): void {
  const subscription = this.subscriptions.get(errorPayload.topic)

  if (!subscription || !subscription.confirmed) {
    // No active subscription for this topic
    this.globalErrorHandler(errorPayload)
    return
  }

  if (subscription.onError) {
    // Use subscription-specific handler
    subscription.onError(errorPayload)
  } else {
    // Fall back to global handler
    this.globalErrorHandler(errorPayload)
  }
}
```

### Missing Subscription Errors

**Added**: January 16, 2026  
**Related**: Test updates in `frontend/src/plugins/__tests__/wsClientBase.spec.ts`

When the WebSocket client receives an update message (`.update`) for a topic that has no active subscription, it **throws an Error** rather than logging a warning. This is a deliberate design decision reflecting that missing subscriptions indicate a serious state inconsistency between client and server.

```typescript
// In routeUpdateMessage()
const subscription = this.subscriptions.get(data.topic)
if (!subscription || !subscription.confirmed) {
  throw new Error(`No active subscription found for topic: ${data.topic}`)
}
```

**Rationale:**

- **State Consistency**: Update messages should only arrive for subscriptions the client explicitly created
- **Fail Fast**: Silent warnings hide bugs; throwing forces immediate investigation
- **Testing**: Makes state inconsistencies immediately detectable in tests

**Error Flow:**

```
Backend sends update → routeUpdateMessage() → No subscription found
    ↓
throw Error("No active subscription...")
    ↓
window.onunhandledrejection (if uncaught)
    ↓
errorService.handle() → Toast notification
```

**Prevention:**

- Ensure proper subscription lifecycle management (subscribe before expecting updates)
- Clean up subscriptions via `unsubscribe()` when no longer needed
- Use `subscription.confirmed` checks before assuming updates will arrive
```

### Backend Integration

The backend sends error messages via the `topic_error` callback in `generic_route.py`:

```python
# Backend: generic_route.py
async def topic_error(topic: str, error: Exception) -> None:
    error_payload = SubscriptionError(
        topic=topic,
        error=ErrorPayload.from_exception(error),
        recoverable=getattr(error, 'recoverable', False)
    )
    message = WebSocketMessage(
        type=f"{route_name}.error",
        payload=error_payload.model_dump()
    )
    await send_to_topic(topic, message)
```

### Best Practices

1. **Always provide `onError` for critical subscriptions** (orders, positions, equity)
2. **Log all errors** even when handled - aids debugging
3. **Show user notifications** for non-recoverable errors
4. **Check `recoverable` flag** to decide on retry behavior
5. **Don't close connection** on subscription errors - other subscriptions remain active

### Error Types (from Backend)

| Code               | Description                          | Recoverable        |
| ------------------ | ------------------------------------ | ------------------ |
| `PROVIDER_TIMEOUT` | Data provider didn't respond in time | Yes                |
| `PROVIDER_ERROR`   | Data provider returned error         | Depends            |
| `INVALID_PARAMS`   | Subscription parameters invalid      | No                 |
| `AUTH_EXPIRED`     | Authentication token expired         | No (reauth needed) |
| `RATE_LIMITED`     | Too many requests                    | Yes (after delay)  |

See [Backend Error Management](../../backend/docs/ERROR-MANAGEMENT.md) for complete error code reference.

See [Frontend Error Management](./ERROR-MANAGEMENT.md) for error class hierarchy and toast notification system.

---

**Version**: 3.4.0 (Missing Subscription Error Handling)  
**Date**: January 16, 2026  
**Status**: ✅ Production Ready  
**Maintainers**: Development Team

**Version History:**

- 3.4.0: Missing Subscription Errors (throw instead of warn, added January 2026)
- 3.3.0: Global Error Handler Integration (added December 2025)
- 3.2.0: Subscription Error Handling (added December 2025)

**Note**: This document consolidates the previous separate documents:

- `WEBSOCKET-CLIENT-PATTERN.md` (v2.0.0)
- `WEBSOCKET-CLIENT-BASE.md` (v2.0.0)
- `WEBSOCKET-ARCHITECTURE-DIAGRAMS.md` (v2.0.0)
- Topic Builder Compliance (previously in `docs/WEBSOCKET-CLIENTS.md`, now archived)
- Subscription Error Handling (added December 2025)
