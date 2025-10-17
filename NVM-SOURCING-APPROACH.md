# NVM Sourcing Strategy

## Problem

The `make dev` and other npm-related commands fail because they don't source nvm, causing Node.js 18.16.0 to be used instead of 20.19.0.

## Root Cause

- Only `install` and `install-ci` targets source nvm
- All other targets (`dev`, `build`, `lint`, `type-check`, `test`, etc.) run `npm` directly
- Shell scripts don't source nvm before running npm commands

## Proposed Solution: Create a Helper Script

### Approach 1: Wrapper Script (Recommended)

Create a helper script that all Makefile targets and shell scripts can use.

**File: `frontend/scripts/with-nvm.sh`**

```bash
#!/bin/bash
# Helper script to run commands with the correct Node.js version via nvm

# Source nvm if available
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"

    # Use version from .nvmrc if it exists
    if [ -f ".nvmrc" ]; then
        nvm use >/dev/null 2>&1 || true
    fi
fi

# Execute the command
exec "$@"
```

**Benefits:**

- ✅ Single source of truth for nvm sourcing
- ✅ DRY - no repetition across Makefile targets
- ✅ Easy to maintain
- ✅ Works in both Makefile and shell scripts
- ✅ Handles .nvmrc automatically

**Usage in Makefile:**

```makefile
dev:
	@echo "Starting frontend development server..."
	@./scripts/with-nvm.sh npm run dev

build:
	@echo "Building frontend for production..."
	@./scripts/with-nvm.sh npm run build
```

**Usage in Shell Scripts:**

```bash
#!/bin/bash
# At the top of generation scripts (generate-openapi-client.sh, generate-asyncapi-types.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/with-nvm.sh"
# Rest of script...
```

---

### Approach 2: Makefile Function (Alternative)

Define a Make function that wraps npm commands.

**In frontend/Makefile:**

```makefile
# Helper to run npm with correct Node.js version
define run-with-nvm
	@bash -c 'export NVM_DIR="$$HOME/.nvm"; [ -s "$$NVM_DIR/nvm.sh" ] && . "$$NVM_DIR/nvm.sh"; nvm use 2>/dev/null || true; $(1)'
endef

dev:
	@echo "Starting frontend development server..."
	$(call run-with-nvm,npm run dev)

build:
	@echo "Building frontend for production..."
	$(call run-with-nvm,npm run build)
```

**Benefits:**

- ✅ Keeps everything in Makefile
- ✅ No external script file needed

**Drawbacks:**

- ❌ Doesn't help shell scripts
- ❌ More verbose Makefile
- ❌ Harder to debug

---

### Approach 3: Update All Targets Individually (Not Recommended)

Wrap each npm command with the nvm sourcing logic.

**Drawbacks:**

- ❌ Lots of repetition
- ❌ Error-prone
- ❌ Hard to maintain

---

## Recommended Implementation

**Use Approach 1 (Wrapper Script)** because:

1. Works for both Makefile targets AND shell scripts
2. Single point of maintenance
3. Easy to understand and debug
4. Follows DRY principle

## Files That Need Updates

### Frontend Makefile

All targets that run npm commands:

- `client-generate` → use wrapper
- `lint` → use wrapper
- `type-check` → use wrapper
- `test` → use wrapper
- `test-run` → use wrapper
- `build` → use wrapper
- `dev` → use wrapper

### Shell Scripts

Scripts that run npm or node commands:

- `frontend/scripts/generate-openapi-client.sh` → source wrapper at top
- `frontend/scripts/generate-asyncapi-types.sh` → source wrapper at top
- `frontend/scripts/generate-ws-types.mjs` → run via `with-nvm.sh node ...`
- `frontend/scripts/generate-ws-types.mjs` → run via `with-nvm.sh node ...`

### Project-Level Scripts

- `scripts/dev-fullstack.sh` → use wrapper for frontend commands
- `scripts/test-integration.sh` → use wrapper if it runs frontend tests

## Implementation Steps

1. ✅ Create `frontend/scripts/with-nvm.sh`
2. ✅ Make it executable: `chmod +x frontend/scripts/with-nvm.sh`
3. ✅ Update all npm commands in `frontend/Makefile` to use wrapper
4. ✅ Update shell scripts to source or use wrapper
5. ✅ Test all commands:
   - `make dev`
   - `make build`
   - `make lint`
   - `make type-check`
   - `make test-run`
   - `make client-generate`
6. ✅ Update documentation

## Testing Checklist

```bash
cd frontend

# Test each command
make ensure-node    # Should activate Node 20.19.0
make dev            # Should use Node 20.19.0
make build          # Should use Node 20.19.0
make lint           # Should use Node 20.19.0
make type-check     # Should use Node 20.19.0
make test-run       # Should use Node 20.19.0
make client-generate # Should use Node 20.19.0

# Verify Node version in each
./scripts/with-nvm.sh node --version  # Should show v20.19.0
```

## Alternative: Global Solution (Optional Enhancement)

For users who want nvm always available, suggest adding to their shell profile:

```bash
# In ~/.bashrc or ~/.zshrc
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"

# Auto-use .nvmrc if available
autoload -U add-zsh-hook
load-nvmrc() {
  if [[ -f .nvmrc && -r .nvmrc ]]; then
    nvm use >/dev/null 2>&1
  fi
}
add-zsh-hook chpwd load-nvmrc
load-nvmrc
```

But this is user-specific and shouldn't be required for the project to work.
