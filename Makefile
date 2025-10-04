.PHONY: help install test test-all test-integration lint format dev clients clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	poetry install

test: ## Run tests with coverage
	poetry run pytest --cov=trading_api --cov-report=term-missing --cov-report=html

test-all: ## Run all tests including client generation tests
	poetry run pytest --cov=trading_api --cov-report=term-missing --cov-report=html -m "not integration"
	$(MAKE) clients
	poetry run pytest tests/test_client_generation.py::TestClientGeneration::test_generated_vue_client_structure -v
	poetry run pytest tests/test_client_generation.py::TestClientGeneration::test_generated_vue_client_typescript_validity -v

test-integration: ## Run integration tests (requires external tools)
	$(MAKE) clients
	poetry run pytest -m integration -v

lint: ## Run all linters
	poetry run black --check src/ tests/
	poetry run isort --check-only src/ tests/
	poetry run flake8 src/ tests/
	poetry run mypy src/

format: ## Format code with black and isort
	poetry run black src/ tests/
	poetry run isort src/ tests/

dev: ## Start development server
	poetry run uvicorn trading_api.main:app --host 0.0.0.0 --port 8000 --reload

clients: ## Generate API clients (Vue.js, Python)
	./scripts/generate-clients.sh

export-openapi: ## Export OpenAPI specification
	curl -s http://localhost:8000/api/v1/openapi.json -o openapi.json

docs-html: ## Generate static HTML documentation
	npx redoc-cli bundle openapi.json -o docs/api.html

clean: ## Clean generated files
	rm -rf clients/
	rm -f openapi.json
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
