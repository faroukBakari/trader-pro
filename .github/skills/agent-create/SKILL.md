---
name: agent-create
description: Create VS Code custom agents (.agent.md files) with proper YAML frontmatter, tool configuration, and Claude optimizations. Use when creating agents, configuring subagents, or setting up handoffs.
---

# Custom Agent Creation

You are creating a **VS Code Custom Agent** (`.agent.md` file) for GitHub Copilot. These agents extend Copilot with specialized behaviors, tool restrictions, and orchestration patterns.

---

## <constraints>

### CRITICAL
- **File location**: `.github/agents/{name}.agent.md`
- **No code fence wrappers** — file starts directly with `---`
- **Valid tool aliases only**: `read`, `search`, `edit`, `execute`, `agent`, `web/fetch`, `todo`
- **Model format**: Include `(copilot)` suffix — e.g., `Claude Opus 4.5 (copilot)`

### IMPORTANT
- Hidden subagents require `user-invokable: false`
- Read-only agents should restrict to `tools: ['read', 'search', 'web/fetch']`
- Implementation agents typically need `execute` for terminal access

### GUIDELINES
- Use XML-style sections (`<constraints>`, `<methodology>`) for Claude optimization
- Apply constraint hierarchy: CRITICAL > IMPORTANT > GUIDELINES
- Keep prompts focused on one coherent workflow

</constraints>

---

## <yaml_reference>

### Required Properties

```yaml
---
name: agent-name              # Lowercase, hyphenated
description: What this agent does
---
```

### Optional Properties

| Property | Type | Purpose |
|----------|------|---------|
| `model` | string | `Claude Opus 4.5 (copilot)` or `Claude Sonnet 4.5 (copilot)` |
| `tools` | array | Tool restrictions — see aliases below |
| `agents` | array | Allowed subagents: `['research', 'test']` |
| `user-invokable` | bool | `false` hides agent from user (subagent only) |
| `argument-hint` | string | Placeholder text in agent picker |
| `handoffs` | array | Sequential workflow transitions |

### Tool Aliases

| Alias | Description |
|-------|-------------|
| `read` | Read files and notebooks |
| `search` | Search files and content (grep, glob) |
| `edit` | Modify files |
| `execute` | Run terminal commands |
| `agent` | Invoke subagents |
| `web/fetch` | Fetch web pages |
| `todo` | Task list management |

### Handoffs Configuration

```yaml
handoffs:
  - label: Button Label
    agent: target-agent
    prompt: Instructions passed to target agent
    send: false  # false = user confirms, true = auto-submit
```

</yaml_reference>

---

## <prompt_structure>

### Recommended Layout

```markdown
# Role Title

You are a **[Role]** that [purpose].

---

## <constraints>

### CRITICAL
- **RULE** — explanation

### IMPORTANT
- **RULE** — explanation

### GUIDELINES
- **RULE** — explanation

</constraints>

---

## <methodology>

[Step-by-step workflow]

</methodology>

---

## <output_format>

[Expected output structure]

</output_format>
```

### Constraint Hierarchy

| Level | Expectation | Typical Use |
|-------|-------------|-------------|
| CRITICAL | Must follow | Safety rules, immutable constraints |
| IMPORTANT | Should follow | Best practices, strong preferences |
| GUIDELINES | May follow | Suggestions, style preferences |

</prompt_structure>

---

## <agent_patterns>

### Read-Only Research Agent

For information gathering without side effects:

```yaml
---
name: research
description: Information gathering - read-only, no modifications
tools: ['read', 'search', 'web/fetch']
user-invokable: false
---

# Research Specialist

You gather information without modifying files.

## <constraints>

### CRITICAL
- **Never** suggest code modifications
- **Only** report findings with file references
```

### Implementation Agent

For code changes with validation:

```yaml
---
name: implement
description: Code implementation with test validation
tools: ['read', 'search', 'edit', 'execute', 'agent', 'todo']
agents: ['research', 'test']
handoffs:
  - label: Review Changes
    agent: review
    prompt: Review all changes made in this session.
    send: false
---

# Implementation Engineer

You implement code changes with continuous validation.

## <constraints>

### CRITICAL
- **Always** run tests after changes
- **Never** edit generated code directories
```

### Orchestrator Agent

For coordinating multiple agents:

```yaml
---
name: study
description: Technical analysis with implementation options
tools: ['read', 'search', 'agent', 'web/fetch']
agents: ['research']
handoffs:
  - label: Plan Implementation
    agent: plan
    prompt: Create implementation plan based on analysis.
    send: false
  - label: Start Implementation
    agent: implement
    prompt: Implement the recommended solution.
    send: false
---
```

</agent_patterns>

---

## <workflow>

1. **Define purpose** — What does this agent do?
2. **Select tools** — Minimum required (principle of least privilege)
3. **Choose model** — See `model-selection` skill for FinOps-aware guidance
4. **Set visibility** — `user-invokable: false` for subagents
5. **Configure handoffs** — If sequential workflow needed
6. **Write prompt** — Use constraint hierarchy and XML sections
7. **Validate** — Check tool aliases, model format, file location

</workflow>

---

## <validation>

Before finalizing, verify:

- [ ] File path: `.github/agents/{name}.agent.md`
- [ ] Starts with `---` (no code fence wrapper)
- [ ] Tool aliases are valid (not `bash` — use `execute`; not `fetch` — use `web/fetch`)
- [ ] Model includes `(copilot)` suffix
- [ ] Hidden subagents have `user-invokable: false`
- [ ] Prompt uses constraint hierarchy (CRITICAL/IMPORTANT/GUIDELINES)

</validation>
