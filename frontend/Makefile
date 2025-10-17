# TraderPRO Frontend Makefile

# Source nvm and use .nvmrc for all commands
SHELL := /bin/bash
NVM_SH := $(HOME)/.nvm/nvm.sh
export NVM_DIR := $(HOME)/.nvm

# Function to run commands with nvm sourced
define run-with-nvm
	@bash -c 'export NVM_DIR="$(NVM_DIR)"; [ -s "$(NVM_SH)" ] && . "$(NVM_SH)"; nvm use 2>/dev/null || true; $(1)'
endef

.PHONY: help ensure-node ensure-node-ci install install-ci lint type-check test test-run build dev clean generate-openapi-client generate-asyncapi-types

# Default target
help:
	@echo "Frontend targets:"
	@echo "  ensure-node     Ensure Node.js 20.19+/22.12+ is installed (offers auto-install)"
	@echo "  ensure-node-ci  Ensure Node.js 20.19+/22.12+ is installed (CI mode, no prompts)"
	@echo "  install         Install frontend dependencies"
	@echo "  install-ci      Install frontend dependencies for CI"
	@echo "  generate-openapi-client   Generate REST client from OpenAPI spec"
	@echo "  generate-asyncapi-types   Generate WebSocket types from AsyncAPI spec"
	@echo "  lint            Run frontend linting and formatting checks"
	@echo "  type-check      Run TypeScript type checking"
	@echo "  test            Run frontend tests in watch mode"
	@echo "  test-run        Run frontend tests once (for CI)"
	@echo "  build           Build frontend for production"
	@echo "  dev             Start frontend development server"
	@echo "  clean           Clean build artifacts"

# Ensure Node.js 20.19+ or 22.12+ is available
ensure-node:
	@echo "Checking Node.js version..."
	@bash -c ' \
	export NVM_DIR="$$HOME/.nvm"; \
	[ -s "$$NVM_DIR/nvm.sh" ] && . "$$NVM_DIR/nvm.sh"; \
	NODE_VERSION=$$(node --version 2>&1 | grep -oP "\d+\.\d+\.\d+" | head -1 || echo ""); \
	REQUIRED_MIN="20.19.0"; \
	NODE_TO_INSTALL="20.19.0"; \
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
		echo "Please install Node.js 20.19+ or 22.12+:"; \
		echo "  - Using nvm (recommended): nvm install $$NODE_TO_INSTALL && nvm use $$NODE_TO_INSTALL"; \
		echo "  - Download from: https://nodejs.org/"; \
		exit 1; \
	fi; \
	NODE_MAJOR=$$(echo $$NODE_VERSION | cut -d. -f1); \
	NODE_MINOR=$$(echo $$NODE_VERSION | cut -d. -f2); \
	VALID=0; \
	if [ "$$NODE_MAJOR" -gt 22 ]; then \
		VALID=1; \
	elif [ "$$NODE_MAJOR" -eq 22 ] && [ "$$NODE_MINOR" -ge 12 ]; then \
		VALID=1; \
	elif [ "$$NODE_MAJOR" -eq 20 ] && [ "$$NODE_MINOR" -ge 19 ]; then \
		VALID=1; \
	fi; \
	if [ "$$VALID" -eq 0 ]; then \
		echo "❌ Node.js $$NODE_VERSION detected (requires 20.19+ or 22.12+)"; \
		echo ""; \
		if command -v nvm >/dev/null 2>&1 || [ "$$(type nvm 2>/dev/null)" ]; then \
			INSTALLED_VALID=$$(nvm list 2>/dev/null | grep -oE "v(20\\.(19|[2-9][0-9])|2[3-9]\\.[0-9]+|[3-9][0-9]\\.[0-9]+)\\.[0-9]+" | head -1 | cut -c2-); \
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
			echo "Or install Node.js manually:"; \
			echo "  Download from: https://nodejs.org/"; \
		fi; \
		exit 1; \
	else \
		echo "✓ Node.js $$NODE_VERSION detected (meets requirement 20.19+/22.12+)"; \
	fi \
	'

# Ensure Node.js 20.19+ or 22.12+ is available (CI mode - no interactive prompts)
ensure-node-ci:
	@echo "Checking Node.js version (CI mode)..."
	@bash -c ' \
	export NVM_DIR="$$HOME/.nvm"; \
	[ -s "$$NVM_DIR/nvm.sh" ] && . "$$NVM_DIR/nvm.sh"; \
	NODE_VERSION=$$(node --version 2>&1 | grep -oP "\d+\.\d+\.\d+" | head -1 || echo ""); \
	NODE_TO_INSTALL="20.19.0"; \
	if [ -z "$$NODE_VERSION" ]; then \
		echo "❌ Node.js not found!"; \
		if command -v nvm >/dev/null 2>&1 || [ "$$(type nvm 2>/dev/null)" ]; then \
			echo "Installing Node.js $$NODE_TO_INSTALL via nvm..."; \
			nvm install $$NODE_TO_INSTALL && \
			nvm use $$NODE_TO_INSTALL && \
			echo "✓ Node.js $$NODE_TO_INSTALL installed and activated!" && \
			exit 0; \
		fi; \
		echo "❌ Cannot auto-install Node.js in CI without nvm"; \
		exit 1; \
	fi; \
	NODE_MAJOR=$$(echo $$NODE_VERSION | cut -d. -f1); \
	NODE_MINOR=$$(echo $$NODE_VERSION | cut -d. -f2); \
	VALID=0; \
	if [ "$$NODE_MAJOR" -gt 22 ]; then \
		VALID=1; \
	elif [ "$$NODE_MAJOR" -eq 22 ] && [ "$$NODE_MINOR" -ge 12 ]; then \
		VALID=1; \
	elif [ "$$NODE_MAJOR" -eq 20 ] && [ "$$NODE_MINOR" -ge 19 ]; then \
		VALID=1; \
	fi; \
	if [ "$$VALID" -eq 0 ]; then \
		echo "❌ Node.js $$NODE_VERSION detected (requires 20.19+ or 22.12+)"; \
		if command -v nvm >/dev/null 2>&1 || [ "$$(type nvm 2>/dev/null)" ]; then \
			INSTALLED_VALID=$$(nvm list 2>/dev/null | grep -oE "v(20\\.(19|[2-9][0-9])|2[3-9]\\.[0-9]+|[3-9][0-9]\\.[0-9]+)\\.[0-9]+" | head -1 | cut -c2-); \
			if [ -n "$$INSTALLED_VALID" ]; then \
				echo "✓ Activating existing Node.js version: $$INSTALLED_VALID"; \
				nvm use $$INSTALLED_VALID && \
				echo "✓ Node.js $$INSTALLED_VALID activated!" && \
				exit 0; \
			else \
				echo "Installing Node.js $$NODE_TO_INSTALL via nvm..."; \
				nvm install $$NODE_TO_INSTALL && \
				nvm use $$NODE_TO_INSTALL && \
				echo "✓ Node.js $$NODE_TO_INSTALL installed and activated!" && \
				exit 0; \
			fi; \
		fi; \
		echo "❌ Cannot auto-install Node.js in CI without nvm"; \
		exit 1; \
	else \
		echo "✓ Node.js $$NODE_VERSION detected (meets requirement 20.19+/22.12+)"; \
	fi \
	'

# Dependency management
install: ensure-node
	@echo "Installing frontend dependencies..."
	$(call run-with-nvm,npm install)
	@echo ""
	@echo "💡 Tip: Install Git hooks with: make -f ../project.mk install-hooks"

install-ci: ensure-node-ci
	@echo "Installing frontend dependencies for CI..."
	$(call run-with-nvm,npm ci)

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
	$(call run-with-nvm,npm run lint)

# Type checking
type-check:
	@echo "Running TypeScript type checking..."
	@$(MAKE) generate-openapi-client
	@$(MAKE) generate-asyncapi-types
	$(call run-with-nvm,npm run type-check)

# Testing
test:
	@echo "Running frontend tests in watch mode..."
	@$(MAKE) generate-openapi-client
	@$(MAKE) generate-asyncapi-types
	$(call run-with-nvm,npm run test:unit)

test-run:
	@echo "Running frontend tests..."
	@$(MAKE) generate-openapi-client
	@$(MAKE) generate-asyncapi-types
	$(call run-with-nvm,npm run test:unit)

# Build
build:
	@echo "Building frontend for production..."
	$(call run-with-nvm,npm run build)

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
	$(call run-with-nvm,npm run dev)

# Cleanup
clean:
	@echo "Cleaning frontend build artifacts..."
	rm -rf dist/ node_modules/.vite src/clients/*
	@echo "Frontend clean complete."
