---
name: sonnet-prompting
description: Claude Sonnet 4.5 behavioral flaw catalog with prompt-level mitigations, guard patterns, and optimization techniques. Use when writing prompts, constraints, or methodology for Sonnet-powered agents/subagents — ensures output quality by addressing sycophancy, lazy output, constraint drift, and other documented failure modes.
---

# Sonnet 4.5 Prompting Guide

Prompt engineering patterns that exploit Sonnet 4.5's strengths (speed, code editing, structured output) while guarding against its documented behavioral flaws. Complements generic prompting skills with model-specific mitigations.

**Scope boundary**: This skill covers *how to prompt Sonnet effectively*. For model *selection* (when to use Sonnet vs Opus vs Haiku), apply `model-selection`. For generic prompt *structure* patterns, apply `prompting-guide`. For reasoning directive *quality* (phrasing, timing, chain length), apply `reasoning-calibration`. For prompt *file* mechanics (.prompt.md format), apply `prompt-file-design`.

---

## When to Use This Skill

- Writing or reviewing `<constraints>` for a Sonnet-powered agent or subagent
- Designing methodology sections where Sonnet will execute multi-step work
- Diagnosing poor output quality from a Sonnet-powered agent (lazy output, sycophancy, scope creep)
- Optimizing prompt length/structure for Sonnet's processing characteristics
- Deciding which guard sections to include for a given task type

---

## Sonnet 4.5 Flaw Catalog

Ten documented behavioral flaws from vendor sources, benchmark data, and practitioner reports. Each is assigned a severity and primary mitigation.

| ID | Flaw | Severity | Description | Primary Guard |
|----|------|----------|-------------|---------------|
| **F1** | Sycophancy | HIGH | Agrees with user even when wrong. Validates suboptimal approaches instead of challenging them. Acknowledged by Anthropic in model documentation. | `<anti-sycophancy>` section |
| **F2** | Lazy output | HIGH | Produces placeholders (`// ...rest`, `# similar`) instead of complete code. Most-reported community flaw. Worsens in long sessions. | `<completeness>` section |
| **F3** | Premature completion | HIGH | Declares "done" when partially finished. Completes 3/7 steps and summarizes as complete. Acute in multi-step workflows. | Enumerated completion checklist |
| **F4** | Constraint drift | HIGH | Early instructions lose influence as context grows. "Lost in the middle" — attention peaks at context start/end, sags in middle. | Constraint sandwiching |
| **F5** | Bold changes | MEDIUM | Edits beyond scope — modifies unrelated code, adds unrequested features, refactors unprompted. | `<scope-fence>` section |
| **F6** | Reasoning ceiling | MEDIUM | Multi-hop reasoning degrades after 3-4 steps. Cannot maintain logical thread through complex inference chains. 14% intelligence gap vs Opus. | Decompose to ≤3-hop chains |
| **F7** | Tool hallucination | MEDIUM | Fabricates file paths, invents function names, or uses wrong parameter formats. Especially under context pressure. | Verify-first patterns |
| **F8** | Confirmation bias | MEDIUM | When verifying its own work or expected-to-pass results, tends to confirm correctness despite bugs. | Evidence-based verdicts |
| **F9** | Code slop | LOW-MED | Generates unnecessary abstractions, verbose patterns, over-engineered solutions that ignore project conventions. | Convention anchoring in `<role>` |
| **F10** | Negative suppression | LOW-MED | Reluctant to report "found nothing." Stretches findings to appear thorough. Related to F1. | "Report absence" directive |

---

## Methodology

### Phase 1: Assess Task Risk Profile

Before writing a prompt for a Sonnet-powered agent, identify which flaws the task is most exposed to:

| Task Characteristic | Exposed Flaws | Required Guards |
|---------------------|---------------|-----------------|
| Code generation / implementation | F2, F3, F5, F9 | `<completeness>`, `<scope-fence>`, convention anchoring |
| Evaluation / review / verification | F1, F8, F10 | `<anti-sycophancy>`, evidence-based output format |
| Multi-step workflow (>3 steps) | F3, F4 | Enumerated checklist, constraint sandwiching |
| Long session (>10 tool calls) | F4, F2 | Constraint anchors at methodology midpoints |
| File editing (write-enabled) | F5, F7 | `<scope-fence>`, verify-first patterns |
| Complex reasoning / debugging | F6, F7 | ≤3-hop decomposition, escalation marker |
| Research / information gathering | F1, F10 | Negative result reporting, citation requirements |

**Action**: Select guards matching the task's exposed flaws. Use the Section Decision Table in the `prompting-guide` skill to determine which sections to include, then apply Sonnet-specific calibrations from [template.md](./template.md).

### Phase 2: Apply Guard Patterns

Inject the selected guards into the prompt. Follow these priority rules:

**Priority 1 — Always include for Sonnet tasks:**

1. **Anti-lazy directive** (guards F2): Add to CRITICAL constraints:
   ```
   NEVER use placeholder comments (// ..., # similar, etc.). Output ALL code completely.
   ```

2. **Constraint cap**: Keep CRITICAL tier to **3-5 items max**. Sonnet's constraint adherence drops sharply beyond 5 CRITICAL items. Move overflow to IMPORTANT tier.

**Priority 2 — Include based on risk profile:**

3. **Anti-sycophancy** (guards F1, F8, F10): Required for any evaluation, review, or verification task. See [examples.md § Anti-Sycophancy Guards](./examples.md#anti-sycophancy-guards-f1-f8-f10).

4. **Completion checklist** (guards F3): Required for tasks with >2 numbered steps. Enumerate all steps and require explicit [X/N] progress tracking.

5. **Scope fence** (guards F5): Required for write-enabled tasks. Explicit boundary: modify only what's asked.

6. **Constraint sandwich** (guards F4): Required for long-running agents. Repeat top constraints at methodology midpoint and in final output section. See [examples.md § Constraint Drift Guards](./examples.md#constraint-drift-guards-f4).

**Priority 3 — Include for complex tasks:**

7. **≤3-hop decomposition** (guards F6): If reasoning chain exceeds 3 logical steps, break into sequential phases with intermediate checkpoints. Add escalation marker for Opus handoff.

8. **Verify-first pattern** (guards F7): When tool parameters (file paths, API endpoints) are involved, require search/verify before use.

### Phase 3: Optimize for Sonnet Strengths

After applying guards, optimize the prompt to exploit Sonnet's advantages:

**Speed optimization** — Sonnet processes concise prompts fastest:
- Prefer imperative sentences over verbose explanations
- Use tables over paragraphs for decision logic
- Short `<role>` sections (1-3 lines) outperform verbose ones. Line 1 = identity, lines 2-3 = convention anchoring (for F9 mitigation). Omit filler adjectives.
- Eliminate hedging language ("you might want to consider...") — use direct commands

**Structured output** — Sonnet's highest-compliance format:
- Tables with explicit column headers → near-100% format adherence
- JSON with example → reliable schema compliance
- Numbered lists with explicit count → reliable completeness
- Markdown with headers → good section compliance

**Code editing** — Sonnet's benchmark-leading strength (84.2% on Aider):
- Provide concrete context (existing code, imports, types) over abstract descriptions
- Specify exact file paths and line ranges when possible
- Show the "before" state when requesting modifications

### Phase 4: Validate Prompt

Before finalizing, run these checks:

| Check | What to Verify | Fix If Failing |
|-------|----------------|----------------|
| **CRITICAL cap** | ≤5 items in CRITICAL tier? | Move overflow to IMPORTANT |
| **Guard coverage** | All high-risk flaws from Phase 1 have guards? | Add missing guard sections |
| **Conciseness** | Can any section be shortened without losing meaning? | Compress verbose passages |
| **Sandwich** | For long tasks: constraints repeated at midpoint? | Add `<constraint-anchor>` |
| **Output format** | Structured format specified with example? | Add format with concrete example |
| **Escalation path** | Complex reasoning has Opus fallback noted? | Add escalation marker for F6 |

---

## Quick Reference: Guard Injection Patterns

Minimal guard blocks to copy-paste into prompts. Each targets a specific flaw.

### Anti-Lazy (F2) — 2 lines, high impact
```
NEVER use placeholder comments or abbreviated output. Output ALL code completely.
Incomplete output = failed task.
```

### Anti-Sycophancy (F1) — 3 lines
```
Challenge assumptions when evidence contradicts them.
"This approach has risks" is more valuable than silent compliance.
Report what you did NOT find — absence is a finding.
```

### Completion Lock (F3) — 3 lines
```
This task has N steps. ALL must be completed.
Before finishing, list each step with ✅/❌ status.
If any show ❌, continue working.
```

### Scope Fence (F5) — 2 lines
```
ONLY modify files directly related to the stated task.
Noticed-but-unrelated issues go in a "Not Fixed" section.
```

### Constraint Anchor (F4) — 2 lines, place at methodology midpoint
```
⚠️ CHECKPOINT: Re-read CRITICAL constraints before proceeding.
Verify you are still within scope boundaries.
```

### Reasoning Depth Check (F6) — 2 lines
```
If reasoning requires >3 causal steps simultaneously, state:
"⚠️ REASONING DEPTH exceeded" and provide partial findings for Opus escalation.
```

### Convention Anchor (F9) — 2 lines, place in role
```
Match existing codebase patterns exactly.
Do NOT introduce abstractions absent from neighboring code.
```

---

## Anti-Patterns

- ❌ **Guard stacking** — Adding ALL guard sections to every prompt. Excessive constraints cause their own form of F4 (drift via dilution). Select only guards matching the task's risk profile.
- ❌ **Verbose CRITICAL tier** — More than 5 CRITICAL items. Sonnet's adherence drops sharply. Keep it tight, move overflow to IMPORTANT.
- ❌ **Guardrail-only thinking** — Relying solely on prompt guards for F6 (reasoning ceiling). If the task genuinely requires 5+ hop reasoning, upgrade to Opus. No prompt trick fixes a model capability gap.
- ❌ **Trusting Sonnet self-verification** — Having Sonnet verify its own output without structured evidence patterns. Always require "expected vs found" format for verification tasks.
- ❌ **Ignoring Sonnet strengths** — Over-constraining code-editing tasks where Sonnet excels (84.2% benchmark). Not every code task needs full guard stack — short, focused code edits are Sonnet's sweet spot.

---

## Resources

- [template.md](./template.md) — Sonnet-specific calibration rules and flaw-to-section mapping
- [examples.md](./examples.md) — Concrete guard examples per flaw with before/after comparisons
