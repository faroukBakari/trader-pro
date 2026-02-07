---
name: mode-interactive
description: Guides decision-making when facing open-ended requests or multiple viable approaches. Uses VS Code native ask_questions tool for structured UI widgets. Activates when user asks "what should I", "help me decide", "which approach", or gives vague instructions requiring clarification.
---

# Interactive Mode: Smart-Detect Strategy

Use VS Code's native **`ask_questions`** tool to gather structured user input through real UI widgets (dropdowns, multi-select, free text) **when the request is ambiguous**. Skip straight to work when intent is clear.

For the full `ask_questions` tool contract (schema, response format, hard constraints, and call patterns), apply the **`vscode-integration`** skill § `askQuestions`.

## Core Decision Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│            SHOULD I USE INTERACTIVE QUESTIONS?                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Is the task type obvious from the request?                     │
│     NO  → Ask via ask_questions                                 │
│     YES → Infer and proceed                                     │
│                                                                 │
│  Is scope/complexity explicitly stated?                         │
│     NO  → Ask or infer from context                             │
│     YES → Use stated scope                                      │
│                                                                 │
│  Are focus areas mentioned or implied?                          │
│     NO  → Ask multi-select for priorities                       │
│     YES → Include mentioned areas + sensible defaults           │
│                                                                 │
│  Rule: If 2+ areas unclear → batch into one ask_questions call  │
│        If 1 unclear → infer default, note assumption explicitly │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Inference Heuristics

When keywords strongly signal intent, infer rather than ask:

| Signal Words                                | Likely Intent     | Confidence |
| ------------------------------------------- | ----------------- | ---------- |
| "bug", "broken", "failing", "error"         | Fix/Debug         | High       |
| "refactor", "improve", "clean up"           | Refactoring       | High       |
| "add", "implement", "new", "create"         | New feature       | High       |
| "should we", "compare", "evaluate", "which" | Decision/Analysis | High       |
| "quick", "brief", "just"                    | Minimal scope     | Medium     |
| "thorough", "comprehensive", "deep"         | Full scope        | Medium     |

**Rule**: High confidence → proceed. Medium confidence → note assumption.

## Interaction Design Rules

For detailed component patterns and trigger keywords, apply `prompt-interaction-design` skill.

**Quick rules:**
- Use `ask_questions` tool — never fall back to markdown-formatted questions
- Batch related questions (max 4 per call, 2–6 options each)
- Keep `header` ≤12 chars (it's both the UI label and the response key)
- Mark one option as `recommended` with a short justification in `description`
- `multiSelect: true` for additive choices; default (`false`) for either/or
- Summarize user choices in a table after interaction
- Don't re-ask unless requirements explicitly change

## When to Trigger Interactions

| Phase          | Trigger Condition                  | Component Type                      |
| -------------- | ---------------------------------- | ----------------------------------- |
| **Start**      | Ambiguous scope (2+ unclear areas) | Multi-question `ask_questions` call |
| **Options**    | 2+ viable approaches exist         | Single-select with trade-offs       |
| **Next Steps** | Path forward unclear               | Single-select for action            |

## Anti-Patterns

- ❌ Asking when intent is obvious from context
- ❌ Using markdown-formatted questions instead of `ask_questions` tool
- ❌ Asking one question at a time (batch into one `ask_questions` call)
- ❌ Re-asking after user already clarified
- ❌ More than 6 options per question (decision fatigue)
- ❌ `header` longer than 12 characters (tool call will fail)
- ❌ Missing "do nothing" option for optional changes
- ❌ Using `recommended` on quiz/poll options (it pre-selects and reveals the answer)
