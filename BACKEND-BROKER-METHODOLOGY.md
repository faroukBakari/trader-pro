# Backend Broker Terminal Service - Incremental Implementation Methodology

**Version**: 1.0.0  
**Date**: October 19, 2025  
**Status**: 🚧 In Progress  
**Branch**: `backend-broker`

---

## Overview

This document outlines the incremental, test-driven approach for implementing the backend broker terminal service. The methodology ensures that all tests pass at each step, the interface contract is clearly defined, and the implementation can be safely rolled back at any point.

---

## Core Principles

1. ✅ **Incremental**: Each step is small and independently verifiable
2. ✅ **Test-Driven**: Tests guide implementation at every phase
3. ✅ **Interface-First**: Contract defined before implementation
4. ✅ **Reversible**: Can rollback to any working phase
5. ✅ **Type-Safe**: TypeScript + Pydantic ensure type alignment
6. ✅ **Fallback Preserved**: Mock client always available for offline development
7. ✅ **Adapter Pattern**: Use adapte layer to import client. Never import backend models directly to be able to detect breaking changes

---

## Phase 1: Extract Fallback Client (Frontend Refactoring) 🔧

**Goal**: Consolidate interface and mock logic into service file, ensure all tests pass.

**Design Constraint**: For simplicity and implementation speed, the `IBrokerClient` interface and `BrokerFallbackClient` class are **co-located within the service file** (`frontend/src/services/brokerTerminalService.ts`). This reduces file management overhead and keeps related code together during rapid iteration.

### Step 1.1: Consolidate Interface and Fallback Client

**File**: `frontend/src/services/brokerTerminalService.ts`

The service file now contains three main sections:

1. **IBrokerClient Interface** - Contract definition
2. **BrokerFallbackClient Class** - Mock implementation with private state/methods
3. **BrokerTerminalService Class** - TradingView adapter using delegation

```typescript
// ============================================================================
// BROKER CLIENT INTERFACE
// ============================================================================

export interface IBrokerClient {
  // Order operations
  placeOrder(order: PreOrder): Promise<PlaceOrderResult>;
  modifyOrder(order: Order, confirmId?: string): Promise<void>;
  cancelOrder(orderId: string): Promise<void>;
  getOrders(): Promise<Order[]>;

  // Position operations
  getPositions(): Promise<Position[]>;

  // Execution operations
  getExecutions(symbol: string): Promise<Execution[]>;

  // Account operations
  getAccountInfo(): Promise<AccountMetainfo>;
}

// ============================================================================
// FALLBACK CLIENT (MOCK IMPLEMENTATION)
// ============================================================================

class BrokerFallbackClient implements IBrokerClient {
  // Private state management
  private readonly _orderById = new Map<string, Order>()
  private readonly _positions = new Map<string, Position>()
  private readonly _executions: Execution[] = []
  private orderCounter = 1

  // All mock logic methods (private)
  private async simulateOrderExecution(orderId: string): Promise<void> { ... }
  private updatePosition(execution: Execution): void { ... }

  // Public API methods (interface contract)
  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> { ... }
  async modifyOrder(order: Order, confirmId?: string): Promise<void> { ... }
  async cancelOrder(orderId: string): Promise<void> { ... }
  async getOrders(): Promise<Order[]> { ... }
  async getPositions(): Promise<Position[]> { ... }
  async getExecutions(symbol: string): Promise<Execution[]> { ... }
  async getAccountInfo(): Promise<AccountMetainfo> { ... }
}

// ============================================================================
// BROKER TERMINAL SERVICE
// ============================================================================

export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _client: IBrokerClient;

  constructor(
    host: IBrokerConnectionAdapterHost,
    datafeed: IDatafeedQuotesApi,
    client?: IBrokerClient // Optional: defaults to fallback
  ) {
    this._host = host;
    this._quotesProvider = datafeed;
    this._client = client ?? new BrokerFallbackClient(host, datafeed);
  }

  // All methods delegate to client
  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const result = await this._client.placeOrder(order);
    // Notify TradingView host about updates
    const orders = await this._client.getOrders();
    const placedOrder = orders.find((o) => o.id === result.orderId);
    if (placedOrder) {
      this._host.orderUpdate(placedOrder);
    }
    return result;
  }
  // ... similar for all other methods
}
```

**Verification**:

```bash
cd frontend
make test      # All tests pass
make lint      # No lint errors
```

---

## Phase 2: Define Backend API Contract (Empty Stubs) 📝

**Goal**: Create backend API structure matching the client interface, generate OpenAPI client, verify interface alignment.

### Step 2.1: Create Backend Models

**File**: `backend/src/trading_api/models/broker/__init__.py`

Create Pydantic models matching TradingView types:

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import IntEnum

class OrderStatus(IntEnum):
    CANCELED = 1
    FILLED = 2
    INACTIVE = 3
    PLACING = 4
    REJECTED = 5
    WORKING = 6

class OrderType(IntEnum):
    LIMIT = 1
    MARKET = 2
    STOP = 3
    STOP_LIMIT = 4

class Side(IntEnum):
    BUY = 1
    SELL = -1

class PreOrder(BaseModel):
    """Order request from client"""
    symbol: str
    type: OrderType
    side: Side
    qty: float
    limitPrice: Optional[float] = None
    stopPrice: Optional[float] = None
    # ... match TradingView PreOrder fields

class PlacedOrder(BaseModel):
    """Complete order with status"""
    id: str
    symbol: str
    type: OrderType
    side: Side
    qty: float
    status: OrderStatus
    limitPrice: Optional[float] = None
    stopPrice: Optional[float] = None
    filledQty: Optional[float] = None
    avgPrice: Optional[float] = None
    updateTime: Optional[int] = None
    # ... match TradingView PlacedOrder fields

class Position(BaseModel):
    """Position data"""
    id: str
    symbol: str
    qty: float
    side: Side
    avgPrice: float
    # ... match TradingView PositionBase fields

class Execution(BaseModel):
    """Trade execution record"""
    symbol: str
    price: float
    qty: float
    side: Side
    time: int
    # ... match TradingView Execution fields

class PlaceOrderResult(BaseModel):
    """Result of placing an order"""
    orderId: str

class AccountMetainfo(BaseModel):
    """Account metadata"""
    id: str
    name: str
```

---

### Step 2.2: Create REST API Endpoints (Empty Stubs)

**File**: `backend/src/trading_api/api/broker.py`

Create REST endpoints with **empty implementations** (NotImplementedError stubs). All routes MUST include `summary` and `operation_id` parameters:

```python
from fastapi import APIRouter
from typing import List
from pydantic import BaseModel
from trading_api.models.broker import (
    PreOrder, PlacedOrder, Position, Execution,
    PlaceOrderResult, AccountMetainfo
)

class SuccessResponse(BaseModel):
    """Generic success response for operations that don't return data"""
    success: bool = True

router = APIRouter(prefix="/broker", tags=["broker"])  # Note: /broker only, main.py adds /api/v1

@router.post(
    "/orders",
    response_model=PlaceOrderResult,
    summary="Place a new order",
    operation_id="placeOrder",
)
async def placeOrder(order: PreOrder) -> PlaceOrderResult:
    """Place a new order in the trading system"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub

@router.put(
    "/orders/{order_id}",
    response_model=SuccessResponse,
    summary="Modify an existing order",
    operation_id="modifyOrder",
)
async def modifyOrder(order_id: str, order: PreOrder) -> SuccessResponse:
    """Modify an existing order"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub

@router.delete(
    "/orders/{order_id}",
    response_model=SuccessResponse,
    summary="Cancel an order",
    operation_id="cancelOrder",
)
async def cancelOrder(order_id: str) -> SuccessResponse:
    """Cancel an order"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub

@router.get(
    "/orders",
    response_model=List[PlacedOrder],
    summary="Get all orders",
    operation_id="getOrders",
)
async def getOrders() -> List[PlacedOrder]:
    """Get all orders"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub

@router.get(
    "/positions",
    response_model=List[Position],
    summary="Get all positions",
    operation_id="getPositions",
)
async def getPositions() -> List[Position]:
    """Get all positions"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub

@router.get(
    "/executions/{symbol}",
    response_model=List[Execution],
    summary="Get executions for a symbol",
    operation_id="getExecutions",
)
async def getExecutions(symbol: str) -> List[Execution]:
    """Get execution history for a specific symbol"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub

@router.get(
    "/account",
    response_model=AccountMetainfo,
    summary="Get account information",
    operation_id="getAccountInfo",
)
async def getAccountInfo() -> AccountMetainfo:
    """Get account metadata"""
    raise NotImplementedError("Broker API not yet implemented")  # 👈 Empty stub
```

---

### Step 2.3: Register Router in Main App

**File**: `backend/src/trading_api/main.py`

```python
from trading_api.api import broker as broker_api

# Register broker router
apiApp.include_router(broker_api.router)
```

**Verification**:

```bash
cd backend
make dev  # Start backend
# Backend starts successfully, exports openapi.json with broker endpoints
```

---

### Step 2.4: Generate Frontend Client & Create Adapter

**Architecture Pattern**: Never import generated backend models directly. Always use an adapter layer to:

- Detect breaking changes at compile time
- Convert backend types to TradingView frontend types
- Provide clean interface implementation

**Step 2.4.1: Generate OpenAPI Client**

```bash
# Generate OpenAPI client
cd frontend
make generate-openapi-client

# Generated client will have methods like:
# - placeOrder(order: PreOrder): Promise<PlaceOrderResult>
# - modifyOrder(orderId: string, order: PlacedOrder): Promise<void>
# - etc.
```

**Step 2.4.2: Create Broker API Adapter**

**File**: `frontend/src/plugins/brokerApiAdapter.ts`

This adapter wraps the generated OpenAPI client and converts backend models to TradingView types. **Never import generated models outside this file.**

```typescript
/**
 * Broker API Adapter
 *
 * This adapter wraps the generated OpenAPI client to provide type conversions
 * and a cleaner interface. Do NOT import generated client models but import
 * TradingView types. For API requests/responses, use the adapter types defined here.
 *
 * Rule: Never import backend models outside this file to detect breaking changes.
 */

import { Configuration, BrokerApi } from "@clients/trader-client-generated/";
import type {
  AccountMetainfo,
  Execution,
  Order,
  PlaceOrderResult,
  Position,
  PreOrder,
} from "@public/trading_terminal";

export type ApiResponse<T> = { status: number; data: T };
type ApiPromise<T> = Promise<ApiResponse<T>>;

export class BrokerApiAdapter {
  private rawApi: BrokerApi;

  constructor() {
    this.rawApi = new BrokerApi(
      new Configuration({
        basePath: import.meta.env.TRADER_API_BASE_PATH || "",
      })
    );
  }

  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const response = await this.rawApi.placeOrderApiV1BrokerOrdersPost({
      preOrder: order as any, // Convert TradingView type to backend type
    });

    return {
      status: response.status,
      data: response.data as PlaceOrderResult, // Convert backend type to TradingView type
    };
  }

  async modifyOrder(orderId: string, order: Order): ApiPromise<void> {
    const response = await this.rawApi.modifyOrderApiV1BrokerOrdersOrderIdPut({
      orderId,
      placedOrder: order as any,
    });

    return {
      status: response.status,
      data: undefined as void,
    };
  }

  async cancelOrder(orderId: string): ApiPromise<void> {
    const response =
      await this.rawApi.cancelOrderApiV1BrokerOrdersOrderIdDelete({
        orderId,
      });

    return {
      status: response.status,
      data: undefined as void,
    };
  }

  async getOrders(): ApiPromise<Order[]> {
    const response = await this.rawApi.getOrdersApiV1BrokerOrdersGet();

    return {
      status: response.status,
      data: response.data as Order[],
    };
  }

  async getPositions(): ApiPromise<Position[]> {
    const response = await this.rawApi.getPositionsApiV1BrokerPositionsGet();

    return {
      status: response.status,
      data: response.data as Position[],
    };
  }

  async getExecutions(symbol: string): ApiPromise<Execution[]> {
    const response =
      await this.rawApi.getExecutionsApiV1BrokerExecutionsSymbolGet({
        symbol,
      });

    return {
      status: response.status,
      data: response.data as Execution[],
    };
  }

  async getAccountInfo(): ApiPromise<AccountMetainfo> {
    const response = await this.rawApi.getAccountInfoApiV1BrokerAccountGet();

    return {
      status: response.status,
      data: response.data as AccountMetainfo,
    };
  }
}
```

**Step 2.4.3: Create Backend Client Using Adapter**

**File**: `frontend/src/clients/brokerBackendClient.ts`

```typescript
import { BrokerApiAdapter } from "@/plugins/brokerApiAdapter";
import type { IBrokerClient } from "@/services/brokerTerminalService";
import type {
  AccountMetainfo,
  Execution,
  Order,
  PlaceOrderResult,
  Position,
  PreOrder,
} from "@public/trading_terminal";

/**
 * Backend broker client that uses the API adapter
 * Implements IBrokerClient interface for TradingView integration
 */
export class BrokerBackendClient implements IBrokerClient {
  private adapter: BrokerApiAdapter;

  constructor() {
    this.adapter = new BrokerApiAdapter();
  }

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const response = await this.adapter.placeOrder(order);
    return response.data;
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    const orderId = confirmId ?? order.id;
    await this.adapter.modifyOrder(orderId, order);
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this.adapter.cancelOrder(orderId);
  }

  async getOrders(): Promise<Order[]> {
    const response = await this.adapter.getOrders();
    return response.data;
  }

  async getPositions(): Promise<Position[]> {
    const response = await this.adapter.getPositions();
    return response.data;
  }

  async getExecutions(symbol: string): Promise<Execution[]> {
    const response = await this.adapter.getExecutions(symbol);
    return response.data;
  }

  async getAccountInfo(): Promise<AccountMetainfo> {
    const response = await this.adapter.getAccountInfo();
    return response.data;
  }
}
```

**Verification**: TypeScript compilation should succeed:

```bash
cd frontend
npm run type-check  # Should pass with no errors
```

**Adjustment Loop**: If types don't match:

- Adjust backend API signatures
- Regenerate OpenAPI spec: restart `make dev`
- Regenerate client: `make generate-openapi-client`
- Update adapter type conversions in `brokerApiAdapter.ts`
- Repeat until interface matches perfectly

**Benefits of Adapter Pattern**:

1. ✅ **Breaking Change Detection**: Type mismatches caught at compile time
2. ✅ **Isolation**: Generated models never leak into application code
3. ✅ **Clean Interface**: Adapter provides consistent API surface
4. ✅ **Type Safety**: Explicit conversions between backend and frontend types
5. ✅ **Maintainability**: All type conversions in one place

---

## Phase 3: Implement Backend Logic (TDD) 🧪

**Goal**: Implement actual backend logic, ensure frontend tests pass with real backend.

### Step 3.1: Create Broker Service (Mock Logic)

**File**: `backend/src/trading_api/core/broker_service.py`

Move mock logic from frontend fallback client to backend:

```python
from typing import Dict, List, Optional
from trading_api.models.broker import (
    PreOrder, PlacedOrder, Position, Execution,
    PlaceOrderResult, OrderStatus, Side
)

class BrokerService:
    """Mock broker service for development"""

    def __init__(self):
        self._orders: Dict[str, PlacedOrder] = {}
        self._positions: Dict[str, Position] = {}
        self._executions: List[Execution] = []
        self._order_counter = 1

    async def place_order(self, order: PreOrder) -> PlaceOrderResult:
        """Place a new order"""
        order_id = f"ORDER-{self._order_counter}"
        self._order_counter += 1

        placed_order = PlacedOrder(
            id=order_id,
            symbol=order.symbol,
            type=order.type,
            side=order.side,
            qty=order.qty,
            status=OrderStatus.WORKING,
            limitPrice=order.limitPrice,
            stopPrice=order.stopPrice,
        )

        self._orders[order_id] = placed_order

        # Simulate execution after delay
        await self._simulate_execution(order_id)

        return PlaceOrderResult(orderId=order_id)

    async def _simulate_execution(self, order_id: str) -> None:
        """Private: Simulate order execution"""
        import asyncio
        await asyncio.sleep(0.2)  # Small delay

        order = self._orders.get(order_id)
        if not order:
            return

        # Create execution
        execution = Execution(
            symbol=order.symbol,
            price=order.limitPrice or 100.0,
            qty=order.qty,
            side=order.side,
            time=int(time.time() * 1000)
        )
        self._executions.append(execution)

        # Update order status
        order.status = OrderStatus.FILLED
        order.filledQty = order.qty
        order.avgPrice = execution.price

        # Update position
        self._update_position(execution)

    def _update_position(self, execution: Execution) -> None:
        """Private: Update position from execution"""
        position_id = f"{execution.symbol}-POS"
        existing = self._positions.get(position_id)

        if existing:
            # Update existing position logic
            # ... (similar to frontend fallback)
            pass
        else:
            # Create new position
            self._positions[position_id] = Position(
                id=position_id,
                symbol=execution.symbol,
                qty=execution.qty,
                side=execution.side,
                avgPrice=execution.price
            )

    # ... implement all other methods
    async def get_orders(self) -> List[PlacedOrder]:
        return list(self._orders.values())

    async def get_positions(self) -> List[Position]:
        return list(self._positions.values())

    async def get_executions(self, symbol: str) -> List[Execution]:
        return [e for e in self._executions if e.symbol == symbol]
```

---

### Step 3.2: Wire Service to API Endpoints

**File**: `backend/src/trading_api/api/broker.py`

Replace `pass` with actual service calls:

```python
from trading_api.core.broker_service import BrokerService

# Create singleton service instance
broker_service = BrokerService()

@router.post("/orders", response_model=PlaceOrderResult)
async def place_order(order: PreOrder) -> PlaceOrderResult:
    """Place a new order"""
    return await broker_service.place_order(order)  # 👈 Real implementation

@router.get("/orders", response_model=List[PlacedOrder])
async def get_orders() -> List[PlacedOrder]:
    """Get all orders"""
    return await broker_service.get_orders()  # 👈 Real implementation

# ... wire all other endpoints
```

---

### Step 3.3: Write Backend Unit Tests

**File**: `backend/tests/test_broker_service.py`

```python
import pytest
from trading_api.core.broker_service import BrokerService
from trading_api.models.broker import PreOrder, OrderType, Side, OrderStatus

@pytest.mark.asyncio
async def test_place_order_creates_working_order():
    service = BrokerService()

    order = PreOrder(
        symbol="AAPL",
        type=OrderType.LIMIT,
        side=Side.BUY,
        qty=100,
        limitPrice=150.0
    )

    result = await service.place_order(order)
    assert result.orderId.startswith("ORDER-")

    orders = await service.get_orders()
    assert len(orders) == 1
    assert orders[0].status in [OrderStatus.WORKING, OrderStatus.FILLED]

@pytest.mark.asyncio
async def test_order_execution_creates_position():
    service = BrokerService()

    order = PreOrder(
        symbol="AAPL",
        type=OrderType.MARKET,
        side=Side.BUY,
        qty=100
    )

    await service.place_order(order)

    # Wait for execution
    import asyncio
    await asyncio.sleep(0.3)

    positions = await service.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].qty == 100
    assert positions[0].side == Side.BUY

@pytest.mark.asyncio
async def test_cancel_order():
    service = BrokerService()
    order = PreOrder(symbol="AAPL", type=OrderType.LIMIT, side=Side.BUY, qty=100)
    result = await service.place_order(order)

    await service.cancel_order(result.orderId)

    orders = await service.get_orders()
    cancelled = next(o for o in orders if o.id == result.orderId)
    assert cancelled.status == OrderStatus.CANCELED
```

**Verification**:

```bash
cd backend
make test  # All backend tests should pass
```

---

### Step 3.4: Write Backend API Integration Tests

**File**: `backend/tests/test_api_broker.py`

```python
import pytest
from httpx import AsyncClient
from trading_api.main import apiApp

@pytest.mark.asyncio
async def test_place_order_endpoint():
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.post("/api/v1/broker/orders", json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0
        })

        assert response.status_code == 200
        data = response.json()
        assert "orderId" in data
        assert data["orderId"].startswith("ORDER-")

@pytest.mark.asyncio
async def test_get_orders_endpoint():
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        # First place an order
        await client.post("/api/v1/broker/orders", json={
            "symbol": "AAPL",
            "type": 2,  # MARKET
            "side": 1,  # BUY
            "qty": 50
        })

        # Then get orders
        response = await client.get("/api/v1/broker/orders")
        assert response.status_code == 200
        orders = response.json()
        assert len(orders) >= 1
```

**Verification**:

```bash
cd backend
make test  # All tests pass including new broker tests
```

---

## Phase 4: Frontend Integration & Validation ✅

**Goal**: Use real backend client in frontend, ensure all frontend tests pass.

### Step 4.1: Update Frontend Service to Use Backend Client

**File**: `frontend/src/services/brokerTerminalService.ts`

Add smart client selection:

```typescript
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _client: IBrokerClient;

  constructor(
    host: IBrokerConnectionAdapterHost,
    datafeed: IDatafeedQuotesApi,
    useBackend: boolean = true // 👈 Feature flag
  ) {
    this._host = host;
    this._quotesProvider = datafeed;

    // Smart client selection
    if (useBackend && this.isBackendAvailable()) {
      this._client = new BrokerBackendClient("http://localhost:8000");
    } else {
      this._client = new BrokerFallbackClient(host, datafeed);
    }
  }

  private isBackendAvailable(): boolean {
    // Simple availability check
    // Could be improved with actual health check
    return true; // For now, assume available in development
  }
}
```

---

### Step 4.2: Run Frontend Tests Against Real Backend

**File**: `frontend/src/services/brokerTerminalService.test.ts`

Update tests to optionally use real backend:

```typescript
describe("BrokerTerminalService", () => {
  let service: BrokerTerminalService;
  let mockHost: IBrokerConnectionAdapterHost;

  beforeEach(() => {
    mockHost = createMockHost();
    // Use fallback client for unit tests (no backend needed)
    service = new BrokerTerminalService(mockHost, mockDatafeed, false);
  });

  it("should place order successfully", async () => {
    const order: PreOrder = {
      symbol: "AAPL",
      type: OrderType.Limit,
      side: Side.Buy,
      qty: 100,
      limitPrice: 150.0,
    };

    const result = await service.placeOrder(order);
    expect(result.orderId).toBeDefined();
    expect(result.orderId).toMatch(/^ORDER-\d+$/);
  });

  // All other tests remain the same
  // They work with both fallback and backend client!
});
```

**Verification**:

```bash
cd frontend
make test  # All frontend tests pass (using fallback)

# Optional: Integration test with real backend
cd backend
make dev &  # Start backend in background

cd frontend
USE_BACKEND=true make test  # Tests with real backend
```

---

## Phase 5: Full Stack Validation 🚀

### Step 5.1: Manual E2E Testing

```bash
# Terminal 1: Start backend
cd backend
make dev

# Terminal 2: Start frontend
cd frontend
make dev

# Browser: Open http://localhost:5173
# - Place orders from TradingView UI
# - Verify orders appear in Order Panel
# - Verify positions update correctly
# - Verify executions are recorded
```

---

### Step 5.2: Smoke Tests (Optional)

```bash
cd smoke-tests
npm test  # Playwright E2E tests
```

---

## Implementation Checklist

| Phase     | Step                    | File(s)                                          | Verification         | Status |
| --------- | ----------------------- | ------------------------------------------------ | -------------------- | ------ |
| **1.1**   | Consolidate in service  | `frontend/src/services/brokerTerminalService.ts` | `make test`          | ✅     |
| **2.1**   | Backend models          | `backend/src/trading_api/models/broker/`         | `make lint`          | ⏳     |
| **2.2**   | API stubs               | `backend/src/trading_api/api/broker.py`          | `make dev`           | ⏳     |
| **2.3**   | Register router         | `backend/src/trading_api/main.py`                | Backend starts       | ⏳     |
| **2.4.1** | Generate OpenAPI client | Auto-generated                                   | Generation success   | ⏳     |
| **2.4.2** | Create broker adapter   | `frontend/src/plugins/brokerApiAdapter.ts`       | `npm run type-check` | ⏳     |
| **2.4.3** | Create backend client   | `frontend/src/clients/brokerBackendClient.ts`    | `npm run type-check` | ⏳     |
| **3.1**   | Broker service          | `backend/src/trading_api/core/broker_service.py` | N/A                  | ⏳     |
| **3.2**   | Wire endpoints          | `backend/src/trading_api/api/broker.py`          | N/A                  | ⏳     |
| **3.3**   | Backend unit tests      | `backend/tests/test_broker_service.py`           | `make test`          | ⏳     |
| **3.4**   | Backend API tests       | `backend/tests/test_api_broker.py`               | `make test`          | ⏳     |
| **4.1**   | Smart client selection  | `frontend/src/services/brokerTerminalService.ts` | `make test`          | ⏳     |
| **4.2**   | Frontend integration    | Tests & manual                                   | Both pass            | ⏳     |
| **5.1**   | E2E manual testing      | Browser testing                                  | Visual verification  | ⏳     |
| **5.2**   | Smoke tests             | `smoke-tests/`                                   | `npm test`           | ⏳     |

---

## Key Benefits

1. ✅ **Incremental**: Each step is small and verifiable
2. ✅ **Test-Driven**: Tests guide implementation at every phase
3. ✅ **Interface-First**: Contract defined before implementation
4. ✅ **Reversible**: Can rollback to any working phase
5. ✅ **Parallel Work**: Backend and frontend can evolve together
6. ✅ **Fallback Preserved**: Mock client always available
7. ✅ **Type-Safe**: TypeScript + Pydantic ensure type alignment
8. ✅ **Breaking Change Detection**: Adapter pattern catches API mismatches at compile time

---

## Notes

- Each phase completion should be committed to git
- All tests must pass before moving to next phase
- Interface mismatches trigger adjustment loop in Phase 2.4
- Frontend always works (via fallback client) throughout implementation

---

**Last Updated**: October 19, 2025  
**Maintained by**: Development Team
