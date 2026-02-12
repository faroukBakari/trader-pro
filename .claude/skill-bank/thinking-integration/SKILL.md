---
name: thinking-integration
description: CLI thinking controls mapped to reasoning tiers. Load when calibrating effort levels or configuring subagent thinking
keywords: [thinking, effort, adaptive-thinking, extended-thinking, finops, subagent-effort]
category: reasoning
disable-model-invocation: true
---

# Thinking Integration

Bridges Claude Code CLI thinking controls to the reasoning tier model (T0–T4 from `reasoning-strategy`). Provides effort-level guidance for main agent and subagents, FinOps guardrails, and promptable tuning patterns.

**Depends on**: `reasoning-strategy` (tier definitions), `model-selection` (model capabilities)

---

## When to Use This Skill

- Calibrating thinking effort for a task or subagent delegation
- Deciding between effort levels (`low`/`medium`/`high`/`max`)
- Optimizing thinking cost without sacrificing quality
- Configuring session or project-level thinking defaults
- Diagnosing whether thinking is helping or hurting performance

---

## 1. CLI Thinking Controls (Opus 4.6)

### Current Controls

| Control | Method | Scope | Notes |
|---------|--------|-------|-------|
| **Toggle thinking** | `Alt+T` (Linux/Win), `Option+T` (Mac) | Session | On/off toggle |
| **Effort level** | `/model` → left/right arrows | Session | `low` / `medium` / `high` / `max` |
| **Effort env var** | `CLAUDE_CODE_EFFORT_LEVEL` | Global or session | Set in `settings.json` `env` or shell |
| **Disable thinking** | `MAX_THINKING_TOKENS=0` | Global or session | Only value that works on Opus 4.6 |
| **Verbose mode** | `Ctrl+O` | Session | Shows summarized thinking as gray italic text |
| **Fast mode** | `/fast` | Persistent | 2.5x speed, same model, higher cost — combinable with effort |

### Key Facts

- **Adaptive thinking is the default** on Opus 4.6 — the model decides when and how much to think
- **Interleaved thinking is automatic** — Claude reasons between tool calls (the "think tool" pattern)
- **Keyword triggers are deprecated** — `think`, `ultrathink`, `think harder` have no effect on token allocation
- **`MAX_THINKING_TOKENS`** is ignored on Opus 4.6 except when set to `0` (disables entirely)
- **`max` effort is Opus 4.6 only** — errors on other models

### Effort Level Behavior

| Level | Thinking Behavior | Latency | Cost Impact |
|-------|-------------------|---------|-------------|
| `low` | Minimizes/skips thinking | Lowest | Lowest |
| `medium` | Moderate thinking, skips for trivial queries | Moderate | Moderate |
| `high` (default) | Almost always thinks deeply | Higher | Higher |
| `max` | No constraints on depth (Opus only) | Highest | Highest |

---

## 2. Tier-to-Effort Mapping

Maps the abstract T0–T4 reasoning tiers (from `reasoning-strategy`) to concrete CLI effort levels.

| Tier | Name | Effort Level | Rationale |
|------|------|-------------|-----------|
| **T0** | Direct | `low` | Known answers, lookups — thinking adds latency with no quality gain |
| **T1** | Linear CoT | `medium` | Single-domain reasoning — moderate thinking sufficient |
| **T2** | Structured Decomposition | `high` | Multi-factor decisions — deep thinking justified |
| **T3** | Inter-Action Deliberation | `high` | Multi-tool workflows — interleaved thinking (automatic on Opus 4.6) |
| **T4** | Adversarial Self-Correction | `max` | Ambiguous/high-stakes — unconstrained depth for adversarial reasoning |

### When to Override Default (`high`)

**Downgrade to `medium` or `low`:**
- Task is clearly T0–T1 (file reads, simple edits, known patterns)
- Subagent doing routine work (search, extraction, formatting)
- Iteration speed matters more than first-pass quality
- Cost sensitivity on repetitive operations

**Upgrade to `max`:**
- Architecture decisions with long-term consequences
- Debugging elusive race conditions or state bugs
- Security review or audit
- Ambiguous requirements needing tradeoff analysis
- After a failed attempt at `high` — escalate one level

---

## 3. Subagent Effort Guidance

Recommended effort levels when delegating to subagents via `Task` tool.

| Subagent Type | Default Tier | Recommended Effort | Rationale |
|---------------|-------------|-------------------|-----------|
| `Explore` | T0–T1 | `low` | File discovery, pattern matching — thinking unnecessary |
| `Bash` | T0 | `low` | Terminal execution — no reasoning needed |
| `Plan` | T2–T3 | `high` | Implementation planning — deep reasoning justified |
| `general-purpose` | T1–T3 | `high` | Multi-step research, implementation, reviews — default effort appropriate |

**Note**: Effort settings are per-session, not per-subagent. Subagents inherit the session's thinking configuration. Adjust the session effort before delegating when the subagent's task demands a different level than the main task.

---

## 4. Thinking as Flaw Mitigation

Extended/interleaved thinking can mitigate known model-specific flaws — but can also **amplify** biases in specific conditions.

### Opus Flaws Affected by Thinking

| Flaw | ID | Thinking Impact | Direction |
|------|----|--------------------|-----------|
| Framing bias amplification | O1 | At `low`/`medium` effort, adaptive thinking short-circuits before correcting the initial complexity misclassification. The biased classification becomes the basis for all subsequent decisions | **Amplifies** ❌ |
| Selective completion | O2 | At `high` effort, thinking *can* catch incomplete work — but only if the prompt includes enumerated requirements. Without a checklist, thinking rationalizes early exit | **Mixed** ⚠️ |
| Premature victory | O3 | Interleaved thinking between tool calls helps detect "declaring done" — but the model's confidence in completion grows with thinking depth, making it harder to self-correct | **Mixed** ⚠️ |

**The pre-deliberation trap**: Opus 4.6's adaptive thinking evaluates query complexity from the raw prompt *before* any structured reasoning fires. If user framing anchors the classification to "simple" (e.g., "fix this typo"), the model allocates minimal thinking, which means the structured reasoning that would correct the misclassification never runs. This is a **self-reinforcing loop**:

```
Casual framing → low complexity heuristic → minimal thinking allocated
  → no structured reasoning to challenge the classification
    → process gates with qualifiers ("non-trivial") evaluate as FALSE
      → gate skipped → task executed at T0 when it needed T1–T2
```

**Mitigation**: Use unconditional process gates (see `prompting-guide` § Gate Design). When the gate fires regardless of classification, thinking gets a chance to evaluate the domain match and correct the tier assignment.

### Sonnet Flaws Addressable by Thinking

| Flaw | ID | How Thinking Helps |
|------|----|--------------------|
| Reasoning ceiling | F6 | Interleaved thinking extends 3-4 hop ceiling via mid-chain reasoning |
| Confirmation bias | F8 | T4 adversarial thinking forces counter-evidence evaluation |
| Premature completion | F3 | Thinking between tool calls catches missed steps |

**Pattern**: For Sonnet tasks hitting F6 (multi-hop), decompose into phases with checkpoints and ensure interleaved thinking is active.

### Haiku Flaws — Limited Mitigation

| Flaw | ID | Thinking Impact |
|------|----|--------------------|
| Reasoning depth wall | H1 | Minimal — Haiku's 1-2 hop ceiling is structural, not thinking-budget-limited |
| Verification rubber-stamp | H5 | None — Haiku lacks adversarial reasoning capacity regardless of thinking budget |

**Recommendation**: For Haiku, invest in task decomposition (shorter chains) rather than increased thinking effort. Use `low` effort and compensate with tighter prompt structure.

---

## 5. Promptable Thinking Tuning

Adaptive thinking is **promptable** — system prompt guidance influences when and how deeply Claude thinks.

### Recommended System-Level Directive

Add to CLAUDE.md or session context when thinking optimization matters:

```
Extended thinking should match task complexity. Minimize thinking for
file reads, simple edits, and known-pattern tasks. Reserve deep
thinking for architecture decisions, ambiguous bugs, and multi-step
planning where reasoning quality directly affects outcome quality.
```

### Task-Level Tuning Examples

**Suppress thinking** (speed-critical subagent):
```
Respond directly without extensive deliberation. This is a straightforward
extraction task — locate the pattern and return it.
```

**Encourage deep thinking** (architecture review):
```
Before recommending an approach, reason through at least 3 alternative
designs. For each, evaluate: complexity, maintainability, and alignment
with existing patterns. Then argue against your top choice before finalizing.
```

**Anti-pattern — don't over-specify thinking steps**:
```
# BAD — constrains model creativity
Step 1: List all variables. Step 2: Trace data flow. Step 3: ...

# GOOD — sets goal, lets model reason freely
Thoroughly analyze the data flow through this module. Consider edge cases
and identify any state mutations that could cause race conditions.
```

---

## 6. FinOps: Thinking Cost Guardrails

| Checkpoint | Trigger | Gate Action |
|------------|---------|-------------|
| **Effort calibration** | Subagent delegation | Set effort matching task tier — don't default everything to `high` |
| **Thinking ROI** | `max` effort used >2 consecutive turns | Verify task genuinely needs T4; downgrade if diminishing returns |
| **Overthinking detection** | Simple task + `high`/`max` effort | Up to 36% performance degradation on intuitive tasks — downgrade |
| **Verbose audit** | Suspecting wasted thinking tokens | Use `Ctrl+O` to inspect whether thinking is producing useful reasoning |
| **Fast mode combo** | Iteration speed needed + quality still matters | `/fast` + `medium` effort = fast iteration without fully disabling thinking |

### Cost Impact Reference

Thinking tokens are billed at output token rates. More thinking = higher cost:
- `low` effort: ~baseline cost
- `medium` effort: ~1.2–1.5x baseline
- `high` effort: ~1.5–2x baseline
- `max` effort: ~2–3x baseline (unbounded depth)

Combine with `/fast` mode (2.5x speed, higher per-token cost) for time-sensitive work where quality still matters.

---

## 7. Thinking Mode Timing

Three distinct reasoning timing modes (from `reasoning-calibration/timing-and-chains.md`):

| Mode | When It Runs | CLI Relevance |
|------|-------------|---------------|
| **Pre-Response** | Before first output | Controlled by effort level — `high`/`max` ensures deep pre-response reasoning |
| **Inter-Action** | Between tool calls | **Automatic on Opus 4.6** — interleaved thinking enabled by default |
| **Post-Action** | After completion | Not CLI-controlled — driven by prompt directives (reflexion pattern) |

**Key insight**: With Opus 4.6, you get both pre-response AND inter-action reasoning automatically at `high` effort. The main calibration lever is effort level, not thinking mode selection.

---

## 8. Quick Reference

### Session Setup Checklist

1. Is thinking enabled? (`Alt+T` to check/toggle)
2. Is effort level appropriate for the session's primary task tier?
3. For subagent-heavy sessions, consider adjusting effort before each delegation
4. Use `Ctrl+O` periodically to verify thinking is productive

### Decision Flowchart

```
Task arrives →
  Is it T0 (lookup, file read, simple action)?
    → effort: low, skip thinking
  Is it T1 (single-domain implementation)?
    → effort: medium
  Is it T2 (design decision, multi-factor)?
    → effort: high (default — usually already set)
  Is it T3 (multi-tool workflow, policy-heavy)?
    → effort: high (interleaved thinking automatic)
  Is it T4 (ambiguous, high-stakes, architecture)?
    → effort: max
  Did previous attempt fail at current effort?
    → escalate one level
```

---

## References

- [Adaptive Thinking — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking)
- [Effort Parameter — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Extended Thinking Tips — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/extended-thinking-tips)
- [The "think" tool — Anthropic Engineering](https://www.anthropic.com/engineering/claude-think-tool)
- [Claude Code Common Workflows](https://code.claude.com/docs/en/common-workflows)
