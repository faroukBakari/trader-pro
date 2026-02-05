# Methodology: Crafting Optimal `.agent.md` Files

> **Target Environment:** VS Code + GitHub Copilot  
> **Target Models:** Claude Opus 4.5, Sonnet 4.5, Haiku 4.5  
> **Version:** 1.0 | Updated: 2026-02-05

---

## Table of Contents

1. [Quick Reference](#1-quick-reference)
2. [Understanding the Agent System](#2-understanding-the-agent-system)
3. [File Structure & Syntax](#3-file-structure--syntax)
4. [YAML Frontmatter Properties](#4-yaml-frontmatter-properties)
5. [Crafting the Prompt Body](#5-crafting-the-prompt-body)
6. [Claude-Specific Optimizations](#6-claude-specific-optimizations)
7. [Subagent Orchestration](#7-subagent-orchestration)
8. [Tool Configuration](#8-tool-configuration)
9. [Handoffs & Workflows](#9-handoffs--workflows)
10. [Project-Specific Patterns](#10-project-specific-patterns)
11. [Examples Library](#11-examples-library)
12. [Migration Guide](#12-migration-guide)
13. [Testing & Validation](#13-testing--validation)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Quick Reference

### Directory Structure

```
.github/
├── agents/                      # Official VS Code agent directory
│   ├── plan.agent.md           # Planning agent
│   ├── implement.agent.md      # Implementation agent
│   ├── research.agent.md       # Research subagent (read-only)
│   ├── review.agent.md         # Code review agent
│   └── test.agent.md           # Testing specialist
├── prompts/                     # Reusable prompt templates (for / commands)
│   └── *.prompt.md
└── copilot-instructions.md      # Global instructions (always applied)
```

### Minimal Valid Agent File

```markdown
---
description: Brief description of what this agent does
---

You are a [role]. Your task is to [primary objective].
```

### Complete Agent File Template

```markdown
---
name: agent-name
description: Concise description shown in UI (required)
model: Claude Opus 4.5 (copilot)
argument-hint: Example prompt or usage hint
tools: ["read", "search", "edit", "bash", "agent"]
agents: ["research", "test"]
user-invokable: true
disable-model-invocation: false
target: vscode
handoffs:
  - label: Review Changes
    agent: review
    prompt: Review the implementation above for quality and security.
    send: false
---

# Role: [Role Name]

[Core prompt instructions...]
```

---

## 2. Understanding the Agent System

### What Are Custom Agents?

Custom agents are specialized AI personas with:

- **Focused instructions** tailored to specific tasks
- **Restricted tool access** for safety and precision
- **Subagent orchestration** for complex workflows
- **Context isolation** to prevent prompt pollution

### Agent vs Prompt File

| Aspect           | `.agent.md`                  | `.prompt.md`                 |
| ---------------- | ---------------------------- | ---------------------------- |
| **Location**     | `.github/agents/`            | `.github/prompts/`           |
| **Invocation**   | Agent picker dropdown        | `/` slash commands           |
| **Context**      | Controls full agent behavior | Appends to current agent     |
| **Tools**        | Defines available tools      | Inherits from current agent  |
| **Statefulness** | Persists during session      | One-shot prompt augmentation |

### Mental Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VS CODE AGENT SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │   Built-in   │    │    Custom    │    │   Subagent   │         │
│  │    Agent     │    │    Agent     │    │   (spawned)  │         │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤         │
│  │ • Agent      │    │ • plan       │    │ • research   │         │
│  │ • Plan       │    │ • implement  │    │ • test       │         │
│  │ • Ask        │    │ • review     │    │ • analyze    │         │
│  └──────────────┘    └──────────────┘    └──────────────┘         │
│         │                   │                   ↑                  │
│         │                   │                   │                  │
│         └───────────────────┴───────────────────┘                  │
│                             │                                       │
│                    ┌────────┴────────┐                             │
│                    │  YAML + Prompt  │                             │
│                    │  Configuration  │                             │
│                    └─────────────────┘                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. File Structure & Syntax

### Filename Conventions

```
ALLOWED CHARACTERS: a-z, A-Z, 0-9, ., -, _
EXTENSION: .agent.md (preferred) or .md (legacy in .github/agents/)

NAMING PATTERNS:
✅ plan.agent.md          # Simple, descriptive
✅ code-review.agent.md   # Hyphenated for multi-word
✅ research_v2.agent.md   # Versioned with underscore
❌ my agent.agent.md      # No spaces
❌ plan!.agent.md         # No special chars
```

### File Encoding

- **UTF-8** encoding required
- **LF** line endings (Unix-style)
- No BOM (Byte Order Mark)

### Structure Anatomy

```markdown
---
# YAML Frontmatter (optional but recommended)
# Properties control agent behavior
---

# Markdown Body (required)

# Contains the actual prompt instructions

# This is what Claude receives as the system prompt
```

---

## 4. YAML Frontmatter Properties

### Property Reference Table

| Property                   | Type               | Required | Default       | Description                                      |
| -------------------------- | ------------------ | -------- | ------------- | ------------------------------------------------ |
| `name`                     | string             | No       | filename      | Display name in UI                               |
| `description`              | string             | **Yes**  | -             | Brief purpose description (shown as placeholder) |
| `model`                    | string \| string[] | No       | Current model | AI model to use                                  |
| `argument-hint`            | string             | No       | -             | Example prompt shown in input field              |
| `tools`                    | string[]           | No       | All tools     | Available tool names/aliases                     |
| `agents`                   | string[]           | No       | All           | Allowed subagent names                           |
| `user-invokable`           | boolean            | No       | true          | Show in agent dropdown                           |
| `disable-model-invocation` | boolean            | No       | false         | Prevent as subagent                              |
| `target`                   | string             | No       | both          | `vscode`, `github-copilot`, or both              |
| `handoffs`                 | object[]           | No       | -             | Sequential workflow transitions                  |
| `mcp-servers`              | object             | No       | -             | MCP server configs (org-level only)              |

### Model Specification

```yaml
# Single model (preferred)
model: Claude Opus 4.5 (copilot)

# Fallback chain (tries in order)
model:
  - Claude Opus 4.5 (copilot)
  - Claude Sonnet 4.5 (copilot)
  - Claude Haiku 4.5 (copilot)

# Available Claude models (as of 2026-02):
# - Claude Opus 4.5 (copilot)    → Complex reasoning, architecture
# - Claude Sonnet 4.5 (copilot)  → Balanced capability/speed
# - Claude Haiku 4.5 (copilot)   → Fast, cost-effective
```

### Model Selection Guidelines

| Use Case                    | Recommended Model | Rationale                       |
| --------------------------- | ----------------- | ------------------------------- |
| Architecture decisions      | Opus 4.5          | Complex reasoning required      |
| Code implementation         | Sonnet 4.5        | Good balance of capability      |
| Quick lookups, simple edits | Haiku 4.5         | Fast, efficient                 |
| Research subagents          | Sonnet 4.5        | Needs capability, runs parallel |
| Security review             | Opus 4.5          | High-stakes analysis            |

### Tools Configuration

```yaml
# Enable all tools
tools: ['*']

# Read-only agent (safe for research)
tools: ['read', 'search', 'web/fetch']

# Implementation agent
tools: ['read', 'search', 'edit', 'execute', 'agent']

# Planning agent with subagent support
tools: ['read', 'search', 'agent', 'todo']
```

### Tool Aliases Reference

| Alias       | Maps To                            | Description           |
| ----------- | ---------------------------------- | --------------------- |
| `read`      | Read, NotebookRead                 | Read file contents    |
| `edit`      | Edit, MultiEdit, Write             | Modify files          |
| `search`    | Grep, Glob                         | Search files/content  |
| `execute`   | runInTerminal, awaitTerminal, etc. | Run terminal commands |
| `agent`     | custom-agent, Task                 | Invoke subagents      |
| `web/fetch` | WebFetch                           | Fetch web pages       |
| `todo`      | TodoWrite                          | Task list management  |

---

## 5. Crafting the Prompt Body

### Claude-Optimized Prompt Structure

Based on Anthropic's best practices, structure prompts with clear sections:

```markdown
---
description: Your agent description
---

# Role: [Descriptive Role Name]

You are a [role] with expertise in [domain].

[1-2 sentences on working style and priorities]

---

# <constraints>

## CRITICAL (Non-negotiable)

- **Constraint 1** — explanation
- **Constraint 2** — explanation

## IMPORTANT (Strong preferences)

- Preference with context

## GUIDELINES (Apply judgment)

- Flexible guidance

</constraints>

---

# <methodology>

## Phase 1: [Name]

1. Step one
2. Step two

## Phase 2: [Name]

1. Step one
2. Step two

</methodology>

---

# <output_format>

[Define expected output structure, format, and examples]

</output_format>
```

### XML-Style Section Tags

Claude models respond well to XML-style semantic sections:

```markdown
# <section_name>

Content here...
</section_name>
```

**Recommended sections:**

- `<constraints>` — Rules and limitations
- `<methodology>` — Step-by-step process
- `<output_format>` — Expected response structure
- `<examples>` — Few-shot examples
- `<context>` — Background information
- `<tools>` — Tool usage guidance

### Constraint Hierarchy

Structure rules by enforcement level:

```markdown
# <constraints>

## CRITICAL (Non-negotiable)

Rules that must NEVER be violated

## IMPORTANT (Strong preferences)

Rules that SHOULD be followed unless clear reason exists

## GUIDELINES (Apply judgment)

Flexible guidance to consider

</constraints>
```

### Prompt Length Guidelines

| Agent Complexity       | Recommended Length | Max Allowed  |
| ---------------------- | ------------------ | ------------ |
| Simple (focused task)  | 500-1500 chars     | 5,000 chars  |
| Moderate (multi-step)  | 1500-5000 chars    | 15,000 chars |
| Complex (orchestrator) | 5000-15000 chars   | 30,000 chars |

**Rule:** Shorter is better. Long prompts dilute attention.

---

## 6. Claude-Specific Optimizations

### Anthropic's Agent Design Principles

From official Anthropic guidance:

> "Start simple. Find the simplest solution possible, and only increase complexity when needed."

| Principle        | Application                                    |
| ---------------- | ---------------------------------------------- |
| **Simplicity**   | Start with minimal tools, add only when needed |
| **Transparency** | Show agent's planning steps explicitly         |
| **Clear ACI**    | Document tools thoroughly                      |
| **Ground truth** | Encourage environment validation at each step  |
| **Guardrails**   | Use tool restrictions for safety               |

### Effective Prompt Patterns

#### 1. Role Grounding

```markdown
# Role: Solutions Architect

You are a **Solutions Architect** with deep expertise in **System Design**,
**Integration Patterns**, and **Technology Selection**.

You think in terms of:

- **Tradeoffs**, not perfect solutions
- **Portability**, avoiding vendor lock-in
- **Leverage**, using existing assets first
```

#### 2. Constraint Clarity

```markdown
## CRITICAL

- **NEVER** modify files in `*_generated/` directories
- **ALWAYS** run tests after code changes
- **NO** use of `any` type in TypeScript

## IMPORTANT

- Prefer existing patterns over new paradigms
- Update documentation for API changes
```

#### 3. Decision Framework

```markdown
## When to Ask vs Proceed

| Situation             | Action                                   |
| --------------------- | ---------------------------------------- |
| Clear single approach | Proceed with rationale                   |
| 2+ viable options     | Present options, ask preference          |
| High-stakes decision  | Present options AND request confirmation |
```

#### 4. Explicit Output Format

```markdown
# <output_format>

## During Execution

Keep updates brief:
```

✅ Completed task X
⏳ Working on Y...

```

## Completion Summary
```

## Summary

**Completed:** [what was done]
**Changes:** [file links]
**Tests:** [status]

```
</output_format>
```

### Token Efficiency

Claude handles large contexts well, but:

1. **Front-load critical info** — Put most important constraints first
2. **Use tables** — More compact than prose for structured data
3. **Reference external files** — Use `[link](path)` instead of embedding
4. **Avoid redundancy** — State each constraint once

### Extended Thinking Support

For complex reasoning tasks (Opus 4.5):

```markdown
## Complex Decision Protocol

For architectural decisions or debugging:

1. **Articulate the problem** clearly before solving
2. **Consider 2-3 approaches** before committing
3. **Explain your reasoning** as you progress
4. **Validate assumptions** against codebase evidence
```

---

## 7. Subagent Orchestration

### Why Use Subagents?

| Benefit                    | Description                             |
| -------------------------- | --------------------------------------- |
| **Context isolation**      | Keeps main agent focused                |
| **Parallel execution**     | Research multiple areas simultaneously  |
| **Specialized behavior**   | Different tools/models per task         |
| **Reduced token usage**    | Only final result returns to main agent |
| **Experimental isolation** | Dead ends don't pollute main context    |

### Configuring Subagent Access

```yaml
# Allow all subagents
agents: ['*']

# Restrict to specific subagents
agents: ['research', 'test', 'review']

# Prevent any subagent use
agents: []
```

### Creating Hidden Subagents

For agents only accessible via orchestration:

```yaml
---
name: research
description: Internal research subagent
user-invokable: false # Hide from dropdown
disable-model-invocation: false # Allow invocation by other agents
tools: ["read", "search", "fetch"] # Read-only for safety
model: Claude Sonnet 4.5 (copilot) # Balance capability/cost
---
```

### Orchestrator Pattern

Main agent that delegates to specialized subagents:

```yaml
---
name: architect
description: Technical architect that delegates to specialists
tools: ['agent', 'read', 'search', 'todo']
agents: ['research', 'security-review', 'implementation-planner']
---

# Role: Technical Architect

You orchestrate complex technical work by delegating to specialized agents.

## Delegation Strategy

| Task Type | Delegate To | Expected Output |
|-----------|-------------|-----------------|
| Background research | research | Summary of findings |
| Security analysis | security-review | Risk assessment |
| Implementation plan | implementation-planner | Step-by-step plan |

## Workflow

1. Analyze the request to identify required expertise
2. Delegate research tasks to subagents (can run in parallel)
3. Synthesize subagent outputs
4. Present unified recommendation
```

### Invoking Subagents in Prompts

```markdown
## Research Protocol

When you need background information:

- Use a subagent to research the topic
- Specify exactly what information you need
- The subagent will return only the final summary

Example prompt to subagent:
"Research authentication patterns used in this codebase. Return:

1. Current auth implementation locations
2. Token handling patterns
3. Any security considerations found"
```

---

## 8. Tool Configuration

### Principle of Least Privilege

**Start restrictive, add tools as needed.**

| Agent Type     | Recommended Tools                 | Rationale           |
| -------------- | --------------------------------- | ------------------- |
| Research       | `read`, `search`, `fetch`         | Read-only, safe     |
| Planning       | `read`, `search`, `agent`, `todo` | Can delegate, track |
| Implementation | `read`, `search`, `edit`, `bash`  | Full modification   |
| Review         | `read`, `search`, `agent`         | Analyze, delegate   |

### Read-Only Agent Pattern

For research and analysis without side effects:

```yaml
---
name: research
description: Gathers information without modifying files
tools: ['read', 'search', 'web/fetch']
---

# Research Specialist

Your role is information gathering only.

## CRITICAL
- **NEVER** suggest code modifications
- **NEVER** use edit tools
- **ONLY** report findings

## Output
Return structured research findings:
- Current state of X
- Relevant patterns found
- Recommendations for consideration
```

### Implementation Agent Pattern

Full capability for code changes:

```yaml
---
name: implement
description: Implements code changes with test validation
tools: ['read', 'search', 'edit', 'execute', 'agent', 'todo']
agents: ['research', 'test']
---

# Implementation Engineer

## CRITICAL
- **ALWAYS** run tests after changes
- **NEVER** edit generated code (`*_generated/`)
- **ALWAYS** update a todo list for multi-step changes

## Subagent Usage
- Use `research` subagent for background investigation
- Use `test` subagent for test-focused analysis
```

### Tool Documentation for Claude

When tools have complex usage, document in the prompt:

```markdown
## Tool Usage Guidelines

### Terminal Commands

Before running any terminal command:

1. Check if a Makefile target exists first
2. Use project environment wrappers (`make`, `poetry run`)
3. Add timeout for commands piped to `head`/`tail`

### File Editing

- Include 3-5 lines of context around changes
- Verify file path exists before editing
- Never edit `*_generated/` directories
```

---

## 9. Handoffs & Workflows

### What Are Handoffs?

Handoffs create guided sequential workflows between agents:

```
┌───────────┐     handoff     ┌───────────┐     handoff     ┌───────────┐
│   Plan    │ ──────────────→ │ Implement │ ──────────────→ │  Review   │
└───────────┘                 └───────────┘                 └───────────┘
    Button:                       Button:
    "Start Implementation"        "Review Changes"
```

### Handoff Configuration

```yaml
handoffs:
  - label: Start Implementation # Button text
    agent: implement # Target agent name
    prompt: | # Pre-filled prompt
      Implement the plan above. Follow each step in order.
    send: false # Auto-submit if true
    model: Claude Sonnet 4.5 (copilot) # Optional model override
```

### Common Workflow Patterns

#### 1. Plan → Implement → Review

```yaml
# plan.agent.md
handoffs:
  - label: Start Implementation
    agent: implement
    prompt: Implement the plan above step by step.
    send: false

# implement.agent.md
handoffs:
  - label: Review Changes
    agent: review
    prompt: Review all changes made in this session.
    send: false
```

#### 2. Write Tests → Implement (TDD)

```yaml
# tdd-red.agent.md
---
name: tdd-red
description: Write failing tests first (TDD red phase)
tools: ["read", "search", "edit"]
handoffs:
  - label: Make Tests Pass
    agent: tdd-green
    prompt: Implement code to make these tests pass.
---
```

#### 3. Research → Decide → Implement

```yaml
# study.agent.md
handoffs:
  - label: With Option A
    agent: implement
    prompt: Implement using the first recommended approach.
  - label: With Option B
    agent: implement
    prompt: Implement using the alternative approach.
```

### When to Use Handoffs

| Scenario                      | Use Handoffs? | Rationale                 |
| ----------------------------- | ------------- | ------------------------- |
| Human approval between phases | Yes           | Explicit control points   |
| Fixed sequential workflow     | Yes           | Clear progression         |
| Dynamic task decomposition    | No            | Use subagents instead     |
| Parallel research             | No            | Subagents run in parallel |

---

## 10. Project-Specific Patterns

### trader-pro Integration

Align agent behavior with existing project conventions:

````yaml
---
name: trader-implement
description: Implementation engineer for trader-pro codebase
model: Claude Opus 4.5 (copilot)
tools: ['read', 'search', 'edit', 'execute', 'agent', 'todo']
---

# Implementation Engineer (trader-pro)

## Project-Specific Rules

### CRITICAL
- **NEVER** use `npm` or `poetry` directly — always use `make` targets
- **NEVER** edit files in `*_generated/` directories
- **ALWAYS** run `make -C backend type-check` after Python changes
- **ALWAYS** run tests after implementation: `make -C backend test`

### Documentation First
Before implementing:
1. Check `docs/DOCUMENTATION-GUIDE.md` for relevant docs
2. Scan `.github/copilot-instructions.md` for immutable rules
3. Search `@workspace` for existing patterns

### Type Safety
- TypeScript: No `any` — use `unknown` + type guards
- Python: Full type hints required, no `Any`

### Commands Reference
```bash
make -f project.mk dev-fullstack  # Start dev servers
make -C backend test              # Backend tests
make -C frontend test             # Frontend tests
make -f project.mk generate       # Regenerate specs/clients
````

````

### Referencing copilot-instructions.md

Include critical project rules inline or reference:

```markdown
## Project Conventions

Follow all rules in [copilot-instructions.md](../../copilot-instructions.md).

Key reminders:
- Module independence (no cross-module imports)
- Type safety (no `any`, full type hints)
- Makefile-first commands
````

---

## 11. Examples Library

### Example 1: Research Subagent

```markdown
---
name: research
description: Information gathering without code changes
user-invokable: false
tools: ["read", "search", "fetch"]
model: Claude Sonnet 4.5 (copilot)
---

# Research Specialist

You gather information and report findings. You never modify code.

## CRITICAL

- Output findings only — no implementation suggestions
- Be concise — summarize, don't dump raw data
- Cite specific file paths for all references

## Output Format
```

## Research Findings: [Topic]

### Current Implementation

- [file.py](file.py#L10-L50): [What it does]

### Patterns Found

- Pattern 1: [Description with file references]

### Relevant Documentation

- [doc.md](doc.md): [Key points]

### Recommendations

1. [Actionable finding]
2. [Actionable finding]

```

```

### Example 2: Planning Agent with Handoff

```markdown
---
name: plan
description: Creates implementation plans without modifying code
model: Claude Opus 4.5 (copilot)
tools: ["read", "search", "agent", "todo"]
agents: ["research"]
handoffs:
  - label: Start Implementation
    agent: implement
    prompt: Execute the plan above step by step.
    send: false
---

# Implementation Planner

Create detailed action plans for a follow-up implementation agent.

## CRITICAL

- **NEVER** modify code — output is limited to the plan
- **ALWAYS** validate feasibility by checking codebase
- **DELEGATE** research tasks to the research subagent

## Methodology

1. **Analyze** the request thoroughly
2. **Research** using subagents for unfamiliar areas
3. **Plan** with specific file paths and code snippets
4. **Validate** each step is feasible before including

## Output Format

**1. [Step Title]:** `[Risk: Low|Medium|High]`

- Task description with [file references](path)
- Code snippet or command if helpful

**2. [Step Title]:** `[Risk: Low|Medium|High]`

- ...

⚠️ **Review the plan**, then click "Start Implementation" to proceed.
```

### Example 3: Security Review Agent

```markdown
---
name: security-review
description: Analyzes code for security vulnerabilities
model: Claude Opus 4.5 (copilot)
tools: ["read", "search"]
---

# Security Reviewer

Analyze code for security vulnerabilities following OWASP guidelines.

## Focus Areas

| Category     | Check For                            |
| ------------ | ------------------------------------ |
| Injection    | SQL, command, LDAP injection risks   |
| Auth         | Weak auth, session management issues |
| XSS          | Reflected, stored, DOM-based XSS     |
| CSRF         | Missing CSRF protection              |
| Secrets      | Hardcoded credentials, exposed keys  |
| Dependencies | Known vulnerable packages            |

## Output Format

## Security Review: [Scope]

### Findings

| Severity    | Location             | Issue              | Recommendation            |
| ----------- | -------------------- | ------------------ | ------------------------- |
| 🔴 Critical | [file:L10](file#L10) | SQL injection      | Use parameterized queries |
| 🟡 Medium   | [file:L25](file#L25) | Missing validation | Add input sanitization    |

### Summary

- Critical: X
- High: X
- Medium: X
- Low: X

### Action Items

1. [Prioritized fix]
2. [Prioritized fix]
```

### Example 4: TDD Orchestrator

```markdown
---
name: tdd
description: Test-driven development orchestrator
tools: ["agent"]
agents: ["tdd-red", "tdd-green", "tdd-refactor"]
---

# TDD Orchestrator

Guide test-driven development using the Red-Green-Refactor cycle.

## Workflow

1. Use **tdd-red** subagent to write failing tests first
2. Use **tdd-green** subagent to implement minimal passing code
3. Use **tdd-refactor** subagent to improve code quality

## Delegation

For each feature request:
```

→ tdd-red: Write failing test
← Returns: Test code + failure confirmation
→ tdd-green: Implement to pass
← Returns: Implementation + passing tests
→ tdd-refactor: Clean up
← Returns: Refactored code + tests still passing

```

Report final summary of all test iterations.
```

---

## 12. Migration Guide

### From `.prompt.md` to `.agent.md`

Your current prompt files use this structure:

```markdown
---
agent: "agent"
name: "plan-v2"
model: "Claude Opus 4.5"
description: "Description here"
---
```

**Migration steps:**

1. **Create directory:**

   ```bash
   mkdir -p .github/agents
   ```

2. **Rename and move files:**

   ```bash
   mv .github/prompts/plan.prompt.md .github/agents/plan.agent.md
   ```

3. **Update frontmatter:**

   **Before (`.prompt.md`):**

   ```yaml
   ---
   agent: "agent"
   name: "plan-v2"
   model: "Claude Opus 4.5"
   description: "Generate implementation plans"
   ---
   ```

   **After (`.agent.md`):**

   ```yaml
   ---
   name: plan
   description: Generate implementation plans without modifying code
   model: Claude Opus 4.5 (copilot)
   tools: ["read", "search", "agent", "todo"]
   argument-hint: Describe the feature to plan
   handoffs:
     - label: Start Implementation
       agent: implement
       prompt: Execute the plan above.
   ---
   ```

4. **Add new properties:**
   - `tools` — Explicit tool access
   - `agents` — Allowed subagents
   - `handoffs` — Workflow transitions
   - `argument-hint` — Input guidance

### Property Mapping

| Old Property     | New Property  | Notes                      |
| ---------------- | ------------- | -------------------------- |
| `agent: "agent"` | Remove        | Implicit, not needed       |
| `name`           | `name`        | Same                       |
| `model`          | `model`       | Add `(copilot)` suffix     |
| `description`    | `description` | Same                       |
| N/A              | `tools`       | New — define explicitly    |
| N/A              | `agents`      | New — restrict subagents   |
| N/A              | `handoffs`    | New — workflow transitions |

### Keep Both Systems

You can maintain both during transition:

- `.github/agents/*.agent.md` → Agent picker access
- `.github/prompts/*.prompt.md` → `/` slash command access

---

## 13. Testing & Validation

### Validation Checklist

Before using a new agent:

```
□ YAML frontmatter parses without errors
□ description is present (required)
□ tools array contains only valid tool names
□ agents array contains only existing agent names
□ model name uses correct format with (copilot) suffix
□ handoff agent references exist
□ Prompt body renders correctly in preview
```

### VS Code Diagnostics

Access the customization diagnostics view:

1. Right-click in the Chat view
2. Select **Diagnostics**
3. View loaded agents, any errors

### Testing Subagents

To verify subagent invocation:

1. Create a simple test agent:

   ```yaml
   ---
   name: test-orchestrator
   tools: ["agent"]
   agents: ["research"]
   ---
   Use the research subagent to find all TODO comments.
   ```

2. Invoke and verify:
   - Subagent is spawned (check output)
   - Only final result returns
   - Main context not polluted

### Testing Handoffs

1. Create source agent with handoff
2. Complete a task
3. Verify handoff button appears
4. Click and verify:
   - Target agent activated
   - Prompt pre-filled correctly
   - Context carries forward

---

## 14. Troubleshooting

### Common Issues

| Issue                  | Cause                   | Solution                   |
| ---------------------- | ----------------------- | -------------------------- |
| Agent not in dropdown  | `user-invokable: false` | Set to `true` or remove    |
| Subagent not available | Not in `agents` list    | Add to `agents: []` array  |
| Tool not working       | Wrong tool name         | Check tool aliases table   |
| Model not found        | Incorrect format        | Use `Model Name (copilot)` |
| Handoff not appearing  | Agent name mismatch     | Match exact agent filename |
| YAML parse error       | Invalid syntax          | Validate YAML formatting   |

### Debugging Steps

1. **Check diagnostics:** Right-click Chat → Diagnostics
2. **Verify file location:** Must be in `.github/agents/`
3. **Check filename:** Only `a-z A-Z 0-9 . - _` allowed
4. **Validate YAML:** Use online YAML validator
5. **Test incrementally:** Start with minimal config, add features

### Error Messages

| Error                | Meaning                        | Fix                             |
| -------------------- | ------------------------------ | ------------------------------- |
| "Agent not found"    | `handoffs.agent` doesn't exist | Create target agent or fix name |
| "Tool not available" | Tool disabled or invalid       | Check valid tool names          |
| "Unable to parse"    | YAML syntax error              | Fix YAML formatting             |

---

## Appendix: Complete Reference

### All YAML Properties

```yaml
---
# Identity
name: string                    # Display name (default: filename)
description: string             # Required. Brief purpose description.

# Model Configuration
model: string | string[]        # AI model(s) to use

# Tools & Agents
tools: string[]                 # Available tools (default: all)
agents: string[] | '*'          # Allowed subagents (default: all)

# Visibility Control
user-invokable: boolean         # Show in dropdown (default: true)
disable-model-invocation: bool  # Prevent as subagent (default: false)

# Environment
target: 'vscode' | 'github-copilot'  # Target env (default: both)

# UI Hints
argument-hint: string           # Placeholder in input field

# Workflows
handoffs:                       # Sequential workflow transitions
  - label: string               # Button text
    agent: string               # Target agent name
    prompt: string              # Pre-filled prompt
    send: boolean               # Auto-submit (default: false)
    model: string               # Override model for handoff

# Enterprise (org/enterprise level only)
mcp-servers:                    # MCP server configurations
  server-name:
    type: 'local'
    command: string
    args: string[]
    tools: string[]
    env: object
---
```

### Tool Aliases Complete List

| Category  | Alias       | Description           |
| --------- | ----------- | --------------------- |
| Reading   | `read`      | Read file contents    |
| Editing   | `edit`      | Modify files          |
| Searching | `search`    | Find files/content    |
| Execution | `execute`   | Run terminal commands |
| Agents    | `agent`     | Invoke subagents      |
| Web       | `web/fetch` | Fetch web pages       |
| Tasks     | `todo`      | Task list management  |

---

## Changelog

| Version | Date       | Changes                                                                   |
| ------- | ---------- | ------------------------------------------------------------------------- |
| 1.0     | 2026-02-05 | Initial methodology based on official VS Code and Anthropic documentation |
