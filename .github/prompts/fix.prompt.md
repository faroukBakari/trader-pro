---
name: fix
agent: "builder"
description: "Quick targeted fix — typos, small bugs, bounded corrections. Builder runs in lightweight mode."
---

${input:request:What needs fixing? (describe the issue and where)}

## Context

You are performing a **quick, targeted fix**. Effort tier: **Quick**.

### Effort Calibration: Quick

This is a bounded correction — typo, small bug, rename, config tweak, or single-file fix. Builder should:
- **Skip** heavy discovery and multi-step planning
- **Single implement** invocation (1-3 files max)
- **Verify** via type-check or quick test, not full suite
- **Minimal summary** — no extensive completion report

### Scope Signal
- Target is clear and bounded
- Acceptance criteria: "the fix works"
- If this turns out bigger than expected → upgrade to standard effort

### Key Rules
- Ground changes in codebase evidence — read before editing
- Read `docs/DOCUMENTATION-GUIDE.md` only if relevant to the fix domain
- Use `make` targets — never raw `npm`, `poetry`, `pip`, or `python` commands
- Follow existing code patterns and conventions

### Skills
Apply these skills from `.github/skills/`: engineering-principles, fix-type-errors

$ARGUMENTS
