# Prompt File Design Principles

Design philosophy, quality tests, prompt types, templates, and anti-patterns for `.prompt.md` files. Complements the File Format Specification in the main skill.

---

## Core Principle

Prompts are the **WHAT** layer. They specify context, deliverables, and success criteria. They do NOT contain methodology, constraints, tool instructions, or behavioral rules — those belong in agents and skills.

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
description: "Use {agent} agent to {verb} {object}"
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
description: "Use {agent} agent to {verb} {object}"
---

${input:request:What would you like to {verb}?}
```

### Task Prompt Template

```markdown
---
name: {prompt-name}
description: "{One-line purpose}"
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
