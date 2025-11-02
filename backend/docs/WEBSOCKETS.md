# WebSocket Real-Time Data Streaming

**Version**: 2.0.0 (Modular Architecture)
**Last Updated**: October 30, 2025
**Status**: ✅ Production Ready

> ⚠️ **CRITICAL**: When implementing new WebSocket features or routers, you **MUST** follow the router code generation mechanism documented in [`backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md`](../src/trading_api/shared/ws/WS-ROUTER-GENERATION.md). This ensures type safety, eliminates generic overhead, and maintains consistency across all WebSocket operations. **Never create WebSocket routers manually**.

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

**Location**: `backend/src/trading_api/shared/ws/router_interface.py`

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

class WsRouteInterface(OperationRouter):
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

### ⚠️ Subscription Model Validation (CRITICAL)

**RULE:** Subscription request models MUST NOT have optional parameters.

**Why:** Optional parameters cause topic mismatch between frontend and backend:

- Backend may include default values in response topic string
- Frontend doesn't include optional params in request
- Topics don't match → updates not received

**Validation:** AsyncAPI export validates this automatically (see `scripts/export_asyncapi_spec.py`)

**Example - WRONG:**

```python
class QuoteDataSubscriptionRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)  # ❌ Optional with default
    fast_symbols: List[str] = Field(default_factory=list)  # ❌ Optional with default
```

**Example - CORRECT:**

```python
class QuoteDataSubscriptionRequest(BaseModel):
    symbols: List[str] = Field(..., description="Symbols for slow updates")  # ✅ Required
    fast_symbols: List[str] = Field(..., description="Symbols for fast updates")  # ✅ Required
```

**Validation Enforcement:**

- `make export-asyncapi-spec` fails if optional parameters found
- Error message lists problematic models and parameters
- Fix by making parameters required or removing them entirely

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

- [ ] Backend uses `WsRouteInterface.topic_builder()`
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
- ✅ Single source of truth (`ws/generic_route.py`)

**To add a new WebSocket router**:

1. Add TypeAlias declaration in your module's `ws.py` file (e.g., `modules/datafeed/ws.py`)
2. Run `make generate-ws-routers`
3. Use generated router from your module's `ws_generated/` directory

**Complete documentation**: See [`backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md`](../src/trading_api/shared/ws/WS-ROUTER-GENERATION.md) for the full guide.

### Project Structure

```
backend/src/trading_api/
├── main.py                              # Minimal entrypoint (calls create_app)
├── app_factory.py                       # Application factory
├── models/                              # Centralized models (shared)
│   ├── broker/                         # Order, Position, Execution models
│   └── market/                         # Bar, Quote, Instrument models
├── shared/                              # Always loaded
│   ├── module_interface.py             # Module Protocol definition
│   ├── module_registry.py              # Module Registry
│   ├── api/                            # Shared API (health, versions)
│   ├── plugins/
│   │   └── fastws_adapter.py          # FastWSAdapter with publish() helper
│   ├── ws/                             # WebSocket infrastructure
│   │   ├── router_interface.py        # WsRouteInterface, WsRouteService Protocol
│   │   ├── generic_route.py           # Generic WsRouter template (source of truth) ⚠️
│   │   └── WS-ROUTER-GENERATION.md    # Router generation documentation
│   └── tests/                          # Shared test fixtures
└── modules/                             # Pluggable modules
    ├── datafeed/                       # Market data module
    │   ├── __init__.py                 # DatafeedModule
    │   ├── service.py                  # DatafeedService (implements WsRouteService)
    │   ├── api.py                      # DatafeedApi (REST endpoints)
    │   ├── ws.py                       # DatafeedWsRouters + TypeAlias declarations
    │   ├── ws_generated/               # Auto-generated routers ⚠️
    │   │   ├── __init__.py
    │   │   ├── barwsrouter.py          # Generated BarWsRouter class
    │   │   └── quotewsrouter.py        # Generated QuoteWsRouter class
    │   └── tests/                      # Module-specific tests
    └── broker/                         # Trading module
        ├── __init__.py                 # BrokerModule
        ├── service.py                  # BrokerService (implements WsRouteService)
        ├── api.py                      # BrokerApi (REST endpoints)
        ├── ws.py                       # BrokerWsRouters + TypeAlias declarations
        ├── ws_generated/               # Auto-generated routers ⚠️
        │   ├── __init__.py
        │   ├── orderwsrouter.py        # Generated OrderWsRouter class
        │   ├── positionwsrouter.py     # Generated PositionWsRouter class
        │   └── ...                     # Other broker routers
        └── tests/                      # Module-specific tests
```

⚠️ **Router Generation**: Each module owns its generated routers in `modules/{module}/ws_generated/`. Routers are auto-generated from the `shared/ws/generic_route.py` template. See [`WS-ROUTER-GENERATION.md`](../src/trading_api/shared/ws/WS-ROUTER-GENERATION.md) for details.

### Key Components

#### WsRouteService - Protocol-Based Service Architecture

**Location**: `shared/ws/router_interface.py`

The `WsRouteService` is a Protocol that defines the contract for services providing WebSocket topic management:

```python
class WsRouteService(Protocol):
    """Protocol for services providing WebSocket topic lifecycle management."""

    async def create_topic(self, topic: str) -> None:
        """Create and start data generation for a topic."""
        ...

    def remove_topic(self, topic: str) -> None:
        """Stop and clean up data generation for a topic."""
        ...
```

**Implementations**:

- `modules/broker/service.py::BrokerService` - Broker operations (orders, positions, executions)
- `modules/datafeed/service.py::DatafeedService` - Market data (bars, quotes)

**Service Pattern**:

Services implement this Protocol by managing their own topic generators as asyncio tasks:

```python
class DatafeedService:
    """Market data service implementing WsRouteService Protocol."""

    def __init__(self) -> None:
        self._topic_generators: dict[str, asyncio.Task] = {}

    async def create_topic(self, topic: str) -> None:
        """Start generator task for topic."""
        if topic not in self._topic_generators:
            if topic.startswith("bars:"):
                task = asyncio.create_task(self._bar_generator(topic))
                self._topic_generators[topic] = task

    def remove_topic(self, topic: str) -> None:
        """Stop generator task for topic."""
        if topic in self._topic_generators:
            self._topic_generators[topic].cancel()
            del self._topic_generators[topic]

    async def _bar_generator(self, topic: str, topic_update: Callable) -> None:
        """Generate and broadcast bar data for topic."""
        while True:
            bar = self.mock_last_bar(symbol, resolution)
            # Broadcast via topic_update callback
            topic_update(bar)
            await asyncio.sleep(interval)
```

**Key Features**:

- **Protocol-Based**: Services implement a simple two-method contract
- **Self-Managed**: Each service manages its own generator tasks
- **Async Generators**: Long-running tasks that broadcast updates via callback
- **Clean Lifecycle**: Tasks created on subscription, cancelled on unsubscribe

**Data Flow**:

```
Service generator → topic_update(data) → Router updates_queue → FastWSAdapter → Clients
```

#### FastWSAdapter (shared/plugins/fastws_adapter.py)

**Self-Contained WebSocket Adapter with Broadcasting**

The `FastWSAdapter` manages WebSocket connections and broadcasting by overriding `include_router()` and `setup()`:

```python
class FastWSAdapter(FastWS):
    """Self-contained WebSocket adapter with embedded endpoint and broadcasting."""

    def __init__(self, ...) -> None:
        super().__init__(...)
        self._pending_routers: list[Callable] = []
        self._broadcast_tasks: list[asyncio.Task] = []

    def include_router(self, router: WsRouteInterface) -> None:
        """Override to register router and store broadcast coroutine."""
        super().include_router(router)

        async def broadcast_router_messages() -> None:
            """Background task that polls router's updates_queue."""
            while True:
                update = await router.updates_queue.get()
                message = Message(
                    type=f"{router.route}.update",
                    payload=update.model_dump(),
                )
                await self.server_send(message, topic=update.topic)

        # Store for later startup
        self._pending_routers.append(broadcast_router_messages)

    def setup(self, app: FastAPI) -> None:
        """Override setup to start all broadcasting tasks."""
        super().setup(app)

        for broadcast_coro in self._pending_routers:
            task = asyncio.create_task(broadcast_coro())
            self._broadcast_tasks.append(task)

        self._pending_routers.clear()
```

**Key Features**:

- **include_router() Override**: Registers router with parent, creates broadcast coroutine
- **setup() Override**: Starts all pending broadcast tasks when FastAPI app is ready
- **Per-Router Broadcasting**: Each router has its own background task polling `updates_queue`
- **Clean Integration**: Services call topic_update → enqueues to router.updates_queue → broadcast task sends to clients
- **Type Safety**: Pydantic models validated before broadcasting

#### WsRouter - Generic WebSocket Router

**Location**: `shared/ws/generic_route.py`

The `WsRouter` is a generic implementation that handles subscription management with reference counting:

```python
class WsRouter(WsRouteInterface, Generic[_TRequest, _TData]):
    def __init__(
        self,
        *,
        route: str = "",
        tags: list[str | Enum] | None = None,
        service: WsRouteService,  # Injected service
    ) -> None:
        super().__init__(prefix=f"{route}.", tags=tags)
        self.route = route
        self.service = service
        self.topic_trackers: dict[str, int] = {}  # Reference counting

        @self.send("subscribe", reply="subscribe.response")
        async def send_subscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Subscribe to real-time data updates"""
            topic = self.topic_builder(payload)
            client.subscribe(topic)

            if topic not in self.topic_trackers:
                # First subscriber - create topic
                self.topic_trackers[topic] = 1
                await self.service.create_topic(topic)
            else:
                # Additional subscriber - increment count
                self.topic_trackers[topic] += 1

            return SubscriptionResponse(status="ok", message="Subscribed", topic=topic)

        @self.send("unsubscribe", reply="unsubscribe.response")
        def send_unsubscribe(
            payload: _TRequest,
            client: Client,
        ) -> SubscriptionResponse:
            """Unsubscribe from data updates"""
            topic = self.topic_builder(payload)
            client.unsubscribe(topic)

            # Decrement count, cleanup when count hits 0
            if topic in self.topic_trackers:
                self.topic_trackers[topic] -= 1
                if self.topic_trackers[topic] <= 0:
                    del self.topic_trackers[topic]
                    self.service.remove_topic(topic)

            return SubscriptionResponse(status="ok", message="Unsubscribed", topic=topic)

        @self.recv("update")
        def update(
            payload: SubscriptionUpdate[_TData],
        ) -> SubscriptionUpdate[_TData]:
            """Broadcast data updates to subscribed clients"""
            return payload
```

**Key Design Decisions**:

1. **Service Injection**: Router receives `WsRouteService` instance (no global state)
2. **Reference Counting**: Simple `dict[str, int]` tracks subscriber count per topic
3. **Lazy Topic Creation**: Service's `create_topic()` called only on first subscription
4. **Auto-Cleanup**: Service's `remove_topic()` called when count reaches 0
5. **Type Safety**: Generic parameters `_TRequest` and `_TData` ensure type safety

**Subscription Flow**:

```
First Client → subscribe → topic_trackers[topic] = 1 → service.create_topic(topic)
Second Client → subscribe → topic_trackers[topic] = 2 (no create_topic call)
First Client → unsubscribe → topic_trackers[topic] = 1 (no remove_topic call)
Second Client → unsubscribe → topic_trackers[topic] = 0 → service.remove_topic(topic)
```

#### Router Factory Classes

**Location**: `modules/broker/ws.py`, `modules/datafeed/ws.py`

Router factories instantiate and inject services:

```python
# modules/broker/ws.py
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.router_interface import WsRouteInterface, WsRouteService

if TYPE_CHECKING:
    # TypeAlias declarations for code generation
    OrderWsRouter: TypeAlias = WsRouter[OrderSubscriptionRequest, PlacedOrder]
    PositionWsRouter: TypeAlias = WsRouter[PositionSubscriptionRequest, Position]
else:
    # Runtime imports from generated routers
    from .ws_generated import OrderWsRouter, PositionWsRouter

class BrokerWsRouters(list[WsRouteInterface]):
    def __init__(self, broker_service: WsRouteService):
        order_router = OrderWsRouter(
            route="orders", tags=["broker"], service=broker_service
        )
        position_router = PositionWsRouter(
            route="positions", tags=["broker"], service=broker_service
        )
        super().__init__([order_router, position_router, ...])

# modules/datafeed/ws.py
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.router_interface import WsRouteInterface, WsRouteService

if TYPE_CHECKING:
    # TypeAlias declarations for code generation
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteWsRouter: TypeAlias = WsRouter[QuoteSubscriptionRequest, Quote]
else:
    # Runtime imports from generated routers
    from .ws_generated import BarWsRouter, QuoteWsRouter

class DatafeedWsRouters(list[WsRouteInterface]):
    def __init__(self, datafeed_service: WsRouteService):
        bar_router = BarWsRouter(
            route="bars", tags=["datafeed"], service=datafeed_service
        )
        quote_router = QuoteWsRouter(
            route="quotes", tags=["datafeed"], service=datafeed_service
        )
        super().__init__([bar_router, quote_router])
```

**Benefits**:

- Clean dependency injection
- No global singletons
- Easy testing (mock services)
- Service lifecycle tied to routers

#### Integration (app_factory.py + main.py)

```python
# app_factory.py - Application Factory Pattern
from trading_api.shared.module_registry import ModuleRegistry
from trading_api.modules.datafeed import DatafeedModule
from trading_api.modules.broker import BrokerModule
from trading_api.shared.plugins.fastws_adapter import FastWSAdapter

def create_app(enabled_modules: list[str] | None = None):
    """Create FastAPI application with enabled modules.

    Args:
        enabled_modules: List of module names to enable.
                        If None, all modules are enabled.
    """
    # Create module registry
    registry = ModuleRegistry()
    registry.clear()  # Clean slate for each app instance

    # Register modules
    registry.register(DatafeedModule())
    registry.register(BrokerModule())

    # Filter modules if specified
    if enabled_modules:
        for module in registry.get_all_modules():
            module._enabled = module.name in enabled_modules

    # Create FastAPI and WebSocket apps
    api_app = FastAPI(...)
    ws_app = FastWSAdapter(...)

    # Load enabled modules
    for module in registry.get_enabled_modules():
        # Include API routers
        for router in module.get_api_routers():
            api_app.include_router(router, prefix="/api/v1")

        # Include WebSocket routers
        for ws_router in module.get_ws_routers():
            ws_app.include_router(ws_router)

    # Register AsyncAPI docs
    ws_app.setup(api_app)

    # Define WebSocket endpoint
    @api_app.websocket("/api/v1/ws")
    async def websocket_endpoint(
        client: Annotated[Client, Depends(ws_app.manage)]
    ):
        await ws_app.serve(client)

    return api_app, ws_app

# main.py - Minimal Entrypoint
import os
from trading_api.app_factory import mount_app_modules

# Parse enabled modules from environment
enabled_modules = os.getenv("ENABLED_MODULES", "all")
if enabled_modules != "all":
    enabled_modules = [m.strip() for m in enabled_modules.split(",")]
else:
    enabled_modules = None

# Create application
apiApp, wsApp = mount_app_modules(enabled_modules=enabled_modules)

# Export for spec generation scripts
app = apiApp  # Required for scripts/export_openapi_spec.py
```

**Architecture Benefits**:

1. **Modular**: Each module (datafeed, broker) is independently loadable
2. **Factory Pattern**: Applications created via `mount_app_modules()` for full control
3. **Protocol-Based**: Services implement simple `create_topic`/`remove_topic` contract
4. **Testable**: Easy to create isolated test apps with specific modules
5. **No Global State**: Services lazy-loaded per module instance
6. **Clean Lifecycle**: Services manage their own generator tasks
7. **Type Safe**: Full type inference from service to router to client
8. **Scalable Broadcasting**: FastWSAdapter handles per-router message queues
9. **Configuration-Driven**: Load specific modules via `ENABLED_MODULES` environment variable

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

## Resources

### Documentation

- **AsyncAPI Spec**: http://localhost:8000/api/v1/ws/asyncapi.json
- **Interactive Docs**: http://localhost:8000/api/v1/ws/asyncapi
- **Architecture**: See `ARCHITECTURE.md` (Real-Time Architecture section)
- **Backend README**: `backend/README.md`
- **Router Generation**: `backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md` (backend code generation)
- **Frontend Client Generation**: `frontend/WS-CLIENT-AUTO-GENERATION.md` (frontend type-safe clients)

### Code References

- **Main App**: `backend/src/trading_api/main.py`
- **App Factory**: `backend/src/trading_api/app_factory.py`
- **Module Interface**: `backend/src/trading_api/shared/module_interface.py`
- **Module Registry**: `backend/src/trading_api/shared/module_registry.py`
- **FastWS Adapter**: `backend/src/trading_api/shared/plugins/fastws_adapter.py`
- **Router Interface**: `backend/src/trading_api/shared/ws/router_interface.py`
- **Generic Router**: `backend/src/trading_api/shared/ws/generic_route.py`
- **Datafeed Module**: `backend/src/trading_api/modules/datafeed/__init__.py`
- **Datafeed Service**: `backend/src/trading_api/modules/datafeed/service.py`
- **Datafeed Routers**: `backend/src/trading_api/modules/datafeed/ws.py`
- **Broker Module**: `backend/src/trading_api/modules/broker/__init__.py`
- **Broker Service**: `backend/src/trading_api/modules/broker/service.py`
- **Broker Routers**: `backend/src/trading_api/modules/broker/ws.py`
- **Shared Tests**: `backend/src/trading_api/shared/tests/`
- **Datafeed Tests**: `backend/src/trading_api/modules/datafeed/tests/`
- **Broker Tests**: `backend/src/trading_api/modules/broker/tests/`

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

## Modular Architecture Notes

### Module Independence

Each module (datafeed, broker) is completely self-contained:

- **Service**: Implements `WsRouteService` Protocol
- **API**: REST endpoints for module operations
- **WebSocket**: Real-time data streaming routers
- **Tests**: Module-specific isolated tests
- **Generated Routers**: Auto-generated in `modules/{module}/ws_generated/`

### Configuration-Driven Loading

Load specific modules via environment variable:

```bash
# Start with all modules (default)
make dev

# Start with datafeed only
ENABLED_MODULES=datafeed make dev

# Start with broker only
ENABLED_MODULES=broker make dev

# Start with multiple specific modules
ENABLED_MODULES=datafeed,broker make dev
```

### Adding New Modules

To add a new WebSocket-enabled module:

1. Create module directory: `modules/new_module/`
2. Implement `Module` Protocol in `modules/new_module/__init__.py`
3. Create service implementing `WsRouteService` in `modules/new_module/service.py`
4. Add WebSocket routers with TypeAlias declarations in `modules/new_module/ws.py`
5. Run `make generate-ws-routers` to generate concrete routers
6. Register module in `app_factory.py::create_app()`

See `ARCHITECTURE.md` and `API-METHODOLOGY.md` for detailed module implementation guides.

---

**Last Updated**: October 30, 2025
**Maintainer**: Development Team
**Version**: 2.0.0 (Modular Architecture)
