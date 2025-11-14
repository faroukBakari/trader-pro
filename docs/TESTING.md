# Testing Strategy

## Overview

Trading Pro uses a multi-tier testing approach that enables independent testing of backend and frontend components, with integration tests verifying end-to-end behavior.

## Testing Philosophy

### Independent Components

- **Backend Tests**: Run without frontend
- **Frontend Tests**: Run without backend
- **Integration Tests**: Verify complete system

### Benefits

- ✅ Fast feedback loops
- ✅ Parallel CI/CD execution
- ✅ No external dependencies for unit tests
- ✅ Reliable test results

## Backend Testing

### Running Tests

```bash
cd backend
make test      # Run all tests
make test-cov  # With coverage report
```

### Test Framework

- **pytest**: Test runner
- **pytest-asyncio**: Async support
- **httpx TestClient**: API testing without HTTP server

### Example Test

```python
from httpx import AsyncClient
from trading_api.main import app

async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

### What's Tested

- ✅ API endpoint responses
- ✅ Data validation and serialization
- ✅ Business logic
- ✅ WebSocket operations
- ✅ Error handling

### No Dependencies

Backend tests use FastAPI's TestClient:

- No HTTP server needed
- No database connections
- Pure Python testing
- Fast execution (< 1 second)

## Frontend Testing

### Running Tests

```bash
cd frontend
make test  # Run once
make test      # Watch mode
```

### Test Framework

- **Vitest**: Test runner
- **Vue Test Utils**: Component testing
- **jsdom**: DOM simulation

### Example Test

```typescript
import { mount } from "@vue/test-utils";
import ApiStatus from "@/components/ApiStatus.vue";

describe("ApiStatus", () => {
  it("displays health status", async () => {
    const wrapper = mount(ApiStatus);
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("ok");
  });
});
```

### What's Tested

- ✅ Component rendering
- ✅ User interactions
- ✅ Service layer with mocks
- ✅ Router navigation
- ✅ State management

### Automatic Mocks

Frontend uses mock data when:

- Generated clients unavailable
- Backend not running
- During unit tests

## Integration Testing

### Prerequisites

```bash
# Start backend first
cd backend && make dev
```

### Running Integration Tests

```bash
make -f project.mk test-integration
```

### What's Tested

- ✅ Client generation from live API
- ✅ Type safety with generated clients
- ✅ Real HTTP communication
- ✅ WebSocket connections
- ✅ End-to-end data flow

### Integration Test Example

```typescript
describe("API Integration", () => {
  it("fetches real health data", async () => {
    const health = await apiService.getHealth();

    expect(health.status).toBe("ok");
    expect(health.version).toBeDefined();
  });
});
```

## Authentication Testing

### Overview

The authentication system has comprehensive test coverage (92 tests) across multiple layers:

- Repository tests (19)
- Service tests (14)
- Middleware tests (21)
- API tests (18)
- Integration tests (10)
- Module-specific authenticated endpoint tests (10)

### Backend Authentication Tests

**Test Organization:**

```
backend/
├── src/trading_api/modules/auth/tests/
│   ├── conftest.py                    # Auth fixtures
│   ├── test_repository.py             # Repository tests
│   ├── test_service.py                # Service tests
│   └── test_api.py                    # API tests
├── tests/unit/
│   └── test_auth_middleware.py        # Middleware tests
└── tests/integration/
    └── test_auth_integration.py       # Integration tests
```

**Running Auth Tests:**

```bash
# All auth module tests
cd backend
pytest src/trading_api/modules/auth/tests/ -v

# Middleware tests
pytest tests/unit/test_auth_middleware.py -v

# Integration tests
pytest tests/integration/test_auth_integration.py -v
```

### Mocking Google OAuth

**Pattern:** Use `monkeypatch` to mock Google OAuth verification:

```python
@pytest.fixture
def mock_google_oauth(monkeypatch):
    """Mock Google OAuth token verification."""
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
    return mock_parse_id_token
```

**Usage:**

```python
async def test_login_with_google(client, mock_google_oauth):
    """Test login with mocked Google OAuth."""
    response = await client.post("/api/v1/auth/login", json={
        "google_token": "mock_google_token"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "access_token" in response.cookies
```

### Testing JWT Tokens

**Creating Test Tokens:**

```python
from datetime import datetime, timedelta
import jwt

@pytest.fixture
def valid_jwt_token(test_user):
    """Generate valid JWT token for testing."""
    payload = {
        "user_id": test_user.id,
        "email": test_user.email,
        "full_name": test_user.full_name,
        "picture": test_user.picture,
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

@pytest.fixture
def expired_jwt_token(test_user):
    """Generate expired JWT token for testing."""
    payload = {
        "user_id": test_user.id,
        "email": test_user.email,
        "exp": datetime.utcnow() - timedelta(minutes=5),  # Expired
        "iat": datetime.utcnow() - timedelta(minutes=10)
    }
    return jwt.encode(payload, private_key, algorithm="RS256")
```

**Testing Protected Endpoints:**

```python
async def test_authenticated_endpoint(client, valid_jwt_token):
    """Test accessing protected endpoint with valid token."""
    response = await client.get(
        "/api/v1/broker/orders",
        cookies={"access_token": valid_jwt_token}
    )
    assert response.status_code == 200

async def test_unauthenticated_endpoint(client):
    """Test accessing protected endpoint without token."""
    response = await client.get("/api/v1/broker/orders")
    assert response.status_code == 401
    assert "Missing authentication token" in response.json()["detail"]

async def test_expired_token(client, expired_jwt_token):
    """Test accessing protected endpoint with expired token."""
    response = await client.get(
        "/api/v1/broker/orders",
        cookies={"access_token": expired_jwt_token}
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
```

### Testing Refresh Token Flow

```python
async def test_refresh_token_flow(client, mock_google_oauth):
    """Test complete token refresh flow."""
    # 1. Login
    login_response = await client.post("/api/v1/auth/login", json={
        "google_token": "mock_token"
    })
    refresh_token = login_response.json()["refresh_token"]

    # 2. Wait for access token to expire (or mock time)
    # ...

    # 3. Refresh token
    refresh_response = await client.post("/api/v1/auth/refresh-token", json={
        "refresh_token": refresh_token
    })
    assert refresh_response.status_code == 200

    new_access_token = refresh_response.cookies.get("access_token")
    new_refresh_token = refresh_response.json()["refresh_token"]

    # 4. Old refresh token should be revoked
    old_refresh_response = await client.post("/api/v1/auth/refresh-token", json={
        "refresh_token": refresh_token
    })
    assert old_refresh_response.status_code == 401

    # 5. New tokens should work
    protected_response = await client.get("/api/v1/broker/orders")
    assert protected_response.status_code == 200
```

### Testing Device Fingerprinting

```python
async def test_device_fingerprint_validation(client, mock_google_oauth):
    """Test refresh token requires same device."""
    # Login from device 1
    response1 = await client.post(
        "/api/v1/auth/login",
        json={"google_token": "mock_token"},
        headers={"User-Agent": "Device1", "X-Forwarded-For": "192.168.1.1"}
    )
    refresh_token = response1.json()["refresh_token"]

    # Try refresh from device 2 (different IP/User-Agent)
    response2 = await client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": refresh_token},
        headers={"User-Agent": "Device2", "X-Forwarded-For": "192.168.1.2"}
    )
    assert response2.status_code == 401
    assert "device mismatch" in response2.json()["detail"].lower()
```

### Frontend Authentication Tests

**Test Organization:**

```
frontend/
└── src/services/tests/
    ├── authService.spec.ts            # Service unit tests
    └── authService.integration.spec.ts # Integration tests
```

**Mocking Auth Service:**

```typescript
import { vi } from "vitest";
import { useAuthService } from "@/services/authService";

describe("authService", () => {
  it("should login successfully", async () => {
    const authService = useAuthService();

    // Mock API response
    vi.spyOn(authService.apiAdapter, "loginWithGoogleToken").mockResolvedValue({
      access_token: "jwt_token",
      refresh_token: "refresh_token",
      token_type: "bearer",
      expires_in: 300,
    });

    await authService.loginWithGoogleToken("google_token");

    expect(authService.error.value).toBeNull();
  });

  it("should handle login errors", async () => {
    const authService = useAuthService();

    vi.spyOn(authService.apiAdapter, "loginWithGoogleToken").mockRejectedValue(
      new Error("Invalid token")
    );

    await authService.loginWithGoogleToken("invalid_token");

    expect(authService.error.value).toContain("Invalid token");
  });
});
```

**Testing Router Guards:**

```typescript
import { describe, it, expect, vi } from "vitest";
import { createRouter } from "@/router";
import { useAuthService } from "@/services/authService";

describe("authentication guards", () => {
  it("should redirect to login when not authenticated", async () => {
    const router = createRouter();
    const authService = useAuthService();

    // Mock unauthenticated state
    vi.spyOn(authService, "checkAuthStatus").mockResolvedValue(false);

    await router.push("/broker");

    expect(router.currentRoute.value.path).toBe("/login");
    expect(router.currentRoute.value.query.redirect).toBe("/broker");
  });

  it("should allow access when authenticated", async () => {
    const router = createRouter();
    const authService = useAuthService();

    // Mock authenticated state
    vi.spyOn(authService, "checkAuthStatus").mockResolvedValue(true);

    await router.push("/broker");

    expect(router.currentRoute.value.path).toBe("/broker");
  });
});
```

### WebSocket Authentication Tests

**Testing WebSocket Cookie Authentication:**

```python
async def test_websocket_authentication(client, valid_jwt_token):
    """Test WebSocket connection with valid cookie."""
    async with client.websocket_connect(
        "/api/v1/broker/ws",
        cookies={"access_token": valid_jwt_token}
    ) as ws:
        # Connection established successfully
        await ws.send_json({
            "type": "orders.subscribe",
            "payload": {"orderId": "123"}
        })

        response = await ws.receive_json()
        assert response["type"] == "orders.subscribe.response"
        assert response["payload"]["status"] == "ok"

async def test_websocket_without_authentication(client):
    """Test WebSocket connection without authentication."""
    with pytest.raises(WebSocketException) as exc:
        async with client.websocket_connect("/api/v1/broker/ws"):
            pass

    assert exc.value.code == 1008  # Policy Violation
    assert "authentication" in exc.value.reason.lower()
```

### Best Practices

**Backend:**

1. **Use Fixtures**: Create reusable test fixtures for users, tokens, and auth data
2. **Mock External Services**: Always mock Google OAuth (don't make real API calls)
3. **Test Negative Cases**: Test expired tokens, invalid tokens, missing tokens
4. **Test Device Fingerprinting**: Verify refresh tokens tied to devices
5. **Test Token Rotation**: Ensure old refresh tokens are invalidated

**Frontend:**

1. **Mock API Calls**: Use `vi.spyOn()` to mock auth service methods
2. **Test Loading States**: Verify loading indicators during auth operations
3. **Test Error States**: Check error message display
4. **Test Router Guards**: Verify redirect behavior for protected routes
5. **Test Cookie Handling**: Ensure cookies are included in requests

**Integration:**

1. **Test Complete Flows**: Login → Access → Refresh → Logout
2. **Test Concurrent Requests**: Multiple simultaneous authenticated requests
3. **Test Token Expiry**: Access token expiration and refresh
4. **Test WebSocket Auth**: Cookie authentication in WebSocket handshake

### Running Complete Auth Test Suite

```bash
# Backend (92 tests)
cd backend
pytest src/trading_api/modules/auth/tests/ -v
pytest tests/unit/test_auth_middleware.py -v
pytest tests/integration/test_auth_integration.py -v

# Frontend
cd frontend
npm run test -- authService

# All tests
make -f project.mk test-all
```

See [AUTHENTICATION.md](./AUTHENTICATION.md) for complete authentication system documentation.

## CI/CD Testing

### Parallel Execution

```yaml
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - run: make install-ci
      - run: make test
      - run: make type-check

  frontend:
    runs-on: ubuntu-latest
    steps:
      - run: make install-ci
      - run: make test
      - run: make lint

  integration:
    needs: [backend, frontend]
    runs-on: ubuntu-latest
    steps:
      - run: make test-integration
```

### Benefits

- Jobs run in parallel
- Fast feedback (2-3 minutes total)
- Clear failure isolation

## Test Coverage

### Backend Coverage

```bash
cd backend
make test-cov

# Generates coverage.xml and terminal report
```

**Target**: 80%+ code coverage

### Frontend Coverage

```bash
cd frontend
npm run test:coverage
```

## Testing Best Practices

### 1. Test Isolation

Each test should be independent:

```python
# Good
async def test_health():
    async with AsyncClient(app=app) as client:
        response = await client.get("/health")
    assert response.status_code == 200

# Bad - relies on external state
def test_health():
    response = global_client.get("/health")
```

### 2. Use Mocks for External Dependencies

```typescript
// Good - mock external API
vi.mock("@/services/apiService", () => ({
  getHealth: () => Promise.resolve({ status: "ok" }),
}));

// Bad - requires real backend
const health = await fetch("http://localhost:8000/health");
```

### 3. Keep Tests Fast

- Unit tests: < 100ms each
- Component tests: < 500ms each
- Integration tests: < 5s each

### 4. Test Behavior, Not Implementation

```typescript
// Good - test behavior
expect(wrapper.text()).toContain("Connected");

// Bad - test implementation
expect(wrapper.vm.isConnected).toBe(true);
```

## Test Organization

### Backend Structure

```
backend/tests/
├── test_api_health.py
├── test_api_versioning.py
├── test_ws_datafeed.py
└── test_bar_broadcaster.py
```

### Frontend Structure

```
frontend/src/
├── components/__tests__/
├── services/__tests__/
└── test-setup.ts
```

## WebSocket Testing

### Backend WebSocket Tests

```python
def test_bars_subscription():
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json({
            "type": "bars.subscribe",
            "payload": {"symbol": "AAPL", "resolution": "1"}
        })

        response = ws.receive_json()
        assert response["type"] == "bars.subscribe.response"
```

### Frontend WebSocket Tests

```typescript
import { WsAdapter } from "@/plugins/wsAdapter";

describe("WebSocket Client", () => {
  it("subscribes to bar updates", async () => {
    const adapter = new WsAdapter();
    const callback = vi.fn();

    await adapter.bars.subscribe(
      "test-listener",
      { symbol: "AAPL", resolution: "1" },
      callback
    );

    expect(callback).toHaveBeenCalled();
  });
});
```

## Debugging Tests

### Backend

```bash
# Run specific test with verbose output
cd backend
poetry run pytest tests/test_health.py -v -s

# Run with debugger
poetry run pytest tests/test_health.py --pdb
```

### Frontend

```bash
# Run specific test file
cd frontend
npm run test:unit -- ApiStatus.spec.ts

# Run with UI
npm run test:ui
```

## Smoke Tests

End-to-end tests using Playwright:

```bash
cd smoke-tests
npm install
npm test
```

Tests critical user workflows in a real browser.

## Test Execution Matrix

| Component     | Dependencies       | Speed        | When to Run  |
| ------------- | ------------------ | ------------ | ------------ |
| Backend Unit  | None               | ⚡ Very Fast | Every commit |
| Frontend Unit | None               | ⚡ Very Fast | Every commit |
| Integration   | Backend + Frontend | 🐢 Slower    | PR + Main    |
| Smoke Tests   | Full Stack         | 🐌 Slowest   | Pre-release  |

## Continuous Testing

### Watch Mode

```bash
# Backend
cd backend && poetry run pytest-watch

# Frontend
cd frontend && make test
```

### Pre-commit Testing

Git hooks automatically run tests before commit:

```bash
# Skip for emergencies
git commit --no-verify
```

## Related Documentation

- **Architecture**: See `ARCHITECTURE.md`
- **Development Guide**: See `docs/DEVELOPMENT.md`
- **CI/CD**: See `.github/workflows/ci.yml`
