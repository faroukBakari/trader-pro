# Frontend Generated Code and External Library Exclusions

**Version**: 1.1.0  
**Last Updated**: October 25, 2025  
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

- `src/clients_generated/trader-client-generated/` - OpenAPI-generated REST API client
- `src/clients_generated/ws-types-generated/` - AsyncAPI-generated WebSocket types
- `src/clients/ws-generated/` - WebSocket client scaffolding (if applicable)

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
# Generated API client
src/clients_generated/trader-client-generated/

# Generated WebSocket types
src/clients_generated/ws-types-generated/

# Generated WebSocket client
src/clients/ws-generated/

# OpenAPI/AsyncAPI generation artifacts
openapi.json
asyncapi.json
openapi-3.0.json
openapitools.json
```

**Status**: ✅ All generated code directories excluded

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
  'src/clients/*-generated/**', // 👈 Covers trader-client-generated, ws-types-generated, ws-generated
])
```

**Pattern Used**: Wildcard `*-generated/**` covers all generated client directories

**Status**: ✅ Current - covers all generated code

### 4. Prettier Configuration (`frontend/.prettierignore`)

**Purpose**: Exclude files from Prettier formatting

**Current Exclusions**:

```ignore
# Generated files
src/clients_generated/trader-client-generated/

# External libraries and dependencies
public/
```

**Status**: ⚠️ Missing `ws-types-generated/` and `ws-generated/` - **NEEDS UPDATE**

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
    'public/**',                   // External libraries
    'src/clients/*-generated/**',  // 👈 All generated clients
  ],
}
```

**Status**: ✅ Current - covers all generated code with wildcard

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
- ⚠️ Prettier formatting (missing ws-types-generated in .prettierignore)
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
# Generate trader-client-generated/
cd frontend && make generate-openapi-client
# or
npm run generate:openapi-client
```

**Source**: `backend/openapi.json` (exported from FastAPI)  
**Output**: `src/clients_generated/trader-client-generated/`  
**Tool**: `@openapitools/openapi-generator-cli`

### AsyncAPI WebSocket Types Generation

```bash
# Generate ws-types-generated/
cd frontend && make generate-asyncapi-types
# or
npm run generate:asyncapi-types
```

**Source**: `backend/asyncapi.json` (exported from backend WebSocket routes)  
**Output**: `src/clients_generated/ws-types-generated/`  
**Tool**: Custom script `scripts/generate-ws-types.mjs`

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
git status  # Should not show src/clients/*-generated/
```

## Adding New Generated Code Directories

If you add new code generation (e.g., GraphQL, gRPC):

1. Add to `frontend/.gitignore` with exact path
2. Update `.prettierignore` with exact path
3. Verify ESLint wildcard `src/clients/*-generated/**` still covers it
4. Verify Vitest wildcard `src/clients/*-generated/**` still covers it
5. Update this documentation with:
   - Directory name and purpose
   - Generation command
   - Source specification
   - Tool/script used

## Recommended Naming Convention

**Generated Code**: Use `-generated` suffix (e.g., `graphql-client-generated/`)

**Rationale**: Matches existing wildcard patterns in ESLint and Vitest configs, reducing configuration changes.

## Action Items

### High Priority

- [ ] **Update `.prettierignore`** to include:
  ```ignore
  src/clients_generated/ws-types-generated/
  src/clients/ws-generated/
  ```
  Or use wildcard pattern:
  ```ignore
  src/clients/*-generated/
  ```

### Optional Improvements

- [ ] Consider consolidating external library exclusions in root `.gitignore`
- [ ] Add comment in `tsconfig.app.json` explaining why generated code isn't excluded
- [ ] Document generation scripts in `frontend/README.md`

## Notes

- **Wildcard Patterns**: ESLint and Vitest use `*-generated/**` for future-proofing
- **Type Safety**: Generated clients are type-safe and can be imported normally
- **No Manual Edits**: Never manually edit files in `-generated/` directories
- **Regeneration**: Always re-run generation scripts after backend spec changes
- **Version Control**: Generated code is `.gitignore`d to reduce repository size

## Related Documentation

- **Client Generation**: `/docs/CLIENT-GENERATION.md`
- **WebSocket Clients**: `/docs/WEBSOCKET-CLIENTS.md`
- **Frontend README**: `/frontend/README.md`
- **Makefile Guide**: `/MAKEFILE-GUIDE.md`

---

**Maintained by**: Development Team  
**Review Schedule**: Update when new generated code directories are added  
**Last Review**: October 25, 2025
