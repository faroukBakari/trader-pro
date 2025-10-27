## 🔐 Authentication Implementation - Preparation Summary

### Current State Analysis

**Existing System:**

- ✅ No authentication currently implemented
- ✅ CORS middleware enabled (allow all origins in dev)
- ✅ Pydantic validation for all requests
- ✅ WebSocket infrastructure with `auth_handler` support (FastWS)
- ✅ Type-safe architecture (Python + TypeScript)
- ✅ Code generation pipeline (OpenAPI/AsyncAPI → TypeScript clients)

**Documented Plans (from ARCHITECTURE.md):**

- 🎯 JWT authentication planned
- 🎯 Per-endpoint rate limiting
- 🎯 Enhanced security measures
- 🎯 WebSocket authentication via `auth_handler`

---

## 🏗️ Proposed Authentication Architecture

### 1. **Backend Components** (Following Project Patterns)

#### **Models** (`backend/src/trading_api/models/auth/`)

```python
# Models organized by business domain (following broker/market pattern)
auth/
├── __init__.py
├── common.py        # Shared auth types (TokenType enum, etc.)
├── user.py          # User models (User, UserProfile, UserCreate)
├── credentials.py   # Login models (LoginRequest, LoginResponse)
├── tokens.py        # JWT models (Token, TokenData, RefreshTokenRequest)
└── session.py       # Session models (Session, SessionInfo)
```

**Key Models:**

- `User` - User account (id, email, username, hashed_password, is_active, created_at)
- `LoginRequest` - Credentials (email/username, password)
- `LoginResponse` - Auth result (access_token, refresh_token, user_info)
- `Token` - JWT structure (access_token, token_type, expires_in)
- `TokenData` - Decoded JWT payload (user_id, email, exp, scopes)

#### **Service Layer** (`backend/src/trading_api/core/auth_service.py`)

```python
class AuthService:
    """Authentication and authorization service following project patterns"""

    # In-memory storage for development (like BrokerService pattern)
    _users: Dict[str, User]
    _sessions: Dict[str, Session]
    _refresh_tokens: Dict[str, str]  # token → user_id

    async def register_user(request: UserCreate) -> User
    async def login(credentials: LoginRequest) -> LoginResponse
    async def logout(user_id: str) -> None
    async def refresh_token(refresh_token: str) -> Token
    async def verify_token(token: str) -> TokenData
    async def get_current_user(token: str) -> User
```

#### **REST API** (`backend/src/trading_api/api/auth.py`)

```python
class AuthApi(APIRouter):
    """Auth endpoints following BrokerApi pattern"""

    POST   /auth/register      # User registration
    POST   /auth/login         # Login with credentials
    POST   /auth/logout        # Logout and invalidate tokens
    POST   /auth/refresh       # Refresh access token
    GET    /auth/me            # Get current user profile
    PUT    /auth/me            # Update user profile
    POST   /auth/change-password
```

#### **Dependencies** (`backend/src/trading_api/dependencies/auth.py`)

```python
# FastAPI dependency injection for protected routes
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    """Verify JWT and return current user"""

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Ensure user is active"""

# Optional scopes for role-based access
async def require_scope(required_scope: str):
    """Check user has required permission scope"""
```

#### **WebSocket Authentication** (fastws_adapter.py)

```python
# Update FastWSAdapter to include auth_handler
async def ws_auth_handler(ws: WebSocket) -> bool:
    """
    WebSocket authentication via JWT token

    Protocol:
    1. Client connects
    2. Server accepts connection
    3. Client sends: {"type": "auth", "token": "<jwt>"}
    4. Server validates token and returns success/failure
    5. Connection established or closed
    """
    await ws.accept()
    try:
        auth_msg = await asyncio.wait_for(
            ws.receive_json(),
            timeout=5.0
        )
        if auth_msg.get("type") != "auth":
            return False

        token = auth_msg.get("token")
        user = await auth_service.verify_token(token)

        # Store user context in connection
        ws.state.user = user
        return True

    except (asyncio.TimeoutError, ValueError):
        return False
```

---

### 2. **Frontend Components**

#### **Generated Types** (Auto-generated from OpenAPI)

```typescript
// frontend/src/clients/trader-client-generated/models/
interface User {
  id: string;
  email: string;
  username: string;
  isActive: boolean;
  createdAt: number;
}

interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  user: User;
}
```

#### **Auth Store** (Pinia - State Management)

```typescript
// frontend/src/stores/authStore.ts
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    accessToken: null as string | null,
    refreshToken: null as string | null,
    isAuthenticated: false,
    isLoading: false,
  }),

  actions: {
    async login(credentials: LoginRequest): Promise<void>
    async logout(): Promise<void>
    async refreshToken(): Promise<void>
    async fetchCurrentUser(): Promise<void>

    // Automatic token refresh before expiry
    setupTokenRefresh(): void
  },

  persist: {
    storage: localStorage,
    paths: ['accessToken', 'refreshToken'], // Don't persist user data
  }
})
```

#### **API Adapter Updates** (apiAdapter.ts)

```typescript
export class ApiAdapter {
  private rawApi: V1Api;
  private authStore = useAuthStore();

  constructor() {
    const apiConfig = new Configuration({
      basePath: import.meta.env.VITE_API_URL || "",
      accessToken: () => this.authStore.accessToken || "", // Auto-inject token
    });
    this.rawApi = new V1Api(apiConfig);
  }

  // Auth methods
  async login(credentials: LoginRequest): ApiPromise<LoginResponse>;
  async logout(): ApiPromise<void>;
  async refreshToken(token: string): ApiPromise<Token>;
  async getCurrentUser(): ApiPromise<User>;
}
```

#### **WebSocket Authentication** (wsClientBase.ts)

```typescript
// Update WebSocketBase to send auth token on connection
class WebSocketBase {
  private async __socketConnect(): Promise<void> {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = async () => {
      // Send authentication message
      const authStore = useAuthStore();
      if (authStore.accessToken) {
        this.ws.send(
          JSON.stringify({
            type: "auth",
            token: authStore.accessToken,
          })
        );
      }

      // Wait for auth confirmation before proceeding
      await this.waitForAuthConfirmation();
      this.resolveConnection();
    };
  }

  private async waitForAuthConfirmation(): Promise<void> {
    // Listen for auth response message
    // Reject connection if auth fails
  }
}
```

#### **Router Guards** (index.ts)

```typescript
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    // Redirect to login
    next({ name: "login", query: { redirect: to.fullPath } });
  } else {
    next();
  }
});
```

---

### 3. **Implementation Plan Following API-METHODOLOGY.md**

#### **Phase 1: Backend Models + API Stubs** (1-2 days)

- ✅ Create auth models in `models/auth/`
- ✅ Create `AuthApi` with empty stubs (NotImplementedError)
- ✅ Register auth router in main.py
- ✅ Generate OpenAPI spec
- ✅ Frontend: Generate TypeScript client
- ✅ Verification: Backend starts, specs exported, no type errors

#### **Phase 2: Backend Service Implementation** (2-3 days)

- ✅ Implement `AuthService` (in-memory storage initially)
- ✅ JWT creation/validation utilities
- ✅ Password hashing (bcrypt/passlib)
- ✅ Wire service to API endpoints
- ✅ Write backend unit tests
- ✅ Verification: Backend tests pass

#### **Phase 3: FastAPI Dependencies** (1 day)

- ✅ Create `get_current_user` dependency
- ✅ Create `get_current_active_user` dependency
- ✅ Optional: Role/scope-based dependencies
- ✅ Apply dependencies to protected routes
- ✅ Test dependency injection
- ✅ Verification: Protected routes require authentication

#### **Phase 4: WebSocket Authentication** (1-2 days)

- ✅ Implement `ws_auth_handler` in `FastWSAdapter`
- ✅ Update WebSocket connection to require auth
- ✅ Store user context in connection state
- ✅ Update subscription handlers to use user context
- ✅ Write WebSocket auth tests
- ✅ Verification: WebSocket requires auth token

#### **Phase 5: Frontend Implementation** (2-3 days)

- ✅ Create auth store (Pinia)
- ✅ Update `ApiAdapter` to inject tokens
- ✅ Implement login/logout/refresh flows
- ✅ Update `WebSocketBase` to authenticate
- ✅ Add router guards
- ✅ Create login/register UI components
- ✅ Write frontend tests
- ✅ Verification: Full auth flow works end-to-end

#### **Phase 6: Integration & Documentation** (1 day)

- ✅ End-to-end testing (login → trade → logout)
- ✅ WebSocket reconnection with auth
- ✅ Token refresh automation
- ✅ Update ARCHITECTURE.md
- ✅ Create AUTH-IMPLEMENTATION.md
- ✅ Update ENVIRONMENT-CONFIG.md (JWT_SECRET, etc.)
- ✅ Smoke tests with authentication

---

### 4. **Security Considerations**

**JWT Configuration:**

```python
# Environment variables (ENVIRONMENT-CONFIG.md)
JWT_SECRET_KEY=<random-secret>       # For signing tokens
JWT_ALGORITHM=HS256                  # HMAC SHA-256
ACCESS_TOKEN_EXPIRE_MINUTES=15       # Short-lived access tokens
REFRESH_TOKEN_EXPIRE_DAYS=7          # Long-lived refresh tokens
```

**Password Security:**

```python
# Use bcrypt or passlib for hashing
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

**CORS Updates (Production):**

```python
# Restrict CORS in production
CORS_ORIGINS = ["https://traderpro.com"]  # From env variable
```

**Rate Limiting (Future):**

```python
# Add to auth endpoints
@router.post("/auth/login")
@limiter.limit("5/minute")  # Prevent brute force
async def login(...)
```

---

### 5. **Testing Strategy**

**Backend Tests:**

```python
# tests/test_auth_service.py
async def test_register_user()
async def test_login_success()
async def test_login_invalid_credentials()
async def test_token_refresh()
async def test_token_expiration()

# tests/test_api_auth.py
async def test_protected_endpoint_requires_auth()
async def test_protected_endpoint_with_valid_token()
async def test_protected_endpoint_with_expired_token()

# tests/test_ws_auth.py
async def test_websocket_connection_requires_auth()
async def test_websocket_connection_with_valid_token()
async def test_websocket_connection_with_invalid_token()
```

**Frontend Tests:**

```typescript
// src/stores/__tests__/authStore.spec.ts
describe("AuthStore", () => {
  it("should login successfully");
  it("should logout and clear state");
  it("should refresh token before expiry");
  it("should handle login errors");
});

// src/services/__tests__/authService.spec.ts
describe("Auth Service Integration", () => {
  it("should authenticate and access protected routes");
  it("should handle token expiration");
});
```

---

### 6. **Dependencies to Add**

**Backend:**

```toml
# pyproject.toml
python-jose = "^3.3.0"       # JWT encoding/decoding
passlib = "^1.7.4"           # Password hashing
bcrypt = "^4.0.1"            # Bcrypt hashing algorithm
python-multipart = "^0.0.6"  # Form data parsing
```

**Frontend:**

```json
// package.json - No new dependencies needed
// Using existing: Pinia (state), axios/fetch (HTTP)
```

---

Starting (4/4) _Validate plan and get approval_

## 📋 Next Steps & Recommendations

### Immediate Actions:

1. **Review the Plan** - Confirm the architecture aligns with your requirements
2. **Choose Database** - Decide on user storage (in-memory → PostgreSQL/MongoDB later)
3. **JWT Secret Generation** - Generate strong secret key for production
4. **Scope Definition** - Decide on role-based access control (admin, trader, viewer)

### Estimated Timeline:

| Phase                   | Duration      | Effort                                       |
| ----------------------- | ------------- | -------------------------------------------- |
| Phase 1: Models + Stubs | 1-2 days      | Backend models, API stubs, client generation |
| Phase 2: Service Logic  | 2-3 days      | AuthService, JWT utilities, tests            |
| Phase 3: Dependencies   | 1 day         | FastAPI dependencies, protected routes       |
| Phase 4: WebSocket Auth | 1-2 days      | ws_auth_handler, connection auth             |
| Phase 5: Frontend       | 2-3 days      | Auth store, UI, integration                  |
| Phase 6: Integration    | 1 day         | E2E tests, documentation                     |
| **Total**               | **8-12 days** | Full authentication system                   |

### Key Design Decisions to Confirm:

1. **User Registration:** Open registration vs invite-only?
2. **Token Storage:** localStorage (current) vs httpOnly cookies?
3. **Multi-Factor Auth:** Include 2FA/TOTP in initial implementation?
4. **Account Management:** Email verification, password reset flows?
5. **Session Management:** Single device vs multiple concurrent sessions?

---

## 🎯 Ready to Start?

The preparation is complete! The implementation follows your existing patterns:

- ✅ TDD methodology (API-METHODOLOGY.md)
- ✅ Topic-based models (broker/market pattern)
- ✅ Service layer architecture
- ✅ Type-safe contracts (OpenAPI → TypeScript)
- ✅ WebSocket integration (FastWS auth_handler)
- ✅ Dual-client frontend (mock + real)

**Would you like me to:**

1. Start implementing Phase 1 (Backend Models + API Stubs)?
2. Create a detailed AUTH-IMPLEMENTATION.md document first?
3. Set up environment variables and dependencies?
4. Create authentication-specific documentation?

Let me know how you'd like to proceed! 🚀
