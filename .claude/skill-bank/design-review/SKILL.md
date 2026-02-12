---
name: design-review
description: Solution selection and adversarial validation. Load when proposing solutions or evaluating architecture decisions
keywords: [design-review, adversarial, solution-selection, trade-offs]
category: review
disable-model-invocation: true
---

# Design Review

Two-phase design validation: **select** the right approach, then **stress-test** the proposal.

---

## Phase 1: Solution Selection

Before proposing new solutions, validate against existing assets.

```
┌─────────────────────────────────────────────────────────────┐
│  Can existing code be extended/configured?                  │
│     YES → Propose extension, skip new implementation        │
│     NO  ↓                                                   │
│                                                             │
│  Does a project-approved library solve this?                │
│     YES → Use it, document integration approach             │
│     NO  ↓                                                   │
│                                                             │
│  Is there a well-maintained OSS solution?                   │
│     YES → Evaluate: adoption cost vs build cost             │
│     NO  ↓                                                   │
│                                                             │
│  Custom implementation justified?                           │
│     → Document why alternatives were rejected               │
└─────────────────────────────────────────────────────────────┘
```

### Portability Checklist (for external dependencies)

| Concern | Question | Required Output |
|---------|----------|-----------------|
| **Abstraction** | Can we swap the underlying provider? | Interface/adapter pattern |
| **Data** | Can we export/migrate data if we switch? | Migration path |
| **Stability** | Is this a stable, well-maintained project? | Maintenance status |

### Cost-Benefit Sanity Check

- **Effort vs Value**: Is the solution proportionate to the problem?
- **Opportunity Cost**: What else could this time be spent on?
- **Maintenance Burden**: What's the ongoing cost of this solution?

---

## Phase 2: Stress Test

Before finalizing, **argue against** your proposal. Genuine adversarial thinking, not a checkbox exercise.

### Severity Classification

| Level | Definition | Response |
|-------|------------|----------|
| **Critical** | Blocking, breaking, or security risk | Mention prominently |
| **Tech debt** | Accumulating risk, worth tracking | Note in tradeoffs |
| **Style** | Low impact preference | Mention only if asked |

IMPORTANT: Flag issues only when relevant to the user's question — avoid unsolicited critiques.

### Concern Checklist

Challenge your solution against these 6 concerns:

#### 1. Architectural Drift

**Challenge:** Does this fit where the codebase is heading, or does it fight the grain?

| Detection Signal | Response |
|------------------|----------|
| Module X imports from module Y's internals; bypassed abstractions | Note deviation, assess if intentional or erosion |
| Same problem solved 3+ different ways across codebase | Identify the canonical pattern, flag divergences |
| Naming, file structure, or API style doesn't match established patterns | Reference project conventions, suggest alignment |

#### 2. Abstraction Errors

**Challenge:** Is this the right abstraction level? What might leak?

| Anti-Pattern | Symptom | Guidance |
|--------------|---------|----------|
| **Leaky abstraction** | Implementation details exposed in interface | Suggest encapsulation boundaries |
| **Wrong abstraction** | Forced inheritance, awkward generics | Recommend composition or simpler design |
| **Premature abstraction** | Generic solution for single use case | Advise "rule of three" before abstracting |

#### 3. Coupling Creep

**Challenge:** What new dependencies does this introduce? Will they hurt later?

| Signal | Guidance |
|--------|----------|
| Module A knows too much about Module B's internals | Identify dependency direction, suggest inversion |
| Circular or bidirectional dependencies | Break cycle with interface/event pattern |

#### 4. API Surface Issues

**Challenge:** Would a new team member understand this interface? Is naming consistent?

Surface problems to flag:
- Inconsistent naming (`getUserById` vs `fetch_user` vs `user.get`)
- Mixed paradigms (callbacks + promises + async/await)
- Leaking internal types in public interfaces
- Missing or inconsistent error responses
- Versioning gaps or breaking changes without migration path

#### 5. Over/Under-Engineering

**Challenge:** Is the solution complexity proportionate to the problem?

IMPORTANT: Calibrate feedback to problem scope — avoid applying enterprise patterns to scripts or MVP shortcuts to production systems.

**Over-engineering signals:**
- Abstractions with single implementation
- Configuration for scenarios that don't exist
- "Flexibility" that adds complexity without clear benefit
- Multiple indirection layers for simple operations

**Under-engineering signals:**
- Copy-paste instead of parameterization
- Hard-coded values that should be configurable
- Missing error handling for likely failure modes
- No consideration for scale/growth in critical paths

#### 6. Pattern Violations

**Challenge:** What existing conventions does this break? Is breaking them justified?

---

## Assessment Actions

For each relevant concern:

| Risk Level | Action |
|------------|--------|
| No risk identified | Briefly note why in thinking |
| Risk exists with mitigation | Document the mitigation |
| Accepted tradeoff | Document explicitly in output |
| **Serious flaw revealed** | **REVISE SOLUTION before proceeding** |

## Scaling by Complexity

| Complexity | Requirement |
|------------|-------------|
| Simple | Use judgment — skip if concerns clearly don't apply |
| Moderate | Mandatory — document even if all clear |
| Complex | Mandatory — full table with explicit assessments |

## Output Format

```markdown
### Accepted Tradeoffs

- **[Concern]**: [Why acceptable. Mitigation if any. Known limitations.]

_If no tradeoffs: "None — solution aligns with all design concerns evaluated."_
```

## Anti-Patterns

- ❌ Adding new library without checking existing patterns
- ❌ Custom implementation when mature OSS exists
- ❌ External dependency without exit strategy
- ❌ Over-engineering simple problems
- ❌ Jumping to implementation without stress-testing
