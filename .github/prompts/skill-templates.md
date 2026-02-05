# Skill Content Templates

Reference templates for crafting SKILL.md content. Select template based on skill type.

> ⚠️ **VS Code / GitHub Copilot Compatibility**: Only `name` and `description` are reliably supported. Other fields like `user-invocable`, `disable-model-invocation`, `argument-hint` are **NOT supported** and will be ignored.

> 🚨 **FILE FORMAT**: SKILL.md files must **NOT** have code fence wrappers (no ` ```yaml `, ` ```markdown `, ` ```skill `).
> The file must start directly with `---` (YAML frontmatter). Code fences in templates below are for **documentation display only**.

---

## Reference Skill Template

Use for conventions, patterns, domain knowledge that the agent applies inline.

```markdown
---
name: {name}
description: {What it teaches}. Apply when {trigger contexts}.
---

# {Title}

{Brief intro — when and why to apply this knowledge.}

## {Category 1}

{Conventions, patterns, or rules:}

- {Rule 1}
- {Rule 2}

## {Category 2}

| Pattern   | Usage         | Example   |
| --------- | ------------- | --------- |
| {pattern} | {when to use} | {example} |

## Anti-Patterns

{What NOT to do:}

- ❌ {Anti-pattern 1} — {why it's wrong}
- ❌ {Anti-pattern 2} — {why it's wrong}
```

---

## Task Skill Template

Use for step-by-step workflows with explicit actions.

````markdown
---
name: {name}
description: {What it does}. Use when {trigger phrases}.
---

# {Task Name}

{Brief description of the workflow goal.}

## Prerequisites

{What must be true before starting:}

- {Prereq 1}
- {Prereq 2}

## Input

{Document expected input in the skill body since argument-hint is not supported.}

## Steps

1. **{Step name}**: {What to do}
   ```bash
   {command if applicable}
   ```
````

2. **{Step name}**: {What to do}
   - {Sub-step}
   - {Sub-step}

3. **{Step name}**: {What to do}

## Success Criteria

{How to know the task is complete:}

- [ ] {Criterion 1}
- [ ] {Criterion 2}

## Troubleshooting

| Symptom   | Likely Cause | Fix   |
| --------- | ------------ | ----- |
| {symptom} | {cause}      | {fix} |

````

---

## Hybrid Skill Template

Use when skill has both reference knowledge AND a workflow.

```markdown
---
name: {name}
description: {What it does and teaches}. Use when {trigger phrases}.
---

# {Skill Name}

{Brief intro.}

## Conventions

{Reference knowledge section — patterns to apply.}

## Workflow

{Task section — steps to follow.}

## Reference

For detailed {topic}, see [reference.md](reference.md).
````

---

## Template Selection Guide

| Skill Purpose                 | Template  | Description Strategy                          |
| ----------------------------- | --------- | --------------------------------------------- |
| Conventions/patterns to apply | Reference | Domain keywords ("patterns", "conventions")   |
| Step-by-step workflow         | Task      | Action verbs ("debug", "generate", "analyze") |
| Both knowledge + actions      | Hybrid    | Mixed keywords                                |

## Frontmatter Quick Reference

| Field           | Status          | Notes                                        |
| --------------- | --------------- | -------------------------------------------- |
| `name`          | ✅ Required     | Lowercase-hyphenated, max 64 chars           |
| `description`   | ✅ Required     | Single-line, max 150 chars, trigger keywords |
| `allowed-tools` | ⚠️ Experimental | Space-delimited tool whitelist               |
| `license`       | ✅ Optional     | License name or file reference               |
| `compatibility` | ✅ Optional     | Environment requirements                     |
| `metadata`      | ✅ Optional     | Custom key-value pairs                       |

### ❌ Fields NOT Supported in VS Code

| Field                      | Status     |
| -------------------------- | ---------- |
| `user-invocable`           | ❌ Ignored |
| `disable-model-invocation` | ❌ Ignored |
| `argument-hint`            | ❌ Ignored |
| `context: fork`            | ❌ Ignored |
| `agent`                    | ❌ Ignored |

## Placeholder Reference

| Placeholder          | Replace With                          |
| -------------------- | ------------------------------------- |
| `{name}`             | Lowercase-hyphenated skill name       |
| `{description}`      | Single-line with 2-3 trigger keywords |
| `{trigger contexts}` | When agent should auto-load           |
| `{trigger phrases}`  | What users say to invoke              |
