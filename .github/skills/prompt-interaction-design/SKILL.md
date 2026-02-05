---
name: prompt-interaction-design
description: Interactive UI component patterns for agent prompts. Use when designing prompts that gather user input, preferences, or need wizard-style interactions.
---

# Interactive Component Patterns

Apply these patterns when generating prompts that need structured user input.

---

## Available Components

| Component | Trigger | Best For |
|-----------|---------|----------|
| **Single-Select** | `multiSelect: false` | Technology choices, either/or decisions |
| **Multi-Select** | `multiSelect: true` | Feature selection, capability toggles |
| **Free Text** | `allowFreeformInput: true` | Names, custom values |
| **Recommended** | `recommended: true` | Guide toward best practices |

---

## When to Use Interactive Components

Use interactive gathering when:
- Task has multiple valid approaches (let user choose)
- User preferences significantly affect outcome
- 2+ independent decisions needed (batch questions)
- Clarifying questions would improve quality

---

## Interaction Rules

- Max 4 questions per batch, 2-6 options each
- Mark one option as `recommended` with justification
- Multi-select for additive choices, single-select for either/or
- Headers ≤12 chars; summarize choices in table after

---

## Pattern: Pre-Implementation Gathering

```xml
<user_interaction>
WHEN TO INTERACT:
- Before features with multiple valid approaches
- When configuration affects architecture
- When preferences are not explicitly stated
- When gathering 2+ related pieces of information

FORMAT:
- Batch up to 4 related questions
- 2-6 options per question
- Mark one recommended with justification
- Multi-select for "which features"
- Single-select for "which approach"

AFTER INTERACTION:
- Summarize choices in table
- Proceed with implementation
- Do not re-ask unless requirements change
</user_interaction>
```

---

## Trigger Keywords

| User Says | Response Strategy |
|-----------|-------------------|
| "help me decide", "choose between" | Present options with trade-offs |
| "set up", "configure", "initialize" | Wizard-style multi-question |
| "implement", "create" (ambiguous) | Clarify scope and approach |
| "refactor", "migrate", "upgrade" | Gather constraints and priorities |
| Multiple items listed ("X, Y, and Z") | Multi-select for prioritization |
