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
make -f project.mk generate-openapi-client    # REST client (frontend)
make -f project.mk generate-asyncapi-types    # WS types (frontend)

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
make type-check        # All linters + type checkers (black, isort, flake8, mypy, pyright)
make format            # Format with black + isort

# Build
make build             # Build package
make clean             # Clean artifacts
make clean-cache       # Clean all Python caches
make clean-generated   # Clean all generated files (WS routers, specs, Python clients)

# Code Generation (NEW - Unified approach)
make list-modules             # List all discovered modules
make generate                 # Generate specs & clients for all modules
make generate modules=broker  # Generate for specific module(s)
make generate output_dir=/tmp/custom  # Use custom output directory
make generate modules=broker output_dir=/tmp/custom  # Combine options
# Generates:
#   - OpenAPI specs (REST API documentation)
#   - AsyncAPI specs (WebSocket API documentation)
#   - Python HTTP clients (for inter-module communication)
# Note: WebSocket routers auto-generate at module init (no manual step needed)

# Code Generation (DEPRECATED - Use 'make generate' instead)
make export-openapi-spec      # [DEPRECATED] Use 'make generate'
make export-asyncapi-spec     # [DEPRECATED] Use 'make generate'
make generate-python-clients  # [DEPRECATED] Use 'make generate'
make generate-ws-routers      # [DEPRECATED] Auto-generates at module init

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
```

### Module-Specific Targets

```bash
cd backend

# Unified Code Generation (Recommended)
make list-modules             # List all discovered modules
make generate                 # Generate all: OpenAPI specs, AsyncAPI specs, Python clients
make generate modules=broker  # Generate for specific module
make generate modules=broker,datafeed  # Generate for multiple modules
make generate output_dir=/tmp/custom   # Use custom output directory
make generate modules=broker output_dir=/custom/path  # Combine options

# What gets generated:
# - OpenAPI specs: REST API documentation (specs_generated/*.json)
# - AsyncAPI specs: WebSocket API documentation (specs_generated/*.json)
# - Python HTTP clients: Type-safe inter-module communication (client_generated/*.py)
# - WebSocket routers: Auto-generated at module init (ws_generated/*.py)

# Legacy Commands (Deprecated)
# These still work but show deprecation warnings:
make export-openapi-spec      # Use 'make generate' instead
make export-asyncapi-spec     # Use 'make generate' instead
make generate-python-clients  # Use 'make generate' instead
make generate-ws-routers      # WebSocket routers auto-generate at module init

# Import Boundary Validation
make test-boundaries          # Verify module import boundaries
                              # Enforces: modules → shared/models only
                              # Prevents: cross-module imports
```

**Migration Guide:**

```bash
# Old way (multiple commands)
make export-openapi-spec
make export-asyncapi-spec
make generate-python-clients
make generate-ws-routers

# New way (single command)
make generate

# Selective generation
make generate modules=broker

# Custom output directory
make generate output_dir=/path/to/output
make generate modules=broker output_dir=/custom/path
```

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
