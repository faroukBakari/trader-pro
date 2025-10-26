# FastWS Integration Examples

This document provides practical examples of integrating FastWS WebSocket framework into the Trading API.

> ⚠️ **CRITICAL**: Before implementing WebSocket routers, you **MUST** follow the router code generation mechanism documented in [`../src/trading_api/ws/WS-ROUTER-GENERATION.md`](../src/trading_api/ws/WS-ROUTER-GENERATION.md). The examples below show patterns and usage, but **actual router creation should always use code generation** to ensure type safety and consistency.

## Table of Contents

1. [Basic Setup](#basic-setup)
2. [Creating Custom Operations](#creating-custom-operations)
3. [Topic-Based Broadcasting](#topic-based-broadcasting)
4. [Client Connection Management](#client-connection-management)
5. [Error Handling](#error-handling)
6. [Testing WebSocket Operations](#testing-websocket-operations)
7. [Advanced Patterns](#advanced-patterns)

## Basic Setup

### Minimal FastWS Application

```python
# main.py
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI
from external_packages.fastws import Client, FastWS

# Create FastWS instance
service = FastWS(
    title="Trading WebSockets",
    version="1.0.0",
    asyncapi_url="/asyncapi.json",
    asyncapi_docs_url="/asyncapi"
)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Register AsyncAPI documentation"""
    service.setup(app)
    yield

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def websocket_endpoint(
    client: Annotated[Client, Depends(service.manage)]
):
    """WebSocket endpoint"""
    await service.serve(client)
```

### Custom FastWS Adapter

Our Trading API uses a custom adapter that overrides `include_router()` and `setup()`:

```python
# plugins/fastws_adapter.py
from external_packages.fastws import FastWS, Message
from fastapi import FastAPI
import asyncio

class FastWSAdapter(FastWS):
    """
    Self-contained WebSocket adapter with embedded broadcasting.

    Overrides include_router() to register routers and store broadcast coroutines.
    Overrides setup() to start all broadcasting tasks when FastAPI app is ready.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_routers: list[Callable] = []
        self._broadcast_tasks: list[asyncio.Task] = []

    def include_router(self, router: WsRouterInterface) -> None:
        """Override to register router and create broadcast coroutine"""
        super().include_router(router)

        async def broadcast_router_messages() -> None:
            """Poll router.updates_queue and broadcast to clients"""
            while True:
                update = await router.updates_queue.get()
                message = Message(
                    type=f"{router.route}.update",
                    payload=update.model_dump(),
                )
                await self.server_send(message, topic=update.topic)

        self._pending_routers.append(broadcast_router_messages)

    def setup(self, app: FastAPI) -> None:
        """Override setup to start all broadcasting tasks"""
        super().setup(app)

        for broadcast_coro in self._pending_routers:
            task = asyncio.create_task(broadcast_coro())
            self._broadcast_tasks.append(task)

        self._pending_routers.clear()
```

## Creating Custom Operations

### Simple SEND Operation

Client sends a message, server replies:

```python
# ws/simple.py
from external_packages.fastws import Client, OperationRouter
from pydantic import BaseModel

router = OperationRouter(prefix="simple.")

class PingPayload(BaseModel):
    timestamp: int

class PongResponse(BaseModel):
    timestamp: int
    server_time: int

@router.send("ping", reply="pong")
async def handle_ping(
    payload: PingPayload,
    client: Client
) -> PongResponse:
    """Client pings, server pongs back"""
    import time
    return PongResponse(
        timestamp=payload.timestamp,
        server_time=int(time.time() * 1000)
    )
```

**Client Usage**:

```javascript
// Send ping
ws.send(
  JSON.stringify({
    type: "simple.ping",
    payload: { timestamp: Date.now() },
  })
);

// Receive pong
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "simple.pong") {
    console.log("RTT:", Date.now() - msg.payload.timestamp);
  }
};
```

### RECEIVE Operation (Server-Initiated)

Server broadcasts messages without client request:

```python
# ws/alerts.py
from external_packages.fastws import OperationRouter
from pydantic import BaseModel

router = OperationRouter(prefix="alerts.")

class AlertPayload(BaseModel):
    severity: str
    message: str
    timestamp: int

@router.recv("alert")
async def broadcast_alert(payload: AlertPayload) -> AlertPayload:
    """Server broadcasts alert to all subscribed clients"""
    return payload
```

**Server Broadcasting via Service Generator**:

```python
# In your service implementation
from trading_api.ws.router_interface import WsRouteService
from trading_api.models import AlertPayload
import time

class AlertService(WsRouteService):
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start alert generator for topic"""
        if topic not in self._topic_generators:
            self._topic_generators[topic] = asyncio.create_task(
                self._alert_generator(topic, topic_update)
            )

    async def _alert_generator(self, topic: str, topic_update: Callable) -> None:
        """Generate alerts and call callback"""
        while True:
            alert = AlertPayload(
                severity="warning",
                message="System maintenance in 5 minutes",
                timestamp=int(time.time() * 1000)
            )
            topic_update(alert)
            await asyncio.sleep(300)  # Every 5 minutes
```

## Topic-Based Broadcasting

### Dynamic Topic Builder

Create topics based on parameters:

```python
# ws/datafeed.py
from typing import Any, Callable

TopicBuilder = Callable[[str, dict[str, Any]], str]

def bars_topic_builder(symbol: str, params: dict[str, Any]) -> str:
    """Build topic: bars:SYMBOL:RESOLUTION"""
    resolution = params.get('resolution', '1')
    return f"bars:{symbol}:{resolution}"

def quotes_topic_builder(symbol: str, params: dict[str, Any]) -> str:
    """Build topic: quotes:SYMBOL"""
    return f"quotes:{symbol}"

def orderbook_topic_builder(symbol: str, params: dict[str, Any]) -> str:
    """Build topic: orderbook:SYMBOL:DEPTH"""
    depth = params.get('depth', 10)
    return f"orderbook:{symbol}:{depth}"
```

### Subscribe with Topic Builder

```python
@router.send("subscribe", reply="subscribe.response")
async def subscribe(
    payload: SubscriptionRequest,
    client: Client
) -> SubscriptionResponse:
    """Generic subscription handler"""
    # Build topic dynamically
    topic = bars_topic_builder(payload.symbol, payload.params)

    # Subscribe client to topic
    client.subscribe(topic)

    return SubscriptionResponse(
        status="ok",
        symbol=payload.symbol,
        message=f"Subscribed to {payload.symbol}",
        topic=topic
    )
```

### Broadcasting via Service Generators

```python
# Service implementation
from trading_api.ws.router_interface import WsRouteService

class MarketDataService(WsRouteService):
    def __init__(self):
        self._topic_generators: dict[str, asyncio.Task] = {}

    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start market data generator for topic"""
        if topic not in self._topic_generators:
            # Parse topic to extract symbol and resolution
            # topic format: "bars:{\"resolution\":\"1\",\"symbol\":\"AAPL\"}"
            self._topic_generators[topic] = asyncio.create_task(
                self._stream_market_data(topic, topic_update)
            )

    async def _stream_market_data(self, topic: str, topic_update: Callable) -> None:
        """Stream market data to subscribed clients via callback"""
        while True:
            # Get new bar data
            bar = await self.fetch_latest_bar("AAPL", resolution="1")

            # Call callback to enqueue update
            topic_update(bar)

            await asyncio.sleep(60)  # 1-minute interval
```

## Client Connection Management

### Accessing Client Information

```python
@router.send("info", reply="info.response")
async def get_client_info(
    client: Client,
    app: FastWS
) -> dict:
    """Get information about current client"""
    return {
        "client_id": client.uid,
        "subscriptions": list(client.topics),
        "total_connections": len(app.connections)
    }
```

### Managing Subscriptions

```python
@router.send("list_subscriptions", reply="subscriptions")
async def list_subscriptions(client: Client) -> dict:
    """List all active subscriptions for this client"""
    return {
        "client_id": client.uid,
        "topics": list(client.topics),
        "count": len(client.topics)
    }

@router.send("clear_subscriptions", reply="cleared")
async def clear_all(client: Client) -> dict:
    """Unsubscribe from all topics"""
    topics = list(client.topics)
    for topic in topics:
        client.unsubscribe(topic)

    return {
        "status": "ok",
        "cleared": topics,
        "count": len(topics)
    }
```

### Broadcasting to All Clients

```python
async def notify_all_clients(message: str):
    """Send notification to all connected clients"""
    notification = {
        "type": "system.notification",
        "message": message,
        "timestamp": int(time.time() * 1000)
    }

    # System notifications broadcast via service generator
    # SystemService creates a notification and calls topic_update(notification)
    # which enqueues to router.updates_queue for broadcasting
```

## Error Handling

### Validation Errors

FastWS automatically handles Pydantic validation errors:

```python
class StrictPayload(BaseModel):
    value: int  # Must be integer
    name: str   # Must be string

@router.send("strict", reply="strict.response")
async def strict_operation(payload: StrictPayload) -> dict:
    """This will fail if payload doesn't match schema"""
    return {"received": payload.model_dump()}
```

**Invalid Request**:

```javascript
// ❌ This will fail - wrong types
ws.send(
  JSON.stringify({
    type: "strict",
    payload: { value: "not_an_int", name: 123 },
  })
);

// Result: WebSocket closed with code 1003
// Reason: "Could not validate payload"
```

### Custom Error Handling

```python
from fastapi import WebSocketException, status

@router.send("risky_operation", reply="result")
async def risky(payload: dict, client: Client) -> dict:
    """Operation that might fail"""
    try:
        # Risky logic
        result = perform_operation(payload)
        return {"status": "ok", "result": result}

    except ValueError as e:
        # Send error response instead of closing connection
        return {
            "status": "error",
            "message": str(e)
        }

    except Exception as e:
        # Critical error - close connection
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR,
            reason=f"Internal error: {str(e)}"
        )
```

### Graceful Degradation

```python
@router.send("subscribe_with_fallback", reply="response")
async def subscribe_fallback(
    payload: SubscriptionRequest,
    client: Client
) -> SubscriptionResponse:
    """Subscribe with fallback to default resolution"""
    try:
        topic = bars_topic_builder(payload.symbol, payload.params)
        client.subscribe(topic)

        return SubscriptionResponse(
            status="ok",
            symbol=payload.symbol,
            message=f"Subscribed to {payload.symbol}",
            topic=topic
        )

    except Exception as e:
        # Fall back to default resolution
        fallback_topic = f"bars:{payload.symbol}:1"
        client.subscribe(fallback_topic)

        return SubscriptionResponse(
            status="ok",
            symbol=payload.symbol,
            message=f"Subscribed with fallback (error: {e})",
            topic=fallback_topic
        )
```

## Testing WebSocket Operations

### Basic Operation Test

```python
# tests/test_ws_operations.py
from fastapi.testclient import TestClient
from trading_api.main import apiApp

def test_ping_pong():
    """Test ping-pong operation"""
    client = TestClient(apiApp)

    with client.websocket_connect("/api/v1/ws") as websocket:
        # Send ping
        websocket.send_json({
            "type": "simple.ping",
            "payload": {"timestamp": 1234567890}
        })

        # Receive pong
        response = websocket.receive_json()

        assert response["type"] == "simple.pong"
        assert response["payload"]["timestamp"] == 1234567890
        assert "server_time" in response["payload"]
```

### Subscription Test

```python
def test_subscription_flow():
    """Test complete subscription workflow"""
    client = TestClient(apiApp)

    with client.websocket_connect("/api/v1/ws") as websocket:
        # Subscribe
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {
                "symbol": "AAPL",
                "params": {"resolution": "1"}
            }
        })

        # Verify subscription response
        response = websocket.receive_json()
        assert response["type"] == "bars.subscribe.response"
        assert response["payload"]["status"] == "ok"
        assert response["payload"]["topic"] == "bars:AAPL:1"

        # Unsubscribe
        websocket.send_json({
            "type": "bars.unsubscribe",
            "payload": {
                "symbol": "AAPL",
                "params": {"resolution": "1"}
            }
        })

        # Verify unsubscribe response
        response = websocket.receive_json()
        assert response["type"] == "bars.unsubscribe.response"
        assert response["payload"]["status"] == "ok"
```

### Broadcasting Test

```python
import pytest
from trading_api.main import wsApp
from trading_api.models.market.bars import Bar

@pytest.mark.asyncio
async def test_server_publish():
    """Test server-initiated broadcast"""
    client = TestClient(apiApp)

    with client.websocket_connect("/api/v1/ws") as websocket:
        # Subscribe
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {"symbol": "AAPL", "params": {"resolution": "1"}}
        })

        # Clear subscription response
        _ = websocket.receive_json()

        # Service generator automatically broadcasts updates
        # The service's _bar_generator calls topic_update(bar)
        # which enqueues to router.updates_queue
        # FastWSAdapter broadcasts from queue

        # Receive broadcast
        update = websocket.receive_json()

        assert update["type"] == "bars.update"
        assert "close" in update["payload"]
```

## Advanced Patterns

### Multi-Channel Subscription

```python
class MultiSubscribeRequest(BaseModel):
    """Subscribe to multiple symbols at once"""
    symbols: list[str]
    params: dict[str, Any] = Field(default_factory=dict)

@router.send("multi_subscribe", reply="multi_subscribe.response")
async def multi_subscribe(
    payload: MultiSubscribeRequest,
    client: Client
) -> dict:
    """Subscribe to multiple symbols"""
    topics = []

    for symbol in payload.symbols:
        topic = bars_topic_builder(symbol, payload.params)
        client.subscribe(topic)
        topics.append(topic)

    return {
        "status": "ok",
        "symbols": payload.symbols,
        "topics": topics,
        "count": len(topics)
    }
```

### Conditional Updates in Generator

```python
class MarketDataService(WsRouteService):
    async def _bar_generator_with_threshold(
        self,
        topic: str,
        topic_update: Callable,
        threshold: float = 0.01
    ) -> None:
        """Only broadcast if price changed significantly"""
        last_price = None

        while True:
            new_bar = await self.fetch_latest_bar(symbol)

            if last_price is None:
                # First update always broadcasts
                topic_update(new_bar)
                last_price = new_bar.close
            else:
                # Calculate change
                change = abs(new_bar.close - last_price) / last_price

                if change >= threshold:
                    topic_update(new_bar)
                    last_price = new_bar.close

            await asyncio.sleep(1)
```

### Rate-Limited Updates in Generator

```python
import asyncio
from collections import defaultdict

class MarketDataService(WsRouteService):
    """Service with rate-limited updates"""

    def __init__(self):
        super().__init__()
        self.min_interval = 1.0  # Minimum seconds between updates
        self.last_update: dict[str, float] = {}
        self.pending_data: dict[str, Any] = {}

    async def _rate_limited_generator(
        self,
        topic: str,
        topic_update: Callable
    ) -> None:
        """Generate updates with rate limiting"""
        while True:
            data = await self.fetch_data()
            now = asyncio.get_event_loop().time()
            last = self.last_update.get(topic, 0)

            if now - last >= self.min_interval:
                # Immediate update
                topic_update(data)
                self.last_update[topic] = now
            else:
                # Store for batch update
                self.pending_data[topic] = data

            await asyncio.sleep(0.1)
```

### Connection Metrics

```python
from collections import defaultdict

class ConnectionMetrics:
    """Track WebSocket connection metrics"""

    def __init__(self):
        self.subscriptions_per_topic = defaultdict(int)
        self.messages_received = 0
        self.messages_sent = 0

    def on_subscribe(self, topic: str):
        self.subscriptions_per_topic[topic] += 1

    def on_unsubscribe(self, topic: str):
        self.subscriptions_per_topic[topic] -= 1
        if self.subscriptions_per_topic[topic] <= 0:
            del self.subscriptions_per_topic[topic]

    def get_metrics(self) -> dict:
        return {
            "total_subscriptions": sum(self.subscriptions_per_topic.values()),
            "unique_topics": len(self.subscriptions_per_topic),
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent
        }

# Usage in operation handler
metrics = ConnectionMetrics()

@router.send("subscribe", reply="subscribe.response")
async def subscribe_with_metrics(
    payload: SubscriptionRequest,
    client: Client
) -> SubscriptionResponse:
    topic = bars_topic_builder(payload.symbol, payload.params)
    client.subscribe(topic)
    metrics.on_subscribe(topic)
    metrics.messages_received += 1

    return SubscriptionResponse(...)
```

## Best Practices

### 1. Use Type Hints

```python
# ✅ Good - Clear types
@router.send("subscribe", reply="response")
async def subscribe(
    payload: SubscriptionRequest,  # Pydantic validates
    client: Client                 # FastWS injects
) -> SubscriptionResponse:         # Return type hint
    ...

# ❌ Bad - No type hints
@router.send("subscribe", reply="response")
async def subscribe(payload, client):
    ...
```

### 2. Prefix Routers

```python
# ✅ Good - Organized with prefix
router = OperationRouter(prefix="bars.", tags=["market_data"])

@router.send("subscribe", reply="subscribe.response")
# Results in: "bars.subscribe" → "bars.subscribe.response"

# ❌ Bad - No prefix, cluttered namespace
router = OperationRouter()

@router.send("bars_subscribe", reply="bars_subscribe_response")
```

### 3. Document Operations

```python
# ✅ Good - Documented
@router.send("subscribe", reply="subscribe.response")
async def subscribe(payload: SubscriptionRequest, client: Client):
    """
    Subscribe to real-time bar updates for a symbol

    This operation adds the client to a topic-based subscription.
    Updates will be broadcast via the 'bars.update' message type.

    Args:
        payload: Subscription parameters (symbol, resolution)
        client: WebSocket client connection

    Returns:
        Confirmation with topic identifier
    """
    ...

# ❌ Bad - No documentation
@router.send("subscribe", reply="subscribe.response")
async def subscribe(payload, client):
    ...
```

### 4. Handle Errors Gracefully

```python
# ✅ Good - Graceful error handling
@router.send("operation", reply="response")
async def operation(payload: Request) -> Response:
    try:
        result = perform_task(payload)
        return Response(status="ok", data=result)
    except ValueError as e:
        return Response(status="error", message=str(e))

# ❌ Bad - Unhandled exceptions close connection
@router.send("operation", reply="response")
async def operation(payload: Request) -> Response:
    result = perform_task(payload)  # May raise exception
    return Response(status="ok", data=result)
```

---

**See Also**:

- `docs/websockets.md` - Complete WebSocket API documentation
- `external_packages/fastws/README.md` - FastWS framework documentation
- `tests/test_ws_datafeed.py` - Working test examples
