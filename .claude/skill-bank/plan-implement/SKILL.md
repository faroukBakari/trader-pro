---
name: plan-implement
description: Implementation planning before code changes. Load when creating action plans or validating implementation choices
keywords: [planning, implementation, action-plan, features, code-changes]
category: development
disable-model-invocation: true
---

# Implementation Planning

Generate actionable implementation plans for validation before code changes.

## Scope

Applies when:
- Planning a new feature implementation
- Outlining multi-step code changes
- Validating implementation choices before writing code
- Creating executor-ready action plans

## Critical Constraints

CRITICAL:

- DO NOT create, edit, or delete any files — planning only
- DO NOT implement or modify code
- ALWAYS output the plan in conversation and stop

IMPORTANT:

- Search documentation before proposing approaches
- Identify exact file paths, modules, and dependencies
- Verify requirements and compliance for each step

## Execution Protocol

### Phase 1: Query Analysis

Parse the user's request deeply:
- Extract requirements and constraints
- Identify any attached context or references
- Note explicit and implicit acceptance criteria

### Phase 2: Documentation Review

1. Search `docs/DOCUMENTATION-GUIDE.md` for relevant documentation
2. Scan and internalize relevant sections
3. Check `.github/copilot-instructions.md` for immutable rules and patterns

### Phase 3: Codebase Research

1. Search workspace for similar features or patterns
2. Identify exact file paths, modules, and dependencies
3. Note existing conventions to follow

### Phase 4: Gap Analysis

Evaluate documentation against request:
- Identify potential conflicts
- Flag deprecations or outdated patterns
- Note logic gaps or missing requirements

### Phase 5: Refinement Loop

1. **Macro Planning:** Draft high-level step sequence
2. **Feasibility Check:** For each step, verify:
   - Requirements satisfied
   - Compliance with conventions
   - Risk level assessment
3. **Pivot if needed:** If complexity/risk high, revise immediately
4. **Confirm:** Continue until entire sequence is feasible

## Output Format

```markdown
**1- [Step Title]:** `[Risk: Low|Medium|High]`
- [Task description]
    * [Mermaid UML if logic is complex]
    * [Code snippet for illustration only]
    * [Command template if needed]
- [Next task description]

**2- [Step Title]:** `[Risk: Low|Medium|High]`
- [Task description]
```

## Risk Classification

| Level | Criteria | Guidance |
|-------|----------|----------|
| **Low** | Follows existing patterns, minimal dependencies | Proceed with confidence |
| **Medium** | New patterns or moderate dependencies | Document assumptions |
| **High** | Breaking changes, complex integrations | Consider alternatives |

## Plan Execution Model

A plan is a **hypothesis**, not a contract. Benchmark data shows that committing to a full plan and executing it linearly ("the plan tunnel") has poor first-attempt success rates — especially as complexity grows.

### First-Attempt Success Reality (Feb 2026 benchmarks)

| Complexity Tier | Example | pass@1 Odds | Source |
|-----------------|---------|-------------|--------|
| **Simple** (1-3 files, existing patterns, tests exist) | Bug fix, add field, swap implementation | 70-80% | SWE-bench Verified (~72-81%), OSWorld (72.7%) |
| **Multi-step** (4-8 files, new patterns, some unknowns) | New API endpoint + frontend wiring, provider integration | 40-65% | Terminal-Bench 2.0 (65.4%), SWE-bench Pro (~43-56%) |
| **Compound** (8+ files, cross-module, architectural decisions) | New module, multi-system migration, design-heavy feature | 25-40% | CMU office-task study (~26-30%), REAL benchmark (41% ceiling) |

**Key insight**: pass@1 → pass@3 closes a large gap (Verdent AI: 76.1% → 81.2%). Building in one retry per step is cheap insurance.

### The Plan Tunnel Anti-Pattern

```
❌ Plan Tunnel (linear execution):
  Plan Step 1 → Step 2 → Step 3 → ... → Step N → hope it works

✅ Checkpoint-Verify-Iterate:
  Plan Step 1 → verify ✓ → Step 2 → verify ✓ → Step 3 → verify ✗ → adjust → retry → verify ✓ → ...
```

**Why linear fails**: Errors in Step 2 compound silently through Steps 3-N. By Step N, the codebase is in an inconsistent state that's harder to fix than starting over. Interaction depth correlates with success (r=0.87 per arXiv study) — models that verify at each step outperform those that execute plans in one pass.

### Plan Design Rules

When producing a plan, embed these execution properties into every step:

1. **Verification gate** — Each step MUST specify how to verify it worked (test command, type-check, observable behavior). No step without a gate.
2. **Independent commitability** — Each step should leave the codebase in a valid state. If step N+1 fails, step N's work is still usable.
3. **Retry budget** — For Medium/High risk steps, note "retry: 1" in the plan. The executor gets one adjustment attempt before escalating.
4. **Fail-fast ordering** — Riskiest/most uncertain steps go first. If they fail, less work is wasted.

### Complexity-Aware Execution Strategy

| Plan Complexity | Steps | Recommended Execution |
|-----------------|-------|-----------------------|
| **Simple** (≤3 steps, all Low risk) | 1-3 | Single executor pass — checkpoint at end |
| **Medium** (4-6 steps, some Medium risk) | 4-6 | Checkpoint after each step; retry budget = 1 per Medium step |
| **Complex** (7+ steps, any High risk) | 7+ | Decompose into 2-3 independent sub-plans via `problem-decomposition`; checkpoint + verify after each sub-plan |

**Hard rule**: Plans with 7+ steps touching 8+ files MUST be decomposed before execution. The plan tunnel failure rate at this scale (~25-40%) makes linear execution a coin flip.

## Guidelines

- Use Mermaid diagrams for complex logic flows
- Include illustrative code snippets (not implementation)
- Provide command templates where applicable
- Express wordings to clarify design choices
