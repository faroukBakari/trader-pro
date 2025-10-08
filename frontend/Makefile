# TraderPRO Frontend Makefile

.PHONY: help install install-ci lint type-check test test-run build dev clean client-generate

# Default target
help:
	@echo "Frontend targets:"
	@echo "  install         Install frontend dependencies"
	@echo "  install-ci      Install frontend dependencies for CI"
	@echo "  client-generate Generate API client from live server or use mock"
	@echo "  lint            Run frontend linting and formatting checks"
	@echo "  type-check      Run TypeScript type checking"
	@echo "  test            Run frontend tests in watch mode"
	@echo "  test-run        Run frontend tests once (for CI)"
	@echo "  build           Build frontend for production"
	@echo "  dev             Start frontend development server"
	@echo "  clean           Clean build artifacts"

# Dependency management
install:
	@echo "Installing frontend dependencies..."
	npm install

install-ci:
	@echo "Installing frontend dependencies for CI..."
	npm ci

# Client generation
client-generate:
	@echo "Generating API client..."
	./scripts/generate-client.sh

# Linting and formatting
lint:
	@echo "Running frontend linting and formatting checks..."
	npm run lint

# Type checking
type-check:
	@echo "Running TypeScript type checking..."
	npm run type-check

# Testing
test:
	@echo "Running frontend tests in watch mode..."
	npm run test:unit

test-run:
	@echo "Running frontend tests..."
	npm run test:unit run

# Build
build:
	@echo "Building frontend for production..."
	npm run build

# Development server
dev:
	@echo "Starting frontend development server..."
	@echo "🧹 Cleaning generated client..."
	rm -rf src/clients/trader-client-generated
	npm run dev

# Cleanup
clean:
	@echo "Cleaning frontend build artifacts..."
	rm -rf dist/ node_modules/.vite src/clients/trader-client-generated
	@echo "Frontend clean complete."
