# Trading API

A FastAPI-based trading API server built with Test Driven Development.

## Quick Start

### Prerequisites
- Python 3.10+
- Poetry (recommended) or pip

### Installation

Using Poetry:
```bash
poetry config virtualenvs.in-project true
poetry install
poetry shell
```

Using pip:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Running the API

```bash
poetry run uvicorn trading_api.main:app --reload
```

Or with pip:
```bash
uvicorn trading_api.main:app --reload
```

### Running Tests

```bash
poetry run pytest
```

### API Documentation

Once the server is running, visit:
- Interactive docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI spec: http://127.0.0.1:8000/openapi.json

## Development

This project follows Test Driven Development (TDD) practices:
1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green

### Code Quality

We use:
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking
- pre-commit for git hooks

## Project Structure

```
trading-api/
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── trading_api/
│       ├── __init__.py
│       ├── main.py
│       └── api/
│           └── health.py
├── tests/
│   └── test_health.py
├── pyproject.toml
└── README.md
```
