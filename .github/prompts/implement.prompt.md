---
name: implement
agent: "implement"
description: "Use implement agent to build or fix code"
---

${input:request:What would you like to implement?}

## Context

You are in **Freeform Implementation Mode**. Translate requirements into working code.

### Key Rules
- ALWAYS create todo list for multi-step changes
- ALWAYS run tests after changes
- NEVER edit `*_generated/` directories
- NO `any`/`Any` in TypeScript/Python
- Read `docs/DOCUMENTATION-GUIDE.md` to find relevant docs for your task
- Use `make` targets — never raw `npm`, `poetry`, `pip`, or `python` commands

### Output
Incremental updates per step, completion summary with files changed, test results.

### Skills
Apply these skills from `.github/skills/`: drift-guard, mode-interactive

$ARGUMENTS
