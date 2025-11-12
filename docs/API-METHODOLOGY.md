# Backend Service Implementation Methodology (TDD with Dual-Client Architecture)

**Template Version**: 3.0  
**Status**: Generic Reusable Template (Modular Architecture)  
**Original Implementation**: Broker Terminal Service  
**Applicable To**: Any backend service implementation (broker, datafeed, notifications, user management, etc.)  
**Architecture**: Modular backend with factory-based pattern

---

## Overview

This document outlines a **generic, incremental, test-driven approach** for implementing backend services integrated with frontend clients. The methodology applies to any service (broker, datafeed, notifications, etc.) and ensures:

- All tests pass at each step
- Interface contracts are clearly defined before implementation
- Implementation can be safely rolled back at any point
- Type safety across the full stack
- Breaking changes are detected at compile time

**Use this template for**: Trading services, data services, user services, notification services, or any backend API with frontend integration.

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

**Design Pattern**: Co-locate the interface contract and fallback implementation within the service file for rapid iteration. This reduces file management overhead while maintaining clean separation of concerns.

### Step 1.1: Consolidate Interface and Fallback Client

**Location Pattern**: `frontend/src/services/{serviceName}Service.ts`

The service file should contain three main sections:

1. **ApiInterface** - Contract definition with all operations
2. **ApiFallback** - Mock implementation with private state management
3. **ServiceAdapter** - External library/framework adapter using delegation

**Architecture Pattern**:

```typescript
// ============================================================================
// INTERFACE CONTRACT
// ============================================================================

export interface ApiInterface {
  // Define all service operations
  // Pattern: {action}{Resource}(params): Promise<Result>
  createResource(data: ResourceData): ApiPromise<ResourceResult>
  updateResource(id: string, data: ResourceData): ApiPromise<void>
  deleteResource(id: string): ApiPromise<void>
  getResources(filter?: FilterParams): ApiPromise<Resource[]>
  getResourceDetails(id: string): ApiPromise<ResourceDetails>
}

// ============================================================================
// FALLBACK CLIENT (MOCK IMPLEMENTATION)
// ============================================================================

class ApiFallback implements ApiInterface {
  // Private state management (in-memory storage)
  private readonly _resourcesById = new Map<string, Resource>()
  private _counter = 1

  // Private helper methods for simulation
  private async simulateAsync(delay: number = 100): Promise<void> { ... }
  private generateId(prefix: string): string { ... }

  // Public API methods implementing interface contract
  async createResource(data: ResourceData): ApiPromise<ResourceResult> {
    const id = this.generateId('RESOURCE')
    const resource = { id, ...data, status: 'active' }
    this._resourcesById.set(id, resource)
    return { status: 200, data: { id } }
  }
  // ... implement all interface methods
}

// ============================================================================
// SERVICE ADAPTER (EXTERNAL LIBRARY INTEGRATION)
// ============================================================================

export class ServiceAdapter implements ExternalLibraryInterface {
  private readonly _client: ApiInterface
  private readonly mock: boolean

  constructor(
    externalDeps: ExternalDependencies,
    mock: boolean = true
  ) {
    // Initialize dual-client system
    const apiFallback = new ApiFallback()
    const apiAdapter = new ApiAdapter() // Real backend client
    this._client = mock ? apiFallback : apiAdapter
  }

  // Delegate to client and handle external library concerns
  async externalLibraryMethod(params: ExternalParams): Promise<ExternalResult> {
    const response = await this._client.createResource(this.mapParams(params))
    this.notifyExternalLibrary(response.data)
    return this.mapToExternalFormat(response.data)
  }
}
```

**Example from broker implementation**:

- `ApiInterface` defines broker operations (place/modify/cancel orders, get positions)
- `ApiFallback` maintains in-memory maps for orders, positions, executions
- `BrokerTerminalService` adapts to TradingView's `IBrokerWithoutRealtime` interface

**Verification**:

```bash
cd frontend
make test      # All tests pass
make lint      # No linting errors
npm run type-check  # No TypeScript errors
```

---

## Phase 2: Define Backend API Contract (Empty Stubs) 📝

**Goal**: Create backend API structure matching the client interface, generate OpenAPI client, verify interface alignment.

> ⚠️ **WebSocket Features**: If implementing WebSocket operations (not REST), use the router code generation mechanism documented in [`backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md`](backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md) instead of creating routers manually. Module-specific WebSocket routers are generated into `modules/{module}/ws_generated/`. This ensures type safety and consistency.

### Step 2.1: Create Backend Models

**Location Pattern**: `backend/src/trading_api/models/{domain}/`

**Note**: Models are organized by business domain (broker, market, user, etc.), not by service name. This supports model reuse across modules.

**Model Design Guidelines**:

1. **Match Frontend Types**: Pydantic models should mirror frontend TypeScript types
2. **Use Enums**: Define enums for constrained values (matches frontend)
3. **Optional Fields**: Use `Optional[T]` with defaults for nullable fields
4. **Validation**: Add Pydantic validators for business logic
5. **Documentation**: Include docstrings for all models

**Model Structure Pattern**:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import IntEnum
from datetime import datetime

# Pattern 1: Enums for constrained values
class ResourceStatus(IntEnum):
    """Status enum matching frontend constants"""
    PENDING = 1
    ACTIVE = 2
    INACTIVE = 3
    DELETED = 4

class ResourceType(IntEnum):
    """Type enum matching frontend constants"""
    TYPE_A = 1
    TYPE_B = 2

# Pattern 2: Request models (from client)
class ResourceRequest(BaseModel):
    """Request to create/update resource"""
    name: str = Field(..., min_length=1, max_length=100)
    type: ResourceType
    value: float = Field(..., gt=0)
    metadata: Optional[dict] = None

    @validator('name')
    def validate_name(cls, v):
        if v.strip() != v:
            raise ValueError('Name cannot have leading/trailing spaces')
        return v

# Pattern 3: Response models (to client)
class ResourceResponse(BaseModel):
    """Complete resource with server-generated fields"""
    id: str
    name: str
    type: ResourceType
    value: float
    status: ResourceStatus
    metadata: Optional[dict] = None
    createdAt: int  # Unix timestamp
    updatedAt: Optional[int] = None

# Pattern 4: Result models (operation outcomes)
class ResourceOperationResult(BaseModel):
    """Result of resource operation"""
    id: str
    success: bool = True
    message: Optional[str] = None

# Pattern 5: List/query models
class ResourceList(BaseModel):
    """Paginated list of resources"""
    items: List[ResourceResponse]
    total: int
    page: int
    pageSize: int
```

**Real-world example (broker service)**:

- `PreOrder` (request) → `PlacedOrder` (response)
- `OrderStatus`, `OrderType`, `Side` (enums)
- `PlaceOrderResult` (operation result)
- `Position`, `Execution` (domain models)

---

### Step 2.2: Create REST API Endpoints (Empty Stubs)

**Location Pattern**: `backend/src/trading_api/modules/{module}/api.py`

**Note**: Each module has its own `api.py` file. Shared/cross-cutting APIs go in `shared/api/` (e.g., health, versions).

**Endpoint Design Guidelines**:

1. **CRUD Operations**: Follow RESTful patterns (POST, GET, PUT/PATCH, DELETE)
2. **Route Parameters**: Include `summary` and `operation_id` for OpenAPI generation
3. **Response Models**: Always define explicit response models
4. **Error Handling**: Let FastAPI handle validation errors automatically
5. **Empty Stubs**: Start with `NotImplementedError` to establish contract

**Endpoint Pattern**:

```python
from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
from pydantic import BaseModel
from trading_api.models.{domain} import (
    ResourceRequest,
    ResourceResponse,
    ResourceOperationResult,
    # ... import all models from appropriate domain folder
)

class SuccessResponse(BaseModel):
    """Generic success response for operations without data"""
    success: bool = True
    message: str = "Operation completed successfully"

# Router configuration
# Note: Prefix should NOT include version (/api/v1 added by main.py)
router = APIRouter(prefix="/{service}", tags=["{service}"])

# ============================================================================
# CREATE Operation (POST)
# ============================================================================

@router.post(
    "/resources",
    response_model=ResourceOperationResult,
    summary="Create a new resource",
    operation_id="createResource",
    status_code=201,
)
async def createResource(resource: ResourceRequest) -> ResourceOperationResult:
    """Create a new resource in the system"""
    raise NotImplementedError("Service API not yet implemented")  # 👈 Empty stub

# ============================================================================
# READ Operations (GET)
# ============================================================================

@router.get(
    "/resources",
    response_model=List[ResourceResponse],
    summary="Get all resources",
    operation_id="getResources",
)
async def getResources(
    status: Optional[int] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
) -> List[ResourceResponse]:
    """Get list of resources with optional filters"""
    raise NotImplementedError("Service API not yet implemented")

@router.get(
    "/resources/{resource_id}",
    response_model=ResourceResponse,
    summary="Get resource by ID",
    operation_id="getResource",
)
async def getResource(
    resource_id: str = Path(..., description="Resource identifier")
) -> ResourceResponse:
    """Get detailed information for a specific resource"""
    raise NotImplementedError("Service API not yet implemented")

# ============================================================================
# UPDATE Operation (PUT)
# ============================================================================

@router.put(
    "/resources/{resource_id}",
    response_model=SuccessResponse,
    summary="Update an existing resource",
    operation_id="updateResource",
)
async def updateResource(
    resource_id: str,
    resource: ResourceRequest
) -> SuccessResponse:
    """Update an existing resource"""
    raise NotImplementedError("Service API not yet implemented")

# ============================================================================
# DELETE Operation (DELETE)
# ============================================================================

@router.delete(
    "/resources/{resource_id}",
    response_model=SuccessResponse,
    summary="Delete a resource",
    operation_id="deleteResource",
)
async def deleteResource(resource_id: str) -> SuccessResponse:
    """Delete a resource"""
    raise NotImplementedError("Service API not yet implemented")

# ============================================================================
# CUSTOM Operations (service-specific actions)
# ============================================================================

@router.post(
    "/resources/{resource_id}/actions/custom",
    response_model=SuccessResponse,
    summary="Perform custom action on resource",
    operation_id="customAction",
)
async def customAction(
    resource_id: str,
    params: dict
) -> SuccessResponse:
    """Perform service-specific action"""
    raise NotImplementedError("Service API not yet implemented")
```

**Real-world examples** (modular architecture):

- **Broker module**: `modules/broker/api.py` - POST `/broker/orders`, PUT `/broker/orders/{id}`, DELETE `/broker/orders/{id}`, GET `/broker/positions`
- **Datafeed module**: `modules/datafeed/api.py` - GET `/datafeed/config`, POST `/datafeed/quotes`
- **Shared APIs**: `shared/api/health.py` - GET `/health`, `shared/api/versions.py` - GET `/versions`

**Note**: Module prefix (e.g., `/broker`, `/datafeed`) is added by the module's `get_api_routers()` method.

---

### Step 2.3: Register Module in Application Factory

**Location Pattern**: `backend/src/trading_api/app_factory.py`

**Note**: In the modular architecture, modules are registered via the factory pattern, not directly in main.py.

```python
# Modules register themselves via Module Protocol
from trading_api.modules.{module} import {Module}Module

# In app_factory.py create_app() function:
registry.register({Module}Module())

# Module's get_api_routers() returns routers to include
for module in registry.get_enabled_modules():
    for router in module.get_api_routers():
        api_app.include_router(router, prefix="/api/v1")
```

**Verification**:

```bash
cd backend
make dev  # Start backend server
# Server starts successfully
# OpenAPI spec exported to backend/openapi.json
# Service endpoints visible in /docs
```

---

### Step 2.4: Generate Frontend Client & Create Adapter

**Architecture Summary**:

- **Consolidated Adapter**: All backend API operations consolidated in single `ApiAdapter` class
- **Location**: `frontend/src/plugins/apiAdapter.ts`
- **Single Source of Truth**: All backend API interactions go through one adapter file
- **No Service-Specific Adapters**: Consolidate multiple services in same adapter (not separate files)

**Architecture Pattern**: Never import generated backend models outside the adapter. The adapter layer:

- Detects breaking changes at compile time through targeted type casting
- Converts backend types to frontend types via **mapper functions**
- Provides clean, consolidated interface for all API operations
- Applies type casting only to enum/literal/alias fields, not entire objects

**Mapper Functions Pattern**: For complex type transformations, create dedicated mapper functions in `frontend/src/plugins/mappers.ts`:

- **Type-Safe**: Import backend types (suffixed `_Backend`) only in mapper layer
- **Reusable**: Share mappers across REST API and WebSocket clients
- **Isolated**: Backend types never leak outside mappers
- **Maintainable**: Centralized transformation logic in one file
- **Runtime Validation**: Handle enum conversions and null/undefined properly

**Step 2.4.1: Generate OpenAPI Client**

```bash
# Generate TypeScript client from backend OpenAPI spec
cd frontend
make generate-openapi-client

# Generated client structure:
# - frontend/src/clients_generated/trader-client-generated/
# - API methods matching backend operation_id values
# - Type definitions matching backend Pydantic models
```

**Step 2.4.2: Add Service Methods to API Adapter**

**Location**: `frontend/src/plugins/apiAdapter.ts`

**CRITICAL**: The `ApiAdapter` class can optionally implement service-specific `ApiInterface` interfaces to enable type checking against frontend service contracts.

**Design Constraints**:

1. **API Versioning Constraint**:

   - Use per-module-version API classes from generated clients (e.g., `BrokerApi` from `trader-client-broker_v1`)
   - **DO NOT** import individual API methods directly
   - Each module+version generates its own client package: `trader-client-{module}_v{version}`
   - Example: `trader-client-broker_v1` → `BrokerApi`, `trader-client-datafeed_v1` → `DatafeedApi`
   - Configuration classes are version-specific: `Configuration as BrokerConfigurationV1`
   - Supports modular architecture with independent per-module versioning

2. **Type Casting Safety Constraint**:
   - **Rule**: Unsafe casting (`as unknown as`) **ONLY** for literal/alias/enum fields
   - **DO NOT** cast entire objects or complex types blindly
   - Cast only specific enum/literal fields that differ between backend and frontend
   - Ensures type mismatches on complex objects caught at compile time
   - Use type-safe mappers with runtime validation
   - **Mapper Functions**: Can import backend types (not exposed outside)
   - **Adapter Methods**: Never import/use backend types directly

**Pattern**: This adapter wraps the generated OpenAPI client. Never import generated models outside this file.
**Type Casting Examples**:

```typescript
// ✅ CORRECT: Cast enum/literal only
const response = await this.rawApi.createResource({
  ...resource,
  type: resource.type as unknown as BackendResourceType["type"],
  status: resource.status as unknown as BackendResourceType["status"],
});

// ✅ CORRECT: Inline mapper within adapter (simple transformations)
const response = await this.rawApi.createResource({
  ...resource,
  type: resource.type as unknown as BackendResourceType["type"],
  metadata: resource.metadata ?? null,
});

// ✅ BETTER: Dedicated mapper in mappers.ts (complex/reusable transformations)
// File: frontend/src/plugins/mappers.ts
import type { ResourceData as ResourceData_Backend } from "@clients/trader-client-generated";
import type { FrontendResourceData } from "@/types";

export function mapResourceData(
  data: FrontendResourceData
): ResourceData_Backend {
  return {
    name: data.name,
    type: data.type as unknown as ResourceData_Backend["type"],
    value: data.value,
    metadata: data.metadata ?? null,
  };
}

// Usage in ApiAdapter:
import { mapResourceData } from "@/plugins/mappers";
const response = await this.rawApi.createResource(mapResourceData(resource));

// ❌ INCORRECT: Casting entire object
const response = await this.rawApi.createResource(
  resource as unknown as BackendResource
);
```

**Adapter Implementation Pattern**:

```typescript
/**
 * API Adapter (Per-Module-Version Architecture)
 *
 * Wraps generated OpenAPI clients for type conversion and clean interface.
 * Rule: Never import backend models outside this file.
 * Constraint: Use per-module-version API classes (BrokerApi from v1, DatafeedApi from v1, etc.) for all calls.
 * Type Casting: Only cast enums/literals, never entire objects.
 * Versioning: Each module can have independent versions (broker v1, datafeed v1, etc.)
 */

import type {
  ResourceRequest as ResourceRequest_Backend,
  AnotherType as AnotherType_Backend,
} from "@clients/trader-client-broker_v1";
import {
  BrokerApi,
  Configuration as BrokerConfigurationV1
} from "@clients/trader-client-broker_v1";
import {
  DatafeedApi,
  Configuration as DatafeedConfigurationV1
} from "@clients/trader-client-datafeed_v1";
import type {
  FrontendResourceRequest,
  FrontendResourceResponse,
  // ... import frontend types
} from "@/types" or "@external/library";

export type ApiResponse<T> = { status: number; data: T };
export type ApiPromise<T> = Promise<ApiResponse<T>>;

/**
 * Mapper Decision Guide:
 *
 * 1. Simple transformations (1-2 field mappings):
 *    - Inline in ApiAdapter method
 *    - Example: { ...data, status: data.status as unknown as Backend["status"] }
 *
 * 2. Complex transformations (3+ fields, logic, reuse across REST + WebSocket):
 *    - Create in mappers.ts
 *    - Example: mapQuoteData(), mapPreOrder()
 *
 * 3. Backend type imports:
 *    - Mappers: CAN import backend types (ResourceData_Backend)
 *    - ApiAdapter: CANNOT import backend types directly
 *    - Services: NEVER import backend types
 */

// Import mappers from centralized file (for complex transformations)
import { mapQuoteData, mapPreOrder } from '@/plugins/mappers';

export class ApiAdapter {
  // Per-module-version API clients
  private brokerApi: BrokerApi;
  private datafeedApi: DatafeedApi;
  private brokerConfig: BrokerConfigurationV1;
  private datafeedConfig: DatafeedConfigurationV1;

  constructor() {
    // Construct base path with version suffix
    const ApiV1BasePath = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + "/v1";

    // Initialize per-module-version configurations with module-specific paths
    // Base path format: {base}/v{version}/{module}
    // Example: http://localhost:8000/v1/broker, http://localhost:8000/v1/datafeed
    // In multi-process mode, nginx routes these to different backend servers
    this.brokerConfig = new BrokerConfigurationV1({ basePath: ApiV1BasePath + '/broker' });
    this.datafeedConfig = new DatafeedConfigurationV1({ basePath: ApiV1BasePath + '/datafeed' });

    // Initialize per-module-version API clients
    this.brokerApi = new BrokerApi(this.brokerConfig);
    this.datafeedApi = new DatafeedApi(this.datafeedConfig);
  }

  // ======================================================================
  // SERVICE A METHODS
  // ======================================================================

  // Example 1: Simple inline transformation (1-2 fields)
  async createResource(data: FrontendResourceRequest): ApiPromise<FrontendResourceResponse> {
    const response = await this.rawApi.createResource({
      ...data,
      type: data.type as unknown as ResourceRequest_Backend["type"],
    });
    return {
      status: response.status,
      data: response.data as FrontendResourceResponse,
    };
  }

  // Example 2: Complex transformation using mapper from mappers.ts
  async getQuotes(symbols: string[]): ApiPromise<QuoteData[]> {
    const response = await this.rawApi.getQuotes({ symbols });
    return {
      status: response.status,
      data: response.data.map(mapQuoteData),  // 👈 Reusable mapper
    };
  }

  // Example 3: Array mapping with inline transformation
  async getResources(): ApiPromise<FrontendResourceResponse[]> {
    const response = await this.rawApi.getResources();
    return {
      status: response.status,
      data: response.data.map(item => ({
        ...item,
        status: item.status as unknown as FrontendResourceResponse["status"],
      })),
    };
  }

  // ======================================================================
  // SERVICE B METHODS
  // ======================================================================

  async otherServiceOperation(params: OtherParams): ApiPromise<OtherResult> {
    const response = await this.rawApi.otherServiceOperation(params);
    return { status: response.status, data: response.data as OtherResult };
  }
}
```

**Real-world examples**:

- **Broker service**: `placeOrder` (uses `mapPreOrder` from mappers.ts), `getPositions`, `closePosition`
- **Datafeed service**: `getQuotes` (uses `mapQuoteData` from mappers.ts), `resolveSymbol`, `getBars`
- Both consolidated in single `ApiAdapter` class

**When to Create Mappers** (`frontend/src/plugins/mappers.ts`):

1. ✅ **Complex transformations** - 3+ field mappings with logic
2. ✅ **Reusable across REST + WebSocket** - Used by both `ApiAdapter` and `WsAdapter`
3. ✅ **Nested object transformations** - Multiple levels of structure mapping
4. ✅ **Conditional logic** - Different mapping based on status/type
5. ✅ **Backend → Frontend direction** - QuoteData_Backend → QuoteData (TradingView)
6. ✅ **Frontend → Backend direction** - PreOrder (TradingView) → PreOrder_Backend

**When to Use Inline Mapping** (within `ApiAdapter` methods):

1. ✅ **Simple enum/literal casting** - 1-2 fields only
2. ✅ **Single-use transformations** - Not shared elsewhere
3. ✅ **Trivial null handling** - `data.field ?? null`

**Type Alignment Adjustment Loop**:

If frontend types don't match backend:

1. Adjust backend API model signatures
2. Regenerate OpenAPI spec: restart `make dev` (backend)
3. Regenerate TypeScript client: `make generate-openapi-client` (frontend)
4. Update adapter type conversions in `apiAdapter.ts`
5. Apply targeted enum/literal casting only where needed
6. Repeat until interface matches perfectly

**Benefits of This Architecture**:

1. ✅ **Breaking Change Detection**: Compile-time errors for structural mismatches
2. ✅ **Targeted Type Casting**: Only enum/literal fields need unsafe casting
3. ✅ **Compile-Time Validation**: Object structure changes trigger TypeScript errors
4. ✅ **Isolation**: Generated models never leak into application code
5. ✅ **Clean Interface**: Consistent API surface across all services
6. ✅ **Consolidated Architecture**: Single adapter class for all backend APIs
7. ✅ **Maintainability**: All type conversions in one place
8. ✅ **Explicit Safety**: Developers see which fields have type discrepancies

---

## Phase 3: Frontend Integration & TDD Setup

**Goal**: Wire frontend service to use real backend client, run tests against stub backend to see failures (TDD Red phase).

**Note**: Backend client adapter was created in Step 2.4.2 (service methods added to consolidated `ApiAdapter`). The `ApiAdapter` returns `ApiPromise<T>` which wraps responses with HTTP status codes.

### Step 3.1: Align ApiInterface with ApiPromise Return Types

**Goal**: Update service `ApiInterface` and fallback client to use `ApiPromise<T>` return types, matching the `ApiAdapter` signature.

**Location**: `frontend/src/services/{serviceName}Service.ts`

**Changes Pattern**:

1. **Import ApiPromise type** from adapter:

```typescript
import { ApiAdapter, type ApiPromise } from "@/plugins/apiAdapter";
```

2. **Update ApiInterface** to return `ApiPromise<T>`:

```typescript
export interface ApiInterface {
  // All operations return ApiPromise<T> = Promise<{status: number, data: T}>
  createResource(data: ResourceRequest): ApiPromise<ResourceResult>;
  updateResource(id: string, data: ResourceRequest): ApiPromise<void>;
  deleteResource(id: string): ApiPromise<void>;
  getResources(): ApiPromise<Resource[]>;
  getResourceDetails(id: string): ApiPromise<ResourceDetails>;
}
```

3. **Update ApiFallback** to wrap responses:

```typescript
class ApiFallback implements ApiInterface {
  // ... existing private state ...

  async createResource(data: ResourceRequest): ApiPromise<ResourceResult> {
    const id = this.generateId("RESOURCE");
    const resource = { id, ...data, status: "active" };
    this._resourcesById.set(id, resource);

    // Wrap in ApiResponse format
    return {
      status: 200,
      data: { id },
    };
  }

  async getResources(): ApiPromise<Resource[]> {
    return {
      status: 200,
      data: Array.from(this._resourcesById.values()),
    };
  }

  // Apply pattern to all methods: return { status: 200, data: <result> }
}
```

4. **Update ServiceAdapter** to unwrap `.data`:

```typescript
export class ServiceAdapter implements ExternalLibraryInterface {
  // ... existing setup ...

  async externalMethod(params: ExternalParams): Promise<ExternalResult> {
    const response = await this._getApiAdapter().createResource(params);
    const result = response.data; // 👈 Unwrap data

    // Additional logic (notifications, transformations, etc.)
    this.notifyExternalLibrary(result);

    return this.mapToExternalFormat(result);
  }

  async getResources(): Promise<Resource[]> {
    const response = await this._getApiAdapter().getResources();
    return response.data; // 👈 Unwrap data
  }
}
```

**Verification**:

```bash
cd frontend
npm run type-check  # Should pass - ApiAdapter matches ApiInterface
make lint           # Should pass
make test           # All tests should still pass with fallback client
```

**Key Benefits**:

1. ✅ **Type Alignment**: `ApiAdapter` complies with `ApiInterface` without type errors
2. ✅ **Consistent Pattern**: Both fallback and backend clients use same return type
3. ✅ **HTTP Status Awareness**: Status codes available for error handling
4. ✅ **No Breaking Changes**: External library interface receives unwrapped data
5. ✅ **Clean Separation**: Service adapter handles unwrapping, clients provide wrapped responses

---

### Step 3.2: Update Frontend Service to Use Smart Client Selection

**Location**: `frontend/src/services/{serviceName}Service.ts`

**Pattern**: Dual-client system with smart selection based on environment/configuration.

```typescript
import { ApiAdapter, type ApiPromise } from "@/plugins/apiAdapter";

// ============================================================================
// CLIENT INTERFACE
// ============================================================================

export interface ApiInterface {
  // All methods return ApiPromise<T>
  createResource(data: ResourceRequest): ApiPromise<ResourceResult>;
  // ... all service operations
}

// ============================================================================
// FALLBACK CLIENT
// ============================================================================

class ApiFallback implements ApiInterface {
  // All methods return {status: 200, data: T} format
}

// ============================================================================
// SERVICE ADAPTER
// ============================================================================

export class ServiceAdapter implements ExternalLibraryInterface {
  private readonly _externalDeps: ExternalDependencies;

  // Client adapters
  private readonly apiFallback: ApiInterface;
  private readonly apiAdapter: ApiInterface;

  // Mode flag
  private mock: boolean;

  constructor(
    externalDeps: ExternalDependencies,
    mock: boolean = true // 👈 Default to fallback for safety
  ) {
    this._externalDeps = externalDeps;
    this.mock = mock;

    // Initialize both clients
    this.apiFallback = new ApiFallback();
    this.apiAdapter = new ApiAdapter();
  }

  /**
   * Get API client based on mock flag
   * Pattern: Same as datafeedService._getApiAdapter()
   */
  private _getApiAdapter(mock: boolean = this.mock): ApiInterface {
    return mock ? this.apiFallback : this.apiAdapter;
  }

  // All methods unwrap .data from ApiResponse
  async externalMethod(params: ExternalParams): Promise<ExternalResult> {
    const response = await this._getApiAdapter().createResource(params);
    const result = response.data; // 👈 Unwrap data

    // Handle external library concerns
    this.notifyExternalLibrary(result);
    return this.mapToExternalFormat(result);
  }
}
```

**Configuration Pattern**:

```typescript
// Environment-based selection
const useMock = import.meta.env.VITE_USE_MOCK_{SERVICE} !== 'false'
const service = new ServiceAdapter(deps, useMock)

// Or explicit selection
const service = new ServiceAdapter(deps, false) // Use backend
```

---

### Step 3.3: Run Frontend Tests Against Backend Stubs (TDD Red Phase) 🔴

**Goal**: Run frontend tests with backend client enabled to see them **FAIL**. This is the TDD "Red" phase.

**Test Pattern**: `frontend/src/services/__tests__/{serviceName}Service.test.ts`

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ServiceAdapter } from "./{serviceName}Service";
import type { ExternalDependencies } from "@external/library";

// Feature flag to switch between fallback and backend
const USE_MOCK = import.meta.env.VITE_USE_MOCK_{SERVICE} !== "false";

describe("ServiceAdapter", () => {
  let service: ServiceAdapter;
  let mockDeps: ExternalDependencies;

  beforeEach(() => {
    mockDeps = {
      // Mock external dependencies
      notify: vi.fn(),
      // ...
    };

    // Use backend client when USE_MOCK = false
    service = new ServiceAdapter(mockDeps, USE_MOCK);
  });

  it("should create resource successfully", async () => {
    const data = {
      name: "Test Resource",
      type: 1,
      value: 100.0,
    };

    const result = await service.createResource(data);

    // With backend stubs returning NotImplementedError, this will FAIL
    expect(result.id).toBeDefined();
    expect(result.id).toMatch(/^RESOURCE-\d+$/);
  });

  it("should get resources list", async () => {
    const resources = await service.getResources();

    // With backend stubs, this will FAIL
    expect(Array.isArray(resources)).toBe(true);
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
# Terminal 1: Start backend with stub endpoints
cd backend
make dev &

# Terminal 2: Run tests against backend
cd frontend
VITE_USE_MOCK_{SERVICE}=false make test  # Tests will FAIL ❌

# Expected output:
# ❌ Error: NotImplementedError: Service API not yet implemented
# ❌ Failed: should create resource successfully
# ❌ Failed: should get resources list
# ❌ Failed: should update resource
```

**Verification**: Frontend tests **MUST FAIL** at this point. This confirms:

1. ✅ Frontend is wired to backend API correctly
2. ✅ `ApiAdapter` is properly integrated and returns `ApiPromise<T>`
3. ✅ `ServiceAdapter` correctly unwraps `.data` from responses
4. ✅ Backend stubs are returning errors as expected
5. ✅ We're in TDD "Red" phase - tests fail before implementation
6. ✅ Ready to implement backend logic to make tests pass (TDD "Green" phase)

---

## Phase 4: Implement Backend Logic (TDD) 🧪

**Goal**: Implement actual backend logic to make frontend tests pass (TDD Green phase).

### Step 4.1: Create Service Layer

**Location Pattern**: `backend/src/trading_api/modules/{module}/service.py`

**Note**: Each module has its own `service.py` file containing the service implementation. Services are lazy-loaded by the module.

**Service Design Guidelines**:

1. **State Management**: Use in-memory storage (Dict, List) for development/testing
2. **Async Operations**: Use `async/await` for all public methods
3. **ID Generation**: Generate unique IDs with prefixes (e.g., `RESOURCE-{counter}`)
4. **Error Handling**: Raise `ValueError` for business logic errors
5. **Private Methods**: Use `_` prefix for internal helpers

**Service Pattern**:

```python
import asyncio
import time
from typing import Dict, List, Optional
from trading_api.models.{domain} import (
    ResourceRequest,
    ResourceResponse,
    ResourceOperationResult,
    ResourceStatus,
    # ... import all models from appropriate domain
)

class {ServiceName}Service:
    """Service implementation for {service_name}"""

    def __init__(self) -> None:
        # In-memory state (replace with DB in production)
        self._resources: Dict[str, ResourceResponse] = {}
        self._counter = 1

    async def create_resource(self, request: ResourceRequest) -> ResourceOperationResult:
        """
        Create a new resource

        Args:
            request: Resource creation request

        Returns:
            ResourceOperationResult: Result with generated resource ID
        """
        resource_id = f"RESOURCE-{self._counter}"
        self._counter += 1

        resource = ResourceResponse(
            id=resource_id,
            name=request.name,
            type=request.type,
            value=request.value,
            status=ResourceStatus.ACTIVE,
            metadata=request.metadata,
            createdAt=int(time.time() * 1000),
        )

        self._resources[resource_id] = resource

        # Optional: Simulate async processing
        asyncio.create_task(self._process_async(resource_id))

        return ResourceOperationResult(id=resource_id, success=True)

    async def _process_async(self, resource_id: str) -> None:
        """Private: Simulate async background processing"""
        await asyncio.sleep(0.1)  # Small delay
        # Update resource or trigger side effects
        if resource := self._resources.get(resource_id):
            # Perform processing...
            pass

    async def get_resources(self, status: Optional[int] = None) -> List[ResourceResponse]:
        """Get all resources with optional filtering"""
        resources = list(self._resources.values())
        if status is not None:
            resources = [r for r in resources if r.status == status]
        return resources

    async def get_resource(self, resource_id: str) -> ResourceResponse:
        """Get resource by ID"""
        if resource_id not in self._resources:
            raise ValueError(f"Resource not found: {resource_id}")
        return self._resources[resource_id]

    async def update_resource(self, resource_id: str, request: ResourceRequest) -> None:
        """Update existing resource"""
        if resource_id not in self._resources:
            raise ValueError(f"Resource not found: {resource_id}")

        existing = self._resources[resource_id]
        existing.name = request.name
        existing.value = request.value
        existing.metadata = request.metadata
        existing.updatedAt = int(time.time() * 1000)

    async def delete_resource(self, resource_id: str) -> None:
        """Delete resource"""
        if resource_id not in self._resources:
            raise ValueError(f"Resource not found: {resource_id}")
        del self._resources[resource_id]
```

**Real-world example (broker module)**:

- Location: `backend/src/trading_api/modules/broker/service.py`
- In-memory maps: `_orders`, `_positions`, `_executions`
- Async processing: `_simulate_execution()` with delay
- Business logic: `_update_position()` from executions
- Module: `modules/broker/` (api.py, service.py, ws.py, tests/)

---

### Step 4.2: Wire Service to API Endpoints

**Location Pattern**: `backend/src/trading_api/modules/{module}/api.py`

**Note**: In modular architecture, the service is accessed via the module instance, not as a global singleton.

Replace `NotImplementedError` stubs with actual service calls:

```python
# Import service from module-local service.py
from .service import {ServiceName}Service

# Service instance is passed from module __init__.py
# Module creates and manages service lifecycle

class {Module}Api:
    def __init__(self, service: {ServiceName}Service, prefix: str = "/{module}", tags: list[str] | None = None):
        self.service = service
        self.router = APIRouter(prefix=prefix, tags=tags or ["{module}"])
        self._register_routes()

    def _register_routes(self):
        @self.router.post("/resources", response_model=ResourceOperationResult)
        async def createResource(resource: ResourceRequest) -> ResourceOperationResult:
            """Create a new resource"""
            return await self.service.create_resource(resource)  # 👈 Use injected service

@router.post("/resources", response_model=ResourceOperationResult)
async def createResource(resource: ResourceRequest) -> ResourceOperationResult:
    """Create a new resource"""
    return await service_instance.create_resource(resource)  # 👈 Real implementation

@router.get("/resources", response_model=List[ResourceResponse])
async def getResources(status: Optional[int] = None) -> List[ResourceResponse]:
    """Get all resources"""
    return await service_instance.get_resources(status)  # 👈 Real implementation

# ... wire all other endpoints
```

---

## Phase 5: Verify Frontend Tests Pass then Write Backend Tests (TDD Green Phase) ✅

**Goal**: Verify that frontend tests now pass with the implemented backend logic.

### Step 5.1: Run Frontend Tests with Backend Implementation

After implementing the backend logic (Phase 4), run frontend tests with backend client:

**Verification (TDD Green Phase)** 🟢:

```bash
# Terminal 1: Start backend with implementation
cd backend
make dev

# Terminal 2: Run frontend tests with backend client
cd frontend
VITE_USE_MOCK_{SERVICE}=false make test

# Expected output:
# ✅ All tests should now PASS
# ✅ should create resource successfully
# ✅ should get resources list
# ✅ should update resource
# ✅ should delete resource
# ✅ should handle errors correctly
```

**Success Criteria**:

1. ✅ All frontend tests pass with mock=false (backend client)
2. ✅ Frontend tests still pass with fallback client (without flag)
3. ✅ Backend tests pass (`cd backend && make test`)
4. ✅ No type errors (`npm run type-check`)
5. ✅ No lint errors (`make lint`)

### Step 5.2: Write Backend Unit Tests

**Location Pattern**: `backend/src/trading_api/modules/{module}/tests/test_service.py`

**Note**: Tests are co-located with modules. Each module has its own `tests/` directory.

**Test Pattern**:

```python
import pytest
from trading_api.modules.{module}.service import {ServiceName}Service
from trading_api.models.{domain} import ResourceRequest, ResourceStatus

@pytest.fixture
async def service():
    """Fixture to create fresh service instance"""
    return {ServiceName}Service()

@pytest.mark.asyncio
async def test_create_resource(service):
    """Test resource creation"""
    request = ResourceRequest(
        name="Test Resource",
        type="STANDARD",
        value=100.0,
        metadata={"key": "value"}
    )

    result = await service.create_resource(request)

    assert result.success
    assert result.id.startswith("RESOURCE-")

@pytest.mark.asyncio
async def test_get_resources(service):
    """Test getting resources list"""
    # Create test data
    request = ResourceRequest(name="Test", type="STANDARD", value=100.0)
    await service.create_resource(request)

    resources = await service.get_resources()

    assert len(resources) > 0
    assert resources[0].status == ResourceStatus.ACTIVE

@pytest.mark.asyncio
async def test_update_resource(service):
    """Test resource update"""
    # Create resource
    request = ResourceRequest(name="Original", type="STANDARD", value=100.0)
    result = await service.create_resource(request)

    # Update it
    update_request = ResourceRequest(name="Updated", type="STANDARD", value=200.0)
    await service.update_resource(result.id, update_request)

    # Verify
    resource = await service.get_resource(result.id)
    assert resource.name == "Updated"
    assert resource.value == 200.0

@pytest.mark.asyncio
async def test_delete_resource(service):
    """Test resource deletion"""
    # Create resource
    request = ResourceRequest(name="Test", type="STANDARD", value=100.0)
    result = await service.create_resource(request)

    # Delete it
    await service.delete_resource(result.id)

    # Verify it's gone
    with pytest.raises(ValueError, match="Resource not found"):
        await service.get_resource(result.id)
```

**Real-world example (broker module tests)**:

- File: `backend/src/trading_api/modules/broker/tests/test_api.py`
- Tests cover: place_order, get_orders, get_positions, get_executions, modify_order, cancel_order
- Uses factory-based fixtures with isolated module loading: `create_app(enabled_modules=["broker"])`
- Fixtures defined in: `modules/broker/tests/conftest.py` (module-specific) and `shared/tests/conftest.py` (shared factory)

**Verification**:

```bash
cd backend
make test  # All backend tests should pass
```

---

### Step 5.3: Write Backend API Integration Tests

**Location Pattern**: `backend/src/trading_api/modules/{module}/tests/test_api.py`

**Note**: Module tests use factory-based fixtures with isolated module loading.

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_resource_endpoint(async_client):
    # async_client fixture from conftest.py creates app with only this module
    # Uses: create_app(enabled_modules=["{module}"])
        response = await client.post("/api/v1/{service}/resources", json={
            "name": "Test Resource",
            "type": "STANDARD",
            "value": 100.0,
            "metadata": {"key": "value"}
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["id"].startswith("RESOURCE-")

@pytest.mark.asyncio
async def test_get_resources_endpoint():
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        # First create a resource
        await client.post("/api/v1/{service}/resources", json={
            "name": "Test",
            "type": "STANDARD",
            "value": 100.0
        })

        # Then get resources
        response = await client.get("/api/v1/{service}/resources")
        assert response.status_code == 200
        resources = response.json()
        assert len(resources) >= 1
```

**Verification**:

```bash
cd backend
make test  # All tests pass including new service tests
```

---

## Phase 6: Full Stack Validation (TDD Refactor Phase) ✅

**Goal**: Validate the complete implementation across all layers and test modes.

### Step 6.1: Manual Full Stack Testing

**Manual validation patterns** (adjust to your service features):

**With Backend Implementation**:

1. Start backend: `cd backend && make dev`
2. Start frontend: `cd frontend && VITE_USE_MOCK_{SERVICE}=false make dev`
3. Open browser: `http://localhost:5173`
4. Exercise core service features:
   - Create resources (check IDs, status, values)
   - Update resources (verify changes persist)
   - Delete resources (confirm removal)
   - List/filter resources (check results)
   - Error scenarios (invalid IDs, bad data)
5. Monitor backend logs for API calls
6. Check browser DevTools network tab

**With Fallback Client**:

1. Start frontend only: `cd frontend && make dev`
2. Open browser: `http://localhost:5173`
3. Exercise same features as above
4. Verify fallback client simulates expected behavior
5. No backend errors (since no backend running)

---

### Step 6.2: Smoke Tests

**Smoke test pattern**: `smoke-tests/tests/{service_name}.spec.ts`

```typescript
import { test, expect } from "@playwright/test";

test("service features end-to-end", async ({ page }) => {
  // Navigate to service UI
  await page.goto("http://localhost:5173");

  // Test resource creation
  await page.click('[data-testid="create-resource-btn"]');
  await page.fill('[data-testid="resource-name"]', "Test Resource");
  await page.click('[data-testid="submit-btn"]');

  // Verify creation success
  await expect(page.locator('[data-testid="resource-list"]')).toContainText(
    "Test Resource"
  );

  // Test resource update
  await page.click('[data-testid="edit-resource-btn"]');
  await page.fill('[data-testid="resource-name"]', "Updated Resource");
  await page.click('[data-testid="submit-btn"]');

  // Verify update
  await expect(page.locator('[data-testid="resource-list"]')).toContainText(
    "Updated Resource"
  );

  // Test resource deletion
  await page.click('[data-testid="delete-resource-btn"]');
  await page.click('[data-testid="confirm-btn"]');

  // Verify deletion
  await expect(page.locator('[data-testid="resource-list"]')).not.toContainText(
    "Updated Resource"
  );
});
```

**Run smoke tests**:

```bash
# With backend
cd backend && make dev  # Terminal 1
cd frontend && VITE_USE_MOCK_{SERVICE}=false make dev  # Terminal 2
cd smoke-tests && npm test  # Terminal 3

# With fallback
cd frontend && make dev  # Terminal 1
cd smoke-tests && npm test  # Terminal 2
```

**Real-world example (broker smoke tests)**:

- File: `smoke-tests/tests/broker.spec.ts`
- Tests: place order, modify order, cancel order, view positions
- Uses Playwright with TradingView Trading Terminal UI

### Step 6.3: Success Criteria

✅ **All must pass**:

1. **Frontend tests**: `cd frontend && make test` (both with/without backend)
2. **Backend tests**: `cd backend && make test`
3. **Type checks**: `cd frontend && npm run type-check`
4. **Linters**: `make lint` (root), `cd frontend && make lint`, `cd backend && make lint`
5. **Smoke tests**: `cd smoke-tests && npm test` (both modes)
6. **Manual testing**: Core features work as expected
7. **Documentation**: README files updated with new features

---

## Implementation Checklist

Use this checklist to track implementation progress for any service:

| Phase     | Step                         | Location Pattern                                               | Verification          | Status |
| --------- | ---------------------------- | -------------------------------------------------------------- | --------------------- | ------ |
| **1.1**   | Consolidate in service       | `frontend/src/services/{serviceName}Service.ts`                | `make test`           | ⏳     |
| **2.1**   | Backend models               | `backend/src/{api_name}/models/{service_name}/`                | `make lint`           | ⏳     |
| **2.2**   | API stubs                    | `backend/src/{api_name}/api/{service_name}.py`                 | `make dev`            | ⏳     |
| **2.3**   | Register router              | `backend/src/{api_name}/main.py`                               | Backend starts        | ⏳     |
| **2.4.1** | Generate OpenAPI client      | Auto-generated                                                 | Generation success    | ⏳     |
| **2.4.2** | Add to adapter               | `frontend/src/plugins/apiAdapter.ts` (consolidated)            | `npm run type-check`  | ⏳     |
| **3.1**   | Adjust for ApiPromise types  | `frontend/src/services/{serviceName}Service.ts`                | Type check passes     | ⏳     |
| **3.2**   | Wire backend client          | `frontend/src/services/{serviceName}Service.ts`                | `make test`           | ⏳     |
| **3.3**   | Run tests (Red phase) 🔴     | `frontend/src/services/__tests__/{serviceName}Service.test.ts` | Tests FAIL (expected) | ⏳     |
| **4.1**   | Service layer                | `backend/src/{api_name}/core/{service_name}_service.py`        | N/A                   | ⏳     |
| **4.2**   | Wire endpoints               | `backend/src/{api_name}/api/{service_name}.py`                 | N/A                   | ⏳     |
| **4.3**   | Backend unit tests           | `backend/tests/test_{service_name}_service.py`                 | `make test`           | ⏳     |
| **4.4**   | Backend API tests            | `backend/tests/test_api_{service_name}.py`                     | `make test`           | ⏳     |
| **5.1**   | Verify tests pass (Green) 🟢 | Frontend + Backend tests                                       | All tests pass        | ⏳     |
| **6.1**   | E2E manual testing           | Browser testing                                                | Visual verification   | ⏳     |
| **6.2**   | Smoke tests                  | `smoke-tests/tests/{service_name}.spec.ts`                     | `npm test`            | ⏳     |

**Status Legend**:

- ⏳ = Not started / In Progress
- ✅ = Completed
- ❌ = Blocked / Failed

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
9. ✅ **Consolidated Architecture**: Single `ApiAdapter` class handles multiple service operations
10. ✅ **Maintainable**: All backend API conversions centralized in one file
11. ✅ **Reusable**: Generic patterns applicable to any service implementation

---

## Generic Placeholder Reference

When implementing a new service, replace these placeholders:

| Placeholder       | Example (Broker)    | Description                             |
| ----------------- | ------------------- | --------------------------------------- |
| `{module}`        | `broker`            | Lowercase module name                   |
| `{Module}`        | `Broker`            | PascalCase module name                  |
| `{service_name}`  | `broker`            | Lowercase service name (same as module) |
| `{serviceName}`   | `brokerTerminal`    | camelCase service name (frontend)       |
| `{ServiceName}`   | `BrokerService`     | PascalCase service class name           |
| `{SERVICE}`       | `BROKER`            | Uppercase for env vars                  |
| `{domain}`        | `broker`, `market`  | Business domain for models folder       |
| `{resource}`      | `order`, `position` | Generic resource type                   |
| `{Resource}`      | `Order`, `Position` | PascalCase resource type                |
| `ExternalLibrary` | `TradingView`       | Third-party library/framework name      |

---

## Notes

- Each phase completion should be committed to git
- All tests must pass before moving to next phase
- Interface mismatches trigger adjustment loop in Phase 2.4
- Frontend always works (via fallback client) throughout implementation
- Type casting rule: Only use `as unknown as` for literal/alias/enum fields, never entire objects
- Service methods should be consolidated in `ApiAdapter` class for consistency
- This methodology is generic and can be applied to any backend service implementation

---

**Document Version**: 3.0 (Generic Template - Modular Architecture)  
**Last Updated**: November 11, 2025  
**Original Implementation**: Broker Terminal Service  
**Migration**: Updated for modular backend architecture with factory pattern
