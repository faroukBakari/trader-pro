---
name: reasoning-strategy
description: Cognitive effort calibration across reasoning depths. Load when designing methodology or calibrating thinking effort
keywords: [cognitive-effort, reasoning-depth, complexity, calibration, tiers, framing-bias, debiasing]
category: reasoning
disable-model-invocation: true
---

# Reasoning Strategy

Techniques for calibrating **cognitive effort** in agent-authored prompts and methodologies. Maps task complexity to the appropriate reasoning depth — preventing both over-thinking (wasted tokens on simple tasks) and under-thinking (shallow responses on complex problems).

**Scope boundary**: This skill covers tier *selection* (which level of reasoning effort). For directive *execution quality* (phrasing, format, timing, chain length), apply `reasoning-calibration`. For model-specific *behavioral guards*, apply `sonnet-prompting` or `haiku-prompting`.

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

For detailed patterns with directive code blocks for each tier (T0–T4), see [tier-patterns.md](./tier-patterns.md).

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

## Framing Bias on Complexity Assessment

User prompt framing systematically biases the tier classification. The model's internal complexity heuristic operates **before** structured reasoning, making it vulnerable to anchoring.

### The Classification Mechanism

Three layers interact to produce a biased tier assignment:

| Layer | Mechanism | Evidence |
|---|---|---|
| **1. Adaptive thinking heuristic** | Model evaluates query complexity from prompt text to decide thinking depth. Casual framing → low complexity → minimal reasoning allocated | Anthropic docs: "Claude calibrates thinking based on effort parameter and **query complexity**" |
| **2. Anchoring bias** | Framing words set a complexity ceiling before any analysis. "Typo" anchors low even if the actual task is complex | Science Advances (2025): LLMs influenced by meta-information; ScienceDirect RCT: anchoring confirmed across Claude/GPT-4/Gemini |
| **3. Sycophancy alignment** | Model adopts the user's implicit assessment of task difficulty via RLHF preference dynamics | Anthropic sycophancy research: responses matching user views are preferred during training |

### Framing Words and Their Tier Bias

| Framing | Typical Bias | Actual Tier May Be |
|---|---|---|
| "typo", "quick fix", "minor", "small" | T0 (Direct) | T1–T2 (type errors, cross-file fixes) |
| "fix", "update", "change" | T0–T1 | T2–T3 (multi-step debugging) |
| "refactor", "implement", "redesign" | T2–T3 | Correctly assessed |
| "investigate", "diagnose", "audit" | T2–T3 | Correctly assessed |

**Key insight**: Framing bias is **asymmetric** — minimizing words cause under-classification more often than maximizing words cause over-classification. The model's default is to take the user's framing at face value.

### Debiasing: Classify by Domain, Not Framing

When assessing task complexity for tier selection:

1. **Ignore the user's complexity framing** — words like "just", "quick", "simple" are user expectations, not task properties
2. **Classify by action domain**: What does the task actually require?
   - Involves type system, linting, or static analysis → T1+ (not T0)
   - Requires reading diagnostics output → T1+ (not T0)
   - Spans multiple files or modules → T2+
   - Requires reasoning about interactions or side effects → T3+
3. **Classify by verification needs**: What's required to confirm completion?
   - If verification requires running tools (linters, tests, builds) → T1+
   - If verification spans system boundaries → T2+

### Complexity Assessment Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| **Trusting user framing** | "Fix this typo" → T0, skipping process gates | Classify by domain and verification needs, not user words |
| **Anchoring on task size** | Small file change → low tier | A one-line type fix can require T2 reasoning about type narrowing |
| **Skipping conditional gates** | "Non-trivial" qualifier + casual framing → gate bypassed | Use unconditional gates with fast exit (see `prompting-guide`) |
| **Static tier from initial assessment** | First impression sticks even after discovering complexity | Re-evaluate tier after first tool result reveals actual scope |

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
