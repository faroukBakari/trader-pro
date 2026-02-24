---
name: ws-development
description: Full-stack WebSocket subscription development. Load when adding WS routes, topic services, or debugging WS data flows
user-invocable: false
---

# WebSocket Development

Methodology for adding, modifying, and debugging full-stack WebSocket subscription features. Covers the backend router framework, service topic protocol, frontend client layers, type generation pipeline, and error handling contracts.

---

## When to Use This Skill

- Adding a new WebSocket data stream (new router + service topic + frontend client)
- Modifying an existing subscription (changing params, payload shape, or error behavior)
- Debugging subscription lifecycle issues (subscribe/unsubscribe, topic leaks, stale clients)
- Understanding the type pipeline (Pydantic model → AsyncAPI → generated TS → mapper)
- Writing or updating WS tests (backend or frontend)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend                                                            │
│                                                                     │
│  Vue Component                                                      │
│    ↕ subscribe(listenerId, params, onUpdate, onError?)              │
│  WsAdapter  (singleton facade — one client per data domain)         │
│    ↕ deduplication by paramsKey, debounced unsubscribe              │
│  WebSocketClient<TParams, TBackendData, TData>  (per-route)        │
│    ↕ dataMapper(backendData) → frontendData                         │
│  WebSocketBase  (singleton per URL — raw WS lifecycle)              │
│    ↕ JSON message: { type, payload }                                │
├─────────────────── WebSocket ───────────────────────────────────────┤
│ Backend                                                             │
│                                                                     │
│  FastWSAdapter  (per-module, serves /ws endpoint)                   │
│    ↕ routes messages to WsRouter by operation type                  │
│  WsRouter[TRequest, TData]  (generic — 4 operations auto-wired)    │
│    ↕ topic lifecycle: _create_topic / _remove_topic                 │
│  Service (WsRouteService protocol)                                  │
│    ↕ create_topic(topic, topic_update, topic_error, user_id)        │
│  Provider (Capability interface)                                    │
│    ↕ subscribe_*(callback, on_error) → subscription_id              │
│  External System (TWS, exchange, etc.)                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### 1. Topic String Contract (Critical Invariant)

The backend and frontend MUST produce identical topic strings for the same subscription parameters. This is the identity key that routes messages to the correct subscribers.

**Format**: `"{route}:{serializedParams}"`

**Serialization rules** (both sides must match exactly):
- Keys sorted alphabetically
- `null`/`undefined`/`None` → empty string `""`
- Compact JSON separators: `(",", ":")`
- No trailing spaces or whitespace

Backend function: `buildTopicParams(obj)` in `shared/ws/ws_router.py`
Frontend function: `serializeParams(obj)` in `plugins/wsClientBase.ts`

**Breaking this contract** causes subscriptions to silently fail — updates never reach the client because topic strings don't match.

### 2. The Four Operations

Every `WsRouter[TRequest, TData]` auto-registers exactly four operations on construction:

| Operation | Direction | Purpose |
|-----------|-----------|---------|
| `{route}.subscribe` | client → server | Start subscription, returns topic |
| `{route}.subscribe.response` | server → client | Confirmation with topic string |
| `{route}.unsubscribe` | client → server | End subscription |
| `{route}.unsubscribe.response` | server → client | Confirmation |
| `{route}.update` | server → client | Data payload broadcast |
| `{route}.error` | server → client | Error payload broadcast |

The subscribe/unsubscribe operations use `SubscriptionRequest[TRequest]` envelope.
The update operation uses `SubscriptionUpdate[TData]` envelope.
The error operation uses `SubscriptionError` (with `ErrorPayload`, `recoverable`, `retry_after_ms`).

### 3. Topic Lifecycle

```
First subscriber for params → _create_topic(topic, user_id)
  → service.create_topic(topic, topic_update_cb, topic_error_cb, user_id)
    → provider.subscribe_*(callback, on_error) → subscription_id
    → service stores topic → subscription_id mapping

Provider pushes data → topic_update_cb(data)
  → WsRouter wraps in SubscriptionUpdate, broadcasts to all topic clients

Provider pushes error → topic_error_cb(exc, recoverable, retry_after_ms)
  → WsRouter wraps in SubscriptionError, broadcasts
  → If unrecoverable: unsubscribes all clients, discards topic

Last subscriber unsubscribes → _remove_topic(topic)
  → service.remove_topic(topic)
    → provider.unsubscribe(subscription_id)
```

**Key principle**: Topics are reference-counted. Created on first subscriber, destroyed when last subscriber leaves. The router manages this automatically.

---

## Adding a New WebSocket Stream

### Step 1: Define Backend Models

Create Pydantic models for subscription params and payload data:

```python
# models/{domain}/subscription_models.py
class MySubscriptionRequest(BaseModel):
    """Subscription parameters — fields become part of topic string."""
    symbol: str
    interval: str | None = None   # None serializes to "" in topic

class MyDataPayload(BaseModel):
    """Data pushed to subscribers on each update."""
    symbol: str
    value: float
    timestamp: int
```

**Constraint**: Subscription request fields directly affect topic identity. Two requests with different field values create different topics. Design params to represent the minimal unique subscription key.

### Step 2: Create Backend WS Router

In the module's `ws/v1/__init__.py`:

```python
from trading_api.shared.ws import WsRouter, WsRouterBase, WsRouteService

class MyDataRouter(WsRouter[MySubscriptionRequest, MyDataPayload]):
    pass  # Zero boilerplate — generic types provide everything

class MyModuleWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        my_data_router = MyDataRouter(
            route="my-data",       # becomes "my-data.subscribe", "my-data.update", etc.
            tags=["my-module"],    # AsyncAPI grouping
            service=service,
        )
        super().__init__([my_data_router], service=service)
```

**Constraints**:
- Router class inherits `WsRouter[TRequest, TData]` with concrete types
- Generic types are resolved at runtime via `__orig_bases__` introspection
- The `route` string becomes the operation prefix and topic prefix
- The service must implement the `WsRouteService` protocol (validated at init)

### Step 3: Implement Service Topic Handlers

The service must implement the `WsRouteService` protocol:

```python
class WsRouteService(Protocol):
    async def create_topic(
        self, topic: str,
        topic_update: ProviderUpdateCallback,
        topic_error: TopicErrorCallback,
        user_id: str,
    ) -> None: ...

    def remove_topic(self, topic: str) -> None: ...
```

Implementation pattern:

```python
class MyService(ServiceInterface, WsRouteService):
    _topic_to_subscription_id: dict[str, str]  # topic → provider subscription ID

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._topic_to_subscription_id = {}

    async def create_topic(self, topic, topic_update, topic_error, user_id):
        # 1. Parse topic to extract params
        # Topic format: "my-data:{serialized_params}"
        # 2. Subscribe to provider with callbacks
        async def on_provider_error(exc):
            recoverable = exc.code in self._RECOVERABLE_ERROR_CODES
            await topic_error(exc, recoverable, 5000 if recoverable else None)

        sub_id = await self.my_provider.subscribe_something(
            callback=topic_update,    # provider pushes data → router broadcasts
            on_error=on_provider_error,
        )
        self._topic_to_subscription_id[topic] = sub_id

    def remove_topic(self, topic):
        sub_id = self._topic_to_subscription_id.pop(topic, None)
        if sub_id:
            self.my_provider.unsubscribe(sub_id)

    _RECOVERABLE_ERROR_CODES = frozenset({
        "PROVIDER_MY_TIMEOUT",
        "PROVIDER_MY_CONNECTION_LOST",
        "PROVIDER_MY_RATE_LIMIT",
    })
```

**Constraints**:
- `create_topic` receives two callbacks: `topic_update` for data, `topic_error` for errors
- The service wraps `topic_error` to classify recoverability from provider error codes
- `remove_topic` is synchronous — must not do async I/O
- The service owns the `topic → subscription_id` mapping for cleanup

### Step 4: Generate AsyncAPI Types

After backend changes, the spec generation pipeline runs:
1. `FastWSAdapter.asyncapi()` produces per-module AsyncAPI JSON
2. Shell script finds `*_asyncapi.json` in module specs
3. Node script extracts `components.schemas`, generates TypeScript interfaces/enums
4. Output: `clients_generated/ws-types-{module}_{version}/index.ts`

Run: `make -C backend generate` then `make -C frontend generate`

**Constraint**: Never edit generated files. Fix the source Pydantic model instead.

### Step 5: Create Frontend Mapper

In `plugins/mappers.ts`, follow the naming convention:

```typescript
import type { MyDataPayload as MyDataPayload_Ws_Backend } from '@clients/ws-types-mymodule_v1'
import type { MyDataPayload } from '@/types/mymodule'  // frontend type

export function mapMyData(data: MyDataPayload_Ws_Backend): MyDataPayload {
    return {
        symbol: data.symbol,
        value: data.value,
        timestamp: data.timestamp,
        // null → undefined conversions, enum mappings, etc.
    }
}
```

**Naming convention** (immutable rule from CLAUDE.md):
- REST API types: `TypeName_Api_Backend`
- WS types: `TypeName_Ws_Backend`
- Frontend types: `TypeName` (no suffix)

### Step 6: Register Frontend WS Client

In `plugins/wsAdapter.ts`:

```typescript
// In WsAdapterType interface — add new client
myData: WebSocketInterface<MySubscriptionRequest, MyDataPayload>

// In WsAdapter constructor
this.myData = new WebSocketClient<MySubscriptionRequest, MyDataPayload_Ws_Backend, MyDataPayload>(
    myModuleWsUrl,
    'my-data',           // must match backend route string exactly
    mapMyData,           // backend → frontend type mapper
    500,                 // optional debounce ms (for resolution switching)
)
```

### Step 7: Subscribe from Vue Component

```typescript
// In component setup or composable
const wsAdapter = WsAdapter.getInstance()

onMounted(() => {
    wsAdapter.myData.subscribe(
        'component-unique-id',
        { symbol: 'AAPL', interval: '1m' },
        (data) => { /* handle update */ },
        (error) => { /* handle error (optional) */ },
    )
})

onUnmounted(() => {
    wsAdapter.myData.unsubscribe('component-unique-id')
})
```

---

## Error Handling

| Level | Scope | Example | Handling |
|-------|-------|---------|----------|
| Connection | All subscriptions | Network drop, auth failure | `WebSocketBase` auto-reconnect + `onclose` codes |
| Subscription | Single topic | Invalid params, provider error | `topic_error` callback → frontend `onError` |

**Close codes**: 1000 (normal), 1008 (policy/auth), 1011 (server error), 4000-4999 (app-specific)

**Subscription error flow**: Provider error → Service `topic_error(topic, error)` → Router `_emit_error` → Frontend `onError` → Component error state

**Frontend error classes**: `WsConnectionError` (connection level), `WsSubscriptionError` (topic level) -- both extend `AppError`

---

## Frontend Client Architecture

- **Three layers**: `WsAdapter` (facade, singleton per domain) → `WebSocketClient<TParams, TBackendData, TData>` (per-route, typed) → `WebSocketBase` (singleton per URL, raw WS)
- **Deduplication**: Multiple subscribers to same params share one backend subscription via `paramsKey`
- **Debounced unsubscribe**: 2s delay before sending unsubscribe -- prevents flicker on component remount
- **Reconnection**: `WebSocketBase` auto-reconnects with exponential backoff; re-subscribes active topics on reconnect

---

## Testing Patterns

### Backend WS Tests
```python
@pytest.fixture
def ws_client(module_app):
    """Connect to module WS endpoint."""
    return module_app.test_ws_client("/ws")

async def test_subscribe_sends_update(ws_client, mock_provider):
    ws_client.send({"type": "subscribe", "payload": {"param": "value"}})
    response = ws_client.receive()
    assert response["type"] == "update"
    assert response["payload"]["field"] == expected
```

### Frontend WS Tests
```typescript
describe('WsAdapter', () => {
  it('deduplicates subscriptions by paramsKey', () => {
    const adapter = new WsAdapter(mockClient)
    adapter.subscribe('listener1', params, onUpdate1)
    adapter.subscribe('listener2', params, onUpdate2)
    expect(mockClient.subscribe).toHaveBeenCalledTimes(1) // single backend sub
  })
})
```

---

## Checklist: New WS Stream

- [ ] Pydantic models: `{Name}SubscriptionRequest` + payload model
- [ ] Backend router: `class {Name}Router(WsRouter[Request, Payload]): pass`
- [ ] Router registered in module's `WsRouterBase` subclass
- [ ] Service implements `create_topic` / `remove_topic` for the new route prefix
- [ ] Service defines `_RECOVERABLE_ERROR_CODES` for the provider's error codes
- [ ] Topic-to-subscription-id mapping maintained for cleanup
- [ ] `make -C backend generate` → AsyncAPI spec includes new channel
- [ ] `make -C frontend generate` → TS types generated
- [ ] Frontend mapper: `map{Name}()` with `_Ws_Backend` suffix convention
- [ ] `WsAdapter` updated with new `WebSocketClient` instance
- [ ] Component subscribes with unique listener ID, unsubscribes on unmount
- [ ] Backend tests: subscribe → receive update → unsubscribe
- [ ] Frontend tests: MockWebSocket simulation of full lifecycle

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Topic serialization mismatch (subscribe ok, no updates) | Verify `buildTopicParams`/`serializeParams` produce identical strings |
| Missing `None` → `""` normalization | Both serializers must normalize null/None/undefined to empty string |
| Forgetting `remove_topic` cleanup | Always pop subscription ID and call provider unsubscribe |
| Editing generated WS types | Fix the source Pydantic model, then `make generate` |
| Unrecoverable error without topic discard | `topic_error(recoverable=False)` must discard topic from `_topics` |
| Frontend listener ID collision | Use component-unique IDs (component name + instance ID) |
| Missing onUnmounted unsubscribe | Always pair subscribe/unsubscribe in lifecycle hooks |
