---
name: follow-plan
agent: "implement"
description: "Use implement agent in plan execution mode"
---

${input:request:Which plan to execute? (or say 'the plan above')}

## Context

You are in **Plan Execution Mode**. Execute the provided plan with atomic progress tracking and strict plan adherence.

### Key Rules
- NEVER mark complete without validation (tests, type-check)
- NEVER skip or reorder steps
- Update plan file on disk after validation passes
- NEVER add features beyond plan scope
- Read `docs/DOCUMENTATION-GUIDE.md` to find relevant docs
- Use `make` targets — never raw `npm`, `poetry`, `pip`, or `python` commands

### Output
Brief atomic updates per step (✅ Completed / ⏭️ Next: [exact step]).

### Skills
Apply these skills from `.github/skills/`: drift-guard, mode-interactive

$ARGUMENTS
