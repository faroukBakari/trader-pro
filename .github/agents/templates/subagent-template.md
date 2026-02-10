---
name: subagent-template
description: Template for creating new subagents — reference document used by ia-coord
model: Claude Haiku 4.5 (copilot)
tools: ["read", "search"]
user-invokable: false
---

# Subagent Template

Use this template when creating new subagents. Replace placeholders `{like_this}` with actual content.
File naming convention: `{name}.sub.agent.md`

---

## <!-- BLUEPRINT START: Copy ONLY the content between BLUEPRINT START and BLUEPRINT END into the new file. The written file must be raw text starting with "---" (YAML frontmatter). When verifying, ignore any backtick fences the read_file tool adds to its display output — those are rendering artifacts, not part of the file. -->

name: {subagent-name}
description: {Purpose} - {capability focus}. Delegated by parent agents for {specific task type}.
model: Claude {Haiku 4.5|Sonnet 4.5} (copilot)
tools: ['vscode', '{tool1}', '{tool2}']

# ⚠️ MCP toolsets require '/_' glob suffix: 'context7/_', 'filesystem/_', 'playwright/_' — never bare names

## user-invokable: false

# {Role Title}

You are a **{Specialist Role}** optimized for {specific capability}. You {key behavior} and {working style}.

**Approach**: {Core operating principle — e.g., "Search first, read targeted sections, summarize precisely."}

---

## <constraints>

### CRITICAL

- **{RULE}** — {brief explanation}
- **{RULE}** — {brief explanation}

### IMPORTANT

- **{RULE}** — {brief explanation}
- **{RULE}** — {brief explanation}

### GUIDELINES

- **{RULE}** — {brief explanation}

</constraints>

---

## <methodology>

### Phase 1: {Phase Name}

1. {Action with specific guidance}
2. {Action with specific guidance}

### Phase 2: {Phase Name}

1. {Action with specific guidance}
2. {Action with specific guidance}

### {Additional phases as needed}

</methodology>

---

## <caller_protocol>

Callers should invoke with structured prompts:

```
{Describe expected invocation format}:
- [Specific question/task 1]
- [Specific question/task 2]

Context: [Why this matters / what caller will do with info]
```

Good invocation examples:

- "{Example 1: focused, specific request}"
- "{Example 2: focused, specific request}"

Poor invocation (too broad):

- "{Example of what NOT to send}" ← {Why it's bad}

</caller_protocol>

---

## <output_format>

```markdown
## {Report Title}: [Topic]

### {Section 1}

- {What goes here}

### {Section 2}

- {What goes here}

### {Gaps / Not Found}

- {Explicitly note absent items}
```

</output_format>

---

## <anti_patterns>

| Don't          | Do Instead      |
| -------------- | --------------- |
| {Bad practice} | {Good practice} |
| {Bad practice} | {Good practice} |

</anti_patterns>

<!-- BLUEPRINT END -->

---

> **Template guidance**: Apply `agent-create` skill (frontmatter, constraints) and `ia-quality-gates` skill (A1-A9 + SA1-SA7 gates) when populating this template. See ia-coord methodology for model downgrade rules and tool least-privilege.
