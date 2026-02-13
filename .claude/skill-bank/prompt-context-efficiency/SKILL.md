---
name: prompt-context-efficiency
description: Prompt-level context design and token budget allocation. Load when structuring prompts for token efficiency or scoping context windows
keywords: [context-management, token-budget, prompt-design, relevance-scoping]
category: prompting
disable-model-invocation: true
---

# Context Efficiency — Prompt Design Patterns

Token budget management and context-aware prompt design — applies when authoring prompts that must manage what to include, exclude, and how to structure input for maximum signal per token.

**Scope boundary**: This skill covers *prompt-level context design* — how to structure prompts and context windows for token efficiency. For *runtime* volume handling (large files, convergence gates, batching), apply `runtime-efficiency`. For prompt *structure* patterns (XML sections, guards), apply `prompting-guide`. For prompt *file* mechanics (.prompt.md format), apply `prompt-file-design`.

---

## The Context Budget Mindset

Think of context window as a **budget**, not a limit:

| Context Type | Token Cost | Signal Value | Strategy |
|--------------|------------|--------------|----------|
| System prompt | Fixed | High | Invest here — drives all outputs |
| User query | Low | Critical | Always include fully |
| Reference code | Variable | Medium-High | Filter to relevant sections |
| Logs/output | High | Often Low | Aggressive filtering |
| Search results | High | Variable | Dedupe, rank, truncate |
| Tool schemas | Medium | Low per-call | Load on-demand |

**Golden rule:** Every token should earn its place.

---

## Pattern 1: Progressive Disclosure

Structure prompts to fetch detail incrementally rather than front-loading everything:

```xml
<context_strategy>
PHASE 1 — Orientation (minimal context):
- Provide file structure / function signatures only
- Ask: "Which areas need deeper investigation?"

PHASE 2 — Targeted deep-dive:
- Fetch only the identified relevant sections

PHASE 3 — Synthesis:
- Work with focused, relevant context only
</context_strategy>
```

Use this pattern when designing prompts for agents that will explore codebases, analyze logs, or process multi-file inputs.

---

## Pattern 2: Relevance Boundaries

Explicitly scope what context matters in your prompt:

```xml
<relevance_scope>
INCLUDE:
- Files in `src/modules/{module_name}/`
- Error messages containing "{pattern}"

EXCLUDE:
- Test files (unless debugging tests)
- Generated code in `*_generated/`
- Unrelated modules
</relevance_scope>
```

This prevents agents from wasting tokens on irrelevant context. Narrower scope = higher signal density.

---

## Pattern 3: System Prompt Budget Allocation

When designing system prompts for agents or skills, allocate token budget intentionally:

| Section | Budget Target | Rationale |
|---------|---------------|-----------|
| Role + constraints | 10-15% | High-signal framing, always relevant |
| Domain rules | 20-30% | Task-specific guidance the model needs |
| Examples | 15-25% | Highest per-token value for output quality |
| Reference tables | 10-20% | Structured lookup, high density |
| Anti-patterns | 5-10% | Guardrails, diminishing returns past ~5 items |
| Boilerplate/verbose prose | 0% | Replace with tables or terse rules |

**Key insight**: System prompt tokens are paid on every turn. A 2000-token system prompt in a 20-turn conversation costs 40k tokens — equivalent to reading 10 full files. Invest wisely.

---

## Pattern 4: Output Token Management

Design prompts that control output verbosity:

```xml
<output_efficiency>
RESPONSE SIZING:
- Simple questions → 1-3 sentences
- Code changes → diff-style or minimal replacement
- Analysis → structured summary with bullet points

AVOID:
- Repeating the question back
- Explaining what you're about to do
- Including unchanged code around edits
- Verbose transitions between sections
</output_efficiency>
```

---

## Pattern 5: Multi-Turn Context Decay

In long conversations, earlier context gets compressed or lost. Design prompts that account for this:

- **Anchor critical decisions**: Restate key constraints in the current turn rather than relying on turn-3 context
- **Use structured references**: "As established in the auth module analysis above" rather than assuming the model recalls details
- **Front-load turn-specific context**: Put the most relevant information for THIS turn at the top of the message

---

## Position Sensitivity: The U-Shaped Attention Curve

**Core insight**: LLMs exhibit a U-shaped attention curve (Liu et al. 2023, Stanford). Instructions at the start and end of context are processed effectively; mid-document content suffers ~20-30% compliance loss. Instruction fine-tuning worsens this by biasing models toward beginning positions.

**Practical rules**:
- **Critical rules**: place at start AND end of system prompt (dual placement)
- **Mid-document rules**: higher skip risk — use structural enforcement or hooks for these
- **Long system prompts** (>200 lines): mid-section rules have significantly degraded compliance
- **End-of-prompt positioning**: Anthropic recommends repeating critical guidelines at the end of system prompts. End-of-prompt rules benefit from recency bias. This is the positional complement to the constraint-anchor pattern.

**Design implications**:
- Opening section: role, core constraints, behavioral defaults
- Middle section: domain rules, examples, reference tables (accept some drift)
- Closing section: restate critical constraints, quality gates, anti-patterns

---

## Passive vs Active Context: The Compliance Gap

**Core insight**: Vercel research found passive context (always-in-context, like AGENTS.md) achieves 100% compliance vs 53-79% for active skill loading (model must decide to Read a file). Each active-retrieval decision point is a compliance dropout opportunity.

**Decision framework**:

| Context Type | Placement | Use For |
|--------------|-----------|---------|
| **Passive** (in CLAUDE.md) | Always in system prompt | Critical rules, routing protocol, behavioral defaults — things that MUST be followed every turn |
| **Active** (skills) | Loaded on-demand via Read | Methodology, templates, detailed procedures — things needed only when relevant |

**Anti-pattern**: Putting compliance-critical instructions behind an active-retrieval gate. If it's a hard requirement, make it passive.

**Example split**:
- Passive: "ALWAYS run tests before marking code complete"
- Active: Detailed test fixture patterns, mocking strategies, coverage thresholds

---

## Anti-Patterns: Context Waste

| Waste Pattern | Cost | Fix |
|---------------|------|-----|
| Full file when one function needed | 10-100x | Specify line ranges or function names in prompt |
| All search results unfiltered | 5-20x | Instruct agent to rank, dedupe, limit |
| Repeated context across turns | 2-5x | Reference previous turns, don't restate |
| Tool schemas loaded "just in case" | 1.5-3x | Load on-demand via progressive disclosure |
| Verbose CoT for simple tasks | 2-4x | Match reasoning depth to task complexity |
| Prose where a table would suffice | 2-3x | Use tables for structured information |
