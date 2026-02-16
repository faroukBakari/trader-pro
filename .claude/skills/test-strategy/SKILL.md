---
name: test-strategy
description: Shared test methodology for backend and frontend. Load when planning test suites or evaluating coverage value
user-invocable: false
---

# Test Strategy Patterns

Reusable methodology for planning, implementing, and validating test suites across backend (pytest) and frontend (Vitest) stacks.

## Scope

Apply when:
- Planning a test suite (deciding what to test and in what order)
- Decomposing an API/component surface into test categories
- Evaluating which tests deliver the highest risk-reduction
- Running post-action reflexion after test execution
- Reporting coverage findings with anti-sycophancy

## Test Surface Decomposition

Break any testable surface into four categories:

| Category | What to Test | Examples |
|----------|-------------|----------|
| **Happy path** | Expected inputs → expected outputs | Valid request returns 200, component renders correct text |
| **Boundary conditions** | Empty inputs, max values, type edges | Empty list, null props, max-length string, zero quantity |
| **Error scenarios** | Invalid inputs, missing auth, service failures | 401 without token, 422 with bad payload, rejected promise |
| **State transitions** | Lifecycle, subscriptions, reactive changes | Order placed → filled → cancelled, WebSocket connect → message → disconnect |

## Coverage Value Prioritization

Not all tests are equal. Prioritize by risk-reduction:

```
Highest Value                              Lowest Value
────────────────────────────────────────────────────────
Untested        Untested       Untested       Already-tested
business logic  error paths    edge cases     happy paths
```

When reporting gaps, state both the gap AND its risk level:
- **High risk**: Untested business logic or error paths that could cause data loss/corruption
- **Medium risk**: Untested boundary conditions that could cause unexpected behavior
- **Low risk**: Missing edge case coverage for unlikely scenarios

## Test Plan Checkpoint

Before writing any tests, produce a summary:

```
Target: {module/component/service}
Setup: {fixture pattern — e.g., AsyncClient, mount(), vi.stubGlobal}
Planned tests:
  - Happy path: N tests
  - Boundary: N tests
  - Error: N tests
  - State transitions: N tests
Total: N tests
```

This checkpoint forces reasoning about coverage strategy BEFORE implementation.

## Post-Action Reflexion

After running tests, before reporting results:

1. **Plan adherence** — Compare completed tests against the plan checkpoint. Are all planned categories covered?
2. **Weakest test** — Identify the test with lowest confidence in its value. Note it explicitly.
3. **Coverage extension** — State what additional tests would improve coverage if time allowed.
4. **Findings** — If tests revealed production bugs or architectural issues, report them as findings (don't fix unless asked).

## Anti-Sycophancy Protocol

When analyzing coverage or evaluating test quality:

- **Report actual gaps** — do not inflate reported coverage or downplay missing scenarios
- **State what is NOT tested** — absence of tests is a finding, not something to skip over
- **Challenge weak tests** — if existing tests only assert status codes without checking response shapes, say so explicitly
- **Verify before confirming** — "this module has good coverage" may be false. Check before agreeing.

## Completion Tracking

When creating N planned tests, track progress before declaring done:

| Test | Status |
|------|--------|
| {test name 1} | ✅ / ❌ |
| {test name N} | ✅ / ❌ |

If any show ❌, continue working — do not declare completion.
