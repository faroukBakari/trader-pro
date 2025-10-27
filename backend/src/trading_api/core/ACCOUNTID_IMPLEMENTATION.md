## BROKER SERVICE

the core atomic object for broker logic is the execution object.
execution simulation will update order status and generation an execution object
exectuion simulation will then trigger equity update \_update_equity
equity update will trigger a position update \_update_position
let's create a single loop scanning pending orders and triggering/simulating executions with a random periodicity between 1 and 2 seconds.
before doing all that, we need to extend broker service buisiness members by adding an accountid dimentionality.
let's create an internal buisness class called broker_account:

```python
class BrokerAccount(BaseModel):
    def __init__(self) -> None:
        self._orders: Dict[str, PlacedOrder] = {}
        self._positions: Dict[str, Position] = {}
        self._executions: List[Execution] = []
        self._order_counter = 1
        self._account_id = "DEMO-ACCOUNT"
        self._account_name = "Demo Trading Account"
        self._leverage_settings: Dict[str, float] = {}
        self.unrealizedPL: Dict[str, float] = {}
        self.initial_balance = 100000.0
        self._equity: EquityData = EquityData(
            equity=0.0,
            balance=100000.0,
            unrealizedPL=0.0,
            realizedPL=0.0,
        )
```

then create a single loop scanning pending orders and triggering/simulating executions with a random periodicity between 1 and 2 seconds.

## ACCOUNT ID

faroukBakari: we need to add some refactoring for all api and ws request objects to incorporate accountId in the request.
scan codebase and pipoint impacted source files and suggest implementation to add accountId data to all these requests. let's discuss the approach first. dont showcase all code but prefer using sample illustration along with exhaustive list to apply adaptation to

GitHub Copilot: I'll scan the codebase to identify all API and WebSocket request objects that need to incorporate `accountId`, then suggest an approach.

Read [](file:///home/farouk/trader-pro/docs/DOCUMENTATION-GUIDE.md)

Read [](file:///home/farouk/trader-pro/API-METHODOLOGY.md)

Read [](file:///home/farouk/trader-pro/WEBSOCKET-METHODOLOGY.md)

Now let me search for all request/response models and API/WebSocket endpoints to identify the scope:

Searched text for `class.*Request\(BaseModel\)|class.*Response\(BaseModel\)` (`**/backend/src/**/*.py`), 17 results

Searched text for `@router\.(get|post|put|delete|patch)` (`**/backend/src/**/*.py`), no results

Searched text for `WsRouter\[.*\]` (`**/backend/src/**/*.py`), 6 results

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/api)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/models/broker/orders.py)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/models/broker/positions.py)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/api/broker.py)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/api/datafeed.py)

Searched text for `class (Pre|Modify|Place|Get|Search|Close).*(BaseModel)` (`**/backend/src/trading_api/models/**/*.py`), 8 results

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/models/broker/account.py)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/models/broker/executions.py)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/models/broker/connection.py)

Now let me check the leverage models:

Searched text for `class Leverage.*\(BaseModel\)|class Brackets.*\(BaseModel\)` (`**/backend/src/trading_api/models/**/*.py`), 5 results

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/core/BROKER_SERVICE.md)

Read [](file:///home/farouk/trader-pro/backend/src/trading_api/models/broker/leverage.py)

Perfect! Now I have a comprehensive understanding. Let me create a summary and approach for adding `accountId` to all requests:

## Analysis Summary

Based on my scan of the codebase, here's what needs `accountId` integration:

### **Impacted Components**

#### **A. WebSocket Subscriptions (Already Have AccountId)** ✅

All WebSocket subscription requests **already include** `accountId`:

- `OrderSubscriptionRequest`
- `PositionSubscriptionRequest`
- `ExecutionSubscriptionRequest`
- `EquitySubscriptionRequest`
- `BrokerConnectionSubscriptionRequest`

#### **B. REST API Endpoints (Need AccountId)** ❌

**Broker API Operations** (broker.py):

1. **Order Operations:**

   - `POST /orders` → `placeOrder(PreOrder)`
   - `POST /orders/preview` → `previewOrder(PreOrder)`
   - `PUT /orders/{order_id}` → `modifyOrder(order_id, PreOrder)`
   - `DELETE /orders/{order_id}` → `cancelOrder(order_id)`
   - `GET /orders` → `getOrders()`

2. **Position Operations:**

   - `GET /positions` → `getPositions()`
   - `DELETE /positions/{position_id}` → `closePosition(position_id, amount?)`
   - `PUT /positions/{position_id}/brackets` → `editPositionBrackets(position_id, Brackets)`

3. **Execution Operations:**

   - `GET /executions/{symbol}` → `getExecutions(symbol)`

4. **Leverage Operations:**

   - `GET /leverage/info` → `leverageInfo(LeverageInfoParams)`
   - `PUT /leverage/set` → `setLeverage(LeverageSetParams)`
   - `POST /leverage/preview` → `previewLeverage(LeverageSetParams)`

5. **Account Operations:**
   - `GET /account` → `getAccountInfo()` _(may need accountId as query param)_

**Note:** Datafeed API operations are account-agnostic (market data), so they don't need `accountId`.

---

## **Proposed Approach**

### **Option 1: Header-Based (Recommended)** ✅

**Pros:**

- ✅ Clean API signatures (no parameter pollution)
- ✅ Consistent across all endpoints
- ✅ Easy to add middleware/dependency injection
- ✅ Follows RESTful best practices for cross-cutting concerns
- ✅ Frontend can set once in API client config

**Cons:**

- ⚠️ Requires header handling in frontend API client

**Implementation Pattern:**

```python
# Backend: Use FastAPI dependency injection
from fastapi import Header, HTTPException

async def get_account_id(
    x_account_id: str = Header(..., alias="X-Account-Id")
) -> str:
    """Extract and validate account ID from request header"""
    if not x_account_id:
        raise HTTPException(status_code=400, detail="X-Account-Id header required")
    return x_account_id

# Apply to endpoints
@self.post("/orders")
async def placeOrder(
    order: PreOrder,
    account_id: str = Depends(get_account_id)
) -> PlaceOrderResult:
    return await self.service.place_order(order, account_id)
```

```typescript
// Frontend: Configure API client with header
export class ApiAdapter {
  private rawApi: V1Api;
  private accountId: string = "DEMO-ACCOUNT"; // Default or from config

  constructor() {
    const apiConfig = new Configuration({
      basePath: import.meta.env.API_BASE_PATH || "",
      headers: {
        "X-Account-Id": this.accountId,
      },
    });
    this.rawApi = new V1Api(apiConfig);
  }

  setAccountId(accountId: string): void {
    this.accountId = accountId;
    // Recreate API client with new header
    const apiConfig = new Configuration({
      basePath: import.meta.env.API_BASE_PATH || "",
      headers: {
        "X-Account-Id": accountId,
      },
    });
    this.rawApi = new V1Api(apiConfig);
  }
}
```

---

### **Option 2: Query Parameter**

**Pros:**

- ✅ Visible in API docs
- ✅ Easy to test manually

**Cons:**

- ❌ Repetitive (every endpoint needs `account_id: str = Query(...)`)
- ❌ Pollutes endpoint signatures
- ❌ Not RESTful for write operations (POST/PUT/DELETE)

**Pattern:**

```python
@self.post("/orders")
async def placeOrder(
    order: PreOrder,
    account_id: str = Query(..., alias="accountId")
) -> PlaceOrderResult:
    return await self.service.place_order(order, account_id)
```

---

### **Option 3: Request Body Field**

**Pros:**

- ✅ Part of the model

**Cons:**

- ❌ Requires changing all request models (`PreOrder`, `Brackets`, `LeverageSetParams`)
- ❌ Pollutes business logic models with infrastructure concern
- ❌ Doesn't work for GET/DELETE endpoints

**Pattern:**

```python
class PreOrder(BaseModel):
    accountId: str = Field(..., description="Account ID")  # ❌ Pollutes business model
    symbol: str
    # ... rest of fields
```

---

## **Recommendation: Header-Based Approach (Option 1)**

### **Implementation Steps**

#### **Phase 1: Backend Changes**

1. **Create dependency for account ID extraction**

   - File: `backend/src/trading_api/dependencies.py` (new)
   - Extract `X-Account-Id` header with validation

2. **Update BrokerService methods**

   - Add `account_id: str` parameter to all methods
   - Use multi-account `BrokerAccount` architecture from BROKER_SERVICE.md

3. **Update API endpoints**

   - Add `account_id: str = Depends(get_account_id)` to all broker endpoints
   - Pass `account_id` to service methods

4. **Regenerate OpenAPI spec**
   - Restart backend to export updated `openapi.json`

#### **Phase 2: Frontend Changes**

1. **Update ApiAdapter**

   - Configure `X-Account-Id` header in OpenAPI client
   - Add `setAccountId()` method for dynamic account switching

2. **Update service adapters**

   - No changes needed (header handled at API client level)

3. **Regenerate TypeScript client**
   - Run `make generate-openapi-client`

#### **Phase 3: Testing**

1. **Backend tests**

   - Update all broker API tests to include `X-Account-Id` header

2. **Frontend tests**

   - Update tests to mock account ID in API client

3. **E2E tests**
   - Verify account ID propagation end-to-end

---

## **Detailed File Impact List**

### **Backend Files to Modify**

| File                                      | Change                                | Lines Estimate |
| ----------------------------------------- | ------------------------------------- | -------------- |
| `backend/src/trading_api/dependencies.py` | Create header dependency              | ~15            |
| broker_service.py                         | Add `account_id` param to all methods | ~200           |
| broker.py                                 | Add dependency to 15 endpoints        | ~30            |
| test_api_broker.py                        | Add header to test requests           | ~50            |

### **Frontend Files to Modify**

| File                                        | Change                             | Lines Estimate |
| ------------------------------------------- | ---------------------------------- | -------------- |
| apiAdapter.ts                               | Configure header, add setAccountId | ~20            |
| `frontend/src/services/__tests__/*.spec.ts` | Update test setup                  | ~10            |

---

## **Sample Implementation Illustration**

### **Backend Dependency**

```python
# backend/src/trading_api/dependencies.py
from fastapi import Header, HTTPException

async def get_account_id(
    x_account_id: str = Header(..., alias="X-Account-Id", description="Account identifier")
) -> str:
    """
    Extract account ID from request header.

    Raises:
        HTTPException: If header is missing or invalid
    """
    if not x_account_id or not x_account_id.strip():
        raise HTTPException(
            status_code=400,
            detail="X-Account-Id header is required"
        )
    return x_account_id.strip()
```

### **Backend API Endpoint Example**

```python
# Before
@self.post("/orders", response_model=PlaceOrderResult)
async def placeOrder(order: PreOrder) -> PlaceOrderResult:
    return await self.service.place_order(order)

# After
from fastapi import Depends
from trading_api.dependencies import get_account_id

@self.post("/orders", response_model=PlaceOrderResult)
async def placeOrder(
    order: PreOrder,
    account_id: str = Depends(get_account_id)
) -> PlaceOrderResult:
    return await self.service.place_order(order, account_id)
```

### **Backend Service Method Example**

```python
# Before
async def place_order(self, order: PreOrder) -> PlaceOrderResult:
    order_id = f"ORDER-{self._order_counter}"
    # ...

# After
async def place_order(self, order: PreOrder, account_id: str) -> PlaceOrderResult:
    account = self._get_or_create_account(account_id)
    order_id = f"ORDER-{account._order_counter}"
    # Use account._orders, account._positions, etc.
```

### **Frontend ApiAdapter**

```typescript
export class ApiAdapter {
  private rawApi: V1Api;
  private currentAccountId: string;

  constructor(accountId: string = "DEMO-ACCOUNT") {
    this.currentAccountId = accountId;
    this.rawApi = this.createApiClient(accountId);
  }

  private createApiClient(accountId: string): V1Api {
    return new V1Api(
      new Configuration({
        basePath: import.meta.env.API_BASE_PATH || "",
        headers: {
          "X-Account-Id": accountId,
        },
      })
    );
  }

  setAccountId(accountId: string): void {
    if (accountId !== this.currentAccountId) {
      this.currentAccountId = accountId;
      this.rawApi = this.createApiClient(accountId);
    }
  }

  getAccountId(): string {
    return this.currentAccountId;
  }
}
```

---

## **Discussion Questions**

1. **Header vs Query Parameter**: Do you prefer header-based (cleaner) or query parameter (more visible)?

2. **Default Account**: Should there be a default account ID if header is missing, or always require it?

3. **Multi-Account UI**: Will users switch between accounts in the UI, or is it a single-account setup?

4. **Backward Compatibility**: Do we need to support existing API calls without `accountId` during migration?

5. **WebSocket Consistency**: Since WebSocket subscriptions already use `accountId` in request body, should we keep that pattern or also move to connection-level metadata?

Let me know your preferences, and I'll proceed with the implementation!

faroukBakari: good choice! but how to handle account id accross websocket? suggest a solution that complements the api one

GitHub Copilot: Excellent question! Let's design a WebSocket account handling strategy that complements the REST API header-based approach.

## WebSocket AccountId Handling - Proposed Solution

### **Problem Analysis**

WebSocket differs from REST:

- **REST**: Stateless, header per request ✅
- **WebSocket**: Persistent connection, need account context for entire session

### **Current State**

- ✅ Subscription requests already have `accountId` field (orders, positions, executions, equity, connection)
- ❌ No account-level authentication/validation on connection
- ❌ Each subscription independently specifies `accountId` (redundant)

---

## **Recommended Approach: Hybrid Strategy**

### **Option 1: Connection-Level + Subscription-Level (Recommended)** ✅

**Design:**

1. **Connection Authentication**: Set account ID when establishing WebSocket connection
2. **Subscription Validation**: Verify subscription `accountId` matches connection account
3. **Fallback**: Allow subscription-level override for multi-account scenarios

**Benefits:**

- ✅ Consistent with REST API (account set upfront)
- ✅ Prevents cross-account data leaks
- ✅ Supports multi-account trading (advanced use case)
- ✅ Backward compatible (subscription `accountId` still works)

**Implementation Pattern:**

#### **A. Connection-Level Account (Primary)**

```python
# Backend: WebSocket connection with account context
from fastapi import WebSocket, Query

@wsApp.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    account_id: str = Query("DEMO-ACCOUNT", alias="accountId")  # Default for backward compat
):
    """
    WebSocket endpoint with account-level context

    Query parameter: ?accountId=DEMO-ACCOUNT
    """
    await websocket.accept()

    # Store account context in connection state
    websocket.state.account_id = account_id

    # Process messages with account context
    async for message in websocket.iter_json():
        await handle_message(websocket, message)
```

```typescript
// Frontend: Connect with account ID in query string
export class WebSocketBase {
  private accountId: string;

  constructor(accountId: string = "DEMO-ACCOUNT") {
    this.accountId = accountId;
  }

  private getWebSocketUrl(): string {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const baseUrl =
      import.meta.env.VITE_WS_BASE_URL ||
      `${wsProtocol}//${window.location.host}`;
    // Add accountId as query parameter
    return `${baseUrl}/api/v1/ws?accountId=${encodeURIComponent(
      this.accountId
    )}`;
  }

  setAccountId(accountId: string): void {
    if (accountId !== this.accountId) {
      this.accountId = accountId;
      this.reconnect(); // Reconnect with new account
    }
  }
}
```

#### **B. Subscription-Level Validation**

```python
# Backend: Validate subscription accountId matches connection
async def handle_subscription(websocket: WebSocket, message: dict):
    subscription_account = message.get("payload", {}).get("accountId")
    connection_account = websocket.state.account_id

    # Validation strategies:

    # Strategy 1: Strict (enforce match)
    if subscription_account and subscription_account != connection_account:
        await websocket.send_json({
            "type": f"{message['type']}.error",
            "payload": {
                "error": f"Account mismatch: subscription accountId '{subscription_account}' "
                        f"does not match connection accountId '{connection_account}'"
            }
        })
        return

    # Strategy 2: Flexible (allow override for multi-account)
    effective_account = subscription_account or connection_account

    # Use effective_account for routing
    await route_subscription(websocket, message, effective_account)
```

```typescript
// Frontend: Subscription without accountId (uses connection-level)
export class WebSocketClient<TRequest, TBackend, TFrontend> {
  subscribe(
    listenerGuid: string,
    params: Omit<TRequest, "accountId">, // ✅ Remove accountId requirement
    callback: (data: TFrontend) => void
  ): void {
    // accountId automatically inherited from connection
    this.ws.subscribe(this.topicType, params, listenerGuid, callback);
  }
}
```

---

### **Option 2: Subscription-Level Only (Current State)**

**Keep current implementation** where each subscription includes `accountId`.

**Pros:**

- ✅ Already implemented
- ✅ Explicit per subscription
- ✅ Supports multi-account in single connection

**Cons:**

- ❌ Redundant (repeat accountId for every subscription)
- ❌ Inconsistent with REST API pattern
- ❌ No connection-level security
- ❌ Easy to forget or misuse

---

### **Option 3: Connection-Level Only (Strictest)**

Remove `accountId` from subscription requests entirely.

**Pros:**

- ✅ Simplest API
- ✅ Most consistent with REST
- ✅ Impossible to mix accounts

**Cons:**

- ❌ Requires reconnection to switch accounts
- ❌ Breaking change to existing WebSocket models
- ❌ No multi-account support

---

## **Recommended Implementation: Option 1 (Hybrid)**

### **Step-by-Step Changes**

#### **Phase 1: Backend WebSocket Connection**

**File: main.py**

```python
# Current
@wsApp.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # ...

# Proposed
from fastapi import Query

@wsApp.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    account_id: str = Query("DEMO-ACCOUNT", alias="accountId", description="Account identifier")
):
    """
    WebSocket endpoint with account-level context

    Connection established with accountId in query string.
    Example: ws://localhost:8000/api/v1/ws?accountId=DEMO-ACCOUNT
    """
    await websocket.accept()

    # Store account context in connection state
    websocket.state.account_id = account_id

    # Log connection with account
    logger.info(f"WebSocket connected for account: {account_id}")

    # Existing message handling...
```

#### **Phase 2: Backend Service - Use Connection Account**

**File: router_interface.py** (or router implementation)

```python
# Add helper to extract account from websocket state
def get_websocket_account(websocket: WebSocket) -> str:
    """Get account ID from WebSocket connection state"""
    return getattr(websocket.state, 'account_id', 'DEMO-ACCOUNT')

# In router subscribe handler
async def subscribe(self, websocket: WebSocket, payload: dict):
    connection_account = get_websocket_account(websocket)
    subscription_account = payload.get("accountId")

    # Validation: subscription must match connection (or be omitted)
    if subscription_account and subscription_account != connection_account:
        await websocket.send_json({
            "type": f"{self.route}.subscribe.error",
            "payload": {
                "error": f"Account mismatch: {subscription_account} != {connection_account}"
            }
        })
        return

    # Use connection account as authoritative source
    effective_account = connection_account

    # Build topic with account ID
    topic = self._build_topic(payload, account_id=effective_account)
    # ...
```

#### **Phase 3: Frontend - Update WebSocketBase**

**File: wsClientBase.ts**

```typescript
export class WebSocketBase {
  private ws: WebSocket | null = null;
  private accountId: string;
  private reconnectAttempts = 0;

  constructor(accountId: string = "DEMO-ACCOUNT") {
    this.accountId = accountId;
  }

  private getWebSocketUrl(): string {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = import.meta.env.VITE_WS_HOST || window.location.host;
    const wsPath = import.meta.env.VITE_WS_PATH || "/api/v1/ws";

    // Include accountId in connection query string
    const url = `${wsProtocol}//${wsHost}${wsPath}?accountId=${encodeURIComponent(
      this.accountId
    )}`;

    console.log(`WebSocket connecting with accountId: ${this.accountId}`);
    return url;
  }

  /**
   * Change account and reconnect
   */
  setAccountId(accountId: string): void {
    if (accountId !== this.accountId) {
      console.log(`Switching account from ${this.accountId} to ${accountId}`);
      this.accountId = accountId;

      // Reconnect with new account
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.disconnect();
        this.connect();
      }
    }
  }

  getAccountId(): string {
    return this.accountId;
  }
}
```

#### **Phase 4: Frontend - Simplify Subscription Models (Optional)**

Make `accountId` optional in subscription requests since it's inherited from connection:

```typescript
// Before: accountId required
this.wsAdapter.orders.subscribe(
  "my-listener",
  { accountId: "DEMO-ACCOUNT" }, // ❌ Redundant
  (order) => console.log(order)
);

// After: accountId optional (uses connection-level)
this.wsAdapter.orders.subscribe(
  "my-listener",
  {}, // ✅ Account inherited from connection
  (order) => console.log(order)
);

// Advanced: Multi-account override (if needed)
this.wsAdapter.orders.subscribe(
  "my-listener",
  { accountId: "LIVE-ACCOUNT" }, // ✅ Explicit override
  (order) => console.log(order)
);
```

**TypeScript Type Update:**

```typescript
// Make accountId optional in subscription interfaces
export class WebSocketClient<
  TRequest extends { accountId?: string }, // ✅ Optional now
  TBackend,
  TFrontend
> {
  subscribe(
    listenerGuid: string,
    params: Omit<TRequest, "accountId"> & { accountId?: string }, // Optional override
    callback: (data: TFrontend) => void
  ): void {
    // Send subscription (accountId optional, uses connection default)
    this.ws.subscribe(this.topicType, params, listenerGuid, callback);
  }
}
```

---

## **Backend Model Changes (Optional - Make accountId Optional)**

```python
# Before: accountId required
class OrderSubscriptionRequest(BaseModel):
    accountId: str = Field(..., description="Account ID to subscribe to")

# After: accountId optional (uses connection-level if omitted)
class OrderSubscriptionRequest(BaseModel):
    accountId: Optional[str] = Field(
        None,
        description="Account ID to subscribe to (defaults to connection account)"
    )
```

**Apply to all subscription models:**

- `OrderSubscriptionRequest`
- `PositionSubscriptionRequest`
- `ExecutionSubscriptionRequest`
- `EquitySubscriptionRequest`
- `BrokerConnectionSubscriptionRequest`

---

## **Complete Integration Example**

### **Backend Topic Building with Account**

```python
class BrokerService(WsRouteService):
    def __init__(self):
        # Multi-account storage
        self._accounts: Dict[str, BrokerAccount] = {}

    def _get_or_create_account(self, account_id: str) -> BrokerAccount:
        if account_id not in self._accounts:
            self._accounts[account_id] = BrokerAccount(account_id)
        return self._accounts[account_id]

    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """
        Topic format: "orders:{account_id}:{json_params}"
        OR legacy: "orders:{json_params}" (uses DEMO-ACCOUNT)
        """
        if ":" not in topic:
            raise ValueError(f"Invalid topic format: {topic}")

        parts = topic.split(":", 2)
        topic_type = parts[0]

        # Parse account ID from topic
        if len(parts) == 3:
            # New format: "orders:DEMO-ACCOUNT:{...}"
            account_id = parts[1]
            params_json = parts[2]
        else:
            # Legacy format: "orders:{...}" (backward compat)
            account_id = "DEMO-ACCOUNT"
            params_json = parts[1]

        account = self._get_or_create_account(account_id)

        # Create topic-specific task with account context
        if topic_type == "orders":
            task = asyncio.create_task(
                self._order_generator(account, topic_update)
            )
            self._topic_generators[topic] = task
```

### **Frontend Usage**

```typescript
// App initialization with account
const accountId = "DEMO-ACCOUNT"; // From user session/config

// WebSocket connects with account
const wsAdapter = new WsAdapter(accountId);

// API client uses same account
const apiAdapter = new ApiAdapter(accountId);

// Service initialization
const brokerService = new BrokerTerminalService(
  tradingViewDeps,
  false, // use backend
  wsAdapter,
  apiAdapter
);

// Account switching (e.g., demo ↔ live)
function switchAccount(newAccountId: string) {
  wsAdapter.setAccountId(newAccountId); // Reconnects WebSocket
  apiAdapter.setAccountId(newAccountId); // Updates REST header
}
```

---

## **Summary Comparison**

| Aspect                | REST API               | WebSocket (Proposed)                 |
| --------------------- | ---------------------- | ------------------------------------ |
| **Account Transport** | `X-Account-Id` header  | Query parameter `?accountId=...`     |
| **Scope**             | Per request            | Per connection                       |
| **Switching**         | New header per request | Reconnect required                   |
| **Validation**        | Middleware/dependency  | Connection + subscription validation |
| **Multi-Account**     | N/A (stateless)        | Optional subscription override       |
| **Default**           | Required (400 error)   | `DEMO-ACCOUNT` (backward compat)     |

---

## **Migration Strategy**

### **Phase 1: Add Connection-Level (Non-Breaking)**

- Add `accountId` query param to WebSocket endpoint (default: "DEMO-ACCOUNT")
- Store in `websocket.state.account_id`
- Keep subscription `accountId` required (backward compatible)

### **Phase 2: Validation (Safety)**

- Validate subscription `accountId` matches connection
- Log warnings for mismatches (don't block yet)

### **Phase 3: Make Optional (Breaking - Coordinated)**

- Backend: Make subscription `accountId` optional
- Frontend: Remove `accountId` from subscription calls
- Regenerate AsyncAPI types

### **Phase 4: Enforce (Strictest)**

- Backend: Reject mismatched subscription `accountId`
- Remove default fallback (require explicit connection account)

---

## **Questions for You**

1. **Multi-Account Support**: Do you need to support multiple accounts in a single WebSocket connection (e.g., trade on demo + live simultaneously)?

   - If NO → Simplest: Connection-level only, remove from subscriptions
   - If YES → Hybrid approach with subscription override

2. **Backward Compatibility**: Should we maintain `DEMO-ACCOUNT` default during migration?

   - If YES → Gradual rollout (Phases 1-4)
   - If NO → Breaking change acceptable

3. **Account Switching UX**: How should account switching work?
   - Auto-reconnect WebSocket (slight delay)
   - Or maintain separate connections per account

Which approach do you prefer? I recommend **Option 1 (Hybrid)** with **Phase 1-2** as the first implementation step.
