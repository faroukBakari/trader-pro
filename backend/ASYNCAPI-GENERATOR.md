# AsyncAPI Generator & Client Integration Guide

**Version**: 1.0.0  
**Last Updated**: October 11, 2025  
**Purpose**: Automated TypeScript client generation from AsyncAPI specifications

## Overview

This guide describes how to extend the existing OpenAPI client generation system to also support AsyncAPI WebSocket client generation, creating a unified development experience for both REST and real-time APIs.

## Current State

### ✅ What's Implemented
- **AsyncAPI 3.0 Specification**: Complete spec in `backend/asyncapi.yaml`
- **AsyncAPI Endpoint**: Available at `/api/v1/asyncapi.yaml`
- **WebSocket Infrastructure**: Full backend implementation
- **OpenAPI Client Generation**: Working TypeScript client generation

### 🚧 What's Next
- **AsyncAPI Client Generation**: TypeScript WebSocket clients
- **Frontend WebSocket Service**: Unified API service layer
- **TradingView Integration**: Real-time chart data

## AsyncAPI Client Generation Strategy

### Approach: Extend Existing Pipeline

The current OpenAPI client generation pipeline:
```bash
frontend/scripts/generate-client.sh
├─ Check API availability
├─ Download OpenAPI spec  
├─ Generate TypeScript client
└─ Create index file for imports
```

**Extended pipeline** for AsyncAPI:
```bash
frontend/scripts/generate-client.sh
├─ Check API availability
├─ Download OpenAPI spec ✅
├─ Generate REST TypeScript client ✅
├─ Download AsyncAPI spec 🚧
├─ Generate WebSocket TypeScript client 🚧
└─ Create unified index file 🚧
```

## Implementation Plan

### 1. AsyncAPI Client Generator Selection

**Option A: Custom WebSocket Client Generator**
```typescript
// Pros: Full control, lightweight, tailored to our needs
// Cons: More maintenance, custom implementation

class WebSocketClient {
  connect(url: string): Promise<void>
  subscribe(channel: string, symbol?: string): void
  unsubscribe(channel: string, symbol?: string): void
  send(message: WebSocketMessage): void
  on(event: string, handler: Function): void
}
```

**Option B: Existing AsyncAPI Tools**
```bash
# AsyncAPI Generator (Node.js based)
npm install -g @asyncapi/generator

# Generate TypeScript client
asyncapi generate fromTemplate asyncapi.yaml @asyncapi/typescript-ws-client
```

**Option C: Hybrid Approach** (Recommended)
- Use AsyncAPI parser for schema validation
- Custom lightweight WebSocket client wrapper
- Integrate with existing type generation

### 2. Updated File Structure

```
frontend/src/
├─ clients/
│  ├─ trader-client-generated/           # OpenAPI REST client
│  │  ├─ api/
│  │  ├─ models/
│  │  └─ index.ts
│  └─ trader-websocket-generated/        # AsyncAPI WebSocket client
│     ├─ channels/
│     │  ├─ MarketDataChannel.ts
│     │  ├─ OrderBookChannel.ts
│     │  └─ index.ts
│     ├─ messages/
│     │  ├─ MarketDataTick.ts
│     │  ├─ OrderBookUpdate.ts
│     │  └─ index.ts
│     ├─ WebSocketClient.ts
│     └─ index.ts
└─ services/
   ├─ apiService.ts                      # REST API wrapper
   ├─ websocketService.ts                # WebSocket API wrapper
   └─ tradingService.ts                  # Unified service
```

### 3. WebSocket Client Interface

```typescript
// Generated from AsyncAPI spec
export interface TradingWebSocketClient {
  // Connection management
  connect(): Promise<void>
  disconnect(): void
  
  // Authentication
  authenticate(token: string): Promise<boolean>
  
  // Channel subscriptions
  subscribeMarketData(symbol: string): MarketDataSubscription
  subscribeOrderBook(symbol: string): OrderBookSubscription
  subscribeChartData(symbol: string, resolution: string): ChartDataSubscription
  
  // Private channels (require auth)
  subscribeAccount(): AccountSubscription
  subscribeOrders(): OrderSubscription
  subscribePositions(): PositionSubscription
  subscribeNotifications(): NotificationSubscription
  
  // Connection state
  readonly connectionState: 'connecting' | 'connected' | 'disconnected' | 'error'
  readonly isAuthenticated: boolean
}

// Generated subscription interfaces
export interface MarketDataSubscription {
  onTick(handler: (tick: MarketDataTick) => void): void
  unsubscribe(): void
}
```

## Updated Client Generation Script

### Enhanced `generate-client.sh`

```bash
#!/bin/bash
# Enhanced Frontend API Client Generator
# Generates both REST (OpenAPI) and WebSocket (AsyncAPI) clients

set -e

# Configuration
API_URL="${VITE_API_URL:-http://localhost:${BACKEND_PORT:-8000}}"
REST_OUTPUT_DIR="./src/clients/trader-client-generated"
WS_OUTPUT_DIR="./src/clients/trader-websocket-generated"
OPENAPI_SPEC="openapi.json"
ASYNCAPI_SPEC="asyncapi.yaml"

echo "🚀 Dual API Client Generator (REST + WebSocket)"

# Function to check API availability
check_api_available() {
    local health_url="$API_URL/api/v1/health"
    echo "📡 Checking API server at: $health_url"
    curl -sf "$health_url" > /dev/null 2>&1
}

# Function to generate REST client (existing)
generate_rest_client() {
    echo "🔧 Generating REST TypeScript client..."
    # Existing OpenAPI generation logic
    npx @openapitools/openapi-generator-cli generate \
        -i "$OPENAPI_SPEC" \
        -g typescript-axios \
        -o "$REST_OUTPUT_DIR" \
        -c "./openapi-generator-config.json"
}

# Function to generate WebSocket client (new)
generate_websocket_client() {
    echo "🔧 Generating WebSocket TypeScript client..."
    
    # Create output directory
    rm -rf "$WS_OUTPUT_DIR"
    mkdir -p "$WS_OUTPUT_DIR"/{channels,messages,types}
    
    # Option A: Custom generation
    node ./scripts/generate-websocket-client.js "$ASYNCAPI_SPEC" "$WS_OUTPUT_DIR"
    
    # Option B: Use AsyncAPI generator (if available)
    # asyncapi generate fromTemplate "$ASYNCAPI_SPEC" @asyncapi/typescript-ws-client -o "$WS_OUTPUT_DIR"
}

# Function to download AsyncAPI spec
download_asyncapi_spec() {
    local asyncapi_url="$API_URL/api/v1/asyncapi.yaml"
    echo "📥 Downloading AsyncAPI specification from: $asyncapi_url"
    curl -sf "$asyncapi_url" -o "$ASYNCAPI_SPEC"
}

# Function to create unified index
create_unified_index() {
    cat > "./src/clients/index.ts" << 'EOF'
// Auto-generated unified API client exports
// This file is automatically generated. Do not edit manually.

// REST API Client
export * from './trader-client-generated'

// WebSocket API Client  
export * from './trader-websocket-generated'

// Unified service
export { TradingService } from '../services/tradingService'
EOF
}

# Main execution
main() {
    if check_api_available; then
        # Download specifications
        download_openapi_spec  # existing function
        download_asyncapi_spec
        
        # Generate clients
        generate_rest_client
        generate_websocket_client
        
        # Create unified exports
        create_unified_index
        
        echo "✅ Dual client generation successful!"
        echo "📁 REST client: $REST_OUTPUT_DIR"  
        echo "📁 WebSocket client: $WS_OUTPUT_DIR"
    else
        echo "⚠️ API not available - using mock clients"
        # Existing fallback logic
    fi
}

main
```

## WebSocket Service Layer

### Unified Trading Service

```typescript
// src/services/tradingService.ts
import { RestApiClient } from '@/clients/trader-client-generated'
import { TradingWebSocketClient } from '@/clients/trader-websocket-generated'

export class TradingService {
  private restClient: RestApiClient
  private wsClient: TradingWebSocketClient
  
  constructor(config: TradingServiceConfig) {
    this.restClient = new RestApiClient(config.apiUrl)
    this.wsClient = new TradingWebSocketClient(config.wsUrl)
  }
  
  // REST API methods
  async getHealth() { return this.restClient.health.getHealth() }
  async getSymbols() { return this.restClient.datafeed.searchSymbols() }
  async getBars(request: GetBarsRequest) { return this.restClient.datafeed.getBars(request) }
  
  // WebSocket methods
  async connectRealTime() { return this.wsClient.connect() }
  subscribeMarketData(symbol: string) { return this.wsClient.subscribeMarketData(symbol) }
  subscribeChartData(symbol: string) { return this.wsClient.subscribeChartData(symbol, '1m') }
  
  // Hybrid methods (REST + WebSocket)
  async initSymbol(symbol: string) {
    // Get initial data via REST
    const symbolInfo = await this.restClient.datafeed.resolveSymbol(symbol)
    const historicalBars = await this.restClient.datafeed.getBars({
      symbol, resolution: '1D', from_time: Date.now() - 86400000, to_time: Date.now()
    })
    
    // Subscribe to real-time updates via WebSocket
    const liveUpdates = this.wsClient.subscribeMarketData(symbol)
    
    return { symbolInfo, historicalBars, liveUpdates }
  }
}
```

## TradingView Integration

### Real-time Datafeed Bridge

```typescript
// src/services/tradingViewDatafeed.ts
import { TradingService } from './tradingService'
import type { IDatafeedChartApi, LibrarySymbolInfo } from '@/public/charting_library'

export class TradingViewDatafeed implements IDatafeedChartApi {
  private tradingService: TradingService
  private subscriptions = new Map<string, any>()
  
  constructor(tradingService: TradingService) {
    this.tradingService = tradingService
  }
  
  // REST API methods (existing)
  async resolveSymbol(symbolName: string): Promise<LibrarySymbolInfo> {
    return this.tradingService.getSymbolInfo(symbolName)
  }
  
  async getBars(symbolInfo: LibrarySymbolInfo, resolution: string, from: number, to: number) {
    return this.tradingService.getBars({ symbol: symbolInfo.name, resolution, from_time: from, to_time: to })
  }
  
  // WebSocket methods (new)
  subscribeBars(symbolInfo: LibrarySymbolInfo, resolution: string, onRealtimeCallback: Function) {
    const subscriptionKey = `${symbolInfo.name}_${resolution}`
    
    // Subscribe to real-time chart data
    const subscription = this.tradingService.subscribeChartData(symbolInfo.name, resolution)
    subscription.onUpdate((candlestick) => {
      onRealtimeCallback({
        time: candlestick.time,
        open: candlestick.open,
        high: candlestick.high,
        low: candlestick.low,
        close: candlestick.close,
        volume: candlestick.volume
      })
    })
    
    this.subscriptions.set(subscriptionKey, subscription)
  }
  
  unsubscribeBars(subscriberUID: string) {
    const subscription = this.subscriptions.get(subscriberUID)
    if (subscription) {
      subscription.unsubscribe()
      this.subscriptions.delete(subscriberUID)
    }
  }
}
```

## Development Workflow

### Local Development

```bash
# 1. Start backend with WebSocket support
cd backend && make dev

# 2. Generate clients (both REST and WebSocket)
cd frontend && npm run client:generate

# 3. Start frontend with real-time data
npm run dev

# 4. Test WebSocket connection
curl http://localhost:8000/api/v1/ws/stats
```

### Testing WebSocket Clients

```typescript
// tests/websocket.integration.spec.ts
import { TradingWebSocketClient } from '@/clients/trader-websocket-generated'

describe('WebSocket Client Integration', () => {
  let client: TradingWebSocketClient
  
  beforeEach(async () => {
    client = new TradingWebSocketClient('ws://localhost:8000/api/v1/ws/v1')
    await client.connect()
  })
  
  it('should connect and receive market data', async () => {
    const subscription = client.subscribeMarketData('AAPL')
    
    const tickPromise = new Promise((resolve) => {
      subscription.onTick(resolve)
    })
    
    const tick = await tickPromise
    expect(tick.symbol).toBe('AAPL')
    expect(tick.price).toBeGreaterThan(0)
  })
})
```

## Maintenance & Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/api/v1/health

# WebSocket stats
curl http://localhost:8000/api/v1/ws/stats

# Client generation test
cd frontend && npm run client:generate
```

### Troubleshooting

**AsyncAPI spec issues**
```bash
# Validate AsyncAPI spec
npx @asyncapi/cli validate backend/asyncapi.yaml

# Check spec accessibility
curl http://localhost:8000/api/v1/asyncapi.yaml
```

**WebSocket connection issues**  
```typescript
// Debug WebSocket connection
const client = new TradingWebSocketClient(wsUrl)
client.on('error', console.error)
client.on('disconnect', () => console.log('Disconnected'))
await client.connect()
```

## Future Enhancements

### Advanced Features
- [ ] WebSocket message compression
- [ ] Automatic reconnection with exponential backoff
- [ ] Message queuing during disconnections
- [ ] Binary message support for high-frequency data

### Code Generation Improvements
- [ ] Watch mode for automatic regeneration
- [ ] Custom templates for AsyncAPI generation
- [ ] Integration with build tools (Vite, Webpack)
- [ ] Type-safe channel and message validation

### Documentation
- [ ] AsyncAPI HTML documentation generation
- [ ] Interactive WebSocket API explorer
- [ ] Client SDK documentation
- [ ] Migration guides for API changes

---

## Quick Reference

### Generate Clients
```bash
cd frontend && npm run client:generate
```

### Test WebSocket Connection
```bash
wscat -c ws://localhost:8000/api/v1/ws/v1
```

### Use in Components
```typescript
import { TradingService } from '@/services/tradingService'

const trading = new TradingService({ apiUrl: '...', wsUrl: '...' })
await trading.connectRealTime()
const marketData = trading.subscribeMarketData('AAPL')
```

**Status**: 🚧 Ready for implementation - backend complete, frontend integration next!