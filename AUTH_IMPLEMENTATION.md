# Authentication & Session Management - Mocked Implementation

**Status**: Ready for Implementation  
**Last Updated**: October 28, 2025  
**Approach**: Mocked OAuth + Single Test User + Pickle Persistence

## Summary

Simplified mocked authentication with session management for rapid development:

- **Authentication**: Mocked OAuth (hardcoded test user, no external API)
- **Storage**: In-memory (Dict), migrate to Redis/PostgreSQL later
- **Account Model**: Single test user (`test@example.com`)
- **Session Delivery**: `X-Session-Id` header (REST), `?sessionId=` param (WebSocket)
- **Migration Path**: Easy upgrade to Google OAuth when needed

## Design Decisions

- **Auth Provider**: Mocked (skip Google Cloud Console setup)
- **Test User**: Hardcoded `google-oauth2|test-user` / `test@example.com`
- **Session Storage**: In-memory Dict → Redis/PostgreSQL (production)
- **Session Expiration**: 7 days (configurable)
- **Token Storage**: sessionStorage (cleared on tab close)

## Architecture

```
Frontend                                Backend
━━━━━━━                                 ━━━━━━━
1. Click "Login as Test User"
2. POST /auth/login {email}         →  Return test user session
3. Store sessionId                  ←  Create session (in-memory)
4. X-Session-Id header (REST)       →  Extract accountId
5. ?sessionId= param (WebSocket)    →  Validate & store in ws.state
```

**Session Structure**:

```python
{
  "session_id": "uuid-v4",
  "user_id": "google-oauth2|test-user",
  "email": "test@example.com",
  "account_id": "ACC-TEST001",
  "created_at": timestamp,
  "expires_at": timestamp
}
```

**Test User** (hardcoded):

```python
{
  "id": "google-oauth2|test-user",
  "email": "test@example.com",
  "name": "Test User",
  "email_verified": True
}
```

## Implementation

### Backend Structure

```
backend/src/trading_api/
├── models/auth/
│   ├── user.py          # User, UserInfo
│   └── session.py       # Session, SessionInfo, MockLoginRequest, LoginResponse
├── core/
│   └── auth_service.py  # AuthService (business logic)
├── dependencies/
│   └── auth.py          # get_current_session, get_account_id (FastAPI dependencies)
├── api/
│   └── auth.py          # /auth endpoints (login, logout, me)
└── plugins/
    └── fastws_adapter.py # ws_auth_handler
```

### Key Models

```python
# models/auth/session.py
class MockLoginRequest(BaseModel):
    email: str = "test@example.com"  # Optional, defaults to test user

class Session(BaseModel):
    session_id: str            # UUID v4
    user_id: str
    email: str
    account_id: str            # "ACC-TEST001"
    created_at: int
    expires_at: int

class LoginResponse(BaseModel):
    session: SessionInfo
    message: str
```

### AuthService (Mocked)

```python
class AuthService:
    """Mocked auth with hardcoded test user (in-memory storage)"""

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._init_test_user()  # Pre-populate test user

    def _init_test_user(self):
        """Initialize hardcoded test user"""
        test_user = User(
            id="google-oauth2|test-user",
            email="test@example.com",
            name="Test User",
            picture=None,
            email_verified=True,
            created_at=int(time.time()),
            last_login=int(time.time())
        )
        self._users[test_user.id] = test_user

    async def mock_login(self, request: MockLoginRequest) -> LoginResponse:
        """Mock login - always succeeds with test user"""
        user_id = "google-oauth2|test-user"
        user = self._users[user_id]

        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user.id,
            email=user.email,
            account_id="ACC-TEST001",
            created_at=int(time.time()),
            expires_at=int(time.time()) + (7 * 24 * 60 * 60)
        )

        self._sessions[session.session_id] = session

        return LoginResponse(
            session=SessionInfo.from_session(session),
            message="Login successful (mocked)"
        )

    async def get_session(self, session_id: str) -> Session | None:
        """Get session by ID (returns None if not found or expired)"""
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check expiration
        if int(time.time()) > session.expires_at:
            # Cleanup expired session
            self._sessions.pop(session_id, None)
            return None

        return session

    async def logout(self, session_id: str):
        """Invalidate session"""
        self._sessions.pop(session_id, None)
```

### Dependencies

```python
# dependencies/auth.py
from typing import Annotated
from fastapi import Header, Depends, HTTPException
from trading_api.core.auth_service import auth_service
from trading_api.models.auth import Session

async def get_current_session(
    x_session_id: Annotated[str, Header(alias="X-Session-Id")]
) -> Session:
    """FastAPI dependency: Extract and validate session from X-Session-Id header

    Note: For microservices, this could call POST /auth/validate endpoint instead
    of the service directly, enabling session validation across service boundaries.
    """
    session = await auth_service.get_session(x_session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session

async def get_account_id(session: Session = Depends(get_current_session)) -> str:
    """FastAPI dependency: Extract account ID from validated session"""
    return session.account_id
```

### Endpoints

```python
# api/auth.py
from trading_api.dependencies.auth import get_current_session
from trading_api.core.auth_service import auth_service

@router.post("/auth/login", response_model=LoginResponse)
async def mock_login(request: MockLoginRequest):
    """Mocked login - no external OAuth required"""
    return await auth_service.mock_login(request)

@router.post("/auth/validate", response_model=Session)
async def validate_session(session_id: str):
    """Validate session by ID - for microservices session validation

    This endpoint allows other microservices to validate sessions without
    direct access to the session storage. Call this from other services
    or from the dependency function for distributed deployments.
    """
    session = await auth_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session

@router.post("/auth/logout")
async def logout(session: Session = Depends(get_current_session)):
    await auth_service.logout(session.session_id)
    return {"message": "Logged out successfully"}

@router.get("/auth/me", response_model=UserInfo)
async def get_current_user_profile(session: Session = Depends(get_current_session)):
    return await auth_service.get_user_info(session.session_id)

# Usage in other API endpoints (e.g., api/broker.py)
from trading_api.dependencies.auth import get_account_id

@router.post("/orders")
async def place_order(
    order: PreOrder,
    account_id: str = Depends(get_account_id)  # Auto-validated
):
    # account_id is automatically extracted from session
    return await broker_service.place_order(account_id, order)
```

### WebSocket Authentication

```python
# plugins/fastws_adapter.py
async def ws_auth_handler(ws: WebSocket) -> bool:
    """Validate ?sessionId= query param"""
    await ws.accept()

    session_id = ws.query_params.get("sessionId")
    if not session_id:
        await ws.close(code=1008, reason="sessionId required")
        return False

    # For microservices: could call POST /auth/validate endpoint instead
    session = await auth_service.get_session(session_id)
    if not session:
        await ws.close(code=1008, reason="Invalid or expired session")
        return False

    # Store in WebSocket state
    ws.state.session = session
    ws.state.account_id = session.account_id
    return True

# Configure in main.py
wsApp = FastWSAdapter(auth_handler=ws_auth_handler, auto_ws_accept=False)
```

### Frontend Implementation

**Auto-Generated Types** (from OpenAPI spec):

```typescript
// Generated in: frontend/src/clients/trader-client-generated/models/
export interface MockLoginRequest {
  email?: string; // Defaults to "test@example.com"
}

export interface SessionInfo {
  session_id: string;
  user_id: string;
  email: string;
  account_id: string;
  created_at: number;
  expires_at: number;
}

export interface LoginResponse {
  session: SessionInfo;
  message: string;
}

export interface UserInfo {
  id: string;
  email: string;
  name: string;
  picture?: string | null;
  email_verified: boolean;
}
```

**Integration with Generated Client**:

```typescript
// stores/authStore.ts
import { AuthApi, Configuration } from "@/clients/trader-client-generated";
import type {
  SessionInfo,
  LoginResponse,
} from "@/clients/trader-client-generated";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    session: null as SessionInfo | null,
    isAuthenticated: false,
  }),

  getters: {
    sessionId: (state) => state.session?.session_id ?? null,
  },

  actions: {
    async mockLogin() {
      // Use auto-generated AuthApi client
      const authApi = new AuthApi();
      const loginResponse: LoginResponse = await authApi.mockLogin({
        mockLoginRequest: { email: "test@example.com" },
      });

      this.session = loginResponse.session;
      this.isAuthenticated = true;

      // Update all API clients with session ID
      this.updateApiConfig();
    },

    async logout() {
      const authApi = new AuthApi();
      await authApi.logout();

      this.session = null;
      this.isAuthenticated = false;
      this.updateApiConfig();
    },

    updateApiConfig() {
      // Recreate Configuration with X-Session-Id header for all generated clients
      const config = new Configuration({
        basePath: import.meta.env.VITE_API_URL,
        headers: this.sessionId ? { "X-Session-Id": this.sessionId } : {},
      });

      // Update apiAdapter with new config
      apiAdapter.setConfiguration(config);
    },
  },

  persist: {
    storage: sessionStorage,
    paths: ["session"],
  },
});

// services/apiAdapter.ts
import {
  Configuration,
  BrokerApi,
  DatafeedApi,
} from "@/clients/trader-client-generated";

class ApiAdapter {
  private config: Configuration;
  public brokerApi: BrokerApi;
  public datafeedApi: DatafeedApi;
  // ... other generated API clients

  constructor() {
    this.config = new Configuration({
      basePath: import.meta.env.VITE_API_URL,
    });
    this.updateClients();
  }

  setConfiguration(config: Configuration) {
    this.config = config;
    this.updateClients();
  }

  private updateClients() {
    // Recreate all API clients with updated configuration
    this.brokerApi = new BrokerApi(this.config);
    this.datafeedApi = new DatafeedApi(this.config);
    // ... other API clients
  }
}

// clients/wsClientBase.ts
class WebSocketBase {
  private getWebSocketUrl(): string {
    const authStore = useAuthStore();
    const sessionId = authStore.sessionId;

    if (!sessionId) {
      throw new Error("No active session - please login first");
    }

    return `${baseUrl}/ws?sessionId=${encodeURIComponent(sessionId)}`;
  }
}
```

## Microservices Architecture Consideration

### Session Validation Endpoint

The `/auth/validate` endpoint enables session validation across microservice boundaries:

**Monolith Mode** (current):

```python
# dependencies/auth.py - Direct service call
session = await auth_service.get_session(x_session_id)
```

**Microservices Mode** (future):

```python
# dependencies/auth.py - HTTP call to auth service
import httpx

async def get_current_session(x_session_id: str) -> Session:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AUTH_SERVICE_URL}/auth/validate",
            json={"session_id": x_session_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        return Session(**response.json())
```

**Benefits**:

- ✅ Same codebase supports both monolith and microservices
- ✅ Auth service can be deployed independently
- ✅ Session storage centralized in auth service
- ✅ Other services remain stateless
- ✅ Easy to add caching layer (Redis) between services

**Migration Path**:

1. Start with monolith (direct service calls)
2. Add feature flag: `USE_REMOTE_AUTH_SERVICE`
3. Implement HTTP client version of `get_current_session`
4. Deploy auth service separately when needed
5. Toggle flag to switch to remote validation

## Client Generation Integration

### Backend → OpenAPI Spec

When auth models and endpoints are created, they automatically appear in the OpenAPI spec:

```bash
# Backend generates spec (automatic on startup or via make generate)
backend/openapi.json
  ├── components.schemas.MockLoginRequest
  ├── components.schemas.LoginResponse
  ├── components.schemas.SessionInfo
  ├── components.schemas.UserInfo
  └── paths./auth/login (POST)
      paths./auth/validate (POST) # For microservices
      paths./auth/logout (POST)
      paths./auth/me (GET)
```

### OpenAPI Spec → TypeScript Client

Frontend client generation creates TypeScript interfaces and API classes:

```bash
# Frontend generates client (make generate-openapi-client)
frontend/src/clients/trader-client-generated/
  ├── models/
  │   ├── MockLoginRequest.ts
  │   ├── LoginResponse.ts
  │   ├── SessionInfo.ts
  │   └── UserInfo.ts
  └── apis/
      └── AuthApi.ts  # mockLogin(), logout(), getCurrentUserProfile()
```

### Type Safety Flow

```
Backend (Pydantic) → OpenAPI JSON Schema → TypeScript Interfaces → Frontend
    ↓                      ↓                       ↓
Session Model      SessionInfo schema      SessionInfo interface
```

**Key Benefits**:

- ✅ Type changes propagate automatically
- ✅ Breaking changes caught at compile time
- ✅ No manual type synchronization needed
- ✅ Single source of truth (backend models)

## Implementation Plan

**Timeline: 4-5 days**

### Phase 1: Backend Mocked Auth (1 day)

- Create auth models (user.py, session.py)
- Implement AuthService with `_init_test_user()` and `mock_login()` (in-memory)
- Create dependencies/auth.py (get_current_session, get_account_id)
- Create /auth endpoints (POST /login, POST /logout, GET /me)
- **Export OpenAPI spec** (automatic, includes auth endpoints)
- Write tests (test_auth_service.py, test_api_auth.py)

### Phase 2: WebSocket Auth (1 day)

- Implement ws_auth_handler (validate sessionId param)
- Update main.py with auth_handler
- Write WebSocket auth tests

### Phase 3: Frontend (1 day)

- **Generate TypeScript client** (`make generate-openapi-client`)
  - Auto-generated auth models: `MockLoginRequest`, `LoginResponse`, `SessionInfo`, `UserInfo`
  - Auto-generated API class: `AuthApi` with typed methods
  - Verify generated types match backend models
- Create/update authStore
  - Use generated `AuthApi` client for login/logout
  - Store `SessionInfo` in Pinia state
  - Implement session persistence (sessionStorage)
- Update ApiAdapter
  - Recreate `Configuration` with `X-Session-Id` header
  - Update all generated API clients (BrokerApi, DatafeedApi, etc.)
- Update WebSocketBase
  - Add `?sessionId=` query param to WebSocket URL
  - Handle missing session error
- Create simple login UI ("Login as Test User" button)
- Add router guards (optional)

### Phase 4: Integration & Testing (1 day)

- Add get_account_id dependency to broker endpoints
- E2E testing: login → place order → logout
- Manual testing with Playwright MCP
- Update ARCHITECTURE.md

### Phase 5: Documentation (0.5 day)

- Update ENVIRONMENT-CONFIG.md with auth flags
- Add testing guide for mocked auth

## Security

### Session Management

- Secure tokens: `secrets.token_urlsafe(32)`
- Session expiration: 7 days (configurable)
- Invalidate on logout
- **Note**: In-memory storage means sessions lost on server restart (acceptable for dev)

### Production Migration

- Replace in-memory Dict with Redis (sessions) or PostgreSQL (persistent storage)
- Add session persistence across server restarts
- Implement distributed session management for multi-instance deployments

### Environment Variables

```bash
# backend/.env
SESSION_EXPIRE_DAYS=7
MOCK_AUTH_ENABLED=true

# frontend/.env
VITE_USE_MOCK_AUTH=true
```

## Testing

### Backend Tests

```python
# test_auth_service.py
- test_init_test_user_exists
- test_mock_login_creates_session
- test_validate_session_valid/expired/invalid
- test_logout_invalidates_session
- test_session_cleanup

# test_api_auth.py
- test_mock_login_endpoint
- test_validate_session_endpoint (valid/invalid/expired)
- test_get_user_info_with_session
- test_logout_endpoint
- test_endpoints_require_session

# test_ws_auth.py
- test_websocket_requires_sessionId
- test_websocket_with_valid/invalid_session
- test_session_stored_in_ws_state
```

### Frontend Tests

```typescript
// authStore.spec.ts
- Mock login flow with generated AuthApi client
- Session storage and persistence
- Logout and session cleanup
- Type safety validation (SessionInfo interface)

// apiAdapter.spec.ts
- X-Session-Id header injection in Configuration
- All generated API clients updated with new config
- Session change triggers client recreation

// wsClientBase.spec.ts
- sessionId query param in WebSocket URL
- Missing session throws error
- Reconnection preserves sessionId
```

### Integration Tests

```typescript
// smoke-tests/mock-auth-flow.spec.ts
- Full mock login flow
- Authenticated API calls
- WebSocket with session
- Logout
```

## Dependencies

### Backend

```bash
# No external OAuth libraries needed for mocked implementation
# Standard library only: secrets, time
```

### Frontend

```bash
# No Google OAuth SDK needed
# Standard Vue/TypeScript dependencies
```

### Environment Setup

```bash
# backend/.env
SESSION_EXPIRE_DAYS=7
MOCK_AUTH_ENABLED=true

# frontend/.env
VITE_USE_MOCK_AUTH=true
```

## Success Criteria

### Functional

- ✅ Users can login with mock test user
- ✅ Sessions stored in-memory (dev mode)
- ✅ Sessions expire after configured duration
- ✅ REST API validates X-Session-Id header
- ✅ WebSocket validates ?sessionId= param
- ✅ Frontend: Mock login flow, session storage, auto-injection

### Testing

- ✅ Unit tests for AuthService, API endpoints, WebSocket auth
- ✅ Frontend tests for auth store, API adapter, WebSocket client
- ✅ E2E test: login → API call → logout

### Documentation

- ✅ ENVIRONMENT-CONFIG.md updated with mock auth flags
- ✅ ARCHITECTURE.md updated with auth flow

## Migration Path to Real Google OAuth

When ready for production Google OAuth:

1. **Install Google SDK**: `poetry add google-auth google-auth-oauthlib`
2. **Add Google validation**: Implement `verify_google_token()` method
3. **Update endpoints**: Add `/auth/google` endpoint alongside `/auth/login`
4. **Frontend OAuth**: Replace mock button with Google OAuth flow
5. **Environment vars**: Add `GOOGLE_CLIENT_ID`, `VITE_GOOGLE_CLIENT_ID`
6. **Feature toggle**: Use `MOCK_AUTH_ENABLED` to switch between implementations

```python
# Feature flag pattern
if settings.MOCK_AUTH_ENABLED:
    return await auth_service.mock_login(request)
else:
    return await auth_service.login_with_google(request)
```

**Benefits**: Zero code refactoring, clean separation, easy rollback.

## Questions

1. ✅ Hardcoded test user (`test@example.com`) - **Confirmed**
2. ✅ Session expiration: 7 days - **Confirmed**
3. ✅ In-memory storage (sessions lost on restart) - **Acceptable for dev**
4. Add broker auth now or later? - **Recommend: Phase 4**
5. Login page or inline button? - **Recommend: Simple button**

Ready to start implementation following TDD methodology.
