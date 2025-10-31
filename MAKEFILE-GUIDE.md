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
make -f project.mk kill-dev          # Kill all dev servers (frontend + backend)

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
make install           # Install dependencies (checks Python/Poetry, optional nginx)
make dev               # Start dev server (checks port)
make kill-dev          # Kill backend dev server (port 8000)

# Testing
make test              # Run tests
make test-cov          # Tests with coverage

# Quality
make lint              # Flake8 only
make lint-check        # All linters + type checkers (black, isort, flake8, mypy, pyright)
make format            # Format with black + isort

# Build
make build             # Build package
make clean             # Clean artifacts

# Multi-Process Backend (Development)
make backend-manager-start          # Start multi-process backend with nginx
make backend-manager-stop           # Stop all backend processes
make backend-manager-status         # Show process status and health
make backend-manager-restart        # Restart all processes
make backend-manager-gen-nginx-conf # Generate nginx config (debug)

# Logging
make logs-tail                      # Tail unified backend log (all servers with prefixes)
make logs-tail-nginx                # Tail nginx logs (access + error)
make logs-clean                     # Clean all backend log files

# API
make generate-python-clients   # Generate HTTP clients (includes format & validation)
make export-openapi-spec       # Export OpenAPI spec
make export-asyncapi-spec      # Export AsyncAPI spec
make validate-package-names    # Validate client package names
```

### Module-Specific Targets

```bash
cd backend

# Package Name Validation
make validate-package-names   # Validate client package names
                              # Checks uniqueness and module correspondence
                              # Runs automatically before client generation
                              # OpenAPI: @trader-pro/client-{module}
                              # AsyncAPI: ws-types-{module}
                              # Python: {Module}Client

# Python HTTP Client Generation
make generate-python-clients  # Generate type-safe HTTP clients
                              # Automatically validates, formats, and type-checks
                              # Used for inter-module communication

# WebSocket Router Generation
make generate-ws-routers      # Generate concrete WS router classes
make watch-ws-routers         # Watch and auto-regenerate routers
make verify-ws-routers        # Verify all routers are up-to-date

# Import Boundary Validation
make test-boundaries          # Verify module import boundaries
                              # Enforces: modules → shared/models only
                              # Prevents: cross-module imports
```

**Note**: WebSocket router generation is critical for maintaining type safety. See `backend/src/trading_api/shared/ws/WS-ROUTER-GENERATION.md` for details.

## Frontend Commands

**Location**: `frontend/Makefile`

```bash
cd frontend

# Development
make ensure-node       # Check Node.js 22.20+
make install           # Install dependencies
make dev               # Start dev server
make kill-dev          # Kill frontend dev server (port 5173)

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
make install-ci        # Non-interactive install (checks Python/Poetry, skips nginx)
make dev-ci            # Background server

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

### Stopping Development Servers

```bash
# Kill all dev servers (useful for port conflicts or stuck processes)
make -f project.mk kill-dev      # Kill both frontend and backend

# Kill individual servers
make -C backend kill-dev         # Kill backend only (port 8000)
make -C frontend kill-dev        # Kill frontend only (port 5173)
```

**Use Cases for `kill-dev`:**

- Port already in use errors (e.g., "Address already in use")
- Stuck processes after crashes or Ctrl+C
- Clean restart needed
- Process not responding to normal termination

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
