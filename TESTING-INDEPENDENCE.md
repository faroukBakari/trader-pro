# Testing Independence Guide

## Overview

This document explains how the backend and frontend can be tested independently, with mocked data when needed, and how integration tests verify the complete system.

## Testing Philosophy

### Separation of Concerns

1. **Backend Tests**: Test API endpoints, business logic, and data models independently
2. **Frontend Tests**: Test UI components, services, and user interactions with mocked API responses
3. **Integration Tests**: Verify end-to-end behavior with real API and client generation

### Benefits

- ✅ **Fast Feedback**: Unit tests run quickly without external dependencies
- ✅ **Parallel Development**: Frontend and backend teams can work independently
- ✅ **CI/CD Efficiency**: Jobs can run in parallel without coordination
- ✅ **Reliability**: Tests don't fail due to network issues or unavailable services

## Backend Testing (Independent)

### Running Backend Tests

```bash
cd backend
make test          # Run all tests
make test-cov      # Run with coverage
make lint-check    # Code quality checks
```

### What's Tested

- ✅ API endpoint responses (using FastAPI TestClient)
- ✅ Data validation and serialization
- ✅ Business logic and versioning
- ✅ OpenAPI specification generation
- ✅ Error handling

### No Dependencies Required

Backend tests use FastAPI's `TestClient` which:
- Creates an in-memory ASGI app
- No actual HTTP server needed
- No database connections
- No external API calls
- Pure Python testing

### Example Backend Test

```python
from httpx import AsyncClient
from trading_api.main import app

async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

## Frontend Testing (Independent)

### Running Frontend Tests

```bash
cd frontend
make test-run      # Run all tests once
make test          # Run in watch mode
make lint          # Code quality checks
```

### What's Tested

- ✅ Vue component rendering and behavior
- ✅ API service layer with mocked responses
- ✅ Router navigation
- ✅ State management
- ✅ User interactions
- ✅ Error handling

### Automatic Mock Fallback

The frontend automatically uses mocked data when:
- Generated API client is not available
- Backend is not running
- During unit tests

### Example Frontend Test

```typescript
import { apiService } from '@/services/apiService'

describe('API Service', () => {

  it('returns health status with mock data', async () => {
    const health = await apiService.getHealth()

    expect(health.status).toBe('ok')
    expect(health.api_version).toBe('v1')
  })
})
```

## Integration Testing

Integration tests verify the complete system with real components.

### Prerequisites

```bash
# Terminal 1: Start backend
cd backend
make dev

# Terminal 2: Run integration tests
cd frontend
npm run client:generate  # Generates real client
npm run test:unit        # Tests use generated client
```

### What's Tested

- ✅ Client generation from live OpenAPI spec
- ✅ Type safety with generated TypeScript client
- ✅ Real HTTP communication
- ✅ End-to-end data flow
- ✅ API contract validation

### CI/CD Integration Testing

```yaml
# GitHub Actions example
integration:
  runs-on: ubuntu-latest
  needs: [backend, frontend]

  steps:
    - name: Start backend
      working-directory: backend
      run: make dev-ci

    - name: Test API endpoints
      working-directory: backend
      run: make health-ci

    - name: Generate frontend client
      working-directory: frontend
      run: npm run client:generate

    - name: Build frontend with real client
      working-directory: frontend
      run: npm run build
```

## Test Execution Matrix

### Backend Only (No Frontend)

```bash
cd backend

✅ make install    # Install dependencies
✅ make test       # All tests pass
✅ make lint-check # Code quality passes
✅ make build      # Package builds
```

**No generated clients needed!**

### Frontend Only (No Backend)

```bash
cd frontend

✅ npm install           # Install dependencies
✅ npm run test:unit run # All tests pass with mocks
✅ npm run lint          # Code quality passes
✅ npm run build         # Build succeeds with mock fallback
```

**No backend server needed!**

### Full Integration

```bash
# Start backend
cd backend && make dev

# In another terminal
cd frontend

✅ npm run client:generate  # Generates real TypeScript client
✅ npm run dev              # Runs with type-safe API calls
✅ npm run build            # Builds with real client
```

**Type safety and real API communication!**

## CI/CD Pipeline Strategy

### Parallel Jobs (Fast)

```
┌─────────────┐     ┌──────────────┐
│   Backend   │     │   Frontend   │
│             │     │              │
│ • Install   │     │ • Install    │
│ • Test      │     │ • Test       │
│ • Lint      │     │ • Lint       │
│ • Build     │     │ • Build      │
└─────────────┘     └──────────────┘
       │                   │
       └────────┬──────────┘
                │
        ┌───────▼────────┐
        │  Integration   │
        │                │
        │ • Start Backend│
        │ • Gen Client   │
        │ • E2E Tests    │
        └────────────────┘
```

### Benefits

1. **Fast Execution**: Parallel jobs complete in ~2-3 minutes
2. **Early Feedback**: Unit tests fail fast before integration
3. **Resource Efficient**: No idle waiting for dependencies
4. **Clear Failures**: Know exactly which layer failed

## File Ignore Strategy

### Backend `.gitignore`

```gitignore
# Auto-generated files
clients/
openapi.json
openapi-3.0.json
.openapi-checksum
```

### Frontend `.gitignore`

```gitignore
# Auto-generated client
src/services/generated/

# OpenAPI artifacts
openapi.json
openapitools.json
```

### Why Ignore Generated Files?

1. **Deterministic**: Can be regenerated from source
2. **Clean Diffs**: No noise in pull requests
3. **No Conflicts**: Avoid merge conflicts in generated code
4. **Fresh Builds**: Always use latest API spec

## Development Workflows

### Scenario 1: Backend Developer

```bash
# Work on backend only
cd backend

# Make changes to API
vim src/trading_api/api/health.py

# Test changes
make test

# Run server (optional)
make dev
```

**No frontend interaction needed!**

### Scenario 2: Frontend Developer

```bash
# Work on frontend only
cd frontend

# Make changes to components
vim src/components/ApiStatus.vue

# Test with mocks
npm run test:unit

# Preview UI (with mocks)
npm run dev
```

**No backend required!**

### Scenario 3: Full-Stack Developer

```bash
# Terminal 1: Backend
cd backend
make dev

# Terminal 2: Frontend
cd frontend
npm run dev  # Auto-generates client from live API
```

**Type-safe integration!**

### Scenario 4: API Contract Change

```bash
# 1. Update backend API
cd backend
vim src/trading_api/api/versions.py
make test

# 2. Restart backend
make dev

# 3. Frontend auto-regenerates client
cd frontend
npm run client:generate

# 4. Update frontend to use new types
vim src/components/ApiStatus.vue
npm run test:unit
```

**Smooth API evolution!**

## Troubleshooting

### Backend Tests Fail

```bash
cd backend

# Check Python environment
poetry env info

# Reinstall dependencies
poetry install

# Run specific test
poetry run pytest tests/test_health.py -v
```

### Frontend Tests Fail

```bash
cd frontend

# Clean and reinstall
rm -rf node_modules package-lock.json
npm install

# Run specific test
npm run test:unit -- ApiStatus.spec.ts
```

### Integration Issues

```bash
# Verify backend is running
curl http://localhost:8000/api/v1/health

# Regenerate client
cd frontend
rm -rf src/services/generated
npm run client:generate

# Check generated client
cat src/services/generated/index.ts  # Should be present
```

## Best Practices

### 1. Write Unit Tests First

✅ **Do**: Test components in isolation with mocks
```typescript
const health = await apiService.getHealth()  // Uses mock
expect(health.status).toBe('ok')
```

❌ **Don't**: Require running backend for unit tests
```typescript
const response = await fetch('http://localhost:8000/health')  // Bad!
```

### 2. Use Integration Tests Sparingly

- Unit tests should cover 80%+ of code
- Integration tests verify contracts and workflows
- Keep integration tests fast and focused

### 3. Mock External Dependencies

✅ **Do**: Mock in services layer
```typescript
export class ApiService {
  async getHealth() {
    const client = await getGeneratedClient()
    return client ? await client.getHealth() : mockHealth()
  }
}
```

❌ **Don't**: Mock in components
```typescript
// Component should use service, not fetch directly
const response = await fetch('/api/health')
```

### 4. Keep Tests Fast

- Backend tests: < 1 second
- Frontend tests: < 2 seconds
- Integration tests: < 30 seconds

### 5. Test Isolation

- Each test should be independent
- No shared state between tests
- Clean up after tests

## Summary

| Aspect | Backend | Frontend | Integration |
|--------|---------|----------|-------------|
| **Speed** | ⚡ Very Fast | ⚡ Very Fast | 🐢 Slower |
| **Dependencies** | None | None | Backend + Frontend |
| **Runs On** | Python Only | Node.js Only | Both |
| **Tests** | API Logic | UI/UX | End-to-End |
| **CI Time** | ~30 seconds | ~45 seconds | ~2 minutes |
| **When to Run** | Every commit | Every commit | PR + Main branch |

## Conclusion

This architecture enables:

- ✅ **Independent Development**: Teams work without blocking each other
- ✅ **Fast Feedback**: Tests run in seconds, not minutes
- ✅ **Parallel CI/CD**: Jobs run concurrently
- ✅ **Flexible Testing**: Unit tests with mocks, integration tests with real services
- ✅ **Clean Repository**: No generated files tracked

Both backend and frontend are **self-sufficient** while maintaining **type safety** when integrated.
