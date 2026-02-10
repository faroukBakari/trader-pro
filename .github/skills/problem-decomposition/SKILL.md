---
name: problem-decomposition
description: Break complex problems into tractable sub-problems with clear interfaces, dependencies, and validation. Use when a problem has multiple interacting dimensions, compounding uncertainty, or when direct attack exceeds working memory.
---

# Problem Decomposition

Transform complex, multi-dimensional problems into ordered sets of smaller sub-problems that can be solved independently and composed into a complete solution. Addresses the structural question *"how should I cut this problem?"*

**Scope boundary**: This skill covers decomposition — breaking problems into sub-problems with interfaces and dependencies. It does NOT cover request parsing (`request-evaluation`), code change sequencing (`plan-implement`), reasoning depth selection (`reasoning-strategy`), or bug investigation (`debug-hypothesis`).

---

## When to Use This Skill

- A task has **3+ interacting concerns** that can't be reasoned about simultaneously
- Direct attack keeps producing **partial or inconsistent solutions**
- The problem spans **multiple domains, layers, or systems**
- Work needs to be **distributed** across subagents or phases
- You notice yourself **switching between concerns** without making progress on any

---

## Methodology

### Phase 1: Problem Comprehension

**CRITICAL**: Never decompose a problem you don't understand. Premature decomposition produces sub-problems that don't compose back into a solution.

**Steps:**
1. **State the problem** in one sentence (forces precision)
2. **Define the goal state** — what does "solved" look like concretely?
3. **List constraints** — what limits the solution space?
4. **Identify inputs** available and **outputs** required
5. **Count interacting dimensions** — how many concerns interact?

**Decomposition trigger:**

| Signal | Action |
|--------|--------|
| ≤2 dimensions, clear path | Direct attack — no decomposition needed |
| 3-5 dimensions, some interactions | Decompose — this skill applies |
| 6+ dimensions, deep interactions | Decompose, then recursively decompose sub-problems |
| Problem not yet understood | STOP — gather more context first, do not decompose |

### Phase 2: Dimension Selection

Identify the **axes along which the problem can be cut**. Choosing the right dimension is the highest-leverage decision — more important than the sub-problem list itself.

**Dimensions:**

| Dimension | Cut By | Best When | Example |
|-----------|--------|-----------|---------|
| **Functional** | What each part does | Clear separation of concerns | Auth, data layer, UI, notifications |
| **Data-flow** | How data moves | Pipeline or transformation chains | Parse → validate → transform → persist |
| **Temporal** | When things happen | Phased rollouts, migrations | Schema → API → UI → integration tests |
| **Abstraction** | Level of detail | Layered architecture | Interface design → implementation → optimization |
| **Risk** | Uncertainty level | High-unknown problems | Spike unknowns → design with learnings → build |
| **Dependency** | What blocks what | External integration constraints | Foundation → dependent features → integration |

**Selection heuristic:**
```
Which dimension produces sub-problems with the LEAST coupling between them?
  → That is usually the right cut.

If two dimensions produce similar coupling:
  → Prefer the one that enables earlier validation of the riskiest assumption.

ALWAYS consider at least 2 dimensions before choosing.
```

### Phase 3: Decomposition

For each sub-problem, define these five attributes:

1. **Identity** — What is this sub-problem? (one sentence)
2. **Inputs** — What does it need from outside?
3. **Outputs** — What does it produce for others?
4. **Success criteria** — How do you verify it's solved?
5. **Dependencies** — What must be solved first?

**Dependency types:**

| Type | Pattern | Implication |
|------|---------|-------------|
| **Sequential** | A → B → C | B blocks on A; optimize critical path |
| **Parallel** | A ∥ B ∥ C | Independent; concurrent execution possible |
| **Converging** | A,B,C → D | D needs all; identify which are on critical path |
| **Shared resource** | A ⇄ B | Contention risk; may need coordination protocol |

**Granularity stop rule** — stop decomposing when each sub-problem:
- Can be solved in a **single focused session** without further breakdown
- Can be **verified independently** with its own success criteria
- Doesn't need to know the **internal details** of sibling sub-problems
- Further splitting would create **artificial coupling** (the halves need constant coordination)

### Phase 4: Validation

Apply three tests to verify the decomposition is sound:

**Test 1 — Completeness (no gaps):**
> "If I solve ALL sub-problems, does the original problem become fully solved?"
> - Map every aspect of the goal state to at least one sub-problem
> - Gap detected → add a sub-problem or expand an existing one

**Test 2 — Independence (minimal coupling):**
> "Can each sub-problem be solved knowing only its inputs and outputs — not the internals of siblings?"
> - For each pair, count shared assumptions beyond the defined interfaces
> - More than 2 shared assumptions → coupling too tight → re-cut or merge

**Test 3 — Reassembly (solutions compose):**
> "When I combine the sub-problem solutions, do they integrate without rework?"
> - Trace outputs of each sub-problem to inputs of its dependents
> - Mismatched interfaces → specify interface contracts now, before solving

**If any test fails:**

| Failure | Common Fix |
|---------|-----------|
| Completeness | Add missing sub-problem or expand existing one |
| Independence | Wrong dimension — re-cut along a different axis |
| Reassembly | Missing interface spec — define contracts between sub-problems |

---

## Decomposition Patterns

Reusable structures for common problem shapes:

| Pattern | Problem Shape | Sub-Problem Structure |
|---------|--------------|----------------------|
| **Pipeline** | Input → transformations → output | Stage 1 → Stage 2 → ... → Stage N |
| **Layer cake** | Multiple abstraction levels | Interface → Logic → Data → Infrastructure |
| **Feature fan** | Multiple independent capabilities | Feature A ∥ Feature B ∥ Feature C → Integration |
| **Spike-then-build** | High uncertainty | Spike unknowns → Design → Build → Verify |
| **Strangler** | Replace existing system | Adapter → New impl → Traffic shift → Retire old |
| **Contract-first** | Multi-agent / multi-team | Define interfaces → Implement in parallel → Integration test |

---

## Heuristics

1. **One-sentence test**: If you can't describe a sub-problem in one sentence, it's still too complex — decompose further
2. **3±1 rule**: Aim for 3-5 sub-problems per level. Fewer = under-decomposition; more = over-decomposition or wrong dimension
3. **Interface weight**: Count data items flowing between sub-problems. If total interface items > sub-problems × 2, coupling is too high
4. **Riskiest first**: Order execution so the most uncertain sub-problem is tackled first — fail fast on unknowns
5. **Symmetry suspicion**: If all sub-problems are roughly equal size, verify you're not forcing artificial symmetry — real problems are usually asymmetric
6. **Two-level maximum**: Don't decompose more than 2 levels deep before validating the top level. Premature depth wastes effort if the top-level cut was wrong

---

## Anti-Patterns

- ❌ **Listing aspects, not sub-problems** — "Consider performance, security, scalability" is analysis, not decomposition. Each sub-problem must be *solvable* and *verifiable*.
- ❌ **Decomposing before understanding** — Cutting a problem you don't fully grasp produces sub-problems that don't reassemble. Phase 1 is not optional.
- ❌ **First-dimension bias** — The first decomposition axis that comes to mind is often wrong. Always evaluate at least 2 dimensions before choosing.
- ❌ **Missing interfaces** — Sub-problems defined by what they *do* but not what they *exchange*. Every boundary needs an explicit input/output contract.
- ❌ **Infinite recursion** — Decomposing 3 into 9 into 27. Apply the granularity stop rule; two levels max without validation.
- ✅ **Dimension-first thinking** — Choose the cutting axis before listing sub-problems. The axis determines quality; the list follows naturally.

---

## Output Format

```markdown
## Problem Decomposition

### Problem Statement
{One-sentence problem description}

### Goal State
{What "solved" looks like concretely}

### Dimension Chosen
{Which axis and why} (alternatives considered: {list})

### Sub-Problems

| # | Sub-Problem | Inputs | Outputs | Depends On | Success Criteria |
|---|-------------|--------|---------|------------|------------------|
| 1 | {name} | {data needed} | {data produced} | — | {how to verify} |
| 2 | {name} | {data needed} | {data produced} | #1 | {how to verify} |
| 3 | {name} | {data needed} | {data produced} | #1 | {how to verify} |
| 4 | {name} | {data needed} | {data produced} | #2, #3 | {how to verify} |

### Execution Order
- Phase 1: #1 (foundation)
- Phase 2: #2 ∥ #3 (parallel — both depend on #1)
- Phase 3: #4 (integration)

### Validation
- Completeness: ✅/❌ {notes}
- Independence: ✅/❌ {notes}
- Reassembly: ✅/❌ {notes}
```
