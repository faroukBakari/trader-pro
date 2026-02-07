# Prompt Template

Use this template when creating new prompts. Prompts should be **THIN** — focusing only on context and deliverable specification, never methodology.

---

<!-- BLUEPRINT START: Copy ONLY the content between BLUEPRINT START and BLUEPRINT END into the new file. The written file must be raw text starting with "---" (YAML frontmatter). When verifying, ignore any backtick fences the read_file tool adds to its display output — those are rendering artifacts, not part of the file. -->
---
agent: "{agent-name}"  # Which agent executes this prompt
model: "Claude {Sonnet|Opus|Haiku} {4.5|4.6} (copilot)"  # Optional: override agent default
name: "{prompt-name}"  # Used after typing / in chat
description: "{One-line description of what this prompt does}"
argument-hint: "{Optional: placeholder text to guide user input}"  # Optional
tools: ['{tool1}', '{tool2}']  # Optional: override agent tool list
---

# {Prompt Title}

{Brief description of what this prompt does and when to use it}

## Context

{Describe the context needed for this task. Use variables where appropriate:}

- **Target**: ${input:target:{default_value}}
- **Scope**: ${selection}  # If working with selected code
- **Files**: [Relevant files or folders to consider]

{Or reference instruction files:}
See [project guidelines](../instructions/guidelines.md) for standards.

## Deliverable

{Clearly specify what output is expected:}

**Format**: {markdown report | code implementation | analysis document | etc.}

**Must include**:
- {Required element 1}
- {Required element 2}
- {Required element 3}

**Success criteria**:
- {Criterion 1}
- {Criterion 2}

{Optional: Include example format}
```
{Example output structure}
```

## Additional Context

{Any extra context, constraints, or references specific to this task}
<!-- BLUEPRINT END -->

---

> **Template guidance**: Apply `ia-quality-gates` skill (P1-P6 gates) when populating this template. See [prompt-examples.md](./prompt-examples.md) for VS Code variables, boundary guidance, and concrete good/bad examples.
