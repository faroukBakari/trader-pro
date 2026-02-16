---
name: haiku-prompting
description: Claude Haiku 4.5 flaw catalog with prompt-level mitigations. Load when writing prompts for Haiku-powered subagents
user-invocable: false
---

# Haiku 4.5 Prompting Guide

Prompt engineering patterns that exploit Haiku 4.5's strengths (speed, cost, routine tool use) while guarding against its documented behavioral flaws. Complements generic prompting skills with model-specific mitigations.

**Scope boundary**: This skill covers *how to prompt Haiku effectively*. For model *selection* (when to use Haiku vs Sonnet vs Opus), apply `model-selection`. For generic prompt *structure* patterns, apply `prompting-guide`. For reasoning directive *quality* (phrasing, timing, chain length), apply `reasoning-calibration`. For prompt *file* mechanics (.prompt.md format), apply `prompt-file-design`. For Sonnet-specific guards, apply `sonnet-prompting`.

---

## When to Use This Skill

- Writing or reviewing `<constraints>` for a Haiku-powered subagent
- Designing methodology sections where Haiku will execute routine tasks
- Diagnosing poor output quality from a Haiku-powered subagent (hallucination, missed instructions, truncation)
- Optimizing prompt structure for Haiku's processing characteristics (speed, cost, capacity tradeoffs)
- Deciding which guard sections to include for a given Haiku task type
- Calibrating existing Sonnet guard patterns for Haiku's tighter operating envelope

---

## Haiku 4.5 Flaw Catalog

Nine documented behavioral flaws from benchmark data, practitioner reports, and observed workspace behavior. Each is assigned a severity and primary mitigation. Flaws are categorized by their relationship to the Sonnet 4.5 flaw catalog (F1-F10).

### Amplified Sonnet Flaws (worse in Haiku)

| ID | Flaw | Severity | Sonnet Equiv. | Delta | Description | Primary Guard |
|----|------|----------|---------------|-------|-------------|---------------|
| **H1** | Reasoning depth wall | CRITICAL | F6 (3-4 hops) | 50-66% worse | Reliable at 1-2 hops only. Beyond 2, produces wrong conclusions, skipped steps, or premature "done". Any "if X then analyze Y then decide Z" chain exceeds capacity. | Task decomposition to ≤2 hops |
| **H2** | Instruction fragility | HIGH | F4 (drift) | Faster onset | Drops IMPORTANT-tier constraints after 3-5 tool calls (vs Sonnet's ~10). CRITICAL constraints hold longer but the safe window is narrower. | Constraint compression — ≤3 CRITICAL |
| **H3** | Synthesis incapacity | HIGH | F1+F10 | New failure class | Cannot connect disparate findings. Extracts data point A and B individually but fails at "A implies B because C." Tends to list findings without drawing conclusions. | Restrict to extraction, not analysis |
| **H4** | Tool chain breakdown | HIGH | F3 (premature) | Worse | When task requires multi-tool sequences (grep → read → analyze), degrades at step 3+. Produces premature conclusions from step 1-2 results, skipping deeper investigation. | Single-tool-per-invocation design |
| **H5** | Verification rubber-stamp | HIGH | F1+F8 | Significantly worse | Near-zero capacity for critical evaluation. If caller says "verify X works," Haiku confirms even with contradictory evidence. Cannot balance expectations vs evidence. | Never assign verification tasks |
| **H6** | Output truncation | MEDIUM | F2 (lazy) | Moderately worse | Summarizes prematurely or drops tail content on long outputs. Cuts off earlier than Sonnet. Silent truncation without acknowledgment. | Explicit truncation markers |
| **H7** | Hallucination under ambiguity | MEDIUM | F7 (tool halluc.) | Worse | When target not found, invents plausible file paths, function names, or parameter values rather than reporting absence. Less capacity to "know it doesn't know." | Mandatory NOT FOUND protocol |

### New Haiku-Specific Flaws (not present in Sonnet)

| ID | Flaw | Severity | Description | Primary Guard |
|----|------|----------|-------------|---------------|
| **H8** | Format compliance erosion | MEDIUM | Follows structured output formats well on short tasks, but compliance degrades faster than Sonnet as task complexity grows. JSON schemas, tables, and markdown break under multi-step pressure. | Format re-anchor before output |
| **H9** | Overly literal interpretation | LOW-MED | Interprets instructions literally, missing intent. "Find the test file for this module" returns only exact filename matches rather than understanding project conventions. Lacks contextual inference. | Explicit search strategy instructions |

---

## Haiku Operating Envelope

Understanding Haiku's safe operating parameters prevents assigning tasks that exceed its capacity.

| Parameter | Haiku 4.5 | Sonnet 4.5 | Implication |
|-----------|-----------|------------|-------------|
| Reliable reasoning hops | 1-2 | 3-4 | T0 tasks only (reasoning-strategy) |
| CRITICAL constraint cap | ≤3 | ≤5 | Tighter constraint budget |
| Tool calls before drift | 3-5 | ~10 | Shorter agent sessions |
| Structured output reliability | Short tasks only | Sustained | Re-anchor format on multi-step |
| Synthesis / connection | None | Basic | Extract only, no analysis |
| Self-correction | None | Limited | Parent must verify all output |
| Speed | 4-5x Sonnet | Baseline | Real advantage for high-volume work |
| Cost | 0.33x Sonnet | Baseline | 3 Haiku calls ≈ 1 Sonnet call |

**Key insight**: Haiku's operating envelope is T0 (Direct) on the reasoning-strategy tier model. Any task requiring T1+ reasoning should use Sonnet minimum.

---

## Methodology

### Phase 1: Verify Task Fitness

Before writing a prompt for a Haiku-powered subagent, confirm the task fits Haiku's envelope:

| Task Characteristic | Haiku Fit | If No → |
|---------------------|-----------|---------|
| Requires 0-1 reasoning hops? | ✅ Proceed | Use Sonnet |
| Single tool type per invocation? | ✅ Proceed | Use Sonnet |
| No evaluation/judgment needed? | ✅ Proceed | Use Sonnet |
| Output is data, not analysis? | ✅ Proceed | Use Sonnet |
| Session ≤5 tool calls? | ✅ Proceed | Add constraint anchor or use Sonnet |
| No synthesis across findings? | ✅ Proceed | Use Sonnet |

**If ANY answer is "No"** → either redesign the task to fit, or upgrade to Sonnet. No prompt trick compensates for a capability gap.

### Phase 2: Assess Risk Profile

If the task fits, identify which Haiku flaws it's exposed to:

| Task Characteristic | Exposed Flaws | Required Guards |
|---------------------|---------------|-----------------|
| File reading / extraction | H7, H9 | NOT FOUND protocol, search strategy |
| Command execution | H6, H7 | Truncation markers, no-guess directive |
| Search / grep operations | H7, H9 | Literal interpretation guard, widening strategy |
| Multi-file parallel reads | H2, H8 | Constraint compression, format re-anchor |
| Doc navigation | H9, H3 | Explicit path instructions, no synthesis |
| Data transformation | H6, H8 | Output scope lock, format anchor |

### Phase 3: Apply Guard Patterns

Inject guards matching the risk profile. Haiku has a **tighter constraint budget** than Sonnet — every guard must earn its place.

**Priority 1 — Always include for Haiku subagents:**

1. **Anti-hallucination** (guards H7): The single most important Haiku guard.
   ```
   If target not found, respond "NOT FOUND: {what was searched}".
   NEVER guess, infer, or fabricate file paths, function names, or values.
   ```

2. **Constraint compression**: Keep CRITICAL tier to **≤3 items**. Haiku's adherence drops sharply beyond 3. Move overflow to IMPORTANT.

**Priority 2 — Include based on risk profile:**

3. **Output scope lock** (guards H6): Required when output may be long.
   ```
   If output would exceed {N} lines, summarize with "[TRUNCATED: {count} additional items]".
   Never silently drop content.
   ```

4. **Search strategy** (guards H9): Required for search/discovery tasks.
   ```
   Search exact match FIRST, then broaden with pattern/glob.
   If zero results, try {alternative strategies} before reporting NOT FOUND.
   ```

5. **Format re-anchor** (guards H8): Required for multi-step tasks with structured output.
   ```
   Re-read the output_format section before writing your final response.
   ```

**Priority 3 — Include for edge cases:**

6. **Constraint anchor** (guards H2): If session may reach 4-5 tool calls.
   ```
   ⚠️ Re-read CRITICAL constraints before proceeding.
   ```

### Phase 4: Calibrate from Sonnet Guards

When adapting a Sonnet prompt for Haiku, apply these calibration rules:

| Sonnet Guard | Haiku Calibration |
|--------------|-------------------|
| `<anti-sycophancy>` | **Remove** — assign evaluation tasks to Sonnet instead (H5) |
| `<completeness>` | **Replace** with output scope lock — Haiku truncates rather than placeholders |
| `<scope-fence>` | **Simplify** — Haiku rarely makes bold changes (insufficient capacity for F5) |
| `<constraint-anchor>` | **Lower threshold** — trigger at 3 tool calls, not 10 |
| `<reasoning_guidance>` | **Remove** — if task needs reasoning, upgrade to Sonnet (H1) |
| CRITICAL ≤5 cap | **Tighten** to ≤3 (H2) |
| Convention anchoring | **Unnecessary** — Haiku doesn't generate code (H1 prevents it) |

### Phase 5: Validate Prompt

| Check | What to Verify | Fix If Failing |
|-------|----------------|----------------|
| **CRITICAL cap** | ≤3 items in CRITICAL tier? | Move overflow to IMPORTANT |
| **Task fitness** | Task fits Haiku operating envelope (Phase 1)? | Redesign or upgrade model |
| **Guard coverage** | All high-risk flaws from Phase 2 have guards? | Add missing guards |
| **No evaluation** | No judgment/verification/analysis expected? | Remove or upgrade to Sonnet |
| **Output format** | Structured format with concrete example? | Add format with example |
| **NOT FOUND protocol** | Anti-hallucination guard present? | Always add — non-negotiable |

---

## Quick Reference: Guard Injection Patterns

Minimal guard blocks for Haiku subagent prompts. Each targets a specific flaw.

### Anti-Hallucination (H7) — MANDATORY, 2 lines
```
If target not found, respond "NOT FOUND: {what was searched}".
NEVER guess, infer, or fabricate file paths, function names, or values.
```

### Output Scope Lock (H6) — 2 lines
```
If output would exceed {N} lines, summarize with "[TRUNCATED: {count} items omitted]".
Never silently drop content — acknowledge what was omitted.
```

### Constraint Compression (H2) — design rule
```
Keep CRITICAL constraints to ≤3 items.
Merge related constraints. Move all overflow to IMPORTANT tier.
```

### Search Strategy (H9) — 3 lines
```
Search exact match FIRST, then broaden with glob/regex patterns.
If zero results after broadening, try alternative names or paths.
Report all search attempts before concluding NOT FOUND.
```

### Format Re-Anchor (H8) — 1 line
```
Re-read the <output_format> section before writing your final response.
```

### Constraint Anchor (H2) — 1 line, place at tool call 3
```
⚠️ Re-read CRITICAL constraints before proceeding.
```

### Synthesis Fence (H3) — 2 lines
```
Report findings as extracted data only.
Do NOT draw conclusions, infer causality, or recommend actions.
```

---

## Haiku vs Sonnet: Guard Selection Matrix

Side-by-side comparison for deciding which guards apply to which model:

| Guard Section | Sonnet | Haiku | Why Different |
|---------------|--------|-------|---------------|
| `<anti-sycophancy>` | Required for eval tasks | **Never** — don't assign eval to Haiku | H5 makes it pointless |
| `<completeness>` | Required for code gen | **Replace** with output scope lock | Haiku truncates, doesn't placeholder |
| `<scope-fence>` | Required for write tasks | **Simplify or remove** | Haiku lacks capacity for bold changes |
| `<constraint-anchor>` | At 10+ tool calls | **At 3+ tool calls** | H2 faster drift onset |
| `<reasoning_guidance>` | For structured thinking | **Never** — upgrade model instead | H1 makes reasoning guards futile |
| `<anti-hallucination>` | Optional (verify-first) | **Always mandatory** | H7 is Haiku's #1 risk |
| `<output-scope-lock>` | Rarely needed | **Often needed** | H6 earlier truncation |
| `<search-strategy>` | Rarely needed | **For search tasks** | H9 literal interpretation |
| `<synthesis-fence>` | Not applicable | **For multi-finding tasks** | H3 prevents analysis |
| `<format-re-anchor>` | Not needed | **For multi-step tasks** | H8 format erosion |

---

## Anti-Patterns

- ❌ **Assigning evaluation tasks** — "Review this code" or "verify the fix" on Haiku. H5 (rubber-stamp) means it will confirm anything. Use Sonnet for all evaluation.
- ❌ **Expecting synthesis** — "Analyze these 5 files and explain the pattern." Haiku can extract from each file individually but cannot connect findings (H3). Use Sonnet for synthesis.
- ❌ **Long tool chains** — Tasks requiring 4+ sequential tool calls where each depends on the previous. Haiku degrades at step 3+ (H4). Redesign as independent parallel reads or upgrade to Sonnet.
- ❌ **Overloading CRITICAL** — More than 3 CRITICAL items. Haiku's constraint adherence drops sharply beyond 3, faster than Sonnet's 5-item cliff. Keep CRITICAL tight.
- ❌ **Reasoning guards without model upgrade** — Adding `<reasoning_guidance>` to a Haiku prompt. No prompt trick fixes a 1-2 hop ceiling (H1). If the task needs reasoning, upgrade to Sonnet.
- ❌ **Trusting Haiku output without parent verification** — Parent agents (Sonnet/Opus) must always verify Haiku subagent outputs. Haiku has near-zero self-correction capacity.
- ❌ **Silent failure assumption** — Expecting Haiku to report "I can't do this." Haiku will attempt any task and produce plausible-looking but potentially wrong output (H7). Design for failure at the architecture level.
- ❌ **Using Sonnet guard patterns unmodified** — Sonnet guards assume 3-4 hop reasoning, 5-item CRITICAL cap, and 10+ call sessions. All three are wrong for Haiku. Always calibrate per Phase 4.

---

## Resources

- [template.md](./template.md) — Haiku-specific calibration rules and flaw-to-section mapping
- [examples.md](./examples.md) — Concrete guard examples per flaw with before/after comparisons
