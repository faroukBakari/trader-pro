# WebSocket Real-Time Data Streaming

**Version**: 1.0.0
**Last Updated**: October 12, 2025
**Status**: ✅ Production Ready

> ⚠️ **CRITICAL**: When implementing new WebSocket features or routers, you **MUST** follow the router code generation mechanism documented in [`backend/src/trading_api/ws/WS-ROUTER-GENERATION.md`](../src/trading_api/ws/WS-ROUTER-GENERATION.md). This ensures type safety, eliminates generic overhead, and maintains consistency across all WebSocket operations. **Never create WebSocket routers manually**.

## Overview

The Trading API provides real-time market data streaming via WebSocket connections using the FastWS framework. This enables bidirectional communication for subscribing to live market data updates with minimal latency.

## Quick Start

### Endpoint

```
ws://localhost:8000/api/v1/ws
```

### Basic Connection Example

```javascript
// JavaScript/TypeScript
const ws = new WebSocket("ws://localhost:8000/api/v1/ws");

ws.onopen = () => {
  console.log("Connected to Trading API WebSocket");

  // Subscribe to Apple 1-minute bars
  ws.send(
    JSON.stringify({
      type: "bars.subscribe",
      payload: {
        symbol: "AAPL",
        params: { resolution: "1" },
      },
    })
  );
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Received:", message);

  if (message.type === "bars.update") {
    console.log("New bar:", message.payload);
  }
};
```

## Architecture

### Technology Stack

- **Framework**: FastWS 0.1.7 (AsyncAPI-documented WebSocket wrapper for FastAPI)
- **Protocol**: WebSocket (RFC 6455) over HTTP upgrade
- **Documentation**: AsyncAPI 2.4.0 specification
- **Message Format**: JSON with strict Pydantic validation
- **Transport**: ASGI via Uvicorn

### ⚠️ CRITICAL: Topic Builder Contract

**MUST BE IDENTICAL ACROSS BACKEND AND FRONTEND**

The topic builder is the **core contract** for WebSocket subscriptions. The algorithm must produce identical topic strings in both Python (backend) and TypeScript (frontend).

#### Topic Format

```
{route}:{JSON-serialized-params}
```

Where:

- `{route}` = WebSocket route name (e.g., "bars", "orders", "positions")
- `{JSON-serialized-params}` = Compact JSON with **sorted keys**, no whitespace

**Examples**:

```
bars:{"resolution":"1","symbol":"AAPL"}
orders:{"accountId":"TEST-001"}
executions:{"accountId":"TEST-001","symbol":"AAPL"}
positions:{"accountId":"TEST-001"}
equity:{"accountId":"TEST-001"}
broker-connection:{"accountId":"TEST-001"}
```

#### Implementation (Python)

**Location**: `backend/src/trading_api/ws/router_interface.py`

```python
def buildTopicParams(obj: Any) -> str:
    """
    JSON stringify with sorted object keys for consistent serialization.
    Handles nested objects and arrays recursively.
    """
    def sort_recursive(item: Any) -> Any:
        if isinstance(item, dict):
            # Sort dict keys alphabetically
            return {k: sort_recursive(v) for k, v in sorted(item.items())}
        elif isinstance(item, list):
            # Recursively process list elements
            return [sort_recursive(element) for element in item]
        elif item is None:
            # Convert null to empty string
            return ""
        else:
            return item

    sorted_obj = sort_recursive(obj)
    # Compact JSON: no whitespace, separators=(",", ":")
    return json.dumps(sorted_obj, separators=(",", ":"))

class WsRouterInterface(OperationRouter, WsRouterProto):
    def topic_builder(self, params: BaseModel) -> str:
        return f"{self.route}:{buildTopicParams(params.model_dump())}"
```

#### Algorithm Requirements

**Both implementations MUST**:

1. **Sort object keys alphabetically** at all nesting levels
2. **Use compact JSON** with separators `(",", ":")` - no spaces
3. **Handle nested objects** recursively with sorted keys
4. **Handle arrays** by processing each element recursively
5. **Handle null values** by converting to empty string `""`
6. **Match parameter casing** exactly as defined in Pydantic models

#### Frontend Compliance

**Location**: `frontend/src/plugins/wsClientBase.ts`

The frontend MUST implement the identical algorithm:

```typescript
function buildTopicParams(obj: unknown): string {
  if (obj === null || obj === undefined) {
    return "";
  }

  if (typeof obj !== "object") {
    return JSON.stringify(obj);
  }

  if (Array.isArray(obj)) {
    return `[${obj.map(buildTopicParams).join(",")}]`;
  }

  const objRecord = obj as Record<string, unknown>;
  const sortedKeys = Object.keys(objRecord).sort();
  const pairs = sortedKeys.map(
    (key) => `${JSON.stringify(key)}:${buildTopicParams(objRecord[key])}`
  );
  return `{${pairs.join(",")}}`;
}
```

#### Why This Matters

**Subscription Flow**:

1. Frontend sends subscription request with params
2. Backend generates topic using `topic_builder(params)`
3. Backend returns topic in `subscribe.response`
4. Frontend must use **exact same topic** to receive updates
5. Backend broadcasts updates to subscribers of that exact topic string

**Failure Scenario**:

```python
# Backend generates: "orders:{\"accountId\":\"TEST-001\"}"
# Frontend expects: "orders:TEST-001"
# Result: No updates received, subscription appears dead
```

#### Testing Topic Builder

Always verify both implementations produce identical output:

```python
# Backend test
params = OrderSubscriptionRequest(accountId="TEST-001", symbol="AAPL")
topic = topic_builder(params)
assert topic == 'orders:{"accountId":"TEST-001","symbol":"AAPL"}'
```

```typescript
// Frontend test
const params = { accountId: "TEST-001", symbol: "AAPL" };
const topic = `orders:${buildTopicParams(params)}`;
assert(topic === 'orders:{"accountId":"TEST-001","symbol":"AAPL"}');
```

#### Anti-Patterns

❌ **Simple String Concatenation** (WRONG):

```python
# Backend
topic = f"bars:{symbol}:{resolution}"  # NO!

# Frontend
topic = `bars:${symbol}:${resolution}`  // NO!
```

✅ **JSON Serialization** (CORRECT):

```python
# Backend
topic = f"{route}:{buildTopicParams(params.model_dump())}"

# Frontend
topic = `${route}:${buildTopicParams(params)}`
```

#### Compliance Checklist

When implementing WebSocket features:

- [ ] Backend uses `WsRouterInterface.topic_builder()`
- [ ] Frontend uses `buildTopicParams()` helper
- [ ] Both sort object keys alphabetically
- [ ] Both use compact JSON (no whitespace)
- [ ] Both handle nested objects/arrays recursively
- [ ] Both convert null to empty string
- [ ] Parameter names match Pydantic model fields exactly
- [ ] Tests verify identical topic generation

See `docs/WEBSOCKET-CLIENTS.md` for frontend implementation details.

### Message Structure

All WebSocket messages follow a consistent envelope format:

```typescript
interface WebSocketMessage<T> {
  type: string; // Operation identifier (e.g., "bars.subscribe")
  payload?: T; // Operation-specific data (optional)
}
```

### Operation Types

FastWS defines two operation categories:

1. **SEND**: Client → Server (with optional reply)
2. **RECEIVE**: Server → Client (broadcast)

## API Reference

### Operations

#### 1. Subscribe to Bar Updates

**Type**: SEND (Client → Server)
**Operation**: `bars.subscribe`
**Reply**: `bars.subscribe.response`

Subscribe to real-time OHLC bar updates for a specific symbol and resolution.

**Request**:

```json
{
  "type": "bars.subscribe",
  "payload": {
    "symbol": "AAPL",
    "params": {
      "resolution": "1"
    }
  }
}
```

**Response**:

```json
{
  "type": "bars.subscribe.response",
  "payload": {
    "status": "ok",
    "symbol": "AAPL",
    "message": "Subscribed to AAPL",
    "topic": "bars:AAPL:1"
  }
}
```

**Parameters**:

- `symbol` (string, required): Symbol ticker (e.g., "AAPL", "GOOGL", "MSFT")
- `params.resolution` (string, optional): Time resolution. Default: "1"
  - Intraday: "1", "5", "15", "30", "60" (minutes)
  - Daily+: "D" (day), "W" (week), "M" (month)

**Returns**:

- `status` (string): "ok" or "error"
- `symbol` (string): Echo of subscribed symbol
- `message` (string): Human-readable status message
- `topic` (string): Internal topic identifier for this subscription

#### 2. Unsubscribe from Updates

**Type**: SEND (Client → Server)
**Operation**: `bars.unsubscribe`
**Reply**: `bars.unsubscribe.response`

Remove subscription to bar updates for a symbol/resolution pair.

**Request**:

```json
{
  "type": "bars.unsubscribe",
  "payload": {
    "symbol": "AAPL",
    "params": {
      "resolution": "1"
    }
  }
}
```

**Response**:

```json
{
  "type": "bars.unsubscribe.response",
  "payload": {
    "status": "ok",
    "symbol": "AAPL",
    "message": "Unsubscribed from AAPL",
    "topic": "bars:AAPL:1"
  }
}
```

#### 3. Bar Data Updates

**Type**: RECEIVE (Server → Client)
**Operation**: `bars.update`

Real-time OHLC bar data broadcast to subscribed clients.

**Message**:

```json
{
  "type": "bars.update",
  "payload": {
    "time": 1697097600000,
    "open": 150.0,
    "high": 151.0,
    "low": 149.5,
    "close": 150.5,
    "volume": 1000000
  }
}
```

**Payload** (Bar model):

- `time` (integer): Unix timestamp in milliseconds
- `open` (float): Opening price
- `high` (float): Highest price
- `low` (float): Lowest price
- `close` (float): Closing price
- `volume` (integer): Trading volume

## Topic-Based Pub/Sub

### Topic Format

Internal topic structure: `bars:{SYMBOL}:{RESOLUTION}`

**Examples**:

- `bars:AAPL:1` → Apple Inc., 1-minute bars
- `bars:GOOGL:5` → Alphabet Inc., 5-minute bars
- `bars:MSFT:D` → Microsoft Corp., daily bars
- `bars:TSLA:W` → Tesla Inc., weekly bars

### Subscription Behavior

- **Multi-Symbol**: Each client can subscribe to multiple symbols simultaneously
- **Multi-Resolution**: Same symbol with different resolutions creates separate topics
- **Broadcast Filtering**: Updates sent only to clients subscribed to that specific topic
- **Automatic Cleanup**: Subscriptions cleared on client disconnect

### Example Multi-Subscription

```javascript
// Subscribe to multiple symbols and resolutions
const subscriptions = [
  { symbol: "AAPL", resolution: "1" },
  { symbol: "AAPL", resolution: "D" },
  { symbol: "GOOGL", resolution: "5" },
  { symbol: "MSFT", resolution: "15" },
];

subscriptions.forEach((sub) => {
  ws.send(
    JSON.stringify({
      type: "bars.subscribe",
      payload: {
        symbol: sub.symbol,
        params: { resolution: sub.resolution },
      },
    })
  );
});

// Each subscription creates a unique topic:
// - bars:AAPL:1
// - bars:AAPL:D
// - bars:GOOGL:5
// - bars:MSFT:15
```

## Connection Management

### Configuration

The WebSocket server is configured with the following settings:

```python
# From main.py
wsApp = FastWSAdapter(
    title="Trading WebSockets",
    version="1.0.0",
    heartbeat_interval=30.0,           # Seconds
    max_connection_lifespan=3600.0,    # Seconds (1 hour)
    asyncapi_url="/api/v1/ws/asyncapi.json",
    asyncapi_docs_url="/api/v1/ws/asyncapi"
)
```

### Lifecycle Phases

1. **Connection**

   - Client initiates WebSocket handshake to `/api/v1/ws`
   - Server accepts connection (auto_ws_accept=True)
   - Unique client ID (UUID) assigned

2. **Authentication** (Optional)

   - Current: No authentication required
   - Future: JWT token validation via auth_handler

3. **Active Session**

   - Client sends subscribe/unsubscribe messages
   - Server broadcasts updates to subscribed topics
   - Heartbeat monitoring ensures client is responsive

4. **Disconnection**
   - Graceful: Client closes connection
   - Timeout: No message within heartbeat_interval
   - Lifespan: Connection exceeds max_connection_lifespan
   - Error: Protocol violations or validation failures

### Heartbeat Requirements

**Interval**: 30 seconds

Clients must send at least one message every 30 seconds to maintain the connection. Any valid operation (subscribe, unsubscribe) counts as heartbeat activity.

**Timeout Behavior**:

```json
// Connection closed with WebSocket error
{
  "code": 1003,
  "reason": "Connection timed out. Heartbeat interval 30.0. Max connection lifespan 3600.0"
}
```

**Best Practice**:

```javascript
// Send periodic ping via subscribe/unsubscribe to keep connection alive
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    // Re-subscribe to existing subscription as heartbeat
    ws.send(
      JSON.stringify({
        type: "bars.subscribe",
        payload: { symbol: "AAPL", params: { resolution: "1" } },
      })
    );
  }
}, 25000); // 25 seconds (before 30s timeout)
```

### Maximum Connection Duration

**Lifespan**: 3600 seconds (1 hour)

All connections are automatically closed after 1 hour. Clients should implement reconnection logic.

**Reconnection Strategy**:

```javascript
function connectWebSocket() {
  const ws = new WebSocket("ws://localhost:8000/api/v1/ws");

  ws.onclose = (event) => {
    console.log("Disconnected:", event.code, event.reason);
    // Reconnect after 5 seconds
    setTimeout(() => {
      connectWebSocket();
    }, 5000);
  };

  return ws;
}
```

## Error Handling

### WebSocket Error Codes

FastWS uses standard WebSocket close codes:

| Code | Reason                     | Description                                |
| ---- | -------------------------- | ------------------------------------------ |
| 1003 | Unsupported Data           | Invalid message format or validation error |
| 1003 | Could not validate payload | Pydantic validation failed                 |
| 1003 | No matching type           | Unknown operation type                     |
| 1003 | Connection timed out       | Heartbeat interval exceeded                |

### Common Error Scenarios

#### 1. Invalid Message Format

**Cause**: Message is not valid JSON or missing required fields

**Example**:

```javascript
// ❌ Wrong
ws.send("not json");

// ✅ Correct
ws.send(
  JSON.stringify({
    type: "bars.subscribe",
    payload: { symbol: "AAPL", params: {} },
  })
);
```

#### 2. Unknown Operation

**Cause**: Operation type not registered in FastWS

**Example**:

```javascript
// ❌ Wrong
ws.send(
  JSON.stringify({
    type: "unknown.operation",
    payload: {},
  })
);

// ✅ Correct - Use documented operations
ws.send(
  JSON.stringify({
    type: "bars.subscribe",
    payload: { symbol: "AAPL", params: {} },
  })
);
```

#### 3. Validation Error

**Cause**: Payload doesn't match Pydantic model schema

**Example**:

```javascript
// ❌ Wrong - missing required 'symbol' field
ws.send(
  JSON.stringify({
    type: "bars.subscribe",
    payload: { params: {} },
  })
);

// ✅ Correct
ws.send(
  JSON.stringify({
    type: "bars.subscribe",
    payload: { symbol: "AAPL", params: {} },
  })
);
```

### Client-Side Error Handling

```javascript
ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = (event) => {
  console.log("Closed:", event.code, event.reason);

  if (event.code === 1003) {
    // Protocol error - check message format
    console.error("Protocol violation:", event.reason);
  }
};

ws.onmessage = (event) => {
  try {
    const message = JSON.parse(event.data);

    // Check for error responses
    if (message.payload?.status === "error") {
      console.error("Operation failed:", message.payload.message);
    }
  } catch (err) {
    console.error("Failed to parse message:", err);
  }
};
```

## Testing

### Integration Tests

WebSocket endpoints are tested using FastAPI's TestClient:

```python
# From tests/test_ws_datafeed.py
from fastapi.testclient import TestClient
from trading_api.main import apiApp

def test_subscribe_to_bars():
    client = TestClient(apiApp)

    with client.websocket_connect("/api/v1/ws") as websocket:
        # Send subscribe message
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {
                "symbol": "AAPL",
                "params": {"resolution": "1"}
            }
        })

        # Receive response
        response = websocket.receive_json()

        # Assertions
        assert response["type"] == "bars.subscribe.response"
        assert response["payload"]["status"] == "ok"
        assert response["payload"]["symbol"] == "AAPL"
        assert response["payload"]["topic"] == "bars:AAPL:1"
```

### Test Coverage

Current test suite covers:

- ✅ Basic WebSocket connection
- ✅ Subscribe operation
- ✅ Unsubscribe operation
- ✅ Multiple symbols subscription
- ✅ Multiple resolutions per symbol
- ✅ Default resolution handling
- ✅ Server-side broadcast to subscribers

### Running Tests

```bash
cd backend
make test

# Run specific WebSocket tests
poetry run pytest tests/test_ws_datafeed.py -v
```

## AsyncAPI Documentation

### Interactive Documentation

Visit the AsyncAPI UI in your browser:

```
http://localhost:8000/api/v1/ws/asyncapi
```

This provides:

- Complete operation reference
- Message schemas
- Payload examples
- Channel descriptions

### AsyncAPI Specification

Raw AsyncAPI 2.4.0 JSON specification:

```
http://localhost:8000/api/v1/ws/asyncapi.json
```

Use this for:

- Code generation
- Contract testing
- Third-party integrations
- Documentation tools

## Implementation Details

### FastWS Framework

FastWS is an open-source WebSocket framework built on top of FastAPI, similar to how FastAPI uses OpenAPI for REST APIs.

**Key Features**:

- AsyncAPI specification generation
- Operation-based routing (similar to HTTP routes)
- Automatic message validation via Pydantic
- Built-in connection management
- Topic-based pub/sub broadcasting

**Source**: https://github.com/endrekrohn/fastws

### Router Code Generation

⚠️ **CRITICAL**: All WebSocket routers in this project are generated from a generic template using code generation. This approach provides:

- ✅ Better IDE support and autocomplete
- ✅ Eliminates generic type parameters at runtime
- ✅ Full type inference without `Generic[T, U]`
- ✅ Automatic quality checks (Black, isort, Ruff, mypy)
- ✅ Single source of truth (`ws/generic.py`)

**To add a new WebSocket router**:

1. Update `ROUTER_SPECS` in `scripts/generate_ws_router.py`
2. Run `make generate-ws-routers`
3. Use generated router from `ws/generated/`

**Complete documentation**: See [`backend/src/trading_api/ws/WS-ROUTER-GENERATION.md`](../src/trading_api/ws/WS-ROUTER-GENERATION.md) for the full guide.

### Project Structure

```
backend/src/trading_api/
├── main.py                         # WebSocket app initialization
├── plugins/
│   └── fastws_adapter.py          # FastWSAdapter with publish() helper
└── ws/
    ├── __init__.py                # Module exports
    ├── generic.py                 # Generic template (source of truth) ⚠️
    ├── datafeed.py                # Usage with TYPE_CHECKING guard
    └── generated/                 # Auto-generated routers ⚠️
        ├── __init__.py            # Generated exports
        └── barwsrouter.py         # Generated BarWsRouter class
```

⚠️ **Router Generation**: The `generated/` directory contains auto-generated concrete router classes from the `generic.py` template. See [`WS-ROUTER-GENERATION.md`](../src/trading_api/ws/WS-ROUTER-GENERATION.md) for details.

### Key Components

#### FastWSAdapter (plugins/fastws_adapter.py)

```python
class FastWSAdapter(FastWS):
    """Self-contained WebSocket adapter with embedded endpoint"""

    async def publish(
        self,
        topic: str,
        data: BaseModel,
        route: str = "bars"
    ) -> None:
        """broadcast data update to all subscribed clients"""
        message = Message(type=route, payload=data.model_dump())
        await self.server_send(message, topic=topic)
```

#### Operation Router (ws/datafeed.py)

```python
router = OperationRouter(prefix="bars.", tags=["datafeed"])

@router.send("subscribe", reply="subscribe.response")
async def send_subscribe(
    payload: SubscriptionRequest,
    client: Client,
) -> SubscriptionResponse:
    topic = bars_topic_builder(payload.symbol, payload.params)
    client.subscribe(topic)
    return SubscriptionResponse(...)

@router.recv("update")
async def update(payload: Bar) -> Bar:
    """Broadcast data updates to subscribed clients"""
    return payload
```

#### Integration (main.py)

```python
# Import consolidated routers from ws module
from .ws import ws_routers

# Create WebSocket app
wsApp = FastWSAdapter(...)

# Include all WebSocket routers
for ws_router in ws_routers:
    wsApp.include_router(ws_router)

# Register AsyncAPI docs
wsApp.setup(apiApp)

# Define endpoint
@apiApp.websocket("/api/v1/ws")
async def websocket_endpoint(
    client: Annotated[Client, Depends(wsApp.manage)]
):
    await wsApp.serve(client)
```

**Note**: The `ws` module's `__init__.py` consolidates all routers from topical files (datafeed, trading, account, etc.) into a single `ws_routers` list. See [`WS-ROUTER-GENERATION.md`](../src/trading_api/ws/WS-ROUTER-GENERATION.md) for details.

## Performance Considerations

### Connection Limits

- **Current**: No hard limit (controlled by OS and Uvicorn)
- **Recommended**: Use reverse proxy (nginx) for production load balancing
- **Monitoring**: Track connection count via `wsApp.connections`

### Message Throughput

- **Async I/O**: Non-blocking message handling via asyncio
- **Broadcast Efficiency**: Uses asyncio.TaskGroup for parallel client sends
- **Serialization**: Pydantic's optimized JSON serialization

### Scalability

For production deployments:

1. Use multiple Uvicorn workers
2. Implement Redis pub/sub for cross-worker broadcasting
3. Add WebSocket sticky sessions in load balancer
4. Monitor memory usage per connection

## Security Considerations

### Current State

- ✅ Message validation via Pydantic
- ✅ Connection timeouts (heartbeat + lifespan)
- ✅ CORS configuration at FastAPI level
- ⏳ Authentication (planned - JWT tokens)
- ⏳ Rate limiting (planned - per-client limits)
- ⏳ SSL/TLS (production deployment)

### Production Checklist

- [ ] Enable JWT authentication via `auth_handler`
- [ ] Implement per-client rate limiting
- [ ] Use WSS (WebSocket Secure) over HTTPS
- [ ] Add connection origin validation
- [ ] Set up monitoring and alerting
- [ ] Configure reverse proxy (nginx/Caddy)
- [ ] Implement graceful shutdown handling

## Future Enhancements

### Planned Features (v2)

1. **Additional Channels**

   - `quotes.*` - Real-time quote snapshots
   - `trades.*` - Individual trade updates
   - `orderbook.*` - Order book depth updates

2. **Private Channels** (Authenticated)

   - `account.*` - Account balance updates
   - `positions.*` - Position changes
   - `orders.*` - Order status updates
   - `notifications.*` - User-specific alerts

3. **Client Features**

   - Auto-reconnection with exponential backoff
   - Message queuing during disconnection
   - Subscription state persistence
   - TypeScript client SDK generation

4. **Infrastructure**
   - Redis pub/sub for horizontal scaling
   - Prometheus metrics export
   - WebSocket compression (per-message deflate)
   - Custom binary protocol option

## Troubleshooting

### Connection Fails Immediately

**Symptoms**: WebSocket closes right after opening

**Solutions**:

- Verify endpoint URL: `ws://localhost:8000/api/v1/ws`
- Check backend is running: `make dev`
- Review server logs for errors
- Test with simple WebSocket client first

### No Updates Received

**Symptoms**: Subscribe succeeds but no `bars.update` messages

**Possible Causes**:

1. Not subscribed to correct topic
2. No server-side data being broadcasted
3. WebSocket connection silently dropped

**Solutions**:

```javascript
// Verify subscription response
const response = await waitForMessage(ws, "bars.subscribe.response");
console.log("Subscribed to:", response.payload.topic);

// Monitor connection state
ws.onclose = (event) => {
  console.log("Connection closed:", event.code, event.reason);
};
```

### Frequent Disconnections

**Symptoms**: Connection drops every ~30 seconds

**Cause**: Heartbeat timeout (no messages sent)

**Solution**: Implement heartbeat keep-alive

```javascript
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        type: "bars.subscribe",
        payload: { symbol: "AAPL", params: { resolution: "1" } },
      })
    );
  }
}, 25000);
```

## Bar Broadcasting Service

The Trading API includes an optional background service that automatically generates and broadcasts mocked bar data to subscribed WebSocket clients.

### Overview

The **BarBroadcaster** service:

- Runs as a background task within the FastAPI application
- Generates realistic bar variations using `DatafeedService.mock_last_bar()`
- Broadcasts updates only to topics with active subscribers (minimal overhead)
- Fully configurable via environment variables
- Includes comprehensive metrics tracking

### Configuration

Control the broadcaster using environment variables:

```bash
# Enable/disable broadcaster (default: true)
BAR_BROADCASTER_ENABLED=true

# Broadcast interval in seconds (default: 2.0)
BAR_BROADCASTER_INTERVAL=2.0

# Symbols to broadcast (comma-separated, default: AAPL,GOOGL,MSFT)
BAR_BROADCASTER_SYMBOLS=AAPL,GOOGL,MSFT,TSLA

# Resolutions to broadcast (comma-separated, default: 1)
BAR_BROADCASTER_RESOLUTIONS=1,5,D
```

### Usage

#### Default Configuration

By default, the broadcaster is enabled and broadcasts for AAPL, GOOGL, and MSFT at 1-minute resolution every 2 seconds.

```bash
# Start API with default broadcaster settings
cd backend
make dev
```

You'll see startup logs:

```
📡 Bar broadcaster started: symbols=['AAPL', 'GOOGL', 'MSFT'], interval=2.0s
```

#### Custom Configuration

```bash
# Fast updates for day trading simulation
export BAR_BROADCASTER_INTERVAL=0.5
export BAR_BROADCASTER_SYMBOLS=AAPL,TSLA
export BAR_BROADCASTER_RESOLUTIONS=1
make dev

# Multiple timeframes
export BAR_BROADCASTER_RESOLUTIONS=1,5,15,D
make dev

# Disable broadcaster
export BAR_BROADCASTER_ENABLED=false
make dev
```

#### Metrics

The broadcaster tracks performance metrics accessible during runtime:

```python
from trading_api.main import bar_broadcaster

# Get metrics
if bar_broadcaster:
    metrics = bar_broadcaster.metrics
    print(f"Broadcasts sent: {metrics['broadcasts_sent']}")
    print(f"Broadcasts skipped: {metrics['broadcasts_skipped']}")
    print(f"Errors: {metrics['errors']}")
```

**Metrics include**:

- `is_running`: Boolean indicating if broadcaster is active
- `interval`: Current broadcast interval in seconds
- `symbols`: List of symbols being broadcast
- `resolutions`: List of resolutions being broadcast
- `broadcasts_sent`: Total number of successful broadcasts
- `broadcasts_skipped`: Number of skipped broadcasts (no subscribers)
- `errors`: Number of errors encountered

### Performance

The broadcaster is designed to be efficient:

1. **Selective Broadcasting**: Only sends data to topics with active subscribers
2. **Lightweight Generation**: Bar generation is fast (< 1ms per symbol)
3. **Async Operation**: Doesn't block the main event loop
4. **Metrics Tracking**: Monitor performance in real-time

**Typical Performance**:

- CPU overhead: < 1% on modern hardware
- Memory: ~10MB for service
- Latency: < 5ms from generation to broadcast

### Architecture

```
┌─────────────────────┐
│  FastAPI Lifespan   │
│  (main.py)          │
└──────────┬──────────┘
           │
           │ startup
           ▼
┌─────────────────────┐
│  BarBroadcaster     │  ◄─── Configuration (env vars)
│  Background Task    │
└──────────┬──────────┘
           │
           │ every N seconds
           ▼
┌─────────────────────┐
│  DatafeedService    │
│  .mock_last_bar()   │
└──────────┬──────────┘
           │
           │ Bar data
           ▼
┌─────────────────────┐
│  FastWSAdapter      │
│  .publish()         │
└──────────┬──────────┘
           │
           │ WebSocket
           ▼
┌─────────────────────┐
│  Subscribed Clients │
│  (browsers, apps)   │
└─────────────────────┘
```

### Testing

The broadcaster is thoroughly tested:

**Unit Tests** (`tests/test_bar_broadcaster.py`):

- Lifecycle management (start/stop)
- Subscriber checking logic
- Broadcasting behavior
- Error handling
- Metrics tracking

**Integration Tests** (`tests/test_ws_datafeed.py`):

- End-to-end WebSocket broadcasting
- Message format validation
- Subscription filtering

Run tests:

```bash
cd backend
pytest tests/test_bar_broadcaster.py -v
pytest tests/test_ws_datafeed.py -v
```

### Production Considerations

For production environments, consider:

1. **Disable for Production Data**: Turn off broadcaster when using real market data

   ```bash
   export BAR_BROADCASTER_ENABLED=false
   ```

2. **Resource Scaling**: Adjust interval based on number of clients

   ```bash
   # More clients = longer interval to reduce load
   export BAR_BROADCASTER_INTERVAL=5.0
   ```

3. **Monitoring**: Track metrics to ensure performance

   - broadcasts_sent should increase steadily
   - broadcasts_skipped is OK (means no subscribers)
   - errors should be 0 or very low

4. **Offloading**: For high-volume scenarios, see `docs/bar-broadcasting.md` for Redis-based approach

## Resources

### Documentation

- **AsyncAPI Spec**: http://localhost:8000/api/v1/ws/asyncapi.json
- **Interactive Docs**: http://localhost:8000/api/v1/ws/asyncapi
- **Architecture**: See `ARCHITECTURE.md` (Real-Time Architecture section)
- **Backend README**: `backend/README.md`
- **Router Generation**: `backend/src/trading_api/ws/WS-ROUTER-GENERATION.md` (backend code generation)
- **Frontend Client Generation**: `frontend/WS-CLIENT-AUTO-GENERATION.md` (frontend type-safe clients)
- **Redis Broadcasting**: `backend/docs/bar-broadcasting.md` (future scalable approach)

### Code References

- **Main App**: `backend/src/trading_api/main.py`
- **FastWS Adapter**: `backend/src/trading_api/plugins/fastws_adapter.py`
- **Operations**: `backend/src/trading_api/ws/datafeed.py`
- **Broadcaster**: `backend/src/trading_api/services/bar_broadcaster.py`
- **Configuration**: `backend/src/trading_api/core/config.py`
- **Tests**: `backend/tests/test_ws_datafeed.py`, `backend/tests/test_bar_broadcaster.py`

### Frontend Integration

- **Type Generator**: `frontend/scripts/generate-ws-types.mjs` - Auto-generates TypeScript types from AsyncAPI
- **Base Client**: `frontend/src/plugins/wsClientBase.ts` - WebSocket client implementation
- **Generated Types**: `frontend/src/clients/ws-types-generated/index.ts` - Auto-generated (do not edit)

**Frontend Generation Flow**:

1. Backend exposes AsyncAPI spec at `/api/v1/ws/asyncapi.json`
2. Frontend `generate-ws-types.mjs` downloads spec → generates ALL TypeScript interfaces
3. No hardcoded schema lists - fully automatic discovery!

### External Resources

- **FastWS GitHub**: https://github.com/endrekrohn/fastws
- **FastWS Docs**: See `backend/external_packages/fastws/README.md`
- **AsyncAPI Spec**: https://www.asyncapi.com/docs/reference/specification/v2.4.0
- **WebSocket Protocol**: https://datatracker.ietf.org/doc/html/rfc6455

---

**Last Updated**: October 12, 2025
**Maintainer**: Development Team
**Version**: 1.0.0 (Stable)
