---
agent: "Plan"
name: "tdd-plan"
description: "Generate a step-by-step TDD action plan for implementing a feature."
---

## TDD Feature Planner

Generate a detailed, actionable TDD implementation plan.

## Inputs

1.  **Feature Description**: (string) The user's high-level description of the feature to be built (e.g., "Add a 'placeOrder' endpoint to the 'Broker' module").
2.  **User Materials**: (string, optional) Any additional context, designs, or brainstorming notes provided by the user.

### Step 1: Analyze Context

1.  **Read project architecture**: `docs/DOCUMENTATION-GUIDE.md`
2.  **Read and internalize** the **Feature Description** and any **User Materials** from the inputs to understand requirements and constraints.
3.  **Review testing strategy**: `docs/TESTING.md` for test organization and patterns.
4.  **Select methodology** based on feature type:
    * REST API → `API-METHODOLOGY.md` (6-phase)
    * WebSocket → `WEBSOCKET-METHODOLOGY.md` (6-phase)
    * Other → Red-Green-Refactor
5.  **Find similar implementations**: Search `@workspace` for existing patterns.
6.  **Identify locations**: Module paths, test files, and dependencies to modify.

### Step 2: Generate Plan

Adapt the chosen methodology to this specific feature.

**Guiding Principle**: Deconstruct the feature into a logical sequence. For APIs, this is typically **outside-in**: 1. API route/spec, 2. Controller/Handler, 3. Service logic, 4. Data model/adapter. For other types, start with the most critical test.

For each phase:

* **File paths** - Exact locations following project patterns.
* **Actions** - Specific, executable tasks (e.g., "Add `placeOrder()` to `BrokerApiAdapter`").
* **Verification** - Command to run (e.g., `make test`, `npm run type-check`).
* **Expected result** - Pass/fail status for TDD checkpoints.

Mark TDD phases clearly:

* 🔴 **Red Phase** - Tests must fail (no implementation yet).
* 🟢 **Green Phase** - Tests must pass (implementation complete).

### Step 3: Output Format

````markdown
### Plan for [Feature Name]

**Methodology**: [API-METHODOLOGY.md / WEBSOCKET-METHODOLOGY.md / Custom]
**Module**: `backend/src/trading_api/modules/[module]/`
**Tests**: `backend/.../tests/`, `frontend/src/services/__tests__/`

#### Phase 1: [Phase Name]

-   `[ ]` (`path/to/file.py`): Specific action
-   `[ ]` (`path/to/file.ts`): Specific action
-   **Verify**: `make test` → Expected: ✅ pass / 🔴 fail

#### Phase 2: [Phase Name]

...

#### Validation

-   `[ ]` All tests pass: `make test`
-   `[ ]` Type checks pass: `npm run type-check`
-   `[ ]` Smoke tests pass: `make smoke-test`