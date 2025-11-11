---
agent: "Plan"
name: "tdd-plan"
description: "Generate a detailed, step-by-step TDD action plan for a new feature."
---
  
## TDD Feature Planner

You are a TDD planning expert. Your goal is to generate a detailed, step-by-step TDD action plan.

1.  **Analyze Context:**

    - **CRITICAL:** Read `docs/DOCUMENTATION-GUIDE.md` to understand architecture
    - Determine feature type:
      - **REST API Service** → Use `API-METHODOLOGY.md` as template
      - **WebSocket Feature** → Use `WEBSOCKET-METHODOLOGY.md` as template
      - **Other** → Use Red-Green-Refactor pattern
    - Search for similar implementations: `@workspace [related feature]`
    - Identify: module location, test files, dependencies

2.  **Generate Plan:**

    - If REST/WebSocket: **Adapt the 6-phase methodology** to this specific feature
    - For each phase, provide:
      - **File locations** (using project patterns)
      - **Specific actions** (e.g., "Add `placeOrder` method to `ApiAdapter`")
      - **Verification command** (e.g., `make test`, `npm run type-check`)
      - **Expected outcome** (tests pass/fail at this phase)
    - Mark TDD Red phase (tests MUST fail)
    - Mark TDD Green phase (tests MUST pass)

3.  **Output Format:**

### Plan for [Feature Name]

**Methodology**: [API-METHODOLOGY.md Phase 1-6 / WEBSOCKET-METHODOLOGY.md / Custom]
**Module**: `backend/src/trading_api/modules/[module]/`
**Tests**: `backend/src/trading_api/modules/[module]/tests/`, `frontend/src/services/__tests__/`

#### Phase 1: [Phase Name] (from methodology)

- `[ ]` (file: `...`): Action 1
- `[ ]` (file: `...`): Action 2
- **Verify**: `make test` → [Expected: pass/fail]

[Continue for all phases...]

#### Validation Checkpoint

- `[ ]` Run `/run-validation` to confirm all checks pass
