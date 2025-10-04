# Trading API Makefile

.PHONY: help install-hooks uninstall-hooks setup-backend setup-frontend setup dev-backend dev-frontend test lint format clean ci-setup

# Default target
help:
	@echo "Available targets:"
	@echo "  install-hooks     Install Git hooks for pre-commit checks"
	@echo "  uninstall-hooks   Remove Git hooks"
	@echo "  setup             Full project setup (hooks + dependencies)"
	@echo "  setup-backend     Setup backend dependencies"
	@echo "  setup-frontend    Setup frontend dependencies"
	@echo "  dev-backend       Start backend development server"
	@echo "  dev-frontend      Start frontend development server"
	@echo "  test              Run all tests"
	@echo "  lint              Run all linters"
	@echo "  format            Format all code"
	@echo "  clean             Clean build artifacts"
	@echo "  ci-setup          Setup for CI environment"

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

# CI-specific setup
ci-setup: install-hooks
	@echo "Setting up CI environment..."
	@if [ "$$CI" = "true" ]; then \
		echo "CI environment detected"; \
	else \
		echo "Local development environment"; \
	fi

# Project setup
setup: install-hooks setup-backend setup-frontend
	@echo "Project setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  make dev-backend    # Start backend server (port 8000)"
	@echo "  make dev-frontend   # Start frontend server (port 5173)"

setup-backend:
	@echo "Setting up backend..."
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found. Please install Poetry: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	cd backend && poetry install

setup-frontend:
	@echo "Setting up frontend..."
	@if ! command -v npm >/dev/null 2>&1; then \
		echo "npm not found. Please install Node.js: https://nodejs.org/"; \
		exit 1; \
	fi
	cd frontend && npm install

# Development servers
dev-backend:
	@echo "Starting backend server on http://localhost:8000"
	cd backend && poetry run uvicorn trading_api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "Starting frontend server on http://localhost:5173"
	cd frontend && npm run dev

# Testing
test: test-backend test-frontend

test-backend:
	@echo "Running backend tests..."
	cd backend && poetry run pytest -v

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm run test:unit run

# Linting
lint: lint-backend lint-frontend

lint-backend:
	@echo "Linting backend..."
	cd backend && poetry run flake8 src/ tests/
	cd backend && poetry run mypy src/

lint-frontend:
	@echo "Linting frontend..."
	cd frontend && npm run lint
	cd frontend && npx prettier --check src/

# Formatting
format: format-backend format-frontend

format-backend:
	@echo "Formatting backend..."
	cd backend && poetry run black src/ tests/
	cd backend && poetry run isort src/ tests/

format-frontend:
	@echo "Formatting frontend..."
	cd frontend && npm run format

# Build
build: build-backend build-frontend

build-backend:
	@echo "Building backend..."
	cd backend && poetry build

build-frontend:
	@echo "Building frontend..."
	cd frontend && npm run build

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	cd backend && rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage
	cd frontend && rm -rf dist/ node_modules/.cache/
	@echo "Clean complete."

# Health check
health:
	@echo "Checking project health..."
	@echo "Backend health:"
	@curl -f http://localhost:8000/health 2>/dev/null || echo "Backend not running"
	@echo ""
	@echo "Frontend health:"
	@curl -f http://localhost:5173 2>/dev/null >/dev/null && echo "Frontend running" || echo "Frontend not running"