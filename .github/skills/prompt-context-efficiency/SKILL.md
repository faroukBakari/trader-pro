---
name: prompt-context-efficiency
description: Context management and FinOps patterns for prompts. Use when optimizing token budget, handling large inputs, or designing context-efficient prompts.
---

# Context Efficiency Patterns

Apply these patterns when generating prompts that handle large inputs or need token-aware design.

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

Structure prompts to fetch detail incrementally:

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

---

## Pattern 2: Input Preprocessing

Tell the model HOW to handle large inputs:

```xml
<input_handling>
FOR LOGS:
- Skip repetitive entries (keep first + count)
- Focus on: errors, warnings, state transitions
- Ignore: debug spam, health checks

FOR CODE:
- Prioritize: signatures, class definitions, error handling
- Skim: boilerplate, imports
- Deep-read: business logic, custom implementations

FOR SEARCH RESULTS:
- Deduplicate similar findings
- Rank by relevance, summarize patterns
</input_handling>
```

---

## Pattern 3: Relevance Boundaries

Explicitly scope what context matters:

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

---

## Pattern 4: Output Token Management

```xml
<output_efficiency>
RESPONSE SIZING:
- Simple questions → 1-3 sentences
- Code changes → diff-style or minimal replacement
- Analysis → structured summary

AVOID:
- Repeating the question back
- Explaining what you're about to do
- Including unchanged code around edits
- Verbose transitions
</output_efficiency>
```

---

## Anti-Patterns: Context Waste

| Waste Pattern | Cost | Fix |
|---------------|------|-----|
| Full file for one function | 10-100x | Use line ranges or grep |
| All search results unfiltered | 5-20x | Rank, dedupe, limit |
| Repeated context across turns | 2-5x | Reference previous |
| Tool schemas "just in case" | 1.5-3x | Load on-demand |
| Verbose CoT for simple tasks | 2-4x | Match depth to complexity |
