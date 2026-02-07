---
name: prompt-interaction-design
description: VS Code native ask_questions tool patterns for agent prompts. Use when designing prompts that gather user input, preferences, or need wizard-style interactions via real UI widgets.
---

# Interactive Component Patterns

Apply these patterns when designing agent prompts that need structured user input. **Always use the VS Code native `ask_questions` tool** — it provides real quick-pick widgets that return structured JSON.

For the full `ask_questions` tool contract (schema, response format, hard constraints), apply the **`vscode-integration`** skill § `askQuestions`.

---

## Available Components

| Component | Config | Best For | Example |
|-----------|--------|----------|---------|
| **Single-Select** | `multiSelect: false` (default) | Either/or decisions, approach selection | "Which pattern?" |
| **Multi-Select** | `multiSelect: true` | Feature toggles, priority selection | "Which areas?" |
| **Free Text** | `allowFreeformInput: true` | Names, custom values, explanations | "Project name?" |
| **Free Text Only** | `options: []` (empty array) | Open-ended input with no presets | "Describe the issue" |
| **Recommended** | `recommended: true` on one option | Guide toward best practices | Default approach |

---

## When to Use Interactive Components

Use `ask_questions` when:
- Task has multiple valid approaches (let user choose)
- User preferences significantly affect outcome
- 2+ independent decisions needed (batch into one call)
- Clarifying questions would improve quality
- Scope or target is ambiguous

**Do NOT use** when:
- Intent is obvious from context (infer instead)
- User already clarified in previous messages
- Only one viable approach exists

---

## Interaction Rules

1. **Batch** related questions into a single `ask_questions` call (max 4)
2. **Mark one** option as `recommended` with justification in `description`
3. **Multi-select** for additive choices ("which features"); single-select for either/or ("which approach")
4. **Headers** ≤12 chars — they're both UI labels and JSON response keys
5. **Summarize** user choices in a markdown table after receiving response
6. **Proceed** with implementation — do not re-ask unless requirements change

---

## Design Patterns

### Pattern: Pre-Implementation Gathering

Use when a task has multiple valid approaches or configurations:

```
ask_questions({
  questions: [
    {
      header: "Approach",
      question: "Which implementation approach should I use?",
      options: [
        { label: "Option A", description: "Trade-off summary", recommended: true },
        { label: "Option B", description: "Trade-off summary" },
        { label: "Do Nothing", description: "Keep current implementation" }
      ]
    },
    {
      header: "Scope",
      question: "How thorough should the change be?",
      options: [
        { label: "Minimal", description: "Only the specific issue" },
        { label: "Moderate", description: "Issue + adjacent improvements", recommended: true },
        { label: "Full", description: "Complete area refactor" }
      ]
    }
  ]
})
```

### Pattern: Feature Selection

Use when user needs to pick from a set of additive options:

```
ask_questions({
  questions: [
    {
      header: "Features",
      question: "Which capabilities should be included?",
      multiSelect: true,
      options: [
        { label: "Auth", description: "JWT + OAuth2", recommended: true },
        { label: "WebSocket", description: "Real-time updates" },
        { label: "Caching", description: "Redis-backed cache layer" },
        { label: "Rate Limiting", description: "Per-user throttling" }
      ]
    }
  ]
})
```

### Pattern: Named Input

Use when you need a user-provided name or custom value:

```
ask_questions({
  questions: [
    {
      header: "Name",
      question: "What should the new module be called?",
      allowFreeformInput: true,
      options: [
        { label: "analytics", description: "Based on described functionality" },
        { label: "reporting", description: "Matches existing naming convention" }
      ]
    }
  ]
})
```

### Pattern: Free Text Only

Use when no presets make sense — user must describe in their own words:

```
ask_questions({
  questions: [
    {
      header: "Details",
      question: "Describe the expected behavior that isn't working correctly."
    }
  ]
})
```

---

## Trigger Keywords

| User Says | Response Strategy |
|-----------|-------------------|
| "help me decide", "choose between" | Single-select with trade-offs |
| "set up", "configure", "initialize" | Multi-question wizard (2–4 questions) |
| "implement", "create" (ambiguous scope) | Clarify scope and approach |
| "refactor", "migrate", "upgrade" | Gather constraints and priorities |
| Multiple items listed ("X, Y, and Z") | Multi-select for prioritization |

---

## Anti-Patterns

- ❌ Markdown-formatted questions instead of `ask_questions` tool
- ❌ One question per call when multiple are related (batch them)
- ❌ `header` longer than 12 characters (causes validation error)
- ❌ More than 6 options (decision fatigue)
- ❌ `recommended: true` on quiz/poll answers (reveals the answer)
- ❌ Re-asking after user already clarified
- ❌ Asking when intent is obvious from context
- ❌ Missing "do nothing" / "skip" option for optional changes
