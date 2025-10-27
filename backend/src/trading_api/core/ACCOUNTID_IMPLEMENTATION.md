# Account ID Implementation - Decision Documentation

**Status**: Design Complete  
**Last Updated**: October 27, 2025  
**Related Files**:

- `backend/src/trading_api/core/broker_service.py`
- `backend/src/trading_api/plugins/fastws_adapter.py`
- `backend/src/trading_api/main.py`
- `frontend/src/clients/wsClientBase.ts`
- `frontend/src/services/apiAdapter.ts`

---

## Executive Summary

Account ID implementation follows a **connection-scoped** approach for both REST API and WebSocket communications:

- **REST API**: `X-Account-Id` HTTP header (per request)
- **WebSocket**: `accountId` query parameter (per connection) via FastWS `auth_handler`
- **Backend Service**: Multi-account `BrokerAccount` architecture
- **Frontend**: Account ID configured at client initialization, reconnection required for switching

---

## Architecture Decisions

### 1. REST API: Header-Based Approach ✅

**Decision**: Use `X-Account-Id` HTTP header for all broker API requests

**Rationale**:

- ✅ Clean API signatures (no parameter pollution)
- ✅ Consistent across all endpoints
- ✅ Easy middleware/dependency injection
- ✅ Follows RESTful best practices for cross-cutting concerns
- ✅ Frontend sets once in API client config

**Implementation**:

```python
# Backend: FastAPI dependency
async def get_account_id(
    x_account_id: str = Header(..., alias="X-Account-Id")
) -> str:
    if not x_account_id:
        raise HTTPException(status_code=400, detail="X-Account-Id header required")
    return x_account_id

# Apply to all broker endpoints
@router.post("/orders")
async def placeOrder(
    order: PreOrder,
    account_id: str = Depends(get_account_id)
) -> PlaceOrderResult:
    return await service.place_order(order, account_id)
```

```typescript
// Frontend: API client with session-based header injection
export class ApiAdapter {
  private rawApi: V1Api;
  private apiConfig: Configuration;
  private sessionId: string | null;

  private static readonly SESSION_ID_KEY = "trader_session_id";

  constructor() {
    // Auto-discover sessionId from sessionStorage
    this.sessionId = this.readSessionId();

    // Create configuration with session-based headers
    this.apiConfig = this.createConfiguration();
    this.rawApi = new V1Api(this.apiConfig);
  }

  private readSessionId(): string | null {
    try {
      return sessionStorage.getItem(ApiAdapter.SESSION_ID_KEY);
    } catch (error) {
      console.warn("[ApiAdapter] Unable to read sessionId:", error);
      return null;
    }
  }

  private createConfiguration(): Configuration {
    const headers: Record<string, string> = {};

    // Map sessionId → X-Account-Id header
    if (this.sessionId) {
      headers["X-Account-Id"] = this.sessionId;
    }

    return new Configuration({
      basePath: import.meta.env.TRADER_API_BASE_PATH || "",
      headers,
    });
  }

  setSessionId(sessionId: string | null): void {
    if (sessionId !== this.sessionId) {
      if (sessionId) {
        sessionStorage.setItem(ApiAdapter.SESSION_ID_KEY, sessionId);
      } else {
        sessionStorage.removeItem(ApiAdapter.SESSION_ID_KEY);
      }

      this.sessionId = sessionId;
      this.apiConfig = this.createConfiguration();
      this.rawApi = new V1Api(this.apiConfig);
    }
  }

  getSessionId(): string | null {
    return this.sessionId;
  }
}
```

**Frontend Terminology**: Uses `sessionId` (user-facing) mapped to `X-Account-Id` header (backend contract)

**Session Storage**:

- Key: `trader_session_id`
- Location: `sessionStorage` (cleared on tab close, more secure than localStorage)
- Auto-discovery: ApiAdapter reads sessionId on initialization
- Dynamic updates: `setSessionId()` recreates client with new headers

**Affected Endpoints** (15+ broker operations):

- Order operations: place, preview, modify, cancel, getOrders
- Position operations: getPositions, closePosition, editPositionBrackets
- Execution operations: getExecutions
- Leverage operations: leverageInfo, setLeverage, previewLeverage
- Account operations: getAccountInfo

---

### 2. WebSocket: FastWS Auth Handler with Query Parameters ✅

**Decision**: Use FastWS `auth_handler` to extract `accountId` from query parameters and store in WebSocket state

**Rationale**:

- ✅ Consistent with REST API (account set upfront at connection time)
- ✅ Native FastWS authentication pattern
- ✅ No endpoint signature changes required
- ✅ Account context available throughout connection lifecycle
- ✅ Clean separation of concerns (auth vs routing)
- ✅ Easy to extend for stricter validation

**Implementation**:

```python
# backend/src/trading_api/plugins/fastws_adapter.py
async def ws_auth_handler(ws: WebSocket) -> bool:
    """
    FastWS authentication handler for account context extraction.

    Extracts accountId from query parameters and stores in WebSocket state.
    """
    await ws.accept()

    # Extract from query parameters
    account_id = ws.query_params.get("accountId")

    if not account_id:
        account_id = "DEMO-ACCOUNT"  # Default for backward compatibility
        logger.warning(f"No accountId provided, using default: {account_id}")

    # Store in WebSocket state
    ws.state.account_id = account_id

    logger.info(f"WebSocket authenticated for account: {account_id}")

    return True  # Accept connection

# backend/src/trading_api/main.py
from trading_api.plugins.fastws_adapter import ws_auth_handler

wsApp = FastWSAdapter(
    # ... other params
    auth_handler=ws_auth_handler,
    auto_ws_accept=False,  # Let auth handler control acceptance
)
```

```typescript
// Frontend: WebSocket connection with account ID
export class WebSocketBase {
  private getWebSocketUrl(): string {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const baseUrl = `${wsProtocol}//${window.location.host}`;
    return `${baseUrl}/api/v1/ws?accountId=${encodeURIComponent(
      this.accountId
    )}`;
  }

  setAccountId(accountId: string): void {
    this.accountId = accountId;
    this.reconnect(); // Reconnect with new account
  }
}
```

**Validation Strategy**: Hybrid (connection-level + optional subscription-level)

- Connection account stored in `ws.state.account_id`
- Subscription `accountId` validated against connection account
- Subscription `accountId` can be omitted (uses connection default)
- Strict mode: Reject mismatched subscription `accountId`

---

### 3. Backend Service: Multi-Account Architecture ✅

**Decision**: Refactor `BrokerService` to use internal `BrokerAccount` class for account isolation

**Current State**:

```python
class BrokerService:
    def __init__(self):
        self._orders: Dict[str, PlacedOrder] = {}
        self._positions: Dict[str, Position] = {}
        self._account_id = "DEMO-ACCOUNT"  # Single account
```

**Target Architecture**:

```python
class BrokerAccount:
    """Internal business class for account-scoped state"""
    def __init__(self, account_id: str):
        self._account_id = account_id
        self._orders: Dict[str, PlacedOrder] = {}
        self._positions: Dict[str, Position] = {}
        self._executions: List[Execution] = []
        self._equity: EquityData = EquityData(...)
        # ... all business state

class BrokerService(WsRouteService):
    def __init__(self):
        self._accounts: Dict[str, BrokerAccount] = {}

    def _get_or_create_account(self, account_id: str) -> BrokerAccount:
        if account_id not in self._accounts:
            self._accounts[account_id] = BrokerAccount(account_id)
        return self._accounts[account_id]

    async def place_order(self, order: PreOrder, account_id: str):
        account = self._get_or_create_account(account_id)
        # Use account._orders, account._positions, etc.
```

**Execution Simulator Changes**:

- Per-account execution simulator tasks
- Topic format: `"orders:{account_id}:{params}"`
- Callback registry includes account context

---

### 4. Subscription Models: Keep Required for Now ✅

**Decision**: Keep `accountId` required in WebSocket subscription models (backward compatible)

**Current Models** (all have required `accountId`):

- `OrderSubscriptionRequest`
- `PositionSubscriptionRequest`
- `ExecutionSubscriptionRequest`
- `EquitySubscriptionRequest`
- `BrokerConnectionSubscriptionRequest`

**Future Option** (Phase 3): Make `accountId` optional

```python
class OrderSubscriptionRequest(BaseModel):
    accountId: Optional[str] = Field(
        None,
        description="Account ID (defaults to connection account)"
    )
```

---

## Implementation Phases

### Phase 1: WebSocket Connection-Level Account (Current) ✅

**Status**: Design Complete, Ready for Implementation

**Backend Tasks**:

1. ✅ Create `ws_auth_handler` in `fastws_adapter.py`
2. ✅ Update `main.py` to use `auth_handler` and `auto_ws_accept=False`
3. Update WebSocket endpoint docstring to document query parameter
4. Update router handlers to extract account from `client.ws.state.account_id`

**Frontend Tasks**:

1. Update `WebSocketBase.getWebSocketUrl()` to include `accountId` query parameter
2. Add `setAccountId()` method for account switching (triggers reconnection)
3. Update service initialization to pass account ID

**Testing**:

- Backend: Test WebSocket connection with/without `accountId` query param
- Frontend: Test account ID in connection URL
- Integration: Verify account context propagation

---

### Phase 2: REST API Header-Based Account (Future)

**Status**: Documented, Not Yet Implemented

**Backend Tasks**:

1. Create `backend/src/trading_api/dependencies.py` with `get_account_id()`
2. Add `account_id: str = Depends(get_account_id)` to all 15+ broker endpoints
3. Update `BrokerService` methods to accept `account_id` parameter
4. Refactor to `BrokerAccount` multi-account architecture
5. Regenerate OpenAPI spec

**Frontend Tasks**:

1. Update `ApiAdapter` to configure `X-Account-Id` header
2. Add `setAccountId()` method (recreates API client)
3. Regenerate TypeScript client

**Testing**:

- Backend: Add `X-Account-Id` header to all broker API tests
- Frontend: Mock account ID in API client tests
- E2E: Verify header propagation

---

### Phase 3: Subscription accountId Optional (Future)

**Status**: Optional Enhancement

**Backend Tasks**:

1. Make `accountId` optional in all subscription request models
2. Default to connection account if subscription `accountId` omitted
3. Regenerate AsyncAPI spec

**Frontend Tasks**:

1. Update `ApiAdapter` to auto-read `sessionId` from `sessionStorage`
2. Add `setSessionId()` method to update session and recreate client
3. Map `sessionId` → `X-Account-Id` header in Configuration
4. Add `getSessionId()` method for session retrieval
5. Regenerate TypeScript client (if models change)

**Testing**:

- Backend: Add `X-Account-Id` header to all broker API tests
- Frontend: Mock `sessionStorage` in API client tests
- Frontend: Test auto-discovery of sessionId on ApiAdapter init
- Frontend: Test setSessionId() recreates client with new headers
- E2E: Verify header propagation from sessionStorage → API

---

### Phase 4: Multi-Account BrokerService Refactor (Future)

**Status**: Architecture Defined

**Tasks**:

1. Extract `BrokerAccount` internal class
2. Refactor all service methods to accept `account_id`
3. Per-account execution simulator tasks
4. Update topic format to include account ID
5. Comprehensive testing of account isolation

---

## Key Design Principles

### 1. Account Scope

- **REST**: Request-scoped (header per request)
- **WebSocket**: Connection-scoped (query parameter at connection time)
- **Frontend Session**: Browser sessionStorage-scoped (cleared on tab close)

### 2. Account Switching

- **REST**: Immediate (new header value per request)
- **WebSocket**: Requires reconnection (new connection with different `accountId`)

### 3. Multi-Account Support

- **Primary Use Case**: Single account per user session
- **Advanced Use Case**: Multiple accounts via separate connections (demo + live)
- **Not Supported**: Multiple accounts in single WebSocket connection (for simplicity)

### 4. Backward Compatibility

- **Development**: `DEMO-ACCOUNT` default (optional `accountId`)
- **Production**: Account ID required (strict validation)
- **Migration**: Gradual rollout with defaults, then enforce

### 5. TradingView Integration

- TradingView's broker API doesn't explicitly define account context
- `currentAccount()` method returns active account ID
- Account switching requires creating new broker service instance
- Our pattern: Account ID passed at service initialization time

### 6. Frontend Terminology Mapping

## Comparison: REST vs WebSocket vs Frontend

| Aspect            | REST API               | WebSocket (FastWS)               | Frontend Session                 |
| ----------------- | ---------------------- | -------------------------------- | -------------------------------- |
| **Transport**     | `X-Account-Id` header  | Query parameter `?accountId=...` | `sessionStorage` key             |
| **Terminology**   | `accountId`            | `accountId`                      | `sessionId`                      |
| **Storage Key**   | N/A                    | N/A                              | `trader_session_id`              |
| **Scope**         | Per request            | Per connection                   | Per browser tab                  |
| **Validation**    | FastAPI dependency     | FastWS `auth_handler`            | sessionStorage.getItem()         |
| **Switching**     | New header per request | Reconnect required               | setSessionId() + recreate client |
| **State Storage** | Request context        | `websocket.state.account_id`     | `sessionStorage`                 |
| **Multi-Account** | N/A (stateless)        | Optional subscription override   | One session per tab              |
| **Default**       | Required (400 error)   | `DEMO-ACCOUNT` (backward compat) | `null` (no session)              |
| **Pattern**       | Middleware/dependency  | Connection authentication        | Auto-discovery on init           |
| **Persistence**   | None                   | Connection lifetime              | Tab lifetime (cleared on close)  |

| Aspect                | REST API               | WebSocket (FastWS)               |
| --------------------- | ---------------------- | -------------------------------- |
| **Account Transport** | `X-Account-Id` header  | Query parameter `?accountId=...` |
| **Scope**             | Per request            | Per connection                   |
| **Validation**        | FastAPI dependency     | FastWS `auth_handler`            |
| **Switching**         | New header per request | Reconnect required               |
| **State Storage**     | Request context        | `websocket.state.account_id`     |
| **Multi-Account**     | N/A (stateless)        | Optional subscription override   |
| **Default**           | Required (400 error)   | `DEMO-ACCOUNT` (backward compat) |
| **Pattern**           | Middleware/dependency  | Connection authentication        |

---

## File Impact Summary

### Backend Files (~300 lines)

| File                    | Change                         | Lines | Phase   |
| ----------------------- | ------------------------------ | ----- | ------- |
| `fastws_adapter.py`     | Add `ws_auth_handler` function | ~50   | Phase 1 |
| `main.py`               | Configure auth handler         | ~5    | Phase 1 |
| `dependencies.py` (new) | Create header dependency       | ~15   | Phase 2 |

## Testing Strategy

### Unit Tests

- Backend: WebSocket auth handler with various query param scenarios
- Backend: REST dependency with valid/missing/invalid headers
- Frontend: sessionStorage read/write operations
- Frontend: sessionId → X-Account-Id header mapping
- Frontend: Session switching logic (setSessionId)
- Frontend: ApiAdapter initialization with/without sessionId------------------------------------- | ----- | ------- |
  | `wsClientBase.ts` | Query param + reconnect logic | ~10 | Phase 1 |
  | `apiAdapter.ts` | Session-based header injection | ~50 | Phase 2 |
  | `services/__tests__/*.spec.ts` | Update test setup (mock sessionStorage) | ~10 | Phase 2 |

---

## Testing Strategy

### Unit Tests

- Backend: WebSocket auth handler with various query param scenarios
- Backend: REST dependency with valid/missing/invalid headers
- Frontend: URL construction with account ID
- Frontend: Account switching logic

### Integration Tests

- WebSocket connection with account context
- REST API calls with account header
- Account ID propagation through service layers

### E2E Tests

- Full broker workflow with account ID
- Account switching scenarios
- Multi-account isolation

---

## Future Enhancements

### 1. Strict Account Validation

```python
async def ws_auth_handler(ws: WebSocket) -> bool:
    account_id = ws.query_params.get("accountId")

    # Validate against allowed accounts
    if account_id not in ALLOWED_ACCOUNTS:
        logger.error(f"Invalid account: {account_id}")
        return False  # Reject connection

    ws.state.account_id = account_id
    return True
```

### 2. JWT Token-Based Authentication

````python
async def ws_auth_handler(ws: WebSocket) -> bool:
    token = ws.query_params.get("token")

### 4. Account-Specific Configuration

- Per-account leverage settings
- Per-account risk limits
- Per-account execution rules

### 5. Session Management Enhancements

**Session Lifecycle**:
```typescript
// Login flow
async login(credentials) {
  const { session_id } = await authService.login(credentials)
  apiAdapter.setSessionId(session_id)  // Auto-sets X-Account-Id header
}

// Logout flow
logout() {
  apiAdapter.setSessionId(null)  // Clears session
}
````

**Cross-Tab Session Sync**:

```typescript
// Listen for sessionStorage changes across tabs
window.addEventListener("storage", (event) => {
  if (event.key === "trader_session_id") {
    apiAdapter.setSessionId(event.newValue);
  }
});
```

**Session Validation**:

````typescript
// Before each request, verify session exists
private createConfiguration(): Configuration {
  if (!this.sessionId) {
    console.warn('[ApiAdapter] No session - requests may fail')
  }
  // ... rest of config
}
``` account_id
        return True
    except JWTError:
        return False
````

### 3. Account Manager UI Integration

- Integrate with TradingView's account switching UI
- Support multiple accounts in `accountsMetainfo()`
- Dynamic account switching without page reload

### 4. Account-Specific Configuration

**Decision Log**:

- 2025-10-27: Chose FastWS `auth_handler` over query parameter dependency
- 2025-10-27: Decided on connection-scoped WebSocket account (vs subscription-scoped)
- 2025-10-27: Chose header-based REST API approach (vs query parameter)
- 2025-10-27: Planned multi-account `BrokerAccount` architecture
- 2025-10-27: Chose session-based header injection (auto-read from sessionStorage)
- 2025-10-27: Frontend uses `sessionId` terminology, mapped to `X-Account-Id` backend header
- 2025-10-27: Use `sessionStorage` (tab-scoped) instead of `localStorage` (persistent)

## References

- **FastWS Documentation**: `backend/external_packages/fastws/README.md`
- **Broker Architecture**: `docs/BROKER-ARCHITECTURE.md`
- **WebSocket Methodology**: `WEBSOCKET-METHODOLOGY.md`
- **API Methodology**: `API-METHODOLOGY.md`
- **TradingView Broker API**: `frontend/IBROKERCONNECTIONADAPTERHOST.md`

---

**Decision Log**:

- 2025-10-27: Chose FastWS `auth_handler` over query parameter dependency
- 2025-10-27: Decided on connection-scoped WebSocket account (vs subscription-scoped)
- 2025-10-27: Chose header-based REST API approach (vs query parameter)
- 2025-10-27: Planned multi-account `BrokerAccount` architecture

**Next Steps**:

1. Implement Phase 1: WebSocket connection-level account
2. Test account context propagation
3. Update documentation after implementation
4. Plan Phase 2: REST API header-based account
