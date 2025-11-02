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

.PHONY: help install install-ci test test-boundaries test-modules test-cov test-integration lint type-check format build clean clean-cache clean-generated dev dev-ci kill-dev health-ci list-modules generate export-openapi-spec export-asyncapi-spec generate-python-clients generate-ws-routers backend-manager-start backend-manager-stop backend-manager-status backend-manager-restart backend-manager-gen-nginx-conf logs-tail logs-tail-nginx logs-clean $(addprefix test-module-, $(DISCOVERED_MODULES))

# Default target
help:
	@echo "Backend targets:"
	@echo "  install           Install backend dependencies (auto-checks Python/Poetry/nginx)"
	@echo "  install-ci        Install backend dependencies for CI (non-interactive)"
	@echo ""
	@echo "Testing targets:"
	@echo "  test              Run all tests (boundaries + modules + integration)"
	@echo "  test-boundaries   Validate import boundaries between modules"
	@echo "  test-modules      Run all module tests (use modules=mod1,mod2 to select specific)"
	@echo "  test-integration  Run integration tests"
	@echo "  test-cov          Run all tests with coverage"
	@echo ""
	@echo "Module-specific test targets (auto-discovered):"
	@for module in $(DISCOVERED_MODULES); do \
		echo "  test-module-$$module"; \
	done
	@echo ""
	@echo "Code quality targets:"
	@echo "  lint              Run backend linting (flake8 only)"
	@echo "  type-check        Run backend linting with type checking (black, isort, flake8, mypy, pyright)"
	@echo "  format            Format backend code"
	@echo ""
	@echo "Development targets:"
	@echo "  dev               Start backend development server with debugpy"
	@echo "  dev-ci            Start backend server for CI (background)"
	@echo "  kill-dev          Kill any running backend development server"
	@echo "  health-ci         Check backend health (CI)"
	@echo ""
	@echo "Multi-process backend (with nginx):"
	@echo "  backend-manager-start   Start multi-process backend with nginx (config=dev-config.yaml)"
	@echo "  backend-manager-stop    Stop multi-process backend"
	@echo "  backend-manager-status  Show backend process status"
	@echo "  backend-manager-restart Restart multi-process backend"
	@echo "  backend-manager-gen-nginx-conf Generate nginx config (debug)"
	@echo ""
	@echo "Build & cleanup targets:"
	@echo "  build             Build backend package"
	@echo "  clean             Clean build artifacts"
	@echo "  clean-cache       Clean all Python caches (mypy, pytest, pycache, ruff)"
	@echo "  clean-generated   Clean all *_generated* files and directories"
	@echo ""
	@echo "Code generation targets:"
	@echo "  list-modules          List all discovered modules"
	@echo "  generate              Generate specs & clients for all modules"
	@echo "                        Options: modules=mod1,mod2  (specific modules)"
	@echo "                                 output_dir=/path   (custom output directory)"
	@echo "  export-openapi-spec   [DEPRECATED] Export OpenAPI specification (use: make generate)"
	@echo "  export-asyncapi-spec  [DEPRECATED] Export AsyncAPI specification (use: make generate)"
	@echo "  generate-python-clients  [DEPRECATED] Generate Python HTTP clients (use: make generate)"
	@echo "  generate-ws-routers   [DEPRECATED] WS routers auto-generate at module init (no manual generation needed)"
	@echo ""
	@echo "Logging targets:"
	@echo "  logs-tail         Tail unified backend log (all servers with prefixes)"
	@echo "  logs-tail-nginx   Tail nginx logs (access + error)"
	@echo "  logs-clean        Clean all backend log files"
	@echo ""
	@echo "Discovered modules: $(DISCOVERED_MODULES)"

# List all discovered modules
list-modules:
	@echo "📦 Discovered modules:"
	@for module in $(DISCOVERED_MODULES); do \
		echo "  - $$module"; \
	done

# Unified generation command
# Usage: make generate [modules=mod1,mod2] [output_dir=/path/to/output]
generate:
	@echo "🔨 Generating for modules: $(SELECTED_MODULES)"
	@if [ -n "$(output_dir)" ]; then \
		echo "📁 Output directory: $(output_dir)"; \
	fi
	@for module in $(SELECTED_MODULES); do \
		echo ""; \
		echo "======================================================================"; \
		echo "🔨 Generating for module: $$module"; \
		echo "======================================================================"; \
		if [ -n "$(output_dir)" ]; then \
			poetry run python scripts/module_codegen.py "$$module" "$(output_dir)" || { echo "❌ Failed for $$module"; exit 1; }; \
		else \
			poetry run python scripts/module_codegen.py "$$module" || { echo "❌ Failed for $$module"; exit 1; }; \
		fi; \
	done
	@echo ""
	@echo "======================================================================"
	@echo "✅ Generation complete for all modules"
	@echo "======================================================================"

# Backend dependency management
install:
	@echo "Installing backend dependencies..."
	@echo ""
	@echo "[1/3] Checking Poetry..."
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
		echo "✓ Poetry is already installed: $$(poetry --version)"; \
	fi
	@echo ""
	@echo "[2/3] Checking Python version..."
	@if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then \
		VENV_PYTHON_VERSION=$$(.venv/bin/python --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
		REQUIRED_VERSION="3.11"; \
		if [ -n "$$VENV_PYTHON_VERSION" ] && [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$VENV_PYTHON_VERSION" | sort -V | head -n1)" = "$$REQUIRED_VERSION" ]; then \
			echo "✓ Found existing virtual environment with Python $$VENV_PYTHON_VERSION"; \
			poetry install; \
		else \
			echo "⚠️  Existing venv has incompatible Python version ($$VENV_PYTHON_VERSION), recreating..."; \
			rm -rf .venv; \
			PYTHON_VERSION=$$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
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
						echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!"; \
					else \
						echo "Please install Python 3.11 or higher manually"; \
						exit 1; \
					fi; \
				else \
					echo "Please install Python 3.11 or higher:"; \
					echo "  - Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"; \
					echo "  - Using pyenv: pyenv install $$PYTHON_TO_INSTALL && pyenv local $$PYTHON_TO_INSTALL"; \
					exit 1; \
				fi; \
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
							echo "✓ Python $$INSTALLED_311 activated!"; \
						else \
							echo "Please activate Python manually"; \
							exit 1; \
						fi; \
					else \
						echo "Would you like to install Python $$PYTHON_TO_INSTALL via pyenv? [y/N]"; \
						read -r REPLY; \
						if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
							echo "Installing Python $$PYTHON_TO_INSTALL..."; \
							pyenv install $$PYTHON_TO_INSTALL && \
							pyenv local $$PYTHON_TO_INSTALL && \
							echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!"; \
						else \
							echo "Please install Python manually"; \
							exit 1; \
						fi; \
					fi; \
				else \
					echo "pyenv not found. Install it for automatic Python version management:"; \
					echo "  curl https://pyenv.run | bash"; \
					echo ""; \
					echo "Or install Python manually:"; \
					echo "  Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"; \
					exit 1; \
				fi; \
			else \
				echo "✓ Python $$PYTHON_VERSION detected (meets requirement $$REQUIRED_VERSION+)"; \
			fi; \
			poetry install; \
		fi; \
	else \
		echo "No existing virtual environment found, checking Python..."; \
		PYTHON_VERSION=$$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
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
					echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!"; \
				else \
					echo "Please install Python 3.11 or higher manually"; \
					exit 1; \
				fi; \
			else \
				echo "Please install Python 3.11 or higher:"; \
				echo "  - Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"; \
				echo "  - Using pyenv: pyenv install $$PYTHON_TO_INSTALL && pyenv local $$PYTHON_TO_INSTALL"; \
				exit 1; \
			fi; \
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
						echo "✓ Python $$INSTALLED_311 activated!"; \
					else \
						echo "Please activate Python manually"; \
						exit 1; \
					fi; \
				else \
					echo "Would you like to install Python $$PYTHON_TO_INSTALL via pyenv? [y/N]"; \
					read -r REPLY; \
					if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
						echo "Installing Python $$PYTHON_TO_INSTALL..."; \
						pyenv install $$PYTHON_TO_INSTALL && \
						pyenv local $$PYTHON_TO_INSTALL && \
						echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!"; \
					else \
						echo "Please install Python manually"; \
						exit 1; \
					fi; \
				fi; \
			else \
				echo "pyenv not found. Install it for automatic Python version management:"; \
				echo "  curl https://pyenv.run | bash"; \
				echo ""; \
				echo "Or install Python manually:"; \
				echo "  Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"; \
				exit 1; \
			fi; \
		else \
			echo "✓ Python $$PYTHON_VERSION detected (meets requirement $$REQUIRED_VERSION+)"; \
		fi; \
		poetry install; \
	fi
	@echo ""
	@echo "[3/3] Checking nginx (required for multi-process mode)..."
	@if [ -f ".local/bin/nginx" ]; then \
		echo "✅ Local nginx available: $$(.local/bin/nginx -v 2>&1)"; \
	elif command -v nginx >/dev/null 2>&1; then \
		echo "✅ System nginx available: $$(nginx -v 2>&1)"; \
	else \
		echo "⚠️  nginx not found (optional - only needed for multi-process mode)"; \
		echo ""; \
		echo "Would you like to install standalone nginx? [y/N]"; \
		read -r REPLY; \
		if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
			echo "Installing standalone nginx binary..."; \
			poetry run python scripts/install_nginx.py && \
			echo "✅ nginx installed successfully!"; \
		else \
			echo "Skipping nginx installation. You can install it later with:"; \
			echo "  poetry run python scripts/install_nginx.py"; \
			echo "  OR: sudo apt install nginx"; \
		fi; \
	fi
	@echo ""
	@echo "✅ Backend installation complete!"

# CI-optimized install (non-interactive)
install-ci:
	@echo "Installing backend dependencies for CI..."
	@echo ""
	@echo "[1/2] Checking Poetry..."
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found. Installing Poetry..."; \
		if command -v pipx >/dev/null 2>&1; then \
			echo "Installing Poetry via pipx (recommended)..."; \
			pipx install poetry; \
		elif command -v pip3 >/dev/null 2>&1; then \
			echo "pipx not found. Installing Poetry via pip3..."; \
			pip3 install --user poetry; \
		else \
			echo "Installing Poetry via official installer..."; \
			curl -sSL https://install.python-poetry.org | python3 -; \
		fi; \
		if ! command -v poetry >/dev/null 2>&1; then \
			echo "❌ Poetry installation failed"; \
			exit 1; \
		fi; \
		echo "Poetry installed successfully!"; \
	else \
		echo "✓ Poetry is already installed: $$(poetry --version)"; \
	fi
	@echo ""
	@echo "[2/2] Checking Python version..."
	@PYTHON_VERSION=$$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1); \
	REQUIRED_VERSION="3.11"; \
	PYTHON_TO_INSTALL="3.11.7"; \
	if [ -z "$$PYTHON_VERSION" ]; then \
		echo "❌ Python 3 not found!"; \
		if command -v pyenv >/dev/null 2>&1; then \
			echo "Installing Python $$PYTHON_TO_INSTALL via pyenv..."; \
			pyenv install -s $$PYTHON_TO_INSTALL && \
			pyenv local $$PYTHON_TO_INSTALL && \
			echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!"; \
		else \
			echo "❌ Cannot auto-install Python in CI without pyenv"; \
			exit 1; \
		fi; \
	fi; \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$PYTHON_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo "❌ Python $$PYTHON_VERSION detected (requires $$REQUIRED_VERSION or higher)"; \
		if command -v pyenv >/dev/null 2>&1; then \
			INSTALLED_311=$$(pyenv versions 2>/dev/null | grep -E '^\s*3\.(1[1-9]|[2-9][0-9])' | head -1 | tr -d ' *'); \
			if [ -n "$$INSTALLED_311" ]; then \
				echo "✓ Activating existing Python version: $$INSTALLED_311"; \
				pyenv local $$INSTALLED_311 && \
				echo "✓ Python $$INSTALLED_311 activated!"; \
			else \
				echo "Installing Python $$PYTHON_TO_INSTALL via pyenv..."; \
				pyenv install -s $$PYTHON_TO_INSTALL && \
				pyenv local $$PYTHON_TO_INSTALL && \
				echo "✓ Python $$PYTHON_TO_INSTALL installed and activated!"; \
			fi; \
		else \
			echo "❌ Cannot auto-install Python in CI without pyenv"; \
			exit 1; \
		fi; \
	else \
		echo "✓ Python $$PYTHON_VERSION detected (meets requirement $$REQUIRED_VERSION+)"; \
	fi
	@echo ""
	@echo "Installing dependencies..."
	@poetry install --no-interaction
	@echo "✅ CI installation complete!"

test-boundaries:
	@echo "Running root-level tests..."
	poetry run pytest tests/ -v --ignore=tests/integration/

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

test: test-boundaries test-modules test-integration
	@echo "✅ All tests passed (boundaries + modules + integration)"

# Coverage targets
test-cov: test-boundaries
	@echo "Running all tests with coverage..."
	poetry run pytest -x --cov=trading_api --cov-report=xml --cov-report=term-missing

# Linting and formatting
lint:
	@echo "Running backend linting..."
	poetry run flake8 src/ tests/

type-check:
	@echo "Running backend linting with full checks..."
	poetry run black --check src/ tests/
	poetry run isort --check-only src/ tests/
	poetry run flake8 src/ tests/
	poetry run mypy src/
	@echo "Running pyright type checking..."
	poetry run pyright src/

format:
	@echo "Formatting backend code..."
	poetry run autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive src/ tests/
	poetry run black src/ tests/
	poetry run isort src/ tests/
	@echo "Removing trailing whitespace..."
	@find src/ tests/ -name "*.py" -type f -exec sed -i 's/[[:space:]]*$$//' {} +
	@echo "✅ Backend formatting complete"

# Development server
dev: clean-generated
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
	poetry run python -m debugpy --listen 0.0.0.0:5678 -m uvicorn "trading_api.main:$(BACKEND_APP_NAME)" \
		--reload \
		--reload-exclude '*/openapi.json' \
		--reload-exclude '*/asyncapi.json' \
		--reload-exclude '*/clients/*' \
		--reload-exclude '*/ws_generated/*' \
		--reload-exclude '*/.local/*' \
		--reload-exclude '*/.pids/*' \
		--reload-exclude '*/scripts/*' \
		--reload-exclude '*/__pycache__/*' \
		--reload-exclude '*.pyc' \
		--host 0.0.0.0 \
		--port $(BACKEND_PORT) \
		--log-level info

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
	@echo "Generating WebSocket routers..."
	@$(MAKE) generate-ws-routers
	poetry build

# CI health check
health-ci:
	@echo "Testing API endpoints for CI..."
	curl -f http://localhost:$(BACKEND_PORT)/api/v1/core/health || exit 1
	curl -f http://localhost:$(BACKEND_PORT)/api/v1/core/version || exit 1

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

# Clean all generated files using *_generated* pattern
clean-generated:
	@echo "🧹 Cleaning all generated files..."
	@echo ""
	@echo "Searching for *_generated* files and directories..."
	@find . -name "*_generated*" -type f -o -name "*_generated*" -type d | while read item; do \
		if [ -f "$$item" ]; then \
			echo "  ✓ Removing file: $$item"; \
			rm -f "$$item"; \
		elif [ -d "$$item" ]; then \
			echo "  ✓ Removing directory: $$item"; \
			rm -rf "$$item"; \
		fi; \
	done
	@echo ""
	@echo "✅ All generated files removed!"
	@echo ""
	@echo "💡 Tip: Regenerate files with:"
	@echo "   make generate-ws-routers       # WebSocket routers"
	@echo "   make export-openapi-spec       # OpenAPI specs"
	@echo "   make export-asyncapi-spec      # AsyncAPI specs"
	@echo "   make generate-python-clients   # Python HTTP clients"


# Export OpenAPI specification (offline) - DEPRECATED
export-openapi-spec:
	@echo "⚠️  ========================================================================="
	@echo "⚠️  DEPRECATED: 'make export-openapi-spec' is deprecated"
	@echo "⚠️  "
	@echo "⚠️  Use instead:"
	@echo "⚠️    make generate              # Generate for all modules"
	@echo "⚠️    make generate modules=broker  # Generate for specific module"
	@echo "⚠️  "
	@echo "⚠️  The new 'make generate' command generates:"
	@echo "⚠️    - OpenAPI specs"
	@echo "⚠️    - AsyncAPI specs"
	@echo "⚠️    - Python HTTP clients"
	@echo "⚠️  "
	@echo "⚠️  Note: WebSocket routers auto-generate at module init (no manual step needed)"
	@echo "⚠️  ========================================================================="
	@echo ""
	@sleep 3
	@echo "Running legacy export-openapi-spec script..."
	poetry run python scripts/export_openapi_spec.py

# Export AsyncAPI specification (offline) - DEPRECATED
export-asyncapi-spec:
	@echo "⚠️  ========================================================================="
	@echo "⚠️  DEPRECATED: 'make export-asyncapi-spec' is deprecated"
	@echo "⚠️  "
	@echo "⚠️  Use instead:"
	@echo "⚠️    make generate              # Generate for all modules"
	@echo "⚠️    make generate modules=broker  # Generate for specific module"
	@echo "⚠️  "
	@echo "⚠️  The new 'make generate' command generates:"
	@echo "⚠️    - OpenAPI specs"
	@echo "⚠️    - AsyncAPI specs"
	@echo "⚠️    - Python HTTP clients"
	@echo "⚠️  "
	@echo "⚠️  Note: WebSocket routers auto-generate at module init (no manual step needed)"
	@echo "⚠️  ========================================================================="
	@echo ""
	@sleep 3
	@echo "Running legacy export-asyncapi-spec script..."
	poetry run python scripts/export_asyncapi_spec.py

# Generate Python HTTP clients from per-module OpenAPI specs - DEPRECATED
generate-python-clients:
	@echo "⚠️  ========================================================================="
	@echo "⚠️  DEPRECATED: 'make generate-python-clients' is deprecated"
	@echo "⚠️  "
	@echo "⚠️  Use instead:"
	@echo "⚠️    make generate              # Generate for all modules"
	@echo "⚠️    make generate modules=broker  # Generate for specific module"
	@echo "⚠️  "
	@echo "⚠️  The new 'make generate' command generates:"
	@echo "⚠️    - OpenAPI specs"
	@echo "⚠️    - AsyncAPI specs"
	@echo "⚠️    - Python HTTP clients"
	@echo "⚠️  "
	@echo "⚠️  Note: WebSocket routers auto-generate at module init (no manual step needed)"
	@echo "⚠️  ========================================================================="
	@echo ""
	@sleep 3
	@echo "Running legacy generate-python-clients script..."
	poetry run python scripts/generate_python_clients.py
	@echo ""
	@echo "Formatting generated clients..."
	poetry run autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive src/trading_api/clients/
	poetry run black src/trading_api/clients/
	poetry run isort src/trading_api/clients/
	@echo ""
	@echo "Validating generated clients..."
	poetry run black --check src/trading_api/clients/
	poetry run isort --check-only src/trading_api/clients/
	poetry run flake8 src/trading_api/clients/
	poetry run mypy src/trading_api/clients/
	poetry run pyright src/trading_api/clients/
	@echo ""
	@echo "✅ Client generation complete and validated!"

# Generate WebSocket router classes - DEPRECATED
# Usage: make generate-ws-routers [module=<module_name>]
# Note: WebSocket routers are now generated automatically at module initialization
generate-ws-routers:
	@echo "⚠️  ========================================================================="
	@echo "⚠️  DEPRECATED: 'make generate-ws-routers' is deprecated"
	@echo "⚠️  "
	@echo "⚠️  WebSocket routers are now generated automatically at module init!"
	@echo "⚠️  "
	@echo "⚠️  Router generation happens in ws.py files when you:"
	@echo "⚠️    - Import the module"
	@echo "⚠️    - Start the backend server"
	@echo "⚠️    - Run make generate (triggers module initialization)"
	@echo "⚠️  "
	@echo "⚠️  No manual generation needed anymore!"
	@echo "⚠️  ========================================================================="
	@echo ""
	@sleep 3
	@echo "Running legacy generate-ws-routers for compatibility..."
	@if [ -n "$(module)" ]; then \
		echo "Generating WebSocket routers for module: $(module)"; \
		poetry run python -c "\
from trading_api.shared.ws.module_router_generator import generate_module_routers; \
import sys; \
result = generate_module_routers('$(module)', silent=False, skip_quality_checks=False); \
sys.exit(0 if result else 1)"; \
	else \
		echo "Generating WebSocket routers for all modules with ws.py files..."; \
		for mod in $(DISCOVERED_MODULES); do \
			echo ""; \
			echo "Checking module: $$mod"; \
			poetry run python -c "\
from trading_api.shared.ws.module_router_generator import generate_module_routers; \
result = generate_module_routers('$$mod', silent=False, skip_quality_checks=False); \
exit(0)" || true; \
		done; \
		echo ""; \
		echo "✅ Router generation complete!"; \
	fi

# Multi-process backend management (using backend-manager)
backend-manager-start:
	@echo "Checking nginx installation..."
	@if [ -f ".local/bin/nginx" ]; then \
		echo "✅ Local nginx available: $$(.local/bin/nginx -v 2>&1)"; \
	elif command -v nginx >/dev/null 2>&1; then \
		echo "✅ System nginx available: $$(nginx -v 2>&1)"; \
	else \
		echo "❌ nginx not found!"; \
		echo ""; \
		echo "Install options:"; \
		echo "  1. Standalone (no sudo): poetry run python scripts/install_nginx.py"; \
		echo "  2. System package: sudo apt install nginx"; \
		exit 1; \
	fi
	@CONFIG=$${config:-dev-config.yaml}; \
	echo "Starting multi-process backend with config: $$CONFIG"; \
	poetry run python scripts/backend_manager.py start $$CONFIG --generate-nginx

backend-manager-stop:
	@CONFIG=$${config:-dev-config.yaml}; \
	echo "Stopping multi-process backend..."; \
	poetry run python scripts/backend_manager.py stop $$CONFIG

backend-manager-status:
	@CONFIG=$${config:-dev-config.yaml}; \
	poetry run python scripts/backend_manager.py status $$CONFIG

backend-manager-restart:
	@echo "Checking nginx installation..."
	@if [ -f ".local/bin/nginx" ]; then \
		echo "✅ Local nginx available: $$(.local/bin/nginx -v 2>&1)"; \
	elif command -v nginx >/dev/null 2>&1; then \
		echo "✅ System nginx available: $$(nginx -v 2>&1)"; \
	else \
		echo "❌ nginx not found!"; \
		echo ""; \
		echo "Install options:"; \
		echo "  1. Standalone (no sudo): poetry run python scripts/install_nginx.py"; \
		echo "  2. System package: sudo apt install nginx"; \
		exit 1; \
	fi
	@CONFIG=$${config:-dev-config.yaml}; \
	echo "Restarting multi-process backend with config: $$CONFIG"; \
	poetry run python scripts/backend_manager.py restart $$CONFIG --generate-nginx

backend-manager-gen-nginx-conf:
	@CONFIG=$${config:-dev-config.yaml}; \
	OUTPUT=$${output:-nginx-dev.conf}; \
	echo "Generating nginx config from $$CONFIG to $$OUTPUT"; \
	poetry run python scripts/backend_manager.py gen-nginx-conf $$CONFIG -o $$OUTPUT --validate

# Logging commands
logs-tail:
	@echo "📋 Tailing all backend server logs..."
	@echo "Press Ctrl+C to stop"
	@echo ""
	@if [ -d ".local/logs" ] && ls .local/logs/*-*.log >/dev/null 2>&1; then \
		tail -f .local/logs/broker-*.log .local/logs/datafeed-*.log 2>/dev/null | awk '{print "[" strftime("%H:%M:%S") "] " $$0}'; \
	else \
		echo "❌ No server log files found in .local/logs/"; \
		echo "Start the backend first: make backend-manager-start"; \
		exit 1; \
	fi

logs-tail-nginx:
	@echo "📋 Tailing nginx logs..."
	@echo "Press Ctrl+C to stop"
	@echo ""
	@if [ -f ".local/logs/nginx-access.log" ] || [ -f ".local/logs/nginx-error.log" ]; then \
		tail -f .local/logs/nginx-*.log 2>/dev/null; \
	else \
		echo "❌ Nginx log files not found"; \
		echo "Start the backend first: make backend-manager-start"; \
		exit 1; \
	fi

logs-clean:
	@echo "🧹 Cleaning backend log files..."
	@if [ -d ".local/logs" ]; then \
		for file in .local/logs/*.log; do \
			[ -f "$$file" ] && > "$$file"; \
		done; \
		echo "✅ All log files cleaned (truncated)"; \
	else \
		echo "✅ No log directory found (nothing to clean)"; \
	fi
