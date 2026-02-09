# Reasoning Timing & Chain Length

Extended reference for Parts 3 and 4 of the reasoning-calibration skill.

---

## Reasoning Timing

WHEN reasoning happens relative to action is the highest-leverage decision for agentic tasks.

### Three Timing Modes

| Mode | When Reasoning Happens | Mechanism | Best For |
|------|----------------------|-----------|----------|
| **Pre-Response** | Before first output | Extended thinking / budget_tokens | One-shot analysis, math, architecture |
| **Inter-Action** | Between tool calls | Think-tool pattern / deliberation | Multi-tool agentic workflows |
| **Post-Action** | After completion | Reflexion / self-evaluation | Iterative improvement, test-fix loops |

### Pre-Response Reasoning

The model reasons internally before producing any output. In Claude, controlled via extended thinking with `budget_tokens`.

**When effective**:
- Single-turn analysis where all information is available upfront
- Mathematical or logical problems with deterministic answers
- Architecture decisions where the model must synthesize before responding

**When ineffective**:
- Multi-tool workflows where later tool results change the reasoning basis
- The model has insufficient context — reasoning on incomplete data amplifies errors
- Simple tasks (T0–T1) — adds latency with negligible quality gain

**Directive pattern**:
```xml
<reasoning_guidance>
Before responding, thoroughly analyze:
1. {What to examine}
2. {What to evaluate}
3. {What to decide}
Then present your conclusion with supporting evidence.
</reasoning_guidance>
```

### Inter-Action Reasoning (Think-Tool Pattern)

The model reasons explicitly BETWEEN actions — after observing tool results and before choosing the next action. Anthropic's think-tool benchmarks show **54% relative improvement** on τ-Bench (0.584 vs 0.332 baseline).

**When effective**:
- Tool results affect which action to take next (branching workflows)
- Policy-heavy environments where constraint compliance must be verified at each step
- Sequential decisions where mistakes compound (file edits, state mutations)

**When ineffective**:
- Predetermined linear tool chains (read → edit → test)
- Simple lookups or data retrieval with no decision between steps

**Directive pattern**:
```markdown
### IMPORTANT
- **Pause and reason** after each tool result, before the next action
- Before each tool call, state:
  1. What the previous result revealed
  2. What constraints apply to the next action
  3. Why this specific next action is the right choice
```

### Post-Action Reasoning (Reflexion)

The model evaluates completed work and decides whether to revise. Based on Shinn et al. (2023) — verbal reinforcement learning through self-reflection.

**When effective**:
- Test-fix cycles where output quality is measurable
- Iterative refinement where each pass improves on the previous
- Code generation where tests provide objective feedback

**Directive pattern**:
```markdown
After completing the task:
1. Evaluate your output against each stated requirement
2. Identify the weakest aspect of your solution
3. If the weakest aspect is below acceptable quality, revise it
4. State what you would do differently with more time
```

### Timing Selection Heuristic

```
Is all information available upfront, with no tool calls needed?
  └── YES → Pre-Response reasoning

Will tool results determine the NEXT action (not just provide data)?
  └── YES → Inter-Action reasoning

Is the output objectively verifiable (tests, linting, metrics)?
  └── YES → Post-Action reasoning (Reflexion)

Multiple apply?
  └── Combine: Pre-Response for planning, Inter-Action for execution,
      Post-Action for validation
```

---

## Chain Length Optimization

Reasoning chains have a sweet spot. Too short → missed steps. Too long → model loses coherence or introduces contradictions.

### Model-Specific Sweet Spots

| Model | Max Effective Hops | Optimal Range | Beyond Max |
|-------|-------------------|---------------|------------|
| **Claude Opus 4** | 7-8 hops | 3-6 steps | Quality degrades gradually |
| **Claude Sonnet 4.5** | 3-4 hops | 2-3 steps | Sharp quality cliff (F6) |
| **Claude Haiku 4.5** | 1-2 hops | 1 step | Unreliable beyond 2 |

**"Hop" definition**: One logical inference step where the conclusion of step N becomes the premise of step N+1. Simple observations or data lookups are NOT hops.

### Decomposition Strategy

When a reasoning chain exceeds the model's sweet spot:

```
Original: 6-hop chain → A → B → C → D → E → F

Decomposed (for Sonnet):
Phase 1 (3 hops): A → B → C → [checkpoint: summarize findings]
Phase 2 (3 hops): [resume from summary] → D → E → F

Each phase stays within the 3-hop sweet spot.
Checkpoint summaries reset the reasoning context.
```

**Directive pattern for decomposition**:
```markdown
### Phase N: {Analysis Segment}
Analyze steps 1-3. After step 3, **summarize your findings in 2-3 sentences**
before proceeding to Phase N+1.
```

### Checkpoint Injection Points

Place reasoning checkpoints at these natural boundaries:

| Boundary | Checkpoint Content |
|----------|-------------------|
| Between analysis dimensions | "Summarize findings so far before analyzing the next dimension" |
| After evidence collection | "What do the collected evidence points converge on?" |
| Before recommendation | "Given the analysis above, restate the key constraints" |
| At methodology midpoint | `<constraint-anchor>` — re-read critical constraints |
