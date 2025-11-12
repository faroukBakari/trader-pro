# TraderPRO Project Makefile

# Environment variables with fallback values
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

# Module discovery
BACKEND_MODULES = $(shell find backend/src/trading_api/modules -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -v __pycache__ || echo "")

.PHONY: help install install-hooks dev-backend dev-frontend dev-fullstack kill-dev test-all test-smoke lint-all format-all build-all clean-all test-integration generate backend-generate frontend-generate generate-openapi-client generate-asyncapi-types health

# Default target
help:
	@echo "Project-wide targets:"
	@echo "  install           Install Git hooks + all dependencies (backend + frontend)"
	@echo "  install-hooks     Install Git hooks for pre-commit checks only"
	@echo "  dev-backend       Start backend development server"
	@echo "  dev-frontend      Start frontend development server"
	@echo "  dev-fullstack     Start backend, then start frontend"
	@echo "  kill-dev          Stop all running development servers (frontend then backend)"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-all              Run all tests (backend + frontend)"
	@echo "  test-smoke            Run smoke tests with Playwright"
	@echo "  test-integration      Run full integration test suite"
	@echo ""
	@echo "Other targets:"
	@echo "  lint-all          Run all linters"
	@echo "  format-all        Format all code"
	@echo "  build-all         Build all projects"
	@echo ""
	@echo "Cleanup targets:"
	@echo "  clean-all         Clean all build artifacts (full cleanup)"
	@echo ""
	@echo "Code generation targets:"
	@echo "  generate                  Generate all (backend specs + frontend clients)"
	@echo "  backend-generate          Generate backend specs (OpenAPI + AsyncAPI + Python clients)"
	@echo "  frontend-generate         Generate frontend TypeScript clients from backend specs"
	@echo "                            (requires backend specs - run 'backend-generate' first)"
	@echo "  generate-openapi-client   Generate frontend OpenAPI REST client (called by watcher)"
	@echo "  generate-asyncapi-types   Generate frontend AsyncAPI WebSocket types (called by watcher)"
	@echo ""
	@echo "Health targets:"
	@echo "  health                    Check project health (backend + frontend)"
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

# Development servers
dev-backend:
	@echo "Starting backend development server..."
	make -C backend clean-generated
	make -C backend dev

dev-frontend:
	@echo "Starting frontend development server..."
	make -C frontend clean-generated
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

test-all:
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
	make -C backend type-check
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
	@echo "🧹 Removing frontend build cache..."
	rm -rf frontend/node_modules/.vite
	@echo "🧹 Removing test artifacts..."
	rm -rf smoke-tests/test-results smoke-tests/playwright-report
	@echo "Clean complete."

# Code generation targets
generate:
	@echo "Generating all (backend specs + frontend clients)..."
	@echo ""
	@echo "[1/2] Generating backend specs..."
	@echo "=========================================="
	@$(MAKE) backend-generate
	@echo ""
	@echo "[2/2] Generating frontend clients..."
	@echo "=========================================="
	@$(MAKE) frontend-generate
	@echo ""
	@echo "✅ All code generation complete!"

backend-generate:
	@echo "Generating backend specs (OpenAPI + AsyncAPI + Python clients)..."
	make -C backend generate

frontend-generate:
	@echo "Generating frontend TypeScript clients from backend specs..."
	@echo "Note: Requires backend specs to exist (run 'backend-generate' first)"
	make -C frontend generate

generate-openapi-client:
	@echo "Generating frontend OpenAPI REST client from backend specs..."
	make -C frontend generate

generate-asyncapi-types:
	@echo "Generating frontend AsyncAPI WebSocket types from backend specs..."
	make -C frontend generate

# Health check
health:
	@echo "Checking project health..."
	@echo ""
	@echo "[1/2] Checking backend health..."
	@echo "=========================================="
	@if make -C backend health-ci 2>/dev/null; then \
		echo "✅ Backend is healthy"; \
	else \
		echo "⚠️  Backend health check not available (server may not be running)"; \
	fi
	@echo ""
	@echo "[2/2] Checking frontend health..."
	@echo "=========================================="
	@if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "✅ Frontend server is running on port 5173"; \
	else \
		echo "⚠️  Frontend server is not running"; \
	fi
	@echo ""
	@echo "💡 Tip: Start servers with 'make dev-fullstack'"
