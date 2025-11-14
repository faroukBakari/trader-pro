# Authentication System Documentation

**Version:** 1.0.0  
**Status:** ✅ Production Ready (MVP with In-Memory Storage)  
**Last Updated:** November 14, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication Architecture](#authentication-architecture)
3. [Google OAuth Flow](#google-oauth-flow)
4. [JWT Token Structure](#jwt-token-structure)
5. [Cookie-Based Session Management](#cookie-based-session-management)
6. [Frontend Integration](#frontend-integration)
7. [Backend Integration](#backend-integration)
8. [WebSocket Authentication](#websocket-authentication)
9. [Security Considerations](#security-considerations)
10. [Production Migration Path](#production-migration-path)
11. [Testing Authentication](#testing-authentication)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The Trading Pro platform implements a **JWT-based authentication system** with Google OAuth integration, providing secure, stateless authentication for both REST and WebSocket connections.

### Key Features

- ✅ **Google OAuth Integration** - Verify Google ID tokens via `authlib`
- ✅ **JWT Access Tokens** - RS256-signed tokens with 5-minute expiry
- ✅ **Refresh Token Rotation** - Opaque tokens with device fingerprinting
- ✅ **Cookie-Based Sessions** - HttpOnly, Secure, SameSite=Strict cookies
- ✅ **Stateless Middleware** - Public key validation (no database queries)
- ✅ **WebSocket Authentication** - Automatic via cookies
- ✅ **Service-Based Frontend** - No Pinia store, authentication in service layer
- ✅ **Router Guards** - Stateless with API introspection (30s cache)

### Design Philosophy

**Stateless & Scalable:**

- Middleware validates JWT with public key only (no database)
- Horizontally scalable (no session state)
- Independent auth module (can be disabled)

**Security First:**

- HttpOnly cookies prevent XSS attacks
- SameSite=Strict prevents CSRF attacks
- Token rotation prevents refresh token theft
- Device fingerprinting validates token origin

**Developer Experience:**

- Automatic cookie handling (browser managed)
- No manual token management in frontend
- Type-safe JWT payload (`UserData` model)
- Comprehensive test coverage (92 tests)

---

## Authentication Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ authService.ts   │  │ Router Guards    │  │ LoginView.vue │ │
│  │ (Service-based)  │  │ (Stateless)      │  │ (Google OAuth)│ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘ │
└───────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │
            │ Uses API           │ Introspects       │ Sends token
            │                    │                    │
┌───────────▼────────────────────▼────────────────────▼──────────┐
│                         Backend Layer                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Auth Module (modules/auth/)                  │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │ Repository │  │   Service    │  │   API (v1.py)   │  │  │
│  │  │ (In-Memory)│→│ (AuthService)│→│ (/login, /me)   │  │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               ↓                                 │
│                    Sets access_token cookie                     │
│                               ↓                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       Shared Middleware (shared/middleware/auth.py)       │  │
│  │  - get_current_user() - REST authentication               │  │
│  │  - get_current_user_ws() - WebSocket authentication       │  │
│  │  - Public key validation only (stateless)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               ↓                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Protected Endpoints (broker, datafeed)           │  │
│  │  - All endpoints require authentication                   │  │
│  │  - User data from `get_current_user` dependency           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Module Organization

**Backend:**

- **Auth Module** - `backend/src/trading_api/modules/auth/`

  - Repository layer (user and refresh token storage)
  - Service layer (JWT generation, Google OAuth verification)
  - API layer (login, refresh, logout, me, introspect endpoints)

- **Shared Middleware** - `backend/src/trading_api/shared/middleware/auth.py`
  - Stateless JWT validation with public key
  - Independent of auth module (no database access)
  - Used by all protected endpoints

**Frontend:**

- **Auth Service** - `frontend/src/services/authService.ts`

  - Service-based architecture (no Pinia store)
  - Singleton with composable interface
  - Reactive state management

- **Router Guards** - `frontend/src/router/index.ts`
  - Stateless authentication checks
  - API introspection with 30s cache
  - Redirect preservation

---

## Google OAuth Flow

### Complete Authentication Flow

```
┌─────────────┐                                              ┌──────────────┐
│   User      │                                              │   Google     │
│  (Browser)  │                                              │  OAuth API   │
└──────┬──────┘                                              └──────┬───────┘
       │                                                             │
       │  1. Click "Sign in with Google"                            │
       │────────────────────────────────────────────────────────────▶
       │                                                             │
       │  2. Google Sign-In dialog                                  │
       │◀────────────────────────────────────────────────────────────│
       │                                                             │
       │  3. User authorizes                                        │
       │────────────────────────────────────────────────────────────▶
       │                                                             │
       │  4. Google returns ID token                                │
       │◀────────────────────────────────────────────────────────────│
       │                                                             │
┌──────▼──────┐                                   ┌─────────────────┐
│  Frontend   │                                   │  Backend Auth   │
│   Service   │                                   │     Module      │
└──────┬──────┘                                   └────────┬────────┘
       │                                                   │
       │  5. POST /api/v1/auth/login                     │
       │     { google_token: "eyJhbG..." }               │
       │──────────────────────────────────────────────────▶
       │                                                   │
       │                     ┌──────────────────────────┐ │
       │                     │  6. Verify ID token      │ │
       │                     │  7. Fetch Google keys    │ │
       │                     │  8. Validate signature   │ │
       │                     └──────────────────────────┘ │
       │                                                   │
       │                     ┌──────────────────────────┐ │
       │                     │  9. Create/update user   │ │
       │                     │ 10. Generate JWT         │ │
       │                     │ 11. Generate refresh     │ │
       │                     │ 12. Store refresh token  │ │
       │                     └──────────────────────────┘ │
       │                                                   │
       │ 13. Response:                                     │
       │     { access_token, refresh_token, ... }         │
       │     Set-Cookie: access_token=<jwt>; HttpOnly     │
       │◀──────────────────────────────────────────────────│
       │                                                   │
       │ 14. Navigate to protected route                  │
       │                                                   │
```

### Flow Steps

1. **User Initiates Login**: Clicks "Sign in with Google" button
2. **Google Sign-In Dialog**: User authorizes application
3. **Google Returns ID Token**: Short-lived token with user claims
4. **Frontend Sends Token**: POST to `/api/v1/auth/login` with ID token
5. **Backend Verifies Token**: Validates signature with Google's public keys
6. **User Creation**: Creates or updates user in repository
7. **JWT Generation**: Creates access token with user data
8. **Refresh Token**: Generates opaque refresh token with device fingerprint
9. **Token Storage**: Stores refresh token hash in repository
10. **Response**: Returns tokens and sets HttpOnly cookie
11. **Frontend Navigation**: Redirects to protected route

### Google OAuth Configuration

**Required Environment Variables:**

```bash
GOOGLE_CLIENT_ID=1002931823122-xxx.apps.googleusercontent.com
```

**Google Console Setup:**

1. Create project at https://console.cloud.google.com
2. Enable Google+ API
3. Create OAuth 2.0 credentials
4. Add authorized redirect URIs:
   - http://localhost:5173 (development)
   - https://your-domain.com (production)
5. Download client configuration

**Frontend Integration:**

```typescript
// main.ts
import { vue3GoogleSignin } from "vue3-google-signin";

app.use(vue3GoogleSignin, {
  clientId: import.meta.env.VITE_GOOGLE_CLIENT_ID,
});
```

---

## JWT Token Structure

### Access Token (JWT)

**Header:**

```json
{
  "alg": "RS256",
  "typ": "JWT"
}
```

**Payload (`JWTPayload`):**

```json
{
  "user_id": "USER-1",
  "email": "user@example.com",
  "full_name": "John Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "exp": 1731588000,
  "iat": 1731587700
}
```

**Configuration:**

- **Algorithm**: RS256 (RSA Signature with SHA-256)
- **Expiry**: 5 minutes
- **Storage**: HttpOnly cookie
- **Private Key**: `backend/.local/secrets/jwt_private.pem` (4096-bit RSA)
- **Public Key**: `backend/.local/secrets/jwt_public.pem`

**UserData Model (Extracted by Middleware):**

```python
class UserData(BaseModel):
    """User data extracted from JWT token."""
    user_id: str
    email: str
    full_name: str | None
    picture: str | None
```

### Refresh Token

**Format:**

- **Type**: Opaque (URL-safe base64)
- **Length**: 32 bytes (~43 characters)
- **Storage**: Frontend localStorage
- **Hashing**: bcrypt (12 rounds)
- **Expiry**: 7 days (configurable)

**Stored Data (`RefreshTokenData`):**

```python
{
    "token_id": "RT-1",
    "user_id": "USER-1",
    "token_hash": "$2b$12$...",
    "created_at": "2025-11-14T...",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0 ...",
    "fingerprint": "a3f8c2..."  # SHA256(IP + User-Agent)
}
```

### Token Lifecycle

```
Login
  ↓
Generate access token (5min) + refresh token (7d)
  ↓
Access token expires
  ↓
POST /refresh-token with refresh token
  ↓
Validate refresh token + device fingerprint
  ↓
Generate NEW access token + NEW refresh token
  ↓
Revoke OLD refresh token (token rotation)
  ↓
Continue...
```

**Token Rotation Benefits:**

- Limits refresh token lifetime
- Detects token theft (invalidates stolen token)
- Provides audit trail

---

## Cookie-Based Session Management

### Cookie Configuration

**Name:** `access_token`

**Flags:**

```python
response.set_cookie(
    key="access_token",
    value=jwt_token,
    httponly=True,      # JavaScript cannot access
    secure=True,        # HTTPS only (production)
    samesite="strict",  # CSRF protection
    max_age=300,        # 5 minutes
)
```

### Security Benefits

| Feature             | Protection | Description                                          |
| ------------------- | ---------- | ---------------------------------------------------- |
| **HttpOnly**        | XSS        | JavaScript cannot access token via `document.cookie` |
| **Secure**          | MITM       | Cookie only sent over HTTPS connections              |
| **SameSite=Strict** | CSRF       | Cookie not sent on cross-site requests               |
| **Short Expiry**    | Theft      | Limited damage window if token stolen                |

### CORS Configuration

**Backend (`shared/config.py`):**

```python
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGINS = [
    "http://localhost:5173",  # Development
    "https://your-domain.com"  # Production
]
```

**Frontend (Axios/Fetch):**

```typescript
// Automatically includes cookies
fetch("http://localhost:8000/api/v1/auth/me", {
  credentials: "include", // Required for cookies
});
```

### Cookie Workflow

```
User Login
  ↓
Backend sets cookie: Set-Cookie: access_token=<jwt>; HttpOnly
  ↓
Browser stores cookie automatically
  ↓
Future requests include cookie automatically
  ↓
Backend middleware extracts token from cookie
  ↓
Validates JWT and returns user data
  ↓
Endpoint handler receives UserData
```

---

## Frontend Integration

### Auth Service Architecture

**Location:** `frontend/src/services/authService.ts`

**Pattern:** Service-based singleton with composable interface

**Why No Pinia Store?**

- ✅ Authentication is transient (cookies managed by browser)
- ✅ No complex state mutations needed
- ✅ Service provides cleaner API
- ✅ Reactive refs sufficient for loading/error state

**Service Interface:**

```typescript
interface AuthServiceType {
  // Reactive state
  isLoading: Ref<boolean>;
  error: Ref<string | null>;

  // Methods
  checkAuthStatus(): Promise<boolean>;
  loginWithGoogleToken(googleToken: string): Promise<void>;
  logout(): Promise<void>;
}
```

### Usage Example

```typescript
import { useAuthService } from "@/services/authService";

const authService = useAuthService();

// Check authentication
const isAuthenticated = await authService.checkAuthStatus();

// Login
await authService.loginWithGoogleToken(googleToken);

// Logout
await authService.logout();

// Reactive state
console.log(authService.isLoading.value); // false
console.log(authService.error.value); // null
```

### Router Guards

**Location:** `frontend/src/router/index.ts`

**Pattern:** Stateless guards with API introspection

**Implementation:**

```typescript
router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAuth) {
    const isAuthenticated = await authService.checkAuthStatus();

    if (!isAuthenticated) {
      // Save intended destination
      next({
        path: "/login",
        query: { redirect: to.fullPath },
      });
    } else {
      next();
    }
  } else {
    next();
  }
});
```

**Introspection Caching:**

- 30-second cache to minimize API calls
- Cache invalidated on login/logout
- Background refresh on cache expiry

### Login View

**Location:** `frontend/src/views/LoginView.vue`

**Features:**

- Google Sign-In button via `vue3-google-signin`
- Loading state during authentication
- Error message display
- Automatic redirect to intended route

**Example:**

```vue
<template>
  <GoogleSignInButton @success="handleGoogleSignIn" />
  <div v-if="authService.isLoading.value">Logging in...</div>
  <div v-if="authService.error.value">{{ authService.error.value }}</div>
</template>

<script setup lang="ts">
import { useAuthService } from "@/services/authService";
import { useRouter } from "vue-router";

const authService = useAuthService();
const router = useRouter();

async function handleGoogleSignIn(response: any) {
  await authService.loginWithGoogleToken(response.credential);

  // Redirect to intended route or home
  const redirect = router.currentRoute.value.query.redirect as string;
  router.push(redirect || "/");
}
</script>
```

---

## Backend Integration

### Shared Middleware

**Location:** `backend/src/trading_api/shared/middleware/auth.py`

**⚠️ CRITICAL:** This module is INDEPENDENT of the auth module:

- ✅ NO database queries
- ✅ NO private key access (public key only)
- ✅ Stateless validation only
- ✅ Can be used even if auth module is disabled

**Functions:**

```python
from typing import Annotated
from fastapi import Depends, Request, WebSocket
from trading_api.models.auth import UserData

async def get_current_user(request: Request) -> UserData:
    """Validates JWT from cookie and returns user data.

    Process:
    1. Extract token from request.cookies.get("access_token")
    2. Decode JWT with public key (RS256)
    3. Validate payload structure
    4. Return UserData object

    Raises:
        HTTPException(401): If token missing, invalid, or expired
    """
    ...

async def get_current_user_ws(websocket: WebSocket) -> UserData:
    """WebSocket-specific authentication.

    Same process as get_current_user but for WebSocket connections.

    Raises:
        WebSocketException(1008): If authentication fails
    """
    ...
```

### Protected Endpoint Pattern

**REST Endpoints:**

```python
from typing import Annotated
from fastapi import Depends
from trading_api.models.auth import UserData
from trading_api.shared.middleware.auth import get_current_user

@router.get("/orders")
async def get_orders(
    user_data: Annotated[UserData, Depends(get_current_user)]
) -> list[Order]:
    """Get orders for authenticated user."""
    return await order_service.get_user_orders(user_data.user_id)

@router.post("/orders")
async def create_order(
    order: Order,
    user_data: Annotated[UserData, Depends(get_current_user)]
) -> OrderResponse:
    """Create order for authenticated user."""
    order.user_id = user_data.user_id  # Enforce ownership
    return await order_service.create_order(order)
```

**WebSocket Endpoints:**

```python
from trading_api.shared.middleware.auth import get_current_user_ws

class BrokerWsRouters(WsRouterInterface):
    def __init__(self, service: WsRouteService):
        order_router = OrderWsRouter(route="orders", service=service)

        @order_router.on_connect
        async def authenticate(
            client: Client,
            user_data: Annotated[UserData, Depends(get_current_user_ws)]
        ):
            """Authenticate connection and store user data."""
            client.state["user_data"] = user_data

        @order_router.on_subscribe
        async def handle_subscribe(client: Client, topic: str):
            """Filter subscriptions by user."""
            user_data = client.state.get("user_data")
            # Only subscribe to user's own orders
            await service.subscribe_user_orders(user_data.user_id, topic)
```

### Auth Module Endpoints

**Location:** `backend/src/trading_api/modules/auth/api/v1.py`

| Endpoint                     | Method | Auth Required | Description                        |
| ---------------------------- | ------ | ------------- | ---------------------------------- |
| `/api/v1/auth/login`         | POST   | No            | Authenticate with Google OAuth     |
| `/api/v1/auth/refresh-token` | POST   | No            | Refresh access token               |
| `/api/v1/auth/logout`        | POST   | No            | Logout and revoke refresh token    |
| `/api/v1/auth/me`            | GET    | Yes           | Get current user info              |
| `/api/v1/auth/introspect`    | GET    | Yes           | Validate token (for router guards) |

See [Auth Module README](../backend/src/trading_api/modules/auth/README.md) for complete API documentation.

---

## WebSocket Authentication

### Automatic Cookie Authentication

WebSocket connections are authenticated **automatically** via cookies:

```typescript
// Frontend - No authentication code needed!
const ws = new WebSocket("ws://localhost:8000/api/v1/broker/ws");

// Browser automatically includes cookies in handshake
// Backend validates token from cookie
// Connection established if authenticated
```

### Authentication Flow

```
Client initiates WebSocket connection
  ↓
Browser includes access_token cookie in handshake
  ↓
Backend middleware extracts token: websocket.cookies.get("access_token")
  ↓
Validate JWT with public key (RS256)
  ↓
Decode user data from payload
  ↓
Connection accepted (if valid) or rejected (401/403)
  ↓
WebSocket messages flow with authenticated context
```

### Key Points

- ✅ **No Query Parameters**: Token not in URL (more secure)
- ✅ **No Manual Handling**: Browser manages cookies automatically
- ✅ **Same Security**: HttpOnly cookies work for WebSocket handshake
- ✅ **No Frontend Code**: WebSocket clients don't need auth logic
- ✅ **Auto-Reconnection**: Uses same cookie mechanism on reconnect

### Error Handling

```python
# Backend automatically rejects unauthenticated connections
@router.on_connect
async def handle_connect(
    client: Client,
    user_data: Annotated[UserData, Depends(get_current_user_ws)]
):
    """Connection only established if authentication succeeds."""
    client.state["user_data"] = user_data
```

```typescript
// Frontend handles connection failures
ws.onerror = (event) => {
  // 401/403 errors indicate authentication failure
  // Auth service handles token refresh if needed
  // Reconnection uses updated cookie automatically
};
```

---

## Security Considerations

### Current Implementation (MVP)

**✅ Strengths:**

- HttpOnly cookies prevent XSS token theft
- SameSite=Strict prevents CSRF attacks
- Bcrypt hashing for refresh tokens (12 rounds)
- RS256 JWT signature (asymmetric cryptography)
- Device fingerprinting for refresh tokens
- Token rotation on refresh
- Stateless middleware (public key only)
- Short access token expiry (5 minutes)
- Comprehensive test coverage (92 tests)

**⚠️ Limitations (MVP):**

- In-memory storage (no persistence across restarts)
- Basic device fingerprinting (IP + User-Agent only)
- No rate limiting on authentication endpoints
- No anomaly detection for unusual login patterns
- No token blacklist for emergency revocation

### Best Practices

1. **Never Log Tokens**

   ```python
   # ❌ Bad
   logger.info(f"Access token: {access_token}")

   # ✅ Good
   logger.info("User authenticated successfully")
   ```

2. **Rotate Refresh Tokens**

   ```python
   # Always generate new refresh token on use
   new_refresh_token = generate_refresh_token()
   revoke_token(old_refresh_token)
   ```

3. **Validate Audience and Issuer**

   ```python
   # JWT payload validation
   if payload.get("aud") != EXPECTED_AUDIENCE:
       raise HTTPException(401, "Invalid token audience")
   ```

4. **Use Separate Keys**

   ```bash
   # Development keys
   backend/.local/secrets/jwt_private.pem

   # Production keys (secure storage)
   /etc/secrets/jwt_private.pem
   ```

5. **Monitor Failed Attempts**

   ```python
   # Track and alert on repeated failures
   if failed_login_count > 5:
       send_alert("Potential brute force attack")
   ```

6. **Implement Progressive Delays**
   ```python
   # Slow down repeated failures
   delay = min(2 ** failed_attempts, 60)
   await asyncio.sleep(delay)
   ```

### Threat Mitigation

| Threat             | Mitigation                                    |
| ------------------ | --------------------------------------------- |
| **XSS**            | HttpOnly cookies (JavaScript cannot access)   |
| **CSRF**           | SameSite=Strict (cross-site requests blocked) |
| **Token Theft**    | Short expiry (5min), refresh rotation         |
| **Replay Attacks** | Device fingerprinting, token rotation         |
| **MITM**           | HTTPS/WSS only (Secure cookie flag)           |
| **Brute Force**    | Rate limiting (planned), progressive delays   |

---

## Production Migration Path

### Current State (MVP)

- ✅ In-memory user storage (thread-safe)
- ✅ In-memory refresh token storage (thread-safe)
- ⚠️ Data lost on server restart
- ⚠️ No persistence across deployments
- ⚠️ Single-server only (no horizontal scaling)

### Step 1: User Storage → PostgreSQL

**Replace:** `InMemoryUserRepository` → `PostgresUserRepository`

**Schema:**

```sql
CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    picture TEXT,
    created_at TIMESTAMP NOT NULL,
    last_login TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
```

**Implementation:**

```python
class PostgresUserRepository(UserRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

### Step 2: Refresh Token Storage → Redis

**Replace:** `InMemoryRefreshTokenRepository` → `RedisRefreshTokenRepository`

**Benefits:**

- TTL-based automatic expiration
- Persistent across restarts
- Horizontal scaling support
- Atomic operations

**Key Structure:**

```
rt:{token_hash} → RefreshTokenData (JSON)
rt:user:{user_id} → Set[token_hash]  # Secondary index
TTL: 7 days
```

**Implementation:**

```python
class RedisRefreshTokenRepository(RefreshTokenRepositoryInterface):
    def __init__(self, redis: Redis):
        self.redis = redis

    async def store_token(self, token_data: RefreshTokenData) -> None:
        key = f"rt:{token_data.token_hash}"
        value = token_data.model_dump_json()
        await self.redis.setex(key, 7 * 24 * 3600, value)

        # Secondary index
        user_key = f"rt:user:{token_data.user_id}"
        await self.redis.sadd(user_key, token_data.token_hash)
```

### Step 3: Additional Hardening

**Rate Limiting:**

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # Max 5 attempts per minute
async def login(request: Request, ...):
    ...
```

**Token Blacklist:**

```python
# Redis-based blacklist for emergency revocation
async def blacklist_token(token_jti: str, ttl: int) -> None:
    await redis.setex(f"blacklist:{token_jti}", ttl, "1")

async def is_token_blacklisted(token_jti: str) -> bool:
    return await redis.exists(f"blacklist:{token_jti}")
```

**Enhanced Device Fingerprinting:**

```python
def extract_device_fingerprint(request: Request) -> str:
    components = [
        request.client.host,
        request.headers.get("user-agent", ""),
        request.headers.get("accept-language", ""),
        request.headers.get("accept-encoding", ""),
        # Add more entropy in production
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()
```

**Anomaly Detection:**

```python
# Track login patterns
async def detect_anomaly(user_id: str, current_login: LoginAttempt) -> bool:
    recent_logins = await get_recent_logins(user_id, hours=24)

    # Check for unusual location
    if current_login.country != recent_logins[-1].country:
        return True

    # Check for unusual time
    usual_hours = set(login.hour for login in recent_logins)
    if current_login.hour not in usual_hours:
        return True

    return False
```

### Step 4: Key Rotation Strategy

**Generate Production Keys:**

```bash
# 4096-bit RSA keys
openssl genrsa -out jwt_private.pem 4096
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
chmod 600 jwt_private.pem
chmod 644 jwt_public.pem
```

**Key Rotation Process:**

1. Generate new key pair
2. Update backend with new private key
3. Keep old public key for verification (grace period)
4. Invalidate all tokens after grace period
5. Remove old public key

---

## Testing Authentication

### Backend Testing

**Unit Tests:**

```python
# Test JWT generation
def test_create_access_token(auth_service):
    user = User(id="USER-1", email="test@example.com")
    token = auth_service._create_access_token(user)

    # Verify token structure
    payload = jwt.decode(token, public_key, algorithms=["RS256"])
    assert payload["user_id"] == "USER-1"
    assert payload["email"] == "test@example.com"

# Test token validation
async def test_get_current_user(client):
    token = create_test_token(user_id="USER-1")

    response = await client.get(
        "/api/v1/auth/me",
        cookies={"access_token": token}
    )
    assert response.status_code == 200
    assert response.json()["id"] == "USER-1"
```

**Mocking Google OAuth:**

```python
@pytest.fixture
def mock_google_oauth(monkeypatch):
    async def mock_parse_id_token(token, claims_options):
        return {
            "sub": "104857234567890123456",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://lh3.googleusercontent.com/test"
        }

    monkeypatch.setattr(
        "authlib.integrations.starlette_client.OAuth.google.parse_id_token",
        mock_parse_id_token
    )
```

**Integration Tests:**

```python
async def test_full_authentication_flow(client):
    # 1. Login
    response = await client.post("/api/v1/auth/login", json={
        "google_token": "mock_token"
    })
    assert response.status_code == 200
    access_token = response.cookies.get("access_token")
    refresh_token = response.json()["refresh_token"]

    # 2. Access protected endpoint
    response = await client.get("/api/v1/broker/orders")
    assert response.status_code == 200

    # 3. Refresh token
    response = await client.post("/api/v1/auth/refresh-token", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200

    # 4. Logout
    response = await client.post("/api/v1/auth/logout", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
```

### Frontend Testing

**Service Tests:**

```typescript
import { describe, it, expect, vi } from "vitest";
import { useAuthService } from "@/services/authService";

describe("authService", () => {
  it("should login with Google token", async () => {
    const authService = useAuthService();

    // Mock API
    vi.spyOn(authService.apiAdapter, "loginWithGoogleToken").mockResolvedValue({
      access_token: "jwt",
      refresh_token: "refresh",
    });

    await authService.loginWithGoogleToken("google_token");

    expect(authService.error.value).toBeNull();
  });

  it("should check auth status", async () => {
    const authService = useAuthService();

    // Mock introspection
    vi.spyOn(authService.apiAdapter, "introspectToken").mockResolvedValue({
      status: "valid",
    });

    const isAuthenticated = await authService.checkAuthStatus();

    expect(isAuthenticated).toBe(true);
  });
});
```

**Router Guard Tests:**

```typescript
import { describe, it, expect } from "vitest";
import { createRouter } from "@/router";

describe("authentication guards", () => {
  it("should redirect to login for protected routes", async () => {
    const router = createRouter();

    // Mock unauthenticated
    vi.spyOn(authService, "checkAuthStatus").mockResolvedValue(false);

    await router.push("/broker");

    expect(router.currentRoute.value.path).toBe("/login");
    expect(router.currentRoute.value.query.redirect).toBe("/broker");
  });

  it("should allow access to protected routes when authenticated", async () => {
    const router = createRouter();

    // Mock authenticated
    vi.spyOn(authService, "checkAuthStatus").mockResolvedValue(true);

    await router.push("/broker");

    expect(router.currentRoute.value.path).toBe("/broker");
  });
});
```

### Test Organization

```
backend/
├── src/trading_api/modules/auth/tests/
│   ├── conftest.py                    # Auth fixtures
│   ├── test_repository.py             # Repository tests (19)
│   ├── test_service.py                # Service tests (14)
│   └── test_api.py                    # API tests (18)
├── tests/unit/
│   └── test_auth_middleware.py        # Middleware tests (21)
└── tests/integration/
    └── test_auth_integration.py       # Integration tests (10)

frontend/
└── src/services/tests/
    ├── authService.spec.ts            # Service tests
    └── authService.integration.spec.ts # Integration tests
```

**Test Coverage:** 92 tests total, 100% passing

---

## Troubleshooting

### Common Issues

#### 1. "Missing authentication token in cookie"

**Symptom:** 401 error when accessing protected endpoints

**Causes:**

- Access token not set or expired
- CORS not allowing credentials
- Cookie not being sent (SameSite issue)

**Solutions:**

```bash
# Check browser cookies (DevTools → Application → Cookies)
# Look for: access_token cookie at localhost:8000

# Verify backend sets cookie
curl -v -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"google_token": "..."}'
# Look for: Set-Cookie: access_token=...

# Verify CORS configuration
# backend/src/trading_api/shared/config.py
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGINS = ["http://localhost:5173"]

# Frontend must include credentials
fetch('http://localhost:8000/api/v1/auth/me', {
  credentials: 'include'
})
```

#### 2. "Invalid token: Signature verification failed"

**Symptom:** JWT validation fails with signature error

**Causes:**

- Public/private key mismatch
- Wrong key path in environment variables
- Keys regenerated after token creation

**Solutions:**

```bash
# Verify keys exist
ls -la backend/.local/secrets/jwt_*.pem

# Check environment variables
cat backend/.env.local | grep JWT_

# Regenerate keys if needed
cd backend
openssl genrsa -out .local/secrets/jwt_private.pem 4096
openssl rsa -in .local/secrets/jwt_private.pem -pubout -out .local/secrets/jwt_public.pem

# Restart backend
make dev
```

#### 3. "Invalid token or device mismatch"

**Symptom:** Refresh token fails with device mismatch error

**Causes:**

- IP address changed (VPN, network switch)
- User-Agent changed (browser update)
- Using refresh token from different device

**Solutions:**

```python
# This is expected behavior for security
# User must login again

# For development, can disable fingerprint check:
# (NOT for production)
async def get_token(self, token_hash: str, fingerprint: str | None = None):
    if fingerprint and stored_token.fingerprint != fingerprint:
        # Skip check in development
        if os.getenv("ENV") == "development":
            pass  # Allow mismatch
        else:
            return None
```

#### 4. "Google token verification failed"

**Symptom:** Login fails with Google OAuth error

**Causes:**

- Invalid GOOGLE_CLIENT_ID
- Google token expired (1-hour lifetime)
- Internet connectivity issue (can't fetch Google keys)
- Authorized redirect URI mismatch

**Solutions:**

```bash
# Verify client ID matches Google Console
echo $VITE_GOOGLE_CLIENT_ID

# Check Google Console configuration:
# - APIs & Services → Credentials
# - Authorized redirect URIs must include:
#   http://localhost:5173

# Test token manually
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"google_token": "<paste_token_here>"}'

# Check backend logs for detailed error
tail -f backend/logs/app.log
```

#### 5. WebSocket Connection Fails with 401/403

**Symptom:** WebSocket connection rejected immediately

**Causes:**

- Access token expired
- Cookie not included in handshake
- CORS not configured properly

**Solutions:**

```typescript
// Verify cookie exists before connecting
const cookies = document.cookie
  .split(";")
  .find((c) => c.trim().startsWith("access_token="));
console.log("Access token cookie:", cookies);

// Check WebSocket URL is correct
// Must match backend origin for cookies to be sent
const ws = new WebSocket("ws://localhost:8000/api/v1/broker/ws");

// Monitor connection errors
ws.onerror = (event) => {
  console.error("WebSocket error:", event);
  // Check if authentication issue
  // 401/403 = authentication failure
};
```

### Debug Checklist

**Backend:**

- [ ] Keys exist: `backend/.local/secrets/jwt_*.pem`
- [ ] Environment variables set: `JWT_PRIVATE_KEY_PATH`, `GOOGLE_CLIENT_ID`
- [ ] CORS configured: `CORS_ALLOW_CREDENTIALS=True`
- [ ] Auth module enabled: `ENABLED_MODULES` includes `auth`

**Frontend:**

- [ ] Google client ID set: `VITE_GOOGLE_CLIENT_ID`
- [ ] Credentials included: `fetch(..., { credentials: 'include' })`
- [ ] Cookie exists: Check DevTools → Application → Cookies
- [ ] Auth service initialized: `useAuthService()`

**Network:**

- [ ] Backend running: `http://localhost:8000/api/v1/health`
- [ ] CORS headers present: `Access-Control-Allow-Credentials: true`
- [ ] Cookie in request: Check Network tab → Request Headers
- [ ] Cookie in response: Check Network tab → Response Headers

---

## Related Documentation

### Backend Documentation

- **[Auth Module](../backend/src/trading_api/modules/auth/README.md)** - Complete module implementation
- **[Modular Architecture](../backend/docs/MODULAR_BACKEND_ARCHITECTURE.md)** - Module system overview
- **[Backend Testing](../backend/docs/BACKEND_TESTING.md)** - Testing strategy

### Frontend Documentation

- **[Services README](../frontend/src/services/README.md)** - Auth service details
- **[Router README](../frontend/src/router/README.md)** - Router guards implementation
- **[Frontend README](../frontend/README.md)** - Frontend overview

### Cross-Cutting Documentation

- **[Architecture](./ARCHITECTURE.md)** - System architecture overview
- **[Testing](./TESTING.md)** - Testing strategies
- **[Development](./DEVELOPMENT.md)** - Development workflows

---

**Last Updated:** November 14, 2025  
**Maintained by:** Development Team  
**Status:** ✅ Production Ready (MVP)
