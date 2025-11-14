# Trading API Backend

FastAPI-based trading platform backend with modular architecture.

## Documentation

For comprehensive project documentation, see the [root README](../README.md) and the [docs/](../docs/) directory.

### Backend-Specific Documentation

- [Modular Architecture](docs/MODULAR_BACKEND_ARCHITECTURE.md) - Module system and ABC patterns
- [Backend Manager Guide](docs/BACKEND_MANAGER_GUIDE.md) - Multi-process deployment
- [Backend Testing](docs/BACKEND_TESTING.md) - Testing strategy and module isolation
- [WebSockets](docs/BACKEND_WEBSOCKETS.md) - FastWS integration
- [API Specs & Client Generation](docs/SPECS_AND_CLIENT_GEN.md) - Spec generation workflow
- [Modular Versioning](docs/MODULAR_VERSIONNING.md) - Module-level API versioning
- [WebSocket Router Generation](docs/WS_ROUTERS_GEN.md) - WS router code generation

## Architecture Overview

The backend implements a **modular factory-based architecture** with these key patterns:

- **Module ABC Pattern**: All feature modules (auth, broker, datafeed) extend the `Module` abstract base class
- **Application Factory**: Dynamic composition via `create_app()` with selective module loading
- **Multi-Process Deployment**: Production mode runs modules in separate processes with nginx gateway
- **Module Registry**: Centralized management with auto-discovery

**Key Benefits**:

- Independent module development and testing
- Selective deployment (e.g., only broker module)
- Horizontal scaling (modules in separate processes)

See [Modular Architecture](docs/MODULAR_BACKEND_ARCHITECTURE.md) for complete details.

### Authentication Module

The system includes a JWT-based authentication module providing secure, stateless authentication for all endpoints:

**Architecture:**

- **Google OAuth Integration**: Verify Google ID tokens via `authlib`
- **JWT Access Tokens**: RS256-signed tokens with 5-minute expiry
- **Cookie-Based Sessions**: HttpOnly, Secure, SameSite=Strict cookies for XSS protection
- **Refresh Token Rotation**: Device fingerprinting with bcrypt hashing
- **Stateless Middleware**: Public key validation (no database queries)
- **WebSocket Authentication**: Automatic via cookies (no query params)

**Key Features:**

✅ All broker and datafeed endpoints require authentication  
✅ Type-safe JWT payload with `UserData` model  
✅ In-memory storage (MVP) with PostgreSQL/Redis migration path  
✅ Comprehensive test coverage (92 tests, 100% passing)  
✅ Independent module (follows standard modular pattern)

**Documentation:**

- **Module Details**: [Auth Module README](src/trading_api/modules/auth/README.md)
- **Implementation Guide**: [Authentication System Documentation](../docs/AUTHENTICATION.md)
- **Middleware**: Shared middleware in `shared/middleware/auth.py`
- **Models**: JWT and user models in `models/auth/`

**Quick Start:**

```bash
# Start backend with auth module
make dev

# Test authentication endpoints
curl http://localhost:8000/api/v1/auth/health
```

### Protecting Endpoints with Authentication

All endpoints outside the auth module require authentication via dependency injection.

**REST Endpoints:**

```python
from typing import Annotated
from fastapi import Depends
from trading_api.models.auth import UserData
from trading_api.shared.middleware.auth import get_current_user

@router.get("/orders")
async def get_orders(
    user_data: Annotated[UserData, Depends(get_current_user)]
) -> list[Order]:
    """Get orders for authenticated user."""
    # user_data contains: user_id, email, full_name, picture, device_fingerprint
    return await service.get_user_orders(user_data.user_id)
```

**WebSocket Endpoints:**

```python
from trading_api.shared.middleware.auth import get_current_user_ws

@router.on_connect
async def authenticate(
    client: Client,
    user_data: Annotated[UserData, Depends(get_current_user_ws)]
):
    """Authenticate WebSocket connection."""
    client.state["user_data"] = user_data
```

**Key Points:**

- ✅ Middleware validates JWT from cookie (no manual extraction)
- ✅ Middleware uses public key only (stateless, no DB queries)
- ✅ `UserData` model provides type-safe access to user info
- ✅ WebSocket authentication automatic via cookies
- ✅ Same middleware for REST and WebSocket
- ✅ 401/403 errors handled automatically

See [Authentication Documentation](../docs/AUTHENTICATION.md) for complete implementation details.

## Quick Start

```bash
# From project root
make -f project.mk install

# Run backend in dev mode
cd backend
make dev
```

## Development Workflows

### Single Module Development

```bash
# Start only the auth module
ENABLED_MODULES=auth make dev

# Start only the broker module
ENABLED_MODULES=broker make dev

# Start only the datafeed module
ENABLED_MODULES=datafeed make dev

# Start all modules (default)
make dev
```

### Multi-Process Development

```bash
# Start all modules in separate processes with nginx gateway
make backend-dev-multi

# Check status
make backend-status

# View logs
make backend-logs

# Stop all processes
make backend-stop
```

See [Backend Manager Guide](docs/BACKEND_MANAGER_GUIDE.md) for complete commands.

### Spec Generation & Client Updates

```bash
# Generate OpenAPI/AsyncAPI specs and Python clients
make generate

# Generate specs only (no clients)
make generate-specs
```

See [API Specs & Client Generation](docs/SPECS_AND_CLIENT_GEN.md) for details.

## Testing

### Run All Tests

```bash
# All tests
make test

# With coverage
make test-coverage
```

### Module-Specific Testing

```bash
# Test specific modules only
make test-modules modules=broker,datafeed

# Test single module
make test-modules modules=broker
```

### Test Organization

- `tests/` - Root integration tests (cross-module scenarios)
- `tests/integration/` - Full-stack integration tests
- `src/trading_api/modules/*/tests/` - Module-specific tests
- `src/trading_api/shared/tests/` - Shared infrastructure tests

Tests use **factory-based fixtures** for module isolation. See [Backend Testing](docs/BACKEND_TESTING.md) for strategy details.

## Development

This backend uses:

- **FastAPI** for REST API and WebSocket endpoints
- **Poetry** for dependency management
- **Pytest** for testing
- **Type checking** with mypy and pyright

See [DEVELOPMENT.md](../docs/DEVELOPMENT.md) for detailed development guidelines.
