# Auth Module

**Version:** 1.1.0  
**Status:** ✅ Production Ready (MVP with In-Memory Storage)  
**Last Updated:** November 30, 2025

JWT-based authentication module with Google OAuth integration, cookie-based session management, and device fingerprinting.

> **📖 Full Documentation**: See [Authentication System](../../../docs/AUTHENTICATION.md) for comprehensive architecture, security, frontend integration, and production migration guides.

---

## Quick Reference

### Module Structure

```
modules/auth/
├── api/v1.py          # REST endpoints (/login, /me, /introspect, etc.)
├── repository.py      # UserRepository, RefreshTokenRepository (in-memory)
├── service.py         # AuthService (JWT generation, Google OAuth)
├── tests/             # 56+ tests (repository, service, API)
└── README.md          # This file
```

### API Endpoints

| Endpoint                     | Method | Auth | Description                    |
| ---------------------------- | ------ | ---- | ------------------------------ |
| `/api/v1/auth/login`         | POST   | No   | Authenticate with Google OAuth |
| `/api/v1/auth/refresh-token` | POST   | No   | Refresh access token           |
| `/api/v1/auth/logout`        | POST   | No   | Logout and revoke token        |
| `/api/v1/auth/me`            | GET    | Yes  | Get current user info          |
| `/api/v1/auth/introspect`    | GET    | Yes  | Validate token (router guards) |

### Key Components

| Component                         | Purpose                                                   |
| --------------------------------- | --------------------------------------------------------- |
| `AuthService`                     | Business logic, JWT generation, Google OAuth verification |
| `UserRepositoryInterface`         | User CRUD (in-memory MVP)                                 |
| `RefreshTokenRepositoryInterface` | Token storage with device fingerprinting                  |
| Shared middleware                 | `get_current_user()`, `get_current_user_ws()`             |

---

## Service Layer Details

### AuthService Capabilities

```python
@classmethod
def capabilities(cls) -> list[CapabilitySpec]:
    return [CapabilitySpec(name="auth")]
```

### Key Methods

| Method                       | Description                                              |
| ---------------------------- | -------------------------------------------------------- |
| `authenticate_google_user()` | Verify Google token, create/update user, generate tokens |
| `refresh_access_token()`     | Validate refresh token, rotate tokens                    |
| `logout()`                   | Revoke refresh token (silent failure)                    |

### Token Generation

- **Access Token**: RS256 JWT, 5-minute expiry, stored in HttpOnly cookie
- **Refresh Token**: 64-byte opaque token, SHA256 hashed, 7-day expiry

**[DECISION]**: SHA256 used instead of bcrypt to avoid 72-byte input limit issues.

---

## Repository Interfaces

### UserRepositoryInterface

```python
get_by_id(user_id: str) -> User | None
get_by_email(email: str) -> User | None
get_by_google_id(google_id: str) -> User | None
create(user_data: CreateUserData) -> User
update_last_login(user_id: str) -> None
```

### RefreshTokenRepositoryInterface

```python
store_token(token_data: RefreshTokenData) -> None
get_token(token_hash: str, fingerprint: str) -> RefreshTokenData | None
revoke_token(token_hash: str) -> None
revoke_all_user_tokens(user_id: str) -> None
```

**MVP Implementation**: In-memory thread-safe storage.  
**Production**: PostgreSQL for users, Redis for refresh tokens.

---

## Testing

### Test Coverage: 83 tests

```bash
# All auth tests
cd backend && pytest src/trading_api/modules/auth/tests/ -v

# Middleware tests
cd backend && pytest tests/unit/test_auth_middleware.py -v

# Integration tests
cd backend && pytest tests/integration/test_auth_integration.py -v
```

### Mocking Google OAuth

```python
@pytest.fixture
def mock_google_oauth(monkeypatch):
    async def mock_parse_id_token(token, claims_options):
        return {"sub": "123", "email": "test@example.com", "email_verified": True}
    monkeypatch.setattr(
        "authlib.integrations.starlette_client.OAuth.google.parse_id_token",
        mock_parse_id_token
    )
```

---

## Configuration

```bash
# JWT
JWT_PRIVATE_KEY_PATH=.local/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=.local/secrets/jwt_public.pem
ACCESS_TOKEN_EXPIRE_MINUTES=5

# Google OAuth
GOOGLE_CLIENT_ID=...

# Cookie
COOKIE_SECURE=true
```

### Key Generation

```bash
mkdir -p backend/.local/secrets
openssl genrsa -out backend/.local/secrets/jwt_private.pem 4096
openssl rsa -in backend/.local/secrets/jwt_private.pem -pubout -out backend/.local/secrets/jwt_public.pem
```

---

## Related Documentation

- **[Authentication System](../../../docs/AUTHENTICATION.md)** - Full cross-cutting guide
- **[Provider System](../../../docs/PROVIDER-SYSTEM.md)** - Capability pattern
- **[Modular Backend Architecture](../../../docs/MODULAR_BACKEND_ARCHITECTURE.md)**
- **[Frontend Auth Service](../../../../../frontend/src/services/README.md)**

---

**Last Updated:** November 30, 2025
