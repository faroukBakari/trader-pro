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

| Effective | Ineffective | Why |
|-----------|-------------|-----|
| "Analyze X by examining Y and Z" | "Think carefully about X" | Names dimensions vs no structure |
| "Before deciding, reason through:" | "Consider this problem" | Explicit sequencing vs no trigger |
| "Compare A and B on: cost, risk, complexity" | "Weigh the pros and cons" | Named criteria vs shallow defaults |
| "State conclusion, then argue against it" | "Make sure you're right" | Forced adversarial vs confirmation bias |
| "List 3 assumptions. Which could be wrong?" | "Be thorough" | Quantified + challenge vs unmeasurable |
| "What evidence would change your answer?" | "Please reason carefully" | Falsifiability vs polite filler |

**Evidence**: Kojima et al. (2022) — "Let's think step by step" improved accuracy ~17%→~78% on MultiArith. Structured triggers outperform generic.

### Directive Verb Effectiveness

| Tier | Verbs | Effect |
|------|-------|--------|
| **Strong** | Analyze, Decompose, Compare, Diagnose, Evaluate, Contrast | Force examination of internals/relationships |
| **Medium** | Identify, Assess, Classify, Prioritize, Trace | Guide attention to specifics |
| **Weak** | Consider, Think about, Look at, Review, Check | Vague — minimal path |
| **Avoid** | Try to, You might, Perhaps, Please | Hedging — interpreted as optional |

**Rule**: Lead with strong/medium verbs. Reserve weak verbs for optional sub-steps only.

### Structure-Forcing & Depth-Anchoring Phrases

**Constraint patterns** (shape reasoning):
```
"For each N dimensions:" | "Present as:" | "Before answering, reason through:" | "Rank by X, explaining:" | "State answer. Then list 3 objections:"
```

**Depth anchors** (maintain quality through chains):
```
"Provide supporting evidence" | "State assumptions" | "Express uncertainty (high/med/low)" | "State what you DON'T know" | "What makes this wrong?"
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

### Reasoning Quality Signals

**Shallow CoT (theater)**:
- Echo (restates question for 3 sentences) | Single-perspective despite multi-perspective directive | No uncertainty | Predetermined conclusion | Generic observations

**Genuine reasoning**:
- Tension identified ("A supports X, but B favors Y") | Assumptions surfaced ("assumes stateless — changes if not") | Uncertainty expressed ("less confident on X because...") | Counter-evidence cited | Novel connections

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
| **Structured CoT in JSON** | Forcing reasoning into JSON schema increases parsing brittleness, prompt injection surface, and constrains natural token flow without improving quality (Yoav Goldberg) | Use structured output for RESULTS, not REASONING. Let the model reason freely, then format the output. |

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
