# Trading API Makefile

.PHONY: help install-hooks uninstall-hooks setup-backend setup-frontend setup dev-backend dev-frontend test lint format clean

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
setup: install-hooks setup-backend setup-frontend
	@echo "Project setup complete!"

setup-backend:
	@echo "Setting up backend..."
	cd backend && poetry install

setup-frontend:
	@echo "Setting up frontend..."
	cd frontend && npm install

# Development servers
dev-backend:
	cd backend && poetry run uvicorn trading_api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Testing
test:
	@echo "Running backend tests..."
	cd backend && poetry run pytest
	@echo "Running frontend tests..."
	cd frontend && npm run test:unit run

# Linting
lint:
	@echo "Linting backend..."
	cd backend && poetry run flake8 src/ tests/
	@echo "Linting frontend..."
	cd frontend && npm run lint

# Formatting
format:
	@echo "Formatting backend..."
	cd backend && poetry run black src/ tests/
	cd backend && poetry run isort src/ tests/
	@echo "Formatting frontend..."
	cd frontend && npm run format

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	cd backend && rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage
	cd frontend && rm -rf dist/ node_modules/.cache/
	@echo "Clean complete."