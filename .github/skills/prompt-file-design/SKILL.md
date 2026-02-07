---
name: prompt-file-design
description: VS Code prompt file (.prompt.md) design principles, variable patterns, boundary rules, and quality tests. Use when creating prompt files, designing reusable prompts, or reviewing prompt templates.
---

# Prompt File Design

Principles for designing high-quality VS Code `.prompt.md` files — the reusable task templates that define **WHAT** to deliver without prescribing **HOW**. Based on official VS Code documentation, GitHub best practices, and the three-layer agentic model.

---

## Core Principle

Prompts are the **WHAT** layer. They specify context, deliverables, and success criteria. They do NOT contain methodology, constraints, tool instructions, or behavioral rules — those belong in agents and skills.

---

## Structure Reference

```yaml
---
name: prompt-name                        # Used after typing / in chat
description: VS Code prompt file (.prompt.md) design principles, variable patterns, boundary rules, and quality tests. Use when creating prompt files, designing reusable prompts, or reviewing prompt templates.
agent: "agent-name"                      # Optional: which agent executes
model: "Claude Sonnet 4.5"              # Optional: override default model
tools: ['read', 'search']               # Optional: restrict tools
---
```

### Body Components

| Component | Syntax | Purpose |
|-----------|--------|---------|
| Variables | `${input:varName:placeholder}` | User-provided parameters |
| Selection | `${selection}` | Currently selected code |
| Current file | `${file}` | Active editor file |
| Workspace | `${workspaceFolder}` | Root workspace path |
| File references | `[guidelines](../path/to/file.md)` | Link to referenced files (loaded as context) |
| Tool references | `#tool:githubRepo` | Include specific tool context |

---

## Design Rules

### 1. Agent-Agnostic

Prompts should work with any compatible agent. If a prompt only works with one specific agent, the methodology has leaked.

**Test**: Can another agent execute this prompt and produce a valid result? → Yes = correct.

### 2. Variable-Driven

Parameterize via `${input:}` instead of creating separate prompt files per variation.

```markdown
## Context
- **Component**: ${input:name:MyComponent}
- **Framework**: ${input:framework:Vue}
- **Target**: ${file}
```

### 3. Reference, Don't Duplicate

Link to standards files instead of copying content:

```markdown
Follow patterns in [TESTING.md](../../docs/TESTING.md).
Respect conventions in [copilot-instructions.md](../copilot-instructions.md).
```

### 4. Deliverable-Focused

Specify WHAT success looks like:

```markdown
## Deliverable
Generate test file(s) that:
- Cover happy path, error cases, and boundary conditions
- Follow existing test patterns in this project
- Include descriptive test names

## Success Criteria
- All generated tests pass
- No `any` types or `# type: ignore`
```

### 5. Size Limit: ≤50 Lines

If a prompt exceeds 50 lines, content is leaking from the agent or skill layer. Extract methodology to the agent, extract reusable knowledge to a skill.

---

## Dual-Runtime Compatibility

Prompt files can serve both **VS Code Copilot** (via `agent:` routing) and **Claude Code** (via `.claude/commands/` symlink) from a single source file.

### Architecture

```
.github/prompts/plan.prompt.md    ← Source of truth
       ↓ (read by VS Code)               ↓ (symlinked)
VS Code Copilot agent routing     .claude/commands/ → ../. github/prompts/
```

### Runtime Behavior Matrix

| File Section | VS Code Copilot | Claude Code |
|---|---|---|
| YAML frontmatter (`---` block) | **Consumed** — routes to agent, picks model | **Ignored** — skipped entirely |
| `${input:varName:prompt}` | **Rendered** as UI input widget | **Literal text** — harmless, ignored |
| Body (markdown content) | **Sent to model** as additive context (agent has full methodology) | **Primary instruction** — this IS the command |
| `$ARGUMENTS` | **Literal text** — harmless, ignored | **Interpolated** with user's input |

### Enrichment Pattern

VS Code prompts that only contain `${input:...}` are "thin launchers" — they route to an agent that has the full methodology. Claude Code has no agent routing, so thin prompts produce poor results.

**Solution**: Enrich the body with a compressed summary of the agent's methodology. This serves as additive reinforcement in VS Code and primary instruction in Claude Code.

```markdown
---
name: plan
agent: "plan"
description: "Create an implementation plan"
---

${input:request:What would you like to plan?}

## Context

You are an **Implementation Planner**. Create detailed, actionable plans without modifying code.

### Key Rules
- {3-5 agent-specific constraints, not generic project rules}
- Read `docs/DOCUMENTATION-GUIDE.md` to find relevant docs
- Use `make` targets — never raw `npm`, `poetry`, `pip`, or `python` commands

### Methodology
1. **{Phase}** — {compressed description}
2. **{Phase}** — {compressed description}
3. **{Phase}** — {compressed description}

### Output
{What to produce — format expectations}

### Skills
Apply these skills from `.github/skills/`: {skill1}, {skill2}

$ARGUMENTS
```

### Key Principles

1. **Header unchanged** — VS Code frontmatter stays exactly as-is
2. **Body = compressed agent** — NOT a copy, but enough for standalone operation (~20-30 lines)
3. **Both variable systems present** — `${input:...}` (VS Code) and `$ARGUMENTS` (Claude Code) coexist harmlessly
4. **Single source of truth** — `.github/prompts/` is canonical; `.claude/commands/` is a symlink
5. **Still under 50 lines** — enriched prompts should stay within the size limit

### Symlink Setup

```bash
# Directory symlink — zero-maintenance on new prompts
cd .claude && ln -s ../.github/prompts commands
```

Claude Code invokes as `/project:plan.prompt "add auth module"`. The `.prompt` suffix in the command name is a cosmetic tradeoff for zero-maintenance directory symlink.

---

## Quality Tests

Apply all four before finalizing any prompt file:

| Test | Pass Condition | Fail Signal |
|------|----------------|-------------|
| **Swap Test** | Replace this prompt with another on the same agent — agent still works correctly | Prompt contains methodology the agent depends on |
| **Length Test** | ≤50 lines | Duplicated standards, inline methodology, or constraint leaks |
| **Variable Test** | Uses `${input:}` for user-specific parameters | Hardcoded values requiring separate prompt files per variation |
| **Reference Test** | Standards/guidelines linked, not copied into the prompt | Prompt repeats content from other files |

---

## Prompt Types

### Routing Prompts (Slash Command Shortcuts)

Minimal prompt files that serve as **agent switching shortcuts** via the `/` slash command menu. Solves the UX friction of dropdown navigation when chaining agents in a sequential workflow.

**Why routing prompts exist**: In VS Code Copilot Chat, agents appear in the chat mode **dropdown** (click → scroll → select). Prompts appear in the **slash command** menu (type `/` → pick). Slash commands are faster for mid-session agent switching, especially in sequential workflows like study → plan → implement.

**Pattern**:

```yaml
---
name: {agent-name}
agent: "{agent-name}"
description: VS Code prompt file (.prompt.md) design principles, variable patterns, boundary rules, and quality tests. Use when creating prompt files, designing reusable prompts, or reviewing prompt templates.
---

${input:request:What would you like to {verb}?}
```

**Rules**:
- One routing prompt per user-facing agent (1:1 mapping)
- ~6-7 lines maximum — no context, no deliverable, no references
- `name` matches the agent name for discoverability
- `description` follows the pattern: "Use {agent} agent to {verb} {object}"
- Body is a single `${input:request}` variable with a helpful placeholder
- When a new agent is created, create a matching routing prompt

**Routing prompts are the exception** to the "agent-agnostic" rule — they exist specifically to route to one agent. This is their only purpose.

### Task Prompts (Context Templates)

Standard prompt files that carry reusable task context to any compatible agent. These are the primary prompt type described throughout this skill.

| Category | Example Names | Key Variables |
|----------|--------------|---------------|
| Code Generation | `new-component`, `new-endpoint`, `new-module` | `${input:name}`, `${input:module}` |
| Testing | `create-tests`, `test-edge-cases` | `${selection}`, `${input:framework}` |
| Code Review | `review-diff`, `security-scan` | `${input:branch}`, `${file}` |
| Documentation | `explain-code`, `document-api`, `changelog` | `${selection}`, `${input:audience}` |
| Debugging | `debug-error`, `trace-flow` | `${input:errorMessage}` |
| Refactoring | `simplify`, `modernize` | `${selection}`, `${input:targetPattern}` |
| Communication | `summarize-changes`, `write-issue` | `${input:context}` |

---

## Templates

### Routing Prompt Template

```markdown
---
name: {agent-name}
agent: "{agent-name}"
description: VS Code prompt file (.prompt.md) design principles, variable patterns, boundary rules, and quality tests. Use when creating prompt files, designing reusable prompts, or reviewing prompt templates.
---

${input:request:What would you like to {verb}?}
```

### Task Prompt Template

```markdown
---
name: {prompt-name}
description: VS Code prompt file (.prompt.md) design principles, variable patterns, boundary rules, and quality tests. Use when creating prompt files, designing reusable prompts, or reviewing prompt templates.
---

## Context
- **Target**: ${input:target:default}
- **Scope**: ${input:scope:default}
- **Reference**: ${file}

Follow conventions in [relevant-doc](../../path/to/doc.md).

## Deliverable
{What to produce}:
- {Required element 1}
- {Required element 2}
- {Required element 3}

## Success Criteria
- {Measurable criterion 1}
- {Measurable criterion 2}
```

---

## Anti-Patterns

| Anti-Pattern | Example | Fix |
|--------------|---------|-----|
| **Methodology leak** | "First search codebase, then analyze, then..." | Move phases to agent |
| **Constraint leak** | "NEVER modify files. ALWAYS verify types." | Move to agent constraints |
| **Standard duplication** | Copying coding style guide into prompt body | Link to instruction file |
| **Tool prescription** | "Use grep to find X, then read_file to check Y" | Agent decides tools |
| **Over-specification** | Role definition, reasoning guidance, output templates | Those are agent/skill content |
| **Identity crisis** | Prompt with `<role>`, `<constraints>`, `<methodology>` | It's an agent pretending to be a prompt — split properly |
| **Fat routing prompt** | Routing prompt with context/deliverable sections | Keep routing prompts minimal (~7 lines) |

---

## Sources

- [VS Code Prompt Files Documentation](https://code.visualstudio.com/docs/copilot/customization/prompt-files)
- [GitHub Blog — Better Prompts](https://github.blog/developer-skills/github/how-to-write-better-prompts-for-github-copilot/)
- [GitHub Copilot Chat Cookbook](https://docs.github.com/en/copilot/example-prompts-for-github-copilot-chat)
- [awesome-copilot](https://github.com/github/awesome-copilot)
