---
name: drift-guard
description: Mid-flight deviation classification and response protocol. Use when encountering blockers, unexpected findings, scope changes, or new concerns during ongoing work. Prevents silent bold decisions while avoiding over-escalation on minor details.
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

| Signal | Description | Example |
|--------|-------------|---------|
| **Blocker** | Cannot proceed as planned; something prevents the next step | Missing dependency, API returns unexpected format |
| **Surprise** | Reality differs from assumption made at planning time | File already refactored, pattern uses different approach |
| **Scope pull** | Temptation or perceived need to do more than asked | "This function also needs fixing", "Let me also add validation" |
| **New concern** | Discovery that raises quality/security/correctness questions | SQL injection vector, race condition, data integrity risk |
| **Approach failure** | Current strategy is not yielding expected results after fair attempt | Tests keep failing, type system fights back, design doesn't fit |
| **External mismatch** | External system/config/schema differs from what was assumed | API version changed, config format is YAML not JSON |

**When triggered**: Proceed to Phase 2. Do NOT silently make a choice.

### Phase 2: Two-Dimensional Classification

Classify the deviation on two axes:

**Axis 1 — Divergence from Intent**: How far does this choice take us from what was originally asked?

| Level | Definition | Indicators |
|-------|------------|------------|
| **Low** | Same goal, slightly different path | Different variable name, alternative import, equivalent API call |
| **Medium** | Same goal, meaningfully different approach | Different algorithm, alternative library, restructured module |
| **High** | Different or expanded goal | New feature added, scope expanded, architecture changed |

**Axis 2 — Reversibility**: How costly is it to undo if the choice is wrong?

| Level | Definition | Indicators |
|-------|------------|------------|
| **Trivial** | Undo in seconds, no ripple effects | Rename, reformat, swap import |
| **Local** | Undo with moderate effort, changes stay within one file/module | Rewrite function, change approach within module |
| **Broad** | Undo requires significant rework across multiple files/systems | Architecture change, new dependency, schema migration, public API change |
| **Irreversible** | Cannot undo, or cost of undo exceeds cost of original work | Data deletion, external API call with side effects, published interface |

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

**When**: Trivial choice with low divergence. Only one or two reasonable options, either is fine.

**Protocol**:
1. Choose the option that best aligns with existing patterns in the codebase
2. Continue working without interruption
3. No documentation required (the choice is self-evident from the code)

**Examples**: Import style, variable naming following local convention, equivalent API method

#### TACTICAL — Document and Proceed

**When**: Real choice with meaningful alternatives, but locally contained and safely reversible.

**Protocol**:
1. Make the best judgment call based on available context
2. Document the decision in the work output:
   - What was decided
   - What alternatives existed
   - Why this choice was made
3. Continue working
4. Flag in the completion report so the user can review and override

**Template**:
```
⚡ Tactical decision: {what was decided}
   Alternatives: {what else could have been done}
   Rationale: {why this choice}
```

**Examples**: Choosing between two valid error handling strategies, selecting a workaround for a blocker, minor scope addition that's clearly helpful

#### STRATEGIC — Stop and Escalate

**When**: The choice meaningfully changes direction, is hard to reverse, or the agent lacks confidence that the user would agree.

**Protocol**:
1. **STOP** current work — do not implement the choice
2. **Summarize** the situation concisely:
   - What was being done
   - What deviation was encountered
   - Why it requires a decision
3. **Present 2-4 concrete options** with tradeoffs:
   - Each option: what it does, pros, cons, effort
   - Mark a recommended option with rationale
   - Include "pause/defer" as an option when applicable
4. **Wait** for user decision before proceeding
5. **Resume** work with the chosen option

**Template**:
```
🛑 Strategic decision needed: {situation summary}

Options:
  A) {option} — {pros} / {cons}
  B) {option} — {pros} / {cons}
  C) {option} — {pros} / {cons}
  
Recommended: {option letter} because {rationale}
```

**Examples**: Architecture change to accommodate a finding, adding a new dependency, expanding scope significantly, choosing between incompatible approaches

#### CRITICAL — Stop and Recommend Rollback

**When**: The finding is severe enough that continuing on the current path is risky, or an irreversible action is needed.

**Protocol**:
1. **STOP immediately** — do not take further action
2. **Assess damage**: What has already been changed? Is anything already committed/deployed/irreversible?
3. **Identify rollback point**: What was the last known good state?
4. **Present the situation**:
   - What was discovered
   - What risk it poses (security, data integrity, correctness)
   - What has been done so far (and whether it's safe)
   - Recommended rollback steps (if applicable)
   - Path forward options after stabilizing
5. **Wait** for explicit user authorization before ANY further action

**Template**:
```
🚨 Critical: {what was discovered}

Risk: {what could go wrong}
Current state: {what has been changed so far}
Rollback: {steps to return to safe state, or "no changes made yet"}

Recommended: {stabilize first, then...}
```

**Examples**: Security vulnerability discovered in the approach, data loss risk, discovered that the entire premise of the task was based on incorrect assumption, irreversible external side-effect needed

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

## Negative Claim Verification

Absence claims ("X doesn't exist", "no file matches", "this pattern isn't used", "there are no tests for Y") are high-risk assertions. Incorrect absence claims cause duplicates, overwrites, and architectural inconsistencies. They require a higher evidence bar than positive claims.

### The Asymmetry Rule

| Claim Type | Evidence Required | Sufficient Sources |
|------------|-------------------|--------------------|
| **Positive** ("X exists") | One confirming hit | Any tool result showing the item |
| **Negative** ("X doesn't exist") | Targeted exhaustive search | `file_search` or `grep_search` with specific query — NOT memory of a previous listing |

### Protocol

Before asserting that something is **absent, missing, unused, or doesn't exist**:

1. **Detect the claim** — Am I about to say "there is no...", "X is missing", "doesn't exist", "no tests for", "not used anywhere"?
2. **Run a targeted search** — Use `file_search` (for files) or `grep_search` (for patterns/usages) with a query specific to the claimed-absent item
3. **Only assert absence after null result** — If the search returns nothing, the claim is substantiated
4. **Never filter out the claim domain in delegations** — If delegating research while making claims about category X, the delegation MUST include X in its scope

### Anti-Patterns

- ❌ **Memory-based absence** — "I listed the directory earlier and didn't see it" → stale, incomplete, or misread. Search again.
- ❌ **Delegation exclusion** — Telling a subagent to "skip templates" then claiming "no template exists." The delegation filtered out the evidence.
- ❌ **Implied absence** — Seeing `skill-examples.md` and concluding "only examples, no template" without checking. Adjacent files may contradict the inference.
- ✅ **Verified absence** — `file_search("**/skill-template*")` returned 0 results → safe to claim "no skill template exists."

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

- ❌ **Silent architecture** — Making a Strategic-level choice silently because "it's obviously the right thing to do." If it changes direction meaningfully, the user decides, not the agent.
- ❌ **Escalation fatigue** — Escalating every Cosmetic or Tactical choice to the user. This trains users to ignore escalations, defeating the purpose. Bridge aggressively at low severity.
- ❌ **Confidence theater** — Using high self-confidence as justification to skip escalation. The classification is based on divergence and reversibility, NOT on confidence. A 95%-confident irreversible choice still requires escalation.
- ❌ **Scope creep camouflage** — Framing scope expansion as necessary ("I need to also fix X to make Y work") when it's actually optional. If the original task didn't include it and it can wait, TACTICAL at most.
- ❌ **Rollback avoidance** — Continuing past a Critical finding because "we've already done so much work." Sunk cost is not a factor; safety is.
- ❌ **Vague escalation** — Escalating with "what should I do?" instead of presenting concrete options with tradeoffs. Every Strategic/Critical escalation must include actionable choices.
- ✅ **Calibrated judgment** — Bridge cosmetic choices, document tactical ones, escalate strategic ones with options, halt on critical ones. Match response intensity to actual risk.

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
