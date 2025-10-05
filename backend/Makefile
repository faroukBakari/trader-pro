# Trading API Backend Makefile

.PHONY: help install test test-cov lint lint-check format build clean dev health clients export-openapi docs-html

# Default target
help:
	@echo "Backend targets:"
	@echo "  install           Install backend dependencies"
	@echo "  test              Run backend tests"
	@echo "  test-cov          Run backend tests with coverage"
	@echo "  lint              Run backend linting (check only)"
	@echo "  lint-check        Run backend linting with type checking"
	@echo "  format            Format backend code"
	@echo "  build             Build backend package"
	@echo "  dev               Start backend development server"
	@echo "  clean             Clean build artifacts"
	@echo "  health            Check backend health"
	@echo "  export-openapi    Export OpenAPI specification"
	@echo "  docs-html         Generate static HTML documentation"

# Backend dependency management
install:
	@echo "Installing backend dependencies..."
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found. Please install Poetry: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	poetry install

# CI-optimized install (non-interactive)
install-ci:
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

format:
	@echo "Formatting backend code..."
	poetry run black src/ tests/
	poetry run isort src/ tests/

# Development server
dev:
	@echo "Starting backend development server on http://localhost:8000"
	poetry run uvicorn trading_api.main:app --reload --host 0.0.0.0 --port 8000

# CI development server (background)
dev-ci:
	@echo "Starting backend server for CI..."
	poetry run uvicorn trading_api.main:app --host 0.0.0.0 --port 8000 &
	sleep 10

# Build
build:
	@echo "Building backend package..."
	poetry build

# Health check
health:
	@echo "Checking backend health..."
	@curl -f http://localhost:8000/api/v1/health 2>/dev/null || echo "Backend not running"

# CI health check
health-ci:
	@echo "Testing API endpoints for CI..."
	curl -f http://localhost:8000/api/v1/health || exit 1
	curl -f http://localhost:8000/api/v1/version || exit 1

# Cleanup
clean:
	@echo "Cleaning backend build artifacts..."
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage clients/ openapi*.json
	@echo "Backend clean complete."

# Export OpenAPI specification
export-openapi:
	@echo "Exporting OpenAPI specification..."
	curl -s http://localhost:8000/api/v1/openapi.json -o openapi.json

# Generate static HTML documentation
docs-html:
	@echo "Generating static HTML documentation..."
	npx redoc-cli bundle openapi.json -o docs/api.html
