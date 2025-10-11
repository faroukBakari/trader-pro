# Trading API

[![CI](https://github.com/faroukBakari/trading-api/actions/workflows/ci.yml/badge.svg)](https://github.com/faroukBakari/trading-api/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/faroukBakari/trading-api/branch/main/graph/badge.svg)](https://codecov.io/gh/faroukBakari/trading-api)

A FastAPI-based trading API with Vue.js frontend, built with modern development practices.

## 🏗️ Project Structure

```
├── backend/          # FastAPI application
│   ├── src/         # Source code
│   ├── tests/       # Test files
│   └── pyproject.toml
├── frontend/        # Vue.js application
│   ├── src/         # Source code
│   └── package.json
├── .githooks/       # Git hooks for code quality
└── .github/         # CI/CD workflows
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11 with Poetry
- Node.js 20+ with npm
- Git
- **VS Code**: Recommended for best TypeScript/Python experience

### Setup

#### 1. Clone and Install Dependencies
```bash
# Clone the repository
git clone https://github.com/faroukBakari/trading-api.git
cd trading-api

# Install Git hooks and dependencies
make -f project.mk setup
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

See [WORKSPACE-SETUP.md](./WORKSPACE-SETUP.md) for details.

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

See [ENVIRONMENT-CONFIG.md](./ENVIRONMENT-CONFIG.md) for environment variable configuration.

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
# Run all tests
make -f project.mk test-all

# Backend only
make -C backend test

# Frontend only
cd frontend && npm run test:unit
```

### Code Quality
```bash
# Run all linters
make -f project.mk lint-all

# Format all code
make -f project.mk format-all

# Backend only
make -C backend lint-check
make -C backend format
```

## 📖 API Documentation

- **Interactive Docs**: http://localhost:${BACKEND_PORT:-8000}/docs
- **OpenAPI Spec**: http://localhost:${BACKEND_PORT:-8000}/openapi.json
- **ReDoc**: http://localhost:${BACKEND_PORT:-8000}/redoc

### Available Endpoints
- `GET /health` - Health check
- `GET /api/v1/version` - API version info
- `GET /` - Root API metadata

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

## 📁 Project Details

### Backend (`/backend`)
- **Framework**: FastAPI
- **Runtime**: Python 3.11
- **Testing**: pytest, pytest-asyncio, httpx
- **Code Quality**: Black, isort, Flake8, MyPy
- **Dependencies**: Poetry

### Frontend (`/frontend`)
- **Framework**: Vue 3 + TypeScript
- **Build Tool**: Vite
- **Testing**: Vitest + Vue Test Utils
- **Code Quality**: ESLint, Prettier
- **Dependencies**: npm

### Git Hooks (`/.githooks`)
- **Centralized**: Single source of truth for all hooks
- **Cross-platform**: Works on Windows, macOS, Linux
- **Fast**: Only checks changed files
- **Smart**: CI detection, easy bypass options

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