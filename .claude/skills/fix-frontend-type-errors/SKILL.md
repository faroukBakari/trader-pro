---
name: fix-frontend-type-errors
description: Systematic TypeScript/Vue type error resolution (vue-tsc/ESLint). Load when fixing frontend type check failures
user-invocable: false
---

# Frontend Type Error Resolution

Systematic workflow to resolve TypeScript and Vue static type checker errors while preserving runtime behavior.

## Scope

Applies when:
- Fixing vue-tsc or ESLint type errors in `frontend/`
- Resolving frontend type check failures in CI
- Optimizing imports with `import type`
- Eliminating `// @ts-ignore` suppressions

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Behavior Preservation** | Fixes must NOT change runtime logic. Only annotations, imports, and type assertions. |
| **Zero Suppressions** | `// @ts-ignore` is forbidden. Resolve properly or escalate. |
| **Import Optimization** | Use `import type` for type-only imports — erased at runtime. |
| **Minimal Surface** | One error → one minimal fix. Avoid broad refactors. |

## Commands

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
| **B: Import Optimization** | Runtime import used only for types | Switch to `import type` |
| **C: Structural** | Generic variance, interface mismatch | Analyze deeply |
| **D: External** | Untyped library, upstream bug | Escalate |

### Phase 2: Resolution

For each error, apply decision tree:

1. **Generated code?** (`*_generated/`) → Skip
2. **Fixable with annotation?** → Add type hint
3. **Type narrowing issue?** → Add type guard / discriminant check
4. **Import-only-for-types?** → Switch to `import type`
5. **Library typing issue?** → Add `as` assertion with documentation
6. **None apply?** → Follow Suppression Protocol

### Phase 3: Validation

After fixes, run validation (all from project root, fail-fast `&&` chains):

| Change Type | Commands |
|-------------|----------|
| Pure annotations | `make -C frontend lint && make -C frontend type-check` |
| Added type assertion | `make -C frontend lint && make -C frontend type-check && make -C frontend test` |
| Changed runtime imports | `make -C frontend lint && make -C frontend type-check && make -C frontend test` |

## Common Patterns

### Type-Only Import

```typescript
import type { SomeType } from './module'  // Erased at runtime
import { SomeValue } from './module'       // Kept at runtime
```

### Type Guard

```typescript
function isOrder(value: unknown): value is Order {
  return typeof value === 'object' && value !== null && 'orderId' in value
}
```

### Discriminated Union Narrowing

```typescript
type WsMessage = { type: 'order'; data: Order } | { type: 'error'; message: string }

function handle(msg: WsMessage) {
  switch (msg.type) {
    case 'order': // msg.data is Order here
    case 'error': // msg.message is string here
  }
}
```

## Suppression Protocol

**Only after exhausting all fix approaches:**

1. **Document root cause** — Why proper fix is impossible
2. **Propose specific suppression** — `// @ts-expect-error — [reason]`
3. **Validate** — Run type checker to confirm resolution
4. **Report to user** — Format:

```
SUPPRESSION REQUIRED (External Issue)

File: src/path/to/file.ts:42
Error: TS2322 — Type 'X' is not assignable to type 'Y'

Root Cause: [Library/framework limitation]

Proposed: // @ts-expect-error — [library] returns untyped response
const result = untypedCall() as ExpectedType

Validation: Tested — resolves error
```

**DO NOT apply suppressions without user acknowledgment.**

## Anti-Patterns

- Do not use `// @ts-ignore` — use `// @ts-expect-error` with explanation if suppression is unavoidable
- Do not modify runtime behavior to satisfy type checker
- Do not edit generated code (`*_generated/` directories)
- Do not apply broad refactors when targeted fix suffices
