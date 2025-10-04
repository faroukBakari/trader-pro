# Trading API Project Makefile

.PHONY: help setup install-hooks uninstall-hooks dev-backend dev-frontend test-all lint-all format-all build-all clean-all health

# Default target
help:
	@echo "Project-wide targets:"
	@echo "  setup             Full project setup (hooks + dependencies)"
	@echo "  install-hooks     Install Git hooks for pre-commit checks"
	@echo "  uninstall-hooks   Remove Git hooks"
	@echo "  dev-backend       Start backend development server"
	@echo "  dev-frontend      Start frontend development server"
	@echo "  test-all          Run all tests"
	@echo "  lint-all          Run all linters"
	@echo "  format-all        Format all code"
	@echo "  build-all         Build all projects"
	@echo "  clean-all         Clean all build artifacts"
	@echo "  health            Check project health"
	@echo ""
	@echo "Backend-specific targets (in backend/):"
	@echo "  make -C backend help"

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
	cd frontend && npm install
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
	cd frontend && npm run dev

# Testing
test-all:
	@echo "Running all tests..."
	@echo "Backend tests:"
	make -C backend test
	@echo ""
	@echo "Frontend tests:"
	cd frontend && npm run test:unit run

# Linting
lint-all:
	@echo "Running all linters..."
	@echo "Backend linting:"
	make -C backend lint-check
	@echo ""
	@echo "Frontend linting:"
	cd frontend && npm run lint
	cd frontend && npx prettier --check src/

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
	cd frontend && npm run build

# Cleanup
clean-all:
	@echo "Cleaning all build artifacts..."
	make -C backend clean
	cd frontend && rm -rf dist/ node_modules/.cache/
	@echo "Clean complete."

# Health check
health:
	@echo "Checking project health..."
	@echo "Backend health:"
	make -C backend health
	@echo ""
	@echo "Frontend health:"
	@curl -f http://localhost:5173 2>/dev/null >/dev/null && echo "Frontend running" || echo "Frontend not running"