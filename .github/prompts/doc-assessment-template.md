<!-- Version: 2.0 | Last updated: 2026-02-01 -->
# Documentation Assessment Template

Quick reference for `doc-assessment.prompt.md` output formats. The assessment agent reads this at runtime.

---

## Plan File Template

Use this structure for `docs/tmp/documentation-assessment-plan.md`:

```markdown
# Documentation Assessment Plan
**Generated**: [DATE]
**Phase 1 Status**: Approved

---

## Section 1: Approved Refactoring Report

[Copy discrepancy table and structural proposals from Phase 1 output]

---

## Section 2: Wave Plan

### Wave 1: Module-Level (The Truth)
Update docs inside `src/` folders directly against local code.

- [ ] **[ACTION]**: `path/to/doc.md`
  - **Verification Source**: `src/path/to/code/`
  - **Status**: [UP-TO-DATE | INCONSISTENT | NEEDS-VERIFICATION]
  - **Findings**: [Summary of issues]

### Wave 2: Sub-System (The Bridge)
Update integration docs, API contracts, and cross-module flows.

- [ ] **[ACTION]**: `backend/docs/ARCHITECTURE.md`
  - **Verification Source**: `backend/src/trading_api/`
  - **Depends On**: Wave 1 completion

### Wave 3: Project-Level (The Global)
Update root README and high-level architecture docs.

- [ ] **[ACTION]**: `README.md`
  - **Verification Source**: Entire project structure
  - **Depends On**: Wave 2 completion

### Wave 4: Guide Regeneration
- [ ] Regenerate `docs/DOCUMENTATION-GUIDE.md`

---

## Section 3: Execution Instructions

### Per-Document Workflow
1. Read verification source (code) first
2. Compare doc claims against code behavior
3. Update documentation to match code
4. Validate all relative links resolve
5. Mark checkbox complete

### Doc Standards
| Technique | Format |
|-----------|--------|
| Metadata | `<!-- METADATA: scope=..., last_verified=YYYY-MM-DD -->` |
| Decisions | `**[DECISION]**: [choice] — [rationale]` |
| Markers | `[PERFORMANCE]`, `[PITFALL]`, `[SECURITY]`, `[DEPRECATED]` |

### Post-Wave Checklist
- [ ] All checkboxes in wave marked complete
- [ ] Cross-reference tables updated
- [ ] All internal links validated

---

## Section 4: Final Report Instructions

After all waves complete, generate `docs/tmp/documentation-assessment-report.md`:

[template provided in main prompt]
```

---

## Reference Tables

### Document Status

| Status | Icon | Meaning |
|--------|------|---------|
| UP-TO-DATE | - | All references verified |
| INCONSISTENT | ! | Deprecated refs, terminology conflicts |
| NEEDS-VERIFICATION | ? | Complex cross-refs needing validation |
| EXTERNAL | ext | Third-party docs |

### Structural Actions

| Action | When to Use |
|--------|-------------|
| RETAIN | No changes needed |
| UPDATE | Content updated, location unchanged |
| MERGE | Multiple docs describe same code module |
| SPLIT | Single doc covers unrelated code paths |
| MOVE | Doc location misaligned with code |
| DELETE | Ghost doc, no valid verification source |

### Gap Categories

| Type | Definition |
|------|------------|
| Ghost Doc | Doc describes code that no longer exists |
| Dark Code | Significant code with zero doc coverage |
| Knowledge Drift | Doc claims contradict code reality |
| Stale Reference | Links to moved/renamed files |
