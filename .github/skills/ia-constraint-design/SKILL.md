---
name: ia-constraint-design
description: IA constraint calibration — treats constraints as adjustable cursors on spectrums, not binary switches. Use when designing agent constraints, resolving competing design goals, or reviewing constraint tightness for agent maneuverability.
---

# IA Constraint Design

Principles for designing constraints in agentic systems where over-constraining kills effectiveness and under-constraining causes drift. Constraints are **cursors on spectrums** — their position depends on the agent's role, the task's risk profile, and competing design goals.

---

## When to Use This Skill

- Designing constraints for a new agent or skill
- Reviewing whether existing constraints are too tight or too loose
- Resolving contradictions between two design principles that pull in opposite directions
- Evaluating whether a quality gate exception is warranted
- Calibrating constraint intensity for different agent risk profiles

---

## Core Principle: Constraints Are Cursors

Every constraint occupies a position on a spectrum between two extremes. Neither extreme is universally correct — the right position depends on context.

```
TIGHT                              LOOSE
(safe, predictable, limited)       (flexible, adaptive, risky)
  ├──────────┼──────────┤
             ▲
        cursor position
        (context-dependent)
```

### Common Constraint Spectrums

| Spectrum | Tight End | Loose End | Calibration Factor |
|----------|-----------|-----------|-------------------|
| **Boundary purity** | Strict layer separation, no exceptions | Pragmatic blending for real-world needs | Number of runtimes, maintenance cost |
| **Validation depth** | Full pre-flight analysis before any work | Discover-then-validate during execution | Whether context exists before discovery |
| **Scope rigidity** | Execute exactly what was asked, nothing more | Expand scope when clearly beneficial | Reversibility of the expansion |
| **Output formality** | Strict templates, mandatory sections | Adaptive formatting, depth-scaled output | Audience predictability |
| **Tool restriction** | Minimum viable tool set | Full tool access for flexibility | Agent's blast radius on failure |
| **Autonomy** | Stop and ask at every decision point | Bridge decisions silently, report after | Cost of a wrong autonomous decision |

---

## Methodology

### Phase 1: Identify the Spectrum

When writing or reviewing a constraint, identify which spectrum it sits on.

**Test**: Can you articulate what happens at both extremes?

| Question | If You Can't Answer |
|----------|---------------------|
| What breaks if this is too tight? | You may be constraining without understanding the cost |
| What breaks if this is too loose? | You may be under-constraining without seeing the risk |
| What is the constraint protecting against? | The constraint may be unnecessary — delete it |

### Phase 2: Assess Calibration Factors

Position the cursor based on these factors:

#### Factor 1: Blast Radius

How much damage can the agent cause if the constraint is too loose?

| Blast Radius | Constraint Tendency | Examples |
|-------------|---------------------|----------|
| **Irreversible** | Tight | Data deletion, external API calls, published interfaces |
| **Broad** | Moderate-tight | Multi-file architecture changes, dependency additions |
| **Local** | Moderate-loose | Single-file edits, test additions, documentation |
| **None** | Loose | Read-only analysis, recommendations, reports |

#### Factor 2: Discovery Dependency

Does the agent need to explore before it can validate?

| Discovery Need | Constraint Tendency | Examples |
|---------------|---------------------|----------|
| **Must explore first** | Loose on pre-validation | Test coverage analysis, code review, documentation audit |
| **Context available upfront** | Tight on pre-validation | Plan execution, known-target implementation |

When an agent must discover context before evaluating quality — **validation merges with execution**. Formal pre-flight gates become empty rituals that add latency without adding value.

#### Factor 3: Competing Goals

Are multiple design principles pulling in opposite directions?

If yes → proceed to Phase 3.

### Phase 3: Resolve Competing Goals

When two legitimate design principles contradict, use this resolution framework:

#### Step 1: Name the Tension

State both goals explicitly and why they conflict:

```
Goal A: {principle 1} — wants {X}
Goal B: {principle 2} — wants {Y}
Conflict: X and Y are mutually exclusive because {reason}
```

#### Step 2: Evaluate Priority by Context

Neither goal is universally superior. Assess which matters more **for this specific agent**:

| Question | Favors Goal A | Favors Goal B |
|----------|---------------|---------------|
| Which failure is more costly? | A-failure is worse | B-failure is worse |
| Which has a workaround? | B has alternatives | A has alternatives |
| Which affects more users/agents? | A is broader | B is broader |
| Which aligns with the system's primary mission? | A does | B does |

#### Step 3: Choose a Resolution Strategy

| Strategy | When to Use | Example |
|----------|-------------|---------|
| **Prioritize one, acknowledge the other** | One clearly wins in this context | "Boundary purity wins; dual-runtime gets degraded experience" |
| **Scope-split** | Goals apply to different subsets | "Tight for high-risk agents, loose for read-only agents" |
| **Layered compromise** | Can partially satisfy both | "Compressed methodology in prompts (not full), satisfying both portability and standalone operation" |
| **Explicit exception** | Default to one, carve out documented exceptions | "P2 gate applies except for dual-runtime prompts, documented in the gate" |
| **Defer and revisit** | Insufficient data to decide now | "Document the tension, implement the safer choice, revisit when usage data exists" |

#### Step 4: Document the Decision

Every competing-goals resolution must be documented:

```
Tension: {Goal A} vs {Goal B}
Resolution: {strategy chosen}
Rationale: {why this context favors this resolution}
Revisit trigger: {what would change this decision}
```

This prevents future agents/reviews from re-litigating settled tensions without new information.

---

## Calibration Patterns

### Pattern 1: Risk-Proportional Tightness

Constraint tightness scales with the agent's blast radius, not its competence.

```
Read-only agent     → Loose constraints, high autonomy
Single-file editor  → Moderate constraints
Multi-file editor   → Tight constraints with drift-guard
Irreversible actor  → Strictest constraints, mandatory escalation
```

### Pattern 2: Discovery-First Agents

Agents that must explore before they can act should merge validation with discovery rather than front-loading formal gates.

```
❌ Phase 0: Validate request completeness
   Phase 1: Discover context
   Phase 2: Act

✅ Phase 1: Discover context (validation happens naturally here)
   Phase 2: Act with discovered context
```

Applicable to: test generators, code reviewers, documentation auditors — any agent whose first move is necessarily "look at what's there."

### Pattern 3: Graduated Constraint Intensity

Different constraint levels exist for a reason — use all three:

```
CRITICAL  → Binary, non-negotiable, violation = broken output
            Reserve for: safety, correctness, irreversible actions
            
IMPORTANT → Strong preference, occasional exceptions justified
            Reserve for: quality, consistency, maintainability
            
GUIDELINES → Soft guidance, context-dependent application
             Reserve for: style, optimization, convenience
```

**Common mistake**: Promoting everything to CRITICAL. When everything is critical, nothing is — the agent treats all constraints equally and can't prioritize under pressure.

### Pattern 4: Constraint Budget

An agent has finite "attention budget" for constraints. Each additional CRITICAL constraint competes with others for attention.

**Heuristic**: Aim for ≤5 CRITICAL, ≤7 IMPORTANT, unbounded GUIDELINES. If you exceed this, some constraints are probably IMPORTANT masquerading as CRITICAL — demote them.

---

## Anti-Patterns

- ❌ **Binary thinking** — Treating constraints as "on or off" instead of positions on a spectrum. Results in either over-rigid or under-specified agents.
- ❌ **Constraint maximalism** — Adding every possible rule at CRITICAL level "just in case." Saturates the agent's attention budget and reduces compliance with truly critical rules.
- ❌ **Hidden contradictions** — Two design principles that conflict but are both encoded as constraints without acknowledging the tension. The agent picks one arbitrarily per invocation, causing inconsistent behavior.
- ❌ **Uniform tightness** — Same constraint intensity for high-risk and low-risk agents. A read-only analyzer doesn't need the same validation gates as a multi-file code editor.
- ❌ **Phantom gates** — Formal validation phases that can't actually validate anything because the required context doesn't exist yet. Adds latency without value.
- ❌ **Undocumented exceptions** — Loosening a constraint for practical reasons without recording why. Future reviews either re-tighten it (losing the pragmatic benefit) or can't distinguish intentional exceptions from violations.
- ✅ **Calibrated design** — Tight where failure is costly, loose where exploration is needed, documented where tensions exist. The cursor position is intentional and justified.

---

## Quick Reference

```
DESIGNING A CONSTRAINT:
   1. What spectrum does this sit on?
   2. What's the blast radius if too loose?
   3. Does the agent need to discover before validating?
   4. Are competing goals pulling in opposite directions?
      │
      ├── No conflicts → Position cursor by blast radius + discovery need
      └── Conflicts → Name tension → Evaluate priority → Choose strategy → Document
   │
   5. Is this truly CRITICAL, or masquerading?
   6. Am I within the constraint budget (≤5 CRITICAL)?
```

## End of file — no trailing content