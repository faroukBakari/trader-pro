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
│   └── ...
└── __tests__/
    └── apiService.spec.ts  # Unit tests with mocking examples
```

## DatafeedService

The `DatafeedService` class implements the TradingView Charting Library's datafeed interface, including both basic charting functionality and trading platform quotes support.

### Architecture

The service leverages a layered architecture for clean separation of concerns:

```
DatafeedService (Business Logic)
    ↓ uses
WsAdapter (WebSocket Client Wrapper)
    ↓ uses
WebSocketClient<TParams, TBackendData, TData> (Generic Client)
    ↓ uses mappers
Mappers (Type-Safe Transformations)
    ↓ extends
WebSocketBase (Singleton Connection Management)
```

### Features Implemented

✅ **Basic Charting (IBasicDataFeed)**

- Symbol search and resolution via REST API
- Historical data (OHLC bars) via REST API
- Real-time data updates via WebSocket streaming

✅ **Trading Platform Quotes (IDatafeedQuotesApi)**

- Real-time market quotes via WebSocket (bid/ask, last price, volume)
- Quote subscriptions for watchlists and trading features
- Mobile-compatible quote data with change calculations

✅ **Simplified State Management**

- No local subscription tracking needed
- Delegates to `WsAdapter` for all WebSocket operations
- Automatic reconnection and resubscription handled by base client

### Quick Start

1. **Use Existing Implementation**: The service is fully functional with demo data
2. **Customize Data Sources**: Replace demo data with your API/WebSocket feeds
3. **Test Trading Features**: Quotes support enables watchlist, order ticket, and DOM widgets

### WebSocket Adapter Pattern

The service uses `WsAdapter` for centralized WebSocket client management:

```typescript
import { WsAdapter, WsFallback } from '@/plugins/wsAdapter'
import type { WsAdapterType } from '@/plugins/wsAdapter'

export class DatafeedService implements IBasicDataFeed, IDatafeedQuotesApi {
  private wsAdapter: WsAdapterType
  private wsFallback: WsAdapterType
  private mock: boolean

  constructor({ mock = false }: { mock?: boolean } = {}) {
    // Initialize adapters
    this.wsAdapter = new WsAdapter() // Real WebSocket clients
    this.wsFallback = new WsFallback({
      // Mock clients for offline dev
      barsMocker: () => mockLastBar(),
      quotesMocker: () => mockQuoteData('DEMO:SYMBOL'),
    })
    this.mock = mock
  }

  _getWsAdapter(mock: boolean = this.mock): WsAdapterType {
    return mock ? this.wsFallback : this.wsAdapter
  }

  // Subscribe to real-time bars - NO local subscription tracking!
  subscribeBars(listenerGuid, symbolInfo, resolution, onRealtimeCallback) {
    return this._getWsAdapter().bars.subscribe(
      listenerGuid,
      { symbol: symbolInfo.name, resolution },
      onRealtimeCallback,
    )
  }

  // Unsubscribe - base client handles cleanup
  unsubscribeBars(listenerGuid) {
    return this._getWsAdapter().bars.unsubscribe(listenerGuid)
  }
}
```

### Key Benefits

✅ **No Duplicate State**: Service doesn't track subscriptions - `WsAdapter` handles everything  
✅ **Automatic Reconnection**: Base client resubscribes on disconnect  
✅ **Type-Safe Mappers**: Data transformations isolated to mapper layer  
✅ **Dual-Mode Support**: Switch between real and mock WebSocket with one flag  
✅ **Simplified Code**: Services just pass through to adapters

### Supported TradingView Features

- **Charts**: Historical and real-time price charts
- **Watchlist**: Live quotes for multiple symbols
- **Order Ticket**: Real-time pricing for order entry
- **Buy/Sell Buttons**: Bid/ask price display
- **Legend**: Last day change values (mobile compatible)
- **Details Widget**: Market statistics and extended session data

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

The API client is **automatically generated** when you run the development server (via make dev-fullstack):

```bash
# Development (auto-generates clients before startup)
make dev-fullstack

# Manual generation
make generate-openapi-client
make generate-asyncapi-types
```

**How it works:**

1. **Live API Available**: Script checks if backend is running at `http://localhost:8000`
   - ✅ Downloads OpenAPI spec from live API
   - ✅ Generates TypeScript client with full type safety
   - ✅ App uses generated client

2. **No Live API**: Backend not running or not accessible
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
import { apiService } from '../apiService'

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

- `make dev-fullstack` - Before starting dev server
- Makefiles explicitly call generation targets after backend is ready

### How It Works

The generation process (via Makefiles):

1. Backend starts and generates OpenAPI/AsyncAPI specs on startup
2. Makefile targets wait for specs to be available
3. `make generate-openapi-client` - Generates REST client from openapi.json
4. `make generate-asyncapi-types` - Generates WebSocket types from asyncapi.json
5. Frontend starts with fully generated clients

### Custom API URL

Set the API URL via environment variable:

```bash
# Development
# Generation now happens automatically via make dev-fullstack
# Or manually: make generate-openapi-client && make generate-asyncapi-types

# Or in .env file
VITE_API_URL=http://api.example.com
```

### Manual Generation

```bash
# Generate clients manually
make generate-openapi-client
make generate-asyncapi-types
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

The `DatafeedService` class implements the TradingView Charting Library's datafeed interface with both basic charting and trading platform quotes functionality.

## Implementation Status

### ✅ Fully Implemented Methods

All required methods are implemented with demo data:

- **Basic Charting**: `onReady`, `searchSymbols`, `resolveSymbol`, `getBars`, `subscribeBars`, `unsubscribeBars`
- **Trading Platform Quotes**: `getQuotes`, `subscribeQuotes`, `unsubscribeQuotes`

### Demo Data Features

- **400 days of historical bars** with realistic OHLC patterns
- **Real-time price updates** every 500ms for subscribed symbols
- **Quote data** with bid/ask spreads, daily statistics, and change calculations
- **Mobile compatibility** with required fields for legend display
- **Error handling** for unknown symbols and edge cases

## Trading Platform Quotes API

### `getQuotes(symbols, onDataCallback, onErrorCallback): void`

Provides real-time market quotes for trading platform features.

**Current Implementation:**

```typescript
// Returns quote data with realistic market information
const quoteData = {
  s: 'ok', // Status: 'ok' | 'error'
  n: 'AAPL', // Symbol name
  v: {
    // Quote values
    lp: 173.68, // Last price
    ask: 173.7, // Ask price
    bid: 173.66, // Bid price
    spread: 0.04, // Bid-ask spread
    ch: 0.91, // Price change
    chp: 0.53, // Change percentage
    open_price: 173.0, // Open price
    high_price: 174.0, // High price
    low_price: 172.5, // Low price
    prev_close_price: 172.77, // Previous close
    volume: 1234567, // Volume
    short_name: 'AAPL', // Short symbol name
    exchange: 'DEMO', // Exchange name
    description: 'Demo quotes for AAPL',
  },
}
```

**Used By:**

- Watchlist widget
- Order Ticket widget
- Buy/Sell buttons
- Details widget
- Legend (mobile compatibility)
- Depth of Market (DOM)

### `subscribeQuotes(symbols, fastSymbols, onRealtimeCallback, listenerGUID): void`

Subscribes to real-time quote updates for trading features.

**Current Implementation:**

```typescript
// Different update frequencies:
// - Fast symbols: 5 second updates (for active trading)
// - Regular symbols: 30 second updates (for watchlist)

subscribeQuotes(['AAPL'], ['GOOGL'], callback, 'listener-1')
// GOOGL updates every 5s, AAPL updates every 30s
```

### `unsubscribeQuotes(listenerGUID): void`

Removes quote subscription and cleans up timers.

```typescript
unsubscribeQuotes('listener-1') // Stops all updates for this listener
```

## Required Methods (Basic Charting)

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

**Current Implementation (Simplified with WsAdapter):**

```typescript
subscribeBars(
  symbolInfo: LibrarySymbolInfo,
  resolution: ResolutionString,
  onTick: SubscribeBarsCallback,
  listenerGuid: string,
  onResetCacheNeededCallback: () => void
): void {
  // NO local subscription tracking needed!
  // WsAdapter handles all subscription state
  this._getWsAdapter().bars.subscribe(
    listenerGuid,
    { symbol: symbolInfo.name, resolution },
    (bar: Bar) => {
      onTick(bar)
    }
  )
}
```

**Benefits:**

- ✅ No `this.subscriptions = new Map()` needed
- ✅ Base client manages subscription lifecycle
- ✅ Automatic reconnection and resubscription
- ✅ Type-safe data via mappers

### `unsubscribeBars(listenerGuid): void`

Called to unsubscribe from real-time data updates.

**Current Implementation (Simplified with WsAdapter):**

```typescript
unsubscribeBars(listenerGuid: string): void {
  // Just pass through - base client handles cleanup
  this._getWsAdapter().bars.unsubscribe(listenerGuid)
}
```

**Benefits:**

- ✅ Single line implementation
- ✅ No manual cleanup logic
- ✅ Base client handles reference counting
- ✅ Connection closes when last listener unsubscribes

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

## Type-Safe Data Mappers

### Overview

Mappers provide centralized, type-safe transformations between backend and frontend types.

**Location**: `frontend/src/plugins/mappers.ts`

### Available Mappers

#### `mapQuoteData()`

Transforms backend quote data to TradingView frontend format:

```typescript
import { mapQuoteData } from '@/plugins/mappers'
import type { QuoteData as QuoteData_Backend } from '@/clients/trader-client-generated'

// Backend → Frontend transformation
const frontendQuote = mapQuoteData(backendQuote)

// Usage in WsAdapter
this.quotes = new WebSocketClient(
  'quotes',
  mapQuoteData, // Automatic mapping on every message
)
```

#### `mapPreOrder()`

Transforms frontend order to backend format:

```typescript
import { mapPreOrder } from '@/plugins/mappers'
import type { PreOrder } from '@public/trading_terminal/charting_library'

// Frontend → Backend transformation
const backendOrder = mapPreOrder(frontendOrder)

// Handles:
// - Enum type conversions (type, side, stopType)
// - Null handling (limitPrice, stopPrice, etc.)
// - Optional field mapping
```

### Mapper Benefits

✅ **Type Safety**: Backend types isolated to mapper functions  
✅ **Reusability**: Shared across REST and WebSocket clients  
✅ **Maintainability**: Single source of truth for transformations  
✅ **Runtime Validation**: Handles enum conversions and null handling  
✅ **Clean Services**: Services never import backend types directly

### When to Create New Mappers

Create a mapper function when:

1. Backend and frontend use different type definitions
2. Enum values need conversion
3. Field names differ between backend/frontend
4. Complex nested transformations needed
5. Type is used in multiple places (REST + WebSocket)

### Mapper Testing Pattern

```typescript
import { describe, it, expect } from 'vitest'
import { mapQuoteData } from '@/plugins/mappers'

describe('mapQuoteData', () => {
  it('maps success quote data correctly', () => {
    const backend = {
      s: 'ok',
      n: 'AAPL',
      v: { lp: 150.0, bid: 149.9, ask: 150.1 /* ... */ },
    }

    const frontend = mapQuoteData(backend)

    expect(frontend.s).toBe('ok')
    expect(frontend.n).toBe('AAPL')
    expect(frontend.v.lp).toBe(150.0)
  })

  it('maps error quote data correctly', () => {
    const backend = { s: 'error', n: 'INVALID', v: { error: 'Not found' } }
    const frontend = mapQuoteData(backend)

    expect(frontend.s).toBe('error')
    expect(frontend.v).toBe('Not found')
  })
})
```

## Documentation

- [TradingView Datafeed API](https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IDatafeedChartApi)
- [TradingView Tutorials](https://www.tradingview.com/charting-library-docs/latest/tutorials/)
- [WebSocket Client Pattern](../WEBSOCKET-CLIENT-PATTERN.md)
- [WebSocket Client Base](../WEBSOCKET-CLIENT-BASE.md)
- [Client Generation Guide](../../../docs/CLIENT-GENERATION.md)
