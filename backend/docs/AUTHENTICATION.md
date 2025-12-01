# Authentication System

**Version:** 2.0.0  
**Status:** ✅ Production Ready (MVP with In-Memory Storage)  
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
10. [Security Considerations](#security-considerations)
11. [Testing](#testing)
12. [Production Migration](#production-migration)
13. [Troubleshooting](#troubleshooting)

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
│  │  │ (In-Memory)│→ │ (AuthService)│→ │ (/login, /me)   │  │  │
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

**Interfaces:**

- `UserRepositoryInterface`: User CRUD operations
- `RefreshTokenRepositoryInterface`: Token storage with device fingerprinting

**Implementations (MVP):**

- `InMemoryUserRepository`: Thread-safe dict with secondary indexes
- `InMemoryRefreshTokenRepository`: Thread-safe storage with fingerprint validation

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

- In-memory storage (no persistence)
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

- ✅ In-memory storage (thread-safe)
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
