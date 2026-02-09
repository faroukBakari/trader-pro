# Skill Examples & Quick Reference

Companion reference for `skill-template.md`. Contains portability examples, scope guidance, directory structure, and concrete good/bad examples.

---

## Portability Requirements

Skills must be agent-agnostic and tool-agnostic. Gate S1 and S2 check this — here are concrete examples:

### Agent References

❌ **Don't** reference specific agents:
```
Use the `implement` agent to execute this...
Delegate to `research` subagent...
```

✅ **Do** use generic references:
```
Delegate research tasks to a read-only subagent...
Use an implementation agent to execute...
```

### Tool References

❌ **Don't** reference specific tools:
```
tools: ['read', 'search', 'edit']
Use the edit tool to modify files...
```

✅ **Do** describe capabilities:
```
Modify the target file...
Search the codebase for patterns...
```

---

## Skill Scope

A skill should teach **one cohesive method**. If covering multiple unrelated methods, split it.

**Good scope** (focused):
- `debug-hypothesis` — Hypothesis-driven debugging workflow
- `terminal-usage` — Command safety checks and delegation routing
- `design-review` — Solution selection and stress-testing

**Bad scope** (too broad):
- `development-practices` — Testing, debugging, code review, deployment...
  → Split into separate skills

---

## Skill vs Agent: What Goes Where

| Content Type | Lives In |
|--------------|----------|
| Repeatable method | **SKILL** |
| Tool configuration | Agent |
| Subagent topology | Agent |
| Handoff definitions | Agent |
| Behavioral constraints | Agent |

**Test**: "Could a different agent benefit from this exact method?"
- YES → Skill
- NO → Agent-specific, keep inline

---

## Resource Organization

Skills can include additional files beyond SKILL.md:

```
.github/skills/{skill-name}/
├── SKILL.md           # Main skill definition (always loaded at L2)
├── template.md        # Template file (loaded at L3 on reference)
├── example.py         # Example script
└── resources/         # Additional resources
    ├── checklist.md
    └── pattern.md
```

Reference resources using relative paths:
```
See [template](./template.md) for the standard format.
```

---

## Examples

### Good (Portable) Skill

Agent-agnostic, focused method, clear phases:

```yaml
---
name: test-strategy
description: Test planning and coverage analysis. Use when designing test approaches or analyzing test gaps.
---
# Test Strategy

## When to Use
- Planning test coverage for new features
- Analyzing existing test gaps
- Selecting test types (unit, integration, e2e)

## Methodology
### Phase 1: Coverage Analysis
1. Identify critical paths
2. Map existing coverage
3. Find gaps
```

### Bad (Agent-Aware) Skill

References specific agents and tools — this is agent configuration, not a portable skill:

```yaml
---
name: implementation-flow
description: How the implement agent works
---
# Implementation Flow

The `implement` agent follows these steps:
1. Uses the `edit` tool to modify files
2. Runs `execute` tool for tests
3. Delegates to `test` subagent for coverage
```

---

## Quality Checklist

Cross-reference with S1–S5 gates in `ia-quality-gates` skill:

- [ ] Agent-agnostic (no agent names) — S1
- [ ] Tool-agnostic (no tool references) — S2
- [ ] Teaches a repeatable method — S3
- [ ] No project-specific paths — S4
- [ ] Description includes when-to-use triggers — S5
- [ ] Clear phase/step structure
- [ ] Includes examples or templates
- [ ] Lists anti-patterns
