---
name: drift-guard
description: Mid-flight deviation detection and response protocol. Load when encountering blockers or scope changes during work
keywords: [drift, deviation, scope-change, escalation, blockers]
category: workflow
disable-model-invocation: true
---

# Drift Guard

Classification framework for mid-flight deviations during ongoing work. Detects when work is drifting from original intent, classifies severity using two dimensions (divergence × reversibility), and prescribes calibrated responses — from silent bridging to full stop with rollback.

---

## When to Use This Skill

- An implementation step hits a blocker (dependency missing, API changed, test failing unexpectedly)
- An unexpected finding changes assumptions (code already exists, pattern differs from expected)
- Scope is expanding beyond what was asked ("while I'm here, I should also...")
- A new concern emerges (security implication, performance issue, architectural violation)
- The chosen approach isn't working and an alternative is needed
- External context changed (config format different, schema mismatch, version incompatibility)

**Do NOT use for**: Pre-flight request analysis (use request evaluation instead) or post-completion review.

---

## Methodology

### Phase 1: Deviation Detection

Recognize when a deviation is occurring. Apply these trigger checks continuously during work:

**Trigger Signals:**

Blocker | Surprise | Scope pull | New concern | Approach failure | External mismatch

Cannot proceed as planned — Missing dep, API format mismatch | Reality ≠ assumption — File already refactored, different pattern | Temptation to expand scope — "also fix X", "add validation" | Quality/security risk — SQL injection, race condition | Strategy failing after fair attempt — Tests fail, types fight back | System differs from assumption — API version changed, config format changed

**When triggered**: Proceed to Phase 2. Do NOT silently make a choice.

### Phase 2: Two-Dimensional Classification

Classify the deviation on two axes:

**Axis 1 — Divergence from Intent**: How far from the original ask?

Low (same goal, different path) | Medium (same goal, different approach) | High (different/expanded goal)
Variable name, import, API call | Algorithm, library, module structure | New feature, scope expansion, architecture

**Axis 2 — Reversibility**: Cost to undo?

Trivial (seconds, no ripple) | Local (one file/module) | Broad (multi-file) | Irreversible (can't undo)
Rename, reformat, import swap | Rewrite function, local approach change | Architecture, dependency, schema, public API | Data deletion, external side-effect, published interface

### Phase 3: Severity Mapping

Map the two axes to a severity level using this matrix:

```
                    LOW divergence    MEDIUM divergence    HIGH divergence

Trivially           COSMETIC          COSMETIC             TACTICAL
reversible

Locally             COSMETIC          TACTICAL             STRATEGIC
reversible

Broadly             TACTICAL          STRATEGIC            CRITICAL
reversible

Irreversible        STRATEGIC         CRITICAL             CRITICAL
```

### Phase 4: Response Protocol

Apply the response matching the severity level:

#### COSMETIC — Bridge Silently

**When**: Trivial choice with low divergence. One or two reasonable options, either fine.

**Protocol**: Choose option matching existing patterns → continue → no documentation (self-evident)

**Examples**: Import style, variable naming, equivalent API method

#### TACTICAL — Document and Proceed

**When**: Real choice, locally contained, safely reversible.

**Protocol**: Make judgment call → document (what/alternatives/why) → continue → flag in completion report

**Template**: `⚡ Tactical: {decision} | Alternatives: {options} | Rationale: {why}`

**Examples**: Error handling strategy, blocker workaround, minor helpful scope addition

#### STRATEGIC — Stop and Escalate

**When**: Choice changes direction meaningfully, hard to reverse, or uncertain user would agree.

**Protocol**: 🛑 STOP → Summarize (what/deviation/why) → Present 2-4 options (pros/cons/effort) + recommendation → Wait → Resume

**Template**: `🛑 Strategic: {situation} | Options: A) {opt} {pros/cons} B) {opt} {pros/cons} C) {opt} {pros/cons} | Rec: {letter} because {rationale}`

**Examples**: Architecture change, new dependency, major scope expansion, incompatible approaches

#### CRITICAL — Stop and Recommend Rollback

**When**: Severe risk to continue, or irreversible action needed.

**Protocol**: 🚨 STOP → Assess damage → Identify rollback point → Present (discovery/risk/state/rollback/path forward) → Wait for explicit auth

**Template**: `🚨 Critical: {discovery} | Risk: {what fails} | State: {changes so far} | Rollback: {steps or "none yet"} | Rec: {stabilize, then...}`

**Examples**: Security vulnerability, data loss risk, incorrect task premise, irreversible side-effect needed

---

## Escalation Failure Safeguard

If self-resolution is attempted for Tactical-level deviations and fails **twice**, auto-upgrade to Strategic:

```
Attempt 1: Try best approach → fails
Attempt 2: Try alternative → fails
→ Auto-upgrade to STRATEGIC
→ Stop and present the situation to the user
```

This prevents infinite loops of self-resolution attempts on problems that need human judgment.

---

## Instruction Drift Detection

**What it is**: Progressive deprioritization of meta-instructions (process rules, routing gates, quality gates) in favor of object-level task completion during extended tool-use loops. Research (arXiv 2601.04170) found detectable drift after ~73 interactions.

**Distinction from scope drift**: Scope drift = pursuing wrong goal. Instruction drift = pursuing right goal while ignoring HOW rules.

**Detection Signals:**

- Process gates skipped later in session but executed earlier (routing protocol, auto-attach modifiers)
- Quality gates degraded (less testing, less verification, skipped diagnostics)
- Conditional compliance weakening (gates with "if non-trivial" start being bypassed)
- Late-session pattern: increased agent autonomy, decreased protocol adherence

**Mitigation:**

- Re-anchoring at tool-call boundaries: Every N calls (checkpoints at 25, 50, 75), re-read critical routing/quality rules
- Context compaction preserves routing instructions (CLAUDE.md §5 preservation priorities)
- Hook-based enforcement for structural gates (diagnostics, negative claim verification)
- Session length awareness: >50 tool calls = elevated drift risk → increase re-anchoring frequency

**Why it matters**: Instruction drift causes late-session quality degradation — correct output delivered incorrectly (untested, unverified, process-skipped). Early session shows compliance, late session shows autonomous shortcuts.

---

## Negative Claim Verification

Absence claims ("X doesn't exist") are high-risk — incorrect claims cause duplicates, overwrites, inconsistencies. Require higher evidence bar than positive claims.

**Asymmetry Rule**: Positive claim (X exists) → one confirming hit. Negative claim (X absent) → targeted exhaustive search (file_search/grep_search), NOT memory.

**Protocol**: Detect claim → Run targeted search → Assert absence only after null result → Never filter claim domain in delegations

**Anti-Patterns**: ❌ Memory-based ("didn't see it earlier") | ❌ Delegation exclusion ("skip X" then claim "no X") | ❌ Implied ("saw Y, so no X") | ✅ Verified (search returned 0)

---

## Decision Trail

Every work session should maintain an implicit decision trail. At minimum:

| Level | Trail Requirement |
|-------|-------------------|
| COSMETIC | None — self-evident from code |
| TACTICAL | Inline note in completion report |
| STRATEGIC | Recorded before/after user decision in work log |
| CRITICAL | Full situation report preserved |

The trail enables post-hoc review: the user can see WHAT decisions were made, WHY, and WHAT alternatives existed — without having been interrupted for every one.

---

## Anti-Patterns

❌ Silent architecture (Strategic choice without escalation) | ❌ Escalation fatigue (escalating Cosmetic/Tactical) | ❌ Confidence theater (skipping escalation due to confidence) | ❌ Scope creep camouflage (framing optional as necessary) | ❌ Rollback avoidance (sunk cost over safety) | ❌ Vague escalation ("what do?" vs options+tradeoffs)

✅ Calibrated judgment: bridge cosmetic → document tactical → escalate strategic with options → halt on critical

---

## Quick Reference Card

```
TRIGGER: Blocker? Surprise? Scope pull? New concern? Approach failure?
   │
   ▼
CLASSIFY:
   Divergence:    Low ─── Medium ─── High
   Reversibility: Trivial ─── Local ─── Broad ─── Irreversible
   │
   ▼
MAP TO SEVERITY:
   COSMETIC  → Bridge silently, continue
   TACTICAL  → Document choice + alternatives, continue
   STRATEGIC → 🛑 STOP → present options → wait for user
   CRITICAL  → 🚨 STOP → assess damage → recommend rollback → wait
   │
   ▼
SAFEGUARD: 2 failed self-resolutions → auto-upgrade severity
```
