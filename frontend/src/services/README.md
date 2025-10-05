# API Services

This directory contains the API service layer for the frontend application.

## Structure

```
src/services/
├── apiService.ts           # Main API service wrapper (use this in components)
├── datafeedService.ts      # TradingView Datafeed service (implement methods)
├── testIntegration.ts      # Integration test utility
├── generated/              # Auto-generated API client (gitignored)
│   ├── api/               # Generated API classes
│   ├── models/            # Generated TypeScript types
│   ├── client-config.ts   # Pre-configured client instance
│   ├── .client-type       # Marker: 'server' or 'mock'
│   └── ...
└── __tests__/
    └── apiService.spec.ts  # Unit tests with mocking examples
```

## DatafeedService

The `DatafeedService` class provides a blank template for implementing the TradingView Charting Library's datafeed interface. All methods are left empty for custom implementation.

### Quick Start

1. **Implement Required Methods**: Add your data fetching logic to each method in `datafeedService.ts`
2. **Connect Data Source**: Hook up to your API, WebSocket, or database
3. **Test Integration**: Verify charts display your data correctly

### Required Methods Implementation

See the [DatafeedService Implementation Guide](#datafeedservice-implementation-guide) below for detailed examples.

## API Services Usage

### In Components

Use the `apiService` wrapper in your Vue components:

```typescript
import { apiService, type HealthResponse, type APIMetadata } from '@/services/apiService'

// Get health status
const health: HealthResponse = await apiService.getHealth()

// Get API versions
const versions: APIMetadata = await apiService.getVersions()
```

### Smart Client Generation

The API client is **automatically generated** when you run the development server or build:

```bash
# Development (auto-generates client if API is available)
npm run dev

# Build (auto-generates client if API is available)
npm run build

# Manual generation
npm run client:generate
```

**How it works:**

1. **Live API Available**: Script checks if backend is running at `http://localhost:8000`
   - ✅ Downloads OpenAPI spec from live API
   - ✅ Generates TypeScript client with full type safety
   - ✅ Creates `.client-type: server` marker
   - ✅ App uses generated client

2. **No Live API**: Backend not running or not accessible
   - ✅ Creates `.client-type: mock` marker
   - ✅ App automatically uses mock data
   - ✅ Development continues seamlessly

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
import { healthApi, versioningApi } from '@/services/generated/client-config'

// Direct client usage (only works when generated client exists)
const response = await healthApi.getHealthStatus()
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
```

### Testing Generated Client (When Available)

When the generated client is present, you can mock it specifically:

```typescript
import { vi } from 'vitest'

// Mock the generated client
vi.mock('@/services/generated/client-config', () => ({
  healthApi: {
    getHealthStatus: vi.fn(),
  },
  versioningApi: {
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

### Automatic Generation

Client generation happens automatically during:

- `npm run dev` - Before starting dev server
- `npm run build` - Before building for production
- `npm run client:generate` - Manual generation

### How It Works

The generation script (`scripts/generate-client.sh`):

1. Checks if backend API is running at `http://localhost:8000`
2. If available:
   - Downloads OpenAPI spec
   - Generates TypeScript client
   - Creates type-safe API classes
3. If not available:
   - Sets up mock fallback
   - App uses mock data
   - Development continues normally

### Custom API URL

Set the API URL via environment variable:

```bash
# Development
VITE_API_URL=http://api.example.com npm run client:generate

# Or in .env file
VITE_API_URL=http://api.example.com
```

### Manual Generation

```bash
# Generate client (checks for live API)
npm run client:generate

# Or use the script directly
./scripts/generate-client.sh
```

## Benefits

1. **🛡️ Type Safety**: Full TypeScript support with generated types (when available)
2. **🔄 Auto-sync**: Client automatically stays in sync with backend API
3. **🧪 Testability**: Easy to mock with native fallback
4. **🚀 Resilient**: Works with or without generated client
5. **📚 Self-documenting**: Generated types serve as documentation
6. **🎯 Maintainability**: Minimal manual API code to maintain
7. **⚡ Developer Friendly**: Zero configuration, works out of the box

## Architecture Benefits

- **Graceful Degradation**: Missing generated client doesn't break the app
- **Development Friendly**: Tests work without requiring client generation
- **Production Ready**: Automatically uses generated client when available
- **Fail-Safe**: Multiple fallback layers ensure reliability
- **CI/CD Compatible**: Works in all environments

---

# DatafeedService Implementation Guide

The `DatafeedService` class provides a blank template for implementing the TradingView Charting Library's datafeed interface. All methods are left empty for custom implementation.

## Required Methods

### `onReady(callback: OnReadyCallback): void`

Called when the library is ready. Should provide datafeed configuration.

**Example Implementation:**

```typescript
onReady(callback: OnReadyCallback): void {
  setTimeout(() => callback({
    supported_resolutions: ['1D', '1W', '1M'],
    supports_marks: false,
    supports_timescale_marks: false,
    supports_time: false,
  }), 0)
}
```

### `searchSymbols(userInput, exchange, symbolType, onResult): void`

Called when user searches for symbols in the symbol search box.

**Example Implementation:**

```typescript
searchSymbols(userInput: string, exchange: string, symbolType: string, onResult: SearchSymbolsCallback): void {
  // Search your database/API for symbols
  const symbols = searchYourDatabase(userInput, exchange, symbolType)
  onResult(symbols)
}
```

### `resolveSymbol(symbolName, onResolve, onError): void`

Called to get detailed symbol information.

**Example Implementation:**

```typescript
resolveSymbol(symbolName: string, onResolve: ResolveCallback, onError: DatafeedErrorCallback): void {
  try {
    const symbolInfo: LibrarySymbolInfo = {
      name: symbolName,
      full_name: symbolName,
      description: `${symbolName} Description`,
      type: 'stock',
      session: '24x7',
      timezone: 'Etc/UTC',
      ticker: symbolName,
      exchange: 'Your Exchange',
      listed_exchange: 'Your Exchange',
      format: 'price',
      minmov: 1,
      pricescale: 100,
      has_intraday: false,
      has_daily: true,
      supported_resolutions: ['1D'],
      volume_precision: 0,
      data_status: 'streaming',
    }
    onResolve(symbolInfo)
  } catch (error) {
    onError(error.message)
  }
}
```

### `getBars(symbolInfo, resolution, periodParams, onResult, onError): void`

Called to get historical OHLC data for the chart.

**Example Implementation:**

```typescript
async getBars(symbolInfo: LibrarySymbolInfo, resolution: ResolutionString, periodParams: PeriodParams, onResult: HistoryCallback, onError: DatafeedErrorCallback): void {
  try {
    const bars = await fetchHistoricalData(
      symbolInfo.name,
      resolution,
      periodParams.from,
      periodParams.to
    )
    onResult(bars, { noData: bars.length === 0 })
  } catch (error) {
    onError(error.message)
  }
}
```

### `subscribeBars(symbolInfo, resolution, onTick, listenerGuid, onResetCacheNeededCallback): void`

Called to subscribe to real-time data updates.

**Example Implementation:**

```typescript
subscribeBars(symbolInfo: LibrarySymbolInfo, resolution: ResolutionString, onTick: SubscribeBarsCallback, listenerGuid: string, onResetCacheNeededCallback: () => void): void {
  // Store subscription
  this.subscriptions.set(listenerGuid, {
    symbolInfo,
    resolution,
    onTick,
    onResetCacheNeededCallback
  })

  // Start real-time updates
  startRealTimeUpdates(symbolInfo.name, resolution, onTick)
}
```

### `unsubscribeBars(listenerGuid): void`

Called to unsubscribe from real-time data updates.

**Example Implementation:**

```typescript
unsubscribeBars(listenerGuid: string): void {
  const subscription = this.subscriptions.get(listenerGuid)
  if (subscription) {
    stopRealTimeUpdates(listenerGuid)
    this.subscriptions.delete(listenerGuid)
  }
}
```

## Data Format

### Bar Format

```typescript
interface Bar {
  time: number // Unix timestamp in SECONDS
  open: number // Opening price
  high: number // Highest price
  low: number // Lowest price
  close: number // Closing price
  volume?: number // Volume (optional)
}
```

## Usage

The service is automatically instantiated in `TraderChartContainer.vue`:

```typescript
import { DatafeedService } from '@/services/datafeed'

// In component setup
const datafeed = new DatafeedService()
```

## Integration Steps

1. Implement the required methods in `DatafeedService`
2. Connect to your data source (API, WebSocket, etc.)
3. Handle error cases appropriately
4. Test with TradingView charts

## Documentation

- [TradingView Datafeed API](https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IDatafeedChartApi)
- [TradingView Tutorials](https://www.tradingview.com/charting-library-docs/latest/tutorials/)
