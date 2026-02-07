---
name: skill-learning
description: Captures and formalizes reusable knowledge, methods, or lessons from the current conversation. Trigger this when the user signals that a solution was difficult to achieve, expresses a desire to remember a workflow, highlights a "useful" finding, or asks to consolidate insights (e.g., "what did we learn?"). Use this to convert ad-hoc problem-solving into structured, reusable skills.
---

# Skill Learning

Detect, evaluate, and suggest **reusable method candidates** that emerge from active work. Turns implicit expertise used during a task into explicit, shared organizational knowledge.

---

## When to Use This Skill

- After completing a complex multi-step task that required novel reasoning
- During retrospectives on effort-heavy investigations or implementations
- When the same method pattern appears across multiple tasks
- When evaluating whether a workflow should be formalized as a skill
- Periodically, to audit accumulated context for extraction opportunities

---

## Methodology

### Phase 1: Context Mining

Scan the current working context for **repeatable method patterns**. Look for:

| Signal | What It Indicates |
|--------|-------------------|
| Multi-step reasoning applied to solve a problem | Potential methodology skill |
| Decision tree or heuristic constructed ad-hoc | Potential decision framework skill |
| Checklist mentally followed during a task | Potential validation/quality skill |
| Same approach used across 2+ different tasks | High-value extraction candidate |
| Complex domain knowledge synthesized from research | Potential reference/guide skill |
| Effort-heavy investigation with transferable findings | Knowledge worth preserving |

**Output**: A list of 1-5 skill candidates, each described in one sentence.

### Phase 2: Duplicate Check

For each candidate, verify it doesn't already exist:

1. Compare candidate name against **existing skill names** (exact and synonym match)
2. Compare candidate purpose against **existing skill descriptions** (semantic overlap)
3. Check if an existing skill partially covers the candidate's scope

**Decision table:**

| Finding | Action |
|---------|--------|
| Exact name match exists | ❌ Drop — already exists |
| Description overlap > 70% with existing skill | ❌ Drop — already covered |
| Partial overlap (30-70%) with existing skill | ⚠️ Flag as potential extension to existing skill |
| No meaningful overlap | ✅ Proceed to evaluation |

**IMPORTANT**: Do NOT load full skill files during this phase — compare names and descriptions only. Full skill loading wastes context budget when most candidates will be filtered out.

### Phase 3: Candidate Evaluation

Score each surviving candidate on three dimensions:

#### 3a. Effort Capitalization

How much effort was spent discovering/applying this method?

| Effort Level | Score | Indicators |
|-------------|-------|------------|
| **High** | 3 | Multi-step investigation, research, trial-and-error, >30 min equivalent |
| **Medium** | 2 | Structured reasoning, some research, 10-30 min equivalent |
| **Low** | 1 | Quick application of known patterns, <10 min equivalent |

*Higher effort = more value in capturing it so it's not repeated.*

#### 3b. Usage Frequency

How often would this skill be applied across future tasks?

| Frequency | Score | Indicators |
|-----------|-------|------------|
| **Recurring** | 3 | Applies to a common task type (testing, debugging, reviewing, etc.) |
| **Periodic** | 2 | Applies to tasks that occur regularly but not frequently |
| **Rare** | 1 | Applies to niche or one-off scenarios |

#### 3c. Portability

How many different agents/contexts could benefit?

| Portability | Score | Indicators |
|-------------|-------|------------|
| **Universal** | 3 | Any agent could use this method |
| **Multi-agent** | 2 | 2-3 specific agent types would benefit |
| **Single-agent** | 1 | Only useful for one specific agent type |

#### Scoring Decision

| Total Score (3-9) | Recommendation |
|-------------------|----------------|
| **7-9** | ✅ **Learn** — High-value skill worth creating |
| **4-6** | ⚠️ **Consider** — Useful but weigh against skill count overhead |
| **1-3** | ❌ **Skip** — Not worth formalizing |

### Phase 4: User Presentation

Present evaluated candidates to the user for confirmation. Apply `prompt-interaction-design` patterns:

**For 1-3 candidates**: Yes/No per candidate with evaluation summary

```markdown
**Skill Candidates Detected**

Based on the work done, these methods could be extracted as reusable skills:

1. **{Candidate Name}** — {one-line purpose}
   - Effort: {High|Medium|Low} | Frequency: {Recurring|Periodic|Rare} | Portability: {Universal|Multi|Single}
   - Score: {N}/9 → {Learn|Consider|Skip}
   - Create this skill? **Yes / No**

2. **{Candidate Name}** — {one-line purpose}
   ...
```

**For 4+ candidates**: Multi-select checklist

```markdown
**Skill Candidates Detected**

Select which skills to create:

- [ ] **{Candidate Name}** (score {N}/9) — {one-line purpose}
- [ ] **{Candidate Name}** (score {N}/9) — {one-line purpose}
- [ ] **{Candidate Name}** (score {N}/9) — {one-line purpose}
- [ ] **{Candidate Name}** (score {N}/9) — {one-line purpose}
```

**For candidates flagged as extensions**: Suggest extending instead of creating

```markdown
- **{Candidate Name}** — overlaps with existing `{skill-name}` skill
  - Recommendation: Extend `{skill-name}` rather than creating new skill
  - Extend? **Yes / No**
```

---

## Anti-Patterns

- ❌ **Premature extraction** — Creating a skill after seeing a pattern once. Wait for the second occurrence or high effort capitalization score.
- ❌ **Full skill loading during duplicate check** — Wastes context budget. Names and descriptions are sufficient for Phase 2.
- ❌ **Kitchen-sink skills** — Bundling unrelated methods into one skill because they came from the same task. Each skill should teach one cohesive method.
- ❌ **Agent-specific skills** — Extracting a method only one agent would ever use. That belongs inline in the agent, not as a skill.
- ❌ **Skipping user confirmation** — Always present candidates for approval before creating skill files.
- ✅ **Effort-aware extraction** — Prioritize capturing methods that required significant effort to discover, even if usage frequency is moderate.
