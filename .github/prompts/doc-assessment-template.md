# Documentation Assessment Template

Reference template for `doc-assessment.prompt.md`. The assessment agent reads this at runtime.

---

## Section 1: Documentation Refactoring Report (Template)

### Discrepancy Table

| Document          | Verification Source | Status          | Drift Type | Finding                 |
| ----------------- | ------------------- | --------------- | ---------- | ----------------------- |
| `path/to/doc.md`  | `src/module/`       | ⚠️ INCONSISTENT | Knowledge  | Doc says X, code uses Y |
| `path/to/doc2.md` | `src/other/`        | ✅ UP-TO-DATE   | -          | All references verified |

### Structural Proposals

| Action    | Source                  | Target                       | Rationale                 |
| --------- | ----------------------- | ---------------------------- | ------------------------- |
| **MERGE** | `doc-a.md` + `doc-b.md` | `combined.md`                | Both describe same module |
| **SPLIT** | `large-doc.md`          | `api.md` + `architecture.md` | Covers unrelated concerns |
| **MOVE**  | `docs/impl.md`          | `src/module/README.md`       | Align with code location  |

---

## Section 2: Wave Plan Structure

### Wave 1: Module-Level (The Truth)

Update docs inside `src/` folders directly against local code.

- [ ] **[ACTION]**: `path/to/doc.md`
  - **Verification Source**: `src/path/to/code/`
  - **Status**: [UP-TO-DATE | INCONSISTENT | NEEDS-VERIFICATION]
  - **Findings**: [Summary of issues found]

### Wave 2: Sub-System (The Bridge)

Update integration docs, API contracts, and cross-module flows.

- [ ] **[ACTION]**: `backend/docs/ARCHITECTURE.md`
  - **Verification Source**: `backend/src/trading_api/`
  - **Depends On**: Wave 1 completion

### Wave 3: Project-Level (The Global)

Update root README and high-level architecture docs.

- [ ] **[ACTION]**: `README.md`
  - **Verification Source**: Entire project structure
  - **Depends On**: Wave 1 + 2 completion

### Wave 4: Guide Regeneration

Regenerate `docs/DOCUMENTATION-GUIDE.md` to reflect new structure.

---

## Section 3: Execution Instructions (For Follow-Plan Agent)

You are a technical documentation specialist. Execute this plan step-by-step.

### Per-Document Workflow

1. **Read Code First**: Analyze the "Verification Source" before touching the doc
2. **Identify Drift**: Compare doc claims against actual code behavior
3. **Apply Fixes**: Update documentation to match code reality
4. **Validate Links**: Ensure all relative links resolve correctly
5. **Update Checkbox**: Mark task complete in this file

### AI-Readable Standards (Apply to Every Doc)

| Technique        | Format                                                          |
| ---------------- | --------------------------------------------------------------- |
| Metadata Header  | `<!-- METADATA: scope=..., priority=..., last_verified=... -->` |
| ADR Callouts     | `**[DECISION]**: [choice] [rationale] [alternatives-rejected]`  |
| Semantic Markers | `[PERFORMANCE]`, `[PITFALL]`, `[SECURITY]`, `[DEPRECATED]`      |
| Visuals          | Mermaid diagrams > Tables > Bullet points > Paragraphs          |
| Code Snippets    | Small illustrative snippets with source file reference          |

### Post-Wave Checklist

- [ ] All checkboxes in wave marked complete
- [ ] Section numbering updated
- [ ] Cross-reference tables updated
- [ ] All internal links validated (relative paths only)

---

## Section 4: Final Report Structure

After all waves complete, generate `docs/tmp/documentation-assessment-report.md`:

```markdown
# Documentation Assessment Report

**Generated**: [DATE]
**Agent**: doc-assessment

## Executive Summary

- Files assessed: X
- Files updated: Y
- Merges performed: Z
- Splits performed: W

## Structural Changes Applied

[Summary from Section 1 proposals]

## Findings by Category

### Ghost Docs (Docs describing deleted code)

- [List]

### Dark Code (Code with no documentation)

- [List]

### Knowledge Drift (Doc ≠ Code)

- [List]

### Broken Links

- [List]

## Recommendations

[Prioritized list of follow-up actions]
```

---

## Assessment Categories Reference

### Document Status

| Status             | Icon | Meaning                                              |
| ------------------ | ---- | ---------------------------------------------------- |
| UP-TO-DATE         | ✅   | All references verified, no issues                   |
| INCONSISTENT       | ⚠️   | Deprecated refs, terminology conflicts, broken links |
| NEEDS-VERIFICATION | 🔍   | Missing dates, complex cross-refs needing validation |
| EXTERNAL           | 📦   | Third-party docs (verify references only)            |

### Structural Actions

| Action | Icon | Meaning                             |
| ------ | ---- | ----------------------------------- |
| RETAIN | 🔒   | Document unchanged                  |
| UPDATE | 📝   | Content updated, location unchanged |
| MERGE  | 🔄   | Combined into another document      |
| SPLIT  | ✂️   | Divided into multiple documents     |
| MOVE   | 📁   | Relocated to different path         |
| DELETE | 🗑️   | Removed (ghost doc)                 |

---

## Gap Analysis Categories

| Gap Type            | Definition                                       | Example                                |
| ------------------- | ------------------------------------------------ | -------------------------------------- |
| **Ghost Doc**       | Doc describes code/feature that no longer exists | `OAUTH.md` but OAuth removed           |
| **Dark Code**       | Significant code logic with zero doc footprint   | Complex service with no README         |
| **Knowledge Drift** | Doc claims contradict actual code                | Doc: "uses REST", Code: uses WebSocket |
| **Stale Reference** | Links to moved/renamed files                     | Link to `old-path.md` that moved       |
