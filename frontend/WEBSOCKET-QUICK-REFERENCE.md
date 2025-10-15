# WebSocket Client Quick Reference

**Quick lookup guide for developers working with WebSocket clients**

## 🚀 Quick Start

### Create a WebSocket Client

```typescript
import { BarsWebSocketClientFactory } from '@/clients/ws-generated/client'

// Initialize client
const wsClient = BarsWebSocketClientFactory()

// Subscribe to data
const subscriptionId = await wsClient.subscribe(
  { symbol: 'AAPL', resolution: '1' },
  (bar) => {
    console.log('New bar:', bar)
  }
)

// Unsubscribe
await wsClient.unsubscribe(subscriptionId)
```

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| **[WEBSOCKET-IMPLEMENTATION-SUMMARY.md](./WEBSOCKET-IMPLEMENTATION-SUMMARY.md)** | ⭐ Start here - High-level overview |
| **[WEBSOCKET-CLIENT-PATTERN.md](./WEBSOCKET-CLIENT-PATTERN.md)** | ⭐ Complete pattern documentation |
| **[WEBSOCKET-ARCHITECTURE-DIAGRAMS.md](./WEBSOCKET-ARCHITECTURE-DIAGRAMS.md)** | Visual diagrams |
| **[WEBSOCKET-CLIENT-BASE.md](./WEBSOCKET-CLIENT-BASE.md)** | Base client deep dive |
| **[WEBSOCKET-SINGLETON-REFACTORING.md](./WEBSOCKET-SINGLETON-REFACTORING.md)** | Migration guide |

## 🔑 Key Files

```
frontend/
├── src/
│   ├── plugins/
│   │   ├── wsClientBase.ts          ⭐ Base client class
│   │   ├── barsClient.ts            ⭐ Bars client factory
│   │   └── ws-types.ts              ⭐ Type definitions
│   └── services/
│       └── datafeedService.ts       ⭐ Usage example
└── docs/
    ├── WEBSOCKET-IMPLEMENTATION-SUMMARY.md
    ├── WEBSOCKET-CLIENT-PATTERN.md
    ├── WEBSOCKET-ARCHITECTURE-DIAGRAMS.md
    └── WEBSOCKET-CLIENT-BASE.md
```

## 🎯 Common Tasks

### Task: Create New WebSocket Client

When you add a new WebSocket route to the backend, the frontend client is **automatically generated**!

**1. Backend**: Add new router (e.g., for quotes)
```python
# backend/src/trading_api/ws/quotes.py
router = OperationRouter(prefix="quotes.", tags=["datafeed"])

@router.send("subscribe", reply="subscribe.response")
async def send_subscribe(payload: QuoteDataSubscriptionRequest, client: Client):
    # Implementation
```

**2. Frontend**: Regenerate clients
```bash
npm run client:generate && npm run ws:generate
```

**3. Result**: New factory automatically available!
```typescript
// Auto-generated in src/clients/ws-generated/client.ts
import { QuotesWebSocketClientFactory } from '@/clients/ws-generated/client'
import type { QuoteDataSubscriptionRequest, QuoteData } from '@/clients/ws-types-generated'

const wsClient = QuotesWebSocketClientFactory()

const subId = await wsClient.subscribe(
  { symbols: ['AAPL'], fast_symbols: ['GOOGL'] },
  (quote) => console.log('New quote:', quote)
)
```

**No manual code needed** - Types and client factory both auto-generated from AsyncAPI spec!
```

### Task: Handle Errors

```typescript
try {
  const subId = await wsClient.subscribe(params, callback)
} catch (error) {
  if (error.message.includes('timeout')) {
    console.error('Server did not respond')
  } else if (error.message.includes('Topic mismatch')) {
    console.error('Unexpected server response')
  } else {
    console.error('Subscription failed:', error)
  }
}
```

### Task: Multiple Subscriptions

```typescript
const wsClient = BarsWebSocketClientFactory()

// Subscribe to multiple symbols
const subs = await Promise.all([
  wsClient.subscribe({ symbol: 'AAPL', resolution: '1' }, onAAPL),
  wsClient.subscribe({ symbol: 'GOOGL', resolution: '5' }, onGOOGL),
  wsClient.subscribe({ symbol: 'MSFT', resolution: 'D' }, onMSFT),
])

// All share the same WebSocket connection!
```

### Task: Cleanup

```typescript
// Service level cleanup
class MyService {
  private subscriptions = new Set<string>()
  private wsClient = BarsWebSocketClientFactory()

  async cleanup() {
    for (const subId of this.subscriptions) {
      await this.wsClient.unsubscribe(subId)
    }
    this.subscriptions.clear()
  }
}

// Component level cleanup (Vue)
import { onUnmounted } from 'vue'

onUnmounted(() => {
  service.cleanup()
})
```

## 🏗️ Architecture Quick View

```
Application (Service)
    │
    │ Uses interface
    ▼
Client Factory
    │
    │ Creates
    ▼
Base Client (Singleton)
    │
    │ Uses
    ▼
Native WebSocket API
```

## 🎨 Key Patterns

| Pattern | Purpose | Benefit |
|---------|---------|---------|
| **Singleton** | One connection per URL | Resource efficiency |
| **Factory** | Simple instantiation | Clean API |
| **Repository** | Interface-based | Testability |
| **Observer** | Callback subscriptions | Decoupled communication |
| **Promise** | Async operations | Modern syntax |

## 🔄 Message Protocol

**Subscribe Request** (Client → Server):
```json
{
  "type": "bars.subscribe",
  "payload": { "symbol": "AAPL", "resolution": "1" }
}
```

**Subscribe Response** (Server → Client):
```json
{
  "type": "bars.subscribe.response",
  "payload": { "status": "ok", "topic": "bars:AAPL:1" }
}
```

**Data Update** (Server → Client):
```json
{
  "type": "bars.update",
  "payload": { "time": 1697..., "open": 150, ... }
}
```

## 📊 Topic Structure

Format: `{domain}:{key1}:{key2}:...`

Examples:
- `bars:AAPL:1` - Apple, 1-minute bars
- `bars:GOOGL:5` - Alphabet, 5-minute bars
- `quotes:TSLA` - Tesla quotes
- `trades:MSFT` - Microsoft trades

## ⚡ Performance Tips

1. **Reuse clients** - Singleton ensures shared connections
2. **Batch subscriptions** - Use `Promise.all()` for multiple subs
3. **Clean up properly** - Always unsubscribe when done
4. **Monitor connection** - Check `isConnected()` periodically
5. **Handle reconnection** - Let base client handle it automatically

## 🧪 Testing

### Unit Test Example

```typescript
import { vi } from 'vitest'
import { BarsWebSocketClientFactory } from '@/clients/ws-generated/client'

describe('BarsWebSocketClient', () => {
  it('should subscribe to bars', async () => {
    const client = BarsWebSocketClientFactory()
    const callback = vi.fn()

    const subId = await client.subscribe(
      { symbol: 'AAPL', resolution: '1' },
      callback
    )

    expect(subId).toBeDefined()
  })
})
```

### Mock for Testing

```typescript
class MockBarsClient implements BarsWebSocketInterface {
  async subscribe(params, callback) {
    // Generate mock data
    const mockBar = { time: Date.now(), open: 150, ... }
    callback(mockBar)
    return 'mock-sub-id'
  }

  async unsubscribe(id) {
    // Mock cleanup
  }
}
```

## 🚨 Common Issues

### Issue: Connection keeps closing
**Cause**: No heartbeat messages
**Solution**: Backend sends periodic updates or implement ping

### Issue: No updates received
**Cause**: Subscription not confirmed
**Solution**: Check server logs, verify topic matches

### Issue: Multiple connections
**Cause**: Not using factory pattern
**Solution**: Always use `BarsWebSocketClientFactory()`

### Issue: Memory leak
**Cause**: Not unsubscribing
**Solution**: Always call `unsubscribe()` in cleanup

## 🔗 Quick Links

- **Main Docs**: [WEBSOCKET-CLIENT-PATTERN.md](./WEBSOCKET-CLIENT-PATTERN.md)
- **Backend API**: [`../backend/docs/websockets.md`](../backend/docs/websockets.md)
- **Base Client**: [`src/plugins/wsClientBase.ts`](./src/plugins/wsClientBase.ts)
- **Example Usage**: [`src/services/datafeedService.ts`](./src/services/datafeedService.ts)

## 💡 Pro Tips

1. **Always use factories** - `BarsWebSocketClientFactory()` not `new WebSocketClientBase()`
2. **Store subscription IDs** - You'll need them for cleanup
3. **Use TypeScript strict mode** - Catches errors at compile time
4. **Check connection state** - Use `isConnected()` before operations
5. **Log important events** - Helps with debugging
6. **Handle all errors** - Wrap subscriptions in try-catch
7. **Test with mocks** - Use interface-based design for testing
8. **Document your clients** - Follow the pattern for consistency

---

**Version**: 1.0.0
**Date**: October 13, 2025
**For**: Quick reference and developer onboarding
