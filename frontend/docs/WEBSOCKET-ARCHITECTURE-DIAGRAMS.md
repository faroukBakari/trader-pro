# WebSocket Architecture Diagrams

**Date**: November 11, 2025  
**Version**: 2.0.0  
**Status**: ✅ Production Ready

## Overview

Visual reference for the WebSocket architecture in Trading Pro frontend, showing the WsAdapter facade pattern, modular backend integration, and centralized subscription management.

---

## 1. Complete System Architecture

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

---

## 2. Modular Backend Integration

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

---

## 3. Singleton Pattern per URL

```
┌───────────────────────────────────────────────────────────────────────────┐
│                   WebSocketBase Singleton Management                      │
└───────────────────────────────────────────────────────────────────────────┘

Initial State:
┌───────────────────────────────────────┐
│ WebSocketBase.instances = Map()       │
│ (empty)                               │
└───────────────────────────────────────┘


Step 1: WsAdapter creates bars client (URL: /v1/datafeed/ws)
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase {                               │
│     wsUrl: '/v1/datafeed/ws',                                        │
│     ws: WebSocket(CONNECTING...),                                    │
│     subscriptions: Map(),                                            │
│     pendingRequests: Map(),                                          │
│     reconnectAttempts: 0                                             │
│   }                                                                  │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ Returns reference to singleton
         ▼
┌──────────────────┐
│ bars client      │ ──> uses WebSocketBase('/v1/datafeed/ws')
└──────────────────┘


Step 2: WsAdapter creates quotes client (URL: /v1/datafeed/ws)
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase {  ◄── SAME INSTANCE REUSED!   │
│     wsUrl: '/v1/datafeed/ws',                                        │
│     ws: WebSocket(OPEN),                                             │
│     subscriptions: Map(),                                            │
│     pendingRequests: Map(),                                          │
│     reconnectAttempts: 0                                             │
│   }                                                                  │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
         │
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


Step 3: WsAdapter creates orders client (URL: /v1/broker/ws)
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase { ... },                        │
│   '/v1/broker/ws' => WebSocketBase {      ◄── NEW INSTANCE!         │
│     wsUrl: '/v1/broker/ws',                                          │
│     ws: WebSocket(CONNECTING...),                                    │
│     subscriptions: Map(),                                            │
│     pendingRequests: Map(),                                          │
│     reconnectAttempts: 0                                             │
│   }                                                                  │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ Returns reference to new singleton
         ▼
┌──────────────────┐
│ orders client    │ ──> uses WebSocketBase('/v1/broker/ws')
└──────────────────┘


Final State: 2 Singleton Instances
┌──────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.instances = Map {                                      │
│   '/v1/datafeed/ws' => WebSocketBase { ... },   ◄── Shared by 2     │
│   '/v1/broker/ws' => WebSocketBase { ... }      ◄── Shared by 5     │
│ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
         │                              │
         │                              │
         ▼                              ▼
   ┌──────────┐                  ┌──────────┐
   │ Datafeed │                  │ Broker   │
   │ Clients  │                  │ Clients  │
   ├──────────┤                  ├──────────┤
   │ • bars   │                  │ • orders │
   │ • quotes │                  │ • posits │
   └──────────┘                  │ • execs  │
                                 │ • equity │
                                 │ • broker │
                                 │   conn   │
                                 └──────────┘
```

---

## 4. Subscription Lifecycle

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Subscribe Flow                                   │
└───────────────────────────────────────────────────────────────────────────┘

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
│ - Server knows about subscription                                  │
│ - Base client tracks state                                         │
│ - Future updates routed to listener                                │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Message Routing

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Message Flow                                     │
└───────────────────────────────────────────────────────────────────────────┘

Backend sends update:
┌────────────────────────────────────────────────────────────────────┐
│ {                                                                  │
│   "type": "bars.update",                                           │
│   "topic": "bars:AAPL:1",                                          │
│   "data": { time: 1234567890, open: 150.0, ... }                  │
│ }                                                                  │
└────────────┬───────────────────────────────────────────────────────┘
             │
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
│ │                   for this topic                              │ │
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
│ WebSocketClient receives update (backend type)                     │
│ - Applies mapper: mapBar(backendData) → frontendData              │
│ - Calls service callback with frontend types                       │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ Service callback executes (frontend types only)                    │
│ datafeedService: onRealtimeCallback(bar)                           │
└────────────────────────────────────────────────────────────────────┘
```

---

## 6. Reference Counting (Subscription Cleanup)

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Unsubscribe Flow                                 │
└───────────────────────────────────────────────────────────────────────────┘

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
┌────────────────────────────────────────────────────────────────────┐
│ wsAdapter.bars.unsubscribe('listener-1')                           │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.unsubscribe('listener-1', 'bars:AAPL:1')            │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Remove listener-1 from subscription.listeners                  │ │
│ │                                                                │ │
│ │ listeners.size > 0?                                            │ │
│ │ ┌─────────┐              ┌───────────┐                        │ │
│ │ │ Yes:    │              │ No:       │                        │ │
│ │ │ Keep    │              │ Send      │                        │ │
│ │ │ sub     │              │ unsub to  │                        │ │
│ │ │ active  │              │ server +  │                        │ │
│ │ │         │              │ delete    │                        │ │
│ │ │ (other  │              │ sub       │                        │ │
│ │ │ listener│              │           │                        │ │
│ │ │ still   │              │           │                        │ │
│ │ │ using)  │              │           │                        │ │
│ │ └─────────┘              └───────────┘                        │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
Updated State: 1 listener remains
┌────────────────────────────────────────────────────────────────────┐
│ subscriptions.get("bars:AAPL:1") = {                               │
│   topic: "bars:AAPL:1",                                            │
│   confirmed: true,                                                 │
│   listeners: Map {                                                 │
│     'listener-2' => callback2  ◄── Only listener-2 remains        │
│   }                                                                │
│ }                                                                  │
└────────────────────────────────────────────────────────────────────┘


Event: listener-2 unsubscribes (last listener!)
┌────────────────────────────────────────────────────────────────────┐
│ wsAdapter.bars.unsubscribe('listener-2')                           │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.unsubscribe('listener-2', 'bars:AAPL:1')            │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Remove listener-2 from subscription.listeners                  │ │
│ │                                                                │ │
│ │ listeners.size = 0  ◄── LAST LISTENER GONE!                   │ │
│ │                                                                │ │
│ │ Actions:                                                       │ │
│ │ 1. Send bars.unsubscribe to server                            │ │
│ │ 2. Delete subscription from Map                               │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
Final State: Subscription removed
┌────────────────────────────────────────────────────────────────────┐
│ subscriptions.has("bars:AAPL:1") = false  ◄── Cleaned up!         │
└────────────────────────────────────────────────────────────────────┘
```

---

## 7. Reconnection with Resubscription

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Reconnection Flow                                │
└───────────────────────────────────────────────────────────────────────────┘

Active State: 3 active subscriptions
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase('/v1/datafeed/ws') {                                 │
│   ws: WebSocket(OPEN),                                             │
│   subscriptions: Map {                                             │
│     'bars:AAPL:1' => { confirmed: true, listeners: [...] },        │
│     'bars:TSLA:5' => { confirmed: true, listeners: [...] },        │
│     'quotes:AAPL' => { confirmed: true, listeners: [...] }         │
│   }                                                                │
│ }                                                                  │
└────────────────────────────────────────────────────────────────────┘
                     │
                     │ Network issue / Server restart
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocket.onclose triggered                                        │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.handleClose()                                        │
│ - isReconnecting = true                                            │
│ - reconnectAttempts++                                              │
│ - Schedule reconnect with exponential backoff                      │
└────────────┬───────────────────────────────────────────────────────┘
             │
             │ Wait (1s, 2s, 4s, 8s, or 16s)
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.connect()                                            │
│ - Create new WebSocket                                             │
│ - Wait for open                                                    │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocket.onopen triggered                                         │
│ - reconnectAttempts = 0                                            │
│ - isReconnecting = false                                           │
│ - Call resubscribeAll()                                            │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase.resubscribeAll()                                     │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ For each subscription in Map:                                  │ │
│ │                                                                │ │
│ │   1. Mark as unconfirmed                                       │ │
│ │   2. Send subscribe request to server                          │ │
│ │   3. Wait for confirmation                                     │ │
│ │   4. Mark as confirmed (or log error)                          │ │
│ │                                                                │ │
│ │ Results:                                                       │ │
│ │   ✅ bars:AAPL:1 resubscribed                                  │ │
│ │   ✅ bars:TSLA:5 resubscribed                                  │ │
│ │   ✅ quotes:AAPL resubscribed                                  │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
Reconnected State: All subscriptions restored
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase('/v1/datafeed/ws') {                                 │
│   ws: WebSocket(OPEN),  ◄── New connection                         │
│   subscriptions: Map {  ◄── Same subscriptions preserved           │
│     'bars:AAPL:1' => { confirmed: true, listeners: [...] },        │
│     'bars:TSLA:5' => { confirmed: true, listeners: [...] },        │
│     'quotes:AAPL' => { confirmed: true, listeners: [...] }         │
│   }                                                                │
│ }                                                                  │
│                                                                    │
│ Services unaware of reconnection! ✅                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. Type Transformation Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Type Flow (Backend → Frontend)                   │
└───────────────────────────────────────────────────────────────────────────┘

Backend sends (WebSocket):
┌────────────────────────────────────────────────────────────────────┐
│ {                                                                  │
│   "type": "quotes.update",                                         │
│   "topic": "quotes:AAPL",                                          │
│   "data": {                                                        │
│     "s": "ok",                                                     │
│     "n": "AAPL",                                                   │
│     "v": {                                                         │
│       "lp": 150.0,      // last_price (backend naming)            │
│       "bid": 149.9,                                                │
│       "ask": 150.1,                                                │
│       // ... backend field names                                  │
│     }                                                              │
│   }                                                                │
│ }                                                                  │
└────────────┬───────────────────────────────────────────────────────┘
             │
             │ Type: QuoteData_Ws_Backend (generated from AsyncAPI)
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ WebSocketBase routes to WebSocketClient callback                   │
└────────────┬───────────────────────────────────────────────────────┘
             │
             │ Apply mapper
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ mapQuoteData(backendData: QuoteData_Ws_Backend): QuoteData         │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ if (backendData.s === 'error') {                               │ │
│ │   return { s: 'error', n: backendData.n, v: backendData.v }    │ │
│ │ }                                                              │ │
│ │                                                                │ │
│ │ return {                                                       │ │
│ │   s: 'ok',                                                     │ │
│ │   n: backendData.n,                                            │ │
│ │   v: { ...backendData.v } // Copy all fields                  │ │
│ │ }                                                              │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────┬───────────────────────────────────────────────────────┘
             │
             │ Type: QuoteData (TradingView frontend type)
             ▼
┌────────────────────────────────────────────────────────────────────┐
│ Service callback receives frontend type                            │
│ datafeedService.subscribeQuotes(..., (quote: QuoteData) => {       │
│   // quote is frontend type - no backend types leaked!            │
│   console.log(quote.v.lp)  // TypeScript autocomplete works       │
│ })                                                                 │
└────────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key Pattern: Backend types isolated to mappers.ts ONLY          ┃
┃ - Services: import frontend types (TradingView)                 ┃
┃ - Mappers: import backend types (_Ws_Backend suffix)            ┃
┃ - Clients: generic with mapper function, no backend imports     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Conclusion

This architecture provides:

- ✅ **Efficiency** - 2 WebSocket connections for all features
- ✅ **Type Safety** - Backend types isolated to mappers
- ✅ **Simplicity** - Services just call subscribe/unsubscribe
- ✅ **Resilience** - Automatic reconnection with resubscription
- ✅ **Modularity** - Backend modules can deploy independently
- ✅ **Scalability** - Reference counting prevents resource leaks

### Related Documentation

- [WEBSOCKET-CLIENT-PATTERN.md](./WEBSOCKET-CLIENT-PATTERN.md) - Implementation patterns and usage guide
- [WEBSOCKET-CLIENT-BASE.md](./WEBSOCKET-CLIENT-BASE.md) - WebSocketBase detailed reference

---

**Version**: 2.0.0  
**Date**: November 11, 2025  
**Status**: ✅ Production Ready  
**Maintainers**: Development Team
