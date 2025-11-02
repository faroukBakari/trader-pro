# WebSocket Integration Methodology

**Version**: 4.0.0  
**Date**: October 30, 2025  
**Status**: ✅ Production Methodology (Modular Architecture)  
**Related**: `docs/WEBSOCKET-CLIENTS.md`, `ARCHITECTURE.md`  
**Architecture**: Modular backend with factory-based pattern

---

## Overview

This document describes the **proven methodology** for implementing WebSocket features in Trading Pro, following Test-Driven Development (TDD) principles. The approach has been successfully applied to datafeed (bars, quotes) and broker (orders, positions, executions, equity, connection) WebSocket implementations.

### Core Principles

1. **Incremental** - Each phase builds on previous working state
2. **Test-Driven** - Tests guide implementation at every phase
3. **Backend First** - Backend operations before frontend integration
4. **Type-Safe** - Full type alignment via AsyncAPI → TypeScript generation
5. **Pattern-Based** - Leverage proven `WsRouteService` Protocol and `WebSocketBase` singleton
6. **Reversible** - Can rollback to any working phase

---

## Six-Phase Implementation

### Phase Overview

```
Phase 1: Backend Operations → Backend tests pass ✅
Phase 2: Type Generation → Types compile ✅
Phase 3: Frontend Clients → Subscriptions work ✅
Phase 4: Service Integration → TDD Red 🔴
Phase 5: Broadcasting → TDD Green 🟢
Phase 6: Validation → E2E tests pass ✅
```

### Key TDD Flow

- **Red Phase (Phase 4)**: Frontend integration tests fail when backend doesn't broadcast
- **Green Phase (Phase 5)**: Tests pass after backend broadcasts events
- **Refactor (Phase 6)**: Optimize while keeping tests green

---

## Phase 1: Backend WebSocket Operations

**Goal**: Create WebSocket routers with subscription/update operations  
**Duration**: ~1 day  
**Owner**: Backend Team

### Step 1.1: Define Models

**Location**: `backend/src/trading_api/models/{domain}/`

Create Pydantic models in appropriate business domain folder:

- **Market data**: `models/market/` (e.g., `bars.py`, `quotes.py`)
- **Broker data**: `models/broker/` (e.g., `orders.py`, `positions.py`)

**Example (Datafeed Bars)**:

```python
# backend/src/trading_api/models/market/bars.py
from pydantic import BaseModel

class BarsSubscriptionRequest(BaseModel):
    """WebSocket subscription parameters"""
    symbol: str
    resolution: str  # "1", "5", "15", "60", "D"

class Bar(BaseModel):
    """OHLCV bar data"""
    time: int  # Unix timestamp (ms)
    open: float
    high: float
    low: float
    close: float
    volume: int
```

**Key Points**:

- Keep subscription requests simple (minimal required parameters)
- Reuse existing REST models for update payloads when possible
- Follow topic-based organization (business concepts, not API types)

### Step 1.2: Create Router Factory

**Location**: `backend/src/trading_api/modules/{module}/ws.py`

**Note**: Each module has its own `ws.py` file with TypeAlias declarations. Routers are generated into `modules/{module}/ws_generated/`.

Use the router factory pattern with TYPE_CHECKING:

```python
# backend/src/trading_api/modules/datafeed/ws.py
from typing import TYPE_CHECKING, TypeAlias
from trading_api.models.market import Bar, BarsSubscriptionRequest
from trading_api.shared.ws.router_interface import WsRouteInterface, WsRouteService
from trading_api.shared.ws.generic_route import WsRouter

if TYPE_CHECKING:
    # Type alias for type checkers
    BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
else:
    # Runtime: use generated concrete class from module-local ws_generated
    from .ws_generated import BarWsRouter

class DatafeedWsRouters(list[WsRouteInterface]):
    """Factory creating all datafeed WebSocket routers"""

    def __init__(self, datafeed_service: WsRouteService):
        bar_router = BarWsRouter(route="bars", tags=["datafeed"], service=datafeed_service)
        # Add more routers as needed
        super().__init__([bar_router])
```

**Key Points**:

- One router per business concept (bars, orders, positions, etc.)
- Group related routers in a factory class
- Pass service implementing `WsRouteService` Protocol

### Step 1.3: Start the App (Automatic Generation)

**No manual generation needed!** Routers automatically generate when you start the app:

```bash
cd backend
make dev
```

This triggers automatic router generation when each module's router factory is instantiated. The generator scans all `modules/*/ws.py` files for `TypeAlias = WsRouter[...]` patterns and generates concrete classes in `modules/{module}/ws_generated/` **before** they are imported.

**See**: `backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md` for complete generation guide and troubleshooting

### Step 1.4: Register Routers

**Location**: Module's `__init__.py` implements Module Protocol

**Note**: In modular architecture, routers are registered via the Module Protocol, not directly in main.py.

```python
# backend/src/trading_api/modules/datafeed/__init__.py
from typing import List
from fastapi import APIRouter
from trading_api.shared.ws.router_interface import WsRouteInterface
from .service import DatafeedService
from .api import DatafeedApi
from .ws import DatafeedWsRouters

class DatafeedModule:
    def __init__(self):
        self._service = None
        self._enabled = True

    @property
    def name(self) -> str:
        return "datafeed"

    @property
    def service(self):
        if self._service is None:
            self._service = DatafeedService()  # Lazy load
        return self._service

    def get_api_routers(self) -> List[APIRouter]:
        return [DatafeedApi(service=self.service, prefix=f"/{self.name}", tags=[self.name])]

    def get_ws_routers(self) -> List[WsRouteInterface]:
        return DatafeedWsRouters(self.service)

    def configure_app(self, api_app, ws_app) -> None:
        # Optional module-specific configuration
        pass
```

The application factory (`app_factory.py`) automatically registers all enabled modules' routers.

### Step 1.5: Write Backend Tests

**Location**: `backend/src/trading_api/modules/{module}/tests/test_ws.py`

**Note**: WebSocket tests are co-located with modules. Use factory-based fixtures with isolated module loading.

Test subscription/unsubscription flow:

```python
def test_subscribe_bars(client: TestClient):
    # client fixture from conftest.py creates app with only datafeed module
    # Uses: create_app(enabled_modules=["datafeed"])
    with client.websocket_connect("/api/v1/ws") as websocket:
        # Subscribe
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {"symbol": "AAPL", "resolution": "1"}
        })

        # Verify response
        response = websocket.receive_json()
        assert response["type"] == "bars.subscribe.response"
        assert response["payload"]["status"] == "ok"
        assert "bars:" in response["payload"]["topic"]
```

**Verification**:

```bash
cd backend
make test  # All WebSocket tests pass
make lint  # Code quality checks pass
```

**Phase 1 Complete**: ✅ Backend routing infrastructure functional

**What you have**:

- WebSocket routers accepting subscriptions
- Subscription/unsubscription responses working
- Topics being created/removed correctly
- Service implementing `WsRouteService` Protocol
- `create_topic()` receiving `topic_update` callback
- `remove_topic()` cleaning up resources

---

## Phase 2: Frontend Type Generation

**Goal**: Generate TypeScript types from AsyncAPI spec  
**Duration**: < 1 hour (automated)  
**Owner**: Frontend Team

### Step 2.1: Generate Types

Ensure backend is running, then generate types:

```bash
# Start backend (exports AsyncAPI spec)
cd backend && make dev

# Generate TypeScript types (separate terminal)
cd frontend && make generate-asyncapi-types
```

**Output**: Types in `frontend/src/clients/ws-types-generated/`

- `BarsSubscriptionRequest`
- `Bar_backend` (suffixed to avoid conflicts)
- Enumerations and interfaces

### Step 2.2: Create Mappers

**Location**: `frontend/src/plugins/mappers.ts`

**⚠️ CRITICAL - Strict Naming Convention**:

```typescript
// Backend types: {TYPE}_{Source}_Backend
import type { Bar as Bar_Ws_Backend } from "@clients/ws-types-generated";
import type { QuoteData as QuoteData_Api_Backend } from "@clients/trader-client-generated";

// Frontend types: {TYPE} (no suffix)
import type { Bar, QuoteData } from "@public/trading_terminal/charting_library";

// Mapper function
export function mapBar(bar: Bar_Ws_Backend): Bar {
  return {
    time: bar.time,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume ?? 0,
  };
}
```

**Verification**:

```bash
cd frontend
make type-check  # Types compile
make lint        # No errors
```

**Phase 2 Complete**: ✅ Types generated and mappers created

---

## Phase 3: Extend WsAdapter

**Goal**: Add WebSocket clients to centralized adapter  
**Duration**: ~2 hours  
**Owner**: Frontend Team

### Step 3.1: Add Clients to WsAdapter

**Location**: `frontend/src/plugins/wsAdapter.ts`

```typescript
import { WebSocketClient } from "./wsClientBase";
import { mapBar } from "./mappers";
import type {
  BarsSubscriptionRequest,
  Bar_Ws_Backend,
} from "@clients/ws-types-generated";
import type { Bar } from "@public/trading_terminal/charting_library";

export class WsAdapter {
  // Add new client
  bars: WebSocketClient<BarsSubscriptionRequest, Bar_Ws_Backend, Bar>;

  constructor() {
    this.bars = new WebSocketClient("bars", mapBar);
  }
}
```

### Step 3.2: Add Mock Support (Optional)

**Location**: `frontend/src/plugins/wsAdapter.ts`

```typescript
export class WsFallback implements Partial<WsAdapterType> {
  constructor({
    barsMocker,
  }: {
    barsMocker?: () => Bar | null;
  } = {}) {
    if (barsMocker) {
      this.bars = new WebSocketFallback<BarsSubscriptionRequest, Bar>(
        barsMocker
      );
    }
  }
}
```

**Verification**:

```bash
cd frontend
make type-check  # Types compile
make test        # Mock tests pass
```

**Phase 3 Complete**: ✅ WebSocket clients ready for use

---

## Phase 4: Service Integration (TDD Red)

**Goal**: Wire WebSocket to application services, write failing tests  
**Duration**: ~1 day  
**Owner**: Frontend Team

### Step 4.1: Setup WebSocket Integration

**Example (DatafeedService)**:

```typescript
// frontend/src/services/datafeedService.ts
import { WsAdapter } from "@/plugins/wsAdapter";
import type { Bar } from "@public/trading_terminal/charting_library";

export class DatafeedService {
  private readonly _wsAdapter: WsAdapter;

  constructor() {
    this._wsAdapter = new WsAdapter();
  }

  subscribeBars(
    listenerGuid: string,
    symbol: string,
    resolution: string,
    callback: (bar: Bar) => void
  ): void {
    // Subscribe with per-subscription callback
    // Each subscription gets its own callback handler
    this._wsAdapter.bars.subscribe(
      listenerGuid,
      { symbol, resolution },
      callback
    );
  }

  unsubscribeBars(listenerGuid: string): void {
    this._wsAdapter.bars.unsubscribe(listenerGuid);
  }
}
```

### Step 4.2: Write Integration Tests

**Location**: `frontend/src/services/__tests__/{service}.spec.ts`

```typescript
describe("DatafeedService - WebSocket Integration", () => {
  it("should receive bar updates after subscribing", async () => {
    const service = new DatafeedService();
    const bars: Bar[] = [];

    service.subscribeBars("test-guid", "AAPL", "1", (bar) => {
      bars.push(bar);
    });

    // Wait for update
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // ❌ FAILS if backend not broadcasting
    expect(bars.length).toBeGreaterThan(0);
  });
});
```

**Run Tests**:

```bash
cd frontend
make test  # Tests FAIL (expected - TDD Red phase)
```

**Phase 4 Complete**: ✅ Integration wired, tests failing (TDD Red) 🔴

---

## Phase 5: Backend Broadcasting (TDD Green)

**Goal**: Implement broadcasting to make tests pass  
**Duration**: ~2 days  
**Owner**: Backend Team

**Critical Understanding**:
The `WsRouter` passes a `topic_update` callback to your service's `create_topic()` method. Your service's background tasks should call this callback with data updates. The router handles the actual WebSocket broadcasting - your service just needs to call the callback.

### Step 5.1: Implement WsRouteService Protocol

**Location**: `backend/src/trading_api/modules/{module}/service.py`

**Note**: Service implements `WsRouteService` Protocol from `shared.ws.router_interface`.

**Example (DatafeedService)**:

```python
# backend/src/trading_api/modules/datafeed/service.py
import asyncio
import json
from typing import Callable
from trading_api.models.market import Bar, BarsSubscriptionRequest
from trading_api.shared.ws.router_interface import WsRouteService

class DatafeedService(WsRouteService):
    """Datafeed service implementing WsRouteService Protocol"""

    def __init__(self):
        self._topic_generators: dict[str, asyncio.Task] = {}

    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Start generator task for topic

        Args:
            topic: Topic string in format "bars:{json_params}"
            topic_update: Callback function to broadcast updates
        """
        if topic not in self._topic_generators:
            # Parse topic format: "topic_type:{json_params}"
            if ":" not in topic:
                raise ValueError(f"Invalid topic format: {topic}")

            topic_type, params_json = topic.split(":", 1)

            if topic_type == "bars":
                # Parse and validate subscription parameters
                params_dict = json.loads(params_json)
                subscription_request = BarsSubscriptionRequest.model_validate(params_dict)

                # Create generator task with the topic_update callback
                task = asyncio.create_task(
                    self._bar_generator(subscription_request.symbol, topic_update)
                )
                self._topic_generators[topic] = task

    def remove_topic(self, topic: str) -> None:
        """Stop generator task for topic"""
        task = self._topic_generators.get(topic)
        if task:
            task.cancel()
        self._topic_generators.pop(topic, None)

    async def _bar_generator(self, symbol: str, topic_update: Callable[[Bar], None]) -> None:
        """Generate and broadcast bar data

        Args:
            symbol: Symbol to generate bars for
            topic_update: Callback to publish bar updates
        """
        while True:
            # Generate mock bar data
            bar = self.mock_last_bar(symbol)

            # Broadcast to subscribers via callback
            if bar:
                topic_update(bar)

            # Wait before next update
            await asyncio.sleep(0.2)
```

**Key Points**:

- Service manages its own `_topic_generators` dict
- `create_topic()` receives a `topic_update` callback from the router
- Background task calls `topic_update(data)` to broadcast updates
- `remove_topic()` cancels task and cleans up
- No separate `publish()` method needed - use the callback directly

### Step 5.2: Verify Broadcasting

**Run Tests**:

```bash
# Backend tests
cd backend && make test  # All pass

# Frontend tests
cd frontend && make test  # Now PASS! ✅
```

**Phase 5 Complete**: ✅ Broadcasting working, tests pass (TDD Green) ��

---

## Phase 6: Full Stack Validation

**Goal**: End-to-end testing and optimization  
**Duration**: ~1 day  
**Owner**: Full Team

### Step 6.1: Manual Testing

```bash
# Start full stack
make -f project.mk dev-fullstack

# Test scenarios:
# - Subscribe to data → Updates appear
# - Multiple subscriptions → All receive updates
# - Unsubscribe → Updates stop
# - Reconnect → Auto-resubscription works
```

### Step 6.2: Performance Testing

- Verify latency < 100ms (backend → frontend)
- Test with multiple concurrent subscriptions
- Validate reconnection behavior
- Check memory usage over time

### Step 6.3: Smoke Tests

**Location**: `smoke-tests/tests/{feature}.spec.ts`

```typescript
test("bars WebSocket updates", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Subscribe to bars
  await page.click('[data-testid="subscribe-bars"]');

  // Verify updates appear
  await expect(page.locator('[data-testid="bar-data"]')).toBeVisible();
});
```

**Phase 6 Complete**: ✅ Production ready

---

## Success Criteria

### Per-Phase Validation

- **Phase 1**: Backend tests pass, routers registered, AsyncAPI spec updated
- **Phase 2**: Types compile without errors, mappers handle all fields
- **Phase 3**: Can subscribe/unsubscribe, mock data works offline
- **Phase 4**: Integration tests fail (TDD Red), all code compiles
- **Phase 5**: All tests pass (TDD Green), real-time updates work
- **Phase 6**: E2E tests pass, performance metrics met

### Overall Metrics

- ⏱️ **Latency**: < 100ms from backend broadcast to frontend callback
- 🔄 **Reliability**: Auto-reconnection success rate > 99%
- 🛡️ **Type Safety**: Zero runtime type errors
- 📊 **Test Coverage**: > 80% for WebSocket code
- ✅ **Quality Gates**: All lint, format, type-check pass

---

## Implementation Checklist Template

Use this checklist when implementing new WebSocket features:

```markdown
## Phase 1: Backend Operations

- [ ] Models defined in `models/{domain}/`
- [ ] Router factory created in `ws/{domain}.py`
- [ ] Routers auto-generated (via `make dev`)
- [ ] Routers registered in `main.py`
- [ ] Backend tests written and passing
- [ ] AsyncAPI spec includes operations

## Phase 2: Type Generation

- [ ] AsyncAPI types generated
- [ ] Mappers created with strict naming
- [ ] Types compile without errors

## Phase 3: Frontend Clients

- [ ] Clients added to WsAdapter
- [ ] Mock support added to WsFallback
- [ ] Frontend types compile

## Phase 4: Integration (TDD Red)

- [ ] Service handlers setup
- [ ] Integration tests written
- [ ] Tests fail as expected (no broadcasting yet)

## Phase 5: Broadcasting (TDD Green)

- [ ] Service implements WsRouteService Protocol
- [ ] create_topic/remove_topic implemented
- [ ] Broadcasting logic working
- [ ] All tests pass

## Phase 6: Validation

- [ ] Manual testing complete
- [ ] Performance validated
- [ ] Smoke tests added
- [ ] Documentation updated
```

---

## Reference Examples

### Completed Implementations

#### Datafeed Module (Market Data)

- **Location**: `backend/src/trading_api/modules/datafeed/`
- **Routers**: `ws.py` - bars, quotes TypeAlias declarations
- **Generated**: `ws_generated/` - BarWsRouter, QuoteWsRouter concrete classes
- **Service**: `service.py` - DatafeedService implements WsRouteService
- **Tests**: `tests/test_ws.py` - Module-specific WebSocket tests
- **Status**: ✅ Production ready

#### Broker Module (Trading Operations)

- **Location**: `backend/src/trading_api/modules/broker/`
- **Routers**: `ws.py` - orders, positions, executions, equity, connection TypeAlias declarations
- **Generated**: `ws_generated/` - OrderWsRouter, PositionWsRouter, etc. concrete classes
- **Service**: `service.py` - BrokerService (routing complete, broadcasting pending)
- **Tests**: `tests/test_ws.py` - Module-specific WebSocket tests
- **Status**: 🔄 Phase 4 complete, Phase 5 pending

### Key Files

- **Modular Router Generation**: `backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md`
- **Frontend Client Pattern**: `frontend/WEBSOCKET-CLIENT-PATTERN.md`
- **Frontend Client Base**: `frontend/WEBSOCKET-CLIENT-BASE.md`
- **System Architecture**: `ARCHITECTURE.md`
- **Module Protocol**: `backend/src/trading_api/shared/module_interface.py`
- **Application Factory**: `backend/src/trading_api/app_factory.py`

---

## Troubleshooting

### Common Issues

**Types don't compile**

- Ensure backend is running when generating types
- Check strict naming conventions in mappers
- Verify AsyncAPI spec is up to date

**Routers not generated**

- Routers auto-generate on app startup via `make dev`
- Check `modules/{module}/ws.py` has valid `TypeAlias` declarations
- Verify generation output for errors
- Review `backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md` for details

**No updates received**

- Verify backend broadcasting is implemented (Phase 5)
- Check topic builder algorithm matches backend/frontend
- Confirm subscription confirmation received

**Connection drops**

- Check WebSocketBase singleton connection
- Verify auto-reconnection logic
- Review browser console for errors

**Tests fail unexpectedly**

- Ensure backend is running for integration tests
- Check test timeouts are sufficient
- Verify mock data generators work

---

**Version**: 4.0.0 (Modular Architecture)  
**Last Updated**: October 30, 2025  
**Maintained by**: Development Team  
**Migration**: Updated for modular backend architecture with factory pattern
