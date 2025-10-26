# Broker WebSocket Integration - Implementation Methodology

**Version**: 1.0.0  
**Date**: October 22, 2025  
**Status**: 📋 Planning Phase  
**Related**: `IBROKERCONNECTIONADAPTERHOST.md`, `BROKER-TERMINAL-SERVICE.md`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Strategy](#architecture-strategy)
3. [WebSocket Client Pattern](#websocket-client-pattern)
4. [Implementation Phases](#implementation-phases)
5. [Required WebSocket Data Flows](#required-websocket-data-flows)
6. [Integration Pattern](#integration-pattern)
7. [Technical Details](#technical-details)
8. [Testing Strategy](#testing-strategy)

---

## Overview

This document outlines the **WebSocket-driven broker integration** strategy for connecting the TradingView Trading Terminal with a backend broker service. The approach leverages the existing WebSocket infrastructure (`WebSocketBase`, `WsAdapter`) to create a real-time, event-driven trading system.

### Core Principle

**Backend is the source of truth**. All broker state (orders, positions, executions, P&L) lives on the backend. The frontend is a thin relay layer that:

1. **Sends commands** via REST API (place/modify/cancel orders)
2. **Receives events** via WebSocket (order updates, position changes, executions)
3. **Pushes updates** to TradingView via `IBrokerConnectionAdapterHost`

### Key Characteristics

- 🎯 **Event-Driven**: Backend WebSocket events drive all UI updates
- 🔄 **No Local State**: Frontend doesn't track orders/positions (backend does)
- 📡 **Real-Time**: Sub-second latency for broker events
- 🏗️ **Existing Infrastructure**: Uses proven `WebSocketBase` singleton pattern
- 🔌 **Clean Separation**: REST for commands, WebSocket for events
- 🛡️ **Type-Safe**: Full TypeScript/Pydantic type safety with mappers

---

## Architecture Strategy

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

## WebSocket Client Pattern

### Leveraging Existing Infrastructure

The broker WebSocket clients follow the **exact same pattern** as the existing bar/quote clients:

```typescript
// frontend/src/plugins/wsAdapter.ts
import { WebSocketClient } from './wsClientBase.js'
import { mapOrder, mapPosition, mapExecution } from './mappers.js'

export class WsAdapter {
  // Existing clients
  bars: WebSocketClient<BarsSubscriptionRequest, Bar_backend, Bar>
  quotes: WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_backend, QuoteData>

  // NEW: Broker clients (same pattern!)
  orders: WebSocketClient<OrderSubscriptionRequest, Order_backend, Order>
  positions: WebSocketClient<PositionSubscriptionRequest, Position_backend, Position>
  executions: WebSocketClient<ExecutionSubscriptionRequest, Execution_backend, Execution>
  equity: WebSocketClient<EquitySubscriptionRequest, EquityData_backend, EquityData>

  constructor() {
    // Existing
    this.bars = new WebSocketClient('bars', (data) => data)
    this.quotes = new WebSocketClient('quotes', mapQuoteData)

    // NEW: Broker
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

---

## Implementation Phases

### Phase 1: Backend WebSocket Operations (Backend Team)

**Goal**: Create broker WebSocket endpoints and message types

**Tasks**:

1. Define backend models in `backend/src/trading_api/models/broker/`
   - `OrderSubscriptionRequest`, `OrderUpdate`
   - `PositionSubscriptionRequest`, `PositionUpdate`
   - `ExecutionSubscriptionRequest`, `ExecutionUpdate`
   - `EquitySubscriptionRequest`, `EquityUpdate`

2. Create WebSocket router `backend/src/trading_api/ws/broker.py`

   ```python
   router = OperationRouter(prefix="orders.", tags=["broker"])

   @router.send("subscribe", reply="subscribe.response")
   async def subscribe_orders(...)

   @router.recv("update")
   async def order_update(...)
   ```

3. Implement broadcast logic in broker service
   - Broadcast order updates after state changes
   - Broadcast position updates
   - Broadcast executions
   - Broadcast equity updates

4. Update AsyncAPI spec (auto-generated)
5. Test WebSocket operations

**Verification**: Backend WebSocket tests pass

---

### Phase 2: Frontend Type Generation

**Goal**: Generate TypeScript types from backend AsyncAPI spec

**Tasks**:

1. Run type generator: `cd frontend && make generate-asyncapi-types`
2. Verify generated types in `frontend/src/clients/ws-types-generated/`
   - `OrderSubscriptionRequest`
   - `Order_backend`
   - `PositionSubscriptionRequest`
   - `Position_backend`
   - `ExecutionSubscriptionRequest`
   - `Execution_backend`
   - `EquitySubscriptionRequest`
   - `EquityData_backend`

3. Create data mappers in `frontend/src/plugins/mappers.ts`
   ```typescript
   export function mapOrder(order: Order_backend): Order { ... }
   export function mapPosition(pos: Position_backend): Position { ... }
   export function mapExecution(exec: Execution_backend): Execution { ... }
   ```

**Verification**: Types compile, no TypeScript errors

---

### Phase 3: Extend WsAdapter

**Goal**: Add broker WebSocket clients to `WsAdapter`

**Tasks**:

1. Update `frontend/src/plugins/wsAdapter.ts`
   - Add broker client properties
   - Instantiate with mappers
   - Export types

2. Test WebSocket subscription
   ```typescript
   const ws = new WsAdapter()
   await ws.orders.subscribe('test', { accountId: 'ACC-1' }, (order) => {
     console.log('Order update:', order)
   })
   ```

**Verification**: Can subscribe and receive messages

---

### Phase 4: Wire to IBrokerConnectionAdapterHost

**Goal**: Connect WebSocket events to TradingView Trading Host

**Tasks**:

1. Update `BrokerTerminalService` constructor

   ```typescript
   constructor(host, ...) {
     this._host = host
     this._wsAdapter = new WsAdapter()
     this.setupWebSocketHandlers()
   }
   ```

2. Implement `setupWebSocketHandlers()`

   ```typescript
   private setupWebSocketHandlers(): void {
     // Order updates
     this._wsAdapter.orders.subscribe(
       'broker-orders',
       { accountId: this._accountId },
       (order) => this._host.orderUpdate(order)
     )

     // Position updates
     this._wsAdapter.positions.subscribe(...)

     // Execution updates
     this._wsAdapter.executions.subscribe(...)

     // Equity updates
     this._wsAdapter.equity.subscribe(...)
   }
   ```

3. Update REST API methods (don't call `_host.orderUpdate()` after API calls)
   ```typescript
   async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
     const response = await this._apiAdapter.placeOrder(order)
     // No _host.orderUpdate() here - WebSocket will push it
     return response.data
   }
   ```

**Verification**: UI updates when backend broadcasts events

---

### Phase 5: Handle Connection State

**Goal**: Sync WebSocket connection status with TradingView

**Tasks**:

1. Track WebSocket connection state
2. Call `_host.connectionStatusUpdate()` on connect/disconnect
3. Show user notifications on connection issues
4. Handle reconnection gracefully

**Verification**: Connection status shown in UI

---

### Phase 6: Testing & Validation

**Goal**: End-to-end testing of WebSocket integration

**Tasks**:

1. Unit tests for mappers
2. Integration tests (frontend + backend)
3. Manual testing:
   - Place order → See in UI immediately
   - Backend fills order → UI updates
   - Position opens → UI shows position
   - Disconnect → UI shows disconnected
   - Reconnect → Resubscribes automatically

**Verification**: All tests pass, manual testing successful

---

## Required WebSocket Data Flows

### 1. Order Updates (`orders.*`)

**Topic Pattern**: `orders:{accountId}`

**Subscribe Request**:

```typescript
interface OrderSubscriptionRequest {
  accountId: string // "DEMO-001"
}
```

**Subscribe Response**:

```typescript
interface SubscriptionResponse {
  status: 'ok' | 'error'
  message: string
  topic: string // "orders:DEMO-001"
}
```

**Update Message** (Backend → Frontend):

```typescript
interface OrderUpdate {
  type: 'orders.update'
  payload: Order_backend // Complete order object
}
```

**Order Object** (TradingView format):

```typescript
interface Order {
  id: string // "ORDER-123"
  symbol: string // "AAPL"
  type: OrderType // Limit, Market, Stop, StopLimit
  side: Side // Buy (1) or Sell (-1)
  qty: number // 100
  status: OrderStatus // Working, Filled, Canceled, Rejected
  limitPrice?: number // 150.50
  stopPrice?: number // 148.00
  filledQty?: number // 0 or partial fill
  avgPrice?: number // Average fill price
  updateTime?: number // Timestamp
  takeProfit?: number // TP price
  stopLoss?: number // SL price
}
```

**When to Broadcast**:

- Order placed (status: Working)
- Order modified (price/qty changed)
- Order filled (status: Filled, filledQty updated)
- Order partially filled (filledQty incremented)
- Order canceled (status: Canceled)
- Order rejected (status: Rejected)

**Frontend Handler**:

```typescript
this._wsAdapter.orders.subscribe(
  'broker-orders',
  { accountId: this._accountId },
  (order: Order) => {
    this._host.orderUpdate(order) // Push to TradingView

    // Optional: Show notification
    if (order.status === OrderStatus.Filled) {
      this._host.showNotification(
        'Order Filled',
        `Order ${order.id} executed at ${order.avgPrice}`,
        NotificationType.Success,
      )
    }
  },
)
```

---

### 2. Position Updates (`positions.*`)

**Topic Pattern**: `positions:{accountId}`

**Subscribe Request**:

```typescript
interface PositionSubscriptionRequest {
  accountId: string
}
```

**Update Message**:

```typescript
interface PositionUpdate {
  type: 'positions.update'
  payload: Position_backend
}
```

**Position Object**:

```typescript
interface Position {
  id: string // "AAPL-POS-1"
  symbol: string // "AAPL"
  qty: number // 100
  side: Side // Buy (1) or Sell (-1)
  avgPrice: number // 150.00
  pl?: number // Unrealized P&L (optional, can use plUpdate)
  takeProfit?: number // TP price
  stopLoss?: number // SL price
}
```

**When to Broadcast**:

- Position opened (after order fill)
- Position quantity changed (additional fills)
- Position closed (qty → 0)
- Position brackets updated (SL/TP changed)
- Position reversed (side flipped)

**Frontend Handler**:

```typescript
this._wsAdapter.positions.subscribe(
  'broker-positions',
  { accountId: this._accountId },
  (position: Position) => {
    this._host.positionUpdate(position)
  },
)
```

---

### 3. Execution Updates (`executions.*`)

**Topic Pattern**: `executions:{accountId}`  
**Or**: `executions:{accountId}:{symbol}` (symbol-specific)

**Subscribe Request**:

```typescript
interface ExecutionSubscriptionRequest {
  accountId: string
  symbol?: string // Optional: filter by symbol
}
```

**Update Message**:

```typescript
interface ExecutionUpdate {
  type: 'executions.update'
  payload: Execution_backend
}
```

**Execution Object**:

```typescript
interface Execution {
  symbol: string // "AAPL"
  price: number // 150.25
  qty: number // 100
  side: Side // Buy (1) or Sell (-1)
  time: number // Unix timestamp (ms)
  orderId?: string // Optional: link to order
}
```

**When to Broadcast**:

- Order filled (fully or partially)
- Trade executed

**Frontend Handler**:

```typescript
this._wsAdapter.executions.subscribe(
  'broker-executions',
  { accountId: this._accountId },
  (execution: Execution) => {
    this._host.executionUpdate(execution)
  },
)
```

---

### 4. Equity/P&L Updates (`equity.*`)

**Topic Pattern**: `equity:{accountId}`

**Subscribe Request**:

```typescript
interface EquitySubscriptionRequest {
  accountId: string
}
```

**Update Message**:

```typescript
interface EquityUpdate {
  type: 'equity.update'
  payload: EquityData_backend
}
```

**Equity Data**:

```typescript
interface EquityData {
  equity: number // Total equity (balance + unrealized P&L)
  balance?: number // Account balance
  unrealizedPL?: number // Total unrealized P&L
  realizedPL?: number // Total realized P&L
}
```

**When to Broadcast**:

- Market price changes (affects unrealized P&L)
- Position closed (realized P&L)
- Balance updated
- Regular intervals (e.g., every second)

**Frontend Handler**:

```typescript
this._wsAdapter.equity.subscribe(
  'broker-equity',
  { accountId: this._accountId },
  (data: EquityData) => {
    this._host.equityUpdate(data.equity)

    // Update reactive balance/equity values
    if (data.balance !== undefined) {
      this.balance.setValue(data.balance)
    }
    if (data.equity !== undefined) {
      this.equity.setValue(data.equity)
    }
  },
)
```

---

### 5. Broker Connection Status (`broker-connection.*`)

**Topic Pattern**: `broker-connection:{accountId}`

**Purpose**: Track the real connection status between backend and the actual broker (e.g., Interactive Brokers, TD Ameritrade).

**Subscribe Request**:

```typescript
interface BrokerConnectionSubscriptionRequest {
  accountId: string
}
```

**Update Message**:

```typescript
interface BrokerConnectionUpdate {
  type: 'broker-connection.update'
  payload: {
    status: ConnectionStatus // 1=Connected, 2=Connecting, 3=Disconnected, 4=Error
    message?: string
    disconnectType?: DisconnectType // Optional disconnect reason
    timestamp: number
  }
}
```

**When to Broadcast**:

- Backend connects to broker
- Backend loses connection to broker
- Backend is reconnecting to broker
- Broker authentication fails
- Broker session expires

**Frontend Handler**:

```typescript
this._wsAdapter.brokerConnection.subscribe(
  'broker-connection-status',
  { accountId: this._accountId },
  (data: BrokerConnectionStatus) => {
    this._host.connectionStatusUpdate(data.status, {
      message: data.message,
      disconnectType: data.disconnectType,
    })

    // Show notification on disconnect
    if (data.status === ConnectionStatus.Disconnected) {
      this._host.showNotification(
        'Broker Disconnected',
        data.message || 'Connection to broker lost',
        NotificationType.Error,
      )
    }

    // Show notification on reconnect
    if (data.status === ConnectionStatus.Connected) {
      this._host.showNotification(
        'Broker Connected',
        data.message || 'Successfully connected to broker',
        NotificationType.Success,
      )
    }
  },
)
```

**Note**: This is separate from the WebSocket connection. Even if the WebSocket is connected, the backend might be disconnected from the real broker.

---

## Integration Pattern

### Complete Integration Example

```typescript
// frontend/src/services/brokerTerminalService.ts
import type { IBrokerConnectionAdapterHost, IBrokerWithoutRealtime } from '@public/trading_terminal'
import { ConnectionStatus, OrderStatus, NotificationType } from '@public/trading_terminal'
import { WsAdapter } from '@/plugins/wsAdapter'
import { ApiAdapter } from '@/plugins/apiAdapter'

export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _host: IBrokerConnectionAdapterHost
  private readonly _wsAdapter: WsAdapter
  private readonly _apiAdapter: ApiAdapter
  private readonly _accountId: string = 'DEMO-001'

  // Reactive values
  private readonly balance: IWatchedValue<number>
  private readonly equity: IWatchedValue<number>

  constructor(host: IBrokerConnectionAdapterHost, ...) {
    this._host = host
    this._wsAdapter = new WsAdapter()
    this._apiAdapter = new ApiAdapter()

    // Create reactive values
    this.balance = host.factory.createWatchedValue(100000)
    this.equity = host.factory.createWatchedValue(100000)

    // Setup WebSocket handlers
    this.setupWebSocketHandlers()
  }

  private setupWebSocketHandlers(): void {
    // Order updates
    this._wsAdapter.orders.subscribe(
      'broker-orders',
      { accountId: this._accountId },
      (order: Order) => {
        this._host.orderUpdate(order)

        // Show notification on fill
        if (order.status === OrderStatus.Filled) {
          this._host.showNotification(
            'Order Filled',
            `${order.symbol} ${order.side === 1 ? 'Buy' : 'Sell'} ${order.qty} @ ${order.avgPrice}`,
            NotificationType.Success
          )
        }
      }
    )

    // Position updates
    this._wsAdapter.positions.subscribe(
      'broker-positions',
      { accountId: this._accountId },
      (position: Position) => {
        this._host.positionUpdate(position)
      }
    )

    // Execution updates
    this._wsAdapter.executions.subscribe(
      'broker-executions',
      { accountId: this._accountId },
      (execution: Execution) => {
        this._host.executionUpdate(execution)
      }
    )

    // Equity updates
    this._wsAdapter.equity.subscribe(
      'broker-equity',
      { accountId: this._accountId },
      (data: EquityData) => {
        this._host.equityUpdate(data.equity)
        if (data.balance !== undefined) {
          this.balance.setValue(data.balance)
        }
      }
    )

    // Broker connection status (backend ↔ real broker)
    this._wsAdapter.brokerConnection.subscribe(
      'broker-connection-status',
      { accountId: this._accountId },
      (data: BrokerConnectionStatus) => {
        this._host.connectionStatusUpdate(data.status, {
          message: data.message,
          disconnectType: data.disconnectType,
        })

        // Notify user on connection changes
        if (data.status === ConnectionStatus.Disconnected) {
          this._host.showNotification(
            'Broker Disconnected',
            data.message || 'Connection to broker lost',
            NotificationType.Error,
          )
        } else if (data.status === ConnectionStatus.Connected) {
          this._host.showNotification(
            'Broker Connected',
            data.message || 'Successfully connected to broker',
            NotificationType.Success,
          )
        }
      }
    )
  }

  // ============================================================
  // IBrokerWithoutRealtime Implementation
  // ============================================================

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    // Send command to backend via REST
    const response = await this._apiAdapter.placeOrder(order)

    // NO _host.orderUpdate() here!
    // Backend will broadcast via WebSocket

    return response.data
  }

  async modifyOrder(order: Order): Promise<void> {
    await this._apiAdapter.modifyOrder(order)
    // WebSocket will push update
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this._apiAdapter.cancelOrder(orderId)
    // WebSocket will push update
  }

  async closePosition(positionId: string, amount?: number): Promise<void> {
    await this._apiAdapter.closePosition(positionId, amount)
    // WebSocket will push update
  }

  async orders(): Promise<Order[]> {
    const response = await this._apiAdapter.getOrders()
    return response.data
  }

  async positions(): Promise<Position[]> {
    const response = await this._apiAdapter.getPositions()
    return response.data
  }

  async executions(symbol: string): Promise<Execution[]> {
    const response = await this._apiAdapter.getExecutions(symbol)
    return response.data
  }

  connectionStatus(): ConnectionStatus {
    return WebSocketBase.getInstance().isConnected()
      ? ConnectionStatus.Connected
      : ConnectionStatus.Disconnected
  }
}
```

---

## Technical Details

### Backend WebSocket Router Template

```python
# backend/src/trading_api/ws/broker.py
from fastws import OperationRouter, Client
from trading_api.models.broker import (
    OrderSubscriptionRequest,
    SubscriptionResponse,
    Order,
)

router = OperationRouter(prefix="orders.", tags=["broker"])

def orders_topic_builder(account_id: str) -> str:
    return f"orders:{account_id}"

@router.send("subscribe", reply="subscribe.response")
async def subscribe_orders(
    payload: OrderSubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    topic = orders_topic_builder(payload.account_id)
    client.subscribe(topic)
    return SubscriptionResponse(
        status="ok",
        message=f"Subscribed to orders for {payload.account_id}",
        topic=topic,
    )

@router.send("unsubscribe", reply="unsubscribe.response")
async def unsubscribe_orders(
    payload: OrderSubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    topic = orders_topic_builder(payload.account_id)
    client.unsubscribe(topic)
    return SubscriptionResponse(
        status="ok",
        message=f"Unsubscribed from {payload.account_id}",
        topic=topic,
    )

@router.recv("update")
async def order_update(payload: Order) -> Order:
    """Broadcast order updates to subscribed clients"""
    return payload
```

### Broadcasting from Backend Service

```python
# backend/src/trading_api/core/broker_service.py
from trading_api.main import wsApp  # FastWSAdapter instance

class BrokerService:
    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        # Process order
        order = self.create_order(order_request)

        # Save to database
        await self.save_order(order)

        # Order updates are broadcast automatically via service generator
        # The BrokerService._orders_queue gets the update
        # which is consumed by the generator and passed to topic_update callback

        return OrderResult(order_id=order.id)
```

---

## Testing Strategy

### Unit Tests

**Frontend Mappers**:

```typescript
describe('mapOrder', () => {
  it('should map backend order to frontend format', () => {
    const backendOrder: Order_backend = { ... }
    const frontendOrder = mapOrder(backendOrder)
    expect(frontendOrder.id).toBe(backendOrder.id)
    expect(frontendOrder.status).toBe(OrderStatus.Working)
  })
})
```

**Backend WebSocket Operations**:

```python
def test_subscribe_orders(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json({
            "type": "orders.subscribe",
            "payload": {"account_id": "TEST-001"}
        })

        response = websocket.receive_json()
        assert response["type"] == "orders.subscribe.response"
        assert response["payload"]["status"] == "ok"
        assert response["payload"]["topic"] == "orders:TEST-001"
```

### Integration Tests

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

### Manual Testing Checklist

- [ ] Place order → Order appears in Order Panel immediately
- [ ] Backend fills order → Order status changes to "Filled"
- [ ] Position opens → Position Panel shows new position
- [ ] Close position → Position Panel updates
- [ ] WebSocket disconnects → Status shows "Disconnected"
- [ ] WebSocket reconnects → Resubscribes automatically
- [ ] Multiple orders/positions → All update correctly
- [ ] Notifications shown for important events

---

## Summary

### Key Decisions

1. ✅ **WebSocket for Events**: All state updates come via WebSocket
2. ✅ **REST for Commands**: User actions sent via REST API
3. ✅ **Backend Source of Truth**: No local state management in frontend
4. ✅ **Existing Infrastructure**: Leverage `WebSocketBase` singleton pattern
5. ✅ **Type-Safe Mappers**: Backend types → Frontend types via dedicated mappers
6. ✅ **Server Confirmation**: Wait for `.subscribe.response` before routing messages

### Success Metrics

- ⏱️ **Latency**: < 100ms from backend event to UI update
- 🔄 **Reliability**: Auto-reconnection works seamlessly
- 🛡️ **Type Safety**: Zero runtime type errors
- 📊 **Real-Time**: All broker state synced in real-time
- 🧪 **Testability**: Full test coverage (unit + integration)

---

**Next Steps**: See implementation todo list below

**Version**: 1.0.0  
**Date**: October 22, 2025  
**Maintainer**: Development Team
