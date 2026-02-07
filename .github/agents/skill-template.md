# Skill Template

Use this template when creating new skills. Skills should be **PORTABLE** — usable by any agent, not tied to specific tools or agent topology.

---

<!-- BLUEPRINT START: Copy ONLY the content between BLUEPRINT START and BLUEPRINT END into the new file. The written file must be raw text starting with "---" (YAML frontmatter). When verifying, ignore any backtick fences the read_file tool adds to its display output — those are rendering artifacts, not part of the file. -->
---
name: {skill-name}
description: {What the skill teaches and when to use it}. Use when {trigger scenarios}.
---

# {Skill Title}

{One-paragraph description of what capability this skill provides}

---

## When to Use This Skill

{Describe scenarios where this skill applies:}

- {Scenario 1}
- {Scenario 2}
- {Scenario 3}

---

## Methodology

### Phase 1: {Phase Name}

{Describe the first phase of the method}

**Steps:**
1. {Action with specific guidance}
2. {Action with specific guidance}
3. {Action with specific guidance}

**Example:**
```
{Optional: show example of phase 1 output}
```

### Phase 2: {Phase Name}

{Describe the second phase}

**Steps:**
1. {Action with specific guidance}
2. {Action with specific guidance}

**Decision table** (if applicable):
| Condition | Action |
|-----------|--------|
| {Case 1} | {Response 1} |
| {Case 2} | {Response 2} |

### {Additional phases as needed}

---

## Templates / Patterns

{If the skill includes templates, checklists, or patterns, include them here}

**Checklist Example:**
```
□ {Check 1}
□ {Check 2}
□ {Check 3}
```

**Pattern Example:**
```
{Show reusable pattern or template}
```

---

## Anti-Patterns

{Describe common mistakes to avoid}

- ❌ {Anti-pattern 1} — {Why it's wrong}
- ❌ {Anti-pattern 2} — {Why it's wrong}
- ✅ {Correct approach} — {Why it's right}

---

## Output Format

{If the skill produces specific output, describe the format}

```markdown
{Example output structure}
```

---

## Resources

{Optional: reference scripts, examples, or other resources in the skill directory}

- [Example script](./example-script.sh) — {What it does}
- [Template file](./template.md) — {What it's for}
<!-- BLUEPRINT END -->

---

> **Template guidance**: Apply `agent-create` skill (portability, description quality) and `ia-quality-gates` skill (S1-S5 gates) when populating this template. See [skill-examples.md](./skill-examples.md) for portability patterns, scope guidance, and concrete good/bad examples.
