# Git Hooks Setup

This directory contains centralized Git hooks for the trading-api project.

## Quick Setup

For new contributors or after cloning the repository:

```bash
# Using Makefile (recommended)
make install-hooks

# Or using npm script (if working in frontend)
cd frontend && npm run install:hooks

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

**Important**: The hook automatically stashes any unstaged changes before running checks and **always** restores them afterward (even if checks fail), ensuring your work is never lost.

#### For Backend (Python) Files:
- **Black**: Code formatting
- **isort**: Import sorting
- **Flake8**: Code linting
- **MyPy**: Type checking
- **Tests**: Run pytest (local only, skipped in CI)

#### For Frontend (TypeScript/Vue) Files:
- **ESLint**: Code linting and fixing
- **Prettier**: Code formatting
- **TypeScript**: Type checking
- **Tests**: Run unit tests (local only, skipped in CI)

#### For All Files:
- Check for trailing whitespace
- Check for merge conflict markers
- Validate JSON/YAML syntax

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

The hooks work seamlessly with CI:
- Set `git config core.hooksPath .githooks` in CI setup
- Tests and slower checks can be run separately in CI
- Use `SKIP_HOOKS=true` or `--no-verify` for automated commits

## Customization

Edit `.githooks/pre-commit` to modify which checks run or add new ones.
The `shared-lib.sh` contains utility functions for adding new checks.