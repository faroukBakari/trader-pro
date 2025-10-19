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
7. ✅ **Adapter Pattern**: Use adapter layer to import client. Never import backend models directly to be able to detect breaking changes

---

## TDD Flow Summary

This methodology follows a strict Test-Driven Development approach:

### Phase Flow:

1. **Phase 1**: Extract fallback client (frontend refactoring) → Tests pass ✅
2. **Phase 2**: Define backend API contract (empty stubs) → Backend starts, frontend types align ✅
3. **Phase 3**: Wire frontend to backend → **Tests FAIL** 🔴 (TDD Red phase)
4. **Phase 4**: Implement backend logic → Backend tests pass ✅
5. **Phase 5**: Verify frontend tests → **Tests PASS** 🟢 (TDD Green phase)
6. **Phase 6**: Full stack validation → Manual E2E ✅

### Key TDD Insight:

By moving **Phase 3 (Frontend Integration)** before **Phase 4 (Backend Implementation)**, we ensure:

- 🔴 **Red Phase**: Frontend tests fail when pointing to backend stubs (Phase 3.3)
- 🟢 **Green Phase**: Frontend tests pass after backend implementation (Phase 5.1)
- 🔄 **Refactor**: Optimize both frontend and backend code while keeping tests green

This approach validates that:

1. Frontend is correctly wired to backend API
2. Tests accurately reflect expected behavior
3. Backend implementation makes tests pass (not the other way around)

---

## Phase 1: Extract Fallback Client (Frontend Refactoring) 🔧

**Goal**: Consolidate interface and mock logic into service file, ensure all tests pass.

**Design Constraint**: For simplicity and implementation speed, the `ApiInterface` interface and `BrokerFallbackClient` class are **co-located within the service file** (`frontend/src/services/brokerTerminalService.ts`). This reduces file management overhead and keeps related code together during rapid iteration.

### Step 1.1: Consolidate Interface and Fallback Client

**File**: `frontend/src/services/brokerTerminalService.ts`

The service file now contains three main sections:

1. **ApiInterface Interface** - Contract definition
2. **BrokerFallbackClient Class** - Mock implementation with private state/methods
3. **BrokerTerminalService Class** - TradingView adapter using delegation

```typescript
// ============================================================================
// BROKER CLIENT INTERFACE
// ============================================================================

export interface ApiInterface {
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

class BrokerFallbackClient implements ApiInterface {
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
  private readonly _client: ApiInterface;

  constructor(
    host: IBrokerConnectionAdapterHost,
    datafeed: IDatafeedQuotesApi,
    client?: ApiInterface // Optional: defaults to fallback
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

**Architecture Summary**:

- **Consolidated Adapter**: Both datafeed and broker API methods are consolidated in a single `ApiAdapter` class (`frontend/src/plugins/apiAdapter.ts`)
- **Single Source of Truth**: All backend API interactions go through one adapter file
- **No Separate Broker Adapter**: Unlike the initial design, we don't create a separate `BrokerApiAdapter` file

**Architecture Pattern**: Never import generated backend models outside the adapter. Always use an adapter layer to:

- Detect breaking changes at compile time through targeted type casting
- Convert backend types to frontend types
- Provide clean, consolidated interface for all API operations
- Apply type casting only to enum/literal/alias fields, not entire objects
- Use type-safe mapper functions that can import backend types for validation (rename backend types with a \_Backend suffix)
- Keep backend type imports isolated to mapper functions (not ApiAdapter methods)

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

**Step 2.4.2: Add Broker Methods to API Adapter**

**Existing Source File**: `frontend/src/plugins/apiAdapter.ts`

This adapter wraps the generated OpenAPI client and converts backend models to types. **Never import generated models outside this file.**

**CRITICAL**: The `ApiAdapter` class must implement the `ApiInterface` interface (defined in `brokerTerminalService.ts`) to enable direct usage without a wrapper class. The broker methods' signatures must match the interface exactly.

**IMPORTANT Design Constraints**:

1. **API Versioning Constraint**:

   - All API endpoints are available under `V1Api` from `@clients/trader-client-generated/`
   - **DO NOT** import individual API modules (e.g., `BrokerApi`, `DatafeedApi`) directly
   - Use `V1Api` for all API calls to support version upgrade handling
   - Broker methods are consolidated inside the `ApiAdapter` class (not a separate `BrokerApiAdapter`)

2. **Type Casting Safety Constraint**:

   - **Rule of thumb**: Unsafe type casting (`as unknown as`) is **ONLY** reserved for literal/alias/enum typed members
   - **DO NOT** cast entire objects or complex types blindly
   - Cast only specific enum/literal fields that differ between backend and frontend (e.g., `Side`, `OrderType`, `OrderStatus`)
   - This ensures type mismatches on complex objects are caught at compile time
   - The best approach is to implement type-safe mappers with runtime validation
   - **Mapper Functions**: Can import backend types for type safety (not exposed outside apiAdapter)
   - **ApiAdapter Methods**: Never import or use backend types directly - only in mappers
   - Example of **correct** casting in ApiAdapter method:
     ```typescript
     const response = await this.rawApi.placeOrder({
       ...order,
       type: order.type as unknown as GeneratedPreOrder["type"], // ✅ Cast enum only
       side: order.side as unknown as GeneratedPreOrder["side"], // ✅ Cast enum only
     });
     ```
   - Example of **correct** mapper function:

     ```typescript
     import type { QuoteData as BackendQuoteData } from "@clients/trader-client-generated";

     const apiMappers = {
       mapQuoteData: (quote: BackendQuoteData): QuoteData => {
         // Type-safe mapping with backend types
         if (quote.s === "error") {
           return { s: "error" as const, n: quote.n, v: quote.v };
         }
         return { s: "ok" as const, n: quote.n, v: { ...quote.v } };
       },
     };
     ```

   - Example of **incorrect** casting:
     ```typescript
     const response = await this.rawApi.placeOrder(
       order as unknown as GeneratedPreOrder
     ); // ❌ Casting entire object
     ```

```typescript
/**
 * API Adapter (Consolidated Datafeed + Broker)
 *
 * This adapter wraps the generated OpenAPI client to provide type conversions
 * and a cleaner interface. Do NOT import generated client models but import
 * TradingView types. For API requests/responses, use the adapter types defined here.
 *
 * Rule: Never import backend models outside this file to detect breaking changes.
 * Constraint: Use V1Api (not individual API classes) for version upgrade handling.
 * Type Casting Rule: Use type-safe mappers with backend types; only cast enums in mappers.
 */

import type {
  PreOrder as PreOrder_Backend,
  QuoteData as QuoteData_Backend,
} from "@clients/trader-client-generated";
import { Configuration, V1Api } from "@clients/trader-client-generated/";
import type {
  AccountMetainfo,
  Execution,
  Order,
  PlaceOrderResult,
  Position,
  PreOrder,
  QuoteData,
} from "@public/trading_terminal/charting_library";

export type ApiResponse<T> = { status: number; data: T };
type ApiPromise<T> = Promise<ApiResponse<T>>;

// Type-safe mappers for API requests/responses
// Mappers can import backend types for type safety (not exposed outside this file)
const apiMappers = {
  mapQuoteData: (quote: QuoteData_Backend): QuoteData => {
    if (quote.s === "error") {
      return { s: "error" as const, n: quote.n, v: quote.v };
    }
    return { s: "ok" as const, n: quote.n, v: { ...quote.v } };
  },

  mapPreOrder: (order: PreOrder): PreOrder_Backend => {
    return {
      symbol: order.symbol,
      type: order.type as unknown as PreOrder_Backend["type"],
      side: order.side as unknown as PreOrder_Backend["side"],
      qty: order.qty,
      limitPrice: order.limitPrice ?? null,
      stopPrice: order.stopPrice ?? null,
      stopType: order.stopType
        ? (order.stopType as unknown as PreOrder_Backend["stopType"])
        : null,
    };
  },

  ...

};

export class ApiAdapter {
  private rawApi: V1Api;

  // ========================================================================
  // DATAFEED METHODS (for existing datafeed functionality)
  // ========================================================================
  // These methods can keep ApiResponse wrapper if needed by datafeedService
  // ... existing datafeed methods ...

  ...

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const response = await this.rawApi.placeOrder(
      apiMappers.mapPreOrder(order)
    );
    return response.data as PlaceOrderResult;
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    await this.rawApi.modifyOrder(apiMappers.mapPreOrder(order), order.id);
    // Returns void to match interface
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this.rawApi.cancelOrder(orderId);
    // Returns void to match interface
  }

  async getOrders(): Promise<Order[]> {
    const response = await this.rawApi.getOrders();
    // Note: Full cast due to union type mismatch (BracketOrder fields)
    return response.data as unknown as Order[];
  }

  async getPositions(): Promise<Position[]> {
    const response = await this.rawApi.getPositions();
    return response.data.map((position) => ({
      ...position,
      side: position.side as unknown as Position["side"],
    }));
  }

  async getExecutions(symbol: string): Promise<Execution[]> {
    const response = await this.rawApi.getExecutions(symbol);
    return response.data.map((execution) => ({
      ...execution,
      side: execution.side as unknown as Execution["side"],
    }));
  }

  async getAccountInfo(): Promise<AccountMetainfo> {
    const response = await this.rawApi.getAccountInfo();
    return response.data as AccountMetainfo;
  }

}
```

**Adjustment Loop**: If types don't match:

- Adjust backend API signatures
- Regenerate OpenAPI spec: restart `make dev`
- Regenerate client: `make generate-openapi-client`
- Update adapter type conversions in `apiAdapter.ts` (consolidated file)
- Apply targeted enum/literal casting only where needed
- Repeat until interface matches perfectly

**Benefits of Adapter Pattern with Type Casting Constraints**:

1. ✅ **Breaking Change Detection**: Type mismatches on complex objects caught at compile time
2. ✅ **Targeted Type Casting**: Only enum/literal/alias fields require unsafe casting, not entire objects
3. ✅ **Compile-Time Validation**: Structural changes to objects (new fields, removed fields) trigger TypeScript errors
4. ✅ **Isolation**: Generated models never leak into application code
5. ✅ **Clean Interface**: Adapter provides consistent API surface across datafeed and broker operations
6. ✅ **Consolidated Architecture**: Single `ApiAdapter` class handles all backend API interactions
7. ✅ **Maintainability**: All type conversions in one place (`apiAdapter.ts`)
8. ✅ **Explicit Safety**: Developers can immediately see which fields have type discrepancies (enums/literals)

---

## Phase 3: Frontend Integration & TDD setup

**Goal**: Use real backend client in frontend, run tests against stub backend to see failures (TDD Red phase).

**Note**: Backend client adapter was already created in Step 2.4.2 (broker methods added to consolidated `ApiAdapter` class). However, there's a return type mismatch that needs to be resolved first.

**Critical Issue**: The `ApiAdapter` returns `ApiPromise<T>` (which is `Promise<{status: number, data: T}>`), but the current `ApiInterface` in `brokerTerminalService.ts` expects unwrapped `Promise<T>`. We need to align these return types before integration.

### Step 3.1: Adjust ApiInterface and BrokerFallbackClient for ApiPromise Return Types

**Goal**: Update `ApiInterface` and `BrokerFallbackClient` to use `ApiPromise<T>` return types, matching the `ApiAdapter` signature.

**Files to modify**:

- `frontend/src/services/brokerTerminalService.ts` (ApiInterface + BrokerFallbackClient + BrokerTerminalService)

**Changes**:

1. **Import ApiPromise type** from apiAdapter:

```typescript
import { ApiAdapter, type ApiPromise } from "@/plugins/apiAdapter";
```

2. **Update ApiInterface** to return `ApiPromise<T>` instead of `Promise<T>`:

```typescript
export interface ApiInterface {
  // Order operations
  placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult>;
  modifyOrder(order: Order, confirmId?: string): ApiPromise<void>;
  cancelOrder(orderId: string): ApiPromise<void>;
  getOrders(): ApiPromise<Order[]>;

  // Position operations
  getPositions(): ApiPromise<Position[]>;

  // Execution operations
  getExecutions(symbol: string): ApiPromise<Execution[]>;

  // Account operations
  getAccountInfo(): ApiPromise<AccountMetainfo>;
}
```

3. **Update BrokerFallbackClient** to wrap responses in `ApiResponse` format (example methods):

```typescript
class BrokerFallbackClient implements ApiInterface {
  // ... existing private state and methods ...

  // Example: placeOrder now returns ApiPromise<T>
  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const orderId = `ORDER-${this.orderCounter++}`;
    // ... existing order creation logic ...
    await this.simulateOrderExecution(orderId);

    // Wrap in ApiResponse format
    return {
      status: 200,
      data: { orderId },
    };
  }

  // Example: getOrders now returns ApiPromise<T>
  async getOrders(): ApiPromise<Order[]> {
    return {
      status: 200,
      data: Array.from(this._orderById.values()),
    };
  }

  // Apply same pattern to all other methods:
  // modifyOrder, cancelOrder, getPositions, getExecutions, getAccountInfo
  // All return { status: 200, data: <result> }
}
```

4. **Update BrokerTerminalService** to unwrap `.data` from all API responses:

```typescript
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  // ... existing constructor and private methods ...

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const response = await this._getApiAdapter().placeOrder(order);
    const result = response.data; // Unwrap data

    const ordersResponse = await this._getApiAdapter().getOrders();
    const placedOrder = ordersResponse.data.find(
      (o) => o.id === result.orderId
    );
    if (placedOrder) {
      this._host.orderUpdate(placedOrder);
    }
    return result;
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    await this._getApiAdapter().modifyOrder(order, confirmId);

    const ordersResponse = await this._getApiAdapter().getOrders();
    const updatedOrder = ordersResponse.data.find(
      (o) => o.id === (confirmId ?? order.id)
    );
    if (updatedOrder) {
      this._host.orderUpdate(updatedOrder);
    }
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this._getApiAdapter().cancelOrder(orderId);

    const ordersResponse = await this._getApiAdapter().getOrders();
    const cancelledOrder = ordersResponse.data.find((o) => o.id === orderId);
    if (cancelledOrder) {
      this._host.orderUpdate(cancelledOrder);
    }
  }

  async orders(): Promise<Order[]> {
    const response = await this._getApiAdapter().getOrders();
    return response.data;
  }

  async positions(): Promise<Position[]> {
    const response = await this._getApiAdapter().getPositions();
    return response.data;
  }

  async executions(symbol: string): Promise<Execution[]> {
    const response = await this._getApiAdapter().getExecutions(symbol);
    return response.data;
  }

  async accountsMetainfo(): Promise<AccountMetainfo[]> {
    const response = await this._getApiAdapter().getAccountInfo();
    return [response.data];
  }
}
```

**Verification**:

```bash
cd frontend
npm run type-check  # Should pass - ApiAdapter now matches ApiInterface
make lint          # Should pass
make test          # All tests should still pass with fallback client
```

**Key Benefits**:

1. ✅ **Type Alignment**: `ApiAdapter` now complies with `ApiInterface` without type errors
2. ✅ **Consistent Pattern**: Both fallback and backend clients use same `ApiPromise<T>` return type
3. ✅ **HTTP Status Awareness**: Status codes available for error handling (future enhancement)
4. ✅ **No Breaking Changes**: TradingView interface still receives unwrapped data
5. ✅ **Clean Separation**: Service layer handles unwrapping, clients provide wrapped responses

---

### Step 3.2: Update Frontend Service to Use Smart Client Selection (Backend / Fallback)

**File**: `frontend/src/services/brokerTerminalService.ts`

After completing Step 3.0, the service file structure should look like this:

```typescript
import { ApiAdapter, type ApiPromise } from "@/plugins/apiAdapter";

// ============================================================================
// BROKER CLIENT INTERFACE
// ============================================================================

export interface ApiInterface {
  // All methods now return ApiPromise<T> = Promise<{status: number, data: T}>
  placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult>;
  modifyOrder(order: Order, confirmId?: string): ApiPromise<void>;
  cancelOrder(orderId: string): ApiPromise<void>;
  getOrders(): ApiPromise<Order[]>;
  getPositions(): ApiPromise<Position[]>;
  getExecutions(symbol: string): ApiPromise<Execution[]>;
  getAccountInfo(): ApiPromise<AccountMetainfo>;
}

// ============================================================================
// FALLBACK CLIENT (MOCK IMPLEMENTATION)
// ============================================================================

class BrokerFallbackClient implements ApiInterface {
  // ... existing fallback implementation
  // All methods now return {status: 200, data: T} format (see Step 3.0)
}

// ============================================================================
// BROKER TERMINAL SERVICE
// ============================================================================

export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _host: IBrokerConnectionAdapterHost;
  private readonly _quotesProvider: IDatafeedQuotesApi;

  // Client adapters
  private readonly apiFallback: ApiInterface;
  private readonly apiAdapter: ApiAdapter;

  // Mock flag
  private mock: boolean;

  constructor(
    host: IBrokerConnectionAdapterHost,
    datafeed: IDatafeedQuotesApi,
    mock: boolean = true // 👈 Default to fallback for safety
  ) {
    this._host = host;
    this._quotesProvider = datafeed;
    this.mock = mock;

    // Initialize clients
    this.apiFallback = new BrokerFallbackClient(host, datafeed);
    this.apiAdapter = new ApiAdapter();
  }

  /**
   * Get broker client based on mock flag
   * Same pattern as datafeedService._getApiAdapter()
   */
  private _getApiAdapter(mock: boolean = this.mock): ApiInterface {
    return mock ? this.apiFallback : this.apiAdapter;
  }

  // All methods unwrap .data from ApiResponse
  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const response = await this._getApiAdapter().placeOrder(order);
    const result = response.data; // 👈 Unwrap data

    const ordersResponse = await this._getApiAdapter().getOrders();
    const placedOrder = ordersResponse.data.find(
      (o) => o.id === result.orderId
    );
    if (placedOrder) {
      this._host.orderUpdate(placedOrder);
    }
    return result;
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    await this._getApiAdapter().modifyOrder(order, confirmId);

    const ordersResponse = await this._getApiAdapter().getOrders();
    const updatedOrder = ordersResponse.data.find(
      (o) => o.id === (confirmId ?? order.id)
    );
    if (updatedOrder) {
      this._host.orderUpdate(updatedOrder);
    }
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this._getApiAdapter().cancelOrder(orderId);

    const ordersResponse = await this._getApiAdapter().getOrders();
    const cancelledOrder = ordersResponse.data.find((o) => o.id === orderId);
    if (cancelledOrder) {
      this._host.orderUpdate(cancelledOrder);
    }
  }

  async orders(): Promise<Order[]> {
    const response = await this._getApiAdapter().getOrders();
    return response.data; // 👈 Unwrap data
  }

  async positions(): Promise<Position[]> {
    const response = await this._getApiAdapter().getPositions();
    return response.data; // 👈 Unwrap data
  }

  async executions(symbol: string): Promise<Execution[]> {
    const response = await this._getApiAdapter().getExecutions(symbol);
    return response.data; // 👈 Unwrap data
  }

  async accountsMetainfo(): Promise<AccountMetainfo[]> {
    const response = await this._getApiAdapter().getAccountInfo();
    return [response.data]; // 👈 Unwrap data
  }
}
```

**Key Design Points**:

1. ✅ **Type Alignment**: `ApiAdapter` now complies with `ApiInterface` through `ApiPromise<T>` return types
2. ✅ **Fallback Pattern**: Uses same `_getApiAdapter(mock)` pattern for smart client selection
3. ✅ **Response Unwrapping**: All service methods extract `.data` from `ApiResponse` before returning
4. ✅ **Type Safety**: TypeScript ensures both clients match `ApiInterface` contract at compile time
5. ✅ **Fallback Preserved**: Mock client is always available (default: `mock = true`)
6. ✅ **Clean Separation**: Clients return wrapped `ApiResponse`, service unwraps for TradingView
7. ✅ **Consistent Pattern**: Same architecture as `datafeedService.ts`

**Benefits of ApiPromise Pattern**:

- **Compile-Time Validation**: If backend API changes break the interface, TypeScript fails in `apiAdapter.ts`
- **HTTP Status Awareness**: Status codes available for error handling in future
- **No Duplication**: No separate wrapper class needed
- **Consistent Architecture**: Same pattern for both datafeed and broker
- **Clean Contracts**: Both fallback and backend clients implement identical interface

---

### Step 3.3: Run Frontend Tests Against Backend Stubs (TDD Red Phase) 🔴

**Goal**: Run frontend tests with backend client enabled to see them FAIL. This is the TDD "Red" phase.

**Note**: At this point, `ApiAdapter` and `BrokerFallbackClient` both implement `ApiInterface` with `ApiPromise<T>` return types. The `BrokerTerminalService` unwraps the `.data` property before returning to TradingView.

**File**: `frontend/src/services/brokerTerminalService.test.ts`

Update tests to use backend client with mock flag (inverted logic: `mock = false` means use backend):

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";
import { BrokerTerminalService } from "./brokerTerminalService";
import type {
  IBrokerConnectionAdapterHost,
  PreOrder,
  OrderType,
  Side,
} from "@public/trading_terminal/charting_library";

// Feature flag to switch between fallback and backend client
// mock = true (default) → use fallback
// mock = false → use backend API
const USE_MOCK = import.meta.env.VITE_USE_MOCK_BROKER !== "false";

describe("BrokerTerminalService", () => {
  let service: BrokerTerminalService;
  let mockHost: IBrokerConnectionAdapterHost;

  beforeEach(() => {
    mockHost = {
      orderUpdate: vi.fn(),
      positionUpdate: vi.fn(),
      executionUpdate: vi.fn(),
      // ... other required methods
    };

    // Use backend client when USE_MOCK = false
    service = new BrokerTerminalService(mockHost, mockDatafeed, USE_MOCK);
  });

  it("should place order successfully", async () => {
    const order: PreOrder = {
      symbol: "AAPL",
      type: 1, // OrderType.Limit
      side: 1, // Side.Buy
      qty: 100,
      limitPrice: 150.0,
    };

    const result = await service.placeOrder(order);

    // With backend stubs returning NotImplementedError, this will FAIL
    expect(result.orderId).toBeDefined();
    expect(result.orderId).toMatch(/^ORDER-\d+$/);
  });

  it("should get orders list", async () => {
    const orders = await service.orders();

    // With backend stubs, this will FAIL
    expect(Array.isArray(orders)).toBe(true);
  });

  it("should get positions list", async () => {
    const positions = await service.positions();

    // With backend stubs, this will FAIL
    expect(Array.isArray(positions)).toBe(true);
  });

  // ... all other tests
});
```

**Run Tests (Expected to FAIL)**:

```bash
cd frontend

# Run tests with fallback client (should pass)
make test

# Run tests with backend client (should FAIL - TDD Red phase)
cd backend
make dev &  # Start backend with stub endpoints

cd frontend
VITE_USE_MOCK_BROKER=false make test  # Tests will FAIL ❌

# Expected output:
# ❌ Error: NotImplementedError: Broker API not yet implemented
# ❌ Failed: should place order successfully
# ❌ Failed: should get orders list
# ❌ Failed: should get positions list
```

**Verification**: Frontend tests **MUST FAIL** at this point. This confirms:

1. ✅ Frontend is wired to backend API correctly
2. ✅ `ApiAdapter` is properly integrated and returns `ApiPromise<T>`
3. ✅ `BrokerTerminalService` correctly unwraps `.data` from responses
4. ✅ Backend stubs are returning errors as expected
5. ✅ We're in TDD "Red" phase - tests fail before implementation
6. ✅ Ready to implement backend logic to make tests pass (TDD "Green" phase)
   const positions = await service.getPositions();

   // With backend stubs, this will FAIL
   expect(Array.isArray(positions)).toBe(true);
   });

// ... all other tests
});

````

**Run Tests (Expected to FAIL)**:

```bash
cd frontend

# Run tests with fallback client (should pass)
make test

# Run tests with backend client (should FAIL - TDD Red phase)
cd backend
make dev &  # Start backend with stub endpoints

cd frontend
VITE_USE_MOCK_BROKER=false make test  # Tests will FAIL ❌

# Expected output:
# ❌ Error: NotImplementedError: Broker API not yet implemented
# ❌ Failed: should place order successfully
# ❌ Failed: should get orders list
# ❌ Failed: should get positions list
````

**Verification**: Frontend tests **MUST FAIL** at this point. This confirms:

1. ✅ Frontend is wired to backend API correctly
2. ✅ Backend stubs are returning errors as expected
3. ✅ We're in TDD "Red" phase - tests fail before implementation
4. ✅ Ready to implement backend logic to make tests pass (TDD "Green" phase)

---

## Phase 4: Implement Backend Logic (TDD) 🧪

**Goal**: Implement actual backend logic to make frontend tests pass (TDD Green phase).

### Step 4.1: Create Broker Service (Mock Logic)

**File**: `backend/src/trading_api/core/broker_service.py`

Copy mock logic from frontend fallback client to backend (this will make frontend tests pass):

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

### Step 4.2: Wire Service to API Endpoints

**File**: `backend/src/trading_api/api/broker.py`

Replace `NotImplementedError` stubs with actual service calls:

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

## Phase 5: Verify Frontend Tests Pass then Write Backend Tests (TDD Green Phase) ✅

**Goal**: Verify that frontend tests now pass with the implemented backend logic.

### Step 5.1: Run Frontend Tests with Backend Implementation

After implementing the backend logic (Phase 4), run frontend tests with backend client to verify they pass:

**Verification (TDD Green Phase)** 🟢:

```bash
# Terminal 1: Start backend with implementation
cd backend
make dev

# Terminal 2: Run frontend tests with backend client
cd frontend
VITE_USE_MOCK_BROKER=false make test

# Expected output:
# ✅ All tests should now PASS
# ✅ should place order successfully
# ✅ should get orders list
# ✅ should get positions list
# ✅ should modify order
# ✅ should cancel order
# ✅ should get executions
# ✅ should get account info
```

**Success Criteria**:

1. ✅ All frontend tests pass with `VITE_USE_MOCK_BROKER=false`
2. ✅ Frontend tests still pass with fallback client (without flag)
3. ✅ Backend tests pass (`cd backend && make test`)
4. ✅ No type errors (`npm run type-check`)
5. ✅ No lint errors (`make lint`)

### Step 5.2: Write Backend Unit Tests

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

### Step 5.3: Write Backend API Integration Tests

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

## Phase 6: Full Stack Validation 🚀

### Step 6.1: Manual E2E Testing

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

### Step 6.2: Smoke Tests (Optional)

```bash
cd smoke-tests
npm test  # Playwright E2E tests
```

---

## Implementation Checklist

| Phase     | Step                         | File(s)                                               | Verification          | Status |
| --------- | ---------------------------- | ----------------------------------------------------- | --------------------- | ------ |
| **1.1**   | Consolidate in service       | `frontend/src/services/brokerTerminalService.ts`      | `make test`           | ✅     |
| **2.1**   | Backend models               | `backend/src/trading_api/models/broker/`              | `make lint`           | ⏳     |
| **2.2**   | API stubs                    | `backend/src/trading_api/api/broker.py`               | `make dev`            | ⏳     |
| **2.3**   | Register router              | `backend/src/trading_api/main.py`                     | Backend starts        | ⏳     |
| **2.4.1** | Generate OpenAPI client      | Auto-generated                                        | Generation success    | ✅     |
| **2.4.2** | Add broker to adapter        | `frontend/src/plugins/apiAdapter.ts` (consolidated)   | `npm run type-check`  | ✅     |
| **3.1**   | Adjust for ApiPromise types  | `frontend/src/services/brokerTerminalService.ts`      | Type check passes     | ⏳     |
| **3.2**   | Wire backend client          | `frontend/src/services/brokerTerminalService.ts`      | `make test`           | ⏳     |
| **3.3**   | Run tests (Red phase) 🔴     | `frontend/src/services/brokerTerminalService.test.ts` | Tests FAIL (expected) | ⏳     |
| **4.1**   | Broker service               | `backend/src/trading_api/core/broker_service.py`      | N/A                   | ⏳     |
| **4.2**   | Wire endpoints               | `backend/src/trading_api/api/broker.py`               | N/A                   | ⏳     |
| **4.3**   | Backend unit tests           | `backend/tests/test_broker_service.py`                | `make test`           | ⏳     |
| **4.4**   | Backend API tests            | `backend/tests/test_api_broker.py`                    | `make test`           | ⏳     |
| **5.1**   | Verify tests pass (Green) 🟢 | Frontend + Backend tests                              | All tests pass        | ⏳     |
| **6.1**   | E2E manual testing           | Browser testing                                       | Visual verification   | ⏳     |
| **6.2**   | Smoke tests                  | `smoke-tests/`                                        | `npm test`            | ⏳     |

---

## Key Benefits

1. ✅ **Incremental**: Each step is small and verifiable
2. ✅ **Test-Driven**: Tests guide implementation at every phase
3. ✅ **Interface-First**: Contract defined before implementation
4. ✅ **Reversible**: Can rollback to any working phase
5. ✅ **Parallel Work**: Backend and frontend can evolve together
6. ✅ **Fallback Preserved**: Mock client always available
7. ✅ **Type-Safe**: TypeScript + Pydantic ensure type alignment
8. ✅ **Breaking Change Detection**: Targeted type casting on enums/literals catches structural API mismatches at compile time
9. ✅ **Consolidated Architecture**: Single `ApiAdapter` class handles both datafeed and broker operations
10. ✅ **Maintainable**: All backend API conversions centralized in one file

---

## Notes

- Each phase completion should be committed to git
- All tests must pass before moving to next phase
- Interface mismatches trigger adjustment loop in Phase 2.4
- Frontend always works (via fallback client) throughout implementation
- Type casting rule: Only use `as unknown as` for literal/alias/enum fields, never entire objects
- Broker and datafeed methods are consolidated in `ApiAdapter` class for consistency

---

**Last Updated**: October 19, 2025  
**Maintained by**: Development Team
