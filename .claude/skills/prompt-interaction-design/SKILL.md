---
name: prompt-interaction-design
description: Structured user input gathering via ask_questions — decision flowchart, component patterns, inference heuristics. Load when facing vague instructions or designing prompts that gather user input
user-invocable: false
---

# Interactive Prompt Design

Structured decision-making and component patterns for gathering user input via the `ask_questions` tool. Covers **when** to ask (decision flowchart + inference heuristics) and **how** to ask (component patterns + design rules).

---

## Phase 0: Should I Ask?

### Decision Flowchart

```
Is the task type obvious from the request?
   NO  → Ask via ask_questions
   YES → Infer and proceed

Is scope/complexity explicitly stated?
   NO  → Ask or infer from context
   YES → Use stated scope

Are focus areas mentioned or implied?
   NO  → Ask multi-select for priorities
   YES → Include mentioned areas + sensible defaults

Rule: If 2+ areas unclear → batch into one ask_questions call
      If 1 unclear → infer default, note assumption explicitly
```

### Inference Heuristics

When keywords strongly signal intent, infer rather than ask:

| Signal Words | Likely Intent | Confidence |
|---|---|---|
| "bug", "broken", "failing", "error" | Fix/Debug | High |
| "refactor", "improve", "clean up" | Refactoring | High |
| "add", "implement", "new", "create" | New feature | High |
| "should we", "compare", "evaluate", "which" | Decision/Analysis | High |
| "quick", "brief", "just" | Minimal scope | Medium |
| "thorough", "comprehensive", "deep" | Full scope | Medium |

**Rule**: High confidence → proceed. Medium confidence → note assumption.

### Trigger Conditions

| Phase | Trigger | Component Type |
|---|---|---|
| **Start** | Ambiguous scope (2+ unclear areas) | Multi-question `ask_questions` call |
| **Options** | 2+ viable approaches exist | Single-select with trade-offs |
| **Next Steps** | Path forward unclear | Single-select for action |

### When NOT to Ask

- Intent is obvious from context (infer instead)
- User already clarified in previous messages
- Only one viable approach exists

---

## Component Reference

### Available Components

| Component | Config | Best For |
|---|---|---|
| **Single-Select** | `multiSelect: false` (default) | Either/or decisions, approach selection |
| **Multi-Select** | `multiSelect: true` | Feature toggles, priority selection |
| **Free Text** | `allowFreeformInput: true` | Names, custom values, explanations |
| **Free Text Only** | `options: []` (empty array) | Open-ended input with no presets |
| **Recommended** | `recommended: true` on one option | Guide toward best practices |

### askQuestions Schema

```
ask_questions({
  questions: [                      // 1-4 questions per call
    {
      header: "string",             // <=12 chars — UI label AND response key (REQUIRED)
      question: "string",           // Full question text (REQUIRED)
      multiSelect: boolean,         // true = checkboxes, false = single-select (default: false)
      allowFreeformInput: boolean,  // true = user can type custom text (default: false)
      options: [                    // 0-6 options; omit/empty = free text input only
        {
          label: "string",          // Option text (REQUIRED)
          description: "string",    // Secondary text shown below label (optional)
          recommended: boolean      // Pre-selects option, shows recommended badge (optional)
        }
      ]
    }
  ]
})
```

### Response Format

```json
{
  "answers": {
    "<header>": {
      "selected": ["Label A", "Label B"],
      "freeText": "user typed text or null",
      "skipped": false
    }
  }
}
```

### Hard Constraints

| Parameter | Limit | Failure Mode |
|---|---|---|
| `header` | <=12 characters | **Validation error** — tool call fails |
| `questions` | 1-4 per call | **Validation error** — tool call fails |
| `options` | 0-6 per question | **Validation error** — tool call fails |
| `recommended` | Max 1 per question | UX confusion — multiple pre-selected |
| `recommended` | **NEVER** on quiz/poll options | Reveals answer — pre-selects it |

---

## Design Patterns

### Pattern: Pre-Implementation Gathering

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

## Interaction Rules

1. **Batch** related questions into a single `ask_questions` call (max 4)
2. **Mark one** option as `recommended` with justification in `description`
3. **Multi-select** for additive choices ("which features"); single-select for either/or ("which approach")
4. **Headers** <=12 chars — they're both UI labels and JSON response keys
5. **Summarize** user choices in a markdown table after receiving response
6. **Proceed** with implementation — do not re-ask unless requirements change

---

## Trigger Keywords

| User Says | Response Strategy |
|---|---|
| "help me decide", "choose between" | Single-select with trade-offs |
| "set up", "configure", "initialize" | Multi-question wizard (2-4 questions) |
| "implement", "create" (ambiguous scope) | Clarify scope and approach |
| "refactor", "migrate", "upgrade" | Gather constraints and priorities |
| Multiple items listed ("X, Y, and Z") | Multi-select for prioritization |

---

## Anti-Patterns

| Don't | Do Instead |
|---|---|
| Markdown-formatted questions instead of `ask_questions` tool | Always use `ask_questions` for structured input |
| One question per call when multiple are related | Batch into one call (max 4) |
| `header` longer than 12 characters | Keep short — causes validation error |
| More than 6 options per question | Reduce — causes decision fatigue |
| `recommended: true` on quiz/poll answers | Reveals the answer — pre-selects it |
| Re-asking after user already clarified | Proceed with stated preference |
| Asking when intent is obvious from context | Infer from signal words and proceed |
| Missing "do nothing" / "skip" option for optional changes | Always include opt-out for non-mandatory decisions |
