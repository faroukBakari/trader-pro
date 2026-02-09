# Haiku-Specific Calibrations

Haiku-specific adjustments to apply on top of the generic prompt sections defined in the `prompting-guide` skill. This file does NOT redefine sections — it calibrates them for Haiku 4.5's behavioral characteristics.

---

## Haiku Calibration Rules

Apply these adjustments when the target model is Haiku 4.5:

| Generic Section          | Haiku Calibration |
| ------------------------ | ----------------- |
| `<role>`                 | Keep to 1 line. Identity only. No convention anchoring needed — Haiku doesn't generate code. |
| `<task>`                 | Use shortest possible imperative. "Extract X from Y" not "Analyze the codebase to find X in Y." |
| `<constraints>` CRITICAL | Cap at **≤3 items**. Adherence drops sharply beyond 3. Merge related constraints. |
| `<constraints>` language | Ultra-direct. Single-verb imperatives. "Report" not "You should report." |
| `<output_format>`        | Always include with concrete example. Re-anchor before output for multi-step tasks (H8). |
| `<anti-sycophancy>`      | **REMOVE** — do not include. Haiku cannot perform evaluation (H5). Redesign task or upgrade model. |
| `<completeness>`         | **REPLACE** with `<output-scope-lock>`. Haiku truncates rather than placeholders (H6). |
| `<constraint-anchor>`    | Include at **3 tool calls**, not 10. Haiku drifts faster (H2). |
| `<reasoning_guidance>`   | **REMOVE** — do not include. If task needs reasoning, upgrade to Sonnet (H1). |
| `<scope-fence>`          | **SIMPLIFY** to 1 line or remove. Haiku lacks capacity for bold unsolicited changes. |

---

## Minimal Template (Haiku Speed Optimization)

For the focused, single-purpose tasks Haiku excels at. Exploits Haiku's 4-5x speed advantage:

```xml
<task>
{Verb} {target} from {source}.
</task>

<constraints>
CRITICAL:
- {1-2 non-negotiable rules}
- If target not found, respond "NOT FOUND". NEVER guess.
</constraints>

<output_format>
{Exact structure with example}
</output_format>
```

---

## Flaw-to-Section Mapping Reference

| Haiku Flaw                | Primary Guard Section      | Secondary Guard                   |
| ------------------------- | -------------------------- | --------------------------------- |
| H1: Reasoning depth wall  | Upgrade to Sonnet          | Decompose to ≤2-hop sub-tasks     |
| H2: Instruction fragility | Constraint compression ≤3  | `<constraint-anchor>` at 3 calls  |
| H3: Synthesis incapacity  | `<synthesis-fence>`        | Restrict to extraction only       |
| H4: Tool chain breakdown  | Single-tool-per-invocation | Parallel independent reads        |
| H5: Verification rubber   | Upgrade to Sonnet          | Never assign eval/review to Haiku |
| H6: Output truncation     | `<output-scope-lock>`      | File redirection for large output |
| H7: Hallucination          | `<anti-hallucination>`     | NOT FOUND protocol (mandatory)    |
| H8: Format erosion        | `<format-re-anchor>`       | Short output format templates     |
| H9: Literal interpretation | `<search-strategy>`        | Explicit fallback instructions    |

---

## Haiku Section Templates

### `<anti-hallucination>` (H7) — Haiku-specific, replaces Sonnet's verify-first

```xml
<anti-hallucination>
- If target not found, respond: "NOT FOUND: {what was searched for}"
- NEVER guess, infer, or fabricate file paths, function names, or parameter values.
- If uncertain whether a result matches the query, include it with a "[UNCERTAIN]" tag.
</anti-hallucination>
```

### `<output-scope-lock>` (H6) — Haiku-specific, replaces Sonnet's `<completeness>`

```xml
<output-scope-lock>
- If output exceeds {N} items, summarize remainder with "[TRUNCATED: {count} items omitted]".
- Never silently drop content — acknowledge what was omitted and why.
- Prefer structured summaries over raw dumps for large result sets.
</output-scope-lock>
```

### `<synthesis-fence>` (H3) — Haiku-specific, no Sonnet equivalent

```xml
<synthesis-fence>
- Report findings as extracted data only — quote or cite, do not interpret.
- Do NOT draw conclusions, infer causality, or recommend actions.
- If the caller needs analysis, flag: "ANALYSIS NEEDED: {what should be analyzed}"
</synthesis-fence>
```

### `<search-strategy>` (H9) — Haiku-specific, no Sonnet equivalent

```xml
<search-strategy>
- Search exact match FIRST (exact filename, exact string).
- If zero results → broaden with glob patterns or partial matches.
- If still zero → try alternative names, paths, or conventions.
- Report ALL search attempts before concluding NOT FOUND.
</search-strategy>
```

### `<format-re-anchor>` (H8) — Haiku-specific, no Sonnet equivalent

```xml
<format-re-anchor>
⚠️ Before writing your response, re-read the <output_format> section.
Verify your output matches the specified structure exactly.
</format-re-anchor>
```

---

## Model Migration Checklist

When converting a Sonnet subagent to Haiku (cost optimization) or a Haiku subagent to Sonnet (capability upgrade):

### Sonnet → Haiku Downgrade

```
□ Task fits Haiku operating envelope (≤2 hops, no eval, no synthesis)?
□ CRITICAL constraints reduced to ≤3?
□ <anti-sycophancy> removed?
□ <reasoning_guidance> removed?
□ <completeness> replaced with <output-scope-lock>?
□ <constraint-anchor> threshold lowered to 3 tool calls?
□ <anti-hallucination> added (mandatory)?
□ Parent agent verifies Haiku output?
□ No multi-tool chains requiring sequential reasoning?
```

### Haiku → Sonnet Upgrade

```
□ CRITICAL cap can expand to ≤5?
□ Reasoning guidance can be added for complex tasks?
□ Anti-sycophancy guards needed for evaluation tasks?
□ Completeness guards replace output-scope-lock?
□ Convention anchoring added for code generation tasks?
□ Constraint anchor threshold raised to ~10 tool calls?
□ Multi-tool chains now supported?
```
