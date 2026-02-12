# Vision: Claude Code IA Stack — Next Generation

## Context

The project runs **two parallel IA stacks**: GitHub Copilot (`.github/`) and Claude Code (`.claude/`). The Copilot stack has a mature governance model centered on `ia-coord` — a 7-phase orchestrator agent that creates/validates agents, subagents, prompts, and skills with quality gates and boundary separation. The `AGENT-TOPOLOGY-REFACTOR.md` plan already compressed 8 agents into a dual-persona (advisor + builder) model. Skills (49) are mirrored in both stacks.

**The question**: Instead of 1:1 porting ia-coord to Claude Code, what's the *optimal* architecture that leverages Claude Code's native strengths while preserving governance rigor?

---

## 1. Core Insight: Claude Code Collapses the Agent Layer

In Copilot, agents are **persistent files** with YAML frontmatter, loaded by the VS Code extension. Each `.agent.md` carries its own methodology, constraints, tools, and skill references (~200 lines each). The system prompt includes the full agent file on every turn.

In Claude Code, **there are no agent files**. The main conversation IS the orchestrator. "Subagent types" in CLAUDE.md Section 9 are just labels — routing hints that tell the main agent what prompt to craft and which model to select when invoking the `Task` tool. Behavior is *emergent* from: `CLAUDE.md rules + loaded skills + Task prompt`.

This means the Copilot three-layer model:

```
Copilot:   Prompt (ephemeral) → Agent (persistent file) → Skill (reusable method)
```

Collapses in Claude Code to:

```
Claude:    Task prompt (ephemeral) → CLAUDE.md §9 entry (routing hint) → Skill (reusable method)
                                            ↑
                                    No persistent methodology here.
                                    Just: type | use-for | model
```

**The 200 lines of methodology that lived in each .agent.md must go somewhere.** The answer: **skills**. This is already the pattern — builder/advisor behavior comes from CLAUDE.md constraints + loaded skills, not from agent definition files.

---

## 2. Architecture: Lean Kernel + JIT Methodology + Isolated Execution

### Three Pillars

```
┌─────────────────────────────────────────────────────────────────────┐
│  PILLAR 1: LEAN KERNEL  (CLAUDE.md — always loaded, ~350 lines)     │
│                                                                     │
│  What lives here:                                                   │
│  - Immutable rules (typing, module boundaries, generated code)      │
│  - Architecture overview (contract-first, module patterns)          │
│  - Commands (Makefile targets)                                      │
│  - Routing table (§9: subagent_type → use-for → model)              │
│  - Skill loading protocol (scan glossary → drill → apply)           │
│  - FinOps checkpoints                                               │
│                                                                     │
│  What does NOT live here:                                           │
│  - Full methodology for any workflow (that's skills)                │
│  - Agent-specific constraints (emergent from skills)                │
│  - Quality gate definitions (that's ia-quality-gates skill)         │
│  - Templates (inline in skills)                                     │
│                                                                     │
│  Token cost: ~4K tokens idle (vs ~8-10K in Copilot)                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  PILLAR 2: JIT METHODOLOGY  (skill-bank — loaded on demand)         │
│                                                                     │
│  Discovery: glossary (500 tokens) → leaf skill (1-3K tokens)        │
│  Loading: explicit Read, NOT auto-injected into system prompt       │
│  Governance: disable-model-invocation: true on ALL leaf skills      │
│                                                                     │
│  Key advantage over Copilot:                                        │
│  - Copilot loads full agent methodology every turn (~200 lines)     │
│  - Claude Code loads skill methodology ONLY when relevant           │
│  - 5 skills × 150 lines = 750 lines never loaded in idle turns     │
│                                                                     │
│  This is the PRIMARY carrier of "how to work"                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  PILLAR 3: ISOLATED EXECUTION  (Task tool — per-invocation context) │
│                                                                     │
│  Each Task call gets:                                               │
│  - Fresh context (no conversation history leakage)                  │
│  - Explicit prompt with C1-C5 context + O1-O2 output spec          │
│  - Model selection (Opus/Sonnet/Haiku per type)                     │
│  - Tool subset (inherits from settings, scoped by prompt)           │
│                                                                     │
│  Key advantage over Copilot:                                        │
│  - Copilot subagents are sequential (runSubagent blocks)            │
│  - Claude Code can run multiple Task calls in PARALLEL              │
│  - Model tier is explicit per call, not per-file frontmatter        │
└─────────────────────────────────────────────────────────────────────┘
```

### Token Budget Model

```
                          Copilot                Claude Code
                          ───────                ───────────
System prompt (idle):     ~8-10K tokens          ~4K tokens
                          (instructions.md        (CLAUDE.md kernel
                           + agent.md loaded)      only)

Skill methodology:        ~3-5K per agent        0 until needed
                          (in agent file,         (JIT loaded via
                           always present)         glossary → drill)

Subagent invocation:      Full agent.md context   Minimal: prompt
                          passed to runSubagent   + CLAUDE.md kernel
                                                  + explicit context

Per-turn overhead:        ~12-15K tokens          ~4K tokens
                                                  + skills as needed
```

**Estimated savings: ~60% idle token reduction.**

---

## 3. What ia-coord Becomes

ia-coord's 7-phase methodology covers:

| Phase | What It Does | Claude Code Equivalent |
|-------|-------------|----------------------|
| 0. Classify | Determine artifact type (agent/subagent/prompt/skill) | **Simplified**: Only 2 artifact types remain — skills and CLAUDE.md entries |
| 0.5. Stability | Impact assessment for modifications | `stack-stability` skill (needs creation) |
| 1. Requirements | Gather model/tools/handoffs/reasoning needs | **Reduced**: No model/tools/handoffs per-agent. Only skill requirements. |
| 2. Discovery | Search existing patterns | Standard `Explore` agent or `Grep`/`Glob` |
| 3. Template Population | Fill template with content | **Replaced by**: `skill-design` governance (frontmatter spec, naming, categories) |
| 4. Quality Gates | A1-A9, SA1-SA7, P1-P6, S1-S5 | `ia-quality-gates` skill — **but only S1-S5 and a new "R1-R5" for routing entries** |
| 5. Boundary Validation | Clean separation test | `ia-validation` skill (runtime-agnostic, already works) |
| 6. Output | Generate file + catalog update | `Write` tool + `build-skill-tree.py` |
| 7. Leverage Scan | Which agents benefit from new asset? | `Grep` for skill references across CLAUDE.md + skill-bank |

**What collapses:**
- **Agent gates (A1-A9) mostly disappear** — no agent files to validate
- **Subagent gates (SA1-SA7) collapse** — subagent types are 1-line entries, not files
- **Prompt gates (P1-P6) disappear** — no .prompt.md files; Task prompts are ephemeral
- **Templates disappear** — no template files needed; skill-design frontmatter spec IS the template

**What survives and matters more:**
- **Skill gates (S1-S5)** — skills are the PRIMARY artifact, gates are critical
- **Boundary validation** — still essential: is this a skill, a CLAUDE.md rule, or a Task prompt?
- **Stack stability** — still essential: what breaks if we change this skill?
- **Skill-design governance** — naming, frontmatter, categories, tree building

### New ia-coord = Skill Cluster, Not Agent

```
skill-bank/
  ia-design/
    skill-design/SKILL.md          ← HOW to create skills (exists, keep)
    ia-quality-gates/SKILL.md      ← WHAT to validate (exists, UPDATE for Claude Code)
    ia-validation/SKILL.md         ← HOW to validate boundaries (exists, keep)
    ia-stack-ops/SKILL.md          ← NEW: unified IA modification workflow
    stack-stability/SKILL.md       ← NEW: impact assessment (was referenced, never created)
    agent-routing/SKILL.md         ← HOW to delegate (exists, UPDATE routing table)
    claude-code-agent-patterns/    ← Architecture patterns (exists, keep)
    agentic-resources/SKILL.md     ← Marketplace directory (exists, keep)
```

The new `ia-stack-ops` skill replaces ia-coord's phased methodology with a Claude-Code-native workflow (see Section 4).

---

## 4. Workflows

### Workflow A: Create a New Skill

```
User: "Create a skill for X"
  │
  ├─ 1. ROUTE: CLAUDE.md §9 routing rule → "IA stack artifact → load ia-stack-ops"
  │
  ├─ 2. LOAD: Read ia-design glossary → load skill-design + ia-stack-ops
  │
  ├─ 3. CLASSIFY: ia-stack-ops Phase 0 → artifact = skill
  │
  ├─ 4. CHECK OVERLAP: Grep skill-bank for similar keywords/names
  │     If overlap >40% with existing skill → merge or differentiate
  │
  ├─ 5. CREATE: Write .claude/skill-bank/{name}/SKILL.md
  │     Following skill-design frontmatter spec:
  │     - name (kebab-case, ≤30 chars, globally unique)
  │     - description ("{What}. Use when {contexts}.")
  │     - keywords (3-7 terms)
  │     - category (existing or justify new)
  │     - disable-model-invocation: true
  │
  ├─ 6. VALIDATE: Load ia-quality-gates → run S1-S5
  │     S1: Agent-agnostic? (no agent names, no tool defs)
  │     S2: Reusable method steps?
  │     S3: Under 200 lines?
  │     S4: Clear scope boundary?
  │     S5: No task-specific context?
  │
  ├─ 7. BOUNDARY: Load ia-validation → clean separation test
  │     "Could this content live in CLAUDE.md instead?" → if yes, it should
  │     "Is this methodology or configuration?" → methodology = skill
  │
  ├─ 8. REGENERATE: python3 .claude/scripts/build-skill-tree.py --write
  │
  └─ 9. VERIFY: Read generated glossary → confirm skill appears correctly
```

**Token cost**: ~8K total (2 glossary reads + 2 skill reads + file creation + validation)

### Workflow B: Add/Modify a Subagent Type

```
User: "Add a new subagent type for X" or "Change builder's model to Sonnet"
  │
  ├─ 1. LOAD: ia-stack-ops + agent-routing
  │
  ├─ 2. ASSESS IMPACT:
  │     Grep CLAUDE.md for current entry
  │     Grep skill-bank for references to this subagent type
  │     Classify: additive (new type) vs. structural (change existing)
  │
  ├─ 3. VALIDATE ROUTING:
  │     Does this type overlap with existing types?
  │     What's the routing signal? (which user intents trigger this?)
  │     Model selection justified? (Opus=orchestration, Sonnet=execution, Haiku=verification)
  │
  ├─ 4. EDIT: Update CLAUDE.md §9 table
  │     One line: | type | use-for | model |
  │     Update Quick Decision Rules if routing changes
  │
  └─ 5. VERIFY: Read modified section, check consistency
```

**Token cost**: ~3K total (1 skill read + CLAUDE.md edit + verification)

### Workflow C: Modify CLAUDE.md Immutable Rules (High-Impact)

```
User: "Change the typing rule" or "Add a new immutable constraint"
  │
  ├─ 1. LOAD: ia-stack-ops + stack-stability (NEW skill)
  │
  ├─ 2. IMPACT ASSESSMENT:
  │     Dependency scan: what references this rule?
  │     Classify tier:
  │       T1 (cosmetic) → proceed
  │       T2 (behavioral) → present impact, get approval
  │       T3 (structural) → full impact map + approval gate
  │       T4 (breaking) → HALT, present alternatives
  │
  ├─ 3. If approved: Edit CLAUDE.md
  │
  └─ 4. VERIFY: Grep for inconsistencies with skill-bank content
```

### Workflow D: IA Stack Health Check (Periodic)

```
User: "Check IA stack consistency" or proactive after many changes
  │
  ├─ 1. LOAD: ia-validation + ia-quality-gates
  │
  ├─ 2. SCAN (parallel Tasks):
  │     Task A: Verify all skill-bank entries have valid frontmatter
  │     Task B: Verify glossaries match skill-bank (run build-skill-tree.py --dry-run)
  │     Task C: Verify CLAUDE.md §9 types are referenced in routing rules
  │     Task D: Check for orphaned skills (no category) or bloated categories (>12)
  │
  ├─ 3. REPORT: Findings table with severity + remediation
  │
  └─ 4. FIX: If issues found, apply fixes (skill by skill)
```

**Key optimization**: Parallel Task execution for independent checks.

---

## 5. What Changes from Current State

### New Skills to Create (2)

| Skill | Lines (est.) | Purpose |
|-------|-------------|---------|
| `ia-stack-ops` | ~120 | Unified IA modification workflow for Claude Code (replaces ia-coord phases) |
| `stack-stability` | ~80 | Impact assessment methodology (referenced by ia-validation, never created) |

### Skills to Update (2)

| Skill | Change |
|-------|--------|
| `ia-quality-gates` | Add R1-R5 gates for CLAUDE.md routing entries. Annotate A1-A9/SA1-SA7/P1-P6 as "Copilot-only" or remove. |
| `agent-routing` | Update catalog to reflect Claude Code subagent types. Add "IA stack modification → load ia-stack-ops" route. |

### CLAUDE.md Changes (1)

| Section | Change |
|---------|--------|
| §4 IA Stack Ownership | Add: "For IA stack modifications, load `ia-stack-ops` skill via `ia-design` glossary." |
| §9 Quick Decision Rules | Add: rule 0 — "IA stack artifact? → load ia-stack-ops from ia-design glossary" |

### Skills to Keep As-Is (4)

`skill-design`, `ia-validation`, `claude-code-agent-patterns`, `agentic-resources` — all runtime-appropriate, no changes needed.

### What We Do NOT Create

- No `.agent.md` file for ia-coord (no agent files in Claude Code)
- No template files (skill-design frontmatter spec IS the template)
- No subagent_type for ia-coord (IA work needs full conversation context, not isolation)
- No prompt files (Task prompts are ephemeral by design)

---

## 6. The ia-quality-gates Evolution

Current gates map to Claude Code artifacts:

```
COPILOT GATES              →  CLAUDE CODE RELEVANCE
─────────────                  ────────────────────
A1-A9  (agent structure)    →  RETIRED (no agent files)
SA1-SA7 (subagent gates)   →  RETIRED (no subagent files)
P1-P6  (prompt gates)      →  RETIRED (no prompt files)
S1-S5  (skill gates)       →  KEPT (skills are primary artifact)

NEW GATES (Claude Code specific):
R1. Routing entry has clear trigger signal (when to use this type)
R2. Model selection justified (Opus/Sonnet/Haiku rationale)
R3. No overlap with existing subagent types (dedup check)
R4. Description is actionable (tells main agent what prompt to craft)
R5. Consistent with Quick Decision Rules (no routing conflicts)

K1. CLAUDE.md stays under 400 lines (kernel size guard)
K2. New §4 rule has enforcement mechanism (not just "should")
K3. No methodology in CLAUDE.md (belongs in skills)
K4. Settings.json permissions cover new tool patterns
```

---

## 7. Context Control Strategy

### System Prompt Budget

```
CLAUDE.md kernel:     ~350 lines  →  ~4K tokens (HARD CAP: 400 lines)
MEMORY.md:            ~20 lines   →  ~200 tokens
Glossary headers:     ~50 lines   →  ~500 tokens (from Skill tool)
                                     ─────────
                      IDLE TOTAL:    ~4.7K tokens

Skill load (JIT):     ~150 lines  →  ~1.5K tokens per skill
Typical task:          2-3 skills  →  ~4K tokens additional
                                     ─────────
                      ACTIVE TOTAL:  ~8.7K tokens
```

### Subagent Context Isolation

| Subagent Type | What It Sees | What It Doesn't See |
|---------------|-------------|-------------------|
| `implement` | Task prompt + CLAUDE.md + specific file contents | Conversation history, other skills, planning context |
| `research` | Task prompt + CLAUDE.md + web/codebase access | Implementation decisions, code changes in progress |
| `verify` | Task prompt + CLAUDE.md + files to check | Why changes were made, alternative approaches |

**Design principle**: Subagents are **stateless executors**. They see ONLY what they need (C1-C5 in the prompt). The main conversation holds the full context and orchestrates.

### Token Waste Prevention

| Checkpoint | Trigger | Action |
|------------|---------|--------|
| Skill double-load | Same skill read twice in conversation | Skip — already in context |
| Glossary skip | Already know which skill to load | Read leaf skill directly |
| Subagent output bloat | >1000 token response from Task | Summarize before integrating into main context |
| Convergence gate | 8+ tool calls without progress | Reassess approach, compress context, or delegate |

---

## 8. Migration Path (Minimal Disruption)

### Phase 1: Create Missing Skills
1. Create `ia-stack-ops/SKILL.md` — the Claude Code IA workflow
2. Create `stack-stability/SKILL.md` — impact assessment
3. Run `build-skill-tree.py --write`

### Phase 2: Update Existing Skills
4. Update `ia-quality-gates` — add R1-R5, K1-K4; mark Copilot gates
5. Update `agent-routing` — add IA work routing rule

### Phase 3: Update Kernel
6. Update CLAUDE.md §4 and §9 — add IA governance routing

### Phase 4: Validate
7. Run health check workflow (Workflow D above)
8. Test: create a test skill using the new workflow
9. Test: modify a CLAUDE.md entry using the new workflow

### What Does NOT Change
- Copilot stack (`.github/`) — untouched, continues to work independently
- Existing skills — 47 of 49 unchanged
- skill-bank structure — same directories, same frontmatter spec
- build-skill-tree.py — same script, same behavior
- settings.json — no permission changes needed

---

## Summary

| Dimension | Copilot ia-coord | Claude Code Vision |
|-----------|-----------------|-------------------|
| **Artifact** | 159-line agent file | 2 new skills (~200 lines total) |
| **Methodology** | 7-phase orchestration | 4-workflow model (create skill / add type / modify rules / health check) |
| **Governance targets** | Agents, subagents, prompts, skills | Skills + CLAUDE.md entries (2 artifact types, not 4) |
| **Quality gates** | A1-A9, SA1-SA7, P1-P6, S1-S5 | S1-S5 + R1-R5 + K1-K4 (14 gates, not 26) |
| **Token overhead** | ~200 lines always loaded | 0 lines idle; ~150 lines when loaded |
| **Template system** | 5 template files in .github/agents/templates/ | skill-design frontmatter spec (already exists) |
| **Enforcement** | ia-coord agent has exclusive edit rights | CLAUDE.md §4 rule + skill-design methodology |

**The net effect**: ia-coord's governance rigor survives, but adapted for a stack with fewer artifact types, JIT methodology loading, and native context isolation. The result is leaner, cheaper, and leverages what Claude Code does best — parallel execution, explicit context passing, and skill-based progressive disclosure.
