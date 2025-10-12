# FastWS Bar Subscription Implementation - Validation Report

**Date**: October 12, 2025  
**Branch**: server-side-broker  
**Type**: New Feature - Real-time Bar Streaming

## Overview

This document validates the proposed backend-first plan to stand up a FastWS bar subscription endpoint with a dedicated plugin adapter for real-time market data streaming.

## Executive Summary

✅ **APPROVED** - The proposed approach is sound and aligns with existing architecture patterns. All necessary resources are available, and the plan follows established TDD workflow and project guidelines.

## Validation Summary

### ✅ Strengths

1. **Existing FastWS Service**: The `external_packages/fastws/service.py` is fully implemented and ready to use
2. **Existing Models**: `Bar` model already exists in `models/market/bars.py` 
3. **Existing DatafeedService**: `core/datafeed_service.py` with `mock_last_bar()` method is available
4. **Clear Structure**: Plugin directory exists and is ready for new adapters
5. **TDD Infrastructure**: pytest + httpx AsyncClient pattern is established
6. **Documentation Standards**: ARCHITECTURE.md, README.md patterns are well-defined

### ⚠️ Adjustments Needed

1. **Adapter Location**: Use `src/trading_api/adapters/` instead of `src/adapters/`
2. **Service Location**: Place in `core/realtime/` (directory exists but is empty)
3. **Model Organization**: Follow existing `models/market/` pattern for new bar models
4. **WebSocket Route**: Add to `api/` directory following existing patterns

## Detailed Validation

### 1. FastWS Service Analysis

**Location**: `backend/external_packages/fastws/service.py`

**Capabilities**:
```python
class FastWS:
    - @send decorator for registering message handlers
    - Heartbeat support (configurable interval)
    - Client connection management
    - Automatic JSON message parsing
    - Pydantic payload validation
    - Background task support
    - Disconnect callbacks
    - AsyncAPI schema generation
```

**Assessment**: ✅ Fully functional and production-ready

**Key Features for Bar Streaming**:
- Message-based protocol with type/payload structure
- Automatic Pydantic model validation
- Client state management for tracking subscriptions
- Background task support (ideal for streaming)
- Proper lifecycle management (cleanup on disconnect)

### 2. Existing Models Review

**Bar Model** (`models/market/bars.py`):
```python
class Bar(BaseModel):
    time: int       # Milliseconds since epoch
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int]
```

**Assessment**: ✅ Perfect for real-time updates, matches TradingView interface

**Other Relevant Models**:
- `SymbolInfo` - Available for symbol validation
- `DatafeedConfiguration` - Configuration metadata
- All models follow Pydantic pattern

### 3. DatafeedService Analysis

**Location**: `backend/src/trading_api/core/datafeed_service.py`

**Key Method for Streaming**:
```python
def mock_last_bar(self, symbol: str) -> Optional[Bar]:
    """Create a mock bar by modifying the last bar to simulate real-time updates"""
    # Returns Bar with time-based variations
    # Uses deterministic random for testing
```

**Assessment**: ✅ Ideal foundation for real-time bar generation

**Additional Resources**:
- `_sample_bars`: 400 days of historical bars
- `resolve_symbol()`: Symbol validation
- Deterministic random generation (testable)

### 4. Directory Structure Validation

**Current Structure**:
```
backend/src/trading_api/
├── api/                    # REST endpoints (health, datafeed, versions)
├── core/                   # Business logic
│   ├── datafeed_service.py
│   ├── versioning.py
│   └── realtime/           # ✅ EXISTS BUT EMPTY - ready for bars_service.py
├── models/                 # Pydantic models
│   ├── common.py
│   └── market/             # ✅ Perfect location for realtime_bars.py
│       ├── bars.py
│       ├── configuration.py
│       ├── instruments.py
│       ├── quotes.py
│       └── search.py
├── plugins/                # ✅ EMPTY - ready for future use
└── main.py                 # FastAPI app
```

**Recommended Structure**:
```
backend/src/trading_api/
├── adapters/               # ⚡ NEW - adapter layer
│   └── fastws_adapter.py   # FastWS wrapper
├── api/
│   ├── datafeed.py
│   ├── health.py
│   ├── versions.py
│   └── websocket.py        # ⚡ NEW - WebSocket endpoint
├── core/
│   ├── datafeed_service.py
│   ├── versioning.py
│   └── realtime/
│       ├── bars_service.py # ⚡ NEW - Bar streaming logic
│       └── ws_service.py   # ⚡ NEW - FastWS setup & handlers
└── models/
    └── market/
        ├── bars.py
        └── realtime_bars.py # ⚡ NEW - Subscription models
```

**Assessment**: ✅ Clean separation of concerns, follows existing patterns

### 5. Testing Infrastructure

**Current Pattern** (from `test_health.py`, `test_versioning.py`):
```python
import pytest
from httpx import AsyncClient
from trading_api.main import app

@pytest.mark.asyncio
async def test_endpoint() -> None:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    assert response.status_code == 200
```

**Assessment**: ✅ Perfect for testing WebSocket endpoints

**For WebSocket Testing**:
```python
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

async def test_bars_subscription():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws") as websocket:
        # Send subscription
        websocket.send_json({"type": "bars.subscribe", "payload": {...}})
        
        # Receive ack
        ack = websocket.receive_json()
        assert ack["type"] == "bars.ack"
        
        # Receive update
        update = websocket.receive_json()
        assert update["type"] == "bars.update"
```

**Dependencies**: Already available in `pyproject.toml`
- `pytest`
- `pytest-asyncio`
- `httpx`

### 6. Main Application Integration

**Current `main.py` Pattern**:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    validate_response_models(app)
    # ... OpenAPI generation
    yield
    # Shutdown (if needed)

app = FastAPI(lifespan=lifespan)
app.include_router(health_router, prefix="/api/v1", tags=["v1"])
app.include_router(versions_router, prefix="/api/v1", tags=["v1"])
app.include_router(datafeed_router, prefix="/api/v1", tags=["v1"])
```

**Assessment**: ✅ Perfect place for FastWS setup

**Proposed Addition**:
```python
from trading_api.core.realtime.ws_service import fastws_service

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    validate_response_models(app)
    fastws_service.setup(app)  # ⚡ NEW
    # ... existing code
    yield

# Add WebSocket endpoint
from trading_api.api.websocket import router as ws_router
app.include_router(ws_router, prefix="/api/v1", tags=["v1"])
```

### 7. TradingView Compatibility

**From `frontend/public/trading_terminal/datafeed-api.d.ts`**:

```typescript
export interface Bar {
    time: number;     // milliseconds
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}
```

**Assessment**: ✅ Our `Bar` model matches perfectly

**Real-time Data Flow**:
```
Frontend                    Backend
   |                           |
   |-- bars.subscribe -------->|
   |<----- bars.ack -----------|
   |                           |
   |<---- bars.update ---------|  (periodic)
   |<---- bars.update ---------|
   |<---- bars.update ---------|
```

### 8. Dependencies Check

**Current `pyproject.toml`**:
```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.1"           # ✅ WebSocket support
uvicorn = {extras = ["standard"], version = "^0.24.0"}  # ✅ ASGI server
pyyaml = "^6.0.1"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"              # ✅ Testing
pytest-asyncio = "^0.21.1"     # ✅ Async testing
httpx = "^0.25.2"              # ✅ Test client
```

**Assessment**: ✅ All required dependencies are already installed

**No New Dependencies Needed**:
- FastWS is in `external_packages/` (no pip install)
- FastAPI has built-in WebSocket support
- All testing libraries are present

### 9. Documentation Standards

**Existing Documentation**:
- ✅ `ARCHITECTURE.md` - Comprehensive system overview
- ✅ `backend/README.md` - API surface and setup
- ✅ `MAKEFILE-GUIDE.md` - Build system reference
- ✅ `TESTING-INDEPENDENCE.md` - Testing patterns

**Required Updates**:
1. **ARCHITECTURE.md**:
   - Update "Real-Time Architecture (Planned)" to "Real-Time Architecture"
   - Document WebSocket channel structure
   - Add bars subscription flow diagram

2. **backend/README.md**:
   - Add WebSocket endpoint to API surface table
   - Document subscription payload format
   - Add `make test-ws` command (if created)

3. **New Documentation** (optional):
   - `backend/docs/websocket.md` - WebSocket API guide
   - `backend/examples/websocket-client.md` - Client usage examples

### 10. Git Workflow Validation

**Current Branch**: `server-side-broker`

**Commit History Pattern** (from existing work):
```
refactor: reorganize models into dedicated package
- Move models from core/ to models/ directory
- Create unified models/__init__.py
- Update all import statements
```

**Assessment**: ✅ Follows conventional commits pattern

**Recommended Commit Pattern**:
```
feat(websocket): add FastWS adapter and bar subscription endpoint

- Add FastWS adapter wrapper in adapters/fastws_adapter.py
- Create realtime bar models (BarSubscriptionRequest, BarUpdateMessage)
- Implement bars_service with async generator
- Add WebSocket endpoint at /api/v1/ws
- Register bars.subscribe handler with FastWS
- Add comprehensive WebSocket tests
- Update ARCHITECTURE.md with WebSocket documentation

BREAKING CHANGE: New WebSocket endpoint requires client updates

Tests: All tests pass, WebSocket subscription tested
```

## Plan Validation Details

### ✅ Component 1: FastWS Adapter

**Proposed**: `src/adapters/fastws_adapter.py`  
**Corrected**: `src/trading_api/adapters/fastws_adapter.py`

**Responsibilities**:
```python
# Shared FastWS instance
fastws_service = FastWS(heartbeat_interval=30.0)

# Base models
class BaseSubscriptionPayload(BaseModel):
    pass  # Empty base, extended by specific subscriptions

class SubscriptionAck(BaseModel):
    status: str
    message: str

# Helper functions
def register_subscription_handler(...)
def track_background_task(client: Client, task_id: str, task: asyncio.Task)
def cancel_client_tasks(client: Client)
```

**Assessment**: ✅ Clean abstraction, reusable for future subscriptions

**Potential Enhancement**:
```python
# Generic subscription decorator
def fastws_subscription(
    message_type: str,
    *,
    reply: str,
    update_type: str
) -> Callable:
    """Decorator for registering subscription handlers"""
    def decorator(func: HandlerType) -> HandlerType:
        @fastws_service.send(message_type, reply=reply)
        async def wrapper(payload: BaseModel, client: Client):
            # Validate, start task, track in client.state
            result = await func(payload, client)
            return result
        return wrapper
    return decorator
```

### ✅ Component 2: Realtime Bar Models

**Proposed**: `models/realtime_bars.py`  
**Corrected**: `models/market/realtime_bars.py`

**Models**:
```python
from ..common import ErrorResponse
from .bars import Bar

class BarSubscriptionRequest(BaseModel):
    """Subscription request for real-time bars"""
    symbol: str = Field(..., description="Symbol to subscribe")
    resolution: str = Field(default="1D", description="Bar resolution")

class BarUpdateMessage(BaseModel):
    """Real-time bar update message"""
    symbol: str
    resolution: str
    bar: Bar
    timestamp: int  # Message timestamp

class BarSubscriptionAck(BaseModel):
    """Acknowledgment for bar subscription"""
    status: str = Field(default="ok")
    symbol: str
    resolution: str
    message: str = Field(default="Subscription successful")
```

**Assessment**: ✅ Follows existing model patterns, extends base `Bar`

**Export Update Required**:
```python
# models/market/__init__.py
from .realtime_bars import (
    BarSubscriptionRequest,
    BarUpdateMessage,
    BarSubscriptionAck,
)

__all__ = [
    # ... existing exports
    "BarSubscriptionRequest",
    "BarUpdateMessage",
    "BarSubscriptionAck",
]
```

### ✅ Component 3: Realtime Bars Service

**Proposed**: `core/realtime/bars_service.py`

**Implementation Sketch**:
```python
import asyncio
from typing import AsyncGenerator
from ...models import Bar, BarSubscriptionRequest
from ..datafeed_service import DatafeedService

class BarsStreamService:
    """Service for streaming real-time bar updates"""
    
    def __init__(self, datafeed_service: DatafeedService):
        self.datafeed_service = datafeed_service
        
    async def stream_bars(
        self,
        request: BarSubscriptionRequest,
        interval: float = 1.0
    ) -> AsyncGenerator[Bar, None]:
        """Generate real-time bar updates"""
        while True:
            bar = self.datafeed_service.mock_last_bar(request.symbol)
            if bar:
                yield bar
            await asyncio.sleep(interval)
            
    async def start_subscription(
        self,
        request: BarSubscriptionRequest,
        client: Client,
        send_callback: Callable
    ) -> asyncio.Task:
        """Start a background subscription task"""
        
        async def _stream_task():
            async for bar in self.stream_bars(request):
                await send_callback(
                    "bars.update",
                    {
                        "symbol": request.symbol,
                        "resolution": request.resolution,
                        "bar": bar.model_dump(),
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    }
                )
        
        task = asyncio.create_task(_stream_task())
        return task
```

**Assessment**: ✅ Async generator pattern is ideal for streaming

### ✅ Component 4: WebSocket Service

**Proposed**: `core/realtime/ws_service.py`

**Implementation Sketch**:
```python
from ...adapters.fastws_adapter import fastws_service, Client
from ...models import (
    BarSubscriptionRequest,
    BarSubscriptionAck,
    BarUpdateMessage,
)
from .bars_service import BarsStreamService
from ..datafeed_service import DatafeedService

# Initialize services
datafeed_service = DatafeedService()
bars_service = BarsStreamService(datafeed_service)

@fastws_service.send("bars.subscribe", reply="bars.ack")
async def handle_bars_subscription(
    payload: BarSubscriptionRequest,
    client: Client
) -> BarSubscriptionAck:
    """Handle bar subscription requests"""
    
    # Validate symbol
    symbol_info = datafeed_service.resolve_symbol(payload.symbol)
    if not symbol_info:
        return BarSubscriptionAck(
            status="error",
            symbol=payload.symbol,
            resolution=payload.resolution,
            message=f"Symbol {payload.symbol} not found"
        )
    
    # Start streaming task
    task = await bars_service.start_subscription(
        payload,
        client,
        send_callback=client.send
    )
    
    # Track task for cleanup
    if "subscription_tasks" not in client.state:
        client.state["subscription_tasks"] = {}
    client.state["subscription_tasks"][payload.symbol] = task
    
    # Return acknowledgment
    return BarSubscriptionAck(
        status="ok",
        symbol=payload.symbol,
        resolution=payload.resolution,
        message=f"Subscribed to {payload.symbol} bars"
    )

# Cleanup on disconnect
def cleanup_subscriptions(client: Client):
    """Cancel all subscription tasks on disconnect"""
    tasks = client.state.get("subscription_tasks", {})
    for task in tasks.values():
        task.cancel()
```

**Assessment**: ✅ Clean handler pattern, proper lifecycle management

### ✅ Component 5: WebSocket Endpoint

**Proposed**: `api/websocket.py`

**Implementation Sketch**:
```python
from fastapi import APIRouter, WebSocket
from ..core.realtime.ws_service import fastws_service

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data streaming"""
    client = await fastws_service.manage(websocket)
    await fastws_service.serve(client)
```

**Assessment**: ✅ Minimal, delegates to FastWS service

**Main.py Integration**:
```python
from trading_api.api.websocket import router as ws_router

app.include_router(ws_router, prefix="/api/v1", tags=["v1", "websocket"])
```

### ✅ Component 6: Testing Strategy

**Test File**: `tests/test_websocket_bars.py`

**Test Cases**:
```python
import pytest
import asyncio
from starlette.testclient import TestClient
from trading_api.main import app

@pytest.mark.asyncio
async def test_bars_subscription_success():
    """Test successful bar subscription flow"""
    client = TestClient(app)
    
    with client.websocket_connect("/api/v1/ws") as websocket:
        # Subscribe
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {
                "symbol": "AAPL",
                "resolution": "1D"
            }
        })
        
        # Receive ack
        ack = websocket.receive_json()
        assert ack["type"] == "bars.ack"
        assert ack["payload"]["status"] == "ok"
        assert ack["payload"]["symbol"] == "AAPL"
        
        # Receive at least one update
        update = websocket.receive_json()
        assert update["type"] == "bars.update"
        assert "bar" in update["payload"]
        
        bar = update["payload"]["bar"]
        assert "time" in bar
        assert "open" in bar
        assert "high" in bar
        assert "low" in bar
        assert "close" in bar

@pytest.mark.asyncio
async def test_bars_subscription_invalid_symbol():
    """Test subscription with invalid symbol"""
    client = TestClient(app)
    
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {
                "symbol": "INVALID",
                "resolution": "1D"
            }
        })
        
        ack = websocket.receive_json()
        assert ack["type"] == "bars.ack"
        assert ack["payload"]["status"] == "error"

@pytest.mark.asyncio
async def test_subscription_cleanup_on_disconnect():
    """Test that tasks are cancelled on disconnect"""
    # Implementation to verify no lingering tasks
    pass
```

**Additional Tests**:
- Multiple simultaneous subscriptions
- Reconnection handling
- Heartbeat functionality
- Error handling

**Assessment**: ✅ Comprehensive test coverage, follows TDD

## Implementation Plan with TDD Workflow

### Phase 1: Setup & Infrastructure (TDD)

1. **Create Test File First**
   ```bash
   touch backend/tests/test_websocket_bars.py
   ```

2. **Write Failing Test**
   ```python
   def test_websocket_endpoint_exists():
       """Test that /api/v1/ws endpoint exists"""
       # This will fail initially
   ```

3. **Run Test & Watch Fail**
   ```bash
   cd backend
   make test
   ```

4. **Create Minimal Adapter**
   ```bash
   mkdir -p src/trading_api/adapters
   touch src/trading_api/adapters/__init__.py
   touch src/trading_api/adapters/fastws_adapter.py
   ```

5. **Implement FastWS Adapter**
   - Wrap `external_packages.fastws`
   - Export shared `fastws_service` instance
   - Add base models

6. **Run Test Until Pass**

### Phase 2: Models (TDD)

1. **Write Failing Test**
   ```python
   def test_bar_subscription_request_validation():
       """Test BarSubscriptionRequest model validation"""
   ```

2. **Create Model File**
   ```bash
   touch src/trading_api/models/market/realtime_bars.py
   ```

3. **Implement Models**
   - `BarSubscriptionRequest`
   - `BarUpdateMessage`
   - `BarSubscriptionAck`

4. **Update `models/market/__init__.py`**

5. **Run Test Until Pass**

### Phase 3: Bars Service (TDD)

1. **Write Failing Test**
   ```python
   @pytest.mark.asyncio
   async def test_bars_stream_generates_bars():
       """Test that stream_bars yields bar updates"""
   ```

2. **Create Service File**
   ```bash
   touch src/trading_api/core/realtime/bars_service.py
   ```

3. **Implement `BarsStreamService`**
   - Async generator `stream_bars()`
   - Task management `start_subscription()`

4. **Run Test Until Pass**

### Phase 4: WebSocket Service (TDD)

1. **Write Failing Test**
   ```python
   @pytest.mark.asyncio
   async def test_bars_subscription_handler():
       """Test bars.subscribe handler registration"""
   ```

2. **Create WS Service File**
   ```bash
   touch src/trading_api/core/realtime/ws_service.py
   ```

3. **Implement Handler**
   - Register `@fastws_service.send("bars.subscribe")`
   - Integrate `bars_service`
   - Add cleanup logic

4. **Run Test Until Pass**

### Phase 5: Endpoint Integration (TDD)

1. **Write Failing Test**
   ```python
   @pytest.mark.asyncio
   async def test_websocket_endpoint_connection():
       """Test WebSocket connection to /api/v1/ws"""
   ```

2. **Create Endpoint File**
   ```bash
   touch src/trading_api/api/websocket.py
   ```

3. **Implement Endpoint**
   - Create FastAPI router
   - Add WebSocket route
   - Integrate with `fastws_service`

4. **Update `main.py`**
   - Import router
   - Add to app
   - Setup in lifespan

5. **Run Test Until Pass**

### Phase 6: End-to-End Testing (TDD)

1. **Write E2E Test**
   ```python
   @pytest.mark.asyncio
   async def test_full_bar_subscription_flow():
       """Test complete subscription from connect to updates"""
   ```

2. **Run All Tests**
   ```bash
   make test
   ```

3. **Iterate Until All Pass**

### Phase 7: Documentation

1. **Update ARCHITECTURE.md**
   - Real-Time Architecture section
   - WebSocket flow diagram
   - Component descriptions

2. **Update backend/README.md**
   - Add `/api/v1/ws` to API surface table
   - Document subscription messages
   - Add examples

3. **Create WebSocket Guide**
   ```bash
   touch backend/docs/websocket.md
   ```

4. **Add Client Examples**
   ```bash
   touch backend/examples/websocket-client.md
   ```

### Phase 8: Validation & Cleanup

1. **Run Full Test Suite**
   ```bash
   make test-cov
   ```

2. **Run Linters**
   ```bash
   make lint-check
   ```

3. **Clean Up Code**
   - Remove unused imports
   - Remove debug prints
   - Format with black/isort

4. **Manual Testing**
   ```bash
   # Terminal 1
   make dev
   
   # Terminal 2
   # Use wscat or Python websocket client
   ```

## Potential Enhancements

### 1. Multiple Resolution Support

```python
class BarSubscriptionRequest(BaseModel):
    symbol: str
    resolution: str = Field(default="1D", regex=r"^(1|5|15|30|60|D|W|M)$")
```

### 2. Unsubscribe Functionality

```python
@fastws_service.send("bars.unsubscribe", reply="bars.unsubscribe.ack")
async def handle_bars_unsubscribe(
    payload: BarUnsubscribeRequest,
    client: Client
):
    """Cancel a specific subscription"""
    tasks = client.state.get("subscription_tasks", {})
    if payload.symbol in tasks:
        tasks[payload.symbol].cancel()
        del tasks[payload.symbol]
```

### 3. Heartbeat Messages

```python
@fastws_service.send("ping", reply="pong")
async def handle_ping():
    """Heartbeat handler"""
    return {"timestamp": int(datetime.now().timestamp() * 1000)}
```

### 4. Error Recovery

```python
# In bars_service
async def _stream_task():
    try:
        async for bar in self.stream_bars(request):
            await send_callback(...)
    except Exception as e:
        await send_callback("bars.error", {
            "symbol": request.symbol,
            "error": str(e)
        })
```

### 5. Rate Limiting

```python
class BarsStreamService:
    def __init__(self, datafeed_service, max_rate: float = 10.0):
        self.max_rate = max_rate  # Max updates per second
        self.min_interval = 1.0 / max_rate
```

### 6. Subscription Limits

```python
MAX_SUBSCRIPTIONS_PER_CLIENT = 10

async def handle_bars_subscription(...):
    tasks = client.state.get("subscription_tasks", {})
    if len(tasks) >= MAX_SUBSCRIPTIONS_PER_CLIENT:
        return BarSubscriptionAck(
            status="error",
            message="Maximum subscriptions reached"
        )
```

## Risk Assessment

### Low Risk ✅

1. **Technology**: FastWS is already implemented and tested
2. **Dependencies**: All libraries are already in `pyproject.toml`
3. **Patterns**: Following established TDD and architectural patterns
4. **Testing**: Comprehensive test infrastructure exists

### Medium Risk ⚠️

1. **WebSocket Connection Management**: Need to test with multiple concurrent clients
2. **Task Cleanup**: Ensure no resource leaks on disconnect
3. **Error Handling**: Graceful degradation on stream errors

**Mitigation**: Thorough testing with multiple clients, load testing

### Low Risk (Minimal) 🟢

1. **Breaking Changes**: New endpoint, no existing contracts affected
2. **Performance**: Mock data generation is lightweight
3. **Backward Compatibility**: Additive change only

## Timeline Estimate

Based on TDD workflow:

| Phase | Tasks | Est. Time | Status |
|-------|-------|-----------|--------|
| 1. Setup | Adapter, tests | 1-2 hours | Not Started |
| 2. Models | Pydantic models | 30 min | Not Started |
| 3. Service | Bar streaming | 1-2 hours | Not Started |
| 4. WS Service | Handler registration | 1 hour | Not Started |
| 5. Endpoint | FastAPI integration | 30 min | Not Started |
| 6. E2E Tests | Full flow testing | 1-2 hours | Not Started |
| 7. Documentation | Docs, examples | 1-2 hours | Not Started |
| 8. Validation | Testing, cleanup | 1 hour | Not Started |

**Total Estimated Time**: 7-11 hours

**Recommended Approach**: 
- Day 1: Phases 1-3 (4-6 hours)
- Day 2: Phases 4-6 (3-5 hours)
- Day 3: Phases 7-8 (2-3 hours)

## Success Criteria

### Functional Requirements

- ✅ WebSocket endpoint available at `/api/v1/ws`
- ✅ Clients can subscribe to bar updates with `bars.subscribe`
- ✅ Subscription acknowledgments received via `bars.ack`
- ✅ Real-time bar updates delivered via `bars.update`
- ✅ Tasks cancelled on client disconnect
- ✅ Invalid symbols return error acks

### Non-Functional Requirements

- ✅ All tests pass (unit + integration)
- ✅ Test coverage > 80%
- ✅ All linters pass (black, isort, flake8, mypy)
- ✅ Documentation updated
- ✅ No breaking changes to existing API
- ✅ Response time < 100ms for subscription
- ✅ Update frequency configurable (default 1 sec)

### Code Quality

- ✅ Type hints on all functions
- ✅ Docstrings on all public methods
- ✅ No unused imports or variables
- ✅ Follows existing project patterns
- ✅ Error messages are clear and actionable

## Conclusion

**VERDICT**: ✅ **APPROVED FOR IMPLEMENTATION**

### Key Strengths

1. **Solid Foundation**: All required components exist or are well-defined
2. **Clear Architecture**: Plugin/adapter pattern provides clean separation
3. **Established Patterns**: Following TDD and existing code conventions
4. **Low Risk**: Additive feature with no breaking changes
5. **Good Documentation**: Clear plan with validation at each step

### Recommendations

1. **Start with TDD**: Write failing tests first for each component
2. **Incremental Development**: Implement one phase at a time
3. **Frequent Validation**: Run `make test && make lint-check` after each phase
4. **Documentation First**: Update docs as you implement, not after
5. **Manual Testing**: Use real WebSocket client to verify behavior

### Next Steps

1. **Get Approval**: Review this validation document
2. **Create Branch**: Use descriptive branch name (e.g., `feat/websocket-bars`)
3. **Phase 1**: Start with adapter layer and initial tests
4. **Iterate**: Follow TDD workflow through all phases
5. **PR Review**: Submit for review after all tests pass

---

**Validated By**: GitHub Copilot  
**Validation Date**: October 12, 2025  
**Status**: Ready for Implementation  
**Estimated Completion**: 3 days (7-11 development hours)
