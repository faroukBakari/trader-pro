# Auth Module

**Version:** 1.0.0  
**Status:** ✅ Production Ready (MVP with In-Memory Storage)

JWT-based authentication module with Google OAuth integration, cookie-based session management, and device fingerprinting.

---

## Overview

The auth module provides comprehensive authentication and authorization for the Trading Pro platform:

- **Google OAuth Integration**: Verify Google ID tokens via `authlib`
- **JWT Access Tokens**: RS256-signed tokens with 5-minute expiry
- **Refresh Token Rotation**: Opaque tokens with device fingerprinting
- **Cookie-Based Sessions**: HttpOnly, Secure, SameSite=Strict cookies
- **Stateless Middleware**: Public key validation for REST and WebSocket

---

## Architecture

The module follows the standard modular backend pattern:

```
Repository Layer (Data Access)
    ↓
Service Layer (Business Logic)
    ↓
API Layer (HTTP Endpoints)
    ↓
Shared Middleware (Stateless Validation)
```

### Components

#### 1. Repository Layer

**Location:** `repository.py`

Provides data access interfaces with in-memory implementations:

- **`UserRepositoryInterface`**

  - `get_by_id(user_id)` - Fetch user by ID
  - `get_by_email(email)` - Fetch user by email
  - `get_by_google_id(google_id)` - Fetch user by Google ID
  - `create(user_data)` - Create new user
  - `update_last_login(user_id)` - Update last login timestamp

- **`RefreshTokenRepositoryInterface`**
  - `store_token(token_data)` - Store refresh token
  - `get_token(token_hash, fingerprint)` - Retrieve token with device validation
  - `revoke_token(token_hash)` - Revoke single token
  - `revoke_all_user_tokens(user_id)` - Revoke all user tokens

**Implementations:**

- `InMemoryUserRepository` - Thread-safe in-memory storage with secondary indexes
- `InMemoryRefreshTokenRepository` - Thread-safe in-memory storage with device fingerprinting

**Production Migration:**

- Replace `InMemoryUserRepository` with `PostgresUserRepository`
- Replace `InMemoryRefreshTokenRepository` with `RedisRefreshTokenRepository` (TTL + persistence)

#### 2. Service Layer

**Location:** `service.py`

**Class:** `AuthService(ServiceInterface)`

Implements authentication business logic:

**Methods:**

- `verify_google_id_token(id_token: str) -> dict[str, Any]`

  - Validates Google ID token using `authlib.OAuth`
  - Fetches Google's public keys via OIDC discovery
  - Verifies signature, expiration, audience, issuer
  - Returns claims: `sub`, `email`, `email_verified`, `name`, `picture`

- `authenticate_google_user(id_token: str, device_info: DeviceInfo) -> TokenResponse`

  - Verifies Google ID token
  - Creates or updates user in repository
  - Generates access token (JWT) and refresh token
  - Stores refresh token hash with device fingerprint
  - Returns both tokens

- `refresh_access_token(refresh_token: str, device_info: DeviceInfo) -> TokenResponse`

  - Validates refresh token and device fingerprint
  - Generates new access and refresh tokens
  - Stores new refresh token atomically
  - Revokes old refresh token
  - Implements token rotation for security

- `logout(refresh_token: str) -> None`
  - Revokes refresh token
  - Silent failure (idempotent)

**Internal Methods:**

- `_create_access_token(user: User) -> str`

  - Signs JWT with RS256 private key
  - Payload: `JWTPayload(user_id, email, full_name, picture, exp, iat)`
  - 5-minute expiry

- `_generate_refresh_token() -> str`

  - Generates 32-byte URL-safe token
  - Uses `secrets.token_urlsafe(32)`

- `_hash_token(token: str) -> str`
  - Bcrypt hashes token via `passlib.CryptContext`
  - 12 rounds for security/performance balance

#### 3. API Layer

**Location:** `api/v1.py`

**Class:** `AuthApi(APIRouterInterface)`

REST endpoints mounted at `/api/v1/auth`:

##### `POST /login`

Authenticate with Google OAuth.

**Request:**

```json
{
  "google_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "8xK3pQ2mN5wR7tY9vL1cZ4bF6hJ0dG",
  "token_type": "bearer",
  "expires_in": 300
}
```

**Side Effects:**

- Sets `access_token` HttpOnly cookie (5-minute expiry)
- Cookie flags: `httponly=True, secure=True, samesite="strict"`

**Errors:**

- `401`: Invalid Google token, unverified email
- `500`: Server error

##### `POST /refresh-token`

Refresh access token using refresh token.

**Request:**

```json
{
  "refresh_token": "8xK3pQ2mN5wR7tY9vL1cZ4bF6hJ0dG"
}
```

**Response:** Same as `/login`

**Side Effects:**

- Updates `access_token` cookie
- Old refresh token revoked (token rotation)

**Errors:**

- `401`: Invalid or revoked refresh token, device fingerprint mismatch

##### `POST /logout`

Logout and revoke refresh token.

**Request:**

```json
{
  "refresh_token": "8xK3pQ2mN5wR7tY9vL1cZ4bF6hJ0dG"
}
```

**Response:**

```json
{
  "message": "Logged out successfully"
}
```

**Side Effects:**

- Clears `access_token` cookie
- Revokes refresh token

**Errors:** None (silent failure, always succeeds)

##### `GET /me`

Get current authenticated user information.

**Headers:** `Cookie: access_token=<jwt>`

**Response:**

```json
{
  "id": "USER-1",
  "google_id": "104857234567890123456",
  "email": "user@example.com",
  "full_name": "John Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "created_at": "2025-11-14T10:00:00Z",
  "last_login": "2025-11-14T12:30:00Z",
  "is_active": true
}
```

**Errors:**

- `401`: Missing or invalid access token
- `404`: User not found

##### `GET /introspect`

Validate access token from cookie.

**Headers:** `Cookie: access_token=<jwt>`

**Response:**

```json
{
  "status": "valid",
  "exp": 1731588000,
  "error": null
}
```

**Status Values:**

- `valid`: Token is valid
- `expired`: Token has expired
- `error`: Token is malformed or invalid

**Use Case:** Frontend router guards and auth monitoring

---

## Authentication Flow

### 1. Google OAuth Login Flow

```
Frontend                 Backend Auth Service              Google
   |                              |                           |
   |  1. User clicks "Sign in"    |                           |
   |---------------------------->|                           |
   |                              |                           |
   |  2. Google Sign-In dialog    |                           |
   |<-----------------------------|                           |
   |                              |                           |
   |  3. User authorizes          |                           |
   |--------------------------------------------------->|
   |                              |                           |
   |  4. Google returns ID token  |                           |
   |<---------------------------------------------------|
   |                              |                           |
   |  5. POST /login with token   |                           |
   |----------------------------->|                           |
   |                              |                           |
   |                              |  6. Verify ID token       |
   |                              |-------------------------->|
   |                              |                           |
   |                              |  7. Return claims         |
   |                              |<--------------------------|
   |                              |                           |
   |                              |  8. Create/update user    |
   |                              |  9. Generate JWT + refresh|
   |                              | 10. Store refresh token   |
   |                              |                           |
   | 11. Return tokens + set cookie                          |
   |<-----------------------------|                           |
   |                              |                           |
   | 12. Navigate to protected route                         |
```

### 2. Token Refresh Flow

```
Frontend                 Backend Auth Service
   |                              |
   |  1. Access token expires     |
   |                              |
   |  2. POST /refresh-token      |
   |----------------------------->|
   |                              |
   |                              |  3. Validate refresh token
   |                              |  4. Check device fingerprint
   |                              |  5. Generate new tokens
   |                              |  6. Store new refresh token
   |                              |  7. Revoke old refresh token
   |                              |
   |  8. Return new tokens + update cookie
   |<-----------------------------|
```

### 3. WebSocket Authentication

```
Frontend                 Backend Middleware
   |                              |
   |  1. Connect to WebSocket     |
   |----------------------------->|
   |  (Browser auto-sends cookie) |
   |                              |
   |                              |  2. Extract token from cookie
   |                              |  3. Validate JWT signature
   |                              |  4. Decode user data
   |                              |
   |  5. Connection accepted      |
   |<-----------------------------|
   |                              |
   |  6. WebSocket messages       |
   |<---------------------------->|
```

**Note:** No manual token passing needed. Browser automatically includes cookies in WebSocket handshake.

---

## JWT Token Structure

### Access Token (JWT)

**Algorithm:** RS256 (RSA Signature with SHA-256)  
**Expiry:** 5 minutes  
**Storage:** HttpOnly cookie

**Payload (`JWTPayload`):**

```python
{
    "user_id": "USER-1",           # User identifier
    "email": "user@example.com",   # User email
    "full_name": "John Doe",       # Full name (nullable)
    "picture": "https://...",      # Profile picture URL (nullable)
    "exp": 1731588000,             # Expiration timestamp
    "iat": 1731587700              # Issued at timestamp
}
```

**Usage:** All authenticated endpoints receive `UserData` from middleware:

```python
from trading_api.models.auth import UserData
from trading_api.shared.middleware.auth import get_current_user

@router.get("/protected")
async def protected_endpoint(
    user_data: Annotated[UserData, Depends(get_current_user)]
) -> dict:
    return {"user_id": user_data.user_id, "email": user_data.email}
```

### Refresh Token

**Format:** Opaque (URL-safe base64)  
**Length:** 32 bytes (~43 characters)  
**Storage:** localStorage (frontend)  
**Hashing:** bcrypt (12 rounds)

**Stored Data (`RefreshTokenData`):**

```python
{
    "token_id": "RT-1",
    "user_id": "USER-1",
    "token_hash": "$2b$12$...",     # Bcrypt hash
    "created_at": "2025-11-14T...",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0 ...",
    "fingerprint": "a3f8c2..."       # SHA256 hash of IP + User-Agent
}
```

---

## Cookie-Based Authentication

### Cookie Configuration

**Name:** `access_token`  
**Flags:**

- `httponly=True` - JavaScript cannot access (XSS protection)
- `secure=True` - HTTPS only (production)
- `samesite="strict"` - CSRF protection
- `max_age=300` - 5 minutes (matches token expiry)

### Security Benefits

1. **XSS Protection**: HttpOnly prevents JavaScript access to tokens
2. **CSRF Protection**: SameSite=Strict blocks cross-site requests
3. **Automatic Handling**: Browser sends cookies automatically (REST + WebSocket)
4. **No Manual Management**: Frontend never touches access tokens

### CORS Configuration

**Required Settings:**

```python
# backend/src/trading_api/shared/config.py
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGINS = ["http://localhost:5173"]  # Frontend URL
```

---

## Shared Middleware

**Location:** `backend/src/trading_api/shared/middleware/auth.py`

**⚠️ CRITICAL:** This module is INDEPENDENT of the auth module.

- NO database queries
- NO private key access (public key only)
- Stateless validation only

### Functions

#### `get_current_user(request: Request) -> UserData`

Validates JWT from cookie and returns user data.

**Process:**

1. Extract token from `request.cookies.get("access_token")`
2. Decode JWT with public key (RS256)
3. Validate payload structure with `JWTPayload.model_validate()`
4. Extract device fingerprint from request
5. Return `UserData` object

**Errors:** `HTTPException(401)` if token missing, invalid, or expired

#### `get_current_user_ws(websocket: WebSocket) -> UserData`

WebSocket-specific authentication (same process, different exception type).

**Errors:** `WebSocketException(1008)` if authentication fails

#### `extract_device_fingerprint(request: Request | WebSocket) -> str`

Generates SHA256 hash of IP address + User-Agent.

**Format:** 32-character hex string

---

## Device Fingerprinting

### Purpose

Prevent refresh token theft by validating device context.

### Implementation

```python
def extract_device_fingerprint(request: Request) -> str:
    components = [
        request.client.host,                    # IP address
        request.headers.get("user-agent", "unknown")
    ]
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]
```

### Validation

Refresh tokens can only be used from the device where they were issued:

```python
stored_token = await repository.get_token(token_hash, current_fingerprint)
if not stored_token:
    raise HTTPException(401, "Invalid token or device mismatch")
```

### Production Enhancement

For production, add more entropy:

- Accept-Language header
- Accept-Encoding header
- Screen resolution (from client)
- Timezone offset

---

## Testing

### Test Coverage

**Total:** 92 tests (100% passing)

| Layer       | Tests | File                                               |
| ----------- | ----- | -------------------------------------------------- |
| Repository  | 19    | `tests/test_repository.py`                         |
| Service     | 14    | `tests/test_service.py`                            |
| Middleware  | 21    | `tests/unit/test_auth_middleware.py`               |
| API         | 18    | `tests/test_api.py`                                |
| Integration | 10    | `tests/integration/test_auth_integration.py`       |
| Broker Auth | 10    | `modules/broker/tests/test_api_broker.py` (subset) |

### Test Strategy

#### Unit Tests

**Repository Tests:**

```bash
pytest src/trading_api/modules/auth/tests/test_repository.py -v
```

Tests: CRUD operations, concurrent access, secondary indexes

**Service Tests:**

```bash
pytest src/trading_api/modules/auth/tests/test_service.py -v
```

Tests: Google OAuth verification, token generation, refresh rotation, logout

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

**Middleware Tests:**

```bash
pytest backend/tests/unit/test_auth_middleware.py -v
```

Tests: JWT validation, device fingerprint, expired tokens, malformed tokens

#### Integration Tests

```bash
pytest backend/tests/integration/test_auth_integration.py -v
```

Tests:

- Full login → access → refresh → logout flow
- Concurrent refresh requests
- Device fingerprint mismatch
- Token tampering detection
- WebSocket authentication

#### Authenticated Endpoint Tests

**Example from broker module:**

```python
@pytest.fixture
def auth_headers(valid_jwt_token):
    """Fixture providing authentication headers"""
    return {"Authorization": f"Bearer {valid_jwt_token}"}

async def test_get_orders_authenticated(
    client: AsyncClient,
    auth_headers: dict[str, str]
):
    response = await client.get("/api/v1/broker/orders", headers=auth_headers)
    assert response.status_code == 200
```

---

## Production Migration

### Current State (MVP)

- ✅ In-memory user storage (thread-safe)
- ✅ In-memory refresh token storage (thread-safe)
- ⚠️ Data lost on server restart
- ⚠️ No persistence across deployments
- ⚠️ Single-server only (no horizontal scaling)

### Production Requirements

#### 1. User Storage → PostgreSQL

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

#### 2. Refresh Token Storage → Redis

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

#### 3. Additional Production Hardening

- [ ] Rate limiting on `/login` endpoint
- [ ] Refresh token cleanup job (if not using Redis TTL)
- [ ] Token blacklist for emergency revocation
- [ ] Production RSA key pair (4096-bit)
- [ ] Key rotation strategy
- [ ] Monitoring and alerts
- [ ] Enhanced device fingerprinting
- [ ] Anomaly detection (unusual login patterns)

---

## Security Considerations

### Current Implementation

✅ **Strengths:**

- HttpOnly cookies prevent XSS token theft
- SameSite=Strict prevents CSRF attacks
- Bcrypt hashing for refresh tokens (12 rounds)
- RS256 JWT signature (asymmetric cryptography)
- Device fingerprinting for refresh tokens
- Token rotation on refresh
- Stateless middleware (public key only)
- Short access token expiry (5 minutes)

⚠️ **Limitations (MVP):**

- In-memory storage (no persistence)
- Basic device fingerprinting (IP + User-Agent only)
- No rate limiting
- No anomaly detection
- No token blacklist

### Best Practices

1. **Never log tokens** (access or refresh)
2. **Rotate refresh tokens** on every use
3. **Validate audience and issuer** in JWT claims
4. **Use separate keys** for development and production
5. **Monitor failed authentication attempts**
6. **Implement progressive delays** for repeated failures
7. **Revoke all tokens** on password change (if adding password auth)

---

## Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=.local/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=.local/secrets/jwt_public.pem
ACCESS_TOKEN_EXPIRE_MINUTES=5

# Google OAuth
GOOGLE_CLIENT_ID=1002931823122-xxx.apps.googleusercontent.com

# CORS (for cookie credentials)
CORS_ALLOW_CREDENTIALS=true
CORS_ORIGINS=http://localhost:5173

# Cookie Security
COOKIE_SECURE=true  # Set to false for local development (HTTP)
```

### Key Generation

```bash
# Generate RSA key pair
mkdir -p backend/.local/secrets
openssl genrsa -out backend/.local/secrets/jwt_private.pem 4096
openssl rsa -in backend/.local/secrets/jwt_private.pem -pubout -out backend/.local/secrets/jwt_public.pem
chmod 600 backend/.local/secrets/jwt_private.pem
chmod 644 backend/.local/secrets/jwt_public.pem
```

---

## Usage Examples

### Backend: Protected Endpoint

```python
from typing import Annotated
from fastapi import Depends
from trading_api.models.auth import UserData
from trading_api.shared.middleware.auth import get_current_user

@router.get("/my-orders")
async def get_my_orders(
    user_data: Annotated[UserData, Depends(get_current_user)]
) -> list[Order]:
    """Get orders for authenticated user"""
    return await order_service.get_user_orders(user_data.user_id)
```

### Frontend: Using Auth Service

```typescript
import { useAuthService } from "@/services/authService";

const authService = useAuthService();

// Check authentication status
const isAuthenticated = await authService.checkAuthStatus();

// Login with Google token
await authService.loginWithGoogleToken(googleToken);

// Logout
await authService.logout();

// Reactive state
console.log(authService.isLoading.value); // Loading state
console.log(authService.error.value); // Error message
```

---

## Troubleshooting

### Common Issues

#### 1. "Missing authentication token in cookie"

**Cause:** Access token not set or expired

**Solution:**

- Check browser cookies (DevTools → Application → Cookies)
- Verify backend sets cookie on `/login` response
- Check CORS configuration allows credentials

#### 2. "Invalid token: Signature verification failed"

**Cause:** Public/private key mismatch

**Solution:**

- Verify keys generated correctly
- Check `JWT_PRIVATE_KEY_PATH` and `JWT_PUBLIC_KEY_PATH` in `.env.local`
- Ensure middleware uses correct public key

#### 3. "Invalid token or device mismatch"

**Cause:** Refresh token used from different device

**Solution:**

- Device fingerprint changed (IP or User-Agent)
- Expected behavior for security
- User must login again

#### 4. "Google token verification failed"

**Cause:** Invalid or expired Google ID token

**Solution:**

- Check `GOOGLE_CLIENT_ID` matches Google Console configuration
- Verify Google token not expired (1-hour lifetime)
- Check internet connectivity (authlib needs to fetch Google's public keys)

---

## Related Documentation

- [Modular Backend Architecture](../../docs/MODULAR_BACKEND_ARCHITECTURE.md)
- [Backend WebSockets](../../docs/BACKEND_WEBSOCKETS.md)
- [Backend Testing](../../docs/BACKEND_TESTING.md)
- [Authentication Guide](../../../docs/AUTHENTICATION.md) (comprehensive cross-cutting guide)
- [Frontend Auth Service](../../../frontend/src/services/README.md)

---

**Last Updated:** November 14, 2025  
**Maintained by:** Development Team
