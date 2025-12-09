# Makefile Structure Guide

Consistent Makefile-based build system across all components.

**Last Updated:** November 11, 2025

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

**Location**: `project.mk` at repository root (use `make` command)

```bash
make help              # View all targets

# Setup
make install           # Full setup (hooks + deps)

# Development
make dev-fullstack     # Start full stack (recommended)
make dev-backend       # Backend only
make dev-frontend      # Frontend only
make kill-dev          # Kill all dev servers (frontend + backend)

# Code Generation
make generate          # Generate all (backend specs + frontend clients)
make backend-generate  # Backend specs only (OpenAPI + AsyncAPI + Python clients)
make frontend-generate # Frontend clients only (TypeScript from backend specs)

# Quality
make test-all          # Run all tests
make lint-all          # Run all linters
make format-all        # Format all code
make build-all         # Build everything
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
make test                    # Run all tests (boundaries + modules + integration)
make test-boundaries         # Root-level tests only (excluding integration)
make test-providers          # Provider system tests only
make test-modules            # All module tests (auto-discovers modules)
make test-module-<name>      # Specific module tests (e.g., make test-module-auth)
make test-integration        # Integration tests only
make test-cov                # Tests with coverage

# Testing with ARGS (pytest arguments)
make test-providers ARGS="-k test_lazy_loading"           # Single test by pattern
make test-boundaries ARGS="-k 'not slow'"                 # Exclude tests
make test-module-auth ARGS="-k TestClassName -vv"         # Test class with verbose
make test-integration ARGS="-k 'pattern1 or pattern2'"    # Multiple patterns
make test-modules SELECTED_MODULES="auth broker" ARGS="-x"  # Stop on first failure

# Common ARGS examples:
# ARGS="-k test_name"              # Filter by test/class/module name
# ARGS="-vv"                       # Extra verbose output
# ARGS="-x"                        # Stop on first failure
# ARGS="--tb=short"                # Short traceback format
# ARGS="--collect-only"            # List tests without running
# ARGS="-k 'pattern1 or pattern2'" # Multiple test patterns
# ARGS="-k 'not slow'"             # Exclude tests matching pattern

# Quality
make lint              # Flake8 only
make type-check        # All linters + type checkers (black, isort, flake8, mypy, pyright)
make format            # Format with black + isort

# Build
make build             # Build package
make clean             # Clean artifacts
make clean-cache       # Clean all Python caches
make clean-generated   # Clean all generated files (WS routers, specs, Python clients)

# Code Generation (Unified)
make list-modules             # List all discovered modules
make generate                 # Generate all: OpenAPI + AsyncAPI specs + Python clients
make generate modules=broker  # Generate for specific module(s)
make generate output_dir=/tmp/custom  # Use custom output directory
make generate modules=broker output_dir=/tmp/custom  # Combine options
# Generates:
#   - OpenAPI specs (REST API documentation)
#   - AsyncAPI specs (WebSocket API documentation)
#   - Python HTTP clients (for inter-module communication)

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
```

### Module-Specific Targets

```bash
cd backend

# Testing Targets
make test                          # Run all tests (boundaries + modules + integration)
make test-boundaries               # Root-level tests (tests/ excluding integration/)
make test-boundaries ARGS="-vv"    # With extra verbosity
make test-providers                # Provider system tests (src/trading_api/providers/tests/)
make test-providers ARGS="-k test_lazy_loading"  # Specific provider tests
make test-modules                  # All module tests (auto-discovers modules)
make test-modules SELECTED_MODULES="auth broker"  # Specific modules
make test-modules SELECTED_MODULES="auth" ARGS="-x"  # Stop on first failure
make test-module-<name>            # Individual module (e.g., test-module-auth)
make test-module-auth ARGS="-k TestAuthService"  # Filter auth module tests
make test-integration              # Integration tests only
make test-integration ARGS="-k broker_routes"  # Specific integration tests
make test-cov                      # All tests with coverage report

# ARGS Parameter Usage:
# All test targets support ARGS for passing pytest arguments:
#   -k PATTERN          # Filter tests by name/class/module pattern
#   -vv                 # Extra verbose output
#   -x                  # Stop on first failure
#   --tb=short          # Short traceback format
#   --collect-only      # List tests without running
#   --maxfail=N         # Stop after N failures
#
# Pattern matching examples:
#   ARGS="-k test_specific_function"        # Single test function
#   ARGS="-k TestClassName"                 # All tests in a class
#   ARGS="-k 'pattern1 or pattern2'"        # Multiple patterns (OR)
#   ARGS="-k 'pattern1 and pattern2'"       # Both patterns (AND)
#   ARGS="-k 'not slow'"                    # Exclude pattern
#   ARGS="-k TestAuth -vv --tb=short"       # Combined flags

# Unified Code Generation
make list-modules             # List all discovered modules
make generate                 # Generate all: OpenAPI + AsyncAPI specs + Python clients
make generate modules=broker  # Generate for specific module
make generate modules=broker,datafeed  # Generate for multiple modules
make generate output_dir=/tmp/custom   # Use custom output directory
make generate modules=broker output_dir=/custom/path  # Combine options

# What gets generated:
# - OpenAPI specs: REST API documentation (specs_generated/*.json)
# - AsyncAPI specs: WebSocket API documentation (specs_generated/*.json)
# - Python HTTP clients: Type-safe inter-module communication (client_generated/*.py)

# Import Boundary Validation
make test-boundaries          # Verify module import boundaries
                              # Enforces: modules → shared/models only
                              # Prevents: cross-module imports
```

**Usage Examples:**

```bash
# Generate for all modules
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

# API Clients (Unified)
make generate    # Generate all API clients (REST + WebSocket)
# Note: Individual commands (generate-openapi-client, generate-asyncapi-types) are aliases to 'generate'
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
make install  # Installs hooks + all dependencies
```

### Daily Development

```bash
make dev-fullstack  # One command, full stack
```

### Running Tests

```bash
# Run all tests
make -C backend test

# Run specific test categories
make -C backend test-boundaries        # Root-level tests
make -C backend test-providers         # Provider system tests
make -C backend test-modules           # All module tests
make -C backend test-integration       # Integration tests

# Run specific module tests
make -C backend test-module-auth       # Auth module only
make -C backend test-module-broker     # Broker module only

# Filter tests with ARGS
make -C backend test-providers ARGS="-k test_lazy_loading"  # Single test
make -C backend test-module-auth ARGS="-k TestAuthService"  # Test class
make -C backend test-integration ARGS="-k 'broker or datafeed'"  # Multiple patterns

# Quick iteration on failing tests
make -C backend test-module-auth ARGS="-x -vv"  # Stop on first failure, verbose
```

### Stopping Development Servers

```bash
# Kill all dev servers (useful for port conflicts or stuck processes)
make kill-dev                    # Kill both frontend and backend

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
make lint-all format-all test-all
```

### CI Pipeline

```bash
make install
make lint-all
make test-all
make build-all
```

## Tips

- Use `make help` in any directory to see available targets
- Project root commands work with just `make` (no `-f` flag needed)
- Component-specific commands: `make -C backend <target>` or `make -C frontend <target>`
- Most targets check dependencies (Python, Node, Poetry, etc.)
- CI targets are non-interactive and fail fast
