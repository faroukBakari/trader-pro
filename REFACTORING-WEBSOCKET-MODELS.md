# WebSocket Models Refactoring Summary

**Date**: [Current Date]
**Branch**: server-side-broker
**Type**: Code Organization & API Simplification

## Overview

This refactoring consolidated WebSocket models into the central `models/` package and simplified the WebSocket API by removing nested payload structures in favor of flat, typed request models.

## Motivation

### Problems with Previous Approach

1. **Generic Untyped Parameters**: The old `SubscriptionRequest` used `params: dict[str, Any]`, losing type safety
2. **Scattered Models**: WebSocket models in `ws/common.py` separate from REST models in `models/`
3. **Nested Payload Structure**: Client payloads required nested `params` dict, making API less intuitive
4. **Naming Conflicts**: Generic `BaseResponse` and `ErrorResponse` conflicted with TradingView broker API models

### Benefits of New Approach

1. **✅ Type Safety**: Pydantic models with specific fields (`BarsSubscriptionRequest` with `symbol: str, resolution: str`)
2. **✅ Centralized Models**: All models in `models/` package for easier discovery and maintenance
3. **✅ Flat Structure**: Simpler client payloads (`{symbol, resolution}` vs `{symbol, params: {resolution}}`)
4. **✅ Domain-Specific**: Models named after their purpose (`BarsSubscriptionRequest` vs generic `SubscriptionRequest`)
5. **✅ AsyncAPI Generation**: Better AsyncAPI documentation from typed models

## Changes Made

### 1. Model Renames (Conflict Resolution)

**Before:**
```python
# models/common.py
class BaseResponse(BaseModel):
    status: str
    message: str

class ErrorResponse(BaseModel):
    error: str
```

**After:**
```python
# models/common.py
class BaseApiResponse(BaseModel):
    """Base response for API operations"""
    status: str
    message: str

class ErrorApiResponse(BaseModel):
    """Error response for API operations"""
    error: str
```

**Reason**: Avoid conflicts with TradingView's `BaseResponse` from broker API models.

### 2. WebSocket Models Consolidation

**Deleted:**
```python
# ws/common.py (ENTIRE FILE DELETED)
class SubscriptionRequest(BaseModel):
    symbol: str
    params: dict[str, Any] = Field(default_factory=dict)

class SubscriptionResponse(BaseModel):
    status: Literal["ok", "error"]
    symbol: str
    message: str
    topic: str
```

**New Location:**
```python
# models/common.py
class SubscriptionResponse(BaseApiResponse):
    """Generic WebSocket subscription response"""
    topic: str  # Inherits status and message from BaseApiResponse

# models/market/bars.py
class BarsSubscriptionRequest(BaseModel):
    """WebSocket subscription request for bar data"""
    symbol: str
    resolution: str = "1"  # Default 1-minute bars
```

### 3. Module Reorganization

**Deleted:**
- `backend/src/trading_api/services/` (entire directory)
  - `__init__.py`
  - `bar_broadcaster.py` → moved to `core/bar_broadcaster.py`

**Created:**
- `backend/src/trading_api/core/bar_broadcaster.py` (moved from services/)

**Deleted:**
- `backend/src/trading_api/ws/common.py` (models moved to `models/`)

**Modified:**
- `backend/src/trading_api/ws/__init__.py` (removed common.py exports)

### 4. WebSocket API Signature Changes

**Before:**
```python
# ws/datafeed.py
def bars_topic_builder(symbol: str, params: dict) -> str:
    resolution = params.get("resolution", "1")
    return f"bars:{symbol}:{resolution}"

@router.send("subscribe", reply="subscribe.response")
async def send_subscribe(
    payload: SubscriptionRequest,  # Generic model
    client: Client,
) -> SubscriptionResponse:
    topic = bars_topic_builder(payload.symbol, payload.params)
    ...
```

**After:**
```python
# ws/datafeed.py
def bars_topic_builder(params: BarsSubscriptionRequest) -> str:
    return f"bars:{params.symbol}:{params.resolution}"

@router.send("subscribe", reply="subscribe.response")
async def send_subscribe(
    payload: BarsSubscriptionRequest,  # Typed model
    client: Client,
) -> SubscriptionResponse:
    topic = bars_topic_builder(payload)
    ...
```

### 5. Client Payload Structure Simplification

**Before (Nested):**
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

**After (Flat):**
```json
{
  "type": "bars.subscribe",
  "payload": {
    "symbol": "AAPL",
    "resolution": "1"
  }
}
```

## Migration Guide

### For Backend Code

**Old Import:**
```python
from trading_api.ws.common import SubscriptionRequest, SubscriptionResponse
from trading_api.models.common import BaseResponse, ErrorResponse
```

**New Import:**
```python
from trading_api.models.market.bars import BarsSubscriptionRequest
from trading_api.models.common import SubscriptionResponse, BaseApiResponse, ErrorApiResponse
```

**Old Topic Builder:**
```python
topic = bars_topic_builder(symbol="AAPL", params={"resolution": "1"})
```

**New Topic Builder:**
```python
request = BarsSubscriptionRequest(symbol="AAPL", resolution="1")
topic = bars_topic_builder(request)
```

### For WebSocket Clients

**Old JavaScript Client:**
```javascript
ws.send(JSON.stringify({
  type: 'bars.subscribe',
  payload: {
    symbol: 'AAPL',
    params: { resolution: '1' }
  }
}));
```

**New JavaScript Client:**
```javascript
ws.send(JSON.stringify({
  type: 'bars.subscribe',
  payload: {
    symbol: 'AAPL',
    resolution: '1'
  }
}));
```

### For Tests

**Old Test Payload:**
```python
websocket.send_json({
    "type": "bars.subscribe",
    "payload": {
        "symbol": "AAPL",
        "params": {"resolution": "1"}
    }
})
```

**New Test Payload:**
```python
websocket.send_json({
    "type": "bars.subscribe",
    "payload": {
        "symbol": "AAPL",
        "resolution": "1"
    }
})
```

## Files Modified

### Backend Core Changes
- ✅ `backend/src/trading_api/main.py` - Updated import from `services` to `core`
- ✅ `backend/src/trading_api/core/bar_broadcaster.py` - Moved from `services/` (updated imports)
- ✅ `backend/src/trading_api/models/__init__.py` - Added new model exports
- ✅ `backend/src/trading_api/models/common.py` - Renamed models, added `SubscriptionResponse`
- ✅ `backend/src/trading_api/models/market/__init__.py` - Added `BarsSubscriptionRequest` export
- ✅ `backend/src/trading_api/models/market/bars.py` - Added `BarsSubscriptionRequest` model
- ✅ `backend/src/trading_api/ws/__init__.py` - Removed `common` exports
- ✅ `backend/src/trading_api/ws/datafeed.py` - Updated signature and imports

### Deleted Files
- ❌ `backend/src/trading_api/services/__init__.py`
- ❌ `backend/src/trading_api/services/bar_broadcaster.py`
- ❌ `backend/src/trading_api/ws/common.py`

### Test Updates
- ✅ `backend/tests/test_bar_broadcaster.py` - Added type annotations, updated imports
- ✅ `backend/tests/test_ws_datafeed.py` - Updated 6 tests with flat payload structure

### Documentation Updates
- ✅ `REFACTORING-MODELS.md` - Added latest changes section
- ✅ `BROADCASTER-IMPLEMENTATION.md` - Updated file paths
- ✅ `WEBSOCKET-IMPLEMENTATION.md` - Updated models location and examples
- ✅ `backend/docs/websockets.md` - Updated all payload examples
- ✅ `backend/README.md` - Updated project structure
- ✅ `ARCHITECTURE.md` - Updated component structure

### Frontend Changes
- ✅ `frontend/.gitignore` - Added `ws-types-generated/`
- ✅ `frontend/scripts/generate-client.sh` - Added AsyncAPI support
- ✅ `frontend/scripts/generate-ws-types.cjs` - **NEW**: AsyncAPI to TypeScript generator

## Frontend AsyncAPI Support

A new TypeScript type generator was added to automatically generate WebSocket types from the AsyncAPI specification:

### New Script: `generate-ws-types.cjs`

**Purpose**: Converts AsyncAPI specification to TypeScript interfaces

**Features**:
- Generates TypeScript interfaces from AsyncAPI message schemas
- Creates `WS_OPERATIONS` constants for operation names
- Type-safe WebSocket client development
- Automatic generation during build process

**Usage**:
```bash
cd frontend
node scripts/generate-ws-types.cjs
```

**Generated Output**: `frontend/src/services/generated/ws-types-generated/`

**Integration**:
```bash
# Updated generate-client.sh
if [ "$ASYNCAPI_MODE" = "true" ]; then
    node scripts/generate-ws-types.cjs
else
    # OpenAPI generation
fi
```

## Validation

### Tests Passing
All 39 backend tests pass with the refactoring:
```bash
$ cd backend && make test
39 passed in 1.92s
```

**Test Coverage:**
- 23 tests for `BarBroadcaster` (includes new type annotations)
- 7 tests for WebSocket datafeed (updated with flat payloads)
- 9 tests for health/versioning endpoints

### Type Checking
All mypy type checks pass:
```bash
$ cd backend && make lint-check
mypy src/
Success: no issues found in 37 source files
```

### Code Quality
All linting and formatting checks pass:
```bash
$ make lint-check
black --check ✅
isort --check-only ✅
flake8 ✅
mypy ✅
```

## Breaking Changes

### Client-Side Impact

**⚠️ Breaking Change**: WebSocket payload structure changed from nested to flat

**Old Clients** (will fail):
```javascript
// ❌ Old nested structure no longer works
ws.send(JSON.stringify({
  type: 'bars.subscribe',
  payload: { symbol: 'AAPL', params: { resolution: '1' } }
}));
```

**New Clients** (required):
```javascript
// ✅ New flat structure required
ws.send(JSON.stringify({
  type: 'bars.subscribe',
  payload: { symbol: 'AAPL', resolution: '1' }
}));
```

**Migration Path**:
1. Update all WebSocket clients to use flat payload structure
2. Remove `params` wrapper from subscription messages
3. Pass `resolution` directly in payload root

### Server-Side Impact

**Non-Breaking for REST API**: REST endpoints unchanged

**Breaking for WebSocket Imports**:
```python
# ❌ Old imports will fail
from trading_api.ws.common import SubscriptionRequest, SubscriptionResponse
from trading_api.models.common import BaseResponse, ErrorResponse

# ✅ New imports required
from trading_api.models.market.bars import BarsSubscriptionRequest
from trading_api.models.common import SubscriptionResponse, BaseApiResponse, ErrorApiResponse
```

## Benefits Realized

### 1. Type Safety Improvements
- ✅ Pydantic validation on all WebSocket payloads
- ✅ AsyncAPI spec auto-generated from typed models
- ✅ Frontend TypeScript types from AsyncAPI
- ✅ Compile-time error detection

### 2. Code Organization
- ✅ All models centralized in `models/` package
- ✅ `core/` contains background services (bar_broadcaster)
- ✅ `ws/` focused on operations, not models
- ✅ Clear separation of concerns

### 3. Developer Experience
- ✅ Simpler client payloads (flat vs nested)
- ✅ Self-documenting via typed models
- ✅ Better IDE autocomplete
- ✅ Easier to understand and maintain

### 4. API Evolution
- ✅ Domain-specific models enable future features
- ✅ Easy to add new subscription types
- ✅ Version-safe model evolution
- ✅ AsyncAPI docs track changes

## Future Considerations

### Potential Enhancements

1. **Additional Subscription Types**:
   - `QuotesSubscriptionRequest` for real-time quotes
   - `TradesSubscriptionRequest` for trade streams
   - `OrderBookSubscriptionRequest` for order book depth

2. **Generic Base Classes**:
   ```python
   class SubscriptionRequest(BaseModel, Generic[T]):
       """Generic subscription request"""
       symbol: str
       params: T  # Typed parameters
   
   class BarsParams(BaseModel):
       resolution: str = "1"
   
   BarsSubscriptionRequest = SubscriptionRequest[BarsParams]
   ```

3. **Request Validation**:
   - Add custom validators for resolution formats
   - Symbol existence validation
   - Rate limiting per subscription

## Commit Suggestion

```
refactor(backend): consolidate WebSocket models and simplify API

Breaking Changes:
- WebSocket payload structure changed from nested to flat
- Old: {symbol, params: {resolution}} → New: {symbol, resolution}
- Models moved: ws/common.py → models/common.py & models/market/bars.py
- Renamed: BaseResponse → BaseApiResponse, ErrorResponse → ErrorApiResponse

Module Organization:
- services/ → core/ (BarBroadcaster consolidation)
- ws/common.py deleted (models moved to central package)
- Added BarsSubscriptionRequest with typed fields

Benefits:
- Type-safe WebSocket operations via Pydantic
- Simpler client payload structure
- Better AsyncAPI specification
- Centralized model management
- Frontend TypeScript generation from AsyncAPI

Tests:
- Updated 6 WebSocket tests with flat payloads
- Added type annotations to BarBroadcaster tests
- All 39 tests passing, mypy clean

Documentation:
- Updated REFACTORING-MODELS.md
- Updated WEBSOCKET-IMPLEMENTATION.md
- Updated backend/docs/websockets.md
- Updated ARCHITECTURE.md
- Created REFACTORING-WEBSOCKET-MODELS.md

Frontend:
- Added generate-ws-types.cjs for AsyncAPI → TypeScript
- Updated .gitignore for generated types
```

## Related Documentation

- **REFACTORING-MODELS.md** - Historical model refactoring
- **WEBSOCKET-IMPLEMENTATION.md** - WebSocket implementation guide
- **backend/docs/websockets.md** - WebSocket API reference
- **ARCHITECTURE.md** - System architecture overview
- **BROADCASTER-IMPLEMENTATION.md** - Bar broadcaster service

---

**Review Status**: ✅ Complete  
**Breaking Changes**: Yes (WebSocket payload structure)  
**Backward Compatibility**: No (clients must update)  
**Documentation**: Updated  
**Tests**: All passing (39/39)
