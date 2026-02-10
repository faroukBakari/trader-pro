---
name: agent-routing
description: Agent delegation, subagent routing heuristics, and invocation quality standards. Use when deciding to delegate, handoff, or spawn subagents — ensures comprehensive context and accurate output descriptions for every subagent invocation.
---

# Agent Routing: Delegation & Invocation Quality

Use this skill to (1) identify when to delegate work to specialist agents, and (2) ensure every subagent invocation carries **comprehensive context** and a **precise output description**. Poor invocations waste tokens and produce unusable results.

---

## Agent & Subagent Catalog

### User-Facing Agents

| Agent | Specialty | Best For | Model |
|-------|-----------|----------|-------|
| `advisor` | Analysis & consultation | Design tradeoffs, code review, architecture, debugging, read-only advice | Opus |
| `builder` | Build orchestration | Plan + implement + test + document lifecycle, feature builds, fixes | Opus |
| `ia-coord` | Agentic design | Create agents/subagents/prompts/skills | Opus |

### Subagents (invoked via `runSubagent`)

| Subagent | Parent(s) | Model | Key Capability |
|----------|-----------|-------|----------------|
| `research` | advisor, builder | Haiku | Codebase search, web fetch, synthesis |
| `command` | advisor, builder | Haiku | Large-output commands, parallel runs, daemon mgmt |
| `verify` | advisor, builder | Haiku | Multi-file verification with pass/fail verdicts |
| `playwright` | advisor, builder | Haiku | Browser automation for UI inspection |
| `implement` | builder | Sonnet | Low-level code execution per task |
| `doc-update` | builder | Sonnet | Documentation updates with gap analysis |

---

## Routing Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│                  SHOULD I DELEGATE?                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Can I handle this directly in <10 steps?                    │
│     YES → Proceed inline                                        │
│     NO  → Consider delegation                                   │
│                                                                 │
│  2. Do I need information I don't have?                         │
│     YES → Delegate to `research` subagent                       │
│     NO  → Continue                                              │
│                                                                 │
│  3. Do I need documentation context?                            │
│     YES → Delegate to `research` subagent (start from           │
│           docs/DOCUMENTATION-GUIDE.md)                          │
│     NO  → Continue                                              │
│                                                                 │
│  4. What kind of work is it?                                    │
│     Analysis/review/design → `advisor` agent                    │
│     Code changes/builds/tests → `builder` agent                 │
│     IA stack artifacts → `ia-coord` mode                        │
│     Complex commands → `command` subagent                       │
│     None of above → Continue inline                             │
│                                                                 │
│  5. Does this need multi-file verification?                     │
│     YES → Spawn `verify` subagent                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Trigger Heuristics

### Signal Words → Agent Mapping

| User Request Contains | Likely Best Agent | Action |
|-----------------------|-------------------|--------|
| "research", "find out", "investigate", "what does X do" | `research` subagent | Delegate for context gathering |
| "review", "check", "audit", "is this correct" | `advisor` | Apply `code-review` skill + spawn `verify` |
| "design", "how should we", "approach", "evaluate" | `advisor` | Apply `design-review` skill |
| "explain", "how does X work", "compare" | `advisor` | Read-only consultation |
| "debug", "why", "root cause" | `advisor` | Apply `debug-hypothesis` skill |
| "build", "implement", "create", "fix" | `builder` | Plan + orchestrate implement |
| "test", "coverage", "add tests", "spec" | `builder` | Apply `backend-testing`/`frontend-testing` skill |
| "plan", "refactor" | `builder` | Dynamic planning + execution |
| "update docs", "document changes" | `builder` | Spawn `doc-update` subagent |
| "fix types", "type error" | `builder` | Implement applies `fix-type-errors` skill |

### Complexity Triggers

| Situation | Recommended Action |
|-----------|-------------------|
| Multi-file feature implementation | `builder` (plans + orchestrates implement subagent) |
| Unfamiliar codebase area | `research` subagent before acting |
| Need doc context | `research` subagent (start from DOCUMENTATION-GUIDE.md) |
| Code quality check needed | `advisor` (apply `code-review` skill + spawn `verify`) |
| Architecture decision required | `advisor` (apply `design-review` skill) |
| Large-output or parallel commands | `command` subagent |
| Type errors failing CI | `builder` (implement applies `fix-type-errors` skill) |

---

## Subagent Delegation

| Mechanism | When to Use | User Visibility |
|-----------|-------------|------------------|
| **Subagent** (`runSubagent`) | Background research, intermediate steps, code execution, verification | Low — results flow back silently |
| **Mode switch** (text suggestion) | Different persona needed (advisor ↔ builder) | High — user switches agent mode |

---

## Subagent Invocation Protocol

**Every subagent invocation MUST satisfy two quality requirements:**

1. **Comprehensive context** — the subagent has everything it needs to work autonomously
2. **Precise output description** — the subagent knows exactly what to return and how

Subagents are **stateless** and **context-isolated**. They cannot see your conversation history, open files, prior tool calls, or any other ambient context. Every piece of information they need must be **explicitly included in the prompt**.

### The Invocation Quality Checklist

Before every `runSubagent` call, verify these 7 elements:

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

## Per-Subagent Invocation Templates

### `research` — Information Gathering

```
Research [specific topic]:
- [Specific question 1]
- [Specific question 2]

Scope: [directories, modules, file patterns to search]
Background: [why this research is needed — 1-3 sentences]
Prior knowledge: [what we already know, so the subagent doesn't re-discover it]

Output: [what findings I need — patterns, file references, architecture overview]
I will use your findings to [implement feature X / decide between approaches / write tests].
```

**Good example**: "Research how WebSocket routes are registered in the broker module. Scope: `backend/src/trading_api/modules/broker/ws/`. Background: We're adding a new WS route for position updates and need to follow the existing pattern. Prior knowledge: We know `WsRouterBase` is the base class (from `backend/src/trading_api/core/`). Output: Step-by-step pattern showing class inheritance, route registration, and service wiring with file:line citations. I will use your findings to implement the new route."

**Bad example**: "Research WebSocket stuff" — No scope, no background, no output spec, no usage intent.

### `command` — Terminal Execution

```
Execute the following command(s):
1. {command or description} [timeout: {N}s] [cwd: {path}]
2. {command or description} [timeout: {N}s] [cwd: {path}]

Background: [why these commands are being run]
Execution: {parallel | sequential | auto}

Output: Execution report with exit codes, duration, and extracted findings.
Extract: {specific patterns — errors, test failures, coverage numbers, build artifacts}
```

---

## Invocation Quality Self-Check

Run this 4-point check **before every `runSubagent` call**:

```
BEFORE INVOKING: {subagent_name}
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
├── 3. RIGHT SUBAGENT?
│   ├── Read-only codebase search → research
│   ├── Documentation guidance → research (start from DOCUMENTATION-GUIDE.md)
│   ├── Complex/large-output terminal commands → command
│   ├── Multi-file checks with verdicts → verify
│   └── Code execution (builder only) → implement
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

| Skill | Agent Routing Intersection |
|-------|---------------------------|
| `mode-interactive` | Use when agent choice is ambiguous — ask user |
| `plan-implement` | Builder uses for implementation planning methodology |
| `design-review` | Advisor applies for architecture/design analysis |
| `code-review` | Advisor applies for post-implementation code review |
| `debug-hypothesis` | Advisor applies; may trigger research subagent |
| `request-evaluation` | Both agents apply for request gap analysis |
| `terminal-usage` | Applied by command subagent — don't re-apply when delegating |
| `backend-testing` | Builder orchestrates; implement applies pytest patterns |
| `frontend-testing` | Builder orchestrates; implement applies Vitest patterns |
