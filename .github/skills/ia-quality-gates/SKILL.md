---
name: ia-quality-gates
description: Quality gate validation for agentic design artifacts (agents, subagents, prompts, skills). Apply when creating, reviewing, or validating .agent.md, .sub.agent.md, .prompt.md, or SKILL.md files. Covers A1-A9 (agent gates), SA1-SA7 (subagent addendum), P1-P6 (prompt gates), and S1-S5 (skill gates) with fail conditions and remediation actions.
---

# IA Quality Gates

Systematic validation framework for agentic design artifacts. Ensures structural integrity, boundary compliance, and design consistency across agents, subagents, prompts, and skills.

---

## When to Use This Skill

- **Creating** a new agent, subagent, prompt, or skill — run applicable gates before output
- **Validating** an existing artifact — run all gates and report findings
- **Reviewing** a PR that modifies `.agent.md`, `.sub.agent.md`, `.prompt.md`, or `SKILL.md` files
- **Self-checking** — any agent verifying its own compliance after modifications

---

## Methodology

### Phase 1: Select Gate Set

Determine which gates apply based on artifact type:

| Artifact Type | Gate Set | Total Gates |
|---------------|----------|-------------|
| User-facing agent (`.agent.md`) | A1–A9 | 9 |
| Subagent (`.sub.agent.md`) | A1–A9 + SA1–SA7 | 16 |
| Prompt (`.prompt.md`) | P1–P6 | 6 |
| Skill (`SKILL.md`) | S1–S5 | 5 |

**Subagent detection**: File has `.sub.agent.md` extension OR frontmatter contains `user-invokable: false`.

### Phase 2: Run Gates

Execute every gate in the applicable set. If ANY gate fails, fix and re-run.

#### Agent Gates (A1–A9)

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **A1: Structure** | Valid YAML frontmatter with `tools`, `model`, `description` | Missing required fields or invalid YAML syntax | Add missing fields |
| **A2: Role Scope** | Role defines generic capability, not task-specific context | Hardcoded task context in role definition | Generalize role |
| **A3: Model Selection** | Model has `(copilot)` suffix; choice justified for complexity tier | No suffix or unjustified model tier | Add suffix; justify |
| **A4: Tool Aliases** | Uses canonical tool group names; tools justified for role | Wrong aliases (e.g., `bash` instead of `execute`) or unneeded tools | Fix aliases |
| **A5: Constraint Hierarchy** | Constraints use CRITICAL/IMPORTANT/GUIDELINES tiers | Missing tiers or flat constraint list | Restructure |
| **A6: Phased Methodology** | Methodology uses phases, not flat instruction lists | Flat list without phase structure | Restructure into phases |
| **A7: Skill References** | Skills referenced, not inlined (>30 lines = extract) | Inline procedural knowledge exceeds 30 lines | Extract to skill |
| **A8: Delegation & Handoffs** | Subagents use `.sub.agent.md`; handoff targets valid | Missing visibility flags, invalid references, or wrong naming | Fix naming/refs |
| **A9: Catalog Sync** | User-invokable agents registered in Section 9 of `copilot-instructions.md` | New agent missing from catalog | Update catalog |

#### Subagent Addendum (SA1–SA7)

Apply **on top of** A1–A9 when artifact is a subagent:

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **SA-1: Naming & Visibility** | File is `{name}.sub.agent.md`; `user-invokable: false` in frontmatter | Missing flag (defaults visible) or wrong file extension | Rename file; add flag |
| **SA-2: Model Downgrade** | Model is one tier below intended parent, or same tier with documented rationale | Same tier as parent without justification | Downgrade model or document rationale |
| **SA-3: Minimal Tools** | Tools follow least-privilege for role | Write tools on read-only subagent | Remove excess tools |
| **SA-4: Caller Protocol** | Has `<caller_protocol>` section with invocation examples | No interface contract for parent | Add section |
| **SA-5: Output Contract** | Has `<output_format>` section with response template | Unstructured, unpredictable responses | Add section |
| **SA-6: No Handoffs** | No `handoffs:` in frontmatter | Subagent trying to interact with users | Remove handoffs |
| **SA-7: No Nesting** | No `agents:` in frontmatter; no sub-subagent spawning | Cascading delegation (cost + debug risk) | Remove agents list |

**SA-3 tool privilege reference:**

| Subagent Role | Allowed Tools | Rationale |
|---------------|---------------|-----------|
| Read-only research | `['read', 'search']` | No write access needed |
| Web research | `['read', 'search', 'web/fetch']` | Adds web for info gathering |
| Implementation worker | `['read', 'search', 'edit', 'execute']` | Full set only when writing code |
| Analysis / extraction | `['read', 'search']` | Analyze and report, never modify |

#### Prompt Gates (P1–P6)

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **P1: Thinness** | ≤ 50 lines total | Prompt exceeds recommended size | Extract methodology to agent |
| **P2: No Methodology** | No phase/step workflows or constraint blocks | Contains "Phase 1", "Step 1", CRITICAL/IMPORTANT | Move to agent |
| **P3: No Tool Config** | No tools array or tool-specific instructions | Mentions or specifies tools | Remove (agent owns tools) |
| **P4: Uses Variables** | Has `${input:}` or `${file:}` placeholders | No variable placeholders for reusability | Add variables |
| **P5: Context Only** | Contains only task context + deliverable spec | Contains behavioral rules, role definitions, or methodology | Strip non-context |
| **P6: No Duplication** | <70% content overlap with corresponding agent | >70% overlap with agent | Deduplicate |

#### Skill Gates (S1–S5)

| Gate | Check | Fail Condition | Fail Action |
|------|-------|----------------|-------------|
| **S1: Agent-Agnostic** | No references to specific agents | References "the implement agent" or similar | Remove references |
| **S2: Tool-Agnostic** | No tool-specific instructions | Mentions specific tools or CLI commands | Remove tool refs |
| **S3: Method-Focused** | Contains step-by-step procedures | Describes concepts without actionable steps | Add methodology |
| **S4: Portable** | No project-specific paths or structures | References project-specific paths | Generalize |
| **S5: Progressive Disclosure** | Description in `<skill>` tag; SKILL.md loads on demand | Missing description in parent agent's skill reference | Add description |

### Phase 3: Report Results

Present gate results using this format:

```markdown
### Quality Gates
- ✅ A1: Structure valid
- ✅ A2: Role scope generic
- ❌ A4: **FAIL** — Uses `bash` instead of `execute`
  - **Fix**: Replace `bash` with `execute` in tools array
- ✅ A9: Catalog synced

### Summary
- **Passed**: 8/9
- **Failed**: 1 (A4)
- **Status**: ❌ REQUIRES FIX
```

For subagents, append SA gates after A gates. Only show the applicable gate set.

---

## Anti-Patterns

Common gate-skipping behaviors to avoid:

- ❌ **Selective checking** — Running only A1-A3 and skipping A7-A9 because they seem less important. ALL gates must pass.
- ❌ **Assumed compliance** — Marking gates as passed without actually verifying (e.g., assuming model has `(copilot)` suffix without checking).
- ❌ **SA gate amnesia** — Forgetting SA1-SA7 exist when creating a subagent. If `user-invokable: false`, SA gates are mandatory.
- ❌ **Prompt free pass** — Treating prompts as "just text" and skipping P1-P6. Prompts that absorb methodology (P2 violation) are the most common boundary failure.
- ❌ **Soft failures** — Noting a gate failure but proceeding to output without fixing. Every failure must be resolved before output.
- ✅ **Systematic sweep** — Run every gate, report every result, fix every failure, then output.
