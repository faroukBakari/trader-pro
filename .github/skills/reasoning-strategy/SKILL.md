---
name: reasoning-strategy
description: Cognitive effort calibration. Selects reasoning depth (from direct response to adversarial self-correction) based on task complexity. Use when designing methodology, writing reasoning directives, or calibrating thinking effort for prompts / feedbacks / balancings / evaluations / root cause analysis / high level designs / introspections / self challenges.
---

# Reasoning Strategy

Techniques for calibrating **cognitive effort** in agent-authored prompts and methodologies. Maps task complexity to the appropriate reasoning depth — preventing both over-thinking (wasted tokens on simple tasks) and under-thinking (shallow responses on complex problems).

---

## When to Use This Skill

- Designing a new agent's `<methodology>` section — selecting reasoning depth
- Writing prompts that require structured analysis
- Reviewing an agent that produces shallow or sycophantic responses
- Calibrating effort for different task types within a single agent
- Injecting self-correction into high-stakes decision workflows

---

## The Reasoning Tier Model

Five tiers of cognitive effort, grounded in research on Chain-of-Thought (Wei et al. 2022), Tree-of-Thoughts (Yao et al. 2023), and Anthropic's think-tool benchmarks (2025).

### Tier Overview

| Tier | Name | Effort | When | Token Cost |
|---|---|---|---|---|
| **T0** | Direct | None | Known answers, lookups, simple actions | Baseline |
| **T1** | Linear CoT | Low | Single-domain reasoning, standard implementation | +10-20% |
| **T2** | Structured Decomposition | Medium | Multi-factor decisions, design choices | +30-50% |
| **T3** | Inter-Action Deliberation | High | Multi-step tool workflows, policy-heavy decisions | +40-60% |
| **T4** | Adversarial Self-Correction | Very High | Ambiguous/high-stakes, architectural decisions | +50-80% |

### Selection Decision Table

```
Is the answer already known or easily looked up?
  └── YES → T0 (Direct)

Does it require reasoning but in a single domain?
  └── YES → T1 (Linear CoT)

Does it involve tradeoffs across multiple dimensions?
  └── YES → T2 (Structured Decomposition)

Does it span multiple tool calls where mistakes compound?
  └── YES → T3 (Inter-Action Deliberation)

Is the outcome ambiguous, high-stakes, or prone to bias?
  └── YES → T4 (Adversarial Self-Correction)
```

---

## Tier Patterns

### T0: Direct Response

**Use for**: File reads, known facts, simple transformations, single-tool actions.

No reasoning directive needed. Adding one wastes tokens.

```markdown
<!-- No <reasoning_guidance> section — intentional -->
```

**Anti-pattern**: Adding "think step by step" to `list_dir` or `grep_search` tasks.

---

### T1: Linear Chain-of-Thought

**Use for**: Code implementation, bug fixes, single-domain analysis.

**Evidence**: Wei et al. (2022) — zero-shot CoT improves arithmetic/commonsense/symbolic tasks in 540B+ parameter models. Foundation technique, universally supported.

**Pattern — in agent methodology**:
```markdown
### Phase N: {Task}
Show your reasoning step-by-step before producing the final output:
1. State what you observe
2. Identify the relevant pattern or rule
3. Apply it to produce the result
```

**Pattern — in prompt**:
```xml
<reasoning_guidance>
Think through this step-by-step before answering.
</reasoning_guidance>
```

---

### T2: Structured Decomposition

**Use for**: Design decisions, architecture choices, comparative analysis, planning.

**Evidence**: Yao et al. (2023) — constraining reasoning into named categories prevents shallow, linear paths. Game of 24 accuracy: CoT 4% → ToT 74%. The structure forces exploration of alternatives the model would otherwise skip.

**Pattern — in agent methodology**:
```markdown
### Phase N: Analysis

Before deciding, reason through these perspectives:

1. **First-Principles**: What are the core assumptions? Are any wrong?
2. **Multi-Perspective**: Consider at least 3 viewpoints
   (e.g., technical feasibility, maintenance cost, user impact)
3. **Tradeoff Matrix**: For each option, what do you gain and lose?
4. **Constraints Check**: Does the solution violate any stated constraints?
```

**Pattern — in prompt**:
```xml
<reasoning_style>
1. DECOMPOSE: Break the problem into independent sub-questions.
2. MULTI-PERSPECTIVE: Analyze from at least 3 viewpoints.
3. FIRST-PRINCIPLES: Challenge assumptions before building on them.
4. TRADEOFF MATRIX: Explicitly compare options with gains/losses.
</reasoning_style>
```

**Perspective selection guide** — pick 3 relevant to the domain:

| Domain | Typical Perspectives |
|---|---|
| Architecture | Performance, Maintainability, Complexity, Cost |
| Security | Attack surface, Defense depth, Usability tradeoff |
| API Design | Consistency, Discoverability, Backward compatibility |
| Agent Design | Capability, Cost (FinOps), Boundary compliance |
| Refactoring | Risk, Incremental safety, Behavior preservation |

---

### T3: Inter-Action Deliberation (Think-Tool Pattern)

**Use for**: Multi-tool workflows, policy-heavy environments, sequential decisions where mistakes compound.

**Evidence**: Anthropic think-tool benchmarks (Mar 2025) — 54% relative improvement on τ-Bench airline domain (0.584 vs 0.332 baseline). Outperforms extended thinking on agentic tasks because reasoning happens *between* actions, not just before them.

**Key insight**: Extended thinking reasons before the first response. The think-tool pattern reasons *during* execution — after observing tool results and before choosing the next action. For agents that chain 3+ tool calls, this is the higher-leverage intervention.

**Pattern — in agent methodology**:
```markdown
### IMPORTANT
- **Pause and reason** after receiving tool results, before taking the next action
- Before each tool call, explicitly state:
  1. What you learned from the previous result
  2. What constraints apply to the next action
  3. Why this specific next action is the right choice

### Phase N: {Multi-Step Workflow}
Between each step:
- Verify the previous step's output matches expectations
- Check if the plan needs adjustment based on what you found
- Confirm the next action complies with all stated constraints
```

**Pattern — in agent constraints**:
```markdown
### IMPORTANT
- **STOP and VERIFY** after each tool result before proceeding
- **STATE your reasoning** when choosing between alternative next actions
```

**When NOT to use**: Simple linear tool chains where the sequence is predetermined (e.g., "read file → edit file → run tests"). T3 adds value only when tool results affect the *choice* of next action.

---

### T4: Adversarial Self-Correction

**Use for**: Ambiguous problems, high-stakes decisions, situations prone to confirmation bias or sycophancy.

**Evidence**: 
- LATS (Zhou et al. 2024) — MCTS-guided self-evaluation achieves 92.7% pass@1 on HumanEval.
- Anthropic warns about sycophancy — models tend to agree with the user's premise. Explicit counter-argument directives mitigate this.

**Pattern — in agent methodology**:
```markdown
### Phase N: Decision

1. **Generate**: Produce your initial recommendation with supporting reasoning.
2. **Challenge**: Actively argue against your own conclusion:
   - What evidence contradicts it?
   - What assumption, if wrong, would invalidate it?
   - Who would disagree and why?
3. **Revise**: Incorporate valid challenges into a refined recommendation.
4. **Confidence**: Rate your confidence (high/medium/low) and state remaining uncertainties.
```

**Pattern — in prompt**:
```xml
<reasoning_style>
1. ANALYZE: Reason through the problem step-by-step.
2. COUNTER-ARGUE: Challenge your initial conclusion —
   find the strongest objection.
3. SYNTHESIZE: Reconcile analysis with counter-arguments
   into a final position.
4. CONFIDENCE: State confidence level and remaining unknowns.
</reasoning_style>
```

**Anti-pattern**: Using T4 for every decision. The generate-challenge-revise loop costs ~2x the tokens of a direct answer. Reserve for genuinely ambiguous or high-impact decisions.

---

## Mapping Agent Types to Tiers

| Agent Archetype | Default Tier | Escalate To | Rationale |
|---|---|---|---|
| Research / extraction | T0-T1 | T2 if synthesizing | Mostly retrieval, minimal reasoning |
| Implementation / coding | T1 | T3 if multi-file | Linear reasoning sufficient for code tasks |
| Testing | T1-T2 | T3 for test strategy | Coverage analysis needs structured thinking |
| Code review | T2 | T4 for security review | Multi-perspective analysis is core activity |
| Planning | T2-T3 | T4 for ambiguous scope | Tradeoff analysis + inter-step deliberation |
| Architecture study | T2-T3 | T4 for recommendations | Multi-perspective + adversarial challenge |
| RCA / debugging | T3 | T4 for elusive bugs | Hypothesis-driven needs inter-action reasoning |
| Orchestration / coordination | T2 | T3 for delegation decisions | Structured decomposition of task routing |

### Dynamic Tier Escalation

Within a single agent session, tier can escalate based on signals:

```
Initial attempt failed or produced low-confidence result?
  → Escalate one tier

Multiple contradictory evidence found?
  → Escalate to T4 (adversarial)

User explicitly asks "are you sure?" or "think harder"?
  → Escalate one tier

Task turns out simpler than expected?
  → De-escalate to save tokens
```

---

## Integration Patterns

### For Agent Authors (ia-coord)

When creating or reviewing an agent, select the default reasoning tier:

1. **Identify the agent's primary task type** from the mapping table
2. **Set the default tier** in the agent's methodology section
3. **Add escalation triggers** if the agent handles variable-complexity tasks
4. **Inject the corresponding pattern** from the tier patterns above

### For Prompt Authors

When writing prompts that need reasoning:

1. **Assess task complexity** using the selection decision table
2. **Embed the appropriate pattern** as `<reasoning_style>` or `<reasoning_guidance>`
3. **Avoid over-specifying** — T0/T1 tasks need no reasoning directive

### For Methodology Sections

Embed reasoning at the phase level, not globally:

```markdown
<!-- ✅ GOOD: tier-appropriate per phase -->
### Phase 1: Discovery (T0 — direct)
Search for relevant files.

### Phase 2: Analysis (T2 — structured)
Analyze findings from at least 3 perspectives before recommending.

### Phase 3: Decision (T4 — adversarial)
Challenge your recommendation before presenting it.
```

```markdown
<!-- ❌ BAD: blanket reasoning mandate -->
Always think deeply about everything using multi-perspective analysis
with first-principles breakdown and counter-arguments.
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| **Blanket "think hard"** | Wastes tokens on simple tasks, adds latency | Tier-match: T0 for lookups, T4 for ambiguity |
| **Reasoning without structure** | "Think about it" produces shallow, linear output | Use named categories: perspectives, first-principles, counter-arguments |
| **Over-reasoning on knowns** | Reasoning about well-established facts | Skip to T0 (direct) for known answers |
| **Missing self-correction** | High-stakes decisions without challenge step | Add T4 adversarial loop for critical decisions |
| **Sycophantic agreement** | Accepting user's premise without examination | Add counter-argument directive: "challenge the initial assumption" |
| **Reasoning divorced from action** | Extensive analysis without actionable conclusion | Always end reasoning with a concrete decision or next action |
| **Static tier** | Same reasoning depth for all tasks in an agent | Add escalation/de-escalation triggers |

---

## References

| Source | Key Contribution | Year |
|---|---|---|
| Wei et al. — Chain-of-Thought Prompting | Foundation: intermediate reasoning steps improve complex tasks | 2022 |
| Yao et al. — Tree of Thoughts | Structured exploration: multiple paths + self-evaluation + backtracking | 2023 |
| Zhou et al. — LATS | Unified reasoning + acting + planning via MCTS-guided search | 2024 |
| Hao et al. — RAP | LLM-as-world-model planning: 33% improvement over CoT | 2023 |
| Anthropic — Think Tool | Inter-action reasoning: 54% improvement on policy-heavy agentic tasks | 2025 |
| Anthropic — Extended Thinking | Adaptive effort control for pre-response reasoning | 2025 |
| Anthropic — Building Effective Agents | "Start simple, add complexity only when needed" | 2025 |
