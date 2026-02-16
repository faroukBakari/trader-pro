---
name: request-immunity
description: Request immunity patterns and tier selection for user-facing agents. Load when injecting request validation gates
user-invocable: false
---

# Request Immunity

Standard for preventing user-facing agents from acting on inconsistent, incomplete, ambiguous, or misleading requests. Every user-facing agent MUST include a **Phase 0** that validates requests before execution. Validation intensity scales with the agent's exposure to freeform input.

---

## When to Use This Skill

- Creating a user-facing agent that needs request validation
- Selecting the appropriate immunity tier (T1/T2/T3) for an agent
- Injecting Phase 0 validation patterns into an agent's methodology
- Checking RV-1 through RV-4 quality gates on existing agents
- Reviewing whether an agent's request immunity matches its exposure level

---

## Methodology

### Phase 1: Tier Selection

| Agent Characteristic | Tier | Approach | Required Assets |
|---------------------|------|----------|-----------------|
| Handles freeform strategy/design/analysis requests with open scope | **T1: Full** | `request-evaluation` skill (full methodology) → `mode-interactive` for critical gaps | `request-evaluation` + `mode-interactive` skill refs |
| Executes specific tasks but user-invokable with potentially vague input | **T2: Input** | `request-evaluation` skill inline → `mode-interactive` if gaps | `request-evaluation` + `mode-interactive` skill refs |
| Narrow scope, well-defined target, low ambiguity surface | **T3: Scope** | Inline target identification check → ask if target unclear | None — self-contained |

**Decision rules:**
- Primary input is freeform natural language with open scope → **T1**
- Clear action verb but scope/target may be vague → **T2**
- Well-defined narrow scope that just needs a target → **T3**
- When in doubt → choose one tier higher

### Phase 2: Inject Pattern

Select the injection pattern matching the chosen tier.

#### T1: Full Validation

Inject as **Phase 0: Request Validation** in the agent's methodology:

```
1. **Complexity check** — Single clear action with obvious scope?
   - YES → bridge minor assumptions, note them, proceed
   - NO → continue to step 2
2. **Apply `request-evaluation` skill** (full methodology) — Context Decomposition, Deliverable Analysis, Gap Detection, Challenge & Bridge
3. **Process results**:
   - No critical gaps → proceed with bridged assumptions documented
   - Critical gaps → apply `mode-interactive` skill to present gaps as questions
4. **Proceed** with validated, gap-free request
```

Agent constraints: add `request-evaluation` + `mode-interactive` skill references.

#### T2: Input Validation

Inject as **Phase 0: Input Validation** in the agent's methodology:

```
1. **Sufficiency check** — Apply `request-evaluation` skill (Context Decomposition only):
   - Target identifiable? (file, module, feature)
   - Action clear? (what to do)
   - Scope inferable? (how much)
2. **Bridge** — If 1-2 gaps resolvable from project conventions → bridge, note assumptions
3. **Escalate** — If target OR action undetermined → `mode-interactive` with 1-2 focused questions
4. **Proceed** with validated input
```

Agent constraints: add `request-evaluation` + `mode-interactive` skill references.

#### T3: Scope Validation

Inject as **Phase 0: Scope Validation** in the agent's methodology:

```
1. **Target identification** — Can I determine the specific target?
   - Path, module, error context, or plan reference available? → proceed
   - Multiple candidates? → ask: "Which {target type} should I focus on?" (list candidates)
   - No target? → ask: "What would you like me to {action verb}?"
2. **Proceed** with identified target
```

No additional assets required — pattern is self-contained.

### Phase 3: Verify RV Gates

After injection, verify all 4 request immunity gates pass:

| Gate | Check | Fail Condition |
|------|-------|----------------|
| **RV-1** | Phase 0 exists | Methodology doesn't start with request/input/scope validation |
| **RV-2** | Tier appropriate | Validation tier doesn't match agent's freeform input exposure |
| **RV-3** | Assets wired | Required skills (`request-evaluation`, `mode-interactive`) missing from frontmatter/constraints |
| **RV-4** | Escalation path | Agent can't surface unresolvable gaps to user |

---

## Anti-Patterns

- ❌ **Skipping Phase 0** — Agent jumps straight to execution without validating request → wasted work on wrong target
- ❌ **Over-tiering** — T1 validation on a narrow-scope agent → unnecessary overhead, slows simple tasks
- ❌ **Under-tiering** — T3 on an open-scope agent → misses ambiguity, acts on assumptions
- ❌ **Missing asset wiring** — Selecting T1/T2 but not adding skill references → Phase 0 can't execute
- ✅ **Right-sized validation** — Match tier to actual freeform input exposure, wire required assets, verify RV gates
