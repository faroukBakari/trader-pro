---
name: doc-assess
agent: "advisor"
model: "Claude Sonnet 4.5 (copilot)"
description: "Audit documentation health with 6-dimension scoring"
argument-hint: "What to assess? (directory, module, or 'full audit')"
---

${input:scope:What documentation to assess? (e.g. docs/, backend/docs/, or 'full audit')}

## Context

Assess documentation health for: **${scope}**

- Start from `docs/DOCUMENTATION-GUIDE.md` for structure discovery
- Skip `*_generated/` directories
- Check docs against actual codebase state

## Deliverable

Apply the `doc-assessment` skill (from `.github/skills/doc-assessment/SKILL.md`):

1. **Scorecard** — 6 dimensions scored 1-10 with overall rating
2. **Gap Summary** — specific gaps per low-scoring dimension
3. **Remediation Plan** — prioritized actions (Quick Wins / Strategic / Backlog)

Save the remediation plan to `docs/tmp/doc-remediation-plan.md`.

$ARGUMENTS
