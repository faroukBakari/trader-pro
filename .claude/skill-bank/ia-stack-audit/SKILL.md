---
name: ia-stack-audit
description: IA stack integrity audit. Use when checking health before releases, validating drift, or diagnosing governance gaps.
keywords: [audit, integrity, health-check, drift, governance, validation, diagnostic]
category: ia-design
disable-model-invocation: true
---

# IA Stack Audit

Systematic integrity audit for the Claude Code IA stack. Combines structural verification with semantic coherence analysis to surface governance gaps, drift, and latent failures that checklist compliance alone would miss.

**Scope**: `.claude/CLAUDE.md`, `.claude/skill-bank/`, `.claude/skills/`, `.claude/settings.json`, `.claude/scripts/`.

---

## When to Use This Skill

- Before tagging or releasing IA stack changes
- After bulk skill additions, category restructures, or CLAUDE.md rewrites
- When investigating why the stack "feels wrong" (routing misses, gate failures, orphaned skills)
- Periodic health checks (recommended after every 5+ skill modifications)
- When onboarding to a stack you didn't author

---

## Methodology

### Phase 0: Context Extraction

Before auditing, gather environmental signals that reveal what changed and what the operator likely intends to adjust. This phase prevents auditing in a vacuum.

**Gather the following (parallel where possible):**

| Signal Source | What to Extract | Why It Matters |
|---------------|----------------|----------------|
| `git status` + `git diff --stat` scoped to `.claude/` | Which stack files are staged, modified, or untracked | Reveals in-flight changes the audit should account for |
| Recent commit log (last 5 touching `.claude/`) | Pattern of recent stack evolution | Reveals trajectory — are skills being added, merged, restructured? |
| Current conversation context | What task or concern preceded the audit invocation | Reveals the operator's hypothesis about what might be broken |
| `build-skill-tree.py --check` exit code | Whether glossaries are already stale | Fast signal — if stale, structural issues are guaranteed |

**Context synthesis** — Before proceeding, state in 2-3 sentences:
1. What stack areas appear actively changing
2. What the operator's likely concern is (inferred from context)
3. Which audit phases deserve deeper scrutiny based on these signals

> **Reasoning gate**: If you cannot articulate a specific concern or changing area, state that explicitly — "no directional signal detected, running full-spectrum audit." Do not fabricate a hypothesis to appear context-aware.

---

### Phase 1: Structural Integrity

Verify that all stack artifacts conform to their governing specifications. Each check has a defined pass condition — failures are binary, not subjective.

#### 1A: Frontmatter Compliance (all `skill-bank/*/SKILL.md`)

For every leaf skill, verify against the `skill-design` frontmatter spec:

| Field | Requirement | Failure Mode |
|-------|-------------|-------------|
| `name` | Matches directory name, kebab-case, ≤30 chars | Mismatch → discovery breaks |
| `description` | Follows `"{What}. Use when {contexts}."`, ≤120 chars | Bad description → glossary entry is unhelpful |
| `keywords` | 3-7 lowercase terms, no duplicates | Missing → keyword index gaps |
| `category` | Existing category slug | Wrong/missing → skill orphaned from glossaries |
| `disable-model-invocation` | `true` for all leaf skills | Missing → description leaks into system prompt |

**Diagnostic precision**: For each failure, name the specific skill and the specific field. Do not report "some skills have issues" — enumerate.

#### 1B: Glossary Freshness

Compare generated glossaries (`skills/*/SKILL.md`) against current skill-bank state:

- Run `build-skill-tree.py --check` (or simulate by comparing skill counts and descriptions)
- A skill exists in skill-bank with `category: X` but doesn't appear in `skills/X/SKILL.md` → **stale glossary**
- A skill appears in a glossary but no longer exists in skill-bank → **orphaned reference**

#### 1C: Kernel Compliance (CLAUDE.md)

Evaluate against K1-K4 gates:

| Gate | Check |
|------|-------|
| K1 | Total line count ≤400 |
| K2 | Every rule has an enforcement mechanism (settings.json permission, gate, or tool check) |
| K3 | No methodology blocks >10 lines (should be extracted to skills) |
| K4 | Any tool patterns used in new rules are covered by settings.json permissions |

#### 1D: Permission Matrix Coverage

Cross-reference CLAUDE.md commands and skill-referenced operations against `settings.json`:

- Commands mentioned in CLAUDE.md §3 → must have corresponding allow/ask/deny entries
- Destructive operations referenced anywhere → must be in `ask` or `deny`, never `allow`

---

### Phase 2: Semantic Coherence

Structural compliance is necessary but insufficient. A stack can pass every frontmatter check while being semantically incoherent. This phase requires genuine analytical reasoning — not pattern matching.

#### 2A: Routing Coverage Analysis

**Analyze** the relationship between CLAUDE.md §4 routing table and the skill bank:

- For each subagent type in §4: does the skill bank contain methodology that the subagent would need? Identify gaps.
- For each skill in the bank: is there a routing path that would cause it to be loaded? Identify unreachable skills.
- **Contrast** the Delegation Rules against the routing table — are they consistent? Can a task match one but not the other?

> **Reasoning anchor**: For each gap found, state what concrete failure mode it enables. "Skill X is unreachable" is incomplete — "Skill X is unreachable, which means tasks involving {domain} will proceed without {methodology}, risking {consequence}" is diagnostic.

#### 2B: Cross-Reference Integrity

Skills frequently reference other skills by name (e.g., "load `skill-design`", "apply `ia-quality-gates`"). Verify:

- Every skill name referenced in another skill actually exists in skill-bank
- Referenced skills are in compatible categories (a `testing` skill shouldn't reference an `ia-design` skill unless the connection is justified)
- No circular reference chains that would create infinite loading loops

#### 2C: Keyword Coherence

Apply T3 and T4 gates across the full skill bank:

| Gate | What to Check | Threshold |
|------|--------------|-----------|
| T3: Category Fit | Each skill shares >50% keyword overlap with at least one category sibling | <30% overlap → misplaced |
| T4: No Duplication | No skill has >40% keyword overlap with a skill in a *different* category | >40% → merge or differentiate |

**For any T4 violation**: Before recommending a merge, analyze whether the skills serve genuinely different purposes despite keyword similarity. State the distinguishing characteristic. If none exists, recommend merge with specifics.

#### 2D: SPOF Assessment

Identify Single Points of Failure — assets where:
- Dependency count > 10 (many other assets reference it)
- No fallback exists if the asset fails or is removed
- Modification would cascade across multiple categories

For each SPOF, assess whether the current stack has adequate protection (e.g., is the asset versioned, is there a backup pathway, is it in the `ask` permission tier for modifications).

---

### Phase 3: Adversarial Self-Check

This phase prevents the audit from degenerating into confirmation theater. You must reason against your own findings.

#### 3A: Completeness Challenge

Answer these three questions — each requires a substantive, non-vacuous response:

1. **What category of failure would this audit methodology miss?** Name a specific blind spot, not a generic "edge cases." If this methodology checked for X, Y, Z — what failure lives in the space between them?

2. **Which of Phase 2's findings has the weakest evidence?** Identify the finding you're least confident about. State what additional data would strengthen or refute it.

3. **If an adversary wanted to introduce a subtle governance violation that passes this audit, how would they do it?** Describe the attack vector. If the answer is trivial, the audit has a gap — note it.

#### 3B: Context Alignment Verification

Revisit Phase 0's context synthesis. Now that the audit is complete:

- Did the findings address the operator's likely concern (as inferred in Phase 0)?
- If not, was the concern unfounded, or did the audit fail to cover the relevant area?
- Are there findings that the operator didn't expect but should prioritize?

---

### Phase 4: Report and Remediate

#### Report Format

```markdown
## IA Stack Audit Report

### Context
{Phase 0 synthesis — 2-3 sentences on what's changing and why this audit matters now}

### Findings

| # | Severity | Category | Finding | Affected Assets | Confidence |
|---|----------|----------|---------|----------------|------------|
| 1 | CRITICAL/HIGH/MEDIUM/LOW | Phase.Check | {concise finding} | {file paths} | HIGH/MED/LOW |

### Remediation Priority

{Ordered list — most impactful fixes first, grouped by effort level}

#### Immediate (fix now)
- [ ] {finding #} — {specific action} → load `{skill}` for methodology

#### Deferred (fix in next session)
- [ ] {finding #} — {specific action}

#### Monitoring (watch, don't fix yet)
- {finding #} — {why it's not actionable yet}

### Blind Spots
{Phase 3A answers — what this audit might have missed}

### Suggested Skill Activations
{Based on findings, which skills should be loaded next to address issues}
```

#### Severity Definitions

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Stack functionality is broken — glossaries don't load, routing fails, permissions block required operations |
| **HIGH** | Governance gap actively causing quality issues — skills unreachable, gates not enforced, cross-references broken |
| **MEDIUM** | Latent issue that will cause problems under specific conditions — keyword drift, category near capacity, SPOF without protection |
| **LOW** | Style or convention violation with no functional impact — description slightly over 120 chars, keyword could be more specific |

#### Confidence Calibration

Rate each finding's confidence:

| Level | Criteria |
|-------|----------|
| **HIGH** | Finding verified by tool output or direct file inspection — reproducible |
| **MED** | Finding based on pattern analysis — likely correct but edge cases may exist |
| **LOW** | Finding based on inference or indirect evidence — needs verification before acting |

> State what additional evidence would raise LOW findings to MED or HIGH.

---

## Skill Activation Suggestions

Based on common audit findings, the audit report should suggest loading specific skills:

| Finding Pattern | Suggested Skill | Why |
|----------------|----------------|-----|
| Frontmatter violations | `skill-design` | Contains the authoritative frontmatter spec |
| Gate failures | `ia-quality-gates` | Contains all gate definitions (S/R/K) |
| Routing inconsistencies | `agent-routing` | Contains routing heuristics and quality standards |
| CLAUDE.md modifications needed | `stack-stability` | Impact assessment before modifying kernel |
| Keyword/category drift | `skill-design` § Category Taxonomy | Category rules and operations |
| Permission gaps | `ia-stack-ops` § Workflow C | Kernel rule modification with K4 check |

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| **Checklist theater** — Running gates without examining actual content | Passes skills that structurally comply but are semantically empty | Phase 2 requires genuine analysis of content, not just field presence |
| **Bulk-pass bias** — Reporting "52/53 skills pass" without detailing the failure | The one failure may be the critical one | Every failure must be individually diagnosed with affected assets |
| **Generic findings** — "Some cross-references may be stale" | Unactionable — operator can't fix "some" | Name the specific reference, the specific file, the specific line |
| **Missing context** — Auditing without Phase 0 context extraction | Audit misses the reason it was invoked, produces irrelevant findings | Phase 0 is not optional — even "no signal" must be explicitly stated |
| **Skipping Phase 3** — Omitting adversarial self-check because "everything looks fine" | Confirmation bias — audits that find nothing are the most suspect | Phase 3 is mandatory regardless of finding count |
| **Over-remediation** — Recommending fixes for LOW findings as immediate actions | Wastes operator effort on non-issues, buries important findings | Severity-tiered remediation: only CRITICAL/HIGH are immediate |
