# Frontend Generated Code and External Library Exclusions

**Version**: 1.2.0  
**Last Updated**: November 11, 2025  
**Status**: ✅ Current

This document outlines all the configurations that exclude frontend generated code and external libraries from linting, testing, and other development checks.

## Overview

The frontend has two categories of excluded files:

1. **External Libraries**: TradingView charting library and datafeeds (third-party dependencies)
2. **Generated Code**: Auto-generated API clients and WebSocket types from OpenAPI/AsyncAPI specs

## Excluded Directories

### External Libraries (Public Folder)

- `public/charting_library/` - TradingView charting library (minified external code)
- `public/datafeeds/` - TradingView datafeed implementations (third-party examples)
- `public/trading_terminal/` - TradingView Trading Terminal library
- `public/advanced_charting_library/` - TradingView Advanced Chart library

### Generated Code (Auto-Generated from Backend Specs)

**Per-Module Generated Clients** (Modular Architecture):

- `src/clients_generated/trader-client-broker_v1/` - OpenAPI-generated REST API client for broker module
- `src/clients_generated/trader-client-datafeed_v1/` - OpenAPI-generated REST API client for datafeed module
- `src/clients_generated/ws-types-broker_v1/` - AsyncAPI-generated WebSocket types for broker module
- `src/clients_generated/ws-types-datafeed_v1/` - AsyncAPI-generated WebSocket types for datafeed module

**Pattern**: `src/clients_generated/{trader-client|ws-types}-{module}_v{version}/`

## Configuration Files Updated

### 1. Root `.gitignore`

**Purpose**: Prevent generated files from being committed to Git

**Exclusions**:

```ignore
# External TradingView libraries
frontend/public/charting_library/
frontend/public/datafeeds/
frontend/public/trading_terminal/
frontend/public/advanced_charting_library/
```

### 2. Frontend `.gitignore`

**Purpose**: Local frontend-specific Git ignore rules

**Exclusions**:

```ignore
# Generated API clients (per-module pattern)
src/clients_generated/trader-client-*/

# Generated WebSocket types (per-module pattern)
src/clients_generated/ws-types-*/

# OpenAPI/AsyncAPI generation artifacts
openapi.json
asyncapi.json
openapi-3.0.json
openapitools.json
```

**Status**: ✅ All generated code directories excluded with wildcard patterns

### 3. ESLint Configuration (`frontend/eslint.config.ts`)

**Purpose**: Prevent ESLint from linting external and generated code

**Exclusions**:

```typescript
globalIgnores([
  '**/dist/**',
  '**/dist-ssr/**',
  '**/coverage/**',
  '**/public/**', // 👈 Covers all external libraries
  '**/node_modules/**',
  'src/clients_generated/**', // 👈 Covers all generated clients (trader-client-*, ws-types-*)
])
```

**Pattern Used**: Single wildcard `src/clients_generated/**` covers all module-specific generated directories

**Status**: ✅ Current - covers all generated code

### 4. Prettier Configuration (`frontend/.prettierignore`)

**Purpose**: Exclude files from Prettier formatting

**Current Exclusions**:

```ignore
# Generated files (per-module pattern)
src/clients_generated/trader-client-*/
src/clients_generated/ws-types-*/

# External libraries and dependencies
public/
```

**Status**: ✅ Up-to-date - covers all generated directories with wildcard patterns

### 5. TypeScript Configuration (`frontend/tsconfig.app.json`)

**Purpose**: Exclude files from TypeScript type checking

**Exclusions**:

```jsonc
"exclude": [
  "src/**/__tests__/*",
  "public/**/*"              // 👈 Covers external libraries
]
```

**Note**: Generated clients are already TypeScript, so they don't need to be excluded from type checking. They're imported normally.

**Status**: ✅ Adequate - external libraries excluded, generated clients type-safe

### 6. Vitest Configuration (`frontend/vitest.config.ts`)

**Purpose**: Exclude files from test coverage and test runs

**Exclusions**:

```typescript
test: {
  exclude: [
    ...configDefaults.exclude,
    'public/**',                      // External libraries
    'src/clients_generated/**',       // 👈 All generated clients
  ],
}
```

**Status**: ✅ Current - covers all generated code with single wildcard

### 7. Git Hooks (`.githooks/shared-lib.sh`)

**Purpose**: Exclude files from pre-commit checks

**Exclusions**:

```bash
# get_staged_files() and get_changed_files() exclude:
frontend/public/
```

**Status**: ✅ External libraries excluded

**Note**: Generated code inside `src/clients/` may be checked by hooks, but since it's in `.gitignore`, it won't be staged/committed.

### 8. Package.json Scripts (`frontend/package.json`)

**Purpose**: Ensure npm scripts respect exclusions

**Scripts**:

```json
{
  "format": "prettier --write src/", // Only formats src/, respects .prettierignore
  "lint": "eslint .", // Uses eslint.config.ts globalIgnores
  "type-check": "vue-tsc --build --force" // Uses tsconfig.app.json exclude
}
```

**Status**: ✅ All scripts respect configuration exclusions

## What Gets Excluded

### Checks Excluded From:

- ✅ ESLint linting
- ✅ Prettier formatting
- ✅ TypeScript type checking (external libraries only)
- ✅ Vitest testing
- ✅ Git pre-commit hooks
- ✅ Version control (Git)

## Why These Exclusions?

### External Libraries

1. **Third-Party Code**: Libraries we don't control (TradingView)
2. **Large File Sizes**: Minified and very large (10+ MB)
3. **No Need to Lint**: External code doesn't follow our style guide
4. **Performance**: Excluding speeds up tooling
5. **Not Versioned**: Downloaded/installed separately

### Generated Code

1. **Auto-Generated**: Created by OpenAPI/AsyncAPI generators
2. **Regenerated Often**: Changes with every backend spec update
3. **No Manual Edits**: Modified by re-running generation scripts
4. **Type-Safe**: Already TypeScript-compliant
5. **Not Source Code**: Derived from backend specifications

## Code Generation Workflow

### OpenAPI REST Client Generation

```bash
# Generate per-module REST clients
cd frontend && make generate-openapi-client
# or
npm run generate:openapi-client
```

**Source**: Backend module OpenAPI specs (`backend/modules/{module}/openapi.json`)  
**Output**: `src/clients_generated/trader-client-{module}_v{version}/`  
**Tool**: `@openapitools/openapi-generator-cli`

### AsyncAPI WebSocket Types Generation

```bash
# Generate per-module WebSocket types
cd frontend && make generate-asyncapi-types
# or
npm run generate:asyncapi-types
```

**Source**: Backend module AsyncAPI specs (`backend/modules/{module}/asyncapi.json`)  
**Output**: `src/clients_generated/ws-types-{module}_v{version}/`  
**Tool**: Custom script `scripts/generate-asyncapi-types.sh`

### Regeneration Triggers

- Backend API schema changes
- New endpoints added
- WebSocket topic updates
- Type definition modifications

## Verification

To verify exclusions are working:

```bash
# Test ESLint (should not check public/ or generated/)
make -f project.mk lint-frontend
cd frontend && make lint

# Test Prettier (should not format public/ or generated/)
cd frontend && make format

# Test TypeScript (should not check public/)
cd frontend && make type-check

# Test Vitest (should not test public/ or generated/)
cd frontend && make test

# Check Git status (generated files should not appear)
git status  # Should not show src/clients_generated/
```

## Adding New Generated Code Directories

If you add new code generation for additional modules (e.g., new trading module):

1. Generated clients will automatically follow the pattern: `src/clients_generated/{type}-{module}_v{version}/`
2. Existing wildcard patterns in `.gitignore`, ESLint, and Vitest will cover them automatically
3. Verify `.prettierignore` includes the wildcard patterns
4. Update this documentation with:
   - New module name
   - Generation command
   - Source specification location

## Recommended Naming Convention

**Generated Code**: Use pattern `{type}-{module}_v{version}` where:

- `type`: `trader-client` (REST) or `ws-types` (WebSocket)
- `module`: Backend module name (e.g., `broker`, `datafeed`)
- `version`: API version (e.g., `v1`, `v2`)

**Examples**:

- `trader-client-broker_v1/`
- `ws-types-datafeed_v1/`

**Rationale**: Matches modular backend architecture and wildcard patterns in configuration files.

## Action Items

**All action items completed** ✅

Previous issues have been resolved:

- ✅ `.prettierignore` uses wildcard patterns for all generated code
- ✅ All configuration files properly exclude generated directories
- ✅ Documentation updated to reflect modular architecture

### Optional Improvements

- [ ] Consider consolidating external library exclusions in root `.gitignore`
- [ ] Add comment in `tsconfig.app.json` explaining why generated code isn't excluded
- [ ] Document generation scripts in `frontend/README.md`

## Notes

- **Wildcard Patterns**: All configs use `src/clients_generated/**` for future-proofing
- **Modular Architecture**: Generated clients are organized per backend module
- **Type Safety**: Generated clients are type-safe and can be imported normally
- **No Manual Edits**: Never manually edit files in `clients_generated/` directories
- **Regeneration**: Always re-run generation scripts after backend spec changes
- **Version Control**: Generated code is `.gitignore`d to reduce repository size

## Related Documentation

- **Client Generation**: `../../docs/CLIENT-GENERATION.md`
- **WebSocket Clients**: `../../docs/WEBSOCKET-CLIENTS.md`
- **Frontend README**: `../README.md`
- **Makefile Guide**: `../../docs/MAKEFILE-GUIDE.md`
- **Modular Backend**: `../../backend/docs/MODULAR_BACKEND_ARCHITECTURE.md`

---

**Maintained by**: Development Team  
**Review Schedule**: Update when new generated code directories are added  
**Last Review**: November 11, 2025
