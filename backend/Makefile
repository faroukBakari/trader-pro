# TraderPRO Backend Makefile

# Environment variables with fallback values
BACKEND_PORT ?= 8000
BACKEND_APP_NAME ?= app

.PHONY: help ensure-python ensure-python-ci ensure-poetry install test test-cov lint lint-check format build clean dev health clients export-openapi docs-html

# Default target
help:
	@echo "Backend targets:"
	@echo "  ensure-python     Ensure Python 3.11+ is installed (offers auto-install)"
	@echo "  ensure-python-ci  Ensure Python 3.11+ is installed (CI mode, no prompts)"
	@echo "  ensure-poetry     Ensure Poetry is installed (auto-installs if needed)"
	@echo "  install           Install backend dependencies"
	@echo "  test              Run backend tests"
	@echo "  test-cov          Run backend tests with coverage"
	@echo "  lint              Run backend linting (check only)"
	@echo "  lint-check        Run backend linting with type checking"
	@echo "  format            Format backend code"
	@echo "  build             Build backend package"
	@echo "  dev               Start backend development server with debugpy"
	@echo "  dev-no-debug      Start backend development server without debugpy"
	@echo "  clean             Clean build artifacts"
	@echo "  health            Check backend health"
	@echo "  export-openapi    Export OpenAPI specification"
	@echo "  docs-html         Generate static HTML documentation"

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
install: ensure-python ensure-poetry
	@echo "Installing backend dependencies..."
	poetry install

# CI-optimized install (non-interactive)
install-ci: ensure-python-ci ensure-poetry
	@echo "Installing backend dependencies for CI..."
	poetry install --no-interaction

# Testing
test:
	@echo "Running backend tests..."
	poetry run pytest -v

test-cov:
	@echo "Running backend tests with coverage..."
	poetry run pytest --cov=trading_api --cov-report=xml --cov-report=term-missing

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
	poetry run black src/ tests/
	poetry run isort src/ tests/

# Development server
dev:
	@echo "Starting backend development server with debugpy on http://localhost:$(BACKEND_PORT)"
	@echo "Debug server listening on port 5678 (attach debugger to localhost:5678)"
	poetry run python -m debugpy --listen 0.0.0.0:5678 -m uvicorn "trading_api.main:$(BACKEND_APP_NAME)" --reload --host 0.0.0.0 --port $(BACKEND_PORT) --log-level info

# CI development server (background)
dev-ci:
	@echo "Starting backend server for CI..."
	poetry run uvicorn "trading_api.main:$(BACKEND_APP_NAME)" --host 0.0.0.0 --port $(BACKEND_PORT) &
	sleep 10

# Build
build:
	@echo "Building backend package..."
	poetry build

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
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage clients/ openapi*.json
	@echo "Backend clean complete."

# Export OpenAPI specification
export-openapi:
	@echo "Exporting OpenAPI specification..."
	curl -s http://localhost:$(BACKEND_PORT)/api/v1/openapi.json -o openapi.json

# Generate static HTML documentation
docs-html:
	@echo "Generating static HTML documentation..."
	npx redoc-cli bundle openapi.json -o docs/api.html
