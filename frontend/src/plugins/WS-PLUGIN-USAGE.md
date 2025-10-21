````markdown
# WebSocket Client Plugin Usage

## Overview

The `WebSocketClientPlugin` provides a centralized way to handle WebSocket client initialization with automatic fallback when the generated client is not available. It follows the same pattern as `ApiTraderPlugin` for consistency across the codebase.

## Features

- **Automatic Fallback**: Falls back to a mock/fallback client if the generated client fails to import
- **Singleton Pattern**: Ensures only one WebSocket client instance is created across the application
- **Type Safety**: Fully typed with TypeScript generics
- **Error Handling**: Gracefully handles import errors and logs appropriate warnings
- **Consistent API**: Mirrors the `ApiTraderPlugin` pattern for familiar usage

## Architecture

The plugin uses dynamic imports to load the generated WebSocket client:

1. Attempts to import `BarsWebSocketClientFactory` from `@/clients/ws-generated/client`
2. Calls the factory function to create the client instance
3. If import fails, falls back to the provided fallback client class
4. Returns a singleton instance shared across the application

## Usage

### Basic Usage

```typescript
import { WebSocketClientPlugin } from '@/plugins/traderPlugin'
import type { WebSocketInterface } from '@/plugins/wsClientBase'

// Define your fallback client class
class BarsWebSocketFallbackClient implements WebSocketInterface<BarsSubscriptionRequest, Bar> {
  async subscribe(params: BarsSubscriptionRequest, onUpdate: (data: Bar) => void): Promise<string> {
    // Mock implementation for development/testing
    console.log('Using fallback WebSocket client')
    return 'fallback-subscription-id'
  }

  async unsubscribe(listenerGuid: string): Promise<void> {
    // Mock implementation
    console.log('Unsubscribing:', listenerGuid)
  }
}

// Create the plugin instance (typically in a service)
const wsPlugin = new WebSocketClientPlugin<BarsWebSocketInterface>()

// Get the client with automatic fallback
const wsClient = await wsPlugin.getClientWithFallback(BarsWebSocketFallbackClient)

// Use the client
const subscriptionId = await wsClient.subscribe({ symbol: 'AAPL', resolution: '1' }, (data) =>
  console.log('Bar update:', data),
)

// Clean up
await wsClient.unsubscribe(subscriptionId)
```

### Real-World Example (DatafeedService)

This is the actual implementation from `src/services/datafeedService.ts`:

```typescript
import { ApiTraderPlugin, WebSocketClientPlugin } from '@/plugins/traderPlugin'

interface BarsWebSocketInterface {
  subscribe(params: BarsSubscriptionRequest, onUpdate: (data: Bar) => void): Promise<string>
  unsubscribe(listenerGuid: string): Promise<void>
}

class BarsWebSocketFallbackClient implements BarsWebSocketInterface {
  private subscriptions = new Map()
  private intervalId: number

  constructor() {
    // Mock data updates every second
    this.intervalId = setInterval(() => {
      this.subscriptions.forEach(({ onUpdate }) => {
        onUpdate(this.mockLastBar())
      })
    }, 1000)
  }

  async subscribe(params: BarsSubscriptionRequest, onUpdate: (data: Bar) => void): Promise<string> {
    const subscriptionId = `ws_${Date.now()}_${Math.random()}`
    this.subscriptions.set(subscriptionId, { params, onUpdate })
    return subscriptionId
  }

  async unsubscribe(listenerGuid: string): Promise<void> {
    this.subscriptions.delete(listenerGuid)
  }

  destroy(): void {
    if (this.intervalId) {
      window.clearInterval(this.intervalId)
    }
    this.subscriptions.clear()
  }

  private mockLastBar(): Bar {
    // Generate mock bar data for testing
    return {
      time: Date.now(),
      open: 100,
      high: 105,
      low: 95,
      close: 102,
      volume: 1000,
    }
  }
}

export class DatafeedService implements IBasicDataFeed, IDatafeedQuotesApi {
  private apiPlugin: ApiTraderPlugin<ApiClientInterface>
  private wsPlugin: WebSocketClientPlugin<BarsWebSocketInterface>
  private apiFallbackClient: ApiClientInterface = new ApiFallbackClient()
  private wsFallbackClient: BarsWebSocketInterface = new BarsWebSocketFallbackClient()
  private wsClient: BarsWebSocketInterface | null = null

  constructor() {
    this.apiPlugin = new ApiTraderPlugin<ApiClientInterface>()
    this.wsPlugin = new WebSocketClientPlugin<BarsWebSocketInterface>()
  }

  // Load WebSocket client with optional mock override
  async _loadWsClient(mock: boolean = false): Promise<BarsWebSocketInterface> {
    return mock
      ? Promise.resolve(this.wsFallbackClient)
      : this.wsPlugin.getClientWithFallback(BarsWebSocketFallbackClient)
  }

  // Load API client with optional mock override
  async _loadApiClient(mock: boolean = false): Promise<ApiClientInterface> {
    return mock
      ? Promise.resolve(this.apiFallbackClient)
      : this.apiPlugin.getClientWithFallback(ApiFallbackClient)
  }

  // Use in subscription methods
  async subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    onTick: SubscribeBarsCallback,
    listenerGuid: string,
  ): void {
    if (!this.wsClient) {
      this.wsClient = await this._loadWsClient()
    }

    const wsSubscriptionId = await this.wsClient.subscribe(
      { symbol: symbolInfo.name, resolution },
      (bar: Bar) => {
        onTick(bar)
      },
    )

    // Store subscription for cleanup
    this.subscriptions.set(listenerGuid, {
      symbolInfo,
      resolution,
      onTick,
      wsSubscriptionId,
    })
  }

  async unsubscribeBars(listenerGuid: string): void {
    const subscription = this.subscriptions.get(listenerGuid)
    if (subscription?.wsSubscriptionId && this.wsClient) {
      await this.wsClient.unsubscribe(subscription.wsSubscriptionId)
    }
    this.subscriptions.delete(listenerGuid)
  }
}
```

## Client Type Checking

You can check which type of client is being used at runtime:

```typescript
import { WebSocketClientPlugin } from '@/plugins/traderPlugin'

const clientType = WebSocketClientPlugin.getWsClientType()
console.log('Using client type:', clientType)
// Output: 'server' | 'mock' | 'unknown'

// Example usage
if (clientType === 'mock') {
  console.warn('⚠️ Using fallback WebSocket client - features may be limited')
} else if (clientType === 'server') {
  console.info('✅ Using generated WebSocket client')
}
```

## Plugin Pattern Comparison

Both plugins follow the same pattern for consistency:

| Feature                | ApiTraderPlugin                   | WebSocketClientPlugin             |
| ---------------------- | --------------------------------- | --------------------------------- |
| **Generic Type**       | `<Features>`                      | `<Features>`                      |
| **Method Name**        | `getClientWithFallback()`         | `getClientWithFallback()`         |
| **Fallback Parameter** | `new () => Features`              | `new () => Features`              |
| **Type Checking**      | `getApiClientType()`              | `getWsClientType()`               |
| **Client Types**       | `'server' \| 'mock' \| 'unknown'` | `'server' \| 'mock' \| 'unknown'` |
| **Singleton**          | ✅ Yes                            | ✅ Yes                            |

## Benefits

1. **Development Flexibility**: Work without generated clients during development
2. **Graceful Degradation**: Application continues to work even if client generation fails
3. **Testing Support**: Easy to test with mock/fallback clients
4. **Type Safety**: Full TypeScript support ensures compile-time type correctness
5. **Consistent API**: Same pattern as `ApiTraderPlugin` reduces cognitive load
6. **Singleton Pattern**: Prevents multiple WebSocket connections
7. **Error Visibility**: Console warnings make it clear when fallback is used

## Common Patterns

### Pattern 1: Lazy Loading

Load the client only when needed:

```typescript
class MyService {
  private wsPlugin = new WebSocketClientPlugin<BarsWebSocketInterface>()
  private wsClient: BarsWebSocketInterface | null = null

  async ensureClient(): Promise<BarsWebSocketInterface> {
    if (!this.wsClient) {
      this.wsClient = await this.wsPlugin.getClientWithFallback(BarsWebSocketFallbackClient)
    }
    return this.wsClient
  }
}
```

### Pattern 2: Conditional Loading

Use mock in tests, real client in production:

```typescript
async _loadWsClient(mock: boolean = false): Promise<BarsWebSocketInterface> {
  return mock
    ? Promise.resolve(this.wsFallbackClient)
    : this.wsPlugin.getClientWithFallback(BarsWebSocketFallbackClient)
}

// In tests
const client = await service._loadWsClient(true)  // Uses mock

// In production
const client = await service._loadWsClient()  // Uses generated or falls back
```

### Pattern 3: Pre-loading in Constructor

Initialize clients during service construction:

```typescript
constructor() {
  this.wsPlugin = new WebSocketClientPlugin<BarsWebSocketInterface>()
  this.initializeClient()
}

private async initializeClient(): Promise<void> {
  this.wsClient = await this.wsPlugin.getClientWithFallback(BarsWebSocketFallbackClient)
}
```

## Error Handling

The plugin handles errors gracefully:

```typescript
// Generated client available
✅ Generated WebSocket client loaded successfully

// Generated client not available (development/testing)
⚠️ Generated WebSocket client not available: Cannot find module ... => Using fallback WebSocket client
```

## Related Documentation

- [API Trader Plugin](../src/plugins/traderPlugin.ts) - Similar pattern for REST API clients
- [WebSocket Client Base](../src/plugins/wsClientBase.ts) - Base implementation for WebSocket clients
- [Client Generation Guide](../CLIENT-GENERATION.md) - How to generate API clients
- [WebSocket Auto-Generation](../WS-CLIENT-AUTO-GENERATION.md) - How to generate WebSocket clients
- [WebSocket Quick Reference](../WEBSOCKET-QUICK-REFERENCE.md) - Quick lookup guide

## See Also

- [WebSocket Clients Guide](../../docs/WEBSOCKET-CLIENTS.md) - High-level overview
- [WebSocket Client Pattern](../WEBSOCKET-CLIENT-PATTERN.md) - Complete pattern documentation
- [WebSocket Architecture Diagrams](../WEBSOCKET-ARCHITECTURE-DIAGRAMS.md) - Visual diagrams
````
