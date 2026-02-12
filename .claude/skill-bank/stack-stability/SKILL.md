---
name: stack-stability
description: Impact assessment for IA stack modifications. Load when modifying CLAUDE.md, restructuring skills, or changing routing
keywords: [stability, impact-assessment, dependency, risk, change-management, stack-health]
category: ia-design
disable-model-invocation: true
---

# Stack Stability

Methodology for assessing the impact of changes to the IA stack before applying them. Prevents cascading breakage from modifications to high-dependency assets.

---

## When to Use This Skill

- Before modifying CLAUDE.md immutable rules (§4)
- Before restructuring skill categories or merging skills
- Before changing subagent routing that affects multiple workflows
- When evaluating whether a proposed change is safe to apply
- During stack health checks (Workflow D in `ia-stack-ops`)

---

## Methodology

### Step 1: Map Dependencies

For the asset being modified, identify what depends on it:

| Asset Type | Dependency Sources | How to Scan |
|------------|-------------------|-------------|
| CLAUDE.md §4 rule | Skills referencing the rule, workflows assuming it | `Grep` skill-bank + CLAUDE.md for rule keywords |
| CLAUDE.md §4 entry | Skills mentioning the subagent type, Delegation Rules | `Grep` skill-bank for type name |
| Skill | Other skills cross-referencing it, CLAUDE.md mentions | `Grep` skill-bank + CLAUDE.md for skill name |
| Category | All skills with that `category` frontmatter value | `Grep` skill-bank for `category: {name}` |

**Output**: Dependency count + list of dependent assets.

### Step 2: Classify Change Tier

| Tier | Criteria | Example | Gate |
|------|----------|---------|------|
| **T1 — Cosmetic** | Wording, formatting, no behavioral change | Fix typo in skill description | Proceed |
| **T2 — Behavioral** | Changes how one workflow operates | Update model tier for a subagent type | Present impact summary, get approval |
| **T3 — Structural** | Affects multiple skills or workflows | Rename a category, merge two skills | Full impact map + explicit approval |
| **T4 — Breaking** | Reverses an existing convention or removes an asset | Remove a §4 immutable rule | HALT — present alternatives, require explicit override |

**Tier escalation rule**: If dependency count > 5, escalate one tier up.

### Step 3: Impact Map (T2+ only)

For T2 and above, produce an impact map:

```markdown
## Impact Assessment: {change description}

**Tier**: T{N} — {tier name}
**Asset**: {file path}
**Change**: {what will change}

### Dependencies ({count})
| Dependent Asset | How It's Affected | Risk |
|----------------|-------------------|------|
| {asset path} | {description} | Low/Med/High |

### Blast Radius
- **Direct**: {N} assets reference this directly
- **Indirect**: {N} assets depend on direct dependents
- **Total**: {N} assets potentially affected

### Recommendation
{Proceed / Proceed with caution / Requires approval / HALT}
```

### Step 4: SPOF Detection

Single Points of Failure are assets where:
- Dependency count > 10
- No alternative exists if the asset is removed
- Multiple workflows break simultaneously if it changes

**Known SPOFs in this stack**:
- `CLAUDE.md` itself (all workflows depend on kernel)
- `skill-design` (all skill creation depends on it)
- `build-skill-tree.py` (all glossary generation depends on it)

Changes to SPOFs always require T3+ assessment.

### Step 5: Challenge Gate (T2+ only)

Before applying any T2+ change, adversarially challenge it. Every claim about "gaps", "missing capabilities", or "needed improvements" must survive these questions — if it can't, it's not worth the stability cost.

**Value challenge** — kill completeness-driven changes:

| Question | If No → |
|----------|---------|
| Does this solve a problem that has **actually occurred**? | Drop it — theoretical gaps aren't gaps |
| Can you name a **concrete session** where the absence caused a real failure? | Drop it — you're optimizing for paper coverage |
| Would a user notice if this change was never made? | Drop it — invisible improvements are over-engineering |

**Over-engineering guard** — kill accidental complexity:

| Question | If No → |
|----------|---------|
| Is this the **minimum viable change**? | Shrink scope until it is |
| Could the same outcome be achieved by **doing nothing** + relying on existing behavior? | Do nothing |
| Are you adding structure to a problem that occurs **less than once a month**? | Skip — ad-hoc handling is cheaper |

**Cursor balance** — constraints are spectrums, not switches:

| Cursor | Too Tight | Too Loose | Check |
|--------|-----------|-----------|-------|
| Specificity | Rigid rules that break on edge cases | Vague guidance that gets ignored | Does this constrain behavior **only where variance actually hurts**? |
| Process | Gates that slow every change (even trivial) | No gates, silent breakage | Is the gate proportional to the **blast radius**? |
| Coverage | Every edge case documented | Only happy path | Does this cover **observed** failure modes, not hypothetical ones? |

**Verdict**: Only changes that pass all three sections proceed. Annotate the impact map with which challenges the change survived and why.

---

## Quick Assessment (for inline use)

When full assessment is overkill, use this 3-question triage:

1. **How many assets reference this?** → `Grep` for the name/keyword
   - 0-2: Low risk, proceed
   - 3-5: Medium risk, note in commit
   - 6+: High risk, full assessment
2. **Is this a convention or implementation?**
   - Convention (§4 rule, naming pattern): Higher risk — behavior is distributed
   - Implementation (skill body, routing entry): Lower risk — behavior is localized
3. **Is the change reversible?**
   - Yes (can revert via git): Lower risk
   - No (triggers downstream regeneration): Higher risk

---

## Anti-Patterns

| Anti-Pattern | Why Wrong | Fix |
|-------------|-----------|-----|
| Modifying CLAUDE.md §4 without scanning dependents | Rule changes cascade silently | Always run Step 1 dependency scan |
| Treating all changes as T1 | Underestimates blast radius | Honestly classify using Step 2 criteria |
| Skipping SPOF check on core assets | Core changes can break everything | Always check Step 4 for CLAUDE.md, skill-design, build script |
| Assessing impact after making the change | Can't get approval for a fait accompli | Always assess before editing |
