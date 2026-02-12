# Tier Patterns

Detailed patterns for each reasoning tier (T0–T4). Summarized in the main skill's Tier Overview table — this file provides the full directive patterns with code blocks and examples.

---

## T0: Direct Response

**Use for**: File reads, known facts, simple transformations, single-tool actions.

No reasoning directive needed. Adding one wastes tokens.

```markdown
<!-- No <reasoning_guidance> section — intentional -->
```

**Anti-pattern**: Adding "think step by step" to `list_dir` or `grep_search` tasks.

---

## T1: Linear Chain-of-Thought

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

## T2: Structured Decomposition

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

## T3: Inter-Action Deliberation (Think-Tool Pattern)

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

## T4: Adversarial Self-Correction

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
