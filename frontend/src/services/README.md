# API Services

This directory contains the API service layer for the frontend application.

## Structure

```
src/services/
├── apiService.ts           # Main API service wrapper (use this in components)
├── testIntegration.ts      # Integration test utility
├── generated/              # Auto-generated API client (gitignored)
│   ├── api/               # Generated API classes
│   ├── models/            # Generated TypeScript types
│   ├── client-config.ts   # Pre-configured client instance
│   └── ...
└── __tests__/
    └── apiService.spec.ts  # Unit tests with mocking examples
```

## Usage

### In Components

Use the `apiService` wrapper in your Vue components:

```typescript
import { apiService, type HealthResponse, type APIMetadata } from '@/services/apiService'

// Get health status
const health: HealthResponse = await apiService.getHealth()

// Get API versions
const versions: APIMetadata = await apiService.getVersions()
```

### Resilient Architecture

The API service automatically handles different scenarios:

1. **With Generated Client**: Uses the generated TypeScript client for type safety
2. **Without Generated Client**: Falls back to realistic mock data for development
3. **Generated Client Fails**: Gracefully falls back to mocks if generated client errors

This ensures your app works regardless of whether the generated client is available, and provides realistic data for development and testing.

### Mock Data Features

When using the fallback (mock) implementation:

- 🎭 **Realistic Data**: Returns data that matches the real API structure
- ⏱️ **Network Simulation**: Includes realistic network delays (100-150ms)
- 📊 **Multiple Scenarios**: Provides both stable (v1) and planned (v2) API versions
- 🔧 **Configurable**: Mock behavior can be customized for testing
- 📝 **Logging**: Optional console logs to indicate when mocks are being used

```typescript
import { MOCK_CONFIG } from '@/services/apiService'

// Customize mock behavior
MOCK_CONFIG.networkDelay.health = 50 // Faster for testing
MOCK_CONFIG.enableLogs = false // Quiet during tests
```

### Generated Client (Advanced)

For more control, you can use the generated client directly (when available):

```typescript
import { apiClient } from '@/services/generated/client-config'

// Direct client usage (only works when generated client exists)
const response = await apiClient.getHealthStatus()
const health = response.data
```

## Testing

### Unit Tests with Mocking

The service uses mock data implementation, making it easy to test:

```typescript
import { vi } from 'vitest'
import { apiService, MOCK_CONFIG } from '../apiService'

// Customize mock behavior for testing
MOCK_CONFIG.enableLogs = false
MOCK_CONFIG.networkDelay.health = 0 // No delay for faster tests

// Test the mock responses
const health = await apiService.getHealth()
expect(health.status).toBe('ok')
expect(health.message).toContain('mock data')
```

### Testing Generated Client (When Available)

When the generated client is present, you can mock it specifically:

```typescript
import { vi } from 'vitest'

// Mock the generated client
vi.mock('@/services/generated/client-config', () => ({
  apiClient: {
    getHealthStatus: vi.fn(),
    getAPIVersions: vi.fn(),
  },
}))

// Your test here...
```

### Integration Testing

```typescript
import { testApiIntegration } from '@/services/testIntegration'

// Test with real API (requires backend running)
const success = await testApiIntegration()
```

## Client Generation

The API client is automatically generated from the backend's OpenAPI specification.

**⚠️ Note**: Client generation requires a running backend server and is not part of the build process.

```bash
# Generate client manually (requires backend running)
npm run client:generate

# Watch for API changes and regenerate (development only)
npm run client:watch

# Development with client generation
npm run dev:with-client
```

**For Production Builds**:
- The frontend works without generated client (uses mock data)
- Generate client separately in development/staging environments
- Include generated client files in deployment if needed

## Benefits

1. **🛡️ Type Safety**: Full TypeScript support with generated types (when available)
2. **🔄 Auto-sync**: Client automatically stays in sync with backend API
3. **🧪 Testability**: Easy to mock with native fetch fallback
4. **🚀 Resilient**: Works with or without generated client
5. **📚 Self-documenting**: Generated types serve as documentation
6. **🎯 Maintainability**: Minimal manual API code to maintain

## Architecture Benefits

- **Graceful Degradation**: Missing generated client doesn't break the app
- **Development Friendly**: Tests work without requiring client generation
- **Production Ready**: Automatically uses generated client when available
- **Fail-Safe**: Multiple fallback layers ensure reliability
