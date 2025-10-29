# TraderPRO Backend Makefile

# Environment variables with fallback values
BACKEND_PORT ?= 8000
BACKEND_APP_NAME ?= app

# Dynamic module discovery
MODULES_DIR = src/trading_api/modules
DISCOVERED_MODULES = $(shell find $(MODULES_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -v __pycache__ || echo "")

# Module selection (can be overridden: make test modules=broker,datafeed)
ifdef modules
	SELECTED_MODULES = $(subst $(comma), ,$(modules))
else
	SELECTED_MODULES = $(DISCOVERED_MODULES)
endif
comma := ,

.PHONY: help ensure-python ensure-python-ci ensure-poetry install install-ci test test-boundaries test-shared test-modules test-cov test-cov-modules test-integration test-integration-verbose lint lint-check lint-response-models format build clean clean-cache dev dev-no-debug dev-ci kill-dev health health-ci export-openapi-spec export-asyncapi-spec docs-html generate-ws-routers $(addprefix test-module-, $(DISCOVERED_MODULES))

# Default target
help:
	@echo "Backend targets:"
	@echo "  ensure-python     Ensure Python 3.11+ is installed (offers auto-install)"
	@echo "  ensure-python-ci  Ensure Python 3.11+ is installed (CI mode, no prompts)"
	@echo "  ensure-poetry     Ensure Poetry is installed (auto-installs if needed)"
	@echo "  install           Install backend dependencies"
	@echo ""
	@echo "Testing targets:"
	@echo "  test              Run all tests (boundaries + shared + modules + integration)"
	@echo "  test-boundaries   Validate import boundaries between modules"
	@echo "  test-shared       Run shared infrastructure tests"
	@echo "  test-modules      Run all module tests (use modules=mod1,mod2 to select specific)"
	@echo "  test-integration  Run integration tests"
	@echo "  test-integration-verbose  Run integration tests with detailed output"
	@echo "  test-cov          Run all tests with coverage"
	@echo "  test-cov-modules  Run module tests with coverage (use modules=mod1,mod2)"
	@echo ""
	@echo "Module-specific test targets (auto-discovered):"
	@for module in $(DISCOVERED_MODULES); do \
		echo "  test-module-$$module"; \
	done
	@echo ""
	@echo "Other targets:"
	@echo "  lint              Run backend linting (check only)"
	@echo "  lint-check        Run backend linting with type checking"
	@echo "  format            Format backend code"
	@echo "  build             Build backend package"
	@echo "  dev               Start backend development server with debugpy"
	@echo "  dev-no-debug      Start backend development server without debugpy"
	@echo "  kill-dev          Kill any running backend development server"
	@echo "  clean             Clean build artifacts"
	@echo "  clean-cache       Clean all Python caches (mypy, pytest, pycache, ruff)"
	@echo "  health            Check backend health"
	@echo "  export-openapi-spec   Export OpenAPI specification (offline)"
	@echo "  export-asyncapi-spec  Export AsyncAPI specification (offline)"
	@echo "  docs-html         Generate static HTML documentation"
	@echo "  generate-ws-routers Generate WebSocket router classes"
	@echo ""
	@echo "Discovered modules: $(DISCOVERED_MODULES)"

# Ensure Python 3.11+ is available
ensure-python:
	@echo "Checking Python version..."
	@PYTHON_VERSION=$$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
	REQUIRED_VERSION="3.11"; \
	PYTHON_TO_INSTALL="3.11.7"; \
	if [ -z "$$PYTHON_VERSION" ]; then \
		echo "❌ Python 3 not found!"; \
		echo ""; \
		if command -v pyenv >/dev/null 2>&1; then \
			echo "Would you like to install Python $$PYTHON_TO_INSTALL via pyenv? [y/N]"; \
			read -r REPLY; \
			if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
				echo "Installing Python $$PYTHON_TO_INSTALL..."; \
				pyenv install $$PYTHON_TO_INSTALL && \
				pyenv local $$PYTHON_TO_INSTALL && \
				echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!" && \
				exit 0; \
			fi; \
		fi; \
		echo "Please install Python 3.11 or higher:"; \
		echo "  - Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"; \
		echo "  - Using pyenv: pyenv install $$PYTHON_TO_INSTALL && pyenv local $$PYTHON_TO_INSTALL"; \
		exit 1; \
	fi; \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$PYTHON_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo "❌ Python $$PYTHON_VERSION detected (requires $$REQUIRED_VERSION or higher)"; \
		echo ""; \
		if command -v pyenv >/dev/null 2>&1; then \
			INSTALLED_311=$$(pyenv versions 2>/dev/null | grep -E '^\s*3\.(1[1-9]|[2-9][0-9])' | head -1 | tr -d ' *'); \
			if [ -n "$$INSTALLED_311" ]; then \
				echo "✓ Found existing Python version: $$INSTALLED_311"; \
				echo "Would you like to activate it for this project? [y/N]"; \
				read -r REPLY; \
				if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
					pyenv local $$INSTALLED_311 && \
					echo "✓ Python $$INSTALLED_311 activated!" && \
					exit 0; \
				fi; \
			else \
				echo "Would you like to install Python $$PYTHON_TO_INSTALL via pyenv? [y/N]"; \
				read -r REPLY; \
				if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
					echo "Installing Python $$PYTHON_TO_INSTALL..."; \
					pyenv install $$PYTHON_TO_INSTALL && \
					pyenv local $$PYTHON_TO_INSTALL && \
					echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!" && \
					exit 0; \
				fi; \
			fi; \
			echo ""; \
			echo "Manual installation:"; \
			echo "  pyenv install $$PYTHON_TO_INSTALL"; \
			echo "  pyenv local $$PYTHON_TO_INSTALL"; \
		else \
			echo "pyenv not found. Install it for automatic Python version management:"; \
			echo "  curl https://pyenv.run | bash"; \
			echo ""; \
			echo "Or install Python manually:"; \
			echo "  Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"; \
			echo "  Fedora: sudo dnf install python3.11"; \
			echo "  Download: https://www.python.org/downloads/"; \
		fi; \
		exit 1; \
	else \
		echo "✓ Python $$PYTHON_VERSION detected (meets requirement $$REQUIRED_VERSION+)"; \
	fi

# Ensure Python 3.11+ is available (CI mode - no interactive prompts)
ensure-python-ci:
	@echo "Checking Python version (CI mode)..."
	@PYTHON_VERSION=$$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
	REQUIRED_VERSION="3.11"; \
	PYTHON_TO_INSTALL="3.11.7"; \
	if [ -z "$$PYTHON_VERSION" ]; then \
		echo "❌ Python 3 not found!"; \
		if command -v pyenv >/dev/null 2>&1; then \
			echo "Installing Python $$PYTHON_TO_INSTALL via pyenv..."; \
			pyenv install -s $$PYTHON_TO_INSTALL && \
			pyenv local $$PYTHON_TO_INSTALL && \
			echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!" && \
			exit 0; \
		fi; \
		echo "❌ Cannot auto-install Python in CI without pyenv"; \
		exit 1; \
	fi; \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$PYTHON_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo "❌ Python $$PYTHON_VERSION detected (requires $$REQUIRED_VERSION or higher)"; \
		if command -v pyenv >/dev/null 2>&1; then \
			INSTALLED_311=$$(pyenv versions 2>/dev/null | grep -E '^\s*3\.(1[1-9]|[2-9][0-9])' | head -1 | tr -d ' *'); \
			if [ -n "$$INSTALLED_311" ]; then \
				echo "✓ Activating existing Python version: $$INSTALLED_311"; \
				pyenv local $$INSTALLED_311 && \
				echo "✓ Python $$INSTALLED_311 activated!" && \
				exit 0; \
			else \
				echo "Installing Python $$PYTHON_TO_INSTALL via pyenv..."; \
				pyenv install -s $$PYTHON_TO_INSTALL && \
				pyenv local $$PYTHON_TO_INSTALL && \
				echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!" && \
				exit 0; \
			fi; \
		fi; \
		echo "❌ Cannot auto-install Python in CI without pyenv"; \
		exit 1; \
	else \
		echo "✓ Python $$PYTHON_VERSION detected (meets requirement $$REQUIRED_VERSION+)"; \
	fi

# Ensure Poetry is installed
ensure-poetry:
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found. Installing Poetry..."; \
		if command -v pipx >/dev/null 2>&1; then \
			echo "Installing Poetry via pipx (recommended)..."; \
			pipx install poetry; \
		elif command -v pip3 >/dev/null 2>&1; then \
			echo "pipx not found. Installing Poetry via pip3..."; \
			pip3 install --user poetry; \
			echo "Note: Make sure ~/.local/bin is in your PATH"; \
		else \
			echo "Installing Poetry via official installer..."; \
			curl -sSL https://install.python-poetry.org | python3 -; \
			echo "Note: Make sure ~/.local/bin is in your PATH"; \
		fi; \
		if ! command -v poetry >/dev/null 2>&1; then \
			echo "Poetry installation completed but 'poetry' command not found in PATH."; \
			echo "Please add ~/.local/bin to your PATH and retry."; \
			echo "Run: export PATH=\"$$HOME/.local/bin:$$PATH\""; \
			exit 1; \
		fi; \
		echo "Poetry installed successfully!"; \
	else \
		echo "Poetry is already installed: $$(poetry --version)"; \
	fi

# Backend dependency management
install: ensure-poetry
	@echo "Installing backend dependencies..."
	@if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then \
		VENV_PYTHON_VERSION=$$(.venv/bin/python --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
		REQUIRED_VERSION="3.11"; \
		if [ -n "$$VENV_PYTHON_VERSION" ] && [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$VENV_PYTHON_VERSION" | sort -V | head -n1)" = "$$REQUIRED_VERSION" ]; then \
			echo "✓ Found existing virtual environment with Python $$VENV_PYTHON_VERSION"; \
			poetry install; \
		else \
			echo "⚠️  Existing venv has incompatible Python version ($$VENV_PYTHON_VERSION), recreating..."; \
			rm -rf .venv; \
			$(MAKE) ensure-python; \
			poetry install; \
		fi; \
	else \
		echo "No existing virtual environment found, checking Python..."; \
		$(MAKE) ensure-python; \
		poetry install; \
	fi

# CI-optimized install (non-interactive)
install-ci: ensure-python-ci ensure-poetry
	@echo "Installing backend dependencies for CI..."
	poetry install --no-interaction

# Testing
test-boundaries:
	@echo "Validating import boundaries..."
	poetry run pytest tests/test_import_boundaries.py -v

test-shared:
	@echo "Running shared infrastructure tests..."
	poetry run pytest src/trading_api/shared/tests/ -v -x

test-modules:
	@echo "Running module tests..."
	@if [ -z "$(SELECTED_MODULES)" ]; then \
		echo "⚠️  No modules selected or found"; \
	else \
		echo "Testing modules: $(SELECTED_MODULES)"; \
		for module in $(SELECTED_MODULES); do \
			if [ -d "$(MODULES_DIR)/$$module/tests" ]; then \
				echo "Testing module: $$module"; \
				poetry run pytest $(MODULES_DIR)/$$module/tests/ -v -x || exit 1; \
			else \
				echo "⚠️  No tests found for module: $$module"; \
			fi; \
		done; \
	fi

# Individual module tests (auto-generated targets)
$(addprefix test-module-, $(DISCOVERED_MODULES)): test-module-%:
	@echo "Running tests for module: $*..."
	@if [ -d "$(MODULES_DIR)/$*/tests" ]; then \
		poetry run pytest $(MODULES_DIR)/$*/tests/ -v -x; \
	else \
		echo "⚠️  No tests found for module: $*"; \
	fi

test-integration:
	@echo "Running integration tests..."
	poetry run pytest tests/integration/ -v -x -m integration

test-integration-verbose:
	@echo "Running integration tests with detailed output..."
	poetry run pytest tests/integration/ -v -s -m integration

test: test-boundaries test-shared test-modules test-integration
	@echo "✅ All tests passed (boundaries + shared + modules + integration)"

# Coverage targets
test-cov-modules:
	@echo "Running module tests with coverage..."
	@if [ -z "$(SELECTED_MODULES)" ]; then \
		echo "⚠️  No modules selected or found"; \
	else \
		echo "Testing modules with coverage: $(SELECTED_MODULES)"; \
		MODULE_PATHS=$$(for m in $(SELECTED_MODULES); do echo "$(MODULES_DIR)/$$m/tests"; done); \
		poetry run pytest $$MODULE_PATHS --cov=trading_api.modules --cov-report=xml --cov-report=term-missing; \
	fi

test-cov: test-boundaries
	@echo "Running all tests with coverage..."
	poetry run pytest -x --cov=trading_api --cov-report=xml --cov-report=term-missing

# Linting and formatting
lint:
	@echo "Running backend linting..."
	poetry run flake8 src/ tests/

lint-check:
	@echo "Running backend linting with full checks..."
	poetry run black --check src/ tests/
	poetry run isort --check-only src/ tests/
	poetry run flake8 src/ tests/
	poetry run mypy src/

lint-response-models:
	@echo "Validating FastAPI response models..."
	poetry run python scripts/check_response_models.py src/trading_api/api/*.py

format:
	@echo "Formatting backend code..."
	poetry run autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive src/ tests/
	poetry run black src/ tests/
	poetry run isort src/ tests/

# Development server
dev:
	@echo "Starting backend development server with debugpy on http://localhost:$(BACKEND_PORT)"
	@echo "🔍 Checking if backend port is available..."
	@if lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "❌ Error: Backend port $(BACKEND_PORT) is already in use!"; \
		echo ""; \
		echo "Process using port $(BACKEND_PORT):"; \
		lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN; \
		echo ""; \
		echo "Please stop the existing server or use a different port:"; \
		echo "  export BACKEND_PORT=<new_port>"; \
		exit 1; \
	fi
	@echo "✅ Port $(BACKEND_PORT) is available"
	@echo "Debug server listening on port 5678 (attach debugger to localhost:5678)"
	poetry run python -m debugpy --listen 0.0.0.0:5678 -m uvicorn "trading_api.main:$(BACKEND_APP_NAME)" --reload --host 0.0.0.0 --port $(BACKEND_PORT) --log-level info

# Development server without debugger
dev-no-debug:
	@echo "Starting backend development server on http://localhost:$(BACKEND_PORT)"
	@echo "🔍 Checking if backend port is available..."
	@if lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "❌ Error: Backend port $(BACKEND_PORT) is already in use!"; \
		echo ""; \
		echo "Process using port $(BACKEND_PORT):"; \
		lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN; \
		echo ""; \
		echo "Please stop the existing server or use a different port:"; \
		echo "  export BACKEND_PORT=<new_port>"; \
		exit 1; \
	fi
	@echo "✅ Port $(BACKEND_PORT) is available"
	poetry run uvicorn "trading_api.main:$(BACKEND_APP_NAME)" --reload --host 0.0.0.0 --port $(BACKEND_PORT) --log-level info

# Kill backend development server
kill-dev:
	@echo "🔍 Checking for running backend processes..."
	@PIDS=$$(lsof -ti :$(BACKEND_PORT) 2>/dev/null || true); \
	if [ -n "$$PIDS" ]; then \
		echo "Found backend process(es) on port $(BACKEND_PORT):"; \
		lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN 2>/dev/null || true; \
		echo ""; \
		echo "Killing process(es)..."; \
		kill -9 $$PIDS 2>/dev/null || true; \
		sleep 1; \
		if lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
			echo "❌ Failed to kill some processes. Please check manually."; \
			exit 1; \
		else \
			echo "✅ Backend development server stopped"; \
		fi; \
	else \
		echo "✅ No backend process found on port $(BACKEND_PORT)"; \
	fi

# CI development server (background)
dev-ci:
	@echo "Starting backend server for CI..."
	poetry run uvicorn "trading_api.main:$(BACKEND_APP_NAME)" --host 0.0.0.0 --port $(BACKEND_PORT) &
	sleep 10

# Build
build:
	@echo "Building backend package..."
	poetry build
	@./scripts/generate-ws-routers.sh

# Health check
health:
	@echo "Checking backend health..."
	@curl -f http://localhost:$(BACKEND_PORT)/api/v1/health 2>/dev/null || echo "Backend not running"

# CI health check
health-ci:
	@echo "Testing API endpoints for CI..."
	curl -f http://localhost:$(BACKEND_PORT)/api/v1/health || exit 1
	curl -f http://localhost:$(BACKEND_PORT)/api/v1/version || exit 1

# Cleanup
clean:
	@echo "Cleaning backend build artifacts..."
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage clients/ src/trading_api/ws/generated/ openapi.json asyncapi.json
	@echo "Backend clean complete."

# Clean all Python caches
clean-cache:
	@echo "Cleaning all Python caches..."
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytype" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Removed .mypy_cache directories"
	@echo "✓ Removed __pycache__ directories"
	@echo "✓ Removed .pytest_cache directories"
	@echo "✓ Removed .ruff_cache directories"
	@echo "✓ Removed .pytype directories"
	@echo "✓ Removed *.egg-info directories"
	@echo ""
	@echo "💡 Tip: After cleaning caches, reload VS Code window:"
	@echo "   Press Ctrl+Shift+P → 'Developer: Reload Window'"
	@echo "   Or run: 'Python: Restart Language Server'"

# Export OpenAPI specification (offline)
export-openapi-spec:
	@echo "Exporting OpenAPI specification (offline)..."
	poetry run python scripts/export_openapi_spec.py

# Export AsyncAPI specification (offline)
export-asyncapi-spec:
	@echo "Exporting AsyncAPI specification (offline)..."
	poetry run python scripts/export_asyncapi_spec.py

# Generate static HTML documentation
docs-html:
	@echo "Generating static HTML documentation..."
	npx redoc-cli bundle openapi.json -o docs/api.html

# Generate WebSocket router classes
generate-ws-routers:
	@./scripts/generate-ws-routers.sh
