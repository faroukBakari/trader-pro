---
disable-model-invocation: true
name: ia-quality-gates
description: Validation gates for IA stack artifacts (skills, routing, rules). Load when creating or validating IA components
keywords: [quality-gates, validation, skills, routing, kernel, governance, ia-stack]
category: ia-design
---

# IA Quality Gates

Systematic validation framework for IA stack artifacts. Gate sets are organized by artifact type.

---

## When to Use This Skill

- **Creating** a new skill — run S1-S5 before output
- **Adding/modifying** a CLAUDE.md §4 routing entry — run R1-R5
- **Modifying** a CLAUDE.md kernel rule — run K1-K4
- **Validating** an existing artifact — run all applicable gates and report

---

## Methodology

### Phase 1: Select Gate Set

| Artifact Type | Gate Set | Total |
|---------------|----------|-------|
| Skill (`SKILL.md`) | S1–S5 | 5 |
| CLAUDE.md routing entry (§4) | R1–R5 | 5 |
| CLAUDE.md kernel rule | K1–K4 | 4 |

### Phase 2: Run Gates

Execute every gate in the applicable set. If ANY gate fails, fix and re-run.

---

## Gate Definitions

### Skill Gates (S1–S5) — Primary artifact type

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **S1: Agent-Agnostic** | No references to specific agents | References "the implement agent" or similar | Remove references |
| **S2: Tool-Agnostic** | No tool-specific instructions | Mentions specific tools or CLI commands | Remove tool refs |
| **S3: Method-Focused** | Contains step-by-step procedures | Describes concepts without actionable steps | Add methodology |
| **S4: Portable** | No project-specific paths or structures | References project-specific paths | Generalize |
| **S5: Progressive Disclosure** | `disable-model-invocation: true`; description in glossary | Missing flag or missing from glossary | Add flag; rebuild tree |

### Routing Gates (R1–R5) — CLAUDE.md §4 entries

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **R1: Trigger Signal** | Entry has clear "Use For" description | Vague or missing use case | Write actionable trigger description |
| **R2: Model Justified** | Model tier matches complexity (Opus=orchestration, Sonnet=execution, Haiku=verification) | Unjustified model tier | Justify or change tier |
| **R3: No Overlap** | Does not duplicate an existing subagent type's scope | >60% overlap with another type | Merge or differentiate |
| **R4: Actionable Description** | Tells main agent what prompt to craft and what context to pass | Generic "does stuff" description | Rewrite with specific guidance |
| **R5: Routing Consistency** | Appears in both §4 Delegation table AND Delegation Rules | Present in table but missing from rules (or vice versa) | Add to both locations |

### Kernel Gates (K1–K4) — CLAUDE.md rules

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **K1: Kernel Size** | CLAUDE.md stays under 400 lines | Adding rule would exceed 400 lines | Extract methodology to skill instead |
| **K2: Enforceable** | Rule has enforcement mechanism (settings.json, gate, or tool check) | Rule says "should" with no enforcement | Add enforcement or demote to skill guidance |
| **K3: No Methodology** | Rule is a constraint/convention, not a procedure | Contains step-by-step workflows (>10 lines) | Extract to skill, keep 1-line reference |
| **K4: Permission Coverage** | New tool patterns covered by settings.json permissions | New tool usage without permission entry | Update settings.json |

---

## Phase 3: Report Results

```markdown
### Quality Gates: {artifact name}
- ✅ S1: Agent-agnostic
- ❌ R3: **FAIL** — Overlaps with existing `research` type
  - **Fix**: Differentiate scope or merge into existing type

### Summary
- **Passed**: 4/5
- **Failed**: 1 (R3)
- **Status**: ❌ REQUIRES FIX
```

---

## Anti-Patterns

- **Selective checking** — ALL gates in the applicable set must pass
- **Assumed compliance** — Verify each gate against actual content
- **Wrong gate set** — Use S/R/K gates for the matching artifact type
- **Soft failures** — Every failure must be resolved before output
