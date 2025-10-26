# Trading Pro - Architecture Documentation

**Version**: 2.0.0
**Last Updated**: October 21, 2025
**Status**: ✅ Production Ready

## Overview

Trading Pro is a modern full-stack trading platform built with **FastAPI** backend and **Vue.js** frontend, featuring RESTful API (OpenAPI) and real-time WebSocket streaming (AsyncAPI). Designed with **TDD** principles and modern DevOps practices.

## Core Principles

1. **Decoupled Architecture** - Independent frontend/backend development and deployment
2. **Type Safety** - End-to-end TypeScript/Python type safety with automatic client generation
3. **Test-Driven Development** - TDD workflow with comprehensive coverage
4. **Real-Time Streaming** - WebSocket-based market data with FastWS framework
5. **API Versioning** - Backwards-compatible evolution strategy
6. **DevOps Ready** - Automated CI/CD with parallel testing

## System Architecture

### High-Level View

```
┌──────────────────────────────────────────────────────────┐
│                   Trading Pro Platform                    │
├──────────────────────────────────────────────────────────┤
│  Frontend (Vue 3)        │  Backend (FastAPI)            │
│  • Composition API       │  • REST API (OpenAPI)         │
│  • TypeScript + Vite     │  • WebSocket (AsyncAPI)       │
│  • Pinia State Mgmt      │  • API Versioning (v1)        │
│  • Auto Client Gen       │  • TradingView Integration    │
│  • Smart Fallbacks       │  • Broker & Datafeed APIs     │
└──────────────────────────────────────────────────────────┘
```

### Technology Stack

#### Backend

- **Framework**: FastAPI 0.104+ (ASGI async)
- **WebSocket**: FastWS 0.1.7 (AsyncAPI documented)
- **Runtime**: Python 3.11 + Uvicorn
- **Package Mgmt**: Poetry
- **Testing**: pytest + pytest-asyncio + httpx
- **Type Safety**: MyPy + Pydantic
- **Code Quality**: Black + isort + Flake8
- **Docs**: OpenAPI 3.0 + AsyncAPI 2.4.0

#### Frontend

- **Framework**: Vue 3 + Composition API + TypeScript
- **Build**: Vite 7+
- **Package Mgmt**: npm (Node.js 20+)
- **State**: Pinia
- **Routing**: Vue Router 4
- **Testing**: Vitest + Vue Test Utils
- **Charts**: TradingView Advanced Charting Library
- **Code Quality**: ESLint + Prettier

#### Real-Time Infrastructure

- **Protocol**: WebSocket (ws/wss)
- **Framework**: FastWS with AsyncAPI docs
- **Pattern**: Topic-based pub/sub (`bars:SYMBOL:RESOLUTION`)
- **Operations**: Subscribe, Unsubscribe, Update messages
- **Features**: Heartbeat, connection lifespan, metrics

#### DevOps

- **CI/CD**: GitHub Actions (parallel jobs)
- **Testing**: Multi-tier (unit, integration, smoke, e2e)
- **Development**: VS Code multi-root workspace
- **Build**: Intelligent Makefile system

## Component Architecture

### Backend Structure

```
src/trading_api/
├── main.py              # App lifecycle, routing, specs
├── api/                 # REST endpoints (class-based APIRouter)
│   ├── broker.py        # BrokerApi class - Broker operations (orders, positions, leverage)
│   ├── datafeed.py      # DatafeedApi class - Market data endpoints
│   ├── health.py        # HealthApi class - Health checks
│   └── versions.py      # VersionApi class - API versioning
├── ws/                  # WebSocket operations (router factories)
│   ├── router_interface.py  # WsRouterInterface, WsRouteService Protocol
│   ├── generic_route.py     # Generic WsRouter implementation
│   ├── broker.py            # BrokerWsRouters factory (orders, positions, executions, equity, connection)
│   ├── datafeed.py          # DatafeedWsRouters factory (bars, quotes)
│   └── generated/           # Auto-generated concrete router classes
├── core/                # Business logic services
│   ├── broker_service.py      # BrokerService (implements WsRouteService Protocol)
│   └── datafeed_service.py    # DatafeedService (implements WsRouteService Protocol)
├── models/              # Pydantic models (topic-based organization)
│   ├── common.py        # Shared types (BaseApiResponse, SubscriptionUpdate, etc.)
│   ├── health.py        # Health check models
│   ├── versioning.py    # API version models
│   ├── broker/          # Broker business domain models
│   │   ├── common.py       # Shared broker models (SuccessResponse)
│   │   ├── orders.py       # Order models (REST + WebSocket)
│   │   ├── positions.py    # Position models (REST + WebSocket)
│   │   ├── executions.py   # Execution models (REST + WebSocket)
│   │   ├── account.py      # Account/equity models (REST + WebSocket)
│   │   ├── connection.py   # Connection status models (WebSocket)
│   │   └── leverage.py     # Leverage models (REST)
│   └── market/          # Market data business domain models
│       ├── bars.py         # Bar/OHLC models (REST + WebSocket)
│       ├── quotes.py       # Quote models (REST + WebSocket)
│       ├── instruments.py  # Symbol/instrument models (REST)
│       ├── search.py       # Search models (REST)
│       └── configuration.py # Datafeed config models (REST)
└── plugins/
    └── fastws_adapter.py  # FastWS integration adapter

tests/
├── test_api_broker.py   # Broker API tests
├── test_api_health.py   # Health endpoint tests
├── test_api_versioning.py # Versioning API tests
├── test_ws_broker.py    # Broker WebSocket tests
└── test_ws_datafeed.py  # Datafeed WebSocket tests
```

### Backend Models Architecture

**Organizational Principle**: Models are grouped by **business concepts/domains**, not by technical layers or API types.

#### Topic-Based Model Organization

The backend follows a **domain-driven design** approach where models are organized around business concepts (topics) rather than technical API types:

```
models/
├── common.py           # Cross-cutting shared models
├── broker/             # Broker business domain
│   ├── orders.py       # Everything related to orders (REST + WS)
│   ├── positions.py    # Everything related to positions (REST + WS)
│   ├── executions.py   # Everything related to executions (REST + WS)
│   ├── account.py      # Everything related to accounts (REST + WS)
│   ├── connection.py   # Everything related to broker connections (WS)
│   └── leverage.py     # Everything related to leverage (REST)
└── market/             # Market data business domain
    ├── bars.py         # Everything related to bars/OHLC (REST + WS)
    ├── quotes.py       # Everything related to quotes (REST + WS)
    ├── instruments.py  # Everything related to instruments/symbols (REST)
    ├── search.py       # Everything related to search (REST)
    └── configuration.py # Everything related to datafeed config (REST)
```

#### Design Principles

1. **Business Concept Grouping**

   - Each file represents a **single business concept** (orders, positions, bars, etc.)
   - All model variations for that concept live in the same file
   - Both REST and WebSocket models coexist in topic files

2. **Model Type Coexistence**

   - REST request/response models: `PreOrder`, `PlacedOrder`
   - WebSocket subscription models: `OrderSubscriptionRequest`
   - WebSocket update models: Use the same response models as REST
   - All related to the same business concept stay together

3. **No Technical Segregation**

   - ❌ **AVOID**: Separating by API type (`rest_models/`, `ws_models/`)
   - ❌ **AVOID**: Separating by operation type (`requests/`, `responses/`)
   - ✅ **PREFER**: One topic file contains all model types for that domain

4. **Domain Separation**
   - Top-level separation by business domain (`broker/`, `market/`)
   - Reflects the two main API areas: trading operations vs market data
   - Aligns with TradingView API structure (broker API vs datafeed API)

#### Example: orders.py Structure

```python
# models/broker/orders.py

# Enumerations (shared across REST + WebSocket)
class OrderStatus(IntEnum): ...
class OrderType(IntEnum): ...
class Side(IntEnum): ...

# REST Models
class PreOrder(BaseModel):
    """Order request from client (REST API input)"""
    symbol: str
    type: OrderType
    # ...

class PlacedOrder(BaseModel):
    """Complete order with status (REST API output + WebSocket update)"""
    id: str
    symbol: str
    status: OrderStatus
    # ...

# WebSocket Models
class OrderSubscriptionRequest(BaseModel):
    """WebSocket subscription parameters for order updates"""
    accountId: str
```

**Key Insight**: `PlacedOrder` is used in both:

- REST API responses (`GET /api/v1/broker/orders`)
- WebSocket update messages (`orders.update`)

This eliminates duplication and ensures consistency across API types.

#### Benefits of Topic-Based Organization

✅ **Single Source of Truth**: One place for all order-related models
✅ **Reduced Duplication**: Shared models between REST and WebSocket
✅ **Easier Maintenance**: Changes to business logic happen in one file
✅ **Better Discoverability**: Developers find all related models together
✅ **Domain Alignment**: Matches business concepts, not technical infrastructure
✅ **Type Reusability**: Same `PlacedOrder` model for REST responses and WS updates
✅ **Enum Sharing**: Enumerations (`OrderStatus`, `OrderType`) shared across all operations

#### Anti-Patterns to Avoid

❌ **Technical Layer Separation**:

```
models/
├── rest/
│   ├── orders.py
│   └── positions.py
└── websocket/
    ├── orders.py       # Duplication!
    └── positions.py    # Duplication!
```

❌ **Operation Type Separation**:

```
models/
├── requests/
│   ├── order_request.py
│   └── subscription_request.py
└── responses/
    ├── order_response.py
    └── subscription_response.py
```

✅ **Business Topic Organization** (Current):

```
models/
├── broker/
│   ├── orders.py       # PreOrder, PlacedOrder, OrderSubscriptionRequest
│   └── positions.py    # Position, PositionSubscriptionRequest
└── market/
    └── bars.py         # Bar, BarsSubscriptionRequest
```

#### Integration with WebSocket Routers

WebSocket routers import models from their corresponding topic files:

```python
# ws/broker.py
from trading_api.models.broker.orders import OrderSubscriptionRequest, PlacedOrder
from trading_api.models.broker.positions import PositionSubscriptionRequest, Position

if TYPE_CHECKING:
    OrderWsRouter: TypeAlias = WsRouter[OrderSubscriptionRequest, PlacedOrder]
    PositionWsRouter: TypeAlias = WsRouter[PositionSubscriptionRequest, Position]
```

This creates a clean flow:

1. **Business concept** defines all related models in one file
2. **Router** imports subscription request + update model from the same topic file
3. **Type safety** ensured across REST and WebSocket operations

#### Guidelines for New Models

When adding new models:

1. **Identify the business concept** (order, position, bar, quote, etc.)
2. **Locate the appropriate topic file** (`broker/orders.py`, `market/bars.py`, etc.)
3. **Add all model types** to that single file (request, response, subscription)
4. **Share enumerations and common types** across REST and WebSocket
5. **Export from topic `__init__.py`** to maintain clean imports
6. **Update domain `__init__.py`** (`broker/__init__.py`, `market/__init__.py`)
7. **Export from main models** (`models/__init__.py`) for external access

**Never** create separate files for WebSocket vs REST models of the same business concept.

## WebSocket Real-Time Architecture

### WsRouteService Protocol Pattern

The backend implements a **Protocol-based WebSocket service architecture** where services manage their own topic generators and broadcast updates through the FastWSAdapter.

#### Core Components

**1. `WsRouteService` (Protocol)**

Location: `ws/router_interface.py`

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

**Implementations**: `BrokerService`, `DatafeedService`

**2. Service Implementation (Self-Managed Generators)**

Location: `core/datafeed_service.py`, `core/broker_service.py`

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

    async def _bar_generator(self, topic: str) -> None:
        """Generate and broadcast bar data for topic."""
        while True:
            bar = self.mock_last_bar(symbol, resolution)
            await self.publish(topic, bar)  # Publish to FastWSAdapter
            await asyncio.sleep(interval)
```

**3. `WsRouter` (Generic Implementation with Reference Counting)**

Location: `ws/generic_route.py`

```python
class WsRouter(WsRouterInterface, Generic[_TRequest, _TData]):
    """Generic WebSocket router with subscription management."""

    def __init__(self, route: str, tags: list, service: WsRouteService):
        super().__init__(prefix=f"{route}.", tags=tags)
        self.service = service
        self.topic_trackers: dict[str, int] = {}  # Reference counting

    # Subscribe handler creates topic on first subscriber
    @self.send("subscribe", reply="subscribe.response")
    async def send_subscribe(payload: _TRequest, client: Client):
        topic = self.topic_builder(payload)
        client.subscribe(topic)

        if topic not in self.topic_trackers:
            # First subscriber - create topic
            self.topic_trackers[topic] = 1
            await self.service.create_topic(topic)
        else:
            # Additional subscriber - increment count
            self.topic_trackers[topic] += 1

    # Unsubscribe handler removes topic when count reaches 0
    @self.send("unsubscribe", reply="unsubscribe.response")
    def send_unsubscribe(payload: _TRequest, client: Client):
        topic = self.topic_builder(payload)
        client.unsubscribe(topic)

        if topic in self.topic_trackers:
            self.topic_trackers[topic] -= 1
            if self.topic_trackers[topic] <= 0:
                del self.topic_trackers[topic]
                self.service.remove_topic(topic)  # Cleanup
```

**4. `FastWSAdapter` (Broadcasting with Per-Router Queues)**

Location: `plugins/fastws_adapter.py`

```python
class FastWSAdapter(FastWS):
    """Self-contained WebSocket adapter with embedded endpoint and broadcasting."""

    def __init__(self, ...) -> None:
        super().__init__(...)
        self._routers: dict[str, WsRouterInterface] = {}
        self._router_queues: dict[str, asyncio.Queue] = {}
        self._broadcast_tasks: list[asyncio.Task] = []

    def include_router(self, router: WsRouterInterface) -> None:
        """Register router and start broadcasting task."""
        self._routers[router.route] = router
        updates_queue: asyncio.Queue = asyncio.Queue()
        self._router_queues[router.route] = updates_queue

        # Start background task for this router
        task = asyncio.create_task(
            self.broadcast_router_messages(router.route, updates_queue)
        )
        self._broadcast_tasks.append(task)

        super().include_router(router)

    async def broadcast_router_messages(
        self, route: str, updates_queue: asyncio.Queue
    ) -> None:
        """Background task broadcasting messages for a specific router."""
        while True:
            topic, data = await updates_queue.get()
            message = Message(type=f"{route}.update", payload=data)
            await self.server_send(message, topic=topic)

    async def publish(self, topic: str, data: BaseModel, route: str) -> None:
        """Queue data update for broadcasting to subscribed clients."""
        if route in self._router_queues:
            await self._router_queues[route].put((topic, data.model_dump()))
```

#### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WebSocket Data Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Service Layer (BrokerService / DatafeedService)            │
│     └─> Manages _topic_generators: dict[str, asyncio.Task]     │
│     └─> create_topic() starts generator task                   │
│     └─> Generator calls publish(topic, data)                   │
│                                                                 │
│  2. FastWSAdapter (Broadcasting Layer)                         │
│     └─> Maintains _router_queues per router                    │
│     └─> publish() queues (topic, data) for router              │
│     └─> Background task polls queue and broadcasts             │
│         await server_send(message, topic=topic)                │
│                                                                 │
│  3. WsRouter (Subscription Management)                         │
│     └─> Subscribe: Increments topic_trackers[topic]            │
│     └─> First subscriber → service.create_topic()              │
│     └─> Unsubscribe: Decrements topic_trackers[topic]          │
│     └─> Last unsubscribe → service.remove_topic()              │
│                                                                 │
│  4. FastWS Framework                                           │
│     └─> Manages WebSocket connections                          │
│     └─> Delivers updates to subscribed clients via topics      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Decisions

**1. Protocol-Based Contracts**

- Services implement simple two-method Protocol
- No inheritance required (BrokerService, DatafeedService are independent)
- Clean dependency injection

**2. Service-Managed Generators**

- Each service owns its `_topic_generators` dict
- Services control timing and data generation
- Services call `publish()` to broadcast updates

**3. Reference Counting with Simple Dict**

- `topic_trackers: dict[str, int]` tracks subscriber count
- First subscriber triggers `create_topic()`
- Last unsubscribe triggers `remove_topic()`

**4. FastWSAdapter Broadcasting**

- Per-router queues for message distribution
- Background tasks poll queues and broadcast
- Clean separation: services → adapter → clients

#### Router Factory Pattern

**Class-Based API Routers**:

```python
# api/broker.py
class BrokerApi(APIRouter):
    def __init__(self, broker_service: BrokerService):
        super().__init__(prefix="/broker", tags=["broker"])
        self.broker_service = broker_service
        # Define routes in __init__
```

**WebSocket Router Factories**:

```python
# ws/broker.py
class BrokerWsRouters(list[WsRouterInterface]):
    def __init__(self, broker_service: WsRouteService):
        order_router = OrderWsRouter(route="orders", service=broker_service)
        position_router = PositionWsRouter(route="positions", service=broker_service)
        super().__init__([order_router, position_router, ...])
```

**Benefits**:

- Dependency injection (services passed in constructor)
- No global state or singletons
- Testable (mock services easily)
- Clean lifecycle management

### Frontend Structure

```
src/
├── main.ts             # App entry point
├── App.vue             # Root component
├── router/             # Vue Router config
├── stores/             # Pinia state management
├── services/           # API service layer
│   ├── brokerTerminalService.ts   # Broker adapter
│   └── datafeedService.ts         # Datafeed adapter
├── plugins/
│   ├── wsAdapter.ts    # Centralized WebSocket clients wrapper
│   ├── wsClientBase.ts # WebSocket base client (singleton)
│   ├── mappers.ts      # Type-safe data transformations
│   └── apiAdapter.ts   # REST client wrapper
├── clients/            # Auto-generated clients
│   ├── trader-client-generated/   # REST API client
│   └── ws-types-generated/        # WebSocket types
├── components/         # Vue components
└── types/              # TypeScript type definitions

scripts/
├── generate-openapi-client.sh    # REST client generation
└── generate-asyncapi-types.sh    # WebSocket types generation
```

## Data Flow

### REST API Flow

```
Frontend → Generated Client → ApiAdapter → FastAPI Router
         ← Type-safe data  ← Pydantic    ← Business Logic
```

### WebSocket Flow (Centralized Architecture)

```
┌──────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  (DatafeedService, BrokerTerminalService)                    │
└─────────────────────────┬────────────────────────────────────┘
                          │ wsAdapter.bars.subscribe()
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Adapter Layer                             │
│  WsAdapter - Centralized clients (bars, quotes, etc.)        │
└─────────────────────────┬────────────────────────────────────┘
                          │ WebSocketClient<TParams, TBackendData, TData>
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Mapper Layer                              │
│  mappers.ts - Type-safe transformations                      │
│  • mapQuoteData() • mapPreOrder()                            │
└─────────────────────────┬────────────────────────────────────┘
                          │ Backend types → Frontend types
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Client Layer                              │
│  WebSocketClient - Generic client with mapping               │
└─────────────────────────┬────────────────────────────────────┘
                          │ Uses singleton instance
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Base Layer                                │
│  WebSocketBase - Singleton connection management             │
│  • Subscribe/Unsubscribe • Topic routing                     │
│  • Auto-reconnection • Reference counting                    │
└─────────────────────────┬────────────────────────────────────┘
                          │ WebSocket protocol
                          ▼
                   Backend (/api/v1/ws)
```

### WebSocket Message Flow

```
1. SUBSCRIPTION
   Service → WsAdapter.bars.subscribe()
         → WebSocketClient (applies mapper)
         → WebSocketBase (manages connection)
         → Backend
         ← bars.subscribe.response (confirmation)
         → Mark subscription as confirmed

2. DATA UPDATES
   Backend broadcasts → bars.update
         → WebSocketBase (routes to confirmed subscribers)
         → WebSocketClient (applies mapper: TBackendData → TData)
         → Callback in Service
```

## Client Generation

### Automated Workflow

1. **Backend Startup** → Generates `openapi.json` + `asyncapi.json`
2. **File Watchers** → Monitor spec files for changes
3. **Auto-Generation** → Regenerate clients on spec changes
4. **Type Safety** → Full TypeScript types from Pydantic models

**Benefits**:

- ✅ Automatic sync on backend changes
- ✅ Hot reload integration
- ✅ File-based (efficient, no server polling)
- ✅ One command startup: `make dev-fullstack`

## API Versioning

**Current**: `/api/v1/` (Stable)
**Planned**: `/api/v2/` (Future breaking changes)

**Strategy**:

- URL-based versioning (`/api/v{major}/`)
- No breaking changes within versions
- 6-month deprecation period
- Version info in responses

**Lifecycle**: Development → Beta → Stable → Deprecated → Sunset

## Testing Strategy

### Testing Pyramid

```
┌────────────────────────────────────────┐
│ E2E (Playwright)    │ Full workflows   │
├────────────────────────────────────────┤
│ Integration         │ API contracts    │
├────────────────────────────────────────┤
│ Unit Tests          │ Isolated logic   │
│ • Backend (pytest)  │ • FastAPI Test   │
│ • Frontend (Vitest) │ • Vue Test Utils │
└────────────────────────────────────────┘
```

**Key Features**:

- Independent backend/frontend testing (no cross-dependencies)
- FastAPI TestClient for backend (no server needed)
- Mock services for frontend (offline testing)
- Parallel execution in CI/CD

## Mapper Layer Architecture

### Overview

The mapper layer provides centralized, type-safe data transformations between backend and frontend types, ensuring clean separation of concerns.

**Location**: `frontend/src/plugins/mappers.ts`

### ⚠️ STRICT NAMING CONVENTIONS ⚠️

**CRITICAL**: Always follow these naming conventions when importing types in mappers:

```typescript
// ✅ CORRECT: Strict naming pattern
import type { QuoteData as QuoteData_Api_Backend } from "@clients/trader-client-generated";
import type { PlacedOrder as PlacedOrder_Ws_Backend } from "@clients/ws-types-generated";
import type {
  QuoteData,
  PlacedOrder,
} from "@public/trading_terminal/charting_library";

// ❌ WRONG: Inconsistent naming
import type { QuoteData as QuoteData_Backend } from "@clients/trader-client-generated";
import type { PlacedOrder as Order_Backend } from "@clients/ws-types-generated";
```

**Naming Rules**:

- **API Backend imports**: `<TYPE>_Api_Backend` (e.g., `QuoteData_Api_Backend`)
- **WebSocket Backend imports**: `<TYPE>_Ws_Backend` (e.g., `PlacedOrder_Ws_Backend`)
- **Frontend imports**: `<TYPE>` (e.g., `QuoteData`, `PlacedOrder`)

**Why Strict Naming?**

- **Readability**: Instantly identify source of each type
- **Maintainability**: Consistent pattern across all mappers
- **Type Safety**: Clear distinction between backend variants (API vs WS)
- **Debugging**: Easy to trace type mismatches

### Design Pattern

```
Backend Types (Python Pydantic)
    ↓ OpenAPI/AsyncAPI Generation
Generated Types (*_Backend suffix)
    ↓ Mapper Functions
Frontend Types (TradingView/Custom)
```

### Available Mappers

#### `mapQuoteData()`

Transforms backend quote data to TradingView frontend format:

```typescript
import type { QuoteData as QuoteData_Backend } from "@/clients/trader-client-generated";
import type { QuoteData } from "@public/trading_terminal/charting_library";

export function mapQuoteData(quote: QuoteData_Backend): QuoteData {
  if (quote.s === "error") {
    return { s: "error", n: quote.n, v: quote.v };
  }
  return {
    s: "ok",
    n: quote.n,
    v: {
      ch: quote.v.ch,
      chp: quote.v.chp,
      lp: quote.v.lp,
      ask: quote.v.ask,
      bid: quote.v.bid,
      // ... complete field mapping
    },
  };
}
```

**Usage**: Integrated in `WsAdapter` for real-time quotes, also used in REST API responses.

#### `mapPreOrder()`

Transforms frontend order to backend format with enum conversions:

```typescript
export function mapPreOrder(order: PreOrder): PreOrder_Backend {
  return {
    symbol: order.symbol,
    type: order.type as unknown as PreOrder_Backend["type"],
    side: order.side as unknown as PreOrder_Backend["side"],
    qty: order.qty,
    limitPrice: order.limitPrice ?? null,
    stopPrice: order.stopPrice ?? null,
    // ... handles optional fields and enum conversions
  };
}
```

**Usage**: Used in broker service for order placement.

### Integration Points

1. **WebSocket Clients** - Mappers applied automatically in `WsAdapter`:

   ```typescript
   this.quotes = new WebSocketClient("quotes", mapQuoteData);
   ```

2. **REST API Responses** - Mappers used in service layer:

   ```typescript
   const quotes = await api.getQuotes(symbols);
   return quotes.map(mapQuoteData);
   ```

3. **Type Isolation** - Services never import backend types directly:

   ```typescript
   // ✅ CORRECT: Use mapper
   import { mapQuoteData } from "@/plugins/mappers";

   // ❌ WRONG: Don't import backend types in services
   import type { QuoteData as QuoteData_Backend } from "@/clients/...";
   ```

### Benefits

✅ **Type Safety**: Compile-time validation of transformations
✅ **Reusability**: Single mapper for REST + WebSocket
✅ **Maintainability**: Centralized transformation logic
✅ **Backend Isolation**: Backend types confined to mapper layer
✅ **Runtime Validation**: Handles enum conversions and null handling

## Real-Time Architecture

### WebSocket Implementation

**Endpoint**: `ws://localhost:8000/api/v1/ws`
**Framework**: FastWS 0.1.7
**Documentation**: AsyncAPI at `/api/v1/ws/asyncapi`

> ⚠️ **IMPORTANT**: All WebSocket routers are generated using code generation from a generic template. When implementing WebSocket features, always follow the router generation mechanism documented in [`backend/src/trading_api/ws/WS-ROUTER-GENERATION.md`](backend/src/trading_api/ws/WS-ROUTER-GENERATION.md). This ensures type safety, consistency, and passes all quality checks.

### Centralized Adapter Pattern

All WebSocket operations go through `WsAdapter`:

```typescript
// Single entry point for all WebSocket clients
export class WsAdapter implements WsAdapterType {
  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>;
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>;

  constructor() {
    this.bars = new WebSocketClient("bars", (data) => data);
    this.quotes = new WebSocketClient("quotes", mapQuoteData);
  }
}
```

**Features**:

- Singleton WebSocket connection (shared across all clients)
- Automatic data mapping via mappers
- Server-confirmed subscriptions
- Auto-reconnection with resubscription
- Type-safe operations

### Message Pattern

```json
{
  "type": "operation.name",
  "payload": {
    /* data */
  }
}
```

### Operations

**Subscribe to Bars**:

```json
// Client → Server
{"type": "bars.subscribe", "payload": {"symbol": "AAPL", "resolution": "1"}}

// Server → Client
{"type": "bars.subscribe.response", "payload": {"status": "ok", "topic": "bars:AAPL:1"}}
```

**Receive Updates**:

```json
// Server → Client (Broadcast)
{"type": "bars.update", "payload": {"time": 1697097600000, "open": 150.0, ...}}
```

### Topic Format

**CRITICAL**: Topics use **JSON-serialized parameters** with sorted keys, not simple string concatenation.

```
{route}:{JSON-serialized-params}
```

**Examples**:

- `bars:{"resolution":"1","symbol":"AAPL"}` - Apple 1-minute bars
- `orders:{"accountId":"TEST-001"}` - Orders for account TEST-001
- `executions:{"accountId":"TEST-001","symbol":"AAPL"}` - AAPL executions for account

**⚠️ Topic Builder Compliance**: The topic builder algorithm MUST be **identical** in backend (Python) and frontend (TypeScript). See:

- Backend: `backend/src/trading_api/ws/router_interface.py` - `buildTopicParams()`
- Frontend: `frontend/src/plugins/wsClientBase.ts` - `buildTopicParams()`
- Documentation: `backend/docs/WEBSOCKETS.md` and `docs/WEBSOCKET-CLIENTS.md`

**Features**:

- Multi-symbol/multi-account subscriptions per client
- Topic-based filtering with complex parameters
- Broadcast only to subscribers with matching topics
- Automatic cleanup on disconnect
- Type-safe parameter serialization

### Connection Management

- **Heartbeat**: 30s interval (client must send messages)
- **Max Lifespan**: 1 hour per connection
- **Error Handling**: Graceful with WS status codes
- **Authentication**: Extensible (currently optional)

## Development Workflow

### Full-Stack Development

```bash
# Recommended: One command starts everything
make -f project.mk dev-fullstack

# What it does:
# 1. Port availability check
# 2. Start backend (generates specs)
# 3. Wait for backend ready
# 4. Generate API clients
# 5. Start file watchers (auto-regenerate on changes)
# 6. Start frontend
# 7. Monitor all processes
```

### Component Development

```bash
# Backend only
cd backend && make dev

# Frontend only (after backend ready)
cd frontend && make dev

# Run tests
make -f project.mk test-all

# Code quality
make -f project.mk lint-all format-all
```

## Design Patterns

### Backend Patterns

- **Dependency Injection** - FastAPI's DI system
- **Service Layer** - Business logic separation
- **Repository Pattern** - Data access abstraction
- **Response Models** - Consistent API responses

### Frontend Patterns

- **Composition API** - Vue 3 modern pattern
- **Store Pattern** - Pinia state management
- **Service Layer** - API abstraction with smart fallbacks
- **Dual-Client System** - Mock + Real backend adapters

### Cross-Cutting

- **Contract-First** - OpenAPI/AsyncAPI specifications
- **Test-Driven** - TDD workflow
- **Type-First** - TypeScript/Python type safety

## Performance Considerations

### Backend

- ASGI async/await for high concurrency
- In-memory caching for frequently accessed data
- Pydantic model optimization
- Efficient WebSocket broadcasting (topic-based)

### Frontend

- Vite for fast ES builds
- Code splitting and lazy loading
- Vue 3 Composition API optimizations
- Efficient state management with Pinia

### Real-Time

- Connection pooling
- Topic-based filtering (send only to subscribers)
- Heartbeat system for connection health
- Configurable rate limiting

## Security

### Current Measures

- CORS configuration
- Pydantic input validation
- MyPy + TypeScript static analysis
- Comprehensive test coverage

### Planned Enhancements

- JWT authentication
- Per-endpoint rate limiting
- HTTPS/WSS for production
- Enhanced input sanitization

## Monitoring & Observability

**Current**:

- Health endpoints (`/api/v1/health`)
- API version tracking
- WebSocket connection metrics
- Comprehensive test reporting

**Planned**:

- Application metrics (response times, error rates)
- WebSocket lifecycle tracking
- Centralized error logging
- Performance profiling

## Documentation Structure

### Core Documentation

- **ARCHITECTURE.md** - System architecture (this file)
- **BACKEND-API-METHODOLOGY.md** - TDD implementation guide
- **docs/DEVELOPMENT.md** - Development workflows
- **docs/TESTING.md** - Testing strategies
- **docs/CLIENT-GENERATION.md** - API client generation
- **docs/WEBSOCKET-CLIENTS.md** - WebSocket implementation

### Configuration

- **WORKSPACE-SETUP.md** - VS Code workspace
- **ENVIRONMENT-CONFIG.md** - Environment variables
- **MAKEFILE-GUIDE.md** - Make commands reference
- **HOOKS-SETUP.md** - Git hooks

### Component Documentation

- **backend/docs/** - Backend-specific docs
- **frontend/** - Frontend implementation docs

## Deployment

### Development

```bash
make -f project.mk dev-fullstack  # All-in-one development
```

### Production (Planned)

- Load balancer (nginx) with SSL/TLS + WebSocket proxy
- Container orchestration (Docker/Kubernetes)
- Database layer (Redis + PostgreSQL)
- Monitoring and observability platform

## Future Roadmap

### Short Term (3 months)

- Complete JWT authentication
- Docker containerization
- Real market data integration
- E2E test suite completion

### Medium Term (6 months)

- Cloud deployment (Kubernetes)
- Production monitoring
- Performance analytics
- Enhanced security measures

### Long Term (12+ months)

- Mobile application
- AI-powered trading insights
- Advanced charting features
- Multi-region deployment

## Success Metrics

✅ **Independent Development** - Parallel team workflows
✅ **Type Safety** - End-to-end type checking
✅ **Real-Time Ready** - WebSocket infrastructure complete
✅ **Test-Driven** - Comprehensive testing at all levels
✅ **DevOps Friendly** - Automated CI/CD pipelines
✅ **Developer Experience** - Zero-config setup with intelligent fallbacks
✅ **Production Ready** - Scalable architecture for deployment

---

**Maintained by**: Development Team
**Review Schedule**: Quarterly architecture reviews
