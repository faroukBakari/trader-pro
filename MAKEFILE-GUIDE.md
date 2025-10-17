# Makefile Structure Guide

This project uses a consistent Makefile-based build system across all components.

## Philosophy

- **Consistency**: CI workflows use the same `make` commands as local development
- **Simplicity**: All common tasks have memorable make targets
- **Composability**: Project-level targets delegate to component-level Makefiles
- **Documentation**: Every Makefile has a `help` target showing available commands

## Makefile Hierarchy

```
project.mk              # Project-wide orchestration
├── backend/Makefile    # Backend-specific targets
└── frontend/Makefile   # Frontend-specific targets
```

## Project-Level Commands

Located in `project.mk` at the repository root:

```bash
# View all available targets
make -f project.mk help

# Common workflows
make -f project.mk setup        # Full project setup (hooks + dependencies)
make -f project.mk install-all  # Install all dependencies (backend + frontend)
make -f project.mk test-all     # Run all tests
make -f project.mk lint-all     # Run all linters
make -f project.mk build-all    # Build everything
```

## Backend Commands

Located in `backend/Makefile`:

```bash
cd backend

# Development
make ensure-python     # Check Python 3.11+ (offers auto-install with confirmation)
make ensure-python-ci  # Check Python 3.11+ (CI mode, auto-installs without prompts)
make ensure-poetry     # Ensure Poetry is installed (auto-installs if needed)
make install          # Install dependencies (auto-installs Python & Poetry if needed)
make install-ci       # Install dependencies for CI (non-interactive)
make dev          # Start development server
make dev-ci       # Start server in background for CI

# Testing
make test         # Run tests
make test-cov     # Run tests with coverage

# Code Quality
make lint         # Run flake8 linting
make lint-check   # Run all linters (black, isort, flake8, mypy)
make format       # Format code with black and isort

# Build & Deploy
make build        # Build Python package
make clean        # Clean build artifacts

# API
make health       # Check API health
make health-ci    # Check API health for CI (fail on error)
make clients      # Generate API clients
make export-openapi  # Export OpenAPI spec
```

## Frontend Commands

Located in `frontend/Makefile`:

```bash
cd frontend

# Development
make ensure-node     # Check Node.js 20.19+/22.12+ (offers auto-install with confirmation)
make ensure-node-ci  # Check Node.js 20.19+/22.12+ (CI mode, auto-installs without prompts)
make install        # Install dependencies (auto-installs Node.js if needed)
make install-ci     # Install dependencies for CI (npm ci)
make dev            # Start development server

# Testing
make test         # Run tests in watch mode
make test-run     # Run tests once (for CI)

# Code Quality
make lint         # Run ESLint and Prettier checks
make type-check   # Run TypeScript type checking

# Build & Deploy
make build        # Build for production
make clean        # Clean build artifacts
```

## CI Integration

The GitHub Actions workflow (`.github/workflows/ci.yml`) uses these Makefiles exclusively:

```yaml
# Backend CI
- run: make install-ci
- run: make test-cov
- run: make lint-check

# Frontend CI
- run: make install-ci
- run: make lint
- run: make type-check
- run: make test-run
- run: make build
```

## Benefits

1. **Developer Experience**: Same commands work locally and in CI
2. **Maintainability**: Changes to build process are centralized in Makefiles
3. **Discoverability**: `make help` shows available commands at each level
4. **Consistency**: No mixing of `npm run`, `poetry run`, and custom scripts in CI
5. **Flexibility**: Easy to add new targets or modify existing ones

## Best Practices

### Adding New Targets

1. Add to appropriate Makefile (backend/frontend/project)
2. Add to `.PHONY` declaration at top of file
3. Add to `help` target description
4. Use consistent naming (verb-noun pattern)
5. Include descriptive echo statements

### Example New Target

```makefile
.PHONY: my-target

my-target:
	@echo "Running my custom task..."
	# Your commands here
```

### Updating CI

When adding new build steps, update both:
1. The appropriate Makefile
2. The CI workflow to use the new make target

## Common Patterns

### Conditional Execution

```makefile
# Old pattern - just check and fail
install:
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found!"; \
		exit 1; \
	fi
	poetry install

# New pattern - validate and auto-install with confirmation
ensure-python:
	@PYTHON_VERSION=$$(python3 --version | grep -oP '\d+\.\d+' | head -1); \
	if [ "$$(printf '%s\n' "3.11" "$$PYTHON_VERSION" | sort -V | head -n1)" != "3.11" ]; then \
		if command -v pyenv >/dev/null 2>&1; then \
			echo "Install Python 3.11.7? [y/N]"; \
			read -r REPLY; \
			[ "$$REPLY" = "y" ] && pyenv install 3.11.7 && pyenv local 3.11.7; \
		fi; \
	fi

ensure-poetry:
	@if ! command -v poetry >/dev/null 2>&1; then \
		pipx install poetry || pip3 install --user poetry; \
	fi

install: ensure-python ensure-poetry
	poetry install
```

### Cross-Directory Targets

```makefile
backend-target:
	make -C backend specific-target
```

### CI-Specific Behavior

```makefile
install-ci:
	poetry install --no-interaction --with dev
```

## Troubleshooting

### Target Not Found

```bash
# Make sure you're in the right directory
cd backend  # or frontend
make <target>

# Or use the project-level Makefile
cd <project-root>
make -f project.mk <target>
```

### Permission Errors

```bash
# Make sure scripts are executable
chmod +x scripts/*.sh
```

### CI Failures

1. Check that the Makefile target works locally first
2. Ensure all dependencies are in `install-ci` target
3. Verify CI environment has necessary tools (poetry, npm, etc.)
