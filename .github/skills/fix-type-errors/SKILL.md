---
name: fix-type-errors
description: Systematic type error resolution for Python (mypy/pyright) and TypeScript (vue-tsc). Use when fixing type errors, resolving type check failures, or optimizing type imports.
---

# Type Error Resolution

Systematic workflow to resolve static type checker errors while preserving runtime behavior.

## Scope

Applies when:
- Fixing mypy, pyright, or vue-tsc errors
- Resolving type check failures in CI
- Optimizing imports for type-only dependencies
- Eliminating `# type: ignore` suppressions

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Behavior Preservation** | Fixes must NOT change runtime logic. Only annotations, imports, and casts. |
| **Zero Suppressions** | `# type: ignore` / `// @ts-ignore` are forbidden. Resolve properly or escalate. |
| **Import Optimization** | Use `TYPE_CHECKING` (Python) or `import type` (TypeScript) for type-only imports. |
| **Minimal Surface** | One error → one minimal fix. Avoid broad refactors. |

## Commands

### Backend (Python)

| Priority | Command | Use Case |
|----------|---------|----------|
| 1. Makefile | `make -C backend type-check` | Full check (black, isort, flake8, mypy, pyright) |
| 2. Direct | `cd backend && poetry run pyright src/ tests/` | Pyright only |
| 3. Single-file | `cd backend && poetry run pyright path/to/file.py` | Fast iteration |

### Frontend (TypeScript/Vue)

| Priority | Command | Use Case |
|----------|---------|----------|
| 1. Makefile | `make -C frontend lint type-check` | Full check (ESLint + vue-tsc) |
| 2. Direct | `cd frontend && npm run type-check` | vue-tsc only |
| 3. Single-file | `cd frontend && npx vue-tsc --noEmit src/path/to/file.ts` | Fast iteration |

## Workflow

### Phase 1: Error Discovery

1. Run type checker and capture output
2. Parse into structured list: `[file:line] error_code: message`
3. Categorize:

| Category | Examples | Action |
|----------|----------|--------|
| **A: Direct Fix** | Missing annotation, wrong type | Fix immediately |
| **B: Import Optimization** | Circular import, runtime-only import | Move to `TYPE_CHECKING` |
| **C: Structural** | Generic variance, protocol mismatch | Analyze deeply |
| **D: External** | Untyped library, upstream bug | Escalate |

### Phase 2: Resolution

For each error, apply decision tree:

1. **Generated code?** (`*_generated/`) → Skip
2. **Fixable with annotation?** → Add type hint
3. **Type narrowing issue?** → Add isinstance/assert/guard
4. **Import-only-for-types?** → Move to TYPE_CHECKING block
5. **Library typing issue?** → Add cast() with documentation
6. **None apply?** → Follow Suppression Protocol

### Phase 3: Validation

After fixes, run validation:

| Change Type | Commands |
|-------------|----------|
| Pure annotations | `make format type-check` (no tests) |
| Added cast/assert | `make format type-check test` |
| Changed runtime imports | `make format type-check test` |

## Common Patterns

### Python: TYPE_CHECKING Import

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from expensive_module import ExpensiveType

def func(param: "ExpensiveType") -> None:
    ...
```

### Python: Cast for Library Gaps

```python
from typing import cast
result = cast(ExpectedType, untyped_call())  # Document why safe
```

### TypeScript: Type-Only Import

```typescript
import type { SomeType } from './module'  // Erased at runtime
import { SomeValue } from './module'       // Kept at runtime
```

## Suppression Protocol

**Only after exhausting all fix approaches:**

1. **Document root cause** — Why proper fix is impossible
2. **Propose specific suppression** — `# pyright: ignore[reportAssignmentType]`
3. **Validate** — Run type checker to confirm resolution
4. **Report to user** — Format:

```
⚠️ SUPPRESSION REQUIRED (External Issue)

File: path/to/file.py:42
Error: [reportAssignmentType] Type "X" is not assignable to "Y"

Root Cause: [Library/framework limitation]

Proposed: __tablename__ = cast(Any, "users")

Validation: ✅ Tested — resolves error
```

**DO NOT apply suppressions without user acknowledgment.**

## Anti-Patterns

- ❌ Using `# type: ignore` without exhausting fixes
- ❌ Modifying runtime behavior to satisfy type checker
- ❌ Editing generated code (`*_generated/` directories)
- ❌ Broad refactors when targeted fix suffices
