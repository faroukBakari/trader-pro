---
disable-model-invocation: true
name: ia-validation
description: Artifact validation for skills, routing, and rules. Load when checking boundary compliance or running audits
keywords: [validation, boundary, compliance, artifacts, separation]
category: ia-design
---

# IA Validation

Structured workflow for validating IA stack artifacts against quality gates and boundary separation rules. Produces severity-ranked findings with concrete remediation steps.

---

## When to Use This Skill

- Validating a skill, routing entry, or kernel rule against quality gates
- Checking boundary compliance of IA stack artifacts
- Generating structured validation reports
- Auditing artifact quality after modifications

---

## Methodology

### Phase 1: Load & Classify

1. **Load artifact** — Read the target file
2. **Classify type**:
   - **Skill**: `SKILL.md` filename in `skill-bank/`
   - **Routing entry**: Row in CLAUDE.md §4 delegation tables
   - **Kernel rule**: Constraint or convention in CLAUDE.md §1/§3
3. **Select gate set**:
   - Skill → S1–S5 (5 gates)
   - Routing entry → R1–R5 (5 gates)
   - Kernel rule → K1–K4 (4 gates)

### Phase 2: Run Quality Gates

Apply `ia-quality-gates` skill with the selected gate set. Execute ALL gates — no partial runs.

### Phase 2.5: Stack Stability Dimension (Comprehensive Assessments)

For full stack validation (not single-artifact checks), stack stability is a **first-class dimension**:
1. Full dependency graph mapping (count dependents per asset)
2. Stability tier classification (T1-T4 for every asset)
3. SPOF identification (assets with disproportionate centrality)
4. Interface contract risk assessment (frozen surfaces)
5. Skill registry overhead check (total count ≤50 healthy, >65 halt; descriptions ≤2 lines)

Stack stability assesses whether the stack can safely evolve — more important than whether individual assets pass quality gates.

### Phase 3: Boundary Separation Test

Apply the separation test to every section of the artifact:

| Content Type | Correct Layer | Violation If Found In |
|-------------|---------------|----------------------|
| Constraints, conventions, routing | **CLAUDE.md kernel** | Skill (unless it's methodology about applying constraints) |
| Reusable methodology (>30 lines) | **Skill** | CLAUDE.md kernel (inflates always-loaded cost) |
| Auto-generated index | **Glossary** | Hand-edited (overwritten by tree builder) |

**Boundary test questions:**
- Is this methodology in CLAUDE.md? → Extract to skill
- Is this routing logic in a skill? → Move to CLAUDE.md §4
- Is this index content hand-edited? → Should be auto-generated via `build-skill-tree.py`

### Phase 4: Severity Classification & Remediation

| Violation Type | Severity | Remediation |
|----------------|----------|-------------|
| CLAUDE.md contains methodology (>10 lines) | BLOCKING | Extract to skill, keep 1-line reference |
| Skill references specific agent names | HIGH | Remove agent awareness (S1 violation) |
| Skill contains tool-specific instructions | HIGH | Remove tool refs (S2 violation) |
| Routing logic embedded in skill | MEDIUM | Move routing to CLAUDE.md §4 |
| Glossary hand-edited | MEDIUM | Regenerate via `build-skill-tree.py --write` |
| Skill missing `disable-model-invocation` | MEDIUM | Add flag to frontmatter |

---

## Output Format

```markdown
## Validation Report: {artifact name}

**Type**: [Skill/Routing entry/Kernel rule]
**Status**: [PASS | WARNINGS | VIOLATIONS]

### Quality Gates
- S1: Agent-agnostic
- {gate}: **VIOLATION** — {description}
  - **Fix**: {remediation step}

### Boundary Violations
- **{severity}**: {description}
  - **Fix**: {remediation step}

### Recommendations
1. {Prioritized fix}
```

---

## Anti-Patterns

- **Selective gate checking** — Running only structural gates and skipping boundary separation
- **Soft failures** — Noting violations but marking overall status as PASS
- **Wrong gate set** — Applying the wrong S/R/K gate set to an artifact type
- **Systematic sweep** — Run every applicable gate, report every finding, offer every fix
