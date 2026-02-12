---
name: engineering-principles
description: Four canonical decision checkpoints: reuse, leverage, standards, cost. Load before implementing or adding dependencies
keywords: [principles, reuse, standards, cost-awareness, decision-checkpoints]
category: development
disable-model-invocation: true
---

# Engineering Principles

Four cross-cutting principles that apply to **every** agent workflow — implementation, planning, testing, review, debugging. Each principle translates into a concrete checkpoint agents execute before proceeding.

---

## When to Use This Skill

- **Before implementing**: Is there an existing solution to reuse?
- **Before adding a dependency**: Can an existing dependency handle this?
- **Before creating a pattern**: Does a standard/convention already exist?
- **Before a long operation**: Is the cost justified?
- **During review**: Do changes violate any principle?

---

## The Four Principles

### P1: Never Reinvent the Wheel

**Rule**: Search before building. Check existing workspace code, project dependencies, and established libraries before writing custom solutions.

**Checkpoint** (execute before creating new code/patterns):

| Step | Question | If YES |
|------|----------|--------|
| 1 | Does workspace already have similar code? | Extend or reuse it |
| 2 | Does an existing project dependency solve this? | Use its API |
| 3 | Is there a well-known library/standard solution? | Evaluate adoption vs custom |
| 4 | All NO? | Proceed with custom — document why |

**Scope by agent type:**
- **Implementing/Testing**: Search sibling modules for patterns before writing
- **Planning**: Include a "reuse analysis" acknowledging existing workspace patterns
- **Reviewing**: Flag custom code that duplicates existing utilities or ignores available libraries
- **IA design**: Apply `agentic-resources` skill — search marketplaces before building custom agents/skills

### P2: Use What You Got

**Rule**: Maximize leverage of existing tools, dependencies, and abstractions before introducing new ones.

**Checkpoint** (execute before adding anything new):

| Decision | Ask | If YES |
|----------|-----|--------|
| New dependency | Can an existing dep cover ≥80% of the need? | Use existing, adapt the gap |
| New abstraction | Can an existing class/module be extended? | Extend, don't duplicate |
| New tool | Does a built-in tool or existing MCP tool handle this? | Use it |
| New command | Is there a `make` target? | Use `make` (per `terminal-usage`) |

**Anti-patterns:**
- Adding a package for a single utility function an existing dep already provides
- Creating a new base class when an existing one accepts extension
- Installing a new CLI tool when an existing project tool covers the use case

### P3: Align with Industry Standards

**Rule**: Follow established conventions (RFCs, PEPs, OWASP, framework docs) when they exist. Deviate only with explicit justification.

**Checkpoint** (execute for architectural/API/security decisions):

| Domain | Standard Source | Key References |
|--------|----------------|----------------|
| Python typing | PEP 484, 585, 604 | `mypy` / `pyright` compliance |
| API design | OpenAPI, REST conventions | HTTP methods, status codes, naming |
| Security | OWASP Top 10 | Input validation, auth patterns |
| Testing | AAA (Arrange-Act-Assert) | Single-behavior tests, fixtures |
| Frontend | Vue 3 Composition API docs | Composable patterns, reactivity |
| Documentation | Diataxis framework | Tutorials, how-to, reference, explanation |

**When to check**: Before finalizing any design decision that touches API shape, security boundaries, typing patterns, or documentation structure.

**Scope by agent type:**
- **Implementing**: Match framework conventions (FastAPI, Vue 3, Pydantic)
- **Testing**: Follow AAA pattern, framework-specific test conventions
- **Reviewing**: Flag deviations from established standards
- **Planning**: Reference applicable standards in the plan

### P4: Cost Awareness

**Rule**: Every operation has a cost. Before long or repetitive operations, ask: "Is there a cheaper path to the same signal?"

**Checkpoint**: Can I batch, filter, scope, or delegate to reduce cost?

| Concern | Skill |
|---------|-------|
| Volume handling (large files, diffs, search results) | `runtime-efficiency` |
| Prompt context design (token budgets, relevance scoping) | `prompt-context-efficiency` |
| Model selection (cheapest viable model) | `model-selection` |

---

## Integration Pattern

Agents reference this skill in their `### IMPORTANT` constraints section:

```
- Apply `engineering-principles` skill checkpoints — P1 (reuse check) before creating new code, P2 (leverage check) before adding dependencies
```

This is a **checkpoint skill**, not a methodology replacement — agents run the relevant check inline at decision points, not as a separate phase.

---

## Anti-Patterns

- ❌ Running all 4 checks for every trivial edit — only invoke at decision points (new code, new dep, design choice, long operation)
- ❌ Blocking on P3 (standards) for cosmetic code — reserve for architectural/API/security decisions
- ❌ Over-optimizing P4 (FinOps) at the cost of thoroughness — efficiency serves quality, not the reverse
- ✅ Quick inline check at natural decision points — lightweight, not ceremonial
