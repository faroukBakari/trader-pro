# Trading API

[![CI](https://github.com/faroukBakari/trading-api/actions/workflows/ci.yml/badge.svg)](https://github.com/faroukBakari/trading-api/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/faroukBakari/trading-api/branch/main/graph/badge.svg)](https://codecov.io/gh/faroukBakari/trading-api)

A modern full-stack trading platform with FastAPI backend and Vue.js frontend. Features REST API for traditional request/response operations and WebSocket streaming for real-time market data updates.

## 🏗️ Project Structure

```
trader-pro/
├── backend/              # Modular FastAPI backend
│   ├── src/
│   │   └── trading_api/
│   │       ├── modules/          # Pluggable feature modules
│   │       │   ├── broker/       # Trading operations module
│   │       │   └── datafeed/     # Market data module
│   │       ├── shared/           # Module interface, registry, core infrastructure
│   │       │   ├── module_interface.py  # Module ABC
│   │       │   ├── module_registry.py   # Module management
│   │       │   └── api/          # Shared API routers (health, versioning)
│   │       ├── models/           # Centralized Pydantic models
│   │       └── app_factory.py    # Application factory for dynamic composition
│   ├── scripts/
│   │   └── backend_manager.py    # Multi-process orchestration
│   ├── dev-config.yaml           # Deployment configuration
│   ├── tests/                    # Integration tests
│   └── pyproject.toml
├── frontend/             # Vue.js application
│   ├── src/             # Source code
│   └── package.json
├── docs/                # Project-wide documentation
├── .githooks/           # Git hooks for code quality
└── .github/             # CI/CD workflows
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 with Poetry
- Node.js 22.20+ with npm
- Git
- **VS Code**: Recommended for best TypeScript/Python experience

### Setup

#### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/faroukBakari/trading-api.git
cd trading-api

# Install dependencies (includes Git hooks)
make -f project.mk install
```

#### 2. Open in VS Code (Recommended)

```bash
# Open the multi-root workspace for proper TypeScript/Python support
code trader-pro.code-workspace
```

**Why use the workspace file?**

- ✅ Proper TypeScript resolution for frontend
- ✅ Correct Python environment detection for backend
- ✅ No `import.meta` errors
- ✅ Better IntelliSense and debugging

See [WORKSPACE-SETUP.md](./docs/WORKSPACE-SETUP.md) for details.

### Development

```bash
# Start backend (terminal 1)
make -f project.mk dev-backend

# Start frontend (terminal 2)
make -f project.mk dev-frontend
```

- Backend: http://localhost:${BACKEND_PORT:-8000}
- Frontend: http://localhost:${FRONTEND_PORT:-5173}
- API Docs: http://localhost:${BACKEND_PORT:-8000}/docs

See [ENVIRONMENT-CONFIG.md](./docs/ENVIRONMENT-CONFIG.md) for environment variable configuration.

**Module-Specific Development** (Backend):

```bash
# Start only specific modules
ENABLED_MODULES=broker make -f project.mk dev-backend

# Multi-process mode (production-like)
make -C backend backend-dev-multi
```

See [docs/FULLSTACK-DEV-MODE.md](docs/FULLSTACK-DEV-MODE.md) for watch system and [backend/docs/BACKEND_MANAGER_GUIDE.md](backend/docs/BACKEND_MANAGER_GUIDE.md) for multi-process deployment.

## 🔧 Development

### Git Hooks

Automatic code quality checks run on every commit:

- **Backend**: Black, isort, Flake8, MyPy, pytest
- **Frontend**: ESLint, Prettier, TypeScript, Vitest
- **All files**: Whitespace, merge conflicts, syntax

```bash
# Install hooks (one-time setup)
make -f project.mk install-hooks

# Skip hooks temporarily
git commit --no-verify
```

### Testing

```bash
# Run all tests (auto-generates API clients for frontend)
make -f project.mk test-all

# Backend only
make -C backend test

# Frontend only (auto-generates clients)
cd frontend && npm run test:unit
```

**Note**: Frontend tests automatically generate API clients from the backend's OpenAPI spec before running.

### Code Quality

```bash
# Run all linters
make -f project.mk lint-all

# Format all code
make -f project.mk format-all

# Backend only
make -C backend type-check
make -C backend format
```

## 📖 Documentation

### Core Documentation

- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and design
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflows and setup
- **[Testing Strategy](docs/TESTING.md)** - Testing approach and best practices
- **[Client Generation](docs/CLIENT-GENERATION.md)** - API client auto-generation
- **[WebSocket Clients](docs/WEBSOCKET-CLIENTS.md)** - Real-time WebSocket implementation

### API Documentation

- **Interactive Docs**: http://localhost:${BACKEND_PORT:-8000}/api/v1/docs
- **AsyncAPI Docs**: http://localhost:${BACKEND_PORT:-8000}/api/v1/ws/asyncapi
- **Backend Details**: See [backend/docs/](backend/docs/)

### Quick Links

- REST API: http://localhost:${BACKEND_PORT:-8000}/api/v1/openapi.json
- WebSocket: ws://localhost:${BACKEND_PORT:-8000}/api/v1/ws
- Frontend: http://localhost:${FRONTEND_PORT:-5173}

## 🏃‍♂️ CI/CD

The project uses GitHub Actions for continuous integration:

### Workflows

- **Backend**: Python 3.11, Poetry, pytest, linting
- **Frontend**: Node.js 20-22, npm, ESLint, Vitest, build
- **Integration**: End-to-end API tests, frontend build against live API

### Quality Gates

- All tests must pass
- Code coverage reporting
- Linting and formatting checks
- Type checking (MyPy + TypeScript)
- Build verification

## 📁 Technology Stack

### Backend

- **Framework**: FastAPI 0.104+ (REST) + FastWS 0.1.7 (WebSocket)
- **Architecture**: Modular factory-based with ABC protocol (pluggable modules, selective deployment)
- **Runtime**: Python 3.11+ with Uvicorn ASGI server
- **Dependencies**: Poetry for package management
- **Testing**: pytest + pytest-asyncio + httpx TestClient
- **Code Quality**: Black, isort, Flake8, MyPy + pre-commit hooks

### Frontend

- **Framework**: Vue 3 + Composition API + TypeScript
- **Build**: Vite 7+ (fast ES build tool)
- **Dependencies**: npm with Node.js 22.20+
- **Testing**: Vitest + Vue Test Utils + jsdom
- **Code Quality**: ESLint + Prettier + pre-commit hooks

### DevOps

- **CI/CD**: GitHub Actions with parallel job execution
- **Testing**: Multi-tier (unit, integration, smoke, e2e)
- **Git Hooks**: Automated code quality and testing
- **Workspace**: VS Code multi-root workspace support

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for complete technical details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run the hooks: `make lint && make test`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Setup for Contributors

```bash
# After cloning
make -f project.mk setup    # Install all dependencies and hooks
make -f project.mk dev-backend    # Start backend server
make -f project.mk dev-frontend   # Start frontend server
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue.js Documentation](https://vuejs.org/)
- [Poetry Documentation](https://python-poetry.org/)
- [Vite Documentation](https://vitejs.dev/)
