# WebSocket Client Architecture Diagrams

**Date**: October 13, 2025
**Version**: 1.0.0

## Overview

This document provides visual diagrams to help understand the WebSocket client architecture, data flow, and patterns used in the Trading Pro frontend.

---

## 1. Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Application Layer                              │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │ DatafeedService  │  │  OrderService    │  │ AccountService   │    │
│  │                  │  │                  │  │                  │    │
│  │ - subscribeBars  │  │ - placeOrder     │  │ - getBalance     │    │
│  │ - unsubscribeBars│  │ - cancelOrder    │  │ - watchAccount   │    │
│  │ - getBars (HTTP) │  │ - watchOrders    │  │                  │    │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘    │
│           │                     │                      │               │
│           │ Uses interface      │                      │               │
└───────────┼─────────────────────┼──────────────────────┼───────────────┘
            │                     │                      │
            │                     │                      │
┌───────────▼─────────────────────▼──────────────────────▼───────────────┐
│                          Client Layer                                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  BarsWebSocketInterface                                         │  │
│  │  = WebSocketInterface<BarsSubscriptionRequest, Bar>             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                            │                                            │
│                            │ Created by                                 │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  BarsWebSocketClientFactory()                                   │  │
│  │  └─> new WebSocketClientBase<Request, Data>('bars')            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Similar patterns for:                                                  │
│  - QuotesWebSocketClientFactory() → 'quotes'                           │
│  - TradesWebSocketClientFactory() → 'trades'                           │
│  - OrdersWebSocketClientFactory() → 'orders'                           │
│                                                                         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                │ Uses/Composes
                                │
┌───────────────────────────────▼─────────────────────────────────────────┐
│                          Base Layer                                     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ WebSocketClientBase<TParams, TData>                             │  │
│  │                                                                  │  │
│  │ Static (Shared):                                                 │  │
│  │  - instances: Map<url, instance>  (Singleton registry)          │  │
│  │  - ws: WebSocket | null           (Shared connection)           │  │
│  │                                                                  │  │
│  │ Instance (Per URL):                                              │  │
│  │  - subscriptions: Map<id, state>  (Active subscriptions)        │  │
│  │  - pendingRequests: Map<id, ...>  (Awaiting responses)          │  │
│  │  - referenceCount: number         (Usage tracking)              │  │
│  │  - topicType: string              (e.g., 'bars', 'quotes')      │  │
│  │                                                                  │  │
│  │ Methods:                                                         │  │
│  │  - subscribe()      (Send request, wait confirmation)           │  │
│  │  - unsubscribe()    (Send request, cleanup)                     │  │
│  │  - sendRequest()    (Send + await response)                     │  │
│  │  - handleMessage()  (Route incoming messages)                   │  │
│  │  - connect()        (Establish WebSocket)                       │  │
│  │  - disconnect()     (Close WebSocket)                           │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                │ Uses
                                │
┌───────────────────────────────▼─────────────────────────────────────────┐
│                       Native Browser API                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ WebSocket (Browser Native)                                      │  │
│  │                                                                  │  │
│  │  - send()                                                        │  │
│  │  - close()                                                       │  │
│  │  - onopen                                                        │  │
│  │  - onmessage                                                     │  │
│  │  - onerror                                                       │  │
│  │  - onclose                                                       │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Singleton Pattern Visualization

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   WebSocket Singleton Management                        │
└─────────────────────────────────────────────────────────────────────────┘

State: Empty
┌──────────────────────────────────────┐
│ WebSocketClientBase.instances = {}   │
└──────────────────────────────────────┘


Event: BarsWebSocketClientFactory() called (URL: ws://server)
┌──────────────────────────────────────────────────────────────┐
│ WebSocketClientBase.instances = {                            │
│   'ws://server': {                                           │
│     referenceCount: 1,                                       │
│     ws: WebSocket(OPEN),                                     │
│     subscriptions: {},                                       │
│     topicType: 'bars'                                        │
│   }                                                          │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
                      │
                      │ Returns client instance #1
                      ▼
                ┌──────────────┐
                │ Client 1     │
                │ (bars)       │
                └──────────────┘


Event: QuotesWebSocketClientFactory() called (URL: ws://server)
┌──────────────────────────────────────────────────────────────┐
│ WebSocketClientBase.instances = {                            │
│   'ws://server': {                                           │
│     referenceCount: 2,  ◄─── Incremented!                   │
│     ws: WebSocket(OPEN), ◄─── Same connection reused!       │
│     subscriptions: {},                                       │
│     topicType: 'bars,quotes' ◄─── Multiple types supported  │
│   }                                                          │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
                      │
                      │ Returns same instance
                      ▼
        ┌──────────────┐    ┌──────────────┐
        │ Client 1     │    │ Client 2     │
        │ (bars)       │    │ (quotes)     │
        └──────────────┘    └──────────────┘
              │                    │
              └──────────┬─────────┘
                         │
                  Both share same
                  WebSocket connection!


Event: Client 1 calls dispose()
┌──────────────────────────────────────────────────────────────┐
│ WebSocketClientBase.instances = {                            │
│   'ws://server': {                                           │
│     referenceCount: 1,  ◄─── Decremented!                   │
│     ws: WebSocket(OPEN), ◄─── Still open (Client 2 active)  │
│     subscriptions: {},                                       │
│     topicType: 'quotes'                                      │
│   }                                                          │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
                      │
                      │ Connection remains alive
                      ▼
                ┌──────────────┐
                │ Client 2     │
                │ (quotes)     │
                └──────────────┘


Event: Client 2 calls dispose()
┌──────────────────────────────────────────────────────────────┐
│ WebSocketClientBase.instances = {}  ◄─── Cleaned up!        │
│                                                              │
│ WebSocket connection closed and removed                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Subscription Flow Sequence

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────┐
│ Service  │    │ BarsWSClient │    │ WSClientBase │    │ Server │
└────┬─────┘    └──────┬───────┘    └──────┬───────┘    └───┬────┘
     │                 │                   │                  │
     │ subscribeToBars('AAPL', '1', cb)   │                  │
     ├────────────────>│                   │                  │
     │                 │                   │                  │
     │                 │ subscribe(        │                  │
     │                 │   'bars.subscribe',                  │
     │                 │   { symbol: 'AAPL', resolution: '1' },
     │                 │   'bars:AAPL:1',  │                  │
     │                 │   'bars.update',  │                  │
     │                 │   callback        │                  │
     │                 │ )                 │                  │
     │                 ├──────────────────>│                  │
     │                 │                   │                  │
     │                 │                   │ 1. Create subscription state
     │                 │                   │    (id, topic, callback, unconfirmed)
     │                 │                   │                  │
     │                 │                   │ 2. sendRequest() │
     │                 │                   ├─────────────────>│
     │                 │                   │ { type: 'bars.subscribe',
     │                 │                   │   payload: { symbol: 'AAPL', resolution: '1' } }
     │                 │                   │                  │
     │                 │                   │                  │ Process request
     │                 │                   │                  │ Subscribe to topic
     │                 │                   │                  │
     │                 │                   │ 3. Response      │
     │                 │                   │<─────────────────┤
     │                 │                   │ { type: 'bars.subscribe.response',
     │                 │                   │   payload: { status: 'ok', topic: 'bars:AAPL:1' } }
     │                 │                   │                  │
     │                 │                   │ 4. Verify:       │
     │                 │                   │    - topic matches
     │                 │                   │    - status == 'ok'
     │                 │                   │                  │
     │                 │                   │ 5. Mark subscription confirmed
     │                 │                   │                  │
     │                 │ subscriptionId    │                  │
     │                 │<──────────────────┤                  │
     │                 │                   │                  │
     │ subscriptionId  │                   │                  │
     │<────────────────┤                   │                  │
     │                 │                   │                  │
     │ Store subId     │                   │                  │
     │                 │                   │                  │
     │                 │                   │                  │
     │                 │                   │ 6. Bar Update    │
     │                 │                   │<─────────────────┤
     │                 │                   │ { type: 'bars.update',
     │                 │                   │   payload: { time: ..., open: ..., ... } }
     │                 │                   │                  │
     │                 │                   │ 7. Route to confirmed
     │                 │                   │    subscriptions with
     │                 │                   │    updateType == 'bars.update'
     │                 │                   │                  │
     │                 │ callback(bar)     │                  │
     │                 │<──────────────────┤                  │
     │                 │                   │                  │
     │ onTick(bar)     │                   │                  │
     │<────────────────┤                   │                  │
     │                 │                   │                  │
     │ Forward to      │                   │                  │
     │ TradingView     │                   │                  │
     │                 │                   │                  │
```

---

## 4. Topic-Based Routing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Topic-Based Message Routing                           │
└─────────────────────────────────────────────────────────────────────────┘

Server broadcasts:
  { type: 'bars.update', payload: { time: ..., open: ... } }
                    │
                    ▼
          WSClientBase.handleMessage()
                    │
                    │ Check: Is this an update message?
                    │ (type.endsWith('.update'))
                    │
                    ▼ YES
          routeUpdateMessage('bars.update', payload)
                    │
                    ▼
     Loop through all subscriptions:
     
     ┌─────────────────────────────────────────────────────┐
     │ Subscription 1:                                     │
     │   id: 'sub_123'                                     │
     │   topic: 'bars:AAPL:1'                              │
     │   updateType: 'bars.update'  ◄─── MATCH!           │
     │   confirmed: true            ◄─── CONFIRMED!       │
     │   callback: (bar) => { ... }                        │
     │                                                     │
     │ Action: Call callback(payload) ✅                   │
     └─────────────────────────────────────────────────────┘
     
     ┌─────────────────────────────────────────────────────┐
     │ Subscription 2:                                     │
     │   id: 'sub_456'                                     │
     │   topic: 'bars:GOOGL:5'                             │
     │   updateType: 'bars.update'  ◄─── MATCH!           │
     │   confirmed: true            ◄─── CONFIRMED!       │
     │   callback: (bar) => { ... }                        │
     │                                                     │
     │ Action: Call callback(payload) ✅                   │
     └─────────────────────────────────────────────────────┘
     
     ┌─────────────────────────────────────────────────────┐
     │ Subscription 3:                                     │
     │   id: 'sub_789'                                     │
     │   topic: 'quotes:TSLA'                              │
     │   updateType: 'quotes.update' ◄─── NO MATCH!       │
     │   confirmed: true                                   │
     │   callback: (quote) => { ... }                      │
     │                                                     │
     │ Action: Skip ⏭️                                     │
     └─────────────────────────────────────────────────────┘
     
     ┌─────────────────────────────────────────────────────┐
     │ Subscription 4:                                     │
     │   id: 'sub_101'                                     │
     │   topic: 'bars:MSFT:D'                              │
     │   updateType: 'bars.update'  ◄─── MATCH!           │
     │   confirmed: false           ◄─── NOT CONFIRMED!   │
     │   callback: (bar) => { ... }                        │
     │                                                     │
     │ Action: Skip (waiting for confirmation) ⏭️          │
     └─────────────────────────────────────────────────────┘
```

---

## 5. Connection State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   WebSocket Connection States                           │
└─────────────────────────────────────────────────────────────────────────┘

                        [INITIAL STATE]
                              │
                              │ getInstance(config)
                              ▼
                        [CONNECTING]
                              │
                              │ Attempt 1: delay 0ms
                              ▼
                        ┌─────────┐
                        │ ws.open │
                        └────┬────┘
                             │
                ┌────────────┴────────────┐
                │                         │
            SUCCESS                    FAILURE
                │                         │
                ▼                         ▼
          [CONNECTED] ◄────────────  [RETRY DELAY]
                │                         │
                │                         │ Exponential backoff
                │                         │ (1s, 2s, 4s, 8s...)
                │                         │
                │                         ▼
                │                    [CONNECTING]
                │                         │
                │                         │ Max attempts reached?
                │                         │
                │                         ├──YES──> [FAILED]
                │                         │
                │                         └──NO───> (retry)
                │
                │ WebSocket.onclose or onerror
                ▼
          [DISCONNECTED]
                │
                │ config.reconnect == true?
                │
                ├──YES──> [RECONNECTING]
                │              │
                │              │ 1. Clear pending requests
                │              │ 2. Attempt reconnection
                │              │ 3. Resubscribe all confirmed
                │              │
                │              ▼
                │         [CONNECTING] (loop back)
                │
                └──NO───> [TERMINATED]
```

---

## 6. Message Type Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Message Types and Handling                           │
└─────────────────────────────────────────────────────────────────────────┘

Incoming Message from Server
       │
       ▼
  Parse JSON → { type: string, payload: any }
       │
       ▼
  Check message type
       │
       ├─────────────────────────────────────────────┐
       │                                             │
       │ Type ends with '.response'?                 │
       │                                             │
  ┌────▼────┐                                  ┌─────▼─────┐
  │   YES   │                                  │    NO     │
  └────┬────┘                                  └─────┬─────┘
       │                                             │
       │ Look up in pendingRequests                  │ Type ends with '.update'?
       │ using requestId                             │
       ▼                                        ┌────▼────┐
  ┌──────────────────────┐                     │   YES   │
  │ Found?               │                     └────┬────┘
  └──┬────────────────┬──┘                          │
     │ YES            │ NO                           │ Route to subscriptions
     │                │                              ▼
     ▼                ▼                    ┌───────────────────┐
  Resolve         Log 'No                 │ Loop through all  │
  promise         matching                │ subscriptions     │
  with payload    request'                └────────┬──────────┘
                                                   │
                                                   │ Filter by:
                                                   │ - confirmed == true
                                                   │ - updateType matches
                                                   │
                                                   ▼
                                          ┌─────────────────────┐
                                          │ Call each callback  │
                                          │ callback(payload)   │
                                          └─────────────────────┘


Message Type Examples:

┌────────────────────────────────────────────────────────────────┐
│ REQUEST (Client → Server)                                      │
│  type: 'bars.subscribe'                                        │
│  payload: { symbol: 'AAPL', resolution: '1' }                  │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│ RESPONSE (Server → Client)                                     │
│  type: 'bars.subscribe.response'  ◄─── Matches pattern         │
│  payload: { status: 'ok', topic: 'bars:AAPL:1' }              │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ UPDATE (Server → Client, broadcast)                            │
│  type: 'bars.update'  ◄─── Ends with '.update'                 │
│  payload: { time: ..., open: ..., high: ..., ... }            │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Error Handling                                   │
└─────────────────────────────────────────────────────────────────────────┘

Subscription Request
       │
       ▼
  Send subscribe message
       │
       ├──────────────────────────────────────┐
       │                                      │
  Wait for response                      Timeout (5s)
       │                                      │
       ▼                                      ▼
  Response received                    ┌──────────────┐
       │                               │ Reject with  │
       │                               │ timeout error│
       ▼                               └──────────────┘
  Check status field                          │
       │                                      │
       ├────────────────────┐                 │
       │                    │                 │
  status == 'ok'       status == 'error'      │
       │                    │                 │
       ▼                    ▼                 │
  Check topic          ┌──────────────┐      │
       │               │ Reject with  │      │
       │               │ server error │      │
       ▼               └──────────────┘      │
  topic matches?              │              │
       │                      │              │
  ┌────┴────┐                 │              │
  │ YES     │ NO              │              │
  ▼         ▼                 │              │
SUCCESS  ┌──────────────┐    │              │
  │      │ Reject with  │    │              │
  │      │ topic error  │    │              │
  │      └──────────────┘    │              │
  │            │              │              │
  │            └──────────────┴──────────────┘
  │                          │
  │                          ▼
  │                    [CATCH BLOCK]
  │                          │
  │                          ▼
  │                    Log error
  │                    Notify service
  │                    (optional: retry)
  │
  ▼
Mark subscription
as confirmed
```

---

## 8. Reconnection Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Reconnection Flow                                   │
└─────────────────────────────────────────────────────────────────────────┘

Connection Lost (WebSocket.onclose)
       │
       ▼
  config.reconnect == true?
       │
  ┌────┴────┐
  │   NO    │ YES
  ▼         ▼
[DONE]   [RECONNECTING]
              │
              ▼
    Clear pending requests
    (reject all with error)
              │
              ▼
    Attempt reconnection
    with exponential backoff
              │
         ┌────┴────┐
         │ SUCCESS │ FAILURE (max retries)
         ▼         ▼
   [CONNECTED]  [FAILED]
         │          │
         ▼          └──> Notify service
    Resubscribe         (connection lost)
    all confirmed
    subscriptions
         │
         ▼
    For each subscription:
      1. Send subscribe request
      2. Wait for confirmation
      3. Mark as confirmed
         │
         ▼
    [FULLY RESTORED]
         │
         └──> Resume normal operation

Exponential Backoff:
  Attempt 1: 0ms
  Attempt 2: 1000ms
  Attempt 3: 2000ms
  Attempt 4: 4000ms
  Attempt 5: 8000ms
  (Max attempts: 5)
```

---

## 9. Factory Pattern Usage

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Factory Pattern                                     │
└─────────────────────────────────────────────────────────────────────────┘

Application Code:
┌────────────────────────────────────────────────────────┐
│ import { BarsWebSocketClientFactory }                 │
│                                                        │
│ const client = BarsWebSocketClientFactory()           │
└────────────────────────┬───────────────────────────────┘
                         │
                         │ Calls factory
                         ▼
Factory Implementation:
┌────────────────────────────────────────────────────────┐
│ export function BarsWebSocketClientFactory() {        │
│   return new WebSocketClientBase<                     │
│     BarsSubscriptionRequest,                          │
│     Bar                                               │
│   >('bars')                                           │
│ }                                                      │
└────────────────────────┬───────────────────────────────┘
                         │
                         │ Creates instance
                         ▼
Base Class Constructor:
┌────────────────────────────────────────────────────────┐
│ constructor(topicType: string) {                       │
│   this.topicType = topicType  // 'bars'              │
│   // Initialize subscriptions, etc.                   │
│ }                                                      │
└────────────────────────┬───────────────────────────────┘
                         │
                         │ Returns
                         ▼
┌────────────────────────────────────────────────────────┐
│ Type: BarsWebSocketInterface                           │
│ = WebSocketInterface<BarsSubscriptionRequest, Bar>    │
│                                                        │
│ Methods:                                               │
│  - subscribe(params, callback): Promise<string>       │
│  - unsubscribe(id): Promise<void>                     │
└────────────────────────────────────────────────────────┘


Type Safety Guarantee:
┌────────────────────────────────────────────────────────┐
│ const client = BarsWebSocketClientFactory()           │
│                                                        │
│ // ✅ TypeScript knows:                               │
│ // - params must be BarsSubscriptionRequest          │
│ // - callback receives Bar                           │
│                                                        │
│ await client.subscribe(                               │
│   { symbol: 'AAPL', resolution: '1' }, // Typed!     │
│   (bar: Bar) => {                      // Typed!     │
│     console.log(bar.open)              // Typed!     │
│   }                                                   │
│ )                                                     │
└────────────────────────────────────────────────────────┘
```

---

## 10. Integration with DatafeedService

```
┌─────────────────────────────────────────────────────────────────────────┐
│              DatafeedService Integration                                │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ TradingView Chart Library                                           │
│                                                                      │
│  subscribeBars(symbolInfo, resolution, onTick, listenerGuid)        │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ Calls
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ DatafeedService (Adapter)                                           │
│                                                                      │
│  subscribeBars(symbolInfo, resolution, onTick, listenerGuid) {      │
│    if (!this.wsClient) return                                       │
│                                                                      │
│    this.wsClient.subscribe(                                         │
│      { symbol: symbolInfo.name, resolution },                       │
│      (bar) => {                                                     │
│        onTick(bar)  // Forward to TradingView                       │
│      }                                                              │
│    ).then(wsSubscriptionId => {                                     │
│      this.subscriptions.set(listenerGuid, { wsSubscriptionId })    │
│    })                                                               │
│  }                                                                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ Uses
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ BarsWebSocketClient                                                  │
│                                                                      │
│  subscribe(params, callback) {                                      │
│    return this.instance.subscribe(                                  │
│      'bars.subscribe',                                              │
│      params,                                                        │
│      topic,                                                         │
│      'bars.update',                                                 │
│      callback                                                       │
│    )                                                                │
│  }                                                                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ Delegates to
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketClientBase                                                  │
│                                                                      │
│  async subscribe(...) {                                             │
│    // 1. Send subscribe request                                     │
│    // 2. Wait for confirmation                                      │
│    // 3. Register callback                                          │
│    // 4. Return subscription ID                                     │
│  }                                                                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ Communicates with
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Backend (FastWS)                                                     │
│                                                                      │
│  @router.send("subscribe")                                          │
│  async def send_subscribe(...):                                     │
│    client.subscribe(topic)                                          │
│    return SubscriptionResponse(status='ok', topic=...)              │
│                                                                      │
│  @router.recv("update")                                             │
│  async def update(...):                                             │
│    # Broadcast to all subscribed clients                            │
└──────────────────────────────────────────────────────────────────────┘


Data Flow:
1. TradingView requests subscription
2. DatafeedService forwards to WebSocket client
3. WebSocket client sends subscribe message to server
4. Server confirms subscription
5. WebSocket client registers callback
6. Server broadcasts bar updates
7. WebSocket client routes update to callback
8. DatafeedService forwards bar to TradingView
9. TradingView updates chart
```

---

**End of Diagrams**

These diagrams illustrate the key architectural patterns, data flows, and component interactions in the WebSocket client implementation. For more details, refer to:

- [`WEBSOCKET-CLIENT-PATTERN.md`](./WEBSOCKET-CLIENT-PATTERN.md) - Comprehensive pattern documentation
- [`WEBSOCKET-IMPLEMENTATION-SUMMARY.md`](./WEBSOCKET-IMPLEMENTATION-SUMMARY.md) - Implementation summary
- [`WEBSOCKET-CLIENT-BASE.md`](./WEBSOCKET-CLIENT-BASE.md) - Base client deep dive

---

**Version**: 1.0.0
**Date**: October 13, 2025
**Status**: ✅ Complete
