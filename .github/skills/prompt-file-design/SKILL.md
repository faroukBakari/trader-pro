---
name: prompt-file-design
description: VS Code prompt file (.prompt.md) format specification and design principles. Use when creating prompt files, designing reusable prompts, or reviewing prompt templates.
---

# Prompt File Design

Two-part reference for VS Code `.prompt.md` files: **File Format Specification** (syntax, variables, runtime behavior) and **Design Principles** (philosophy, quality tests, anti-patterns). Based on official VS Code documentation, GitHub best practices, and the three-layer agentic model.

**Scope boundary**: This skill covers `.prompt.md` *file format and design*. For prompt *content* patterns (XML sections, guards), apply `prompting-guide`. For *context management* within prompts, apply `prompt-context-efficiency`.

---

## Part 1: File Format Specification

### YAML Frontmatter & Variables

```yaml
---
name: prompt-name                        # Used after typing / in chat
description: "One-line purpose"          # Shown in slash command menu
agent: "agent-name"                      # Optional: which agent executes
model: "Claude Sonnet 4.5"              # Optional: override default model
tools: ['read', 'search']               # Optional: restrict tools
---
```

#### Body Components

| Component | Syntax | Purpose |
|-----------|--------|---------|
| Variables | `${input:varName:placeholder}` | User-provided parameters |
| Selection | `${selection}` | Currently selected code |
| Current file | `${file}` | Active editor file |
| Workspace | `${workspaceFolder}` | Root workspace path |
| File references | `[guidelines](../path/to/file.md)` | Link to referenced files (loaded as context) |
| Tool references | `#tool:githubRepo` | Include specific tool context |

### Dual-Runtime Compatibility

Prompt files can serve both **VS Code Copilot** (via `agent:` routing) and **Claude Code** (via `.claude/commands/` symlink) from a single source file.

#### Architecture

```
.github/prompts/plan.prompt.md    ← Source of truth
       ↓ (read by VS Code)               ↓ (symlinked)
VS Code Copilot agent routing     .claude/commands/ → ../.github/prompts/
```

#### Runtime Behavior Matrix

| File Section | VS Code Copilot | Claude Code |
|---|---|---|
| YAML frontmatter (`---` block) | **Consumed** — routes to agent, picks model | **Ignored** — skipped entirely |
| `${input:varName:prompt}` | **Rendered** as UI input widget | **Literal text** — harmless, ignored |
| Body (markdown content) | **Sent to model** as additive context (agent has full methodology) | **Primary instruction** — this IS the command |
| `$ARGUMENTS` | **Literal text** — harmless, ignored | **Interpolated** with user's input |

#### Enrichment Pattern

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

#### Key Principles

1. **Header unchanged** — VS Code frontmatter stays exactly as-is
2. **Body = compressed agent** — NOT a copy, but enough for standalone operation (~20-30 lines)
3. **Both variable systems present** — `${input:...}` (VS Code) and `$ARGUMENTS` (Claude Code) coexist harmlessly
4. **Single source of truth** — `.github/prompts/` is canonical; `.claude/commands/` is a symlink
5. **Still under 50 lines** — enriched prompts should stay within the size limit

#### Symlink Setup

```bash
# Directory symlink — zero-maintenance on new prompts
cd .claude && ln -s ../.github/prompts commands
```

Claude Code invokes as `/project:plan.prompt "add auth module"`. The `.prompt` suffix in the command name is a cosmetic tradeoff for zero-maintenance directory symlink.

---

## Part 2: Design Principles

For design philosophy, quality tests, prompt types (routing vs task), templates, and anti-patterns, see [design-principles.md](./design-principles.md).

---

## Sources

- [VS Code Prompt Files Documentation](https://code.visualstudio.com/docs/copilot/customization/prompt-files)
- [GitHub Blog — Better Prompts](https://github.blog/developer-skills/github/how-to-write-better-prompts-for-github-copilot/)
- [GitHub Copilot Chat Cookbook](https://docs.github.com/en/copilot/example-prompts-for-github-copilot-chat)
