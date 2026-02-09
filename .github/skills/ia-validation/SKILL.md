---
name: ia-validation
description: Validation workflow for IA stack artifacts (agents, subagents, prompts, skills). Use when validating existing artifacts, checking boundary compliance, classifying artifact types, or generating structured validation reports with severity-ranked findings.
---

# IA Validation

Structured workflow for validating existing agentic design artifacts against quality gates and boundary separation rules. Produces severity-ranked findings with concrete remediation steps.

---

## When to Use This Skill

- Validating an existing agent, subagent, prompt, or skill against quality gates
- Checking boundary compliance of IA stack artifacts
- Generating structured validation reports
- Auditing artifact quality after modifications

---

## Methodology

### Phase 1: Load & Classify

1. **Load artifact** — Read the target file
2. **Classify type**:
   - **Subagent**: `user-invokable: false` in frontmatter OR `.sub.agent.md` extension
   - **Agent**: `.agent.md` extension without subagent markers
   - **Prompt**: `.prompt.md` extension
   - **Skill**: `SKILL.md` filename
3. **Select gate set**:
   - Agent → A1–A9 + RV1–RV4 (13 gates)
   - Subagent → A1–A9 + SA-1–SA-7 (16 gates)
   - Prompt → P1–P6 (6 gates)
   - Skill → S1–S5 (5 gates)

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
| "What user wants" (task context) | **Prompt** | Agent, Skill, Subagent |
| "How to behave" (operational rules) | **Agent** | Prompt |
| "Repeatable method" (>30 lines inline) | **Skill** | Prompt, Agent (inline) |

**Subagent-specific checks:**
- Has `handoffs:` in frontmatter → SA-6 violation
- Has `agents:` in frontmatter → SA-7 violation
- Missing `<caller_protocol>` section → SA-4 violation
- Missing `<output_format>` section → SA-5 violation

### Phase 4: Severity Classification & Remediation

| Violation Type | Severity | Remediation |
|----------------|----------|-------------|
| Prompt contains methodology | BLOCKING | Extract to agent |
| Agent inlines skill methods (>30 lines) | HIGH | Extract to skill |
| Skill references specific agents | HIGH | Remove agent awareness |
| Agent contains task templates | MEDIUM | Move to prompt or generalize |
| Subagent has handoffs | HIGH | Remove — subagents are workers (SA-6) |
| Subagent spawns sub-subagents | HIGH | Remove — depth must stay at 1 (SA-7) |
| Subagent missing caller protocol | MEDIUM | Add `<caller_protocol>` section (SA-4) |
| Subagent missing output contract | MEDIUM | Add `<output_format>` section (SA-5) |

---

## Output Format

```markdown
## Validation Report: {filename}

**Type**: [Agent/Subagent/Prompt/Skill]
**Status**: [✅ PASS | ⚠️ WARNINGS | ❌ VIOLATIONS]

### Quality Gates
- ✅ A1: Structure valid
- ❌ {gate}: **VIOLATION** — {description}
  - **Fix**: {remediation step}

### Boundary Violations
- ❌ **{severity}**: {description}
  - **Fix**: {remediation step}

### Recommendations
1. {Prioritized fix}
```

---

## Anti-Patterns

- ❌ **Selective gate checking** — Running only structural gates and skipping boundary separation
- ❌ **Soft failures** — Noting violations but marking overall status as PASS
- ❌ **SA gate amnesia** — Forgetting SA1-SA7 when artifact is a subagent
- ❌ **Prompt free pass** — Treating prompts as "just text" and skipping P1-P6
- ✅ **Systematic sweep** — Run every applicable gate, report every finding, offer every fix
