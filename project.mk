# Trading API Project Makefile

.PHONY: help setup install-hooks uninstall-hooks dev-backend dev-frontend dev-fullstack test-all test-smoke lint-all format-all build-all clean-all health test-integration

# Default target
help:
	@echo "Project-wide targets:"
	@echo "  setup             Full project setup (hooks + dependencies)"
	@echo "  install-hooks     Install Git hooks for pre-commit checks"
	@echo "  uninstall-hooks   Remove Git hooks"
	@echo "  dev-backend       Start backend development server"
	@echo "  dev-frontend      Start frontend development server"
	@echo "  dev-fullstack     Start backend, generate client, then start frontend"
	@echo "  test-all          Run all tests"
	@echo "  test-smoke        Run smoke tests with Playwright"
	@echo "  test-integration  Run full integration test suite"
	@echo "  lint-all          Run all linters"
	@echo "  format-all        Format all code"
	@echo "  build-all         Build all projects"
	@echo "  clean-all         Clean all build artifacts"
	@echo "  health            Check project health"
	@echo ""
	@echo "Backend-specific targets:"
	@echo "  make -C backend help"
	@echo ""
	@echo "Frontend-specific targets:"
	@echo "  make -C frontend help"

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

# Project setup
setup: install-hooks
	@echo "Setting up backend..."
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found. Please install Poetry: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	make -C backend install
	@echo ""
	@echo "Setting up frontend..."
	@if ! command -v npm >/dev/null 2>&1; then \
		echo "npm not found. Please install Node.js: https://nodejs.org/"; \
		exit 1; \
	fi
	make -C frontend install
	@echo ""
	@echo "Project setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  make dev-backend    # Start backend server (port 8000)"
	@echo "  make dev-frontend   # Start frontend server (port 5173)"

# Development servers
dev-backend:
	@echo "Starting backend development server..."
	make -C backend dev

dev-frontend:
	@echo "Starting frontend development server..."
	make -C frontend dev

# Full-stack development
dev-fullstack:
	@echo "Starting full-stack development environment..."
	./scripts/dev-fullstack.sh

# Testing
test-all:
	@echo "Running all tests..."
	@echo "Backend tests:"
	make -C backend test
	@echo ""
	@echo "Frontend tests:"
	make -C frontend test-run

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
	make -C backend clean
	make -C frontend clean
	@echo "Clean complete."

# Health check
health:
	@echo "Checking project health..."
	@echo "Backend health:"
	make -C backend health
	@echo ""
	@echo "Frontend health:"
	@curl -f http://localhost:5173 2>/dev/null >/dev/null && echo "Frontend running" || echo "Frontend not running"