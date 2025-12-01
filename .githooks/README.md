# Git Hooks Setup

**Last Updated:** November 30, 2025

This directory contains centralized Git hooks for the trading-api project.

## Quick Setup

For new contributors or after cloning the repository:

```bash
# Using Makefile (recommended)
make install-hooks

# Or manually
git config core.hooksPath .githooks
chmod +x .githooks/*
```

## Verify Installation

```bash
git config --get core.hooksPath
# Should output: .githooks
```

## What the Hooks Do

### Pre-commit Hook

Automatically runs when you commit code. It will:

**Important**: The hook automatically stashes any unstaged/untracked changes before running checks and **always** restores them afterward (even if checks fail), ensuring your work is never lost.

#### For Backend (Python) Files:

- **Formatting** (`make format`): Black + isort
- **Type checking** (`make type-check`): MyPy + Flake8
- **Tests** (`make test`): pytest (skipped in CI)
- **Spec generation** (`make generate`): OpenAPI/AsyncAPI specs + Python client validation
- **Frontend client regeneration**: Triggers frontend TypeScript client generation from updated specs

#### For Frontend (TypeScript/Vue) Files:

- **Client generation** (`make generate`): TypeScript clients from backend specs
- **Linting** (`make lint`): ESLint with auto-fix
- **Type checking** (`make type-check`): TypeScript compiler
- **Tests** (`make test`): Vitest unit tests (skipped in CI)

#### For All Staged Files:

- Check for trailing whitespace (excludes `frontend/public/`)
- Check for merge conflict markers

## Bypassing Hooks

Sometimes you need to commit quickly or bypass checks:

```bash
# Skip all hooks for one commit
git commit --no-verify

# Skip hooks with environment variable
SKIP_HOOKS=true git commit

# For emergency commits
NO_VERIFY=true git commit
```

## Troubleshooting

### Missing Dependencies

If you get errors about missing tools:

**Backend issues:**

```bash
cd backend
poetry install  # Install Python dependencies
```

**Frontend issues:**

```bash
cd frontend
npm install  # Install Node.js dependencies
```

### Hooks Not Running

```bash
# Check if hooks are installed
git config --get core.hooksPath

# Reinstall hooks
make install-hooks

# Check hook permissions
ls -la .githooks/
# Should show executable permissions (x)
```

### Slow Pre-commit Checks

Tests are skipped in CI environments. For local development:

- Use `git commit --no-verify` for quick commits during development
- Run `make test` separately to run full test suites
- The hooks focus on fast formatting and linting checks

## Manual Commands

Run the same checks manually:

```bash
# All checks
make lint
make format
make test

# Backend only
cd backend
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
poetry run pytest

# Frontend only
cd frontend
npm run lint
npm run format
npm run type-check
npm run test:unit run
```

## CI Integration

The hooks detect CI environments (`CI`, `GITHUB_ACTIONS`, `GITLAB_CI`) and skip tests for faster pipeline runs:

- Format and type-check steps always run
- Tests (`make test`) are skipped in CI
- Use `SKIP_HOOKS=true` or `--no-verify` for automated commits

## Customization

Edit `.githooks/pre-commit` to modify which checks run or add new ones.
The `shared-lib.sh` contains utility functions (`run_check`, `log_*`, `is_ci`, etc.).

## Files in This Directory

| File            | Purpose                             |
| --------------- | ----------------------------------- |
| `pre-commit`    | Main hook script dispatching checks |
| `shared-lib.sh` | Utility functions for hooks         |
| `README.md`     | This documentation                  |
