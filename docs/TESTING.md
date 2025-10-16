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
make test-run  # Run once
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

## CI/CD Testing

### Parallel Execution

```yaml
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - run: make install-ci
      - run: make test
      - run: make lint-check

  frontend:
    runs-on: ubuntu-latest
    steps:
      - run: make install-ci
      - run: make test-run
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
describe("WebSocket Client", () => {
  it("subscribes to bar updates", async () => {
    const client = BarsWebSocketClientFactory();
    const callback = vi.fn();

    await client.subscribe({ symbol: "AAPL", resolution: "1" }, callback);

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
