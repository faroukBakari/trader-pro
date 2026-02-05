---
name: agent-routing
description: Agent delegation and subagent routing heuristics. Use when deciding to delegate, handoff, or spawn subagents for complex tasks.
---

# Agent Routing: Delegation Heuristics

Use this skill to identify when to delegate work to specialist agents instead of handling everything inline. Proactive delegation improves quality and efficiency.

## Agent Catalog

| Agent | Specialty | Best For | Model | Invokable By |
|-------|-----------|----------|-------|--------------|
| `research` | Read-only investigation | Codebase search, web research, context gathering | Sonnet | Subagent only |
| `test` | Test creation & coverage | Writing tests, coverage analysis, test patterns | Sonnet | User, implement |
| `review` | Quality analysis | Code review, security audit, pattern compliance | Opus | User, implement |
| `plan` | Structured planning | Multi-step features, validated implementation plans | Opus | User, study |
| `study` | Architecture decisions | Design tradeoffs, technology selection, refactoring strategies | Opus | User |
| `implement` | Code execution | Writing code, running tests, making changes | Opus | User, plan, study |

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
│  3. Is this a specialized domain?                               │
│     Tests/coverage → `test` agent                               │
│     Security/quality → `review` agent                           │
│     Architecture → `study` agent                                │
│     NO  → Continue inline                                       │
│                                                                 │
│  4. Will output benefit from structured review?                 │
│     YES → Offer `review` handoff after completion               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Trigger Heuristics

### Signal Words → Agent Mapping

| User Request Contains | Likely Best Agent | Action |
|-----------------------|-------------------|--------|
| "research", "find out", "investigate", "what does X do" | `research` | Delegate for context gathering |
| "test", "coverage", "add tests", "spec" | `test` | Delegate for test work |
| "review", "check", "audit", "is this correct" | `review` | Delegate or offer handoff |
| "plan", "design", "how should we", "approach" | `plan` or `study` | Delegate for structured planning |
| "refactor", "improve architecture", "evaluate options" | `study` | Delegate for analysis |
| "implement", "build", "create", "fix" | `implement` | Execute directly or delegate |

### Complexity Triggers

| Situation | Recommended Action |
|-----------|-------------------|
| Multi-file feature implementation | Create `plan` first, then `implement` |
| Unfamiliar codebase area | Use `research` subagent before acting |
| Post-implementation validation | Offer `review` handoff |
| New test suite needed | Delegate to `test` agent |
| Architecture decision required | Use `study` agent for analysis |

## Subagent vs Handoff

| Mechanism | When to Use | User Visibility |
|-----------|-------------|-----------------|
| **Subagent** (`runSubagent`) | Background research, intermediate steps | Low — results flow back silently |
| **Handoff** (manual) | Major phase transitions, user choice needed | High — explicit user action |

### Common Subagent Patterns

```
# Research before implementing
→ runSubagent(research, "Find existing patterns for X in codebase")
→ Use findings to inform implementation

# Coverage analysis before writing tests  
→ runSubagent(test, "Analyze coverage gaps for module Y")
→ Address identified gaps
```

## Anti-Patterns

- ❌ **Over-delegation**: Simple 3-step tasks don't need subagents
- ❌ **Under-delegation**: Attempting complex multi-domain work inline
- ❌ **Redundant research**: Searching for what you already know from context
- ❌ **Skipping review**: Large changes without offering review handoff
- ❌ **Sequential when parallel possible**: Multiple independent research queries should batch

## Integration with Existing Skills

| Skill | Agent Routing Intersection |
|-------|---------------------------|
| `mode-interactive` | Use when agent choice is ambiguous — ask user |
| `plan-implement` | Plan agent produces input for implement agent |
| `design-review` | Study agent uses design-review skill internally |
| `debug-hypothesis` | May trigger research subagent for hypothesis validation |

