---
name: build
agent: "builder"
description: "Feature implementation, refactoring, or test writing — full plan-delegate-verify lifecycle."
---

${input:request:What do you want to build, refactor, or implement?}

## Context

You are executing a **standard build lifecycle**. Effort tier: **Standard**.

### Effort Calibration: Standard

This is a feature, refactor, or substantial change requiring the full builder lifecycle:
- **Full discovery** — research, scan codebase, check docs
- **Dynamic planning** — decompose into atomic tasks with acceptance criteria
- **Build loop** — delegate to implement, verify each step, adjust plan
- **Documentation check** — assess if docs need updating after changes
- **Full verification** — run relevant test suite, type-check, visual check if frontend

### Scope Signals
- Multiple files likely affected
- Tests expected (new or updated)
- Cross-module awareness may be needed
- Acceptance criteria should be explicitly captured

### Key Rules
- Ground all changes in codebase evidence
- Read `docs/DOCUMENTATION-GUIDE.md` to find relevant architecture docs first
- Use `make` targets — never raw `npm`, `poetry`, `pip`, or `python` commands
- Follow existing code patterns — search before creating new abstractions
- Verify after every implement invocation — never skip verification

### Output Expectations

```markdown
## Build Complete: [scope]

**Tasks:** X/X complete
**Files changed:** [list with paths]
**Tests:** All passing (X new, Y updated)
**Docs:** [Updated / Not needed]
**Issues:** [None / list remaining items]
```

### Skills
Apply these skills from `.github/skills/`: plan-implement, engineering-principles, backend-testing, frontend-testing

$ARGUMENTS
