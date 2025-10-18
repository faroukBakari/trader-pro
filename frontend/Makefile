# TraderPRO Frontend Makefile

# Source nvm and use .nvmrc for all commands
SHELL := /bin/bash
NVM_SH := $(HOME)/.nvm/nvm.sh
export NVM_DIR := $(HOME)/.nvm

# Function to run commands with nvm sourced
define ensure-node-version
	@bash -c ' \
	NODE_VERSION=$$(node --version 2>&1 | grep -oP "\d+\.\d+\.\d+" | head -1 || echo ""); \
	NODE_MAJOR=$$(echo $$NODE_VERSION | cut -d. -f1); \
	NODE_MINOR=$$(echo $$NODE_VERSION | cut -d. -f2); \
	VALID=0; \
	if [ "$$NODE_MAJOR" -gt 22 ]; then \
		VALID=1; \
	elif [ "$$NODE_MAJOR" -eq 22 ] && [ "$$NODE_MINOR" -ge 20 ]; then \
		VALID=1; \
	fi; \
	if [ "$$VALID" -eq 1 ]; then \
		echo "✓ Node.js $$NODE_VERSION detected (meets requirement 22.20+)"; \
		$(1); \
		exit $$?; \
	fi; \
	export NVM_DIR="$(NVM_DIR)"; \
	if [ ! -s "$(NVM_SH)" ]; then \
		echo "❌ Error: nvm not found at $(NVM_SH)"; \
		echo ""; \
		echo "Please install nvm:"; \
		echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash"; \
		echo ""; \
		echo "Then restart your shell or run:"; \
		echo "  source ~/.nvm/nvm.sh"; \
		exit 1; \
	fi; \
	. "$(NVM_SH)" || { \
		echo "❌ Error: Failed to source nvm from $(NVM_SH)"; \
		echo ""; \
		echo "Please check your nvm installation:"; \
		echo "  1. Verify nvm.sh exists: ls -la $(NVM_SH)"; \
		echo "  2. Try sourcing manually: source $(NVM_SH)"; \
		echo "  3. Reinstall nvm if needed"; \
		exit 1; \
	}; \
	if ! nvm use 2>/dev/null; then \
		REQUIRED_VERSION=$$(cat .nvmrc 2>/dev/null || echo "22.20.0"); \
		echo "❌ Error: Failed to activate Node.js version from .nvmrc ($$REQUIRED_VERSION)"; \
		echo ""; \
		echo "The required Node.js version is not installed."; \
		echo ""; \
		echo "Please install it with:"; \
		echo "  nvm install $$REQUIRED_VERSION"; \
		echo "  nvm use $$REQUIRED_VERSION"; \
		echo ""; \
		echo "Or run: make ensure-node"; \
		exit 1; \
	fi; \
	$(1)'
endef

.PHONY: help ensure-node install install-ci lint type-check test build dev clean generate-openapi-client generate-asyncapi-types

# Default target
help:
	@echo "Frontend targets:"
	@echo "  ensure-node     Ensure Node.js 22.20+ is installed (offers auto-install)"
	@echo "  install         Install frontend dependencies"
	@echo "  install-ci      Install frontend dependencies for CI"
	@echo "  generate-openapi-client   Generate REST client from OpenAPI spec"
	@echo "  generate-asyncapi-types   Generate WebSocket types from AsyncAPI spec"
	@echo "  lint            Run frontend linting and formatting checks"
	@echo "  type-check      Run TypeScript type checking"
	@echo "  test            Run frontend tests once"
	@echo "  build           Build frontend for production"
	@echo "  dev             Start frontend development server"
	@echo "  clean           Clean build artifacts"

# Ensure Node.js 22.20+ is available
ensure-node:
	@echo "Checking Node.js version..."
	@bash -c ' \
	export NVM_DIR="$$HOME/.nvm"; \
	[ -s "$$NVM_DIR/nvm.sh" ] && . "$$NVM_DIR/nvm.sh"; \
	NODE_VERSION=$$(node --version 2>&1 | grep -oP "\d+\.\d+\.\d+" | head -1 || echo ""); \
	REQUIRED_MIN="22.20.0"; \
	NODE_TO_INSTALL="22.20.0"; \
	if [ -z "$$NODE_VERSION" ]; then \
		echo "❌ Node.js not found!"; \
		echo ""; \
		if command -v nvm >/dev/null 2>&1 || [ "$$(type nvm 2>/dev/null)" ]; then \
			echo "Would you like to install Node.js $$NODE_TO_INSTALL via nvm? [y/N]"; \
			read -r REPLY; \
			if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
				echo "Installing Node.js $$NODE_TO_INSTALL..."; \
				nvm install $$NODE_TO_INSTALL && \
				nvm use $$NODE_TO_INSTALL && \
				echo "✓ Node.js $$NODE_TO_INSTALL installed and activated!" && \
				exit 0; \
			fi; \
		fi; \
		echo "Please install Node.js 22.20+:"; \
		echo "  - Using nvm (recommended): nvm install $$NODE_TO_INSTALL && nvm use $$NODE_TO_INSTALL"; \
		echo "  - Download from: https://nodejs.org/"; \
		exit 1; \
	fi; \
	NODE_MAJOR=$$(echo $$NODE_VERSION | cut -d. -f1); \
	NODE_MINOR=$$(echo $$NODE_VERSION | cut -d. -f2); \
	VALID=0; \
	if [ "$$NODE_MAJOR" -gt 22 ]; then \
		VALID=1; \
	elif [ "$$NODE_MAJOR" -eq 22 ] && [ "$$NODE_MINOR" -ge 20 ]; then \
		VALID=1; \
	fi; \
	if [ "$$VALID" -eq 0 ]; then \
		echo "❌ Node.js $$NODE_VERSION detected (requires 22.20+)"; \
		echo ""; \
		if command -v nvm >/dev/null 2>&1 || [ "$$(type nvm 2>/dev/null)" ]; then \
			INSTALLED_VALID=$$(nvm list 2>/dev/null | grep -oE "v(22\\.(2[0-9]|[3-9][0-9])|2[3-9]\\.[0-9]+|[3-9][0-9]\\.[0-9]+)\\.[0-9]+" | head -1 | cut -c2-); \
			if [ -n "$$INSTALLED_VALID" ]; then \
				echo "✓ Found existing valid Node.js version: $$INSTALLED_VALID - activating it..."; \
				nvm use $$INSTALLED_VALID && \
				echo "✓ Node.js $$INSTALLED_VALID activated!" && \
				exit 0; \
			else \
				echo "Would you like to install Node.js $$NODE_TO_INSTALL via nvm? [y/N]"; \
				read -r REPLY; \
				if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
					echo "Installing Node.js $$NODE_TO_INSTALL..."; \
					nvm install $$NODE_TO_INSTALL && \
					nvm use $$NODE_TO_INSTALL && \
					echo "✓ Node.js $$NODE_TO_INSTALL installed and activated!" && \
					exit 0; \
				fi; \
			fi; \
			echo ""; \
			echo "Manual installation:"; \
			echo "  nvm install $$NODE_TO_INSTALL"; \
			echo "  nvm use $$NODE_TO_INSTALL"; \
		else \
			echo "nvm not found. Install it for automatic Node.js version management:"; \
			echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash"; \
			echo ""; \
			echo "Or install Node.js 22.20+ manually:"; \
			echo "  Download from: https://nodejs.org/"; \
		fi; \
		exit 1; \
	else \
		echo "✓ Node.js $$NODE_VERSION detected (meets requirement 22.20+)"; \
	fi \
	'

# Dependency management
install: ensure-node
	@echo "Installing frontend dependencies..."
	$(call ensure-node-version,npm install)
	@echo ""
	@echo "💡 Tip: Install Git hooks with: make -f ../project.mk install-hooks"

install-ci:
	@echo "Installing frontend dependencies for CI..."
	@npm ci

# Client generation
generate-openapi-client:
	@echo "Generating REST client from OpenAPI spec..."
	@bash -c 'export NVM_DIR="$(NVM_DIR)"; [ -s "$(NVM_SH)" ] && . "$(NVM_SH)"; nvm use 2>/dev/null || true; ./scripts/generate-openapi-client.sh'

generate-asyncapi-types:
	@echo "Generating WebSocket types from AsyncAPI spec..."
	@bash -c 'export NVM_DIR="$(NVM_DIR)"; [ -s "$(NVM_SH)" ] && . "$(NVM_SH)"; nvm use 2>/dev/null || true; ./scripts/generate-asyncapi-types.sh'

# Linting and formatting
lint:
	@echo "Running frontend linting and formatting checks..."
	@$(MAKE) generate-openapi-client
	@$(MAKE) generate-asyncapi-types
	$(call ensure-node-version,npm run lint)

# Type checking
type-check:
	@echo "Running TypeScript type checking..."
	@$(MAKE) generate-openapi-client
	@$(MAKE) generate-asyncapi-types
	$(call ensure-node-version,npm run type-check)

# Testing
test:
	@echo "Running frontend tests..."
	@$(MAKE) generate-openapi-client
	@$(MAKE) generate-asyncapi-types
	$(call ensure-node-version,npm run test:run)

# Build
build:
	@echo "Building frontend for production..."
	$(call ensure-node-version,npm run build)

# Development server
dev:
	@echo "Starting frontend development server..."
	@echo "🔍 Checking if frontend port is available..."
	@if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "❌ Error: Frontend port 5173 is already in use!"; \
		echo ""; \
		echo "Process using port 5173:"; \
		lsof -Pi :5173 -sTCP:LISTEN; \
		echo ""; \
		echo "Please stop the existing server or change the port in vite.config.ts"; \
		exit 1; \
	fi
	@echo "✅ Port 5173 is available"
	$(call ensure-node-version,npm run dev)

# Cleanup
clean:
	@echo "Cleaning frontend build artifacts..."
	rm -rf dist/ node_modules/.vite src/clients/*
	@echo "Frontend clean complete."
