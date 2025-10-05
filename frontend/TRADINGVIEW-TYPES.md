# TradingView Charting Library TypeScript Types

## Overview

The TradingView Charting Library integration uses comprehensive TypeScript type definitions located in `/frontend/src/types/tradingview.ts`. These types ensure type safety and provide excellent IDE intellisense when working with the charting library.

## Project Structure

```
frontend/src/
├── types/
│   └── tradingview.ts          # All TradingView type definitions (exported)
└── components/
    └── TraderChartContainer.vue # Chart component (imports types)
```

## Usage

Import the types you need in your components:

```typescript
import type {
  Bar,
  IDatafeedChartApi,
  LibrarySymbolInfo,
  ResolutionString,
  TradingViewWidget,
  // ... other types as needed
} from '@/types/tradingview'
```

## Type Definitions

### Core Data Types

#### `Bar`
Represents a single candlestick (OHLC) data point:
```typescript
interface Bar {
  time: number      // Unix timestamp in SECONDS (not milliseconds!)
  open: number      // Opening price
  high: number      // High price
  low: number       // Low price
  close: number     // Closing price
  volume?: number   // Optional trading volume
}
```

**Important**: `time` must be in seconds, not milliseconds. Use `Date.now() / 1000` or `Math.floor(Date.now() / 1000)`.

#### `ResolutionString`
Type alias for resolution format:
```typescript
type ResolutionString = string
```
Examples: `"1"` (1 minute), `"5"`, `"15"`, `"60"` (1 hour), `"1D"` (1 day), `"1W"` (1 week), `"1M"` (1 month)

### Configuration Types

#### `DatafeedConfiguration`
Returned by `onReady()` to configure the datafeed:
```typescript
interface DatafeedConfiguration {
  supported_resolutions?: ResolutionString[]  // List of available resolutions
  supports_marks?: boolean                    // Whether marks on bars are supported
  supports_timescale_marks?: boolean          // Whether timescale marks are supported
  supports_time?: boolean                     // Whether server time is provided
}
```

#### `LibrarySymbolInfo`
Complete symbol metadata:
```typescript
interface LibrarySymbolInfo {
  name: string                  // Symbol name (e.g., "AAPL")
  full_name?: string            // Full name including exchange (e.g., "NASDAQ:AAPL")
  description: string           // Human-readable description
  type: string                  // Symbol type: "stock", "forex", "crypto", etc.
  session: string               // Trading hours (e.g., "24x7", "0930-1600")
  timezone: string              // IANA timezone (e.g., "America/New_York", "Etc/UTC")
  ticker: string                // Unique ticker identifier
  exchange: string              // Exchange name
  listed_exchange: string       // Listed exchange name
  format: 'price' | 'volume'    // Price display format
  minmov: number                // Minimum price movement (tick size numerator)
  pricescale: number            // Price scale (tick size denominator)
  has_intraday?: boolean        // Whether intraday data is available
  has_daily?: boolean           // Whether daily data is available
  supported_resolutions?: ResolutionString[]  // Resolutions for this symbol
  volume_precision?: number     // Decimal places for volume
  data_status?: 'streaming' | 'endofday' | 'delayed_streaming'
}
```

**Price format example**: For a price like `123.45`:
- `minmov = 1`
- `pricescale = 100`
- Tick size = `minmov / pricescale = 1 / 100 = 0.01`

### Request/Response Types

#### `PeriodParams`
Parameters for historical data requests:
```typescript
interface PeriodParams {
  from: number              // Start time (Unix timestamp in SECONDS)
  to: number                // End time (Unix timestamp in SECONDS)
  firstDataRequest: boolean // Whether this is the first request
  countBack?: number        // Number of bars to return (countBack mode)
}
```

#### `HistoryMetadata`
Metadata returned with historical bars:
```typescript
interface HistoryMetadata {
  noData: boolean    // Whether there is no data available
  nextTime?: number  // Next bar time if partial data (Unix timestamp in SECONDS)
}
```

### Callback Types

```typescript
type OnReadyCallback = (config: DatafeedConfiguration) => void
type SearchSymbolsCallback = (items: unknown[]) => void
type ResolveCallback = (symbolInfo: LibrarySymbolInfo) => void
type HistoryCallback = (bars: Bar[], meta: HistoryMetadata) => void
type SubscribeBarsCallback = (bar: Bar) => void
type DatafeedErrorCallback = (error: string) => void
```

## Main Interface: `IDatafeedChartApi`

The complete datafeed interface that TradingView expects:

```typescript
interface IDatafeedChartApi {
  onReady(callback: OnReadyCallback): void

  searchSymbols(
    userInput: string,
    exchange: string,
    symbolType: string,
    onResult: SearchSymbolsCallback
  ): void

  resolveSymbol(
    symbolName: string,
    onResolve: ResolveCallback,
    onError: DatafeedErrorCallback
  ): void

  getBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: ResolutionString,
    periodParams: PeriodParams,
    onResult: HistoryCallback,
    onError: DatafeedErrorCallback
  ): void

  subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: ResolutionString,
    onTick: SubscribeBarsCallback,
    listenerGuid: string,
    onResetCacheNeededCallback: () => void
  ): void

  unsubscribeBars(listenerGuid: string): void
}
```

## Implementation Example

The `TraderChartContainer.vue` component shows how to use these types:

```typescript
import type {
  Bar,
  IDatafeedChartApi,
  LibrarySymbolInfo,
  ResolutionString,
  OnReadyCallback,
  ResolveCallback,
  HistoryCallback,
  // ... other imports
} from '@/types/tradingview'

const datafeed: IDatafeedChartApi = {
  onReady: (callback: OnReadyCallback) => {
    callback({
      supported_resolutions: ['1D'],
      supports_marks: false,
      supports_timescale_marks: false,
    })
  },

  resolveSymbol: (
    symbolName: string,
    onResolve: ResolveCallback,
    _onError: DatafeedErrorCallback
  ) => {
    const symbolInfo: LibrarySymbolInfo = {
      name: symbolName,
      description: 'Sample Symbol',
      type: 'stock',
      session: '24x7',
      timezone: 'Etc/UTC',
      // ... other required fields
    }
    onResolve(symbolInfo)
  },

  getBars: (
    symbolInfo: LibrarySymbolInfo,
    resolution: ResolutionString,
    periodParams: PeriodParams,
    onResult: HistoryCallback,
    onError: DatafeedErrorCallback
  ) => {
    try {
      const bars: Bar[] = // ... fetch or generate bars
      onResult(bars, { noData: bars.length === 0 })
    } catch (error) {
      onError(error.message)
    }
  },

  // ... other methods
}
```

## Common Pitfalls

### ❌ Wrong: Milliseconds for time
```typescript
const bar: Bar = {
  time: Date.now(),  // WRONG! This is milliseconds
  // ...
}
```

### ✅ Correct: Seconds for time
```typescript
const bar: Bar = {
  time: Math.floor(Date.now() / 1000),  // Correct: seconds
  // ...
}
```

### ❌ Wrong: Missing required fields
```typescript
const symbolInfo: LibrarySymbolInfo = {
  name: 'AAPL',
  // WRONG: Missing many required fields
}
```

### ✅ Correct: All required fields
```typescript
const symbolInfo: LibrarySymbolInfo = {
  name: 'AAPL',
  description: 'Apple Inc.',
  type: 'stock',
  session: '0930-1600',
  timezone: 'America/New_York',
  ticker: 'AAPL',
  exchange: 'NASDAQ',
  listed_exchange: 'NASDAQ',
  format: 'price',
  minmov: 1,
  pricescale: 100,
}
```

## Type Sources

These type definitions are based on:
- **Official Documentation**: https://www.tradingview.com/charting-library-docs/latest/api/
- **TypeScript Definitions**: `/public/charting_library/datafeed-api.d.ts`
- **API Reference**: `IDatafeedChartApi` interface documentation

## Benefits

1. **Type Safety**: Compile-time errors for incorrect data structures
2. **Intellisense**: Full IDE autocomplete for all datafeed methods and properties
3. **Documentation**: JSDoc comments explain each property and parameter
4. **Maintainability**: Clear contracts make refactoring safer
5. **Reusability**: Types can be imported in multiple components
6. **Separation of Concerns**: Types separate from implementation logic

## File Organization Benefits

### Before (Single File)
- ❌ `TraderChartContainer.vue`: ~500 lines
- ❌ Types mixed with component logic
- ❌ Types not reusable

### After (Separated)
- ✅ `TraderChartContainer.vue`: ~370 lines (26% smaller)
- ✅ `tradingview.ts`: ~234 lines (reusable types)
- ✅ Clear separation of concerns
- ✅ Types can be imported anywhere

## Next Steps

To add real-time data streaming:

1. Implement `subscribeBars` to accept real-time updates:
   ```typescript
   subscribeBars: (
     symbolInfo: LibrarySymbolInfo,
     resolution: ResolutionString,
     onTick: SubscribeBarsCallback,
     listenerGuid: string,
     onResetCacheNeededCallback: () => void
   ) => {
     // Store subscription
     const subscription = {
       symbolInfo,
       resolution,
       onTick,
       guid: listenerGuid
     }

     // Connect to WebSocket or polling mechanism
     startStreaming(subscription)
   }
   ```

2. Call `onTick` callback when new data arrives:
   ```typescript
   function handleNewTick(bar: Bar) {
     subscription.onTick(bar)
   }
   ```

3. Clean up in `unsubscribeBars`:
   ```typescript
   unsubscribeBars: (listenerGuid: string) => {
     stopStreaming(listenerGuid)
   }
   ```

## References

- [TradingView Datafeed API Documentation](https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/)
- [IDatafeedChartApi Interface](https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Datafeed.IDatafeedChartApi)
- [LibrarySymbolInfo Interface](https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.LibrarySymbolInfo)
- [Resolution Format](https://www.tradingview.com/charting-library-docs/latest/core_concepts/Resolution)
