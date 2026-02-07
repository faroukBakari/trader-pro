# IA Coordination Methodology

## The Three-Layer Agentic Design Model

> **Version**: 3.1.0
> **Date**: February 2026
> **Supersedes**: v3.0 (added naming conventions, subagent template, SA-1 naming gate)
> **Coordinator**: `.github/agents/ia-coord.agent.md`

---

## Table of Contents

1. [Overview](#overview)
2. [The Three-Layer Model](#the-three-layer-model)
3. [Layer Definitions](#layer-definitions)
4. [Agent Deployment Modes](#agent-deployment-modes)
5. [Boundary Separation Theory](#boundary-separation-theory)
6. [Decision Frameworks](#decision-frameworks)
7. [Quality Gates](#quality-gates)
8. [Model Selection & FinOps](#model-selection--finops)
9. [Skill Extraction Heuristic](#skill-extraction-heuristic)
10. [Anti-Patterns & Corrective Principles](#anti-patterns--corrective-principles)
11. [VS Code Implementation Reference](#vs-code-implementation-reference)
12. [Templates & Blueprints](#templates--blueprints)
13. [Workflow: Creating IA Assets](#workflow-creating-ia-assets)
14. [References](#references)

---

## Overview

This methodology defines a **three-layer model** for building agentic systems within VS Code Copilot Custom Chat Agents. It enforces strict boundary separation between Prompts, Agents, and Skills to prevent bloat, duplication, and maintenance debt.

The Agent layer operates in **two deployment modes** — user-facing orchestrators and context-isolated subagents — enabling FinOps-optimized delegation, parallelization, and context hygiene without introducing a fourth layer.

### Design Principles

These principles are grounded in the official documentation from Anthropic, VS Code, and the AgentSkills.io standard:

1. **Separation of concerns** — Each layer has one job and doesn't absorb responsibilities from another.
2. **Simplicity first** — Per Anthropic: _"The most successful implementations aren't the most complex — they're ones that are built on simple, composable patterns."_ ([Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents))
3. **Composability** — Prompts attach to agents; skills are referenced from agents or prompts; agents delegate to subagents. Each layer is independently evolvable.
4. **Transparency** — Per Anthropic's ACI (Agent-Computer Interface) principles: clear, well-documented interfaces between layers.
5. **FinOps awareness** — Route work to the cheapest model tier that can handle it. Subagent delegation enables cost-efficient specialization.

---

## The Three-Layer Model

```
┌──────────────────────────────────────────────────────────────────┐
│                    AGENTIC DESIGN STACK                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PROMPT (Ephemeral)     →  WHAT: Context + Deliverable          │
│     .prompt.md files — thin, disposable, variable-driven        │
│                                                                  │
│  AGENT (Persistent)     →  HOW: Tools + Methodology + Behavior  │
│     .agent.md files — orchestration, constraints, delegation    │
│     ├── User-Facing Mode  (user-invokable: true)                │
│     │   Visible in dropdown, orchestrates, offers handoffs      │
│     └── Subagent Mode     (user-invokable: false)               │
│         Hidden, delegated, context-isolated, model-downgraded   │
│                                                                  │
│  SKILL (Eternal)        →  HOW-TO: Portable repeatable method   │
│     SKILL.md files — agent-agnostic, tool-agnostic, zero-cost   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Layer Summary

| Layer      | Question              | Lifecycle                        | Location                      |
| ---------- | --------------------- | -------------------------------- | ----------------------------- |
| **Prompt** | WHAT to deliver       | Ephemeral — injected per-request | `.github/prompts/*.prompt.md` |
| **Agent**  | HOW to orchestrate    | Persistent — survives sessions   | `.github/agents/*.agent.md`   |
| **Skill**  | HOW-TO execute method | Transferable — works anywhere    | `.github/skills/*/SKILL.md`   |

### Relationships

```
User ──selects──▶ Agent from dropdown (or Prompt triggers Agent)
                     │
    ┌────────────────┼────────────────────┐
    │                │                    │
    ▼                ▼                    ▼
 loads Skill      delegates to         uses tools
 (into context)   Subagent             directly
 zero cost        (isolated, cheap)    (edit, bash)
    │                │                    │
    │                ▼                    │
    │           ┌──return──┐              │
    │           │ summary  │              │
    │           └──────────┘              │
    │                                     │
    └────────────┬────────────────────────┘
                 │
                 ▼
            offers Handoff
            to peer Agent
            (user clicks)
```

### Why Three Layers, Not Four

Subagents are `.agent.md` files with `user-invokable: false`. They share the same artifact format, quality gates (A1–A9), YAML structure, and constraint hierarchy as any other agent. The only difference is a deployment flag.

Adding a fourth layer would:

- **Violate Anthropic's simplicity principle**: _"Start simple, add complexity only when needed"_
- **Create artificial boundaries**: The line between subagent and agent is a single boolean, not a structural difference
- **Fragment quality gates**: Separate gates would largely duplicate A1–A9

The three layers answer three orthogonal questions:

- **Prompt**: WHAT does the user want? (ephemeral context)
- **Agent**: HOW should it be done? (persistent orchestration)
- **Skill**: HOW-TO execute a specific method? (portable knowledge)

Subagents don't answer a new question — they answer HOW differently (isolated, cheaper, focused). They are a **deployment mode**, not a layer.

---

## Layer Definitions

### Prompts — The "WHAT" Layer

**Official definition** (VS Code docs): _"Prompt files let you build and share reusable prompt instructions with additional context. Prompt files are Markdown files that provide instructions and context to guide the AI language model towards generating more relevant code suggestions."_

**Characteristics**:

- **Ephemeral**: Injected once, consumed, forgotten
- **Thin**: ≤50 lines recommended; context + deliverable only
- **Variable-driven**: Uses `${input:varName}` for user input, `${file:path}` for file references
- **No methodology**: Never contains HOW to do things — that's the agent's job
- **No tool lists**: Never specifies which tools to use — that's the agent's configuration
- **No constraints**: Never contains behavioral rules — that's the agent's system prompt

**What belongs in a Prompt**:

- Task context (what the user wants)
- Deliverable format (what should be produced)
- Variable placeholders for reusability
- File references for workspace context

**What does NOT belong in a Prompt**:

- Methodology steps / phases
- Constraint hierarchies
- Tool specifications
- Model selection logic
- Role definitions

### Agents — The "HOW" Layer

**Official definition** (VS Code docs): _"Custom agents are AI assistants designed to assist with specific tasks or areas. Each agent has access to its own set of tools, and you can configure agents with custom instructions, tools, and model considerations."_

**Anthropic guidance**: _"Agents dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks."_

**Characteristics**:

- **Persistent**: System prompt loaded once, governs all interactions in that mode
- **Orchestrating**: Decides task decomposition, tool selection, delegation
- **Constrained**: Operates under explicit behavioral rules (CRITICAL > IMPORTANT > GUIDELINES)
- **Tool-aware**: YAML frontmatter declares available tools and subagents
- **Methodology-driven**: Contains phased approaches (e.g., "Phase 1: Discovery → Phase 2: Analysis → Phase 3: Synthesis")
- **Dual-mode**: Can operate as user-facing orchestrator or hidden subagent (see [Agent Deployment Modes](#agent-deployment-modes))

**What belongs in an Agent**:

- YAML frontmatter (tools, model, agents, handoffs)
- Role definition and expertise area
- Constraint hierarchy (what to always/never do)
- Methodology phases (how to approach tasks)
- Skill references via `<skill>` tags (load on demand)
- Delegation rules (when to use subagents)
- Handoff configuration (workflow transitions)
- Caller protocol and output contract (for subagent-mode agents)

**What does NOT belong in an Agent**:

- Full skill method text (reference via `read_file` instead)
- Task-specific context that varies per request (that's a prompt)
- Implementation code or templates (that's a skill or workspace file)

### Skills — The "HOW-TO" Layer

**Official definition** (VS Code docs): _"You can create agent skills to define domain-specific knowledge that an agent can access. Skills describe the know-how, rules, and procedures for specialized tasks."_

**Standard**: Skills follow the [AgentSkills.io](https://agentskills.io) open standard — portable across VS Code Copilot, Claude CLI, and other coding agents.

**Characteristics**:

- **Transferable**: Works with ANY agent, not bound to a specific one
- **Agent-agnostic**: Never references agent names or identities
- **Tool-agnostic**: Describes methods, not tool invocations
- **Progressive disclosure**: 3-level loading (description → SKILL.md → resources/)
- **Method-focused**: Encapsulates domain knowledge as reusable procedures
- **Zero marginal cost**: Loaded into parent's context — no separate LLM invocation

**What belongs in a Skill**:

- Decision frameworks and heuristics
- Step-by-step procedures
- Evaluation criteria / checklists
- Domain-specific knowledge
- Anti-patterns and corrective guidance
- Resource directories for supplementary material

**What does NOT belong in a Skill**:

- Agent names or identity references
- Tool-specific instructions (`use read_file`, `run grep_search`)
- Model selection directives
- Workflow routing logic

---

## Agent Deployment Modes

The Agent layer operates in two deployment modes, controlled by the `user-invokable` frontmatter flag. Both modes produce `.agent.md` files that follow A1–A9 quality gates. The difference is operational, not structural.

### Mode Comparison

| Property       | User-Facing (default)                 | Subagent (`user-invokable: false`)              |
| -------------- | ------------------------------------- | ----------------------------------------------- |
| **Visibility** | Dropdown + prompt `agent:` field      | Invisible — programmatic only via `runSubagent` |
| **Autonomy**   | Decides approach, interacts with user | Receives structured instructions, reports back  |
| **Model tier** | Matches task complexity (Opus/Sonnet) | One tier below parent (Haiku/Sonnet)            |
| **Tool set**   | Full toolkit for the role             | Minimal — principle of least privilege          |
| **Context**    | Accumulates across the session        | Fresh per invocation, discarded after           |
| **Handoffs**   | Can hand off to peer agents           | Never — subagents don't interact with users     |
| **Lifecycle**  | Persistent session                    | Spawned → execute → report → terminate          |

### The Apprentice Nature of Subagents

Subagents are **the apprentice** ("le stagiaire") — not peers, not independent actors. They:

1. **Receive structured tasks** from a parent, not free-form requests from users
2. **Operate in isolation** — their exploration, dead ends, and intermediate work never pollute the parent's context
3. **Return summaries** — only the final distilled result goes back, not the journey
4. **Use cheaper models** — Haiku-tier for grunt work, freeing Opus/Sonnet budget for orchestration
5. **Can run in parallel** — VS Code can spawn multiple subagents simultaneously for independent tasks

This maps directly to Anthropic's **Orchestrator-Workers** pattern: _"A central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results."_

### Context Isolation Mechanics

```
Parent Agent Context Window (Opus, expensive)
├── User request
├── Skill A loaded (50 lines, zero cost)
├── Agent methodology (always present)
├── [Subagent 1 SUMMARY: 20 lines]  ← only this returns
│   └── (Subagent explored 50 files, 30K tokens — all discarded)
├── [Subagent 2 SUMMARY: 15 lines]  ← only this returns
│   └── (Subagent fetched 5 web pages, 20K tokens — all discarded)
└── Parent continues orchestrating with clean context
```

**The context dividend**: Without subagent delegation, an Opus agent exploring 50 files fills its expensive context with intermediate results — file listings, grep outputs, dead-end reads. With delegation, the parent receives only the synthesized 20-line finding, keeping its context focused and its token budget spent on high-value orchestration.

### Parallelization

VS Code confirms: _"VS Code can run multiple subagents simultaneously."_ This maps to Anthropic's **Parallelization** pattern (Sectioning variant):

| Scenario                                 | Sequential Time | Parallel Time   | Speedup |
| ---------------------------------------- | --------------- | --------------- | ------- |
| Research auth + analyze DB + review docs | T₁ + T₂ + T₃    | max(T₁, T₂, T₃) | ~3x     |
| Check 3 files for patterns               | T₁ + T₂ + T₃    | max(T₁, T₂, T₃) | ~3x     |
| Research + extract from large file       | T₁ + T₂         | max(T₁, T₂)     | ~2x     |

**Rule**: Independent tasks → parallel subagent invocation. Dependent tasks (B needs A's output) → sequential invocation.

### Subagent Design Rules (SA-1 to SA-7)

These rules are **conditional extensions** to A1–A9 — they apply when `user-invokable: false`:

| Rule                           | Requirement                                                           | Rationale                                         |
| ------------------------------ | --------------------------------------------------------------------- | ------------------------------------------------- |
| **SA-1: Naming & Visibility**  | File is `{name}.sub.agent.md`; `user-invokable: false` is mandatory   | Deployment mode indicator + discoverability        |
| **SA-2: Model Downgrade**      | Model at most one tier below intended parent              | FinOps: cheap models for grunt work               |
| **SA-3: Minimal Tool Set**     | Principle of least privilege on tools                     | Read-only subagent ≠ needs `edit` or `bash`       |
| **SA-4: Caller Protocol**      | Must document invocation interface in `<caller_protocol>` | Parent needs to know prompt format                |
| **SA-5: Output Contract**      | Must document return format in `<output_format>`          | Parent needs predictable response structure       |
| **SA-6: No Handoffs**          | Never has `handoffs:` in frontmatter                      | Subagents don't interact with users               |
| **SA-7: No Nested Delegation** | Should not spawn sub-subagents (depth = 1)                | Prevents cascading costs and debugging complexity |

#### SA-3: Tool Privilege Reference

| Subagent Role         | Tool Set                             | Rationale                          |
| --------------------- | ------------------------------------ | ---------------------------------- |
| Read-only research    | `['read', 'search']`                 | No write access needed             |
| Web research          | `['read', 'search', 'web/fetch']`    | Adds web for information gathering |
| Implementation worker | `['read', 'search', 'edit', 'bash']` | Full set only when writing code    |
| Analysis / extraction | `['read', 'search']`                 | Analyze and report, never modify   |

---

## Boundary Separation Theory

### The Clean Separation Test

A well-designed IA system passes these boundary tests:

| Test              | Validates                                                                                                         | Method                                        |
| ----------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| **Prompt Swap**   | Could you replace `study.prompt.md` with `implement.prompt.md` on the same agent without changing the agent file? | If yes → prompt is properly thin              |
| **Agent Swap**    | Could a different agent use the same skill files without modification?                                            | If yes → skills are properly agent-agnostic   |
| **Skill Port**    | Could you move a skill to a completely different project and it still makes sense?                                | If yes → skill is properly portable           |
| **Prompt Delete** | If you delete ALL prompts, does the agent still know HOW to work?                                                 | If yes → agent methodology is self-contained  |
| **Mode Swap**     | Could you flip `user-invokable` without restructuring the agent's methodology?                                    | If yes → deployment mode is properly isolated |

### Boundary Violation Taxonomy

Four types of violations degrade system quality:

#### Type 1: Prompt Absorbs Agent Methodology

**Symptom**: Prompt contains phases, constraints, skill references, or behavioral rules.
**Result**: Prompt ≈ miniature agent; changing the prompt changes behavior, not just context.

```markdown
<!-- ❌ WRONG: prompt contains methodology -->

## Phase 1: Research

Read all relevant files using read_file...

## Phase 2: Analysis

Apply the debug-hypothesis skill...

## Constraints

- NEVER modify code
- ALWAYS use semantic_search first

<!-- ✅ CORRECT: prompt contains context + deliverable -->

## Context

${input:taskDescription}

## Deliverable

A structured study report with findings, analysis, and recommendations.
```

#### Type 2: Agent Absorbs Prompt Context

**Symptom**: Agent hardcodes task-specific context that should come from the prompt.
**Result**: Agent becomes single-purpose, loses flexibility.

```markdown
<!-- ❌ WRONG: agent hardcodes context -->

You study the WebSocket architecture of this project...

<!-- ✅ CORRECT: agent defines capability -->

You are a solutions architect. You study, analyze, and compare
technical solutions given any context provided by the user or prompt.
```

#### Type 3: Agent Absorbs Skill Methods

**Symptom**: Agent inlines 50+ lines of procedural knowledge that could be a standalone skill.
**Result**: Knowledge is trapped in one agent, not reusable by others.

```markdown
<!-- ❌ WRONG: inline skill knowledge in agent -->

## Debugging Methodology

1. Reproduce the issue...
2. Form hypotheses...
3. Design experiments...
   [50+ lines of debug method]

<!-- ✅ CORRECT: reference externalized skill -->
<skill>
<name>debug-hypothesis</name>
<file>.github/skills/debug-hypothesis/SKILL.md</file>
</skill>
```

#### Type 4: Skill Becomes Agent-Aware

**Symptom**: Skill references specific agent names, tool names, or model configurations.
**Result**: Skill breaks when used by a different agent or platform.

```markdown
<!-- ❌ WRONG: agent-specific references in skill -->

When the `implement` agent calls this skill, use `run_in_terminal`...
For Opus 4.6 model, increase analysis depth...

<!-- ✅ CORRECT: portable method description -->

When analyzing code changes:

1. Identify modified functions and their callers
2. Trace data flow through modified paths
3. Verify type contracts at module boundaries
```

---

## Decision Frameworks

### Skill vs Subagent

Both provide specialized capability to an agent, but through fundamentally different mechanisms:

| Dimension          | Skill                                                       | Subagent                                                |
| ------------------ | ----------------------------------------------------------- | ------------------------------------------------------- |
| **Mechanism**      | Text loaded into agent's context                            | Separate LLM invocation with own context                |
| **Cost**           | Zero marginal (included in parent's tokens)                 | Separate token consumption (cheaper model)              |
| **Context impact** | Expands parent context by skill size                        | Zero impact — returns summary only                      |
| **Execution**      | Agent applies the knowledge itself                          | Subagent applies its own reasoning                      |
| **Tool access**    | Uses parent's tools                                         | Has its own tool set                                    |
| **Parallelism**    | Sequential (one context)                                    | Can run in parallel with others                         |
| **Best for**       | Decision frameworks, checklists, methodologies (<200 lines) | Exploratory research, large-file analysis, web fetching |

**Decision heuristic**:

```
Does the task require the agent to KNOW something?        → Skill
Does the task require someone to GO DO something?         → Subagent

Is the knowledge < 200 lines and deterministic?           → Skill
Does exploration risk polluting the parent context?       → Subagent

Is the output predictable given the input?                → Skill
Does the task require dynamic searching/reading?          → Subagent

Could the work run in parallel with other work?           → Subagent
Is zero marginal cost important?                          → Skill
```

### Subagent vs Handoff

Both involve another agent, but with fundamentally different control semantics:

| Dimension      | Subagent Delegation                    | Handoff Transition                     |
| -------------- | -------------------------------------- | -------------------------------------- |
| **Control**    | Programmatic (parent decides)          | User-initiated (button click)          |
| **Direction**  | Hierarchical: parent → child → parent  | Lateral: agent A → agent B             |
| **Context**    | Isolated (fresh window)                | Can carry context via prompt           |
| **Visibility** | Invisible to user                      | Visible (button in UI)                 |
| **Return**     | Summary returns to parent              | No return — user is now with new agent |
| **Model**      | Typically cheaper than parent          | Independent                            |
| **Purpose**    | Grunt work, research, focused subtasks | Workflow phase transitions             |

```
Subagent:  Parent ──delegate──▶ Child ──report──▶ Parent continues
Handoff:   Agent A ──hand off──▶ Agent B takes over (Agent A is done)
```

### Complete Mechanism Selection

When an agent needs capability, use this decision table:

| Need                                      | Mechanism               | Layer/Mode              | Example                             |
| ----------------------------------------- | ----------------------- | ----------------------- | ----------------------------------- |
| Agent needs to know a methodology         | **Skill** reference     | Skill layer             | `debug-hypothesis` loaded on demand |
| Someone needs to go search the codebase   | **Subagent** delegation | Agent (subagent mode)   | `research` subagent explores files  |
| User should transition to a new workflow  | **Handoff**             | Agent (peer transition) | plan → implement handoff button     |
| Agent needs to act on the workspace now   | **Tool** call           | Direct tool invocation  | `replace_string_in_file`            |
| Agent needs task context for this request | **Prompt** injection    | Prompt layer            | `study.prompt.md` provides topic    |

---

## Quality Gates

Quality gates are validation checks applied when creating or modifying IA assets. The `ia-coord` agent enforces these automatically.

### Agent Quality Gates (A1–A9)

| Gate                          | Check                                                              | Fail Condition                                 |
| ----------------------------- | ------------------------------------------------------------------ | ---------------------------------------------- |
| **A1: Structure**             | Valid YAML frontmatter with `tools`, `model`, `description`        | Missing required fields or invalid structure   |
| **A2: Role Scope**            | Role defines generic capability, not task-specific context         | Hardcoded task context in role definition      |
| **A3: Model Selection**       | Model has `(copilot)` suffix; choice justified for complexity tier | No suffix or no reasoning for model tier       |
| **A4: Tool Aliases**          | Uses canonical tool group names; tools justified for role          | Wrong aliases or tools without rationale       |
| **A5: Constraint Hierarchy**  | Constraints use CRITICAL/IMPORTANT/GUIDELINES hierarchy            | Missing constraint tiers                       |
| **A6: Phased Methodology**    | Methodology uses phases, not flat instruction lists                | Flat list instead of phased approach           |
| **A7: Skill References**      | Skills referenced, not inlined (>30 lines = extract)               | Inline procedural knowledge exceeds threshold  |
| **A8: Delegation & Handoffs** | Subagents hidden; handoff targets valid; workflows have handoffs   | Missing visibility flags or invalid references |
| **A9: Catalog Sync**          | User-invokable agents registered in Section 9 catalog              | New agent not in copilot-instructions.md       |

#### Subagent Addendum (SA-1 to SA-7)

When `user-invokable: false`, these additional checks apply on top of A1–A9:

| Gate                           | Check                                                         | Fail Condition                            |
| ------------------------------ | ------------------------------------------------------------- | ----------------------------------------- |
| **SA-1: Visibility Flag**      | `user-invokable: false` present in frontmatter                | Missing flag (defaults to visible)        |
| **SA-2: Model Downgrade**      | Model is at most one tier below intended parent               | Same tier as orchestrator (wasted budget) |
| **SA-3: Minimal Tool Set**     | Tools follow least-privilege for the role                     | Write tools on a read-only subagent       |
| **SA-4: Caller Protocol**      | Has `<caller_protocol>` section documenting invocation format | No interface contract for parent          |
| **SA-5: Output Contract**      | Has `<output_format>` section documenting response structure  | Unstructured, unpredictable responses     |
| **SA-6: No Handoffs**          | No `handoffs:` in frontmatter                                 | Subagent trying to interact with users    |
| **SA-7: No Nested Delegation** | No `agents:` in frontmatter; no sub-subagent spawning         | Cascading delegation (cost + debug risk)  |

### Prompt Quality Gates (P1–P6)

| Gate                   | Check                                         | Fail Condition                                              |
| ---------------------- | --------------------------------------------- | ----------------------------------------------------------- |
| **P1: Thinness**       | ≤50 lines                                     | Prompt exceeds recommended size                             |
| **P2: No Methodology** | No phase/step workflows or constraint blocks  | Contains "Phase 1", "Step 1", CRITICAL/IMPORTANT            |
| **P3: No Tool Config** | No tools array or tool-specific instructions  | Mentions tools or specifies tools in YAML                   |
| **P4: Uses Variables** | Has `${input:}` or `${file:}` placeholders    | No variable placeholders for reusability                    |
| **P5: Context Only**   | Contains only task context + deliverable spec | Contains behavioral rules, role definitions, or methodology |
| **P6: No Duplication** | <70% content overlap with corresponding agent | >70% content overlap with corresponding agent               |

### Skill Quality Gates (S1–S5)

| Gate                           | Check                                                  | Fail Condition                                           |
| ------------------------------ | ------------------------------------------------------ | -------------------------------------------------------- |
| **S1: Agent-Agnostic**         | No references to specific agents                       | References specific agents (e.g., "the implement agent") |
| **S2: Tool-Agnostic**          | No tool-specific instructions                          | Mentions VS Code tools or CLI commands                   |
| **S3: Method-Focused**         | Contains step-by-step procedures                       | Describes concepts without actionable steps              |
| **S4: Portable**               | No project-specific paths or structures                | References project-specific paths or structures          |
| **S5: Progressive Disclosure** | Description in `<skill>` tag; SKILL.md loads on demand | Missing description in parent agent's `<skill>` tag      |

---

## Model Selection & FinOps

Model selection balances capability against cost. This section covers both the selection heuristic and the economic rationale for subagent delegation.

### Cost Ratios

| Model          | Input/1M tokens | Output/1M tokens | Relative Cost       | Best For                                                 |
| -------------- | --------------- | ---------------- | ------------------- | -------------------------------------------------------- |
| **Haiku 4.5**  | $0.80           | $4.00            | **0.33x**           | Read-only research, extraction, simple lookups           |
| **Sonnet 4.5** | $3.00           | $15.00           | **1.0x** (baseline) | Code editing, implementation, testing, reviews           |
| **Opus 4.6**   | $15.00          | $75.00           | **3.0x**            | Orchestration, planning, coordination, complex reasoning |

### Selection Heuristic

```
IF agent mostly reads/searches              → Haiku 4.5
IF agent writes code or reviews             → Sonnet 4.5
IF agent orchestrates, plans, or coordinates → Opus 4.6
IF agent is a subagent (user-invokable: false) → one tier below parent
```

### Common Assignments

| Agent Type                      | Recommended Model |
| ------------------------------- | ----------------- |
| Research / extraction subagent  | Haiku 4.5         |
| Implementation / testing agent  | Sonnet 4.5        |
| Review / analysis agent         | Sonnet 4.5        |
| Study / planning / coordination | Opus 4.6          |
| Master coordinator (ia-coord)   | Opus 4.6          |

### FinOps: The Subagent Cost Advantage

Subagent delegation shifts token consumption from expensive orchestrator models to cheap worker models, yielding significant savings.

**Scenario: Complex feature implementation**

| Approach            | Token Usage        | Model       | Cost (relative) |
| ------------------- | ------------------ | ----------- | --------------- |
| **Monolithic Opus** | 100K all-in-one    | Opus 3.0x   | **300 units**   |
| **Orchestrator**    | 20K orchestration  | Opus 3.0x   | 60 units        |
| + Research subagent | 50K file discovery | Haiku 0.33x | 16.5 units      |
| + Extract subagent  | 30K file analysis  | Haiku 0.33x | 9.9 units       |
| **Delegated total** | 100K distributed   | Mixed       | **86.4 units**  |

**Result: ~71% cost reduction** on the research/extraction portion, ~3.5x overall efficiency.

The savings come from two sources:

1. **Model cost differential**: Haiku is 9x cheaper than Opus per token
2. **Context preservation**: Parent doesn't waste expensive Opus tokens on intermediate exploration — subagents absorb that cost at Haiku rates, returning only distilled summaries

---

## Skill Extraction Heuristic

When reviewing agents, apply this heuristic to identify knowledge that should be extracted into standalone skills:

### Extraction Triggers

| Signal                                            | Action                  |
| ------------------------------------------------- | ----------------------- |
| >30 lines of procedural knowledge in an agent     | Extract to skill        |
| Same method appears in 2+ agents                  | Extract and deduplicate |
| Knowledge is domain-specific but agent-agnostic   | Extract to skill        |
| Agent references "follow this methodology" inline | Extract the methodology |
| Knowledge could apply to a different project      | Definitely extract      |

### Extraction Process

1. **Identify** — Find the knowledge block in the agent
2. **Verify portability** — Remove all agent names, tool names, model references
3. **Create skill file** — Place in `.github/skills/{name}/SKILL.md`
4. **Replace inline content** — Add `<skill>` reference in the agent
5. **Validate** — Run S1–S5 quality gates

### Skill vs Subagent Extraction

Not all extracted capability should become a skill. Use this discriminator:

| Extracted Content                     | → Skill | → Subagent |
| ------------------------------------- | ------- | ---------- |
| Decision framework / checklist        | ✅      |            |
| Step-by-step methodology (<200 lines) | ✅      |            |
| Dynamic codebase exploration          |         | ✅         |
| Web research / information gathering  |         | ✅         |
| Large file analysis                   |         | ✅         |
| Deterministic evaluation criteria     | ✅      |            |
| Cross-file pattern discovery          |         | ✅         |

---

## Anti-Patterns & Corrective Principles

### Common Anti-Patterns

| Anti-Pattern          | Symptom                                              | Fix                                             |
| --------------------- | ---------------------------------------------------- | ----------------------------------------------- |
| **Prompt bloat**      | Prompt >50 lines with phases/constraints             | Strip to context + deliverable                  |
| **Agent-as-prompt**   | Agent has no methodology, just passes through        | Add phases, constraints, delegation             |
| **Skill lock-in**     | Skill references "the implement agent"               | Remove all agent/tool names                     |
| **Copy-paste agents** | Two agents share >70% content                        | Extract shared content to skills                |
| **Monolithic agent**  | Single agent does everything, 500+ lines             | Split into agent + skills + subagent delegation |
| **Invisible skill**   | Procedural knowledge embedded in agent, never reused | Extract and register in skill catalog           |

### Subagent Anti-Patterns

| Anti-Pattern                    | Why It's Wrong                                      | Correct Approach                             |
| ------------------------------- | --------------------------------------------------- | -------------------------------------------- |
| **Subagent for simple lookup**  | Spawning overhead exceeds direct grep               | Use `grep_search` tool directly              |
| **Same-tier model**             | No FinOps benefit, adds latency                     | Downgrade model one tier (SA-2)              |
| **Overprivileged tools**        | Write tools on a read-only task                     | Remove `edit`/`bash` (SA-3, least privilege) |
| **Missing caller protocol**     | Parent guesses invocation format                    | Add `<caller_protocol>` section (SA-4)       |
| **Missing output contract**     | Parent parses unstructured response                 | Add `<output_format>` section (SA-5)         |
| **Subagent with handoffs**      | Subagents don't interact with users                 | Remove handoffs (SA-6)                       |
| **Skill disguised as subagent** | Deterministic knowledge doesn't need a separate LLM | Use a skill instead (zero cost)              |
| **Sub-subagent spawning**       | Cascading costs, debugging nightmare                | Keep delegation depth = 1 (SA-7)             |

### Corrective Design Principles

1. **Prompt thinness**: If a prompt exceeds 50 lines, some content belongs in the agent or a skill.
2. **Agent focus**: Each agent should have a clear, bounded responsibility. If it does "everything," decompose.
3. **Skill portability**: Every skill should pass the "different project" test — could it help someone working on a completely different codebase?
4. **Boundary testing**: After any change, run the [Clean Separation Test](#the-clean-separation-test) mentally.
5. **Progressive factoring**: Start with inline knowledge in agents; extract to skills only when reuse emerges or the agent grows beyond ~200 lines.
6. **Delegation economy**: Don't spawn a subagent when a direct tool call or a skill would suffice. Subagents are for context-heavy exploration, not simple operations.
7. **Least privilege**: Subagents get only the tools they need. Research subagents never get `edit` or `bash`.

---

## VS Code Implementation Reference

### YAML Frontmatter Properties (Agents)

```yaml
---
name: agent-name # kebab-case, matches filename
description: >- # One paragraph, shown in chat mode picker
  What this agent does and when to use it.
model: claude-opus-4-20250514 # or claude-sonnet-4-20250514
tools: # Groups, not individual tools
  - read # read_file, list_dir
  - search # grep_search, file_search, semantic_search
  - edit # replace_string_in_file, create_file
  - bash # run_in_terminal
  - agent # runSubagent
  - fetch # fetch_webpage
  - todo # manage_todo_list
  - web # browser tools (Playwright MCP)
agents: # Subagents available for delegation
  - research
  - extract
handoffs: # Workflow transitions
  - label: "Hand off to implement"
    agent: implement
    prompt: "Implement the plan above."
user-invokable: true # false = hidden subagent
disable-model-invocation: true # Prevent Copilot auto-routing
---
```

### Tool Group Reference

| Alias    | Tools Included                                                          | Use Case              |
| -------- | ----------------------------------------------------------------------- | --------------------- |
| `read`   | `read_file`, `list_dir`, `copilot_getNotebookSummary`                   | File inspection       |
| `search` | `grep_search`, `file_search`, `semantic_search`                         | Code discovery        |
| `edit`   | `replace_string_in_file`, `create_file`, `multi_replace_string_in_file` | Code modification     |
| `bash`   | `run_in_terminal`, `get_terminal_output`                                | Command execution     |
| `agent`  | `runSubagent`                                                           | Task delegation       |
| `fetch`  | `fetch_webpage`                                                         | Web content retrieval |
| `todo`   | `manage_todo_list`                                                      | Progress tracking     |
| `web`    | `mcp_microsoft_pla_browser_*`                                           | Browser automation    |

### Prompt Variable Types

```markdown
${input:variableName}          # User text input prompt
${input:variableName|default} # With default value
${file:relative/path.md} # File content injection
```

### Skill Directory Structure

```
.github/skills/
└── skill-name/
    ├── SKILL.md           # Core knowledge (loaded on demand)
    └── resources/         # Optional supplementary material
        ├── checklist.md
        └── examples.md
```

Skills are registered in `<skill>` tags within agents or the copilot-instructions file:

```markdown
<skill>
<name>skill-name</name>
<description>When and why to use this skill</description>
<file>.github/skills/skill-name/SKILL.md</file>
</skill>
```

---

## Templates & Blueprints

Templates for creating each layer are maintained as agent files and used by `ia-coord`:

| Template            | Location                               | Purpose                                                        |
| ------------------- | -------------------------------------- | -------------------------------------------------------------- |
| Agent Blueprint     | `.github/agents/agent-template.md`     | Full agent structure with YAML, role, constraints, methodology |
| Subagent Blueprint  | `.github/agents/subagent-template.md`  | Subagent structure with caller protocol, output contract, SA gates |
| Prompt Blueprint    | `.github/agents/prompt-template.md`    | Thin prompt structure enforcing ≤50 lines                      |
| Skill Blueprint     | `.github/agents/skill-template.md`     | Portable skill structure with progressive disclosure           |

Subagents follow a **dedicated template** because they have 7 mandatory structural differences from user-facing agents (SA-1 to SA-7): forced `user-invokable: false`, `.sub.agent.md` naming, no handoffs, no nested agents, mandatory `<caller_protocol>`, mandatory `<output_format>`, and model-downgraded tools.

### Using Templates

The `ia-coord` agent automatically selects the appropriate template based on the creation request. To use manually:

1. Read the relevant template file
2. Fill in placeholders following the structure
3. Run quality gates for the asset type (including SA-1–SA-7 for subagents)
4. Register in the catalog (`.github/copilot-instructions.md` Section 9) — user-invokable agents only

### Naming Conventions

| Asset | File Pattern | Example |
|-------|-------------|----------|
| User-facing agent | `{name}.agent.md` | `implement.agent.md` |
| Subagent (hidden) | `{name}.sub.agent.md` | `research.sub.agent.md` |
| Prompt | `{name}.prompt.md` | `study.prompt.md` |
| Skill | `{name}/SKILL.md` | `debug-hypothesis/SKILL.md` |

---

## Workflow: Creating IA Assets

The `ia-coord` agent follows a 6-phase methodology:

### Phase 1: Classify

Determine what to create based on keywords:

- "create agent" → Agent (user-facing or subagent — ask if unclear)
- "create prompt" → Prompt
- "create skill" → Skill
- Ambiguous → Ask user

### Phase 2: Discover

Audit existing assets to prevent duplication:

- Read `.github/copilot-instructions.md` Section 9 (catalog)
- Search for similar agents/prompts/skills
- Check if the need is already covered by an existing asset
- For subagent requests: verify the work can't be handled by a skill instead

### Phase 3: Design

Apply the three-layer model:

- Draft the asset using the appropriate template
- Run boundary tests mentally
- Determine if companion assets are needed (e.g., agent needs a skill extraction)
- For subagents:
  - Determine minimal tool set (SA-3)
  - Select model one tier below expected parent (SA-2)
  - Design caller protocol and output contract (SA-4, SA-5)

### Phase 4: Validate

Run quality gates:

- Agent → A1–A9 (+ SA-1–SA-7 if subagent)
- Prompt → P1–P6
- Skill → S1–S5
- Cross-check boundary separation

### Phase 5: Implement

Create the file(s):

- Write the asset to the correct location
- Update the catalog in `.github/copilot-instructions.md` (user-invokable agents only)
- Register skills in parent agents if applicable

### Phase 6: Report

Summarize what was created:

- Files created/modified
- Quality gates passed (including SA gates for subagents)
- Any boundary violations detected and resolved
- FinOps impact (model tier, cost implications)

---

## References

### Official Documentation

| Source                                | URL                                                                                                                           | Key Insight                                             |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Anthropic — Building Effective Agents | [anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents)        | Simplicity, composability, orchestrator-workers pattern |
| VS Code — Custom Agents               | [code.visualstudio.com/.../custom-agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents)             | YAML frontmatter, tool groups, deployment modes         |
| VS Code — Subagents                   | [code.visualstudio.com/.../subagents](https://code.visualstudio.com/docs/copilot/agents/subagents)                            | Context isolation, parallelization, runSubagent         |
| VS Code — Prompt Files                | [code.visualstudio.com/.../prompt-files](https://code.visualstudio.com/docs/copilot/customization/prompt-files)               | Variables, file references, ephemeral nature            |
| VS Code — Agent Skills                | [code.visualstudio.com/.../agent-skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)               | Progressive disclosure, portability, AgentSkills.io     |
| VS Code — Custom Instructions         | [code.visualstudio.com/.../custom-instructions](https://code.visualstudio.com/docs/copilot/customization/custom-instructions) | `.github/copilot-instructions.md` as base context       |
| AgentSkills.io                        | [agentskills.io](https://agentskills.io)                                                                                      | Open standard for portable agent skills                 |

### Anthropic Agentic Patterns Referenced

| Pattern                          | Application in This Methodology                              |
| -------------------------------- | ------------------------------------------------------------ |
| **Orchestrator-Workers**         | Parent agent delegates to subagents, synthesizes results     |
| **Routing**                      | FinOps-aware model selection — cheap models for simple tasks |
| **Parallelization (Sectioning)** | Independent subagents run simultaneously                     |
| **Prompt Chaining**              | Handoffs create sequential agent workflows                   |
| **Evaluator-Optimizer**          | Review agent validates implementation agent's output         |

### Project-Specific Files

| File                                | Purpose                                       |
| ----------------------------------- | --------------------------------------------- |
| `.github/copilot-instructions.md`   | Base instructions + agent catalog (Section 9) |
| `.github/agents/ia-coord.agent.md`      | Master coordinator enforcing this methodology |
| `.github/agents/research.sub.agent.md`  | Research subagent (Haiku, read-only)          |
| `.github/agents/extract.sub.agent.md`   | Extraction subagent (Haiku, read-only)        |
| `.github/agents/agent-template.md`      | Agent creation blueprint                      |
| `.github/agents/subagent-template.md`   | Subagent creation blueprint                   |
| `.github/agents/prompt-template.md`     | Prompt creation blueprint                     |
| `.github/agents/skill-template.md`      | Skill creation blueprint                      |

---

**Last Updated**: February 2026 (v3.0.0)
**Maintained by**: IA Coordination Agent (`ia-coord`)
