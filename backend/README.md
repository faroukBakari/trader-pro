# Trading API

FastAPI backend that powers the Trading Pro platform. It exposes a RESTful API for health reporting, API versioning, and TradingView-compatible market data.

## Features

- REST API with typed responses generated from FastAPI + Pydantic models
- Built-in market datafeed service compatible with the TradingView UDF contract
- Versioned API surface (`/api/v1`) with pluggable future versions
- Automatic OpenAPI generation for client tooling and contract tests
- Test-driven development workflow with pytest and FastAPI TestClient

## Documentation

- `ARCHITECTURE.md` – end-to-end system architecture
- `docs/versioning.md` – API versioning strategy and lifecycle
- `backend/README.md` (this file) – backend setup and reference
- `frontend/CLIENT-GENERATION.md` – TypeScript client generation that consumes the backend OpenAPI spec
- `MAKEFILE-GUIDE.md` – consolidated command reference for the whole project

## Quick Start

### Prerequisites
- Python 3.11
- [Poetry](https://python-poetry.org/) for dependency management

### Install dependencies

```bash
cd backend
make install       # runs poetry install
```

Alternatively, run Poetry manually:

```bash
poetry install
```

### Run the API locally

```bash
# Start the development server on http://localhost:8000
make dev

# Or start without debug tooling
make dev-no-debug

# Manual start (inside Poetry shell)
poetry run uvicorn trading_api.main:app --reload
```

### Run tests and quality checks

```bash
make test              # pytest -v
make lint              # flake8
make lint-check        # black --check + isort --check-only + flake8 + mypy
make format            # black + isort
```

## API Surface

The backend publishes an OpenAPI document at startup. After running the dev server, visit:

- Root metadata: `http://127.0.0.1:8000/`
- Interactive docs (Swagger UI): `http://127.0.0.1:8000/api/v1/docs`
- ReDoc: `http://127.0.0.1:8000/api/v1/redoc`
- Raw OpenAPI JSON: `http://127.0.0.1:8000/api/v1/openapi.json`

### Key endpoints

| Path | Method | Description |
| ---- | ------ | ----------- |
| `/api/v1/health` | GET | Service health heartbeat including version metadata |
| `/api/v1/versions` | GET | List of supported API versions |
| `/api/v1/version` | GET | Details about the active API version |
| `/api/v1/datafeed/config` | GET | TradingView configuration contract |
| `/api/v1/datafeed/search` | GET | Symbol search |
| `/api/v1/datafeed/resolve/{symbol}` | GET | Symbol metadata |
| `/api/v1/datafeed/bars` | GET | Historical OHLC data |
| `/api/v1/datafeed/quotes` | POST | Latest quote snapshot for multiple symbols |
| `/api/v1/datafeed/health` | GET | Datafeed service diagnostics |

## API Versioning

- Current stable surface: `/api/v1`
- Future major versions are announced through `/api/v1/versions`
- Version metadata is defined in `src/trading_api/core/versioning.py`
- Planned `v2` changes (authentication, error payloads, renamed health endpoint) are tracked but not yet exposed

## Client Generation

- The OpenAPI specification is regenerated on application startup and saved to `backend/openapi.json`
- Frontend consumers run `npm run client:generate` (defined in `frontend/package.json`) which uses `frontend/scripts/generate-client.sh`
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
│   ├── main.py                # FastAPI application factory & OpenAPI writer
│   ├── api/
│   │   ├── datafeed.py        # TradingView-compatible endpoints
│   │   ├── health.py          # Service heartbeat
│   │   └── versions.py        # API version catalogue
│   ├── core/
│   │   ├── datafeed_service.py    # In-memory market data provider
│   │   ├── response_validation.py # FastAPI response model guardrails
│   │   └── versioning.py          # Version metadata and helpers
│   └── models/
│       ├── __init__.py
│       ├── common.py
│       └── market/
│           ├── bars.py
│           ├── configuration.py
│           ├── instruments.py
│           ├── quotes.py
│           └── search.py
├── tests/
│   ├── test_health.py
│   └── test_versioning.py
├── docs/
│   └── versioning.md
└── README.md
```

## Troubleshooting

- Ensure the Poetry environment is activated (`poetry shell`) before running manual commands
- `make lint-response-models` validates that every FastAPI route declares a response model (used in CI)
- Regenerate the OpenAPI file manually with `make export-openapi` if frontend tooling requires a fresh contract without starting the server

## Next Steps

- Track API changes in `docs/versioning.md`
- Coordinate with the frontend when updating models so that TypeScript clients remain in sync
