# Trading API

FastAPI backend that powers the Trading Pro platform. It exposes a RESTful API for health reporting, API versioning, and TradingView-compatible market data.

## Features

- REST API with typed responses generated from FastAPI + Pydantic models
- WebSocket real-time streaming with FastWS and AsyncAPI documentation
- Built-in market datafeed service compatible with the TradingView UDF contract
- Versioned API surface (`/api/v1`) with pluggable future versions
- Automatic OpenAPI + AsyncAPI generation for client tooling and contract tests
- Test-driven development workflow with pytest and FastAPI TestClient

## Documentation

- `ARCHITECTURE.md` – end-to-end system architecture
- `docs/versioning.md` – API versioning strategy and lifecycle
- `docs/websockets.md` – WebSocket real-time data streaming guide
- `backend/README.md` (this file) – backend setup and reference
- `frontend/CLIENT-GENERATION.md` – TypeScript client generation that consumes the backend OpenAPI spec
- `MAKEFILE-GUIDE.md` – consolidated command reference for the whole project

## Quick Start

### Prerequisites

- **Python 3.11+** (required by the project)
  - Will be **automatically installed** if you have [pyenv](https://github.com/pyenv/pyenv)
  - Or check version: `python3 --version`
  - Manual install: `pyenv install 3.11 && pyenv local 3.11`
- [Poetry](https://python-poetry.org/) for dependency management (auto-installed if missing)

### Install dependencies

```bash
cd backend
make install       # Validates Python 3.11+, offers to install if needed, then installs dependencies
```

The `make install` command will:

1. **Check Python version** - Validates Python 3.11+ is available
2. **Auto-install Python** - If wrong version and pyenv is available, **offers to install Python 3.11.7** (with confirmation)
3. **Install Poetry** - Automatically installs Poetry if missing
4. **Install dependencies** - Runs `poetry install` to set up the project

**Interactive prompts:**

- If Python 3.11+ is not found and pyenv is available, you'll be asked: `"Would you like to install Python 3.11.7 via pyenv? [y/N]"`
- Type `y` and press Enter to automatically install and activate Python 3.11.7
- Type `n` to skip and see manual installation instructions

Alternatively, check prerequisites manually:

```bash
make ensure-python  # Check Python version
make ensure-poetry  # Ensure Poetry is installed
poetry install      # Install dependencies
```

### Run the API locally

```bash
# Start the development server on http://localhost:8000
make dev

# Or start without debug tooling
make dev-no-debug

# Manual start (inside Poetry shell)
poetry run uvicorn "trading_api.main:$BACKEND_APP_NAME" --reload
```

### Run tests and quality checks

```bash
make test              # pytest -v
make lint              # flake8
make lint-check        # black --check + isort --check-only + flake8 + mypy
make format            # black + isort
```

## API Surface

The backend publishes OpenAPI and AsyncAPI documentation at startup. After running the dev server, visit:

### REST API Documentation

- Root metadata: `http://127.0.0.1:8000/`
- Interactive docs (Swagger UI): `http://127.0.0.1:8000/api/v1/docs`
- ReDoc: `http://127.0.0.1:8000/api/v1/redoc`
- Raw OpenAPI JSON: `http://127.0.0.1:8000/api/v1/openapi.json`

### WebSocket API Documentation

- AsyncAPI Interactive UI: `http://127.0.0.1:8000/api/v1/ws/asyncapi`
- Raw AsyncAPI JSON: `http://127.0.0.1:8000/api/v1/ws/asyncapi.json`
- WebSocket endpoint: `ws://127.0.0.1:8000/api/v1/ws`

### Key REST Endpoints

| Path                                | Method | Description                                         |
| ----------------------------------- | ------ | --------------------------------------------------- |
| `/api/v1/health`                    | GET    | Service health heartbeat including version metadata |
| `/api/v1/versions`                  | GET    | List of supported API versions                      |
| `/api/v1/version`                   | GET    | Details about the active API version                |
| `/api/v1/datafeed/config`           | GET    | TradingView configuration contract                  |
| `/api/v1/datafeed/search`           | GET    | Symbol search                                       |
| `/api/v1/datafeed/resolve/{symbol}` | GET    | Symbol metadata                                     |
| `/api/v1/datafeed/bars`             | GET    | Historical OHLC data                                |
| `/api/v1/datafeed/quotes`           | POST   | Latest quote snapshot for multiple symbols          |
| `/api/v1/datafeed/health`           | GET    | Datafeed service diagnostics                        |

### WebSocket Operations

| Operation          | Type    | Description                                     |
| ------------------ | ------- | ----------------------------------------------- |
| `bars.subscribe`   | SEND    | Subscribe to real-time bar updates for a symbol |
| `bars.unsubscribe` | SEND    | Unsubscribe from bar updates                    |
| `bars.update`      | RECEIVE | Real-time OHLC bar data broadcast               |

See `docs/websockets.md` for detailed WebSocket documentation.

## Bar Broadcasting (Real-Time Mocked Data)

The API includes an optional background service that broadcasts mocked bar data to WebSocket clients:

### Quick Start

```bash
# Default: Enabled, 2s interval, AAPL/GOOGL/MSFT, 1-min resolution
make dev

# Custom configuration
export BAR_BROADCASTER_INTERVAL=1.0
export BAR_BROADCASTER_SYMBOLS=AAPL,TSLA,BTC
export BAR_BROADCASTER_RESOLUTIONS=1,5,D
make dev

# Disable broadcaster
export BAR_BROADCASTER_ENABLED=false
make dev
```

### Environment Variables

| Variable                      | Default           | Description                   |
| ----------------------------- | ----------------- | ----------------------------- |
| `BAR_BROADCASTER_ENABLED`     | `true`            | Enable/disable broadcaster    |
| `BAR_BROADCASTER_INTERVAL`    | `2.0`             | Broadcast interval in seconds |
| `BAR_BROADCASTER_SYMBOLS`     | `AAPL,GOOGL,MSFT` | Comma-separated symbols       |
| `BAR_BROADCASTER_RESOLUTIONS` | `1`               | Comma-separated resolutions   |

### Features

- ✅ **Automatic**: Starts with the application
- ✅ **Efficient**: Only broadcasts to topics with subscribers
- ✅ **Metrics**: Track broadcasts_sent, broadcasts_skipped, errors
- ✅ **Realistic Data**: Uses `DatafeedService.mock_last_bar()` for variations
- ✅ **Configurable**: Full control via environment variables

See `docs/websockets.md` (Bar Broadcasting Service section) for details.

## API Versioning

- Current stable surface: `/api/v1`
- Future major versions are announced through `/api/v1/versions`
- Version metadata is defined in `src/trading_api/core/versioning.py`
- Planned `v2` changes (authentication, error payloads, renamed health endpoint) are tracked but not yet exposed

## Client Generation

- The OpenAPI specification is regenerated on application startup and saved to `backend/openapi.json`
- Frontend consumers run `make generate-openapi-client` and `make generate-asyncapi-types` (defined in Makefiles)
- For ad-hoc exports use `make export-openapi`

## Development Workflow

1. Write a failing test in `backend/tests`
2. Implement the minimal change under `src/trading_api`
3. Keep imports tidy and run formatters via `make format`
4. Use `make lint-check` before raising a pull request

## Project Layout

```
backend/
├── Makefile
├── pyproject.toml
├── src/trading_api/
│   ├── __init__.py
│   ├── main.py                # FastAPI + FastWS application factory
│   ├── api/
│   │   ├── datafeed.py        # TradingView-compatible REST endpoints
│   │   ├── health.py          # Service heartbeat
│   │   └── versions.py        # API version catalogue
│   ├── ws/
│   │   ├── __init__.py        # WebSocket module exports
│   │   └── datafeed.py        # Real-time bar operations
│   ├── plugins/
│   │   └── fastws_adapter.py  # FastWS integration adapter
│   ├── core/
│   │   ├── bar_broadcaster.py     # Background bar broadcasting service
│   │   ├── config.py              # Application configuration
│   │   ├── datafeed_service.py    # In-memory market data provider
│   │   ├── response_validation.py # FastAPI response model guardrails
│   │   └── versioning.py          # Version metadata and helpers
│   └── models/
│       ├── __init__.py
│       ├── common.py          # BaseApiResponse, SubscriptionResponse
│       └── market/
│           ├── bars.py        # Bar, BarsSubscriptionRequest
│           ├── configuration.py
│           ├── instruments.py
│           ├── quotes.py
│           └── search.py
├── external_packages/
│   └── fastws/                # FastWS framework (vendored)
├── tests/
│   ├── test_api_health.py
│   ├── test_api_versioning.py
│   └── test_ws_datafeed.py    # WebSocket integration tests
├── docs/
│   ├── versioning.md
│   └── websockets.md          # WebSocket streaming guide
└── README.md
```

## Troubleshooting

- Ensure the Poetry environment is activated (`poetry shell`) before running manual commands
- `make lint-response-models` validates that every FastAPI route declares a response model (used in CI)
- Regenerate the OpenAPI file manually with `make export-openapi` if frontend tooling requires a fresh contract without starting the server

## Next Steps

- Track API changes in `docs/versioning.md`
- Coordinate with the frontend when updating models so that TypeScript clients remain in sync
