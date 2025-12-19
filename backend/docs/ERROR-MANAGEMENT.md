# Backend Error Management

**Status**: ✅ Production Ready  
**Last Updated**: December 19, 2025  
**Version**: 1.0.0

---

## Table of Contents

- [Overview](#overview)
- [Exception Hierarchy](#exception-hierarchy)
- [Error Code Conventions](#error-code-conventions)
- [Exception Handlers](#exception-handlers)
- [Usage Patterns](#usage-patterns)
- [Testing Patterns](#testing-patterns)
- [Logging](#logging)

---

## Overview

The Trading Pro backend implements a **structured exception handling system** that provides:

- **Type-Safe Exceptions**: Three-tier hierarchy with serializable error details
- **Consistent Error Codes**: Machine-readable codes following naming conventions
- **Centralized Handling**: Global exception handlers for HTTP and WebSocket
- **Clean Logging**: Project-only backtraces with automatic external frame filtering
- **Testable Errors**: Test clients configured for proper error response testing

### Design Philosophy

#### Core Principle: "Only Catch What You Can Handle"

> _"If unsure, let it throw. Let it crash. Log the error."_  
> — Industry best practice, inspired by Erlang's "Let It Crash" philosophy (Joe Armstrong)

**Exceptions are NOT caught within services or providers.** Instead, they propagate naturally through the call stack until reaching the global exception handler at the API or WebSocket endpoint boundary. This approach:

- ✅ Avoids duplicate try/catch blocks throughout the codebase
- ✅ Ensures consistent error responses
- ✅ Provides complete backtraces for debugging
- ✅ Simplifies business logic code

#### Decision Matrix: When to Catch Locally

```
┌────────────────────────────────────────────────────────────────┐
│                   CAN YOU MITIGATE?                            │
├──────────────────────┬─────────────────────────────────────────┤
│         YES          │                   NO                    │
├──────────────────────┼─────────────────────────────────────────┤
│ • Retry with backoff │ • Unknown/unexpected error              │
│ • Fallback value     │ • No recovery possible                  │
│ • Partial results    │ • Caller needs to know anyway           │
│ • Graceful degrade   │                                         │
├──────────────────────┼─────────────────────────────────────────┤
│   ✅ CATCH LOCALLY   │        ❌ LET IT PROPAGATE              │
│   (handle + recover) │   (global handler returns HTTP error)   │
└──────────────────────┴─────────────────────────────────────────┘
```

#### Anti-Patterns Avoided

| Anti-Pattern                   | Description                                | Our Approach                       |
| ------------------------------ | ------------------------------------------ | ---------------------------------- |
| **Pokémon Exception Handling** | "Gotta catch 'em all" — `except Exception` | ❌ Only catch specific types       |
| **Error Swallowing**           | `except: pass` silently discards           | ❌ All errors reach global handler |
| **Defensive Overkill**         | try-except on every line                   | ❌ Single boundary at API/WS level |
| **Log & Pray**                 | `except: logger.error(e)` without re-raise | ❌ Global handler logs + responds  |
| **Cascaded Try-Except**        | Nested try-except blocks                   | ❌ Flat error propagation          |

#### Why This Matters

Scattered try-except blocks cause:

- **Debugging nightmares**: Errors caught and re-raised lose original context
- **Inconsistent responses**: Different catch blocks format errors differently
- **Hidden failures**: Silent catches mask bugs until production
- **Code bloat**: Business logic buried under exception handling boilerplate

**See also:** [Frontend Error Management](../../frontend/docs/ERROR-MANAGEMENT.md) for parallel philosophy in the frontend.

---

## Exception Hierarchy

All exceptions inherit from `TradingApiException`, which provides serializable error information for debugging and client responses.

```
TradingApiException (base)
├── CommonException        # Infrastructure/shared/auth middleware errors
├── ServiceException       # Service layer errors (+module)
└── ProviderException      # Provider errors (+provider, +capability)
```

### Class Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   TradingApiException                       │
│  ─────────────────────────────────────────────────────────  │
│  + code: str              # Machine-readable error code     │
│  + message: str           # Human-readable description      │
│  + backtrace: List[FrameSummary]  # Stack frames            │
│  + timestamp: int         # Unix timestamp                  │
│  ─────────────────────────────────────────────────────────  │
│  + to_dict() → dict       # Serialize for JSON response    │
└─────────────────────────────────────────────────────────────┘
            ▲                    ▲                    ▲
            │                    │                    │
┌───────────┴───────┐ ┌─────────┴─────────┐ ┌───────┴─────────┐
│  CommonException  │ │ ServiceException  │ │ProviderException│
│  ───────────────  │ │ ────────────────  │ │ ───────────────  │
│  (no extra attrs) │ │ + module: str     │ │ + provider: str  │
│                   │ │                   │ │ + capability: str│
└───────────────────┘ └───────────────────┘ └──────────────────┘
```

**Source:** [models/exceptions.py](../src/trading_api/models/exceptions.py)

### TradingApiException (Base)

Base exception for all Trading API errors. Automatically captures backtrace at raise time.

```python
from trading_api.models.exceptions import TradingApiException

raise TradingApiException(
    code="UNHANDLED_EXCEPTION",
    message="An unexpected error occurred",
)
```

**Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `str` | Machine-readable error code |
| `message` | `str` | Human-readable error description |
| `backtrace` | `List[FrameSummary]` | Stack frames (auto-captured via `traceback.extract_tb()`) |
| `timestamp` | `int` | Unix timestamp (auto-set) |

### CommonException

For infrastructure, shared utilities, and middleware errors. Used when errors don't originate from a specific module or provider.

```python
from trading_api.models.exceptions import CommonException

# Capability not found during app startup
raise CommonException(
    code="COMMON_CAPABILITY_NOT_FOUND",
    message=f"No provider found for capability 'datafeed'",
)

# Configuration error
raise CommonException(
    code="COMMON_CONFIG_MISSING",
    message="Required environment variable JWT_SECRET not set",
)
```

**When to use:**

- Authentication middleware errors
- Configuration/startup errors
- Shared utility failures
- Capability resolution failures

### ServiceException

For business logic errors within module services. Includes the module name for context.

```python
from trading_api.models.exceptions import ServiceException

# Datafeed service error
raise ServiceException(
    code="SERVICE_DATAFEED_TOPIC_EXISTS",
    message=f"Topic already exists: {topic}",
    module="datafeed",
)

# Auth service error
raise ServiceException(
    code="SERVICE_AUTH_USER_NOT_FOUND",
    message="User not found",
    module="auth",
)
```

**Additional Attribute:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `module` | `str` | Module name (e.g., "datafeed", "broker", "auth") |

**When to use:**

- Validation errors in services
- Business rule violations
- Resource not found (within service logic)
- Invalid state transitions

### ProviderException

For errors from external provider integrations. Includes provider name and capability type.

```python
from trading_api.models.exceptions import ProviderException

# TWS provider error
raise ProviderException(
    code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
    message=f"Symbol not found: {ticker}",
    provider="tws",
    capability="datafeed",
)

# Google auth provider error
raise ProviderException(
    code="PROVIDER_AUTH_TOKEN_INVALID",
    message=f"Invalid Google token: {error}",
    provider="google",
    capability="auth",
)
```

**Additional Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `provider` | `str` | Provider name (e.g., "tws", "google") |
| `capability` | `str` | Capability type (e.g., "datafeed", "auth") |

**When to use:**

- External API failures
- Connection errors to external services
- Invalid responses from providers
- Provider-specific validation errors

---

## Subscription-Level Error Models

For WebSocket streaming, errors can occur at the subscription level (specific topic fails) rather than connection level. These models provide structured error payloads for client notification.

**Source:** [models/common.py](../src/trading_api/models/common.py)

### ErrorPayload

Pydantic model that bridges `TradingApiException` to client-safe JSON payloads:

```python
from trading_api.models import ErrorPayload

# Convert exception to client payload
exc = ProviderException(
    provider="tws",
    capability="datafeed",
    code="PROVIDER_DATAFEED_TIMEOUT",
    message="Request timed out",
)
payload = ErrorPayload.from_exception(exc)

# Result:
{
    "code": "PROVIDER_DATAFEED_TIMEOUT",
    "message": "Request timed out",
    "timestamp": 1702656000.0,
    "details": {"provider": "tws", "capability": "datafeed"}
}
```

**Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `str` | Error code from exception |
| `message` | `str` | Human-readable error message |
| `timestamp` | `float` | Unix timestamp |
| `details` | `dict \| None` | Extra context (provider, capability, module) |

**Note:** `backtrace` is intentionally excluded (backend-only concern).

### SubscriptionError

Wraps `ErrorPayload` with subscription context and recovery hints:

```python
from trading_api.models import SubscriptionError, ErrorPayload

error = SubscriptionError(
    topic="bars:AAPL:1",
    error=ErrorPayload.from_exception(exc),
    recoverable=True,
    retry_after_ms=5000,
)
```

**Attributes:**
| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `topic` | `str` | required | Subscription topic that failed |
| `error` | `ErrorPayload` | required | Structured error payload |
| `recoverable` | `bool` | `True` | If client can retry |
| `retry_after_ms` | `int \| None` | `None` | Suggested retry delay |

---

## Error Code Conventions

Error codes follow a hierarchical naming convention that indicates the error's origin and type.

### Code Format

```
{LAYER}_{DOMAIN}_{ERROR_TYPE}
```

| Layer    | Prefix      | Description                  |
| -------- | ----------- | ---------------------------- |
| Common   | `COMMON_`   | Infrastructure/shared errors |
| Service  | `SERVICE_`  | Module service errors        |
| Provider | `PROVIDER_` | External provider errors     |

### Error Code Examples

| Code                                    | HTTP Status | Description                       |
| --------------------------------------- | ----------- | --------------------------------- |
| `COMMON_CAPABILITY_NOT_FOUND`           | 500         | Required capability not available |
| `COMMON_CONFIG_MISSING`                 | 500         | Missing configuration             |
| `SERVICE_DATAFEED_TOPIC_EXISTS`         | 400         | Topic already subscribed          |
| `SERVICE_DATAFEED_INVALID_TOPIC_FORMAT` | 400         | Malformed topic string            |
| `SERVICE_DATAFEED_NO_SYMBOLS`           | 400         | Empty symbols list                |
| `SERVICE_AUTH_USER_NOT_FOUND`           | 404         | User doesn't exist                |
| `SERVICE_AUTH_INVALID_REFRESH_TOKEN`    | 401         | Invalid/expired refresh token     |
| `PROVIDER_DATAFEED_SYMBOL_NOT_FOUND`    | 404         | Symbol not found in provider      |
| `PROVIDER_DATAFEED_CONNECTION_FAILED`   | 500         | Provider connection error         |
| `PROVIDER_AUTH_TOKEN_INVALID`           | 401         | Invalid authentication token      |
| `PROVIDER_AUTH_EMAIL_NOT_VERIFIED`      | 403         | Email verification required       |

### HTTP Status Code Mapping

The exception handler automatically maps error codes to HTTP status codes based on patterns:

```python
# From shared/exception_handlers.py

def _get_status_code_from_code(code: str) -> int:
    code_upper = code.upper()

    # Not found errors → 404
    if "NOT_FOUND" in code_upper:
        return 404

    # Auth invalid/expired → 401
    if "AUTH" in code_upper and any(
        p in code_upper for p in ["INVALID", "TOKEN_EXPIRED", "UNAUTHORIZED"]
    ):
        return 401

    # Forbidden
    if "FORBIDDEN" in code_upper or "EMAIL_NOT_VERIFIED" in code_upper:
        return 403

    # Validation/bad request → 400
    if any(
        p in code_upper for p in [
            "INVALID", "BAD_REQUEST", "VALIDATION",
            "TOPIC_EXISTS", "NO_SYMBOLS"
        ]
    ):
        return 400

    # Default → 500
    return 500
```

### WebSocket Close Code Mapping

WebSocket errors use RFC 6455 close codes:

| Pattern                      | Close Code | Meaning          |
| ---------------------------- | ---------- | ---------------- |
| `*_AUTH_*`                   | 1008       | Policy Violation |
| `*_INVALID_*`, `*_NOT_FOUND` | 1003       | Unsupported Data |
| Default                      | 1011       | Internal Error   |

---

## Exception Handlers

Global exception handlers convert `TradingApiException` instances to appropriate HTTP responses or WebSocket close frames.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Client Request                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI/FastWS App                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   API Endpoint / WS Handler                │  │
│  │                          │                                 │  │
│  │                          ▼                                 │  │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐  │  │
│  │  │   Service   │ → │  Provider   │ → │ External System │  │  │
│  │  └─────────────┘   └─────────────┘   └─────────────────┘  │  │
│  │         │                 │                               │  │
│  │         │  Exception bubbles up (not caught)              │  │
│  │         ▼                 ▼                               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Global Exception Handler                      │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │ 1. Log exception with project-only backtrace         │ │  │
│  │  │ 2. Map error code → HTTP status / WS close code      │ │  │
│  │  │ 3. Return JSON response / Close WebSocket            │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              HTTP Response / WebSocket Close                     │
│  {"code": "SERVICE_DATAFEED_TOPIC_EXISTS", "message": "..."}    │
└──────────────────────────────────────────────────────────────────┘
```

### Registration

Exception handlers are registered on the `ModularApp` during factory creation:

```python
# app_factory.py
from trading_api.shared.exception_handlers import register_exception_handlers

modular_app = ModularApp(...)
register_exception_handlers(modular_app)
```

**Source:** [shared/exception_handlers.py](../src/trading_api/shared/exception_handlers.py)

### HTTP Response Format

All HTTP error responses follow this structure:

```json
{
  "code": "SERVICE_DATAFEED_TOPIC_EXISTS",
  "message": "Topic already exists in DatafeedService: bars:{...}"
}
```

**Note:** Backtraces are logged but NOT included in client responses for security.

### WebSocket Close Format

WebSocket errors close the connection with a code and reason:

```python
# Close code: 1003 (Unsupported Data)
# Reason: "SERVICE_DATAFEED_INVALID_TOPIC: Invalid topic format" (max 123 bytes)
await websocket.close(code=1003, reason=f"{code}: {message}"[:123])
```

**Connection State Guard:**

The WebSocket exception handler checks for `DISCONNECTED` state to avoid double-closing:

```python
# Exception handler in shared/exception_handlers.py
if websocket.client_state == WebSocketState.DISCONNECTED:
    return  # Already disconnected, nothing to close
```

> ⚠️ **Critical:** Must check for `DISCONNECTED` (not `!= CONNECTED`). During the handshake phase,
> `client_state` is `CONNECTING`, and an early exit would leave the client hanging without a response.

### WebSocket Subscription Errors

Subscription-level errors notify clients without closing the connection. This is distinct from connection-level errors which terminate the WebSocket.

**Connection-Level vs Subscription-Level:**
| Level | When | Action | Example |
|-------|------|--------|---------|
| **Connection** | Auth failure, protocol error | Close WebSocket | Invalid JWT, malformed message |
| **Subscription** | Specific topic fails | Send error message | Symbol timeout, rate limit |

**Error Message Format:**

```json
{
  "type": "{route}.error",
  "payload": {
    "topic": "bars:AAPL:1",
    "error": {
      "code": "PROVIDER_DATAFEED_TIMEOUT",
      "message": "Request timed out",
      "timestamp": 1702656000.0,
      "details": { "provider": "tws", "capability": "datafeed" }
    },
    "recoverable": true,
    "retry_after_ms": 5000
  }
}
```

**Handling Flow:**

```
Provider Error
     │
     ├─► Recoverable (timeout, rate limit)
     │        │
     │        └─► Broadcast SubscriptionError → Keep connection open
     │
     └─► Non-recoverable (symbol invalid, permission denied)
              │
              └─► exception_handler() → Log + Close connection
```

**See:** [BACKEND_WEBSOCKETS.md](BACKEND_WEBSOCKETS.md#websocket-error-handling) for implementation details.

### Unhandled Exceptions

Non-`TradingApiException` errors are automatically wrapped:

```python
# Any unexpected exception becomes:
TradingApiException(
    code="UNHANDLED_EXCEPTION",
    message=str(exc),
    backtrace=traceback.format_exception(...),
)
```

---

## Usage Patterns

### Provider Layer

Providers raise `ProviderException` for external integration errors:

```python
# providers/tws/__init__.py
class TWSProvider(Provider, DatafeedCapability):

    async def get_symbol_info(self, ticker: str, **kwargs) -> SymbolInfo:
        contract_details_list = await self._tws_client.reqContractDetails(...)

        if not contract_details_list:
            raise ProviderException(
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
                message=f"Symbol not found: {ticker}",
                provider="tws",
                capability="datafeed",
            )

        return contract_details_to_symbol_info(contract_details_list[0])
```

```python
# providers/google/__init__.py
class GoogleProvider(Provider, AuthCapability):

    async def verify_token(self, token: str) -> dict[str, Any]:
        resp = await client.get("https://googleapis.com/.../tokeninfo", ...)

        if resp.status_code != 200:
            raise ProviderException(
                code="PROVIDER_AUTH_TOKEN_INVALID",
                message=f"Invalid Google token: {resp.text}",
                provider="google",
                capability="auth",
            )

        claims = resp.json()

        if claims.get("email_verified") not in (True, "true"):
            raise ProviderException(
                code="PROVIDER_AUTH_EMAIL_NOT_VERIFIED",
                message="Email not verified",
                provider="google",
                capability="auth",
            )

        return claims
```

### Service Layer

Services raise `ServiceException` for business logic errors:

```python
# modules/datafeed/service.py
class DatafeedService(WsRouteService):

    def create_topic(self, topic: str, callback: Callable) -> None:
        if topic in self._topic_to_subscription_id:
            raise ServiceException(
                code="SERVICE_DATAFEED_TOPIC_EXISTS",
                message=f"Topic already exists: {topic}",
                module="datafeed",
            )

        if ":" not in topic:
            raise ServiceException(
                code="SERVICE_DATAFEED_INVALID_TOPIC_FORMAT",
                message=f"Invalid topic format: {topic}",
                module="datafeed",
            )
```

```python
# modules/auth/service.py
class AuthService(ServiceInterface):

    async def refresh_access_token(self, refresh_token: str, ...) -> TokenResponse:
        token_data = await self.token_repository.get_token(token_hash, ...)

        if token_data is None:
            raise ServiceException(
                code="SERVICE_AUTH_INVALID_REFRESH_TOKEN",
                message="Invalid refresh token",
                module="auth",
            )
```

### API Layer

API endpoints do NOT catch exceptions - they let them bubble up:

```python
# modules/datafeed/api/v1.py
class DatafeedApi(APIRouterInterface):

    @self.get("/resolve/{symbol}", response_model=SymbolInfo)
    async def resolve_symbol(symbol: str, ...) -> SymbolInfo:
        # No try/except! Let exceptions propagate to global handler
        symbol_info = await self.service.resolve_ticker(symbol)

        if not symbol_info:
            raise ServiceException(
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
                message=f"Symbol '{symbol}' not found.",
                module="datafeed",
            )

        return symbol_info
```

### Capability Validation

The `ServiceInterface` uses `CommonException` for startup validation:

```python
# shared/service_interface.py
def _resolve_capabilities(self) -> None:
    for req_cap in self.capabilities():
        matched = False

        for provider in self._providers:
            for prov_cap in provider.capabilities():
                if req_cap.matches(prov_cap):
                    self._capability_map[req_cap.name] = provider
                    matched = True
                    break

        if not matched:
            raise CommonException(
                code="COMMON_CAPABILITY_NOT_FOUND",
                message=(
                    f"Service '{self.module_name}' requires capability "
                    f"'{req_cap}' but no provider found."
                ),
            )
```

---

## Testing Patterns

### Test Client Configuration

Test clients must be configured to let FastAPI handle exceptions (not bubble to test code):

```python
# conftest.py

@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync client - exceptions handled by FastAPI."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async client - exceptions handled by FastAPI."""
    transport = ASGITransport(
        app=app,
        raise_app_exceptions=False,  # Critical!
    )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

**Why `raise_*_exceptions=False`?**

- Ensures tests receive HTTP responses (4xx/5xx) not raw exceptions
- Matches production behavior exactly
- Allows testing error response format and status codes

### Testing Error Responses

```python
@pytest.mark.asyncio
async def test_symbol_not_found_returns_404(async_client: AsyncClient) -> None:
    """Test that unknown symbol returns proper error response."""
    response = await async_client.get("/api/v1/datafeed/resolve/INVALID_SYMBOL")

    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "PROVIDER_DATAFEED_SYMBOL_NOT_FOUND"
    assert "message" in data
    assert "INVALID_SYMBOL" in data["message"]


@pytest.mark.asyncio
async def test_invalid_topic_returns_400(async_client: AsyncClient) -> None:
    """Test that invalid topic format returns 400."""
    # Topic without colon separator
    response = await async_client.post(
        "/api/v1/datafeed/subscribe",
        json={"topic": "invalid_no_colon"}
    )

    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "SERVICE_DATAFEED_INVALID_TOPIC_FORMAT"


@pytest.mark.asyncio
async def test_auth_required_returns_401(async_client_no_auth: AsyncClient) -> None:
    """Test that missing auth returns 401."""
    response = await async_client_no_auth.get("/api/v1/broker/accounts")

    assert response.status_code == 401
```

### Testing WebSocket Errors

```python
def test_ws_invalid_subscription_closes_connection(client: TestClient) -> None:
    """Test that invalid WS subscription closes with proper code."""
    with client.websocket_connect("/api/v1/datafeed/ws") as ws:
        ws.send_json({
            "type": "subscribe",
            "payload": {"topic": "invalid"}
        })

        # Connection should close with error
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

        assert exc_info.value.code == 1003  # Unsupported Data
```

---

## Logging

### Single-Log Pattern

Each exception is logged exactly once, even in nested FastAPI app scenarios:

```python
def _log_exception(exc: TradingApiException, status_code: int, request: Request) -> None:
    # Prevent duplicate logging via request state
    if getattr(request.state, "_exception_logged", False):
        return
    setattr(request.state, "_exception_logged", True)

    # Log with appropriate level
    if status_code >= 500:
        logger.error(log_message)
    else:
        logger.warning(log_message)
```

### Log Levels

| Status Code | Level   | Rationale                                    |
| ----------- | ------- | -------------------------------------------- |
| 5xx         | ERROR   | Server errors requiring investigation        |
| 4xx         | WARNING | Client errors (expected in normal operation) |

### Project-Only Backtraces

Backtraces are filtered to show only project code, omitting external library frames:

```
[POST /api/v1/datafeed/resolve/INVALID --> 404: NOT_FOUND]
... omitted 12 frame(s) from external libraries ...
  File "/home/user/trader-pro/backend/src/trading_api/providers/tws/__init__.py", line 142, in get_symbol_info
    raise ProviderException(
  File "/home/user/trader-pro/backend/src/trading_api/modules/datafeed/api/v1.py", line 67, in resolve_symbol
    symbol_info = await self.service.resolve_ticker(symbol)
ProviderException: [PROVIDER_DATAFEED_SYMBOL_NOT_FOUND] Symbol not found: INVALID
```

### Suppressed Loggers

The `uvicorn.error` logger is suppressed to prevent duplicate "Exception in ASGI application" messages:

```python
# app_factory.py
logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
```

---

## Related Documentation

- [MODULAR_BACKEND_ARCHITECTURE.md](./MODULAR_BACKEND_ARCHITECTURE.md) - Exception handler registration in AppFactory
- [PROVIDER-SYSTEM.md](./PROVIDER-SYSTEM.md) - Provider exception patterns
- [BACKEND_TESTING.md](./BACKEND_TESTING.md) - Testing error responses
- [BACKEND_WEBSOCKETS.md](./BACKEND_WEBSOCKETS.md) - WebSocket error handling
