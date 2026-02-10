---
name: implementation-reasoning
description: Reasoning guardrails for implementation agents — prevents design-spiral, enforces materialization checkpoints, and steers thinking toward actionable coding steps. Use when planning implementation, entering complex reasoning chains, or detecting reasoning drift away from concrete code changes.
---

# Implementation Reasoning

Guardrails that keep implementation-focused agents reasoning about **practical coding concerns** instead of spiraling into **architectural design exploration**. Provides pre-reasoning gates, materialization checkpoints, and anti-spiral protocols.

**Core principle**: An implementation agent reasons to decide *how to change code* — not *what the right design is*. If the design isn't settled, the agent lacks a prerequisite and should escalate, not self-solve.

---

## When to Use This Skill

- Before entering a planning or analysis phase in a build workflow
- When a reasoning chain exceeds 3 deliberation steps on the same decision
- When reasoning starts branching into "what if" scenarios about architecture
- When you notice yourself weighing design alternatives rather than sequencing code changes
- As a continuous background check during Phase 1 (Discovery) and Phase 2 (Planning)

---

## Methodology

### Phase 1: Pre-Reasoning Gate (Before Thinking)

Before entering any extended reasoning, answer these **3 materialization questions**:

```
1. What file(s) will I change?     → Must name concrete paths
2. What function/class is affected? → Must name specific symbols
3. What does "done" look like?      → Must describe observable outcome (test passes, type checks, behavior change)
```

**Decision:**

| Result | Action |
|--------|--------|
| All 3 answered concretely | Proceed — reasoning is grounded |
| 1-2 answers are "TBD" or vague | Investigate (search/read) to ground them — max 4 tool calls |
| All 3 are abstract ("refactor the service layer", "fix the mapping") | **STOP** — prerequisite missing. Escalate: the solution design is insufficiently specified |

### Phase 2: Reasoning Boundary Patrol (During Thinking)

Apply these **5 tripwires** continuously during reasoning. If any triggers, execute the prescribed action immediately.

#### Tripwire 1: Design Alternative Detection

**Signal**: You're comparing 2+ architectural approaches ("should enrichment happen before or after conversion?", "should I add a method to X or Y?")

**Action**: STOP. This is a design question. Summarize the alternatives in 2-3 sentences and escalate to advisor. Do not pick one.

**Template**:
```
⚠️ DESIGN QUESTION DETECTED — not in my scope.

Alternatives identified:
- Option A: [brief]
- Option B: [brief]

Trade-off axis: [what makes this hard to decide]

→ Recommend switching to advisor to resolve this design choice before proceeding.
```

#### Tripwire 2: Speculative Branching

**Signal**: Reasoning contains "what if...", "after reconnection...", "in the case where...", "edge case when..." creating hypothetical scenarios beyond the immediate scope.

**Action**: Tag the branch as "out of scope for this implementation pass" and continue with the mainline case. Note the edge case for the advisor to evaluate.

**Rule**: An implementation plan covers the **primary path**. Edge cases and failure modes are design concerns unless explicitly scoped in.

#### Tripwire 3: Unbounded Root Cause Exploration

**Signal**: You've identified the proximate cause but keep digging into underlying causes ("the real issue is...", "but this is caused by...", "which stems from...").

**Action**: After identifying **one clear root cause**, STOP exploring deeper. If the fix for that cause is clear → plan the fix. If not → the root cause analysis needs advisor-level investigation.

**Budget**: Max 2 cause-depth levels. Beyond that = investigation scope.

#### Tripwire 4: Materialization Failure

**Signal**: After 4+ reasoning steps, you still can't name *specific files and functions* to change.

**Action**: The problem is insufficiently understood for implementation. Produce what you know as a structured handoff:

```
📋 IMPLEMENTATION BLOCKED — insufficient specification

What I know:
- [concrete findings so far]

What I need to start coding:
- [specific missing information]

→ Switch to advisor to complete the solution specification.
```

#### Tripwire 5: Scope Expansion

**Signal**: Your reasoning is adding tasks beyond the original scope ("I should also fix...", "while I'm here...", "this also affects...").

**Action**: Note the expansion in a "follow-up" list. Do NOT fold it into the current plan. Apply drift-guard if the expansion is significant.

### Phase 3: Reasoning Shape Enforcement (How to Think)

When implementation reasoning IS warranted, enforce this shape:

#### The "File → Function → Diff" Funnel

```
Level 1: Which files? (paths)
  └─ Level 2: Which functions/classes in those files? (symbols)
       └─ Level 3: What changes to those symbols? (pseudo-diff)
            └─ Level 4: What tests verify the changes? (test names)
```

Each level MUST complete before the next begins. Do not jump to Level 3 (designing the change) without Level 1-2 (grounding where it happens).

#### Reasoning Verb Filter

Use these verbs in implementation reasoning:

| ✅ Implementation verbs | ❌ Design verbs (escalation signals) |
|--------------------------|--------------------------------------|
| Modify, Add, Remove, Rename | Evaluate, Compare, Weigh, Assess |
| Call, Import, Inject, Wire | Should, Could, Might, Perhaps |
| Test, Assert, Mock, Stub | Consider, Explore, Investigate |
| Extract, Inline, Move | Architect, Design, Restructure |

If your reasoning is dominated by ❌ verbs → you're doing design work, not implementation planning.

#### Incremental Step Sizing

Each planned step must be:
- **Implementable** in a single subagent invocation (1-3 files)
- **Verifiable** with a concrete check (test, type-check, grep)
- **Independent** enough to commit if subsequent steps fail

If a step can't meet all three → decompose further or escalate the design complexity.

### Phase 4: Convergence Protocol

| Checkpoint | Threshold | Action |
|------------|-----------|--------|
| **Soft gate** | 3 reasoning steps without a concrete file/function reference | Ground: search codebase for evidence |
| **Medium gate** | 5 reasoning steps total on same topic | Produce intermediate plan draft as-is with gaps marked |
| **Hard gate** | 8 reasoning steps total on same topic | STOP reasoning. Output: what's decided + what's blocked + recommended next step |

---

## Templates

### Implementation-Ready Reasoning Template

```
SCOPE: [1-sentence description of the change]

FILES:
- [path/to/file1.py] → modify [FunctionName]: [what changes]
- [path/to/file2.py] → add [NewFunction]: [what it does]

DEPENDENCIES: [what must be true before this works]

VERIFICATION:
- [ ] Test: [test_name] passes
- [ ] Type check: clean
- [ ] Behavior: [observable outcome]

BLOCKED BY: [nothing / list specific missing info]
```

### Design Escalation Template

```
⚠️ DESIGN DECISION NEEDED — escalating to advisor

Context: [what I was trying to plan]

Decision needed: [the specific design question]
  - Option A: [brief + known pro/con]
  - Option B: [brief + known pro/con]

Impact on implementation: [what changes depending on the answer]

My coding concerns: [practical constraints I've noticed — e.g., "Option A requires modifying a
  generated file", "Option B adds a new dependency"]
```

---

## Anti-Patterns

| Anti-Pattern | Signal | Fix |
|--------------|--------|-----|
| **Design masquerading as planning** | "The architecture should..." | Tripwire 1 — escalate design questions |
| **Infinite root cause chaining** | "But the real problem is..." | Tripwire 3 — max 2 cause levels |
| **Speculative edge case spiraling** | "What about reconnection..." | Tripwire 2 — note and continue mainline |
| **Abstract planning** | Steps with no file paths | Phase 1 gate — all 3 materialization Qs required |
| **Boiling the ocean** | 10+ step plans touching 8+ files | Incremental sizing — cap at 1-3 files per step |
| **Reasoning without acting** | Extended thinking with no tool calls | Convergence Protocol — hard gate at 8 steps |

---

## References

| Source | Key Contribution |
|--------|------------------|
| Wei et al. (2022) — Chain-of-Thought | Structured intermediate steps improve complex task accuracy |
| Yao et al. (2023) — Tree of Thoughts | Structured exploration + self-evaluation + backtracking |
| Anthropic (2025) — Building Effective Agents | "Ground truth from environment at each step"; stopping conditions |
| Anthropic (2025) — Think Tool | Inter-action reasoning: 54% improvement on policy-heavy tasks |
| Kojima et al. (2022) — Zero-shot CoT | Minimal triggers improve accuracy; specificity correlates with depth |
