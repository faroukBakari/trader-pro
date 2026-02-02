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

# Dynamic provider discovery
PROVIDERS_DIR = src/trading_api/providers
DISCOVERED_PROVIDERS = $(shell find $(PROVIDERS_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -vE '__pycache__|tests|capabilities' || echo "")

# Provider selection (can be overridden: make test-providers providers=google,tws)

# Dynamic datastore discovery
DATASTORES_DIR = src/trading_api/datastores
DISCOVERED_DATASTORES = $(shell find $(DATASTORES_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -v __pycache__ || echo "")
ifdef providers
	SELECTED_PROVIDERS = $(subst $(comma), ,$(providers))
else
	SELECTED_PROVIDERS = $(DISCOVERED_PROVIDERS)
endif

comma := ,

.PHONY: help install install-ci test test-full test-boundaries test-boundaries-full test-modules test-modules-full test-cov test-integration test-integration-full lint type-check format build clean clean-cache clean-generated dev dev-ci kill-dev health-ci list-modules list-modules-json generate backend-manager-start backend-manager-stop backend-manager-status backend-manager-restart backend-manager-gen-nginx-conf logs-tail logs-tail-nginx logs-clean install-tws-api show-cache show-cache-json show-cache-symbol $(addprefix test-module-, $(DISCOVERED_MODULES)) test-providers test-providers-full test-providers-core test-providers-core-full list-providers list-providers-json list-datastores list-datastores-json $(addprefix test-provider-, $(DISCOVERED_PROVIDERS)) testmon-forcerun testmon-reset testmon-status

# Default target
help:
	@echo "Backend targets:"
	@echo "  install           Install backend dependencies (auto-checks Python/Poetry/nginx)"
	@echo "  install-ci        Install backend dependencies for CI (non-interactive)"
	@echo ""
	@echo "Testing (default: incremental with testmon, add -full suffix for complete runs):"
	@echo "  test              Run all tests (incremental)"
	@echo "  test-full         Run all tests (complete suite)"
	@echo "  test-boundaries   Validate import boundaries (incremental)"
	@echo "  test-providers    Run all provider tests (incremental)"
	@echo "  test-modules      Run module tests (modules=x,y to select)"
	@echo "  test-integration  Run integration tests (incremental)"
	@echo "  test-cov          Run tests with coverage (always full)"
	@echo ""
	@echo "Testmon utilities:"
	@echo "  testmon-forcerun  Force full run + rebuild database"
	@echo "  testmon-reset     Clear testmon database"
	@echo "  testmon-status    Show testmon database status"
	@echo ""
	@echo "Module-specific test targets (auto-discovered):"
	@for module in $(DISCOVERED_MODULES); do \
		echo "  test-module-$$module"; \
	done
	@echo ""
	@echo "Provider-specific test targets (auto-discovered):"
	@for provider in $(DISCOVERED_PROVIDERS); do \
		echo "  test-provider-$$provider"; \
	done
	@echo ""
	@echo "Code quality targets:"
	@echo "  lint              Run backend linting (flake8 only)"
	@echo "  type-check        Run backend linting with type checking (black, isort, flake8, mypy, pyright)"
	@echo "  format            Format backend code"
	@echo ""
	@echo "Cleanup targets:"
	@echo "  clean             Remove build artifacts and generated files"
	@echo "  clean-cache       Remove Python caches (__pycache__, .pytest_cache, etc.)"
	@echo "  clean-coverage    Remove coverage files (.coverage, coverage.xml, htmlcov/)"
	@echo "  clean-generated   Remove all generated files (*_generated*)"
	@echo ""
	@echo "TWS API targets:"
	@echo "  install-tws-api   Install TWS API with protobuf regeneration and validation"
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
	@echo ""
	@echo "Logging targets:"
	@echo "  logs-tail         Tail unified backend log (all servers with prefixes)"
	@echo "  logs-tail-nginx   Tail nginx logs (access + error)"
	@echo "  logs-clean        Clean all backend log files"
	@echo ""
	@echo "Cache inspection targets:"
	@echo "  show-cache        Show contract cache statistics and latest records"
	@echo "  show-cache-json   Show contract cache statistics in JSON format"
	@echo "  show-cache-symbol Show contracts matching symbol (usage: make show-cache-symbol symbol=AAPL)"
	@echo ""
	@echo "Discovered modules: $(DISCOVERED_MODULES)"
	@echo "Discovered providers: $(DISCOVERED_PROVIDERS)"

# List all discovered modules
list-modules:
	@echo "📦 Discovered modules:"
	@for module in $(DISCOVERED_MODULES); do \
		echo "  - $$module"; \
	done

# List modules as JSON array (for CI dynamic matrix)
list-modules-json:
	@echo '$(DISCOVERED_MODULES)' | tr ' ' '\n' | grep -v '^$$' | jq -R -s -c 'split("\n") | map(select(. != ""))'

# List all discovered providers
list-providers:
	@echo "📦 Discovered providers:"
	@for provider in $(DISCOVERED_PROVIDERS); do \
		echo "  - $$provider"; \
	done

# List providers as JSON array (for CI dynamic matrix)
list-providers-json:
	@echo '$(DISCOVERED_PROVIDERS)' | tr ' ' '\n' | grep -v '^$$' | jq -R -s -c 'split("\n") | map(select(. != ""))'

# List all discovered datastores
list-datastores:
	@echo "📦 Discovered datastores:"
	@for datastore in $(DISCOVERED_DATASTORES); do \
		echo "  - $$datastore"; \
	done

# List datastores as JSON array (for CI dynamic matrix)
list-datastores-json:
	@echo '$(DISCOVERED_DATASTORES)' | tr ' ' '\n' | grep -v '^$$' | jq -R -s -c 'split("\n") | map(select(. != ""))'

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
	@echo "[3/4] Regenerating TWS protobufs..."
	@bash ./scripts/regenerate_tws_protobufs.sh
	@echo ""
	@echo "[4/4] Checking nginx (required for multi-process mode)..."
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
	@echo ""
	@echo "Regenerating TWS protobufs..."
	@bash ./scripts/regenerate_tws_protobufs.sh
	@echo "✅ CI installation complete!"

test-boundaries: check-generate-keypair check-generate-hmac-key
	@echo "Running root-level tests (incremental)..."
	@# test_import_boundaries scans files dynamically - testmon can't track dependencies
	@# Always run it explicitly, then run remaining tests with testmon
	poetry run pytest tests/test_import_boundaries.py -v $(ARGS)
	poetry run pytest tests/ -v --testmon --ignore=tests/integration/ --ignore=tests/test_import_boundaries.py $(ARGS)

test-boundaries-full: check-generate-keypair check-generate-hmac-key
	@echo "Running root-level tests (full)..."
	poetry run pytest tests/ -v --ignore=tests/integration/ $(ARGS)

# Provider core tests (registry, capability spec)
test-providers-core: check-generate-keypair check-generate-hmac-key
	@echo "Running provider core tests (incremental)..."
	poetry run pytest src/trading_api/providers/tests/ -v --testmon $(ARGS)

test-providers-core-full: check-generate-keypair check-generate-hmac-key
	@echo "Running provider core tests (full)..."
	poetry run pytest src/trading_api/providers/tests/ -v $(ARGS)

# All provider tests (core + all discovered providers)
test-providers: test-providers-core
	@echo "Running all provider tests (incremental)..."
	@if [ -z "$(SELECTED_PROVIDERS)" ]; then \
		echo "⚠️  No providers selected or found"; \
	else \
		echo "Testing providers: $(SELECTED_PROVIDERS)"; \
		for provider in $(SELECTED_PROVIDERS); do \
			if [ -d "$(PROVIDERS_DIR)/$$provider/tests" ]; then \
				echo "Testing provider: $$provider"; \
				poetry run pytest --testmon $(PROVIDERS_DIR)/$$provider/tests/ -v -x $(ARGS); \
				EXIT_CODE=$$?; \
				if [ $$EXIT_CODE -eq 5 ]; then \
					echo "⚠️  No tests collected for provider: $$provider (skipping)"; \
				elif [ $$EXIT_CODE -ne 0 ]; then \
					exit 1; \
				fi; \
			else \
				echo "⚠️  No tests found for provider: $$provider"; \
			fi; \
		done; \
	fi

test-providers-full: test-providers-core-full
	@echo "Running all provider tests (full)..."
	@if [ -z "$(SELECTED_PROVIDERS)" ]; then \
		echo "⚠️  No providers selected or found"; \
	else \
		echo "Testing providers: $(SELECTED_PROVIDERS)"; \
		for provider in $(SELECTED_PROVIDERS); do \
			if [ -d "$(PROVIDERS_DIR)/$$provider/tests" ]; then \
				echo "Testing provider: $$provider"; \
				poetry run pytest $(PROVIDERS_DIR)/$$provider/tests/ -v -x $(ARGS); \
				EXIT_CODE=$$?; \
				if [ $$EXIT_CODE -eq 5 ]; then \
					echo "⚠️  No tests collected for provider: $$provider (skipping)"; \
				elif [ $$EXIT_CODE -ne 0 ]; then \
					exit 1; \
				fi; \
			else \
				echo "⚠️  No tests found for provider: $$provider"; \
			fi; \
		done; \
	fi

test-modules: check-generate-keypair check-generate-hmac-key
	@echo "Running module tests (incremental)..."
	@if [ -z "$(SELECTED_MODULES)" ]; then \
		echo "⚠️  No modules selected or found"; \
	else \
		echo "Testing modules: $(SELECTED_MODULES)"; \
		for module in $(SELECTED_MODULES); do \
			if [ -d "$(MODULES_DIR)/$$module/tests" ]; then \
				echo "Testing module: $$module"; \
				poetry run pytest --testmon $(MODULES_DIR)/$$module/tests/ -v -x $(ARGS); \
				EXIT_CODE=$$?; \
				if [ $$EXIT_CODE -eq 5 ]; then \
					echo "⚠️  No tests collected for module: $$module (skipping)"; \
				elif [ $$EXIT_CODE -ne 0 ]; then \
					exit 1; \
				fi; \
			else \
				echo "⚠️  No tests found for module: $$module"; \
			fi; \
		done; \
	fi

test-modules-full: check-generate-keypair check-generate-hmac-key
	@echo "Running module tests (full)..."
	@if [ -z "$(SELECTED_MODULES)" ]; then \
		echo "⚠️  No modules selected or found"; \
	else \
		echo "Testing modules: $(SELECTED_MODULES)"; \
		for module in $(SELECTED_MODULES); do \
			if [ -d "$(MODULES_DIR)/$$module/tests" ]; then \
				echo "Testing module: $$module"; \
				poetry run pytest $(MODULES_DIR)/$$module/tests/ -v -x $(ARGS); \
				EXIT_CODE=$$?; \
				if [ $$EXIT_CODE -eq 5 ]; then \
					echo "⚠️  No tests collected for module: $$module (skipping)"; \
				elif [ $$EXIT_CODE -ne 0 ]; then \
					exit 1; \
				fi; \
			else \
				echo "⚠️  No tests found for module: $$module"; \
			fi; \
		done; \
	fi

# Individual module tests (auto-generated targets, incremental by default)
$(addprefix test-module-, $(DISCOVERED_MODULES)): test-module-%:
	@echo "Running tests for module: $* (incremental)..."
	@if [ -d "$(MODULES_DIR)/$*/tests" ]; then \
		poetry run pytest --testmon $(MODULES_DIR)/$*/tests/ -v -x $(ARGS); \
		EXIT_CODE=$$?; \
		if [ $$EXIT_CODE -eq 5 ]; then \
			echo "⚠️  No tests collected for module: $* (skipping)"; \
		elif [ $$EXIT_CODE -ne 0 ]; then \
			exit 1; \
		fi; \
	else \
		echo "⚠️  No tests found for module: $*"; \
	fi

# Individual provider tests (auto-generated targets, incremental by default)
$(addprefix test-provider-, $(DISCOVERED_PROVIDERS)): test-provider-%:
	@echo "Running tests for provider: $* (incremental)..."
	@if [ -d "$(PROVIDERS_DIR)/$*/tests" ]; then \
		poetry run pytest --testmon $(PROVIDERS_DIR)/$*/tests/ -v -x $(ARGS); \
		EXIT_CODE=$$?; \
		if [ $$EXIT_CODE -eq 5 ]; then \
			echo "⚠️  No tests collected for provider: $* (skipping)"; \
		elif [ $$EXIT_CODE -ne 0 ]; then \
			exit 1; \
		fi; \
	else \
		echo "⚠️  No tests found for provider: $*"; \
	fi

test-integration: check-generate-keypair check-generate-hmac-key
	@echo "Running integration tests (incremental)..."
	@# Backend manager tests require ordered execution, run without testmon
	poetry run pytest tests/integration/ -v -x --testmon -m integration --ignore=tests/integration/test_backend_manager_integration.py $(ARGS)
	poetry run pytest tests/integration/test_backend_manager_integration.py -v -x -m integration $(ARGS)

test-integration-full: check-generate-keypair check-generate-hmac-key
	@echo "Running integration tests (full)..."
	poetry run pytest tests/integration/ -v -x -m integration $(ARGS)

test: test-boundaries test-providers test-modules test-integration
	@echo "✅ All tests passed (incremental with testmon)"

test-full: test-boundaries-full test-providers-full test-modules-full test-integration-full
	@echo "✅ All tests passed (full suite)"

# Coverage targets
test-cov: check-generate-keypair check-generate-hmac-key test-boundaries
	@echo "Running all tests with coverage..."
	@poetry run pytest -x --cov=trading_api --cov-report=xml --cov-report=term-missing
	@echo ""
	@echo "Cleaning up coverage artifacts..."
	@rm -f .coverage.* 2>/dev/null || true
	@echo "✓ Removed intermediate .coverage.* files"
	@echo "✅ Coverage report generated: coverage.xml"

# ============================================
# TESTMON UTILITIES
# ============================================

# Force full test run (rebuild testmon database)
testmon-forcerun: check-generate-keypair check-generate-hmac-key testmon-reset
	@echo "Running all tests (rebuilding testmon database)..."
	poetry run pytest --testmon -v $(ARGS)

# Reset testmon database
testmon-reset:
	@echo "Resetting testmon database..."
	rm -f .testmondata
	@echo "✅ Testmon database cleared"

# Show testmon status
testmon-status:
	@if [ -f ".testmondata" ]; then \
		echo "✅ Testmon database exists"; \
		ls -lh .testmondata; \
	else \
		echo "⚠️  No testmon database found (run tests with --testmon first)"; \
	fi

# Linting and formatting
lint:
	@echo "Running backend linting..."
	poetry run flake8 src/ tests/

type-check:
	@echo "Running backend linting with full checks..."
	poetry run black --check --extend-exclude='/_generated/' src/ tests/
	poetry run isort --check-only src/ tests/
	poetry run flake8 src/ tests/
	poetry run mypy src/ --exclude='.*_generated'
	@echo "Running pyright type checking..."
	poetry run pyright src/ tests/

format:
	@echo "Formatting backend code..."
	poetry run autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive --exclude='*_generated' src/ tests/
	poetry run isort src/ tests/
	poetry run black --extend-exclude='/_generated/' src/ tests/
	@echo "Removing trailing whitespace..."
	@find src/ tests/ -name "*.py" -type f -not -path '*_generated/*' -exec sed -i 's/[[:space:]]*$$//' {} +
	@echo "✅ Backend formatting complete"

# Development server
dev: db-up
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
	@echo "Debug server listening on port 4444 (attach debugger to localhost:4444)"
	poetry run python -m debugpy --listen 0.0.0.0:4444 -m uvicorn "trading_api.main:$(BACKEND_APP_NAME)" \
		--reload \
		--reload-dir src/ \
		--reload-exclude '**/*__generated/*' \
		--reload-exclude '**/__pycache__/*' \
		--reload-exclude '**/*.pyc' \
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
	@poetry run uvicorn "trading_api.main:$(BACKEND_APP_NAME)" --host 0.0.0.0 --port $(BACKEND_PORT) > /dev/null 2>&1 & \
	echo "Waiting for backend to initialize..."; \
	for i in 1 2 3 4 5 6 7 8 9 10; do \
		sleep 1; \
		if lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
			echo "Backend is listening on port $(BACKEND_PORT)"; \
			break; \
		fi; \
	done; \
	echo "Waiting for backend startup sequence (codegen + reload cycles)..."; \
	sleep 8; \
	echo "Running health checks..."; \
	$(MAKE) health-ci

# Build
build:
	@echo "Building backend package..."
	poetry build

# CI health check
health-ci:
	@echo "🔍 Auto-discovering modules for health checks..."
	@MODULES=$$(find $(MODULES_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -v __pycache__ || echo ""); \
	if [ -z "$$MODULES" ]; then \
		echo "❌ No modules found in $(MODULES_DIR)"; \
		exit 1; \
	fi; \
	echo "Found modules: $$MODULES"; \
	echo ""; \
	FAILED=0; \
	for module in $$MODULES; do \
		echo "Checking $$module module..."; \
		SUCCESS=0; \
		for attempt in 1 2 3 4 5; do \
			if curl -f -s http://localhost:$(BACKEND_PORT)/api/v1/$$module/health > /dev/null 2>&1; then \
				echo "  ✅ $$module is healthy (attempt $$attempt)"; \
				SUCCESS=1; \
				break; \
			else \
				if [ $$attempt -lt 5 ]; then \
					echo "  ⏳ $$module not ready yet (attempt $$attempt/5), retrying in 2s..."; \
					sleep 2; \
				fi; \
			fi; \
		done; \
		if [ $$SUCCESS -eq 0 ]; then \
			echo "  ❌ $$module health check failed after 5 attempts"; \
			FAILED=1; \
		fi; \
	done; \
	echo ""; \
	if [ $$FAILED -eq 0 ]; then \
		echo "✅ All module health checks passed"; \
	else \
		echo "❌ Some module health checks failed"; \
		exit 1; \
	fi

# Cleanup
clean:
	@echo "Cleaning backend build artifacts..."
	@echo "Removing build directories..."
	@rm -rf dist/ build/ *.egg-info
	@echo "Removing generated files..."
	@$(MAKE) clean-generated
	@echo "Removing coverage files..."
	@$(MAKE) clean-coverage
	@echo "✅ Clean complete"

# Clean coverage files
clean-coverage:
	@echo "Cleaning coverage files..."
	@rm -f .coverage .coverage.* coverage.xml
	@rm -rf htmlcov/
	@echo "✓ Removed .coverage files"
	@echo "✓ Removed coverage.xml"
	@echo "✓ Removed htmlcov directory"

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
	@echo "   make generate                  # All specs, clients, and routers"
	@echo "   make generate modules=broker   # Specific module only"

# Multi-process backend (using backend-manager)
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

# TWS API Installation & Validation
.PHONY: install-tws-api

install-tws-api: ## Install TWS API with protobuf regeneration and validation
	@echo "========================================"
	@echo "Installing TWS API"
	@echo "========================================"
	@echo ""
	@echo "[1/3] Checking dependencies..."
	@if ! poetry run python -c "import grpc_tools.protoc" 2>/dev/null; then \
		echo "Installing grpcio-tools..."; \
		poetry add --group dev grpcio-tools; \
	else \
		echo "✓ grpcio-tools already installed"; \
	fi
	@if ! poetry run python -c "import mypy_protobuf" 2>/dev/null; then \
		echo "Installing mypy-protobuf..."; \
		poetry add --group dev mypy-protobuf; \
	else \
		echo "✓ mypy-protobuf already installed"; \
	fi
	@echo ""
	@echo "[2/3] Regenerating protobuf files..."
	@bash ./scripts/regenerate_tws_protobufs.sh
	@echo ""
	@echo "[3/3] Validating installation..."
	@poetry run python scripts/validate_tws_install.py
	@Cache inspection targets
.PHONY: show-cache show-cache-json show-cache-symbol

show-cache: ## Show contract cache statistics and latest records
	@echo "🔍 Inspecting contract cache..."
	@if [ ! -f ".local/DB/sqlite/contracts.db" ]; then \
		echo ""; \
		echo "❌ Cache database not found at .local/DB/sqlite/contracts.db"; \
		echo ""; \
		echo "💡 The cache is created after first use:"; \
		echo "   1. Start the backend: make dev"; \
		echo "   2. Search for symbols in the app (e.g., AAPL, MSFT)"; \
		echo "   3. Run this command again"; \
		exit 1; \
	fi
	@poetry run python scripts/inspect_contract_cache.py

show-cache-json: ## Show contract cache statistics in JSON format
	@poetry run python scripts/inspect_contract_cache.py --format json

show-cache-symbol: ## Show contracts matching symbol (usage: make show-cache-symbol symbol=AAPL)
	@if [ -z "$(symbol)" ]; then \
		echo "❌ Error: symbol parameter required"; \
		echo ""; \
		echo "Usage: make show-cache-symbol symbol=AAPL"; \
		exit 1; \
	fi
	@poetry run python scripts/inspect_contract_cache.py --symbol $(symbol)

# Database Management (PostgreSQL via Docker)
.PHONY: db-up db-down db-status db-logs db-psql

# Datastore configuration - loaded from .env, fallbacks for safety
DATASTORE_POSTGRES_PORT ?= 5433
DATASTORE_POSTGRES_DB ?= trader_pro

db-up: ## Start PostgreSQL database (docker-compose)
	@echo "🐘 Starting PostgreSQL database..."
	@DATASTORE_POSTGRES_PORT=$(DATASTORE_POSTGRES_PORT) DATASTORE_POSTGRES_DB=$(DATASTORE_POSTGRES_DB) \
		docker-compose -f docker-compose.dev.yml up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U trader -d $(DATASTORE_POSTGRES_DB) >/dev/null 2>&1; then \
			echo "✅ PostgreSQL is ready!"; \
			break; \
		fi; \
		echo "  Waiting... ($$i/10)"; \
		sleep 2; \
	done
	@echo ""
	@echo "Connection string: postgresql://trader:trader_dev@localhost:$(DATASTORE_POSTGRES_PORT)/$(DATASTORE_POSTGRES_DB)"

db-down: ## Stop PostgreSQL database
	@echo "🛑 Stopping PostgreSQL database..."
	@docker-compose -f docker-compose.dev.yml down
	@echo "✅ PostgreSQL stopped"

db-status: ## Show PostgreSQL container status
	@docker-compose -f docker-compose.dev.yml ps

db-logs: ## Tail PostgreSQL logs
	@docker-compose -f docker-compose.dev.yml logs -f postgres

db-psql: ## Connect to PostgreSQL via psql
	@docker-compose -f docker-compose.dev.yml exec postgres psql -U trader -d $(DATASTORE_POSTGRES_DB)

# Alembic Migrations (SQLModel Wave 2B)
.PHONY: alembic-upgrade alembic-downgrade alembic-revision alembic-current alembic-history db-migrate db-reset

alembic-upgrade: ## Run Alembic upgrade to head
	@echo "🔄 Running Alembic migrations..."
	poetry run alembic upgrade head
	@echo "✅ Migrations complete"

alembic-downgrade: ## Roll back one Alembic migration
	@echo "⏪ Rolling back one migration..."
	poetry run alembic downgrade -1
	@echo "✅ Rollback complete"

alembic-revision: ## Create new Alembic migration (usage: make alembic-revision msg="description")
	@if [ -z "$(msg)" ]; then \
		echo "❌ Error: Please provide a message"; \
		echo "Usage: make alembic-revision msg=\"your migration description\""; \
		exit 1; \
	fi
	poetry run alembic revision --autogenerate -m "$(msg)"

alembic-current: ## Show current Alembic revision
	poetry run alembic current

alembic-history: ## Show Alembic migration history
	poetry run alembic history

db-migrate: alembic-upgrade ## Alias for alembic-upgrade

db-reset: ## Reset database (destroy and recreate with migrations)
	@echo "⚠️  This will destroy all data in the database!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "🗑️  Destroying database..."
	docker-compose -f docker-compose.dev.yml down -v
	@echo "🐘 Recreating database..."
	docker-compose -f docker-compose.dev.yml up -d postgres
	@echo "⏳ Waiting for PostgreSQL to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U trader > /dev/null 2>&1; then \
			echo "✓ PostgreSQL is ready"; \
			break; \
		fi; \
		echo "  Attempt $$i/10 - waiting..."; \
		sleep 2; \
	done
	$(MAKE) alembic-upgrade
	@echo "========================================"
	@echo "✅ Database reset complete"
	@echo "========================================"

# JWT Key Pair Management
SECRETS_DIR := .local/secrets
PRIVATE_KEY := $(SECRETS_DIR)/jwt_private.pem
PUBLIC_KEY := $(SECRETS_DIR)/jwt_public.pem

.PHONY: check-generate-keypair
check-generate-keypair: ## Check and generate JWT key pair if missing
	@echo "🔐 Checking JWT key pair..."
	@if [ -f "$(PRIVATE_KEY)" ] && [ -f "$(PUBLIC_KEY)" ]; then \
		echo "✓ JWT key pair already exists"; \
		echo "  Private key: $(PRIVATE_KEY)"; \
		echo "  Public key: $(PUBLIC_KEY)"; \
	else \
		echo "⚠️  JWT key pair not found. Generating..."; \
		mkdir -p $(SECRETS_DIR); \
		openssl genrsa -out $(PRIVATE_KEY) 4096 2>/dev/null; \
		openssl rsa -in $(PRIVATE_KEY) -pubout -out $(PUBLIC_KEY) 2>/dev/null; \
		chmod 600 $(PRIVATE_KEY); \
		chmod 644 $(PUBLIC_KEY); \
		echo "✓ JWT key pair generated successfully"; \
		echo "  Private key: $(PRIVATE_KEY) (permissions: 600)"; \
		echo "  Public key: $(PUBLIC_KEY) (permissions: 644)"; \
		echo ""; \
		echo "📝 Add to .env.local:"; \
		echo "  JWT_ALGORITHM=RS256"; \
		echo "  JWT_PRIVATE_KEY_PATH=backend/.local/secrets/jwt_private.pem"; \
		echo "  JWT_PUBLIC_KEY_PATH=backend/.local/secrets/jwt_public.pem"; \
		echo "  ACCESS_TOKEN_EXPIRE_MINUTES=5"; \
	fi

# HMAC Key Management (for inter-module authentication)
HMAC_KEY_PATH := $(SECRETS_DIR)/hmac_internal.key

.PHONY: check-generate-hmac-key
check-generate-hmac-key: ## Check and generate HMAC key if missing
	@if [ ! -f "$(HMAC_KEY_PATH)" ]; then \
		echo "🔐 Generating HMAC key for inter-module auth..."; \
		mkdir -p $(SECRETS_DIR); \
		openssl rand -hex 32 > "$(HMAC_KEY_PATH)"; \
		chmod 600 "$(HMAC_KEY_PATH)"; \
		echo "✓ HMAC key generated at $(HMAC_KEY_PATH)"; \
	fi
