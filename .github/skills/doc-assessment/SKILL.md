---
name: doc-assessment
description: Documentation health assessment across 6 quality dimensions with progressive disclosure. Use when auditing doc quality, scoring documentation health, or identifying documentation gaps.
---

# Documentation Health Assessment

Evaluate documentation quality across 6 dimensions with progressive disclosure and token-efficient reading patterns. Produces a scorecard, gap summary, and prioritized remediation plan.

---

## When to Use This Skill

- Periodic documentation health audits
- Before major documentation refactors
- After significant code changes to verify doc accuracy
- When evaluating documentation coverage for a module or subsystem

---

## Methodology

### Phase 1: Scope Selection

Choose assessment depth based on need — never read everything up front.

| Scope Tier | Target | Reading Strategy |
|------------|--------|------------------|
| **Quick** | Single directory or module | Read 3-5 doc files directly |
| **Focused** | Subsystem (backend, frontend, or module cluster) | Use `DOCUMENTATION-GUIDE.md` to identify 5-10 relevant docs |
| **Full** | Entire documentation corpus | Progressive — inventory first, then deepen into low-scoring dimensions |

**Steps:**
1. Determine scope from user input (default: Focused on `docs/` root)
2. Read `docs/DOCUMENTATION-GUIDE.md` to understand doc structure and relationships
3. For Quick/Focused: list target files directly. For Full: build inventory via search

### Phase 2: Progressive Assessment (6 Dimensions)

Score each dimension 1-10. **Read only enough to score** — do not deep-read entire files.

| Dimension | What to Check | Scoring Heuristic |
|-----------|---------------|-------------------|
| **Comprehensiveness** | Are major components documented? | grep for module/feature names in docs; count coverage gaps |
| **Accuracy** | Does content match codebase state? | Spot-check 3-5 file paths, API names, or patterns mentioned in docs |
| **Discoverability** | Is there an index? Clear navigation? Cross-links? | Check `DOCUMENTATION-GUIDE.md` quality + doc titles |
| **Maintainability** | Are docs near code? Update triggers clear? | Check if module docs live in module dirs vs. centralized |
| **Completeness** | Quickstarts, architecture, API refs, troubleshooting? | Check doc type coverage against expected doc categories |
| **Consistency** | Same style/format across docs? | Compare heading structure, tone, formatting across 3-4 docs |

**Progressive disclosure rule:** If a dimension scores ≥ 8, move on. Only deep-read into dimensions scoring < 7 — those need gap mapping.

### Phase 3: Gap Mapping (Low-Scoring Dimensions Only)

For each dimension scoring < 8, identify specific gaps:

**Per gap, capture:**
- What's missing, wrong, or outdated
- Which file and section (or absence of file)
- Severity: Critical (blocks understanding) / High (creates confusion) / Medium (gaps) / Low (polish)

**Token budget:** Limit gap investigation to 3-5 deep file reads per dimension. Use grep/search to find gaps instead of reading entire files.

### Phase 4: Remediation Plan

Organize fixes by effort-vs-impact:

| Category | Criteria | Action Pattern |
|----------|----------|----------------|
| **Quick Wins** | ≤ 1 hour, single file, high impact | Fix immediately or first |
| **Strategic** | Multi-file, architecture-level | Plan before executing |
| **Backlog** | Low urgency or large scope | Track for later |

Each remediation item must include: file path, specific action, estimated effort, and which dimension it improves.

---

## Scorecard Template

```markdown
## Documentation Health Scorecard

| Dimension | Score | Status |
|-----------|-------|--------|
| Comprehensiveness | /10 | |
| Accuracy | /10 | |
| Discoverability | /10 | |
| Maintainability | /10 | |
| Completeness | /10 | |
| Consistency | /10 | |
| **Overall** | **/10** | |

Status: 🟢 8-10 | 🟡 6-7 | 🔴 < 6
```

## Gap Summary Template

```markdown
| Dimension | Gap | Severity | Remediation |
|-----------|-----|----------|-------------|
| {dim} | {what's missing/wrong} | {Critical/High/Med/Low} | {specific fix} |
```

## Remediation Plan Template

```markdown
### Quick Wins
1. [ ] {action} — {file} ({effort}, improves {dimension})

### Strategic
2. [ ] {action} — {scope} ({effort}, improves {dimensions})

### Backlog
3. [ ] {action} — ({effort})
```

---

## Anti-Patterns

- **Reading everything first** — Wastes tokens. Use progressive disclosure: inventory → score → deep-read only low-scoring areas
- **Scoring without evidence** — Every score must reference at least one checked file or search result
- **Vague remediation** — "Improve docs" is useless. Specify file, section, and action
- **Assessing generated code docs** — Skip `*_generated/` directories entirely
- **Deep-reading high-scoring dimensions** — If it scores 8+, move on. Spend tokens where they matter
