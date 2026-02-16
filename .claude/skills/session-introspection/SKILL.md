---
name: session-introspection
description: Session retrospective and IA tuning via history analysis. Load when reviewing sessions or proposing improvements
user-invocable: false
---

# Session Introspection

Analyzes past Claude Code sessions to surface flaws, missed opportunities, and friction points — then proposes **micro-adjustments** to the IA stack. Each adjustment is small and reversible, like tuning a weight in a model. Compound gains emerge over multiple iterations.

**Philosophy**: No big-bang rewrites. Every proposed change must be:
- **Atomic** — one concern per adjustment
- **Reversible** — easy to undo if it doesn't help
- **Measurable** — you can tell if it worked next time

---

## Data Sources

| Source | Access | What It Reveals |
|--------|--------|-----------------|
| **History MCP** | `mcp__claude-code-history__*` | Session inventory, message content, cross-session search |
| **File-History Snapshots** | `~/.claude/filehistory/` | File change patterns, churn, regression points |
| **Git Log** | `git log --oneline -n 50` | Commit frequency, message quality, session → commit mapping |
| **Auto Memory** | `.claude/projects/*/memory/` | What was already learned, what keeps recurring |
| **IA Stack** | `.claude/CLAUDE.md`, `.claude/skills/` | Current rules, skills, routing — the thing being tuned |
| **Settings** | `.claude/settings.json`, `.claude/settings.local.json` | Permission friction, auto-approval patterns |

---

## Methodology

### Phase 1: Scope — Select What to Analyze

Choose one:

| Scope | When | How |
|-------|------|-----|
| **Last session** | Quick feedback loop | `list_sessions` → pick most recent |
| **Date range** | Periodic review (e.g., weekly) | `list_sessions(startDate=..., endDate=...)` |
| **Specific session** | Investigating a known issue | Direct `sessionId` |
| **Topic search** | Tracking a recurring problem | `search_conversations(query="...")` |

**Output**: A list of 1-5 session IDs + their message counts.

**Guard**: If total messages across selected sessions > 500, narrow the scope. Analysis quality degrades with volume.

### Phase 2: Harvest — Extract Signal

For each selected session, extract structured observations across **seven analysis dimensions**. Use `search_conversations` for targeted extraction rather than reading full transcripts.

#### Dimension 1: Token Efficiency

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Redundant reads | Search for same file path appearing 3+ times | File read without subsequent edit = wasted |
| Bloated output | Look for large tool results in transcripts | Commands without `head`/`tail`/`timeout` guards |
| Cache misses | Check `usage.cache_read_input_tokens` in metadata | Low cache-read ratio = context not reused |
| Context pressure | Session message count > 200 | Late-session quality degradation, auto-compaction |

#### Dimension 2: Tool Selection

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Wrong tool | Search for `grep`, `cat`, `find` in Bash calls | Dedicated tool (`Grep`, `Read`, `Glob`) should have been used |
| Underused subagents | Identify 5+ sequential tool calls on same topic | Should have been delegated to a `Task` subagent |
| Missing parallelism | Sequential independent tool calls | Could have been batched in one turn |

#### Dimension 3: Skill Engagement

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Skill loaded | Search for `Read .claude/skills/` | Which skills were actually loaded |
| Skill should have loaded | Cross-reference task type with skill descriptions | Task matches a skill's trigger but skill wasn't loaded |
| Skill loaded but not followed | Loaded skill, then deviated from methodology | Skill methodology unclear or wrong for the case |

#### Dimension 4: Error Patterns

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Permission denials | Search for `Permission.*denied` | Frequent denials = settings.json friction |
| Repeated failures | Same command/tool failing 2+ times | No adaptation after failure |
| Convergence traps | 8+ tool calls without deliverable progress | FinOps checkpoint was missed |

#### Dimension 5: Delegation Quality

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Subagent invoked | Search for `Task` tool usage | Subagent type, prompt quality, result utilization |
| Duplicate work | Parent and subagent searching same things | Context not properly passed |
| Wrong subagent type | Task description mismatches subagent capability | Routing heuristic gap |

#### Dimension 6: Rule Adherence

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Direct `pip`/`npm` | Search for `pip install`, `npm install` | Should use Makefile targets |
| Missing type hints | Search for `Any`, `any`, `type: ignore` | Zero-tolerance rule violated |
| Cross-module imports | Search for imports between modules | Module independence violated |

#### Dimension 7: Communication

| Signal | Search Strategy | What to Look For |
|--------|----------------|------------------|
| Repeated clarifications | User restating the same request | Initial understanding was wrong |
| Over-engineering | User saying "that's too much", "simpler" | Scope creep, not matching request |
| Under-delivery | User asking "what about X?" after completion | Requirements missed |

**Output per dimension**: 0-3 observations, each as:
```
- [DIM_ID] Observation: {what happened}
  Evidence: {session ID, approximate location}
  Frequency: once | recurring | systemic
```

### Phase 3: Classify — Organize Findings

Map each observation to a **severity** and **root cause type**:

| Severity | Meaning | Action Urgency |
|----------|---------|---------------|
| **Noise** | Cosmetic, no real impact | Skip — don't create adjustments for these |
| **Friction** | Slows work but doesn't block | Address in next tuning cycle |
| **Flaw** | Causes wrong output or wasted effort | Address now |
| **Systemic** | Same issue across multiple sessions | Priority fix — affects every session |

| Root Cause Type | Meaning | Typical Lever |
|-----------------|---------|---------------|
| **Discovery gap** | Right skill exists but wasn't found | Keyword/routing adjustment |
| **Coverage gap** | No skill covers this need | New skill or skill extension |
| **Rule ambiguity** | Rule exists but is unclear | Rule clarification |
| **Missing rule** | No rule covers this pattern | New rule |
| **Permission friction** | Settings.json blocks valid workflow | Permission tuning |
| **Habit** | Agent knows the rule but didn't follow it | Reinforce via memory note |

### Phase 4: Reason — Root Cause → Lever

For each non-noise finding, produce a **reasoning chain**:

```
Finding: [observation from Phase 2]
Why it happened: [root cause analysis — be specific]
What lever to pull: [the smallest change that addresses the root cause]
Why this lever: [why this specific change, not a bigger one]
Risk: [what could go wrong if this change is applied]
```

**Key constraint**: Resist the urge to propose big changes. Ask: *"What is the smallest edit that would have prevented this?"* A keyword addition to a skill is better than a new skill. A rule clarification is better than a new rule.

### Phase 5: Propose — Generate Adjustment Plan

Convert each reasoning chain into a concrete **micro-adjustment**:

| Field | Description |
|-------|-------------|
| **ID** | `ADJ-{session-date}-{seq}` (e.g., `ADJ-20260212-01`) |
| **Type** | One of the lever types below |
| **Target** | Exact file path and location |
| **Change** | Precise edit description (what to add/modify/remove) |
| **Confidence** | `high` / `medium` / `low` |
| **Effort** | `trivial` (<2 min) / `small` (2-10 min) / `medium` (10-30 min) |
| **Reversibility** | `trivial` (delete a line) / `easy` (revert an edit) / `moderate` (multiple files) |

#### Lever Types

| Lever | What It Changes | Example |
|-------|----------------|---------|
| `skill-keyword` | Add/adjust keyword in a skill's frontmatter | Add `order-tracking` to broker-related skill |
| `skill-update` | Modify skill methodology or templates | Add missing anti-pattern to a skill |
| `skill-create` | Create new skill for recurring uncovered pattern | New skill for a pattern seen 3+ times |
| `routing-hint` | Add/refine §4 Delegation Rules | Add "data migration?" → `general-purpose` |
| `rule-clarify` | Sharpen an existing CLAUDE.md rule | Expand an ambiguous constraint |
| `rule-add` | Add new CLAUDE.md rule | Only for systemic issues not covered |
| `memory-note` | Add pattern to auto-memory | Record a recurring insight |
| `permission-tune` | Adjust settings.json | Auto-approve a frequently-allowed tool |
| `health-check` | Run stack health check after changes | Always follows skill modifications |

### Phase 6: Prioritize — Rank and Batch

Sort adjustments by **impact/effort ratio**:

```
Priority = (severity_weight × confidence_weight) / effort_weight

severity_weight:  systemic=4, flaw=3, friction=2, noise=0
confidence_weight: high=1.0, medium=0.6, low=0.3
effort_weight:    trivial=1, small=2, medium=4
```

**Batch rules**:
- Apply max 3-5 adjustments per introspection cycle
- Never apply `low` confidence adjustments without user confirmation
- Always apply `trivial` effort + `high` confidence adjustments first
- Group related adjustments (e.g., keyword change + health check)

---

## Output Format

```markdown
## Session Introspection Report

**Scope**: {sessions analyzed, date range}
**Sessions**: {count} sessions, {total messages} messages

### Findings

| # | Dim | Severity | Observation | Evidence |
|---|-----|----------|-------------|----------|
| 1 | Token Efficiency | Friction | {description} | Session {id} |
| 2 | Skill Engagement | Flaw | {description} | Session {id} |
| ... | | | | |

### Adjustment Plan

| ID | Type | Target | Change | Conf | Effort | Priority |
|----|------|--------|--------|------|--------|----------|
| ADJ-...-01 | skill-keyword | `.claude/skills/X/SKILL.md` | Add keyword `Y` | high | trivial | 4.0 |
| ADJ-...-02 | rule-clarify | `.claude/CLAUDE.md` §4 | Expand Z rule | medium | small | 1.2 |
| ... | | | | | | |

### Reasoning (top 3)

**ADJ-...-01**: {full reasoning chain from Phase 4}

**ADJ-...-02**: {full reasoning chain from Phase 4}

### Deferred

{Adjustments ranked too low or too uncertain for this cycle — revisit next time}
```

---

## Execution Guidance

After the report is approved:
1. Apply adjustments in priority order
2. For skill changes → edit skill files directly
3. For routing/rule changes → edit CLAUDE.md
4. For `permission-tune` → edit `.claude/settings.json` directly
5. For `memory-note` → update auto-memory files
6. Record applied adjustments in auto-memory for tracking over time

---

## Iteration Tracking

Maintain a running log in auto-memory to track compound effects:

```markdown
## Introspection Log

| Date | Adjustments Applied | Key Finding | Status |
|------|-------------------|-------------|--------|
| 2026-02-12 | ADJ-...-01, ADJ-...-02 | Skill X missing keyword | Applied, monitoring |
| ... | | | |
```

After 3+ cycles, review the log for:
- **Recurring findings** → indicates a deeper structural issue
- **Applied but ineffective** → revert the adjustment
- **Applied and effective** → reinforce the pattern

---

## Anti-Patterns

| Anti-Pattern | Why Wrong | Instead |
|-------------|-----------|---------|
| Analyzing more than 5 sessions at once | Signal-to-noise ratio collapses | Narrow scope, go deep not wide |
| Proposing >5 adjustments per cycle | Change fatigue, hard to attribute effects | Prioritize ruthlessly, defer the rest |
| Big-bang skill rewrites from findings | Violates atomic/reversible principle | One concern per adjustment |
| Applying `low` confidence adjustments silently | May introduce wrong patterns | Always confirm with user |
| Skipping the reasoning chain | Adjustments without rationale are guesses | Phase 4 is mandatory, not optional |
| Never revisiting the introspection log | No feedback on whether changes worked | Review log every 3 cycles |
| Introspecting the current session | Can't see your own blind spots in real-time | Always analyze past sessions |
| Proposing adjustments outside the lever types | Unstructured changes are hard to track | If it doesn't fit a lever, rethink |
