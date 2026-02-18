---
name: fix-backend-type-errors
description: Systematic Python type error resolution (mypy/pyright). Load when fixing backend type check failures
user-invocable: false
---

# Backend Type Error Resolution

Systematic workflow to resolve Python static type checker errors while preserving runtime behavior.

## Scope

Applies when:
- Fixing mypy or pyright errors in `backend/`
- Resolving backend type check failures in CI
- Optimizing imports for type-only dependencies (`TYPE_CHECKING`)
- Eliminating `# type: ignore` suppressions

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Behavior Preservation** | Fixes must NOT change runtime logic. Only annotations, imports, and casts. |
| **Zero Suppressions** | `# type: ignore` is forbidden. Resolve properly or escalate. |
| **Import Optimization** | Use `TYPE_CHECKING` for type-only imports to avoid circular dependencies. |
| **Minimal Surface** | One error → one minimal fix. Avoid broad refactors. |

## Commands

| Priority | Command | Use Case |
|----------|---------|----------|
| 1. Makefile | `make -C backend type-check` | Full check (black, isort, flake8, mypy, pyright) |
| 2. Direct | `cd backend && poetry run pyright src/ tests/` | Pyright only |
| 3. Single-file | `cd backend && poetry run pyright path/to/file.py` | Fast iteration |

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

After fixes, run validation (all from project root, fail-fast `&&` chains):

| Change Type | Commands |
|-------------|----------|
| Pure annotations | `make -C backend format && make -C backend type-check` |
| Added cast/assert | `make -C backend clean-cache && make -C backend format && make -C backend type-check && make -C backend test` |
| Changed runtime imports | `make -C backend clean-cache && make -C backend format && make -C backend type-check && make -C backend test` |

**Why `clean-cache`**: mypy/pyright cache symbols by name. After adding casts or changing imports, stale cache can mask errors that CI (cold cache) would catch.

## Common Patterns

### TYPE_CHECKING Import

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from expensive_module import ExpensiveType

def func(param: "ExpensiveType") -> None:
    ...
```

### Cast for Library Gaps

```python
from typing import cast
result = cast(ExpectedType, untyped_call())  # Document why safe
```

## Suppression Protocol

**Only after exhausting all fix approaches:**

1. **Document root cause** — Why proper fix is impossible
2. **Propose specific suppression** — `# pyright: ignore[reportAssignmentType]`
3. **Validate** — Run type checker to confirm resolution
4. **Report to user** — Format:

```
SUPPRESSION REQUIRED (External Issue)

File: path/to/file.py:42
Error: [reportAssignmentType] Type "X" is not assignable to "Y"

Root Cause: [Library/framework limitation]

Proposed: __tablename__ = cast(Any, "users")

Validation: Tested — resolves error
```

**DO NOT apply suppressions without user acknowledgment.**

## Anti-Patterns

- Do not use `# type: ignore` without exhausting fixes
- Do not modify runtime behavior to satisfy type checker
- Do not edit generated code (`*_generated/` directories)
- Do not apply broad refactors when targeted fix suffices
