# TraderPRO Project Makefile

# Environment variables with fallback values
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

# Module discovery
BACKEND_MODULES = $(shell find backend/src/trading_api/modules -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -v __pycache__ || echo "")

.PHONY: help setup install install-hooks uninstall-hooks dev-backend dev-frontend dev-fullstack kill-dev test-all test-backend-modules test-smoke lint-all format-all build-all clean-all clean-generated health test-integration generate-ws-routers generate-openapi-client generate-asyncapi-types

# Default target
help:
	@echo "Project-wide targets:"
	@echo "  install           Install Git hooks + all dependencies (backend + frontend)"
	@echo "  setup             Same as install (alias for convenience)"
	@echo "  install-hooks     Install Git hooks for pre-commit checks only"
	@echo "  uninstall-hooks   Remove Git hooks"
	@echo "  dev-backend       Start backend development server"
	@echo "  dev-frontend      Start frontend development server"
	@echo "  dev-fullstack     Start backend, generate client, then start frontend"
	@echo "  kill-dev          Stop all running development servers (frontend then backend)"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-all              Run all tests (backend + frontend)"
	@echo "  test-backend-modules  Run all backend module tests"
	@echo "  test-smoke            Run smoke tests with Playwright"
	@echo "  test-integration      Run full integration test suite"
	@echo ""
	@echo "Other targets:"
	@echo "  lint-all          Run all linters"
	@echo "  format-all        Format all code"
	@echo "  build-all         Build all projects"
	@echo ""
	@echo "Cleanup targets:"
	@echo "  clean-generated   Clean only generated files (quick cleanup)"
	@echo "  clean-all         Clean all build artifacts (full cleanup)"
	@echo ""
	@echo "Code generation targets:"
	@echo "  generate-ws-routers       Generate WebSocket router classes (backend)"
	@echo "  generate-openapi-client   Generate TypeScript REST client (frontend)"
	@echo "  generate-asyncapi-types   Generate TypeScript WebSocket types (frontend)"
	@echo ""
	@echo "Other targets:"
	@echo "  health            Check project health"
	@echo ""
	@echo "Backend-specific targets:"
	@echo "  make -C backend help"
	@echo ""
	@echo "Frontend-specific targets:"
	@echo "  make -C frontend help"
	@echo ""
	@echo "Discovered backend modules: $(BACKEND_MODULES)"

# Git hooks management
install-hooks:
	@echo "Installing Git hooks..."
	git config core.hooksPath .githooks
	chmod +x .githooks/*
	@echo "Git hooks installed successfully!"
	@echo "Hooks location: $$(git config --get core.hooksPath)"

uninstall-hooks:
	@echo "Removing Git hooks..."
	git config --unset core.hooksPath || true
	@echo "Git hooks removed."

# Install all dependencies
install:
	@echo "Installing all project dependencies..."
	@echo ""
	@echo "[1/2] Installing backend dependencies..."
	@echo "========================================"
	make -C backend install
	@echo ""
	@echo "[2/2] Installing frontend dependencies..."
	@echo "========================================="
	make -C frontend install
	@echo ""
	@echo "[3/3] Installing Git hooks..."
	@echo "========================================"
	@$(MAKE) install-hooks
	@echo ""
	@echo "✓ All dependencies installed successfully!"
	@echo ""
	@echo "Next steps:"
	@echo "  make dev-backend    # Start backend server (port 8000)"
	@echo "  make dev-frontend   # Start frontend server (port 5173)"
	@echo "  make dev-fullstack  # Start both servers"

# Project setup (alias for install)
setup: install
	@echo ""
	@echo "Project setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  make dev-backend    # Start backend server (port 8000)"
	@echo "  make dev-frontend   # Start frontend server (port 5173)"

# Development servers
dev-backend:
	@echo "Starting backend development server..."
	@echo "🧹 Cleaning backend generated files..."
	rm -f backend/openapi.json backend/asyncapi.json
	make -C backend dev

dev-frontend:
	@echo "Starting frontend development server..."
	make -C frontend dev

# Full-stack development
dev-fullstack:
	@echo "Starting full-stack development environment..."
	./scripts/dev-fullstack.sh

# Kill all development servers
kill-dev:
	@echo "Stopping all development servers..."
	@echo ""
	@echo "[1/2] Stopping frontend..."
	@echo "=========================================="
	@make -C frontend kill-dev || true
	@echo ""
	@echo "[2/2] Stopping backend..."
	@echo "=========================================="
	@make -C backend kill-dev || true
	@echo ""
	@echo "✅ All development servers stopped"

# Testing
test-backend-modules:
	@echo "Running backend module tests..."
	cd backend && $(MAKE) test-modules

test-all: test-backend-modules
	@echo "Running all tests..."
	@echo ""
	@echo "[1/2] Backend tests"
	@echo "========================================"
	@if ! make -C backend test; then \
		echo "" && \
		echo "❌ Backend tests failed! Stopping test execution." && \
		exit 1; \
	fi
	@echo ""
	@echo "[2/2] Frontend tests (with client generation)"
	@echo "========================================"
	@echo "Note: Client generation happens automatically before tests"
	@if ! make -C frontend test; then \
		echo "" && \
		echo "❌ Frontend tests failed!" && \
		exit 1; \
	fi
	@echo ""
	@echo "✓ All tests completed successfully!"

# Smoke testing
test-smoke:
	@echo "Running smoke tests..."
	cd smoke-tests && ./run-tests.sh

# Integration testing
test-integration:
	@echo "Running integration tests..."
	./scripts/test-integration.sh

# Linting
lint-all:
	@echo "Running all linters..."
	@echo "Backend linting:"
	make -C backend lint-check
	@echo ""
	@echo "Frontend linting:"
	make -C frontend lint
	make -C frontend type-check

# Formatting
format-all:
	@echo "Formatting all code..."
	@echo "Backend formatting:"
	make -C backend format
	@echo ""
	@echo "Frontend formatting:"
	cd frontend && npm run format

# Build
build-all:
	@echo "Building all projects..."
	@echo "Backend build:"
	make -C backend build
	@echo ""
	@echo "Frontend build:"
	make -C frontend build

# Cleanup
clean-all:
	@echo "Cleaning all build artifacts..."
	@echo "🧹 Cleaning backend..."
	make -C backend clean
	@echo "🧹 Cleaning frontend..."
	make -C frontend clean
	@echo "🧹 Cleaning project-level generated files..."
	rm -f backend/openapi.json backend/asyncapi.json
	rm -rf frontend/src/clients/*
	@echo "🧹 Cleaning smoke test artifacts..."
	rm -rf smoke-tests/test-results smoke-tests/playwright-report
	@echo "Clean complete."

# Clean only generated files (lighter cleanup)
clean-generated:
	@echo "Cleaning generated files..."
	@echo "🧹 Removing backend spec files..."
	rm -f backend/openapi.json backend/asyncapi.json
	@echo "🧹 Removing frontend generated clients..."
	rm -rf frontend/src/clients/*
	@echo "🧹 Removing frontend build cache..."
	rm -rf frontend/node_modules/.vite
	@echo "🧹 Removing test artifacts..."
	rm -rf smoke-tests/test-results smoke-tests/playwright-report
	@echo "Generated files cleanup complete."

# Health check
health:
	@echo "Checking project health..."
	@echo "Backend health:"
	make -C backend health
	@echo ""
	@echo "Frontend health:"
	@curl -f http://localhost:$(FRONTEND_PORT) 2>/dev/null >/dev/null && echo "Frontend running" || echo "Frontend not running"

# Code generation targets
generate-ws-routers:
	@echo "Generating WebSocket routers..."
	make -C backend generate-ws-routers

generate-openapi-client:
	@echo "Generating OpenAPI client..."
	make -C frontend generate-openapi-client

generate-asyncapi-types:
	@echo "Generating AsyncAPI types..."
	make -C frontend generate-asyncapi-types