# Trading API

A FastAPI-based trading API server with **hybrid OpenAPI + AsyncAPI architecture** for both REST and real-time WebSocket communication.

## 🚀 Features

- **REST API** (OpenAPI) - Traditional HTTP endpoints for CRUD operations
- **WebSocket API** (AsyncAPI) - Real-time market data streaming
- **API Versioning** - Backwards compatibility and smooth migrations
- **Type Safety** - Full TypeScript client generation
- **TDD Approach** - Test-driven development practices
- **Auto Documentation** - Interactive API docs for both REST and WebSocket

## 📚 Documentation

- **[WebSocket Implementation Guide](WEBSOCKET-README.md)** - Complete WebSocket & AsyncAPI architecture
- **[AsyncAPI Generator Guide](ASYNCAPI-GENERATOR.md)** - Client generation and frontend integration
- **[Versioning Guide](docs/versioning.md)** - API version management

## Quick Start

### Prerequisites
- Python 3.10+
- Poetry (recommended) or pip

### Installation

Using Poetry:
```bash
poetry config virtualenvs.in-project true
poetry install
poetry shell
```

Using pip:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Running the API

#### Using Make (Recommended)
```bash
# Start development server with real-time data feeds
make dev

# Run tests
make test

# Check health
make health
```

#### Manual Start
```bash
poetry run uvicorn trading_api.main:app --reload
```

#### WebSocket Testing
```bash
# Test WebSocket connection with wscat
npm install -g wscat
wscat -c ws://localhost:8000/api/v1/ws/v1

# Send subscription
{"type": "subscribe", "channel": "market_data", "symbol": "AAPL"}
```

### Running Tests

```bash
poetry run pytest
```

### API Documentation

The Trading API supports both REST and WebSocket endpoints with full documentation.

**Current Version**: v1 (stable)

Once the server is running, visit:

#### REST API (OpenAPI)
- **API Root**: http://127.0.0.1:8000/ - API information and version details
- **Interactive docs**: http://127.0.0.1:8000/api/v1/docs
- **ReDoc**: http://127.0.0.1:8000/api/v1/redoc
- **OpenAPI spec**: http://127.0.0.1:8000/api/v1/openapi.json

#### WebSocket API (AsyncAPI)
- **WebSocket endpoint**: ws://127.0.0.1:8000/api/v1/ws/v1
- **AsyncAPI spec**: http://127.0.0.1:8000/api/v1/asyncapi.yaml
- **WebSocket config**: http://127.0.0.1:8000/api/v1/ws/config
- **Connection stats**: http://127.0.0.1:8000/api/v1/ws/stats

#### Health & Versioning
- **Health check**: http://127.0.0.1:8000/api/v1/health
- **Version info**: http://127.0.0.1:8000/api/v1/versions

### API Versioning

The API uses URL-based versioning with the following strategy:

- **Current version**: `/api/v1/` (stable)
- **Future version**: `/api/v2/` (planned with breaking changes)

#### Version Information Endpoints

```bash
# Get all available versions
GET /api/v1/versions

# Get current version info
GET /api/v1/version

# Health check with version info
GET /api/v1/health
```

#### Breaking Changes Planning

Version 2 (v2) will include:
- Authentication required for all endpoints
- New response format for error messages
- Renamed health endpoint to status

#### Versioning Best Practices

1. **Always specify version** in your API calls
2. **Monitor deprecation notices** via `/api/v1/versions`
3. **Test against new versions** before they become stable
4. **Update clients** before old versions sunset

### Client Generation

Generate typed clients for different platforms:

```bash
# Generate all clients (Vue.js TypeScript + Python)
make clients

# Or use the script directly
./scripts/generate-clients.sh
```

**Vue.js/TypeScript Client:**
```bash
# Install the generated client in your Vue.js project
cd clients/vue-client
npm install
# Copy the generated files to your Vue.js project
```

**Python Client:**
```bash
# Install the generated Python client
pip install ./clients/python-client
```

## Development

This project follows Test Driven Development (TDD) practices:
1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green

### Code Quality

We use:
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking
- pre-commit for git hooks

## Project Structure

```
backend/
├── src/trading_api/
│   ├── main.py                    # FastAPI app with REST + WebSocket
│   ├── api/
│   │   ├── health.py             # Health check endpoints
│   │   ├── versions.py           # API versioning
│   │   ├── datafeed.py           # Market data REST API
│   │   └── websockets.py         # WebSocket endpoints
│   └── core/
│       ├── websocket_models.py   # WebSocket message models
│       ├── websocket_manager.py  # Connection management
│       ├── realtime_service.py   # Mock data generators
│       ├── datafeed_service.py   # Market data service
│       └── versioning.py         # Version management
├── tests/
│   ├── test_health.py
│   └── test_versioning.py
├── asyncapi.yaml                 # AsyncAPI 3.0 specification
├── pyproject.toml               # Poetry dependencies
├── Makefile                     # Development commands
├── WEBSOCKET-README.md          # WebSocket implementation guide
├── ASYNCAPI-GENERATOR.md        # Client generation guide
└── README.md
```
