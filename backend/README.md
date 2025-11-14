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

The system includes a JWT-based authentication module with:

- Google OAuth integration
- Cookie-based session management (HttpOnly, Secure, SameSite=Strict)
- Refresh token rotation with device fingerprinting
- Stateless middleware for REST and WebSocket authentication

All broker and datafeed endpoints require authentication. See [auth module documentation](src/trading_api/modules/auth/README.md) for details.

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
