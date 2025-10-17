# Frontend Public Folder Exclusions

This document outlines all the configurations that exclude the frontend public folders (`public/charting_library/` and `public/datafeeds/`) from linting, testing, and other development checks.

## Files Updated

### 1. Root `.gitignore`
- Added exclusions for `frontend/public/charting_library/` and `frontend/public/datafeeds/`
- These folders contain external dependencies (TradingView library) that should not be version controlled

### 2. Frontend `.gitignore`
- Added exclusions for `public/charting_library/` and `public/datafeeds/`
- Local frontend-specific ignore rules

### 3. ESLint Configuration (`frontend/eslint.config.ts`)
- Added `**/public/charting_library/**` and `**/public/datafeeds/**` to `globalIgnores`
- Prevents ESLint from trying to lint external JavaScript libraries

### 4. Prettier Configuration (`frontend/.prettierignore`)
- Created new file to exclude public folders from Prettier formatting
- Also excludes other build artifacts and generated files

### 5. TypeScript Configuration (`frontend/tsconfig.app.json`)
- Added public folders to `exclude` array
- Prevents TypeScript compiler from checking external library types

### 6. Vitest Configuration (`frontend/vitest.config.ts`)
- Added public folders to test exclusions
- Prevents test runner from trying to test external libraries

### 7. Git Hooks (`.githooks/shared-lib.sh`)
- Updated `get_staged_files()` and `get_changed_files()` functions
- Excludes public folders from pre-commit checks

### 8. Package.json Scripts (`frontend/package.json`)
- Updated format script to use `.prettierignore`
- Ensures npm scripts respect exclusions

## What Gets Excluded

### Files/Folders:
- `frontend/public/charting_library/` - TradingView charting library
- `frontend/public/datafeeds/` - TradingView datafeed implementations
- Any subdirectories and files within these folders

### Checks Excluded From:
- ✅ ESLint linting
- ✅ Prettier formatting
- ✅ TypeScript type checking
- ✅ Vitest testing
- ✅ Git pre-commit hooks
- ✅ Version control (Git)

## Why These Exclusions?

1. **External Dependencies**: These folders contain third-party libraries that we don't control
2. **Large File Sizes**: TradingView library files are minified and very large
3. **No Need to Lint**: External code doesn't need to follow our project's code style
4. **Performance**: Excluding these speeds up linting, testing, and builds
5. **Version Control**: These files shouldn't be tracked as they're external dependencies

## Verification

To verify exclusions are working:

```bash
# Test ESLint (should not check public folders)
cd frontend && npx eslint .

# Test Prettier (should not format public folders)
cd frontend && npx prettier --check src/

# Test TypeScript (should not check public folders)
cd frontend && npm run type-check

# Test Vitest (should not try to test public folders)
cd frontend && npm run test:unit
```

## Adding New Public Dependencies

If you add new external libraries to the `public/` folder:

1. Add them to all the configuration files listed above
2. Follow the same pattern: `public/[library-name]/`
3. Update this documentation

## Notes

- The exclusions are comprehensive and cover all major development tools
- External libraries are served statically and loaded globally via script tags
- This setup ensures clean separation between our code and external dependencies