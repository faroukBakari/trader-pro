# Prompt Examples & Quick Reference

Companion reference for `prompt-template.md`. Contains VS Code-specific variable syntax, boundary guidance, and concrete examples.

---

## VS Code Prompt Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `${input:name:default}` | User input with default | `${input:model:gpt-4}` |
| `${selection}` | Currently selected text | Code review context |
| `${file}` | Current file path | File-specific analysis |
| `${workspaceFolder}` | Workspace root | Path references |

---

## What Belongs in Prompts

✅ **INCLUDE**:
- Task-specific context
- Deliverable specification
- Input variables (`${input:...}`)
- File/folder references
- Success criteria

❌ **EXCLUDE** (these belong in the agent):
- Methodology (Phase 1, Phase 2...)
- Constraints (CRITICAL/IMPORTANT)
- Tool lists (agent owns these)
- Behavioral rules
- Output templates (unless task-specific)

---

## Prompt vs Direct Agent Use

| Scenario | Use Prompt? | Reasoning |
|----------|-------------|-----------|
| Repeatable task with template | ✅ Yes | Saves keystrokes, ensures consistency |
| One-off question | ❌ No | Just ask agent directly |
| Needs input variables | ✅ Yes | Structured input gathering |
| Team standardization | ✅ Yes | "Approved work order" |

---

## Examples

### Good (Thin) Prompt

Only context + deliverable — methodology lives in the agent:

```yaml
---
agent: "study"
name: "api-design"
description: "Study RESTful API design approach"
---
# API Design Study

Analyze the API design for ${input:endpoint:/api/users}.

Focus areas: RESTful compliance, security, performance.

**Deliverable**: Architecture recommendation with pros/cons.
```

### Bad (Methodology Leakage)

This prompt absorbed agent methodology — **move phases to the agent**:

```yaml
---
agent: "study"
name: "api-design"
---
# API Design Study

## Phase 1: Discovery
1. Search codebase for existing patterns
2. Check industry standards
3. Validate against OWASP

## Phase 2: Analysis
[50 more lines...]
```

---

## Quality Checklist

Cross-reference with P1–P6 gates in `ia-quality-gates` skill:

- [ ] ≤ 50 lines (excluding frontmatter) — P1
- [ ] No methodology sections — P2
- [ ] No constraint hierarchies — P2
- [ ] No tool lists — P3
- [ ] Agent reference present
- [ ] Uses variables for reusability — P4
- [ ] Focus on "what" not "how" — P5
- [ ] Clear deliverable specification
