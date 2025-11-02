# Backend WebSockets - FastWS Integration Guide

**Version**: 1.0.0  
**Date**: November 2, 2025  
**Status**: ✅ Production Ready

---

## Overview

This guide explains how **FastWS** is integrated into the modular backend architecture and how to create WebSocket-ready modules.

### What is FastWS?

FastWS is a WebSocket framework built on top of FastAPI that provides:

- **AsyncAPI documentation** (WebSocket equivalent of OpenAPI)
- **Topic-based subscriptions** with automatic client management
- **Operation-based routing** (similar to REST endpoints)
- **Type-safe message handling** using Pydantic models

### Integration Architecture

```
Module-Scoped WebSocket Pattern
├─ Each module creates its own FastWSAdapter
├─ Module registers WebSocket endpoint at /ws
├─ Auto-generates AsyncAPI specs per module
└─ Main app merges all AsyncAPI specs
```

---

## How FastWS is Integrated

### 1. FastWSAdapter Wrapper

**Location**: `shared/plugins/fastws_adapter.py`

A custom wrapper around FastWS that adds:

- **Automatic broadcasting** from router queues to subscribed clients
- **Background task management** for continuous message streaming
- **Integration with WsRouteInterface** for standardized routers

**Key Enhancement**: Routers implementing `WsRouteInterface` get automatic broadcasting via queue consumption.

```python
class FastWSAdapter(FastWS):
    """Self-contained WebSocket adapter with embedded endpoint"""

    def include_router(self, router: OperationRouter, *, prefix: str = "") -> None:
        super().include_router(router, prefix=prefix)

        # Only WsRouteInterface routers get automatic broadcasting
        if isinstance(router, WsRouteInterface):
            # Creates background task that reads from router.updates_queue
            # and broadcasts to subscribed clients
```

**Broadcasting Pattern**:

1. Service pushes data to router via `topic_update()` callback
2. Router enqueues update in `updates_queue`
3. FastWSAdapter background task consumes queue
4. Broadcasts to clients subscribed to the topic

### 2. Module-Scoped WebSocket Apps

**Each module creates its own FastWSAdapter** inside `Module.create_app()`:

```python
# In Module.create_app()
if self.ws_routers:
    ws_app = FastWSAdapter(
        title=f"{self.name.title()} WebSockets",
        description=f"Real-time WebSocket app for {self.name} module",
        version="1.0.0",
        asyncapi_url="ws/asyncapi.json",
        asyncapi_docs_url="ws/asyncapi",
        heartbeat_interval=30.0,
        max_connection_lifespan=3600.0,
    )

    # Register module's WebSocket routers
    for ws_router in self.ws_routers:
        ws_app.include_router(ws_router)

    # Register WebSocket endpoint in module's FastAPI app
    @app.websocket("/ws")
    async def websocket_endpoint(
        client: Annotated[Client, Depends(ws_app.manage)],
    ) -> None:
        await ws_app.serve(client)
```

**Result**: Each module has its own WebSocket endpoint at `/api/v1/{module}/ws`

| Module   | WebSocket URL         | AsyncAPI Docs                  |
| -------- | --------------------- | ------------------------------ |
| Broker   | `/api/v1/broker/ws`   | `/api/v1/broker/ws/asyncapi`   |
| Datafeed | `/api/v1/datafeed/ws` | `/api/v1/datafeed/ws/asyncapi` |

### 3. WebSocket Router Interface

**Location**: `shared/ws/router_interface.py`

All WebSocket routers implement `WsRouteInterface`:

```python
class WsRouteInterface(OperationRouter):
    def __init__(self, route: str, *args: Any, **kwargs: Any):
        super().__init__(prefix=f"{route}.", *args, **kwargs)
        self.route: str = route
        self.updates_queue = asyncio.Queue[SubscriptionUpdate[BaseModel]](maxsize=1000)

    def topic_builder(self, params: BaseModel) -> str:
        """Build unique topic from subscription parameters"""
        return f"{self.route}:{buildTopicParams(params.model_dump())}"
```

**Key Features**:

- **Updates Queue**: Routers expose queue for service to push data
- **Topic Builder**: Generates consistent topic names from subscription params
- **Route Namespace**: Each router has a unique route prefix (e.g., `orders.`, `positions.`)

### 4. Service Protocol

**Location**: `shared/ws/router_interface.py`

Services implementing WebSocket features must implement `WsRouteService`:

```python
class WsRouteService(Protocol):
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start generating data for topic (first subscriber)"""
        ...

    def remove_topic(self, topic: str) -> None:
        """Stop generating data for topic (last unsubscribe)"""
        ...
```

**Reference Counting Pattern**: Routers track subscribers per topic and call service methods on first subscribe / last unsubscribe.

---

## Creating a WebSocket-Ready Module

### Checklist

- [ ] Service implements `WsRouteService` protocol
- [ ] Create `ws.py` with TypeAlias declarations
- [ ] Module exposes `ws_routers` property
- [ ] Define subscription request and data models

### Step 1: Define Models

**Location**: `models/{domain}.py`

```python
# Request model (what client sends to subscribe)
class BarSubscriptionRequest(BaseModel):
    symbol: str
    timeframe: TimeFrame

# Data model (what gets streamed to client)
class Bar(BaseModel):
    symbol: str
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
```

### Step 2: Declare Router TypeAlias

**Location**: `modules/{module}/ws.py`

```python
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.module_router_generator import generate_module_routers

if TYPE_CHECKING:
    # TypeAlias for code generation (compile-time only)
    BarWsRouter: TypeAlias = WsRouter[BarSubscriptionRequest, Bar]

class DatafeedWsRouters(list[WsRouteInterface]):
    def __init__(self, datafeed_service: WsRouteService):
        # Auto-generate concrete router classes
        module_name = os.path.basename(os.path.dirname(__file__))
        generate_module_routers(module_name)

        # Import generated routers (runtime)
        if not TYPE_CHECKING:
            from .ws_generated import BarWsRouter

        # Instantiate with service
        bar_router = BarWsRouter(route="bars", service=datafeed_service)
        super().__init__([bar_router])
```

**Pattern**: `TypeAlias = WsRouter[SubscriptionRequestType, DataType]`

**Generation**: Happens automatically during router factory instantiation, creating:

- `ws_generated/barwsrouter.py` - Concrete router class
- `ws_generated/__init__.py` - Exports all routers

### Step 3: Implement Service Protocol

**Location**: `modules/{module}/service.py`

The service is where **business logic integration** happens. It must implement `WsRouteService` protocol and handle:

- **Topic parsing** - Extract subscription parameters from topic string
- **Model validation** - Verify subscription requests using Pydantic models
- **Data generation** - Start/stop streaming based on subscriptions
- **Callback invocation** - Push data to router via `topic_update` callback

```python
import asyncio
import json
from typing import Callable
from trading_api.shared.ws.router_interface import WsRouteService

class DatafeedService(WsRouteService):
    """Service implementing WsRouteService protocol for WebSocket support"""

    def __init__(self):
        self._topic_generators: dict[str, asyncio.Task] = {}

    # !! IMORTANT SECTION !!
    # MAIN BUSINESS SETUP METHOD
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start streaming data for topic (first subscriber)

        Topic format: "{route}:{json_params}"
        Example: "bars:{"symbol":"AAPL","resolution":"1D"}"

        Args:
            topic: Topic string with route and JSON params
            topic_update: Callback to push data to router queue

        Raises:
            ValueError: Invalid topic format or unknown route
            json.JSONDecodeError: Invalid JSON params
        """
        if topic in self._topic_generators:
            return  # Already streaming

        # Parse topic format: "route:json_params"
        if ":" not in topic:
            raise ValueError(f"Invalid topic format: {topic}")

        route, params_json = topic.split(":", 1)

        # !! IMORTANT SECTION !!
        # Route-specific handling
        if route == "bars":
            # Parse and validate subscription params
            params_dict = json.loads(params_json)
            subscription_request = BarsSubscriptionRequest.model_validate(params_dict)

            # THIS IS AN IMPLEMENTATION EXAMPLE FOR ILLUSTRATION
            # ROUTINE MIGHT BE SUB TO AN EXTERNAL SERVICE OR WATCH
            # SOME INTERNAL/EXTERNAL EVENT, ETC. WITH TOPIC_UPDATE
            # AS A CALLBACK / TRIGER
            # SETUP A ROUTINE FOR TOPIC UPDATE HERE

            ...

            # MIGHT NEED TO REGISTER A TASK OR SUB HANDLER, ETC.
            self._topic_generators[topic] = task

        # HANDLE ALL WS ROUTES
        ...

        # REPORT ANY UNHANDLED ROUTES
        else:
            raise ValueError(f"Unknown route type: {route}")

    def remove_topic(self, topic: str) -> None:
        """Stop streaming data for topic (last unsubscribe)"""
        task = self._topic_generators.pop(topic, None)
        if task:
            task.cancel()

    def __del__(self) -> None:
        """Cleanup all streaming tasks on service deletion"""
        for task in self._topic_generators.values():
            if not task.done():
                task.cancel()
```

**Critical Implementation Details**:

1. **Topic Parsing**: Topics follow `"{route}:{json_params}"` format built by router's `topic_builder()`
2. **Model Validation**: Always validate params with Pydantic models (`BarsSubscriptionRequest.model_validate()`)
3. **Error Handling**: Raise `ValueError` for invalid topics/routes, `json.JSONDecodeError` for malformed JSON
4. **Task Management**: Store task references in dict for cleanup on unsubscribe or service deletion
5. **Callback Usage**: Call `topic_update(data)` to push data - router enqueues it for broadcasting

**Why This Matters**:

- ✅ Type-safe params via Pydantic validation
- ✅ Graceful error handling with clear error messages
- ✅ Resource cleanup prevents memory leaks
- ✅ Single source of truth for subscription logic### Step 4: Module Integration

**Location**: `modules/{module}/__init__.py`

```python
class DatafeedModule(Module):
    def __init__(self) -> None:
        super().__init__()
        self._service = DatafeedService()
        self._api_routers = [
            DatafeedApi(service=self.service, prefix="", tags=[self.name])
        ]
        # WebSocket routers (auto-generates during instantiation)
        self._ws_routers = DatafeedWsRouters(datafeed_service=self.service)

    @property
    def ws_routers(self) -> list[WsRouteInterface]:
        return self._ws_routers
```

**That's it!** The module now has WebSocket support:

- ✅ WebSocket endpoint at `/api/v1/datafeed/ws`
- ✅ AsyncAPI spec at `/api/v1/datafeed/ws/asyncapi`
- ✅ Auto-generated routers in `ws_generated/`
- ✅ Automatic broadcasting to subscribed clients

---

## WebSocket Router Generation

**For complete details on router generation, see [WS_ROUTERS_GEN.md](WS_ROUTERS_GEN.md)**

### How It Works

**Automatic generation from TypeAlias declarations**:

1. **Declaration**: Define `TypeAlias = WsRouter[Request, Data]` in `ws.py` (inside `TYPE_CHECKING` block)
2. **Generation**: `generate_module_routers(module_name)` called during router factory instantiation
3. **Parsing**: Regex extracts TypeAlias declarations from `ws.py`
4. **Template**: Loads `generic_route.py` template
5. **Substitution**: Replaces `_TRequest` with `Request`, `_TData` with `Data`
6. **Quality Checks**: Runs Black, Ruff, Flake8, Mypy, Isort (7-step pipeline)
7. **Output**: Creates concrete class in `ws_generated/`

### Generated Router Structure

**Input** (`ws.py`):

```python
if TYPE_CHECKING:
    OrderWsRouter: TypeAlias = WsRouter[OrderSubscriptionRequest, PlacedOrder]
```

**Output** (`ws_generated/orderwsrouter.py`):

```python
class OrderWsRouter(WsRouteInterface):
    def __init__(self, service: WsRouteService, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.service = service
        self.topic_trackers: dict[str, int] = {}

        @self.recv("update")
        def update(payload: SubscriptionUpdate[PlacedOrder]) -> ...:
            """Broadcast data updates to subscribed clients"""

        @self.send("subscribe", reply="subscribe.response")
        async def send_subscribe(payload: OrderSubscriptionRequest, client: Client) -> ...:
            """Subscribe to real-time data updates"""
            # Reference counting + create_topic on first subscriber

        @self.send("unsubscribe", reply="unsubscribe.response")
        def send_unsubscribe(payload: OrderSubscriptionRequest, client: Client) -> ...:
            """Unsubscribe from data updates"""
            # Reference counting + remove_topic on last unsubscribe
```

### Operations

**Each router exposes 3 operations**:

| Operation             | Direction       | Description                             |
| --------------------- | --------------- | --------------------------------------- |
| `{route}.subscribe`   | Client → Server | Subscribe to topic                      |
| `{route}.unsubscribe` | Client → Server | Unsubscribe from topic                  |
| `{route}.update`      | Server → Client | Push data updates to subscribed clients |

**Example for `orders` router**:

- `orders.subscribe` - Subscribe to order updates
- `orders.unsubscribe` - Unsubscribe from order updates
- `orders.update` - Receive order update notifications

### Topic Subscription Flow

```
Client Subscribe Request
├─ 1. Client sends: orders.subscribe { orderId: "123" }
├─ 2. Router builds topic: "orders:{"orderId":"123"}"
├─ 3. Client.subscribe(topic) - FastWS client tracking
├─ 4. First subscriber? → service.create_topic(topic, callback)
├─ 5. Reference counter incremented
└─ 6. Response: { status: "ok", topic: "orders:..." }

Service Pushes Data
├─ 1. Service calls: callback(order_data)
├─ 2. Router enqueues: updates_queue.put(SubscriptionUpdate(topic, data))
├─ 3. FastWSAdapter background task reads queue
├─ 4. Broadcasts: Message(type="orders.update", payload={topic, data})
└─ 5. Client receives update on subscribed topic

Client Unsubscribe Request
├─ 1. Client sends: orders.unsubscribe { orderId: "123" }
├─ 2. Router builds topic: "orders:{"orderId":"123"}"
├─ 3. Client.unsubscribe(topic) - FastWS client tracking
├─ 4. Reference counter decremented
├─ 5. Last subscriber? → service.remove_topic(topic)
└─ 6. Response: { status: "ok", topic: "orders:..." }
```

---

## AsyncAPI Specification

### Per-Module Specs

**Generated during module startup** via `Module.gen_specs_and_clients()`:

**Output**: `modules/{module}/specs_generated/{module}_asyncapi.json`

**Content**:

- **Channels**: All WebSocket operations (`subscribe`, `unsubscribe`, `update`)
- **Messages**: Request/response schemas
- **Schemas**: Pydantic model definitions

**Example**:

```json
{
  "asyncapi": "2.6.0",
  "info": {
    "title": "Broker WebSockets",
    "version": "1.0.0"
  },
  "channels": {
    "orders.subscribe": {
      "description": "Subscribe to order updates",
      "subscribe": {
        "message": { "$ref": "#/components/messages/OrderSubscriptionRequest" }
      }
    },
    "orders.update": {
      "description": "Receive order updates",
      "publish": {
        "message": { "$ref": "#/components/messages/PlacedOrder" }
      }
    }
  }
}
```

### Merged AsyncAPI Spec

**Main app merges all module AsyncAPI specs**:

**Endpoint**: `/api/v1/ws/asyncapi.json`  
**Implementation**: `ModularFastAPI.asyncapi()` in `app_factory.py`

**Merge Strategy**:

- **Channels**: Prefixed with module mount path (`/api/v1/{module}/ws`)
- **Schemas**: Deduplicated and merged
- **Messages**: Deduplicated and merged

**Result**: Single AsyncAPI spec documenting all WebSocket endpoints across all modules.

---

## Client Usage Example

### WebSocket Connection

```typescript
// Connect to module's WebSocket endpoint
const ws = new WebSocket("ws://localhost:8000/api/v1/broker/ws");

// Subscribe to order updates
ws.send(
  JSON.stringify({
    type: "orders.subscribe",
    payload: { orderId: "123" },
  })
);

// Receive updates
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === "orders.subscribe.response") {
    console.log("Subscribed:", message.payload.topic);
  }

  if (message.type === "orders.update") {
    console.log("Order update:", message.payload);
  }
};

// Unsubscribe
ws.send(
  JSON.stringify({
    type: "orders.unsubscribe",
    payload: { orderId: "123" },
  })
);
```

---

## Reference Counting Pattern

**Problem**: Multiple clients may subscribe to the same topic (e.g., AAPL bars).

**Solution**: Reference counting in routers + lazy topic creation/removal.

### Implementation

```python
# In generated router
self.topic_trackers: dict[str, int] = {}

async def send_subscribe(payload: Request, client: Client) -> Response:
    topic = self.topic_builder(payload)
    client.subscribe(topic)

    if topic not in self.topic_trackers:
        # First subscriber - create topic
        await self.service.create_topic(topic, topic_update_callback)
        self.topic_trackers[topic] = 1
    else:
        # Subsequent subscriber - increment counter
        self.topic_trackers[topic] += 1

def send_unsubscribe(payload: Request, client: Client) -> Response:
    topic = self.topic_builder(payload)
    client.unsubscribe(topic)

    self.topic_trackers[topic] -= 1
    if self.topic_trackers[topic] <= 0:
        # Last unsubscribe - remove topic
        self.service.remove_topic(topic)
        self.topic_trackers.pop(topic)
```

**Benefits**:

- ✅ Service only streams data when clients are subscribed
- ✅ Resources freed when no subscribers remain
- ✅ Multiple clients share same data stream

---

## Testing WebSocket Routers

### Unit Tests

**Location**: `modules/{module}/tests/test_ws.py`

```python
@pytest.mark.asyncio
async def test_subscribe_creates_topic(broker_client):
    """Test that subscription creates topic on first subscriber"""
    async with broker_client.websocket_connect("/ws") as ws:
        # Subscribe
        await ws.send_json({
            "type": "orders.subscribe",
            "payload": {"orderId": "123"}
        })

        # Verify response
        response = await ws.receive_json()
        assert response["type"] == "orders.subscribe.response"
        assert response["payload"]["status"] == "ok"
```

### Integration Tests

**Test module isolation** - each module has independent WebSocket endpoint:

```python
def test_broker_ws_endpoint(broker_app):
    """Broker module has WebSocket at /api/v1/broker/ws"""
    client = TestClient(broker_app)

    with client.websocket_connect("/api/v1/broker/ws") as ws:
        # Test broker WebSocket operations
        pass

def test_datafeed_ws_endpoint(datafeed_app):
    """Datafeed module has WebSocket at /api/v1/datafeed/ws"""
    client = TestClient(datafeed_app)

    with client.websocket_connect("/api/v1/datafeed/ws") as ws:
        # Test datafeed WebSocket operations
        pass
```

---

## Troubleshooting

### Issue: Router Generation Fails

**Symptom**: `ModuleNotFoundError: No module named 'ws_generated'`

**Cause**: TypeAlias not in `TYPE_CHECKING` block or syntax error

**Solution**:

1. Verify TypeAlias is inside `if TYPE_CHECKING:` block
2. Check pattern: `RouterName: TypeAlias = WsRouter[Request, Data]`
3. Run manual generation: `make generate modules={module}`

### Issue: Service Protocol Violation

**Symptom**: `TypeError: Can't instantiate abstract class with abstract methods`

**Cause**: Service doesn't implement `create_topic` or `remove_topic`

**Solution**: Implement both methods:

```python
async def create_topic(self, topic: str, topic_update: Callable) -> None:
    # Store callback and start streaming
    pass

def remove_topic(self, topic: str) -> None:
    # Stop streaming and cleanup
    pass
```

### Issue: No Updates Received

**Symptom**: Clients subscribe successfully but never receive updates

**Causes**:

1. Service not calling `topic_update` callback
2. FastWSAdapter not started (missing `ws_app.setup(app)`)
3. Client not subscribed to correct topic

**Debug**:

```python
# In service, add logging
topic_update(data)
logger.info(f"Pushed data to topic: {topic}")

# Check FastWSAdapter background tasks
logger.info(f"Broadcast tasks: {len(ws_app._broadcast_tasks)}")
```

---

## Related Documentation

- **[MODULAR_BACKEND_ARCHITECTURE.md](MODULAR_BACKEND_ARCHITECTURE.md)** - Module system overview
- **[WS_ROUTERS_GEN.md](WS_ROUTERS_GEN.md)** - Router generation details
- **[SPECS_AND_CLIENT_GEN.md](SPECS_AND_CLIENT_GEN.md)** - Spec generation
- **[WEBSOCKET-METHODOLOGY.md](../../WEBSOCKET-METHODOLOGY.md)** - WebSocket design patterns

---

## Quick Reference

### Module WebSocket Checklist

- [ ] Service implements `WsRouteService` protocol
- [ ] Created `ws.py` with TypeAlias declarations
- [ ] TypeAlias inside `if TYPE_CHECKING:` block
- [ ] Router factory calls `generate_module_routers(module_name)`
- [ ] Module exposes `ws_routers` property
- [ ] Defined subscription request and data models

### File Structure

```
modules/{module}/
├── __init__.py              # Module class with ws_routers property
├── service.py               # Implements WsRouteService protocol
├── ws.py                    # TypeAlias declarations + router factory
├── ws_generated/            # Auto-generated (created at init)
│   ├── __init__.py
│   └── {route}wsrouter.py
└── specs_generated/
    └── {module}_asyncapi.json
```

### Key Classes

```python
# FastWS integration
FastWSAdapter              # shared/plugins/fastws_adapter.py
WsRouteInterface          # shared/ws/router_interface.py
WsRouteService            # shared/ws/router_interface.py

# Generation
generate_module_routers   # shared/ws/module_router_generator.py
WsRouter[Request, Data]   # shared/ws/generic_route.py (template)
```

---

**Last Updated**: November 2, 2025  
**Maintainer**: Backend Team  
**Status**: ✅ Production-ready
