---
name: reasoning-calibration
description: Effective reasoning directive techniques. Load after selecting a reasoning tier to maximize reasoning output quality
keywords: [reasoning-directives, phrasing, verification, chain-length, format]
category: reasoning
disable-model-invocation: true
---

# Reasoning Calibration

Teaches **how to write reasoning directives that produce genuine analytical depth** rather than superficial compliance. Complements `reasoning-strategy` (which selects the tier) by calibrating the directive's language, format, timing, and verification.

**Scope boundary**: This skill covers directive *execution quality*. For tier *selection* (T0–T4), apply `reasoning-strategy`. For model-specific *behavioral guards*, apply `sonnet-prompting` or `haiku-prompting`.

---

## When to Use This Skill

- Writing `<reasoning_guidance>` or `<reasoning_style>` XML sections for a prompt
- Authoring methodology phases that require analytical thinking
- Reviewing an agent that produces shallow "going through the motions" reasoning
- Choosing between structured XML, numbered steps, or freeform reasoning format
- Deciding whether reasoning should happen before, during, or after actions
- Calibrating chain length for a specific model's reasoning capability

---

## Part 1: Directive Language

The words you choose determine whether the model genuinely reasons or merely performs reasoning theater.

### Effective vs Ineffective Wordings

| Effective | Why It Works | Ineffective | Why It Fails |
|-----------|-------------|-------------|-------------|
| "Analyze X by examining Y and Z" | Names specific dimensions | "Think carefully about X" | No structure — produces a paragraph |
| "Before deciding, reason through:" | Explicit sequencing | "Consider this problem" | No action trigger |
| "Compare options A and B on: cost, risk, complexity" | Named criteria | "Weigh the pros and cons" | Model picks easy/shallow criteria |
| "State your conclusion, then argue against it" | Forced adversarial | "Make sure you're right" | Triggers confirmation bias |
| "List 3 assumptions. Which could be wrong?" | Quantified + challenge | "Be thorough" | Unmeasurable — ignored |
| "What evidence would change your answer?" | Falsifiability trigger | "Please reason carefully" | Polite filler — zero signal |

**Evidence**: Kojima et al. (2022) showed that even minimal triggers ("Let's think step by step") improve accuracy from ~17% to ~78% on MultiArith. But structured triggers outperform generic ones — the specificity of the directive correlates with reasoning depth.

### Directive Verb Effectiveness

Verbs that **activate** genuine analytical processing (ranked by reliability):

| Tier | Verbs | Effect |
|------|-------|--------|
| **Strong** | Analyze, Decompose, Compare, Diagnose, Evaluate, Contrast | Force examination of internals/relationships |
| **Medium** | Identify, Assess, Classify, Prioritize, Trace | Guide attention to specific aspects |
| **Weak** | Consider, Think about, Look at, Review, Check | Vague — model chooses minimal path |
| **Avoid** | Try to, You might, Perhaps, Please | Hedging — Sonnet interprets as optional |

**Usage rule**: Lead each reasoning step with a **strong** or **medium** verb. Reserve weak verbs for optional sub-steps only.

### Structure-Forcing Phrases

Phrases that **constrain** reasoning into productive shapes:

```
"For each of the following N dimensions:"     → Forces enumerated multi-perspective
"Present your analysis as:"                    → Forces specific output format
"Before answering, reason through these steps:" → Forces pre-answer analysis
"Rank by [criterion], explaining each ranking:" → Forces ordered comparison
"State your answer. Then list 3 objections:"   → Forces adversarial self-check
```

### Depth-Anchoring Phrases

Phrases that **maintain** reasoning quality through long chains. Place at methodology midpoints or before critical steps:

```
"For each point, provide supporting evidence"           → Evidence requirement
"If any step requires >1 assumption, state them"        → Assumption surfacing
"Express uncertainty where applicable (high/med/low)"   → Calibrated confidence
"State what you DON'T know"                             → Negative knowledge
"What would need to be true for this to be wrong?"      → Falsifiability check
```

---

## Part 2: Reasoning Format Selection

The container shape affects reasoning quality. Different formats activate different analytical modes.

### Format Effectiveness Matrix

| Format | Best For | Compliance | Depth Quality | Token Cost |
|--------|----------|-----------|---------------|-----------|
| **XML tags** (`<reasoning_style>`) | Agent/subagent methodology | ~95% | High — model treats as structured task | Medium |
| **Numbered steps** | Sequential analysis, debugging | ~90% | Medium-High — linear but trackable | Low |
| **Named categories** | Multi-perspective analysis | ~90% | High — forces multiple viewpoints | Medium |
| **Table-based** | Comparison, tradeoff analysis | ~95% | High — forces parallel evaluation | Medium |
| **Freeform** ("think through this") | Creative exploration, brainstorming | ~70% | Low-Medium — model takes shortcuts | Lowest |
| **Nested** (categories + steps) | Complex multi-phase analysis | ~85% | Highest — but diminishing returns past 2 levels | High |

### Format Decision Table

```
Is the reasoning embedded in an agent/subagent methodology?
  └── YES → XML tags (<reasoning_style> or <reasoning_guidance>)

Does the task require comparing alternatives?
  └── YES → Table-based (forces parallel structure)

Does the task require multiple perspectives?
  └── YES → Named categories (forces viewpoint enumeration)

Is the reasoning within a single domain?
  └── YES → Numbered steps (linear, efficient)

Is the goal exploratory/creative?
  └── YES → Freeform (avoid over-constraining)
```

**Key insight**: Structured formats outperform freeform by 20-25 percentage points in reasoning accuracy (Yao et al. 2023 — Game of 24: CoT 4% → ToT 74%). The structure prevents the model from taking the shortest path to an answer.

---

## Part 3: Reasoning Timing

For the three timing modes (Pre-Response, Inter-Action, Post-Action) with directive patterns and selection heuristic, see [timing-and-chains.md](./timing-and-chains.md).

---

## Part 4: Chain Length Optimization

For model-specific sweet spots, decomposition strategies, and checkpoint injection points, see [timing-and-chains.md](./timing-and-chains.md#chain-length-optimization).

---

## Part 5: Self-Verification & Confidence

### Verification that Works vs Verification Theater

| Effective Self-Verification | Verification Theater |
|----------------------------|---------------------|
| "State expected outcome, then compare actual" | "Check your work" |
| "List 3 things that could invalidate this" | "Make sure it's correct" |
| "What evidence contradicts your conclusion?" | "Double-check" |
| "If you're wrong, what's the most likely error?" | "Verify your answer" |

**Why generic verification fails**: Models interpret "check your work" as "restate with more confidence" (confirmation bias). Effective verification requires **specific falsification criteria**.

### Counter-Factual Triggers

Force the model to reason against its own conclusion:

```
"Argue the opposing position for 2-3 sentences before finalizing"
"Under what conditions would the opposite approach be better?"
"What would a skeptical reviewer say about this conclusion?"
"Name the strongest objection to your recommendation"
```

### Confidence Calibration

Get calibrated (not inflated) confidence estimates:

```
"Rate confidence as:
 - HIGH: Strong evidence, no significant unknowns
 - MEDIUM: Reasonable evidence, some assumptions
 - LOW: Limited evidence, significant unknowns
Then state what additional information would raise your confidence."
```

**Anti-pattern**: Asking "how confident are you?" without a scale produces inflated confidence (sycophancy). Always provide a defined scale with criteria.

---

## Part 6: Reasoning Quality Signals

### Shallow CoT Indicators

Signs the model is performing reasoning theater rather than genuine analysis:

| Signal | Example | Indicates |
|--------|---------|-----------|
| Echo — restates the question as analysis | "The problem asks us to..." for 3 sentences | No actual reasoning |
| Single-perspective despite multi-perspective directive | Analyzes only "technical feasibility" when asked for 3 perspectives | Lazy compliance |
| No uncertainty expressed | Every conclusion stated with certainty | Confidence inflation |
| Conclusion predetermined | "Steps" lead inevitably to the obvious answer | Reverse-engineered reasoning |
| Generic observations | "This is an important consideration" | No domain-specific analysis |

### Genuine Reasoning Markers

Signs the model is actually analyzing:

| Signal | Example | Indicates |
|--------|---------|-----------|
| Tension identified | "Factor A supports option 1, but factor B favors option 2" | Real tradeoff analysis |
| Assumption surfaced | "This assumes the API is stateless — if not, the approach changes" | Critical thinking |
| Uncertainty expressed | "I'm less confident about X because..." | Calibrated judgment |
| Counter-evidence cited | "However, the test results suggest the opposite" | Genuine evaluation |
| Novel connection | "This is similar to the pattern in module Y" | Cross-domain synthesis |

---

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| **"Think harder"** | Unstructured — model adds length, not depth | Name specific dimensions to analyze |
| **Vague verification** | "Check your work" → confirmation bias | Specify falsification criteria |
| **Maximum everything** | All directives at every tier → dilution | Match directive intensity to tier |
| **Copy-paste reasoning** | Same `<reasoning_guidance>` everywhere | Calibrate per task type and model |
| **Missing timing choice** | Defaulting to pre-response for agentic tasks | Use inter-action for multi-tool workflows |
| **Exceeding model capacity** | 6-hop chain on Sonnet → quality cliff | Decompose into phases within model sweet spot |
| **Verification without criteria** | "Are you sure?" → sycophantic "yes" | "What evidence contradicts this?" |
| **Polite hedging** | "You might want to consider..." | Direct: "Analyze X by examining Y" |

---

## Quick Reference: Writing a Reasoning Directive

```
1. TIER  → Apply reasoning-strategy to select T0–T4
2. VERB  → Lead with a strong directive verb (Analyze, Decompose, Compare)
3. FORMAT → Select XML/steps/categories/table based on task shape
4. SCOPE → Name 2-4 specific dimensions to reason about
5. DEPTH → Add depth anchors ("state assumptions", "express uncertainty")
6. CHAIN → Keep within model's hop limit; decompose if longer
7. VERIFY → Add falsification-based self-check (not "double-check")
8. TIMING → Pre-response OR inter-action OR post-action
```

---

## References

| Source | Contribution | Year |
|--------|-------------|------|
| Kojima et al. — Zero-Shot Reasoners | "Let's think step by step" trigger effectiveness (+60% accuracy) | 2022 |
| Wei et al. — Chain-of-Thought | Foundation: intermediate steps improve complex reasoning | 2022 |
| Wang et al. — Self-Consistency | Multiple reasoning paths + majority vote improve accuracy 10-20% over single CoT | 2023 |
| Yao et al. — Tree of Thoughts | Structured exploration: CoT 4% → ToT 74% on Game of 24 | 2023 |
| Shinn et al. — Reflexion | Post-action verbal self-reflection as reinforcement learning | 2023 |
| Zhou et al. — LATS | MCTS-guided reasoning achieves 92.7% pass@1 on HumanEval | 2024 |
| Anthropic — Think Tool | Inter-action reasoning: 54% improvement on policy-heavy agentic tasks | 2025 |
| Anthropic — Extended Thinking | Pre-response reasoning with controllable depth via budget_tokens | 2025 |
| Anthropic — Building Effective Agents | "Start simple, add complexity only when needed" | 2025 |
