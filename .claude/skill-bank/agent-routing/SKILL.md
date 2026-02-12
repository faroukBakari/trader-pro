---
name: agent-routing
description: Task invocation quality standards — context assembly and output contracts. Load when delegating via the Task tool
keywords: [delegation, invocation, task-tool, context-passing, subagent, quality, contracts]
category: ia-design
disable-model-invocation: true
---

# Agent Routing: Invocation Quality

For valid subagent types and routing rules, see CLAUDE.md §4 Delegation Rules. This skill covers **invocation quality** — ensuring every Task call carries complete context and precise output expectations.

---

## Task Delegation

| Mechanism | When to Use | Context |
|-----------|-------------|---------|
| **Task tool** | Background research, implementation, verification, commands | Fresh context — no conversation history leakage |
| **Inline** | IA stack work, simple tasks (<10 steps), tasks needing full context | Full conversation context preserved |
| **Parallel Tasks** | Independent queries or checks that can run simultaneously | Each gets isolated context |

---

## Task Invocation Protocol

**Every Task invocation MUST satisfy two quality requirements:**

1. **Comprehensive context** — the subagent has everything it needs to work autonomously
2. **Precise output description** — the subagent knows exactly what to return and how

Subagents are **stateless** and **context-isolated**. They cannot see your conversation history, open files, prior tool calls, or any other ambient context. Every piece of information they need must be **explicitly included in the prompt**.

### The Invocation Quality Checklist

Before every `Task` call, verify these 7 elements:

```
┌─────────────────────────────────────────────────────────────────┐
│           SUBAGENT INVOCATION QUALITY CHECKLIST                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CONTEXT (what the subagent needs to know)                      │
│  ─────────────────────────────────────────                      │
│  C1. TASK — What specific work to perform                       │
│  C2. SCOPE — Boundaries (files, modules, directories)           │
│  C3. BACKGROUND — Why this matters / what led here              │
│  C4. CONSTRAINTS — Rules, patterns, conventions to follow       │
│  C5. PRIOR KNOWLEDGE — Findings from earlier steps the          │
│      subagent can't see but needs                               │
│                                                                 │
│  OUTPUT (what the caller needs back)                            │
│  ────────────────────────────────────                           │
│  O1. DELIVERABLE — What artifact/information to return          │
│  O2. FORMAT — Structure, sections, level of detail              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Context Assembly Rules (C1–C5)

| Element | What to Include | Common Mistake |
|---------|-----------------|----------------|
| **C1. Task** | Specific action verb + target. "Find all WebSocket reconnection patterns in the broker module" not "look into WebSocket stuff" | Vague task → subagent explores broadly, burns tokens, returns noise |
| **C2. Scope** | Explicit paths, module names, file patterns. "Search in `backend/src/trading_api/modules/broker/`" | Missing scope → subagent searches entire codebase unnecessarily |
| **C3. Background** | 1-3 sentences on why: "We're adding a new order type and need to understand how existing orders are validated before adding ours" | Missing "why" → subagent can't prioritize findings or judge relevance |
| **C4. Constraints** | Project conventions, anti-patterns to avoid, patterns to follow. "Module boundaries: no cross-module imports. Use provider callbacks" | Missing constraints → subagent may suggest or apply anti-patterns |
| **C5. Prior knowledge** | Summarize relevant findings from earlier steps. "We already know AuthService uses Google OAuth (see `modules/auth/`). Focus on token refresh, not initial auth flow" | Omitting prior context → subagent re-discovers known facts, wastes tokens |

### Output Description Rules (O1–O2)

| Element | What to Include | Common Mistake |
|---------|-----------------|----------------|
| **O1. Deliverable** | Name the artifact type explicitly: "A list of all error handling patterns with file references", "An edit report showing success/failure per file", "A gap analysis with critical questions" | Vague deliverable ("tell me what you find") → subagent guesses what matters, may omit critical info |
| **O2. Format** | Specify structure: "Return as a table with columns: Pattern, File, Line, Description", "Use the digest output format", "Return findings grouped by module" | Missing format → inconsistent responses that require mental parsing by caller |

### The Integration Rule

**The caller MUST specify how they will USE the subagent's output.** This is the single most effective way to ensure the subagent returns the right level of detail and focus:

> "I will use your findings to [write tests / make an architecture decision / construct edit instructions / present options to the user]"

This sentence tells the subagent:
- What **level of detail** is needed (implementation-ready vs. summary)
- What **perspective** to take (test-writer vs. architect vs. editor)
- What **to prioritize** (actionable patterns vs. exhaustive coverage)

---

## Invocation Quality Self-Check

Run this 4-point check **before every `Task` call**:

```
BEFORE INVOKING: Task(subagent_type="{type}")
├── 1. CONTEXT COMPLETE?
│   ├── Can the subagent do its job with ONLY what I've written? (no ambient context)
│   ├── Have I specified scope boundaries? (C2: files, dirs, modules)
│   ├── Have I explained WHY? (C3: background + Integration Rule: usage intent)
│   └── Have I included prior knowledge it can't access? (C5: earlier findings)
│
├── 2. OUTPUT SPECIFIED?
│   ├── Is the deliverable named? (O1: list, report, digest, edit plan, gap analysis)
│   ├── Is the format/structure clear? (O2: table, sections, per-file breakdown)
│   └── Does the subagent know how I'll USE its output? (Integration Rule)
│
├── 3. RIGHT SUBAGENT TYPE?
│   ├── IA stack modification → INLINE (not a Task — load ia-stack-ops)
│   ├── Read-only codebase search → Explore
│   ├── Complex/large-output terminal commands → Bash + command-execution skill
│   ├── Implementation planning → Plan
│   └── Everything else → general-purpose (see CLAUDE.md §4 Delegation Rules)
│
└── 4. WORTH DELEGATING?
    ├── Is this >10 steps or requires isolated exploration? → YES, delegate
    └── Is this <5 steps with context I already have? → NO, do inline
```

---

## Invocation Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| **Context-free invocation** | "Research the auth module" — no scope, no why, no output spec | Add scope (C2), background (C3), and output description (O1+O2) |
| **Ambient context assumption** | Assuming subagent sees conversation history or open files | Explicitly include all relevant prior findings (C5) and file references (C2) |
| **Vague output request** | "Tell me what you find" — subagent guesses what matters | Name the deliverable (O1), specify format (O2), state usage intent |
| **Missing usage intent** | Not telling the subagent what you'll do with its output | Add "I will use your findings to [X]" — changes what the subagent prioritizes |
| **Scope omission** | No directory or file boundaries → searches entire codebase | Always specify paths, modules, or file patterns (C2) |
| **Re-discovery waste** | Not sharing known facts → subagent re-finds them | Include prior knowledge summary (C5) to prevent redundant exploration |
| **Over-delegation** | Simple 3-step tasks don't need subagent isolation | Proceed inline — subagent overhead costs tokens and adds latency |
| **Missing constraints** | Not mentioning project rules → subagent violates conventions | Include relevant conventions (C4): module boundaries, naming, patterns |

---

## Integration with Existing Skills

| Skill | Intersection |
|-------|-------------|
| `ia-stack-ops` | IA stack modifications — handle inline, not via Task delegation |
| `research-methodology` | Embed its caller protocol when delegating research tasks via `general-purpose` |
| `command-execution` | Embed its guard spec when delegating terminal work via `Bash` |
| `design-review` | Load for architecture/design analysis tasks |
| `code-review` | Load for post-implementation code review tasks |
| `debug-hypothesis` | Load for debugging tasks; may trigger research delegation |
| `request-evaluation` | Load for request gap analysis |
| `backend-testing` | Load for pytest-based test tasks |
| `frontend-testing` | Load for Vitest-based test tasks |
