---
name: study
agent: "advisor"
description: "Use advisor agent for deep technical studies, design evaluation, and architecture analysis"
---

${input:request:What would you like to study or evaluate?}

## Context

You are conducting a **deep technical study**. Produce a structured, comprehensive analysis with options, tradeoffs, and a clear recommendation.

### Depth Calibration
- **Simple** questions → Quick Verdict (3-4 paragraphs)
- **Moderate** questions → Standard Report
- **Complex** questions → Full structured report with options table

### Key Rules
- Ground recommendations in codebase evidence
- Always include exit strategy for vendor-specific solutions
- Read `docs/DOCUMENTATION-GUIDE.md` to find relevant docs for your task
- Use `make` targets — never raw `npm`, `poetry`, `pip`, or `python` commands

### Output Format

**Quick Verdict** (simple):
```
**Question:** [Restate]  |  **Verdict:** [Proceed/Not]  |  **Recommendation:** [Action]
Key considerations + Caveats
```

**Standard Report** (moderate/complex):
```
# Technical Study: [Topic]
| Attribute | Value |
|-----------|-------|
| Study Type | Feature Design / Refactoring / Flaw Remediation |
| Complexity | Simple / Moderate / Complex |
| Verdict | Proceed / Proceed with Caveats / Do Not Proceed |
| Confidence | High / Medium / Low |
| Risk Level | Low / Medium / High |
| Effort | S / M / L / XL |

## Summary → Context → Codebase Analysis → Leverage Assessment → Solution Options → Risks → Implementation Sketch → Next Steps
```

After delivering the study, **offer handoffs** to "Plan Implementation" or "Start Implementation" when actionable.

### Skills
Apply these skills from `.github/skills/`: design-review, mode-interactive

$ARGUMENTS
