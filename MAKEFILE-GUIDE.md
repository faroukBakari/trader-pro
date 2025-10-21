# Makefile Structure Guide

Consistent Makefile-based build system across all components.

## Philosophy

- **Consistency**: CI uses same `make` commands as local development
- **Simplicity**: Memorable targets for common tasks
- **Composability**: Project-level delegates to component Makefiles
- **Documentation**: Every Makefile has `help` target

## Hierarchy

```
project.mk              # Project-wide orchestration
├── backend/Makefile    # Backend-specific targets
└── frontend/Makefile   # Frontend-specific targets
```

## Project Commands

**Location**: `project.mk` at repository root

```bash
make -f project.mk help              # View all targets

# Setup
make -f project.mk setup             # Full setup (hooks + deps)
make -f project.mk install-all       # Install all dependencies

# Development
make -f project.mk dev-fullstack     # Start full stack (recommended)
make -f project.mk dev-backend       # Backend only
make -f project.mk dev-frontend      # Frontend only

# Code Generation
make -f project.mk generate-ws-routers        # WebSocket routers
make -f project.mk generate-openapi-client    # REST client
make -f project.mk generate-asyncapi-types    # WS types

# Quality
make -f project.mk test-all          # Run all tests
make -f project.mk lint-all          # Run all linters
make -f project.mk format-all        # Format all code
make -f project.mk build-all         # Build everything
```

## Backend Commands

**Location**: `backend/Makefile`

```bash
cd backend

# Development
make ensure-python     # Check Python 3.11+ (offers auto-install)
make ensure-poetry     # Ensure Poetry installed
make install           # Install dependencies
make dev               # Start dev server (checks port)

# Testing
make test              # Run tests
make test-cov          # Tests with coverage

# Quality
make lint              # Flake8
make lint-check        # All linters (black, isort, flake8, mypy)
make format            # Format with black + isort

# Build
make build             # Build package
make clean             # Clean artifacts

# API
make health            # Check API health
make clients           # Generate clients
make export-openapi    # Export OpenAPI spec
```

## Frontend Commands

**Location**: `frontend/Makefile`

```bash
cd frontend

# Development
make ensure-node       # Check Node.js 22.20+
make install           # Install dependencies
make dev               # Start dev server

# Testing
make test              # Tests in watch mode
make test-ci           # Tests once (CI)

# Quality
make lint              # ESLint
make lint-fix          # ESLint with auto-fix
make format            # Prettier format
make type-check        # TypeScript check

# Build
make build             # Production build
make preview           # Preview production build
make clean             # Clean artifacts

# API Clients
make generate-openapi-client    # Generate REST client
make generate-asyncapi-types    # Generate WS types
```

## CI-Specific Targets

Non-interactive versions for CI/CD:

```bash
# Backend
make ensure-python-ci  # Auto-install Python (no prompts)
make install-ci        # Non-interactive install
make dev-ci            # Background server
make health-ci         # Health check (fail on error)

# Frontend
make install-ci        # Uses npm ci
```

## Common Workflows

### Initial Setup
```bash
make -f project.mk setup  # Installs hooks + all dependencies
```

### Daily Development
```bash
make -f project.mk dev-fullstack  # One command, full stack
```

### Before Commit
```bash
make -f project.mk lint-all format-all test-all
```

### CI Pipeline
```bash
make -f project.mk install-all
make -f project.mk lint-all
make -f project.mk test-all
make -f project.mk build-all
```

## Tips

- Use `make help` in any directory to see available targets
- Add `-f project.mk` when running from root
- Most targets check dependencies (Python, Node, Poetry, etc.)
- CI targets are non-interactive and fail fast
