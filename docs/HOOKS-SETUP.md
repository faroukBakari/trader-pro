# Git Hooks Setup

**Last Updated:** November 11, 2025

## Quick Start

```bash
# Option 1: Install all (recommended for new setup)
make install

# Option 2: Install hooks only
make install-hooks

# Option 3: Manual
git config core.hooksPath .githooks
chmod +x .githooks/*
```

## What Gets Checked

**Important**: The pre-commit hook automatically stashes any unstaged changes **and untracked files** before running checks and **always** restores them afterward, regardless of whether the checks pass or fail. This ensures that:

- Only staged changes are checked
- Your working directory changes are preserved
- Untracked files don't interfere with linting/type checking
- Failed checks don't lose your work
- You get warnings about untracked source files that aren't being committed

### Backend (Python files)

- ✅ Black formatting
- ✅ isort import sorting
- ✅ Flake8 linting
- ✅ MyPy type checking
- ✅ Spec and client generation (`make generate` - unified command)
- ✅ Pytest tests (local only)

**Note on spec validation**:

- **OpenAPI spec validation** ensures all REST API models and routes can be exported without errors
- **AsyncAPI spec validation** ensures all WebSocket models are valid and checks that subscription request models have **required** parameters only (no optional/default values)
- Optional parameters in subscription requests cause topic mismatch issues between request and response
- These validations run on **every commit** to prevent committing invalid schemas that would fail in CI

### Frontend (TypeScript/Vue files)

- ✅ ESLint linting & auto-fixing
- ✅ Prettier formatting
- ✅ TypeScript type checking
- ✅ Vitest unit tests (local only)

### All Files

- ✅ Trailing whitespace
- ✅ Merge conflict markers
- ✅ JSON/YAML validation

## Hook Structure

```
.githooks/
├── pre-commit      # Main dispatcher
├── shared-lib.sh   # Utility functions
└── README.md       # Documentation
```

## Usage

### Skip Hooks Temporarily

```bash
# Skip once
git commit --no-verify

# Skip with env variable
SKIP_HOOKS=true git commit
```

### Run Checks Manually

```bash
make lint && make format && make test
```

```

## Benefits

- ✅ **Cross-platform** - Works on Windows, macOS, Linux
- ✅ **Stack-agnostic** - No npm/Python pre-commit dependencies
- ✅ **Fast** - Only checks changed files
- ✅ **CI-friendly** - Auto-detects CI environment
- ✅ **Version-controlled** - Hook logic is committed
- ✅ **Easy onboarding** - Single command installation

## For New Team Members

1. Clone repo
2. Run `make install`
3. Start coding - hooks run automatically!
```
