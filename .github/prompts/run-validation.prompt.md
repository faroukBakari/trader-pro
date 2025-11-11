---
agent: "agent"
name: "run-validation"
description: "Validate unstaged changes in the workspace based on what has been modified."
---
## Validate Current Changes

You are a Quality Assurance expert. Validate the unstaged changes in the workspace based on what has been modified.

### Step 1: Analyze Changes

First, check what has changed:

```bash
git status
```

Categorize the changes:

- **Backend changes**: Files in `backend/` directory
- **Frontend changes**: Files in `frontend/` directory
- **Documentation changes**: `.md` files (skip validation)
- **Configuration changes**: Root-level config files
- **Mixed changes**: Both backend and frontend

### Step 2: Validate Backend Changes

If changes include backend files (`backend/**`):

#### 2.1. Format Backend Code

```bash
make -C backend format
```

Expected: Auto-fixes formatting issues

**Resources**:

- [MAKEFILE-GUIDE.md](../MAKEFILE-GUIDE.md) - Backend make targets
- Backend uses: black, isort

#### 2.2. Lint & Type-Check Backend

```bash
make -C backend type-check
```

Expected: No linting or type errors (flake8, mypy, pyright)

**Resources**:

- [backend/docs/BACKEND_TESTING.md](../backend/docs/BACKEND_TESTING.md) - Testing guide
- [docs/TESTING.md](../docs/TESTING.md) - Testing strategy

On failure: Review errors and fix code

#### 2.3. Run Backend Tests

```bash
make -C backend test
```

Expected: All tests pass

Test levels:

- **Boundaries**: `make test-boundaries` - Module isolation validation
- **Unit**: `make test-modules` - All module tests
- **Integration**: `make test-integration` - Multi-process tests

**Resources**:

- [backend/docs/BACKEND_TESTING.md](../backend/docs/BACKEND_TESTING.md) - Comprehensive testing guide
- [API-METHODOLOGY.md](../API-METHODOLOGY.md) - TDD methodology
- [WEBSOCKET-METHODOLOGY.md](../WEBSOCKET-METHODOLOGY.md) - WebSocket TDD

On failure: Run specific test with `poetry run pytest path/to/test.py -v -s`

### Step 3: Validate Frontend Changes

If changes include frontend files (`frontend/**`):

#### 3.1. Format Frontend Code

```bash
make -C frontend format
```

Expected: Auto-fixes formatting issues

**Resources**:

- [MAKEFILE-GUIDE.md](../MAKEFILE-GUIDE.md) - Frontend make targets
- Frontend uses: Prettier

#### 3.2. Lint & Type-Check Frontend

```bash
make -C frontend lint
make -C frontend type-check
```

Expected: No linting or type errors (ESLint, TypeScript)

**Resources**:

- [frontend/README.md](../frontend/README.md) - Frontend overview
- [docs/CLIENT-GENERATION.md](../docs/CLIENT-GENERATION.md) - Generated clients

On failure: Fix issues or use `make -C frontend lint-fix` for auto-fixable errors

#### 3.3. Run Frontend Tests

```bash
make -C frontend test-ci
```

Expected: All tests pass

**Resources**:

- [docs/TESTING.md](../docs/TESTING.md) - Testing strategy
- [frontend/src/services/**tests**/README.md](../frontend/src/services/__tests__/README.md) - Service testing

On failure: Run `make test` for watch mode to debug

### Step 4: Validate Configuration Changes

If changes include root-level configuration:

- **Makefile**: Verify syntax with `make -f project.mk help`
- **GitHub Actions**: Check workflow syntax
- **Environment config**: Review [ENVIRONMENT-CONFIG.md](../ENVIRONMENT-CONFIG.md)

### Output Format

For each validation step:

- ✅ Success: "✅ [Component] [Step]: PASSED"
- ❌ Failure: "❌ [Component] [Step]: FAILED" + error summary + suggested fix

**Example Output:**

```
Changes Detected:
- Backend: src/trading_api/modules/broker/api.py
- Frontend: src/services/apiService.ts

Validation Steps:

✅ Backend Format: PASSED (auto-fixed 2 files)
✅ Backend Lint: PASSED
✅ Backend Tests: PASSED (23 tests in 1.2s)
✅ Frontend Format: PASSED (auto-fixed 1 file)
❌ Frontend Lint: FAILED
   - src/services/apiService.ts:45 - unused variable 'result'
   Fix: Remove unused variable or prefix with underscore
✅ Frontend Type-Check: PASSED
```

**Final Summary:**

```
╔════════════════════════════════╗
║  VALIDATION SUMMARY            ║
╠════════════════════════════════╣
║ Backend Format:  [✅/❌/SKIP]  ║
║ Backend Lint:    [✅/❌/SKIP]  ║
║ Backend Tests:   [✅/❌/SKIP]  ║
║ Frontend Format: [✅/❌/SKIP]  ║
║ Frontend Lint:   [✅/❌/SKIP]  ║
║ Frontend Tests:  [✅/❌/SKIP]  ║
╠════════════════════════════════╣
║ Status: [READY / NEEDS FIXES]  ║
╚════════════════════════════════╝
```

### Optional Validation Suggestions

After completing the required validation steps above, you may suggest the following **optional** validations to the user:

#### 1. Full Project Validation

For comprehensive validation before committing:

```bash
# Run all formatters
make -f project.mk format-all

# Run all linters
make -f project.mk lint-all

# Run all tests
make -f project.mk test-all
```

**Resources**: [MAKEFILE-GUIDE.md](../MAKEFILE-GUIDE.md), [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md)

#### 2. Integration Testing

Only if backend was modified:

```bash
# Start backend first
make -C backend dev

# In another terminal
make -f project.mk test-integration
```

#### 3. End-to-End Testing

Only if both backend and frontend were modified:

```bash
# Start full stack
make -f project.mk dev-fullstack

# In another terminal
make -C smoke-tests test
```

**Resources**: [smoke-tests/README.md](../smoke-tests/README.md)

**Note**: Present these as suggestions only. Do not execute them unless specifically requested by the user.

### Key Resources

- **Documentation Index**: [docs/DOCUMENTATION-GUIDE.md](../docs/DOCUMENTATION-GUIDE.md)
- **Makefile Commands**: [MAKEFILE-GUIDE.md](../MAKEFILE-GUIDE.md)
- **Testing Strategy**: [docs/TESTING.md](../docs/TESTING.md)
- **Backend Testing**: [backend/docs/BACKEND_TESTING.md](../backend/docs/BACKEND_TESTING.md)
- **Development Workflows**: [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md)
