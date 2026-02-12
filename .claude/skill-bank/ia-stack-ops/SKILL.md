---
name: ia-stack-ops
description: Unified IA modification workflow. Load when creating skills, adding subagent types, or modifying CLAUDE.md rules
keywords: [ia-stack, governance, skill-creation, routing, stack-modification, quality-gates, health-check]
category: ia-design
disable-model-invocation: true
---

# IA Stack Operations

Unified workflow for modifying the Claude Code IA stack. Replaces multi-phase orchestration with four focused workflows matching the two artifact types: **skills** and **CLAUDE.md entries**.

---

## When to Use This Skill

- Creating a new skill
- Adding or modifying a subagent type in CLAUDE.md §4
- Modifying CLAUDE.md kernel rules
- Running a stack health check / consistency audit

---

## Artifact Types (Claude Code)

| Artifact | Location | Governance |
|----------|----------|------------|
| **Skill** | `.claude/skill-bank/{name}/SKILL.md` | `skill-design` frontmatter spec + S1-S5 gates |
| **Routing entry** | CLAUDE.md §4 table row | R1-R5 gates |
| **Kernel rule** | CLAUDE.md §1/§3 | K1-K4 gates |

---

## Workflow A: Create a New Skill

1. **Classify**: Confirm artifact = skill (methodology, not config)
2. **Check overlap**: `Grep` skill-bank for similar keywords/names. If >40% overlap with existing skill → merge or differentiate
3. **Create**: Write `.claude/skill-bank/{name}/SKILL.md` following `skill-design` frontmatter spec:
   - `name`: kebab-case, ≤30 chars, globally unique
   - `description`: `"{What}. Use when {contexts}."` ≤120 chars
   - `keywords`: 3-7 terms
   - `category`: existing category or justify new
   - `disable-model-invocation: true`
4. **Validate**: Load `ia-quality-gates` → run S1-S5:
   - S1: Agent-agnostic? (no agent names, no tool defs)
   - S2: Tool-agnostic? (no tool-specific instructions)
   - S3: Method-focused? (step-by-step procedures)
   - S4: Portable? (no project-specific paths)
   - S5: Progressive disclosure? (description present, loads on demand)
5. **Boundary test**: Load `ia-validation` → clean separation:
   - "Could this live in CLAUDE.md instead?" → if yes, it should
   - "Is this methodology or configuration?" → methodology = skill
6. **Regenerate**: `python3 .claude/scripts/build-skill-tree.py --write`
7. **Verify**: Read generated glossary → confirm skill appears

---

## Workflow B: Add/Modify a Subagent Type

1. **Assess impact**:
   - `Grep` CLAUDE.md for current entry
   - `Grep` skill-bank for references to this subagent type
   - Classify: additive (new type) vs. structural (change existing)
2. **Validate routing** (R1-R5 from `ia-quality-gates`):
   - R1: Clear trigger signal (when to use this type)
   - R2: Model selection justified (Opus/Sonnet/Haiku)
   - R3: No overlap with existing types
   - R4: Description is actionable
   - R5: Consistent with Delegation Rules
3. **Edit**: Update CLAUDE.md §4 table + Delegation Rules if routing changes
4. **Verify**: Read modified section, check consistency

---

## Workflow C: Modify CLAUDE.md Kernel Rules

1. **Load**: `stack-stability` skill for impact assessment
2. **Impact assessment**:
   - Dependency scan: what references this rule?
   - Classify tier:
     - **T1** (cosmetic): formatting, wording — proceed
     - **T2** (behavioral): changes how agents work — present impact, get approval
     - **T3** (structural): affects multiple skills/workflows — full impact map + approval
     - **T4** (breaking): reverses existing convention — HALT, present alternatives
3. **Validate** (K1-K4 from `ia-quality-gates`):
   - K1: CLAUDE.md stays under 400 lines
   - K2: New rule has enforcement mechanism
   - K3: No methodology in CLAUDE.md (belongs in skills)
   - K4: Settings.json permissions cover new patterns
4. **Edit**: Apply change to CLAUDE.md
5. **Verify**: `Grep` for inconsistencies with skill-bank content

---

## Workflow D: Stack Health Check

Run parallel verification tasks:

**Structural checks:**

| Check | Method | Pass Condition |
|-------|--------|----------------|
| **Frontmatter** | Scan all `skill-bank/*/SKILL.md` | All have valid frontmatter with required fields |
| **Glossary sync** | `build-skill-tree.py --check` | Exit 0 (no drift between generated and existing glossaries) |
| **Routing consistency** | Cross-check §4 types with Delegation Rules | Every type appears in both table and rules |
| **Category health** | Count skills per category | 3-12 skills per category, no orphans |

**Cost/efficiency checks:**

| Check | Method | Pass Condition |
|-------|--------|----------------|
| **Kernel size** | `wc -l .claude/CLAUDE.md` | ≤400 lines (Anthropic recommends ~500 max) |
| **Kernel tokens** | `wc -w .claude/CLAUDE.md` (word count as proxy) | ≤5,000 words (~4k tokens; keeps always-loaded cost <2% of 200k context) |
| **Skill file size** | `wc -l` on each `skill-bank/*/SKILL.md` | No skill >500 lines (Anthropic guideline for on-demand loaded files) |

**Report format**:

```markdown
## Stack Health Report
| Check | Status | Finding |
|-------|--------|---------|
| Frontmatter | ✅/❌ | {detail} |
| Glossary sync | ✅/❌ | {detail} |
| Routing | ✅/❌ | {detail} |
| Categories | ✅/❌ | {detail} |
| Kernel size | ✅/❌ | {line count}/400 |
| Kernel tokens | ✅/❌ | {word count}/5000 |
| Skill file size | ✅/❌ | {largest skill}: {line count}/500 |
```

---

## Decision: Skill vs. CLAUDE.md Entry

| Question | If YES → | If NO → |
|----------|----------|---------|
| Is it a reusable methodology (>30 lines)? | Skill | CLAUDE.md rule or routing entry |
| Does it apply to multiple task types? | Skill | Specific routing entry |
| Is it a constraint/convention (<5 lines)? | CLAUDE.md §4 rule | Skill |
| Is it about when to delegate? | CLAUDE.md §4 routing | Skill |
| Is it about how to do something? | Skill | CLAUDE.md rule |

---

## Anti-Patterns

| Anti-Pattern | Why Wrong | Fix |
|-------------|-----------|-----|
| Creating agent files (`.agent.md`) | No agent files in Claude Code | Use skills + CLAUDE.md routing |
| Methodology in CLAUDE.md | Inflates kernel, always-loaded cost | Extract to skill, reference via glossary |
| Routing without trigger signal | Subagent type never gets invoked | Add clear "when to use" in R1 |
| Skipping `build-skill-tree.py` after skill changes | Glossary desync | Always regenerate after add/remove |
| Modifying glossaries by hand | Overwritten by tree builder | Edit leaf skills, then rebuild |
