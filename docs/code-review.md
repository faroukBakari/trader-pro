# Backend Architecture Code Review

**Date:** December 8, 2025  
**Scope:** Backend architecture, module implementations, provider system, WebSocket infrastructure  
**Status:** Review Complete

---

## Executive Summary

This review analyzes the Trading Pro backend architecture, identifying **3 critical issues**, **5 major issues**, and multiple code quality concerns. The architecture demonstrates strong patterns (contract-first design, capability-based DI, auto-discovery) but has security vulnerabilities and technical debt requiring attention.

---

## 1. Architecture Overview

### Structure

```
backend/src/trading_api/
├── app_factory.py         # ModularApp and AppFactory
├── main.py               # Entry point
├── shared/               # Shared infrastructure
│   ├── module_interface.py      # Module ABC
│   ├── module_registry.py       # Module discovery
│   ├── provider_interface.py    # Provider ABC
│   ├── provider_registry.py     # Provider discovery
│   ├── service_interface.py     # Service base class
│   ├── api/                     # APIRouterInterface
│   ├── middleware/              # Auth middleware
│   └── ws/                      # WebSocket framework
├── modules/              # Feature modules (broker, datafeed, auth)
├── providers/            # Provider implementations (google, tws)
└── models/               # Pydantic models
```

### Strengths

- **Contract-First Design**: Strong use of ABCs and protocols for clear interfaces
- **Capability-Based DI**: Provider system with fail-fast validation at startup
- **Auto-Discovery**: Modules and providers discovered by convention
- **Version Management**: API versioning with directory structure discovery
- **Type Safety**: Comprehensive Pydantic models and type hints
- **Stateless Authentication**: JWT middleware independent of auth module
- **WebSocket Architecture**: Generic router pattern with reference counting
- **Spec Generation**: Auto-generated OpenAPI/AsyncAPI specs per module

---

## 2. Critical Issues

### 2.1 Missing User Context in Broker Operations

**Severity:** 🔴 Critical  
**Location:** `backend/src/trading_api/modules/broker/service.py`

**Problem:** The broker service manages orders, positions, and executions without user scoping. All authenticated users share the same data:

```python
# All orders are stored globally - no user_id filtering
self._orders: Dict[str, PlacedOrder] = {}
self._positions: Dict[str, Position] = {}
```

While API endpoints require authentication via middleware, they don't pass `user_id` to the service for filtering.

**Impact:** Security vulnerability - users could see/modify each other's orders.

**Recommendation:**

- Add `user_id` parameter to all service methods
- Scope all data structures by user
- Update API layer to extract and pass user context

---

### 2.2 Race Condition in WebSocket Client Management

**Severity:** 🔴 Critical  
**Location:** `backend/src/trading_api/shared/ws/topic.py`

**Problem:** The subscribe and unsubscribe logic modifies `_clients` without locks:

```python
def _refresh_active_clients(self) -> set[Client]:
    return set([client for client in self._clients if ...])

# In send_unsubscribe:
self._clients = self._refresh_active_clients()  # Possible race
remaining_topic_clients = [clt for clt in self._clients if ...]
```

**Impact:** Race conditions under high concurrency could cause missed messages or client state corruption.

**Recommendation:**

- Add `asyncio.Lock` for client set modifications
- Consider using thread-safe collections
- Implement atomic subscribe/unsubscribe operations

---

### 2.3 SHA256 for Token Hashing

**Severity:** 🔴 Critical  
**Location:** `backend/src/trading_api/modules/auth/service.py`

**Problem:**

```python
def _hash_token(self, token: str) -> str:
    """Hash token using SHA256.
    Note: For production, consider using bcrypt/argon2..."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

SHA256 is not designed for password/token hashing - it's fast by design, making brute-force attacks feasible.

**Impact:** Refresh tokens vulnerable to offline brute-force attacks if database is compromised.

**Recommendation:**

- Replace with `argon2-cffi` or `bcrypt`
- Implement proper work factor configuration
- Plan migration strategy for existing tokens

---

## 3. Major Issues

### 3.1 Broad Exception Handling in TWSProvider

**Severity:** 🟠 Major  
**Location:** `backend/src/trading_api/providers/tws/tws_provider.py`

**Problem:**

```python
except Exception as e:
    raise DatafeedError(f"Failed to get historical bars for {ticker}: {e}") from e
```

Catching generic `Exception` masks specific errors and loses diagnostic information.

**Recommendation:**

- Catch specific exceptions (`ConnectionError`, `TimeoutError`, `ValueError`)
- Add structured error context
- Log original exception details before wrapping

---

### 3.2 Hardcoded Exchange Logic

**Severity:** 🟠 Major  
**Location:** `backend/src/trading_api/providers/tws/tws_provider.py`

**Problem:** Exchange routing logic duplicated 4+ times:

```python
now_us_eastern = datetime.now(us_eastern)
smart_exchange = (
    "OVERNIGHT"
    if (
        now_us_eastern.weekday() < 5
        and (
            now_us_eastern.time() >= datetime.strptime("20:00:00", "%H:%M:%S").time()
            or now_us_eastern.time() < datetime.strptime("4:00:00", "%H:%M:%S").time()
        )
    )
    else "SMART"
)
```

**Recommendation:**

- Extract to `is_overnight_trading_hours()` helper
- Make trading hours configurable
- Add tests for edge cases (weekends, holidays)

---

### 3.3 Timeout Handling in Synchronous Property

**Severity:** 🟠 Major  
**Location:** `backend/src/trading_api/modules/datafeed/api/v1.py`

**Problem:**

```python
@property
def service(self) -> DatafeedService:
    try:
        if not isinstance(self._service, DatafeedService):
            raise ValueError("Service has not been initialized")
        return self._service
    except (TimeoutError, asyncio.TimeoutError):  # This never fires!
        raise HTTPException(...)
```

Properties are synchronous - `TimeoutError` cannot occur here.

**Recommendation:**

- Remove dead exception handling
- Add proper service initialization validation

---

### 3.4 WsRouteService Not Properly Declared

**Severity:** 🟠 Major  
**Location:** `backend/src/trading_api/shared/ws/ws_route_service.py`

**Problem:** `WsRouteService` has `...` method bodies but isn't a proper Protocol or ABC:

```python
class WsRouteService(ServiceInterface):
    def create_topic(self, topic: str, topic_update: Callable[[Any], Awaitable[None]]) -> None:
        ...  # Should be @abstractmethod or Protocol
```

**Recommendation:**

- Convert to `typing.Protocol` for structural typing, OR
- Add `@abstractmethod` decorators for nominal typing
- Document the expected interface contract

---

### 3.5 Deprecated Event Loop Usage in Tests

**Severity:** 🟠 Major  
**Location:** `backend/tests/conftest.py`

**Problem:**

```python
def create_test_app(enabled_modules: list[str] | None = None) -> ModularApp:
    factory = AppFactory()
    return asyncio.get_event_loop().run_until_complete(...)  # Deprecated
```

**Recommendation:**

- Use `asyncio.run()` for Python 3.10+
- Or use pytest-asyncio's `@pytest.fixture` with async

---

## 4. Code Smells & Technical Debt

### 4.1 Type Ignore Comments

**Count:** 20+ instances across codebase

| Location                | Reason                  |
| ----------------------- | ----------------------- |
| `app_factory.py`        | `lifespan` call         |
| `module_interface.py`   | Return type override    |
| `provider_interface.py` | `capabilities` arg type |
| `tws_client.py`         | Thread-safe callback    |

**Recommendation:** Add specific ignore codes (e.g., `# type: ignore[override]`) and document rationale.

---

### 4.2 TODO/FIXME Markers

| Location                             | Issue                                        |
| ------------------------------------ | -------------------------------------------- |
| `shared/ws/topic.py`                 | "need to validate create_topic params/types" |
| `modules/datafeed/ws/v1/__init__.py` | "need to inject datafeed service"            |
| `providers/tws/tws_client.py`        | "REDESIGN SOCKET STATE MANAGEMENT"           |
| `providers/tws/tws_client.py`        | "debug bar unsubscribe"                      |
| `providers/tws/tws_client.py`        | "need optimizations for idle states"         |
| `providers/tws/ib_socket.py`         | "add clear subscriptions method"             |

---

### 4.3 Long Methods

**Location:** `backend/src/trading_api/providers/tws/tws_provider.py`

The `get_historical_bars()` method is ~120 lines. Should be refactored into:

- Parameter validation
- Contract building
- Request execution
- Response mapping

---

### 4.4 Magic Numbers

**Location:** `backend/src/trading_api/modules/broker/service.py`

```python
# Calculate mock fees (0.1% commission)
commission = order_value * 0.001
margin_required = order_value * 0.5
```

**Recommendation:** Extract to named constants or configuration:

```python
COMMISSION_RATE = Decimal("0.001")  # 0.1%
MARGIN_REQUIREMENT = Decimal("0.5")  # 50%
```

---

### 4.5 Inconsistent Typing Style

**Problem:** Mix of Python 3.9+ style (`dict`, `list`) and older (`Dict`, `List`).

**Recommendation:** Standardize on Python 3.10+ style throughout:

```python
# Before
from typing import Dict, List, Optional
def foo(items: List[str]) -> Dict[str, int]: ...

# After
def foo(items: list[str]) -> dict[str, int]: ...
```

---

### 4.6 Unused Imports

**Location:** Various files

```python
from re import sub  # Unused
from turtle import rt  # Unused and bizarre!
```

**Recommendation:** Run `ruff check --select F401` to identify and remove.

---

## 5. Missing Infrastructure

### 5.1 No Rate Limiting

**Impact:** API vulnerable to abuse and DoS attacks.

**Recommendation:** Add `slowapi` or custom middleware:

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
```

---

### 5.2 No Circuit Breaker for External Services

**Impact:** TWSProvider and GoogleProvider failures cascade to all requests.

**Recommendation:** Implement circuit breaker pattern:

- Use `circuitbreaker` library
- Add health degradation states
- Implement fallback behaviors

---

### 5.3 No Metrics/Telemetry

**Impact:** No observability into production behavior.

**Recommendation:**

- Add OpenTelemetry instrumentation
- Export Prometheus metrics
- Implement structured logging with correlation IDs

---

### 5.4 No Provider Health Checks

**Impact:** Module health endpoints don't reflect provider status.

**Recommendation:** Extend health check to include:

```python
{
    "module": "datafeed",
    "status": "healthy",
    "providers": {
        "tws": {"status": "connected", "latency_ms": 45}
    }
}
```

---

### 5.5 No Graceful WebSocket Shutdown

**Impact:** Abrupt disconnections during deployment.

**Recommendation:**

- Implement shutdown signal handler
- Send close frames to all connected clients
- Wait for clean disconnection with timeout

---

## 6. Testing Gaps

### Current Coverage

- **Auth Module:** 83 tests (repository, service, API, middleware)
- **Broker Module:** Tests for API and WebSocket
- **Datafeed Module:** Limited test coverage

### Identified Gaps

1. **No integration tests for provider failure scenarios**
2. **Limited concurrent WebSocket subscription tests**
3. **No load/stress testing infrastructure**
4. **Missing edge case tests for topic management**
5. **No tests for provider shutdown behavior**
6. **WebSocket authentication flow has limited coverage**

---

## 7. Recommendations Summary

### Immediate (Critical) - Week 1

| Issue                    | Action                                  | Effort   |
| ------------------------ | --------------------------------------- | -------- |
| User scoping in broker   | Add `user_id` to all service methods    | 2-3 days |
| WebSocket race condition | Add `asyncio.Lock` to client management | 1 day    |
| Token hashing            | Replace SHA256 with argon2              | 1 day    |

### Short-term (Major) - Week 2-3

| Issue                 | Action                               | Effort   |
| --------------------- | ------------------------------------ | -------- |
| Exchange logic        | Extract to helper function           | 0.5 days |
| Dead code removal     | Remove impossible exception handling | 0.5 days |
| WsRouteService        | Convert to proper Protocol/ABC       | 0.5 days |
| Deprecated event loop | Update test fixtures                 | 1 day    |
| Type ignore cleanup   | Add specific codes and docs          | 1 day    |

### Medium-term - Month 1

| Issue           | Action                  | Effort |
| --------------- | ----------------------- | ------ |
| Rate limiting   | Add slowapi middleware  | 2 days |
| Circuit breaker | Implement for providers | 3 days |
| Telemetry       | Add OpenTelemetry       | 3 days |
| Provider health | Extend health endpoints | 1 day  |

### Long-term - Quarter 1

| Issue                 | Action                   | Effort  |
| --------------------- | ------------------------ | ------- |
| Persistent storage    | Migrate auth to database | 1 week  |
| Comprehensive metrics | Full observability stack | 2 weeks |
| Chaos testing         | Provider failure testing | 1 week  |

---

## 8. Appendix: File Reference Index

| File                            | Issues        |
| ------------------------------- | ------------- |
| `modules/broker/service.py`     | 2.1, 4.4      |
| `modules/auth/service.py`       | 2.3           |
| `shared/ws/topic.py`            | 2.2, 4.2      |
| `providers/tws/tws_provider.py` | 3.1, 3.2, 4.3 |
| `modules/datafeed/api/v1.py`    | 3.3           |
| `shared/ws/ws_route_service.py` | 3.4           |
| `tests/conftest.py`             | 3.5           |

---

**Review Completed By:** Architecture Review  
**Next Review:** TBD after critical issues addressed
