---
name: mode-interactive
description: Guides decision-making when facing open-ended requests or multiple viable approaches. Activates when user asks "what should I", "help me decide", "which approach", or gives vague instructions requiring clarification.
---

# Interactive Mode: Smart-Detect Strategy

Use interactive UI components to gather structured user input **when the request is ambiguous**. Skip straight to work when intent is clear.

## Core Decision Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│            SHOULD I USE INTERACTIVE QUESTIONS?                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Is the task type obvious from the request?                     │
│     NO  → Ask for clarification                                 │
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
│  Rule: If 2+ areas unclear → batch into one interaction         │
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

## Interaction Format Rules

| Rule                 | Guidance                                      |
| -------------------- | --------------------------------------------- |
| **Batch questions**  | Max 3-4 per interaction block                 |
| **Provide options**  | 2-6 choices with brief descriptions           |
| **Mark recommended** | Highlight best option with justification      |
| **Multi-select**     | For additive choices ("which areas to cover") |
| **Single-select**    | For either/or choices ("which approach")      |
| **Summarize**        | Table of user choices after interaction       |
| **Don't re-ask**     | Unless requirements explicitly change         |

## When to Trigger Interactions

| Phase          | Trigger Condition                  | Component Type                |
| -------------- | ---------------------------------- | ----------------------------- |
| **Start**      | Ambiguous scope (2+ unclear areas) | Multi-question wizard         |
| **Options**    | 2+ viable approaches exist         | Single-select with trade-offs |
| **Next Steps** | Path forward unclear               | Single-select for action      |

## Sample Interaction Format

When presenting choices:

```
**[Category]**

Which approach should I proceed with?

- **Option A** — [trade-off summary] ✅ Recommended: [reason]
- **Option B** — [trade-off summary]
- **Option C (Do Nothing)** — Status quo, [consequence]
```

After selection: proceed with chosen option, include comparison if helpful.

## Anti-Patterns

- ❌ Asking when intent is obvious from context
- ❌ Asking one question at a time (batch related questions)
- ❌ Re-asking after user already clarified
- ❌ More than 6 options (decision fatigue)
- ❌ Missing "do nothing" option for optional changes
