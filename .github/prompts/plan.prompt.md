---
name: plan
agent: "builder"
description: "Comprehensive sprint plan — build, test, verify, and doc updates. Dynamic plan that adjusts during discovery."
---

${input:request:What do you want to plan? (describe the feature, refactor, or fix)}

## Context

You are producing a **comprehensive sprint plan**. Effort tier: **Plan-only**.

### Effort Calibration: Plan-only

Plan comprehensively, don't build. Produce a validated, sprint-ready plan covering the **full lifecycle**:
- **Full discovery** — research, scan codebase, check docs, identify risks
- **Implementation planning** — decompose into steps with file paths, acceptance criteria, risk levels
- **Test planning** — identify what tests to write/update, coverage expectations, test isolation strategy
- **Verification planning** — define verification checkpoints per step (type-check, unit, integration, visual)
- **Documentation planning** — identify which docs need creating/updating after changes
- **No implementation** — do NOT spawn `implement` subagent, do NOT edit files
- **Output the plan** and stop

### Dynamic Plan State

The plan is a **living document** — discovery findings may reshape it:
- Phases are sequential but the plan adjusts as each phase reveals new information
- If discovery reveals the change scope is different than initially assumed → revise the plan
- **When plan adjustments alter the final deliverable** (scope, acceptance criteria, or effort changes significantly) → use interactive mode to present the divergence and debate the revised direction with the user before finalizing
- Flag any phase where the plan "branched" from original assumptions

### Scope Signals
- User wants to see the full approach before committing
- Complex or risky change that benefits from review
- Multiple valid approaches — plan should surface them with tradeoffs

### Key Rules
- Ground the plan in codebase evidence — reference real file paths, existing patterns
- Read `docs/DOCUMENTATION-GUIDE.md` to find relevant architecture docs
- Use `make` targets in command templates — never raw `npm`, `poetry`, `pip`, or `python`
- Identify exact file paths, modules, and dependencies for each step
- Flag risks explicitly with severity
- Every implementation step must have a paired verification step
- Every test step must specify: scope (unit/integration), fixtures needed, mock strategy

### Output Format

```markdown
# Sprint Plan: [scope]

| Attribute | Value |
|-----------|-------|
| Type | Feature / Refactor / Fix / Test |
| Estimated Effort | S / M / L / XL |
| Risk Level | Low / Medium / High |
| Files Affected | [count] |
| Modules Touched | [list] |
| Plan State | Initial / Revised (reason) |

## Implementation Steps

**1. [Step Title]** `[Risk: Low|Medium|High]`
- Files: [paths]
- Task: [description]
- Acceptance: [what "done" looks like]
- Verification: [how to confirm]

## Test Plan

| Test | Type | Files | Fixtures/Mocks | Coverage Target |
|------|------|-------|-----------------|-----------------|
| ... | unit/integration | ... | ... | ... |

## Verification Checkpoints

| After Step | Check | Command | Pass Criteria |
|------------|-------|---------|---------------|
| ... | type-check / unit / integration / visual | ... | ... |

## Documentation Updates

| Doc | Action | Reason |
|-----|--------|--------|
| ... | Create / Update / Review | ... |

## Risks & Mitigations
| Risk | Severity | Mitigation |
|------|----------|------------|

## Open Questions
[Items that need resolution before execution]

## Plan Adjustments
[If discovery changed the plan — what shifted and why]
```

After delivering the plan, suggest **"Use `/build` to execute this plan"** when ready.

### Skills
Apply these skills from `.github/skills/`: plan-implement, engineering-principles, design-review, mode-interactive

$ARGUMENTS
