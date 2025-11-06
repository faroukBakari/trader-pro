# Trading API Backend

FastAPI-based trading platform backend with modular architecture.

## Documentation

For comprehensive project documentation, see the [root README](../README.md) and the [docs/](../docs/) directory.

### Backend-Specific Documentation

- [Backend Manager Guide](docs/BACKEND_MANAGER_GUIDE.md)
- [Backend Testing](docs/BACKEND_TESTING.md)
- [Modular Architecture](docs/MODULAR_BACKEND_ARCHITECTURE.md)
- [WebSockets](docs/BACKEND_WEBSOCKETS.md)
- [API Specs & Client Generation](docs/SPECS_AND_CLIENT_GEN.md)

## Quick Start

```bash
# From project root
make -f project.mk install

# Run backend in dev mode
cd backend
make dev
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage
```

## Development

This backend uses:

- **FastAPI** for REST API and WebSocket endpoints
- **Poetry** for dependency management
- **Pytest** for testing
- **Type checking** with mypy and pyright

See [DEVELOPMENT.md](../docs/DEVELOPMENT.md) for detailed development guidelines.
