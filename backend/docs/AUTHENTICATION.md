# Authentication System

**Version:** 2.0.0  
**Status:** ✅ Production Ready (MVP with DuckDB Storage)
**Last Updated:** November 30, 2025

> **Consolidated Documentation**: This document combines cross-cutting authentication architecture with backend module implementation details.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Google OAuth Flow](#google-oauth-flow)
4. [JWT Token Structure](#jwt-token-structure)
5. [Cookie-Based Sessions](#cookie-based-sessions)
6. [Auth Module Implementation](#auth-module-implementation)
7. [Shared Middleware](#shared-middleware)
8. [Frontend Integration](#frontend-integration)
9. [WebSocket Authentication](#websocket-authentication)
10. [Inter-Module HMAC Authentication](#inter-module-hmac-authentication)
11. [Security Considerations](#security-considerations)
12. [Testing](#testing)
13. [Production Migration](#production-migration)
14. [Troubleshooting](#troubleshooting)

---

## Overview

The Trading Pro platform implements a **JWT-based authentication system** with Google OAuth integration, providing secure, stateless authentication for both REST and WebSocket connections.

### Key Features

| Feature                    | Description                                                     |
| -------------------------- | --------------------------------------------------------------- |
| **Google OAuth**           | Verify Google ID tokens via pluggable `AuthCapability` provider |
| **JWT Access Tokens**      | RS256-signed tokens with 5-minute expiry                        |
| **Refresh Token Rotation** | 64-byte opaque tokens with device fingerprinting                |
| **Cookie-Based Sessions**  | HttpOnly, Secure, SameSite=Strict cookies                       |
| **Stateless Middleware**   | Public key validation only (no database queries)                |
| **WebSocket Auth**         | Automatic via cookies in handshake                              |
| **Provider Pattern**       | Pluggable auth backends via capability system                   |

### Design Principles

1. **Stateless & Scalable**: Middleware validates JWT with public key only (no database), enabling horizontal scaling
2. **Security First**: HttpOnly cookies (XSS), SameSite=Strict (CSRF), token rotation (theft prevention)
3. **Provider-Based**: Auth logic abstracted via `AuthCapability` for pluggable backends
4. **Developer Experience**: Automatic cookie handling, type-safe JWT payload, comprehensive tests

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ authService.ts   │  │ Router Guards    │  │ LoginView.vue │ │
│  │ (Service-based)  │  │ (Stateless)      │  │ (Google OAuth)│ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘ │
└───────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │
            │ Uses API           │ Introspects        │ Sends token
            │                    │                    │
┌───────────▼────────────────────▼────────────────────▼──────────┐
│                         Backend Layer                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Auth Module (modules/auth/)                  │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │ Repository │  │   Service    │  │   API (v1.py)   │  │  │
│  │  │ (DuckDB)   │→ │ (AuthService)│→ │ (/login, /me)   │  │  │
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

| Component         | Location                                            | Purpose                         |
| ----------------- | --------------------------------------------------- | ------------------------------- |
| Auth Module       | `backend/src/trading_api/modules/auth/`             | Repository, service, API layers |
| Shared Middleware | `backend/src/trading_api/shared/middleware/auth.py` | Stateless JWT validation        |
| Auth Service      | `frontend/src/services/authService.ts`              | Frontend auth handling          |
| Router Guards     | `frontend/src/router/index.ts`                      | Protected route enforcement     |

---

## Google OAuth Flow

### Complete Flow Diagram

```
User (Browser)          Frontend            Backend Auth            Google
     │                     │                     │                    │
     │  1. Click Sign-in   │                     │                    │
     │────────────────────>│                     │                    │
     │                     │                     │                    │
     │  2. Google dialog   │                     │                    │
     │<────────────────────│                     │                    │
     │                     │                     │                    │
     │  3. Authorize       │                     │                    │
     │─────────────────────────────────────────────────────────────>│
     │                     │                     │                    │
     │  4. ID token        │                     │                    │
     │<─────────────────────────────────────────────────────────────│
     │                     │                     │                    │
     │                     │  5. POST /login     │                    │
     │                     │────────────────────>│                    │
     │                     │                     │                    │
     │                     │                     │  6. Verify token   │
     │                     │                     │───────────────────>│
     │                     │                     │                    │
     │                     │                     │  7. Valid claims   │
     │                     │                     │<───────────────────│
     │                     │                     │                    │
     │                     │                     │  8. Create/update  │
     │                     │                     │     user, tokens   │
     │                     │                     │                    │
     │                     │ 9. Tokens + cookie  │                    │
     │                     │<────────────────────│                    │
     │                     │                     │                    │
     │ 10. Navigate home   │                     │                    │
     │<────────────────────│                     │                    │
```

### Configuration

**Environment Variables:**

```bash
# Backend
GOOGLE_CLIENT_ID=1002931823122-xxx.apps.googleusercontent.com

# Frontend
VITE_GOOGLE_CLIENT_ID=1002931823122-xxx.apps.googleusercontent.com
```

**Google Console Setup:**

1. Create project at https://console.cloud.google.com
2. Enable Google+ API
3. Create OAuth 2.0 credentials
4. Add authorized origins: `http://localhost:5173`, `https://your-domain.com`

---

## JWT Token Structure

### Access Token

| Property  | Value                              |
| --------- | ---------------------------------- |
| Algorithm | RS256 (RSA + SHA-256)              |
| Expiry    | 5 minutes                          |
| Storage   | HttpOnly cookie                    |
| Keys      | `backend/.local/secrets/jwt_*.pem` |

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

### Refresh Token

| Property | Value                     |
| -------- | ------------------------- |
| Format   | Opaque (URL-safe base64)  |
| Length   | 64 bytes (~86 characters) |
| Storage  | Frontend localStorage     |
| Hashing  | SHA256 (hexdigest)        |
| Expiry   | 7 days                    |

**Stored Data (`RefreshTokenData`):**

```python
{
    "token_id": "TOKEN-...",
    "user_id": "USER-1",
    "token_hash": "a3b4c5...",  # SHA256
    "fingerprint": "a3f8c2..."  # SHA256(IP + User-Agent)
}
```

**[DECISION]**: SHA256 used instead of bcrypt to avoid 72-byte input limit issues.

### Token Lifecycle

```
Login → Generate access (5min) + refresh (7d) tokens
    ↓
Access token expires
    ↓
POST /refresh-token
    ↓
Validate refresh token + device fingerprint
    ↓
Generate NEW tokens, revoke OLD refresh token
    ↓
Continue...
```

---

## Cookie-Based Sessions

### Cookie Configuration

```python
response.set_cookie(
    key="access_token",
    value=jwt_token,
    httponly=True,      # XSS protection
    secure=True,        # HTTPS only
    samesite="strict",  # CSRF protection
    max_age=300,        # 5 minutes
)
```

### Security Benefits

| Flag            | Protection | Description                                    |
| --------------- | ---------- | ---------------------------------------------- |
| HttpOnly        | XSS        | JavaScript cannot access via `document.cookie` |
| Secure          | MITM       | Cookie only sent over HTTPS                    |
| SameSite=Strict | CSRF       | Cookie not sent on cross-site requests         |
| Short Expiry    | Theft      | Limited damage window                          |

### CORS Configuration

```python
# backend/src/trading_api/shared/config.py
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGINS = ["http://localhost:5173"]
```

---

## Auth Module Implementation

**Location:** `backend/src/trading_api/modules/auth/`

### Repository Layer

- `UserRepository(datastore)`: Uses `TableInterface` with unique indexes on `email` and `google_id` for O(1) lookups
- `RefreshTokenRepository(datastore)`: Uses `TableInterface` with secondary index on `user_id` for 1:N token lookups

**Datastore Injection**: Both repositories receive `DatastoreInterface` from `AuthService` via the `ServiceInterface` base class. Index configuration is extracted from `Field(index=True, unique=True)` metadata via `datastore.table(ModelClass)`. Concurrency is handled internally by `TableInterface` (RWLock pattern).

### Service Layer

**Class:** `AuthService(AuthServiceInterface, ServiceInterface)`

**Capability Dependencies:**

```python
@classmethod
def capabilities(cls) -> list[CapabilitySpec]:
    return [CapabilitySpec(name="auth")]
```

**Key Methods:**

| Method                       | Description                                       |
| ---------------------------- | ------------------------------------------------- |
| `authenticate_google_user()` | Verify Google token, create user, generate tokens |
| `refresh_access_token()`     | Validate refresh, rotate tokens                   |
| `logout()`                   | Revoke refresh token (silent failure)             |
| `_create_access_token()`     | Sign JWT with RS256 private key                   |
| `_generate_refresh_token()`  | Generate 64-byte URL-safe token                   |
| `_hash_token()`              | SHA256 hash for storage                           |

### API Layer

**Endpoints:** Mounted at `/api/v1/auth`

| Endpoint         | Method | Auth | Description                     |
| ---------------- | ------ | ---- | ------------------------------- |
| `/login`         | POST   | No   | Authenticate with Google OAuth  |
| `/refresh-token` | POST   | No   | Refresh access token            |
| `/logout`        | POST   | No   | Logout and revoke refresh token |
| `/me`            | GET    | Yes  | Get current user info           |
| `/introspect`    | GET    | Yes  | Validate token (router guards)  |

**Login Request/Response:**

```json
// POST /api/v1/auth/login
// Request:
{ "google_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..." }

// Response:
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "8xK3pQ2mN5wR7tY9vL1cZ4bF6hJ0dG",
  "token_type": "bearer",
  "expires_in": 300
}
// + Set-Cookie: access_token=<jwt>; HttpOnly; Secure; SameSite=Strict
```

---

## Shared Middleware

**Location:** `backend/src/trading_api/shared/middleware/auth.py`

**⚠️ CRITICAL:** This module is INDEPENDENT of the auth module:

- NO database queries
- NO private key access (public key only)
- Stateless validation only

### Functions

#### `get_current_user(request: Request) -> UserData`

REST endpoint authentication.

```python
from trading_api.shared.middleware.auth import get_current_user

@router.get("/orders")
async def get_orders(
    user_data: Annotated[UserData, Depends(get_current_user)]
) -> list[Order]:
    return await order_service.get_user_orders(user_data.user_id)
```

#### `get_current_user_ws(websocket: WebSocket) -> UserData`

WebSocket connection authentication.

```python
@router.on_connect
async def authenticate(
    client: Client,
    user_data: Annotated[UserData, Depends(get_current_user_ws)]
):
    client.state["user_data"] = user_data
```

#### `extract_device_fingerprint(request) -> str`

SHA256 hash of IP + User-Agent (32-char hex).

---

## Frontend Integration

### Auth Service

**Location:** `frontend/src/services/authService.ts`

**Pattern:** Service-based singleton with composable interface (no Pinia store).

```typescript
import { useAuthService } from "@/services/authService";

const authService = useAuthService();

// Check authentication
const isAuthenticated = await authService.checkAuthStatus();

// Login with Google token
await authService.loginWithGoogleToken(googleToken);

// Logout
await authService.logout();

// Reactive state
console.log(authService.isLoading.value);
console.log(authService.error.value);
```

### Router Guards

**Location:** `frontend/src/router/index.ts`

Stateless guards with API introspection (30s cache):

```typescript
router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAuth) {
    const isAuthenticated = await authService.checkAuthStatus();
    if (!isAuthenticated) {
      next({ path: "/login", query: { redirect: to.fullPath } });
    } else {
      next();
    }
  } else {
    next();
  }
});
```

---

## WebSocket Authentication

WebSocket connections authenticate **automatically** via cookies:

```typescript
// No auth code needed!
const ws = new WebSocket("ws://localhost:8000/api/v1/broker/ws");
// Browser includes access_token cookie in handshake
```

**Flow:**

1. Client initiates WebSocket connection
2. Browser includes `access_token` cookie in handshake
3. Backend middleware extracts and validates JWT
4. Connection accepted/rejected based on validation
5. Messages flow with authenticated context

**Benefits:**

- No query parameters (more secure)
- No manual handling (browser manages cookies)
- Same security as REST (HttpOnly cookies)
- Auto-reconnection uses same mechanism

---

## Inter-Module HMAC Authentication

**Added:** January 2026

For secure inter-module HTTP calls (when modules run as separate processes), requests are signed using HMAC-SHA256 with replay protection.

### Overview

| Feature               | Description                                   |
| --------------------- | --------------------------------------------- |
| **Algorithm**         | HMAC-SHA256                                   |
| **Replay Protection** | 30-second TTL window                          |
| **Key Storage**       | `backend/.local/secrets/hmac_internal.key`    |
| **Fallback**          | Cookie-based JWT if signature invalid/missing |

### Signature Format

```
HMAC-SHA256(timestamp|caller_id|method|url|body_hash)
```

Where:

- `timestamp`: Unix timestamp (seconds)
- `caller_id`: Module identifier (e.g., "broker", "datafeed")
- `method`: HTTP method (GET, POST, etc.)
- `url`: Full request URL
- `body_hash`: SHA256 hex digest of request body (or empty body)

### Request Headers

| Header                 | Description                |
| ---------------------- | -------------------------- |
| `X-Internal-Signature` | HMAC-SHA256 hex signature  |
| `X-Internal-Timestamp` | Unix timestamp when signed |
| `X-Internal-Caller`    | Module identifier          |

### Generated Client Usage

Auto-generated clients automatically sign all requests:

```python
from trading_api.modules.datafeed.client_generated import DatafeedClient

# caller_id is required - identifies the calling module
client = DatafeedClient(caller_id="broker")

# Requests are automatically signed with HMAC
symbols = await client.get_symbols()
```

### Middleware Integration

The `get_current_user()` middleware checks for HMAC signatures **before** cookie auth:

```python
async def get_current_user(request: Request) -> UserData:
    # 1. Check internal signature headers
    signature = request.headers.get("X-Internal-Signature")
    timestamp = request.headers.get("X-Internal-Timestamp")
    caller_id = request.headers.get("X-Internal-Caller")

    if signature and timestamp and caller_id and settings.internal_hmac_key:
        if verify_signature(...):
            return INTERNAL_USER  # Pre-defined service account

    # 2. Fall back to cookie-based JWT auth
    token = request.cookies.get("access_token")
    ...
```

### Key Generation

```bash
# Automatic (via Makefile dependency)
make -C backend check-generate-hmac-key

# Manual
mkdir -p backend/.local/secrets
openssl rand -hex 32 > backend/.local/secrets/hmac_internal.key
chmod 600 backend/.local/secrets/hmac_internal.key
```

### Configuration

```python
# backend/src/trading_api/shared/config.py
INTERNAL_HMAC_KEY_PATH: Path = Path(".local/secrets/hmac_internal.key")
INTERNAL_SIGNATURE_TTL_SECONDS: int = 30  # Replay protection window
```

### Security Notes

1. **Replay Protection**: Requests older than 30 seconds are rejected
2. **Timing-Safe Comparison**: Uses `hmac.compare_digest()` to prevent timing attacks
3. **Body Integrity**: Body hash prevents request tampering
4. **Safe Fallback**: Missing/empty key file disables feature (falls back to JWT)
5. **Shared Secret**: Key must be available on all service instances

### Behavior Matrix

| HMAC Key   | Signature Headers | Signature Valid | Result                    |
| ---------- | ----------------- | --------------- | ------------------------- |
| ✅ Present | ✅ Present        | ✅ Valid        | Returns `INTERNAL_USER`   |
| ✅ Present | ✅ Present        | ❌ Invalid      | Falls back to cookie auth |
| ✅ Present | ❌ Missing        | -               | Falls back to cookie auth |
| ❌ Missing | Any               | -               | Falls back to cookie auth |

---

## Security Considerations

### Current Implementation (MVP)

**✅ Strengths:**

- HttpOnly cookies prevent XSS token theft
- SameSite=Strict prevents CSRF attacks
- SHA256 hashing for refresh tokens
- RS256 JWT signature (asymmetric cryptography)
- Device fingerprinting for refresh tokens
- Token rotation on refresh
- Stateless middleware
- Short access token expiry (5 minutes)
- Provider-based auth abstraction

**⚠️ Limitations:**

- DuckDB in-memory storage (no persistence across restarts)
- Basic device fingerprinting (IP + User-Agent only)
- No rate limiting
- No anomaly detection
- No token blacklist

### Threat Mitigation

| Threat         | Mitigation                      |
| -------------- | ------------------------------- |
| XSS            | HttpOnly cookies                |
| CSRF           | SameSite=Strict                 |
| Token Theft    | Short expiry, refresh rotation  |
| Replay Attacks | Device fingerprinting, rotation |
| MITM           | HTTPS only (Secure flag)        |

### Best Practices

1. Never log tokens
2. Rotate refresh tokens on every use
3. Validate audience and issuer in JWT claims
4. Use separate keys for development/production
5. Monitor failed authentication attempts
6. Implement progressive delays for failures

---

## Testing

### Test Coverage

**Total:** 83 tests (100% passing)

| Layer       | Tests | Location                                     |
| ----------- | ----- | -------------------------------------------- |
| Repository  | ~20   | `modules/auth/tests/test_repository.py`      |
| Service     | ~20   | `modules/auth/tests/test_service.py`         |
| API         | ~16   | `modules/auth/tests/test_api.py`             |
| Middleware  | 17    | `tests/unit/test_auth_middleware.py`         |
| Integration | 10    | `tests/integration/test_auth_integration.py` |

### Running Tests

```bash
# All auth tests
cd backend && pytest src/trading_api/modules/auth/tests/ tests/unit/test_auth_middleware.py -v

# Integration tests
cd backend && pytest tests/integration/test_auth_integration.py -v
```

### Mocking Google OAuth

```python
@pytest.fixture
def mock_google_oauth(monkeypatch):
    async def mock_parse_id_token(token, claims_options):
        return {
            "sub": "104857234567890123456",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User"
        }
    monkeypatch.setattr(
        "authlib.integrations.starlette_client.OAuth.google.parse_id_token",
        mock_parse_id_token
    )
```

---

## Production Migration

### Current State (MVP)

- ✅ DuckDB in-memory storage (thread-safe)
- ⚠️ Data lost on restart
- ⚠️ Single-server only

### Step 1: User Storage → PostgreSQL

```sql
CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    picture TEXT,
    created_at TIMESTAMP NOT NULL,
    last_login TIMESTAMP NOT NULL
);
```

### Step 2: Refresh Token Storage → Redis

```
Key: rt:{token_hash}
Value: RefreshTokenData (JSON)
TTL: 7 days

Secondary: rt:user:{user_id} → Set[token_hash]
```

### Step 3: Additional Hardening

- [ ] Rate limiting on `/login`
- [ ] Token blacklist for emergency revocation
- [ ] Production RSA keys (4096-bit)
- [ ] Key rotation strategy
- [ ] Enhanced device fingerprinting
- [ ] Anomaly detection

---

## Troubleshooting

### Common Issues

| Issue                           | Cause                   | Solution                           |
| ------------------------------- | ----------------------- | ---------------------------------- |
| "Missing authentication token"  | Cookie not set/expired  | Check browser cookies, verify CORS |
| "Signature verification failed" | Key mismatch            | Regenerate keys, check paths       |
| "Device mismatch"               | IP/UA changed           | Expected behavior, re-login        |
| "Google token failed"           | Invalid/expired token   | Check client ID, token freshness   |
| WebSocket 401/403               | Cookie not in handshake | Verify same-origin, CORS config    |

### Debug Checklist

**Backend:**

- [ ] Keys exist: `backend/.local/secrets/jwt_*.pem`
- [ ] Environment vars set: `JWT_*_KEY_PATH`, `GOOGLE_CLIENT_ID`
- [ ] CORS: `CORS_ALLOW_CREDENTIALS=True`

**Frontend:**

- [ ] `VITE_GOOGLE_CLIENT_ID` set
- [ ] Credentials included: `credentials: 'include'`
- [ ] Cookie visible in DevTools

**Network:**

- [ ] Backend healthy: `http://localhost:8000/api/v1/health`
- [ ] CORS headers present
- [ ] Cookie in request/response headers

---

## Configuration Reference

### Environment Variables

```bash
# JWT
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=.local/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=.local/secrets/jwt_public.pem
ACCESS_TOKEN_EXPIRE_MINUTES=5

# Google OAuth
GOOGLE_CLIENT_ID=...

# CORS
CORS_ALLOW_CREDENTIALS=true
CORS_ORIGINS=http://localhost:5173

# Cookies
COOKIE_SECURE=true  # false for local HTTP
```

### Key Generation

```bash
mkdir -p backend/.local/secrets
openssl genrsa -out backend/.local/secrets/jwt_private.pem 4096
openssl rsa -in backend/.local/secrets/jwt_private.pem -pubout -out backend/.local/secrets/jwt_public.pem
chmod 600 backend/.local/secrets/jwt_private.pem
chmod 644 backend/.local/secrets/jwt_public.pem
```

---

## Related Documentation

- [Auth Module README](../src/trading_api/modules/auth/README.md) - Module-specific details
- [Provider System](./PROVIDER-SYSTEM.md) - Capability/provider pattern
- [Backend WebSockets](./BACKEND_WEBSOCKETS.md) - WebSocket authentication integration
- [Backend Testing](./BACKEND_TESTING.md) - Testing strategy
- [Frontend Services](../../frontend/src/services/README.md) - Frontend auth service

---

**Last Updated:** November 30, 2025  
**Maintained by:** Development Team
