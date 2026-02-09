---
name: prompting-guide
description: Canonical prompt structure, quality guards, and task-type templates. Use when crafting prompts for coding tasks — the primary entry point for all prompting skills.
---

# Coding Prompt Patterns

Canonical prompt structure, quality guard sections, and task-type templates for coding tasks. Defines the standard XML sections used across all models.

**Related skills** (progressive specialization):
- Model-specific calibration → `sonnet-prompting` (Sonnet 4.5 guard tuning), `haiku-prompting` (Haiku 4.5 guard tuning)
- Reasoning directive quality → `reasoning-calibration` (phrasing, format, timing)
- Token budget / context management → `prompt-context-efficiency`
- `.prompt.md` file mechanics → `prompt-file-design`
- Interactive user input → `prompt-interaction-design`

---

## Unified Prompt Template

The complete set of sections available for coding prompts. Select sections based on the Section Decision Table below.

**Role guidance**: 1-3 lines max. Line 1 = identity. Line 2+ = convention anchoring (codebase patterns, style standards). Omit filler adjectives — they consume tokens without improving output.

```xml
<role>
You are a {seniority} {domain} Developer.
You follow {conventions/standards} and match existing codebase patterns.
</role>

<task>
{Verb} {target} {to achieve what}.

Requirements:
1. {Concrete requirement with measurable criteria}
2. {Concrete requirement with measurable criteria}
</task>

<constraints>
CRITICAL:
- {Non-negotiable rule}

IMPORTANT:
- {Strong preference}

GUIDELINES:
- {Soft guidance}
</constraints>

<anti-sycophancy>
- If the approach has risks or flaws, state them explicitly.
- Report what you did NOT find — absence of evidence is a finding.
- Challenge assumptions when evidence contradicts them.
</anti-sycophancy>

<completeness>
- Output ALL code completely. No placeholders, no abbreviations.
- NEVER use: "// ... rest", "# similar for others", "<!-- etc -->".
- Before finishing, enumerate all requirements and confirm each is addressed.
</completeness>

<scope-fence>
- ONLY modify files directly related to the stated task.
- If you notice unrelated issues, note them but do NOT fix them.
</scope-fence>

<constraint-anchor>
⚠️ PAUSE — Re-read the CRITICAL constraints above.
Confirm you are still operating within scope-fence boundaries.
</constraint-anchor>

<reasoning_guidance>
1. {Step with specific guidance}
2. {Step with specific guidance}
</reasoning_guidance>

<output_format>
{Specify exact structure with field names}

Example:
{Provide a concrete, minimal example}
</output_format>
```

---

## Section Decision Table

| Section | When Required | Skip When |
|---------|---------------|-----------|
| `<role>` | Always | Never skip |
| `<task>` | Always | Never skip |
| `<constraints>` | Always for agents/subagents; optional for simple prompts | One-shot questions with no risk |
| `<anti-sycophancy>` | Evaluation, review, verification, or decisional output | Pure generation with no judgment calls |
| `<completeness>` | Code generation, multi-step work, implementation tasks | Read-only analysis, short answers |
| `<scope-fence>` | Write-enabled tasks (file editing, code generation) | Read-only tasks |
| `<constraint-anchor>` | Long-running sessions (>10 tool calls expected) | Short, single-turn interactions |
| `<reasoning_guidance>` | Tasks requiring structured thinking (debug, review, refactor) | Simple generation with clear specs |
| `<output_format>` | Always when structured output expected | Free-form responses |

---

## Constraint Tiering

Structure constraints by severity for reliable adherence:

```xml
<constraints>
<!-- Tier 1: Non-negotiables — model focuses here most -->
CRITICAL:
- DO NOT {dangerous_pattern} — {reason}
- ALWAYS {security_requirement}

<!-- Tier 2: Strong preferences -->
IMPORTANT:
- Prefer {approved_patterns} over alternatives
- Avoid {anti_patterns} unless {exception_case}

<!-- Tier 3: Style guidance -->
GUIDELINES:
- Consider {optimization} when practical
- When possible, {best_practice}
</constraints>
```

---

## Quality Guard Sections

For full guard XML blocks (anti-sycophancy, completeness, scope-fence, constraint-anchor), see [guards.md](./guards.md).

---

## Task-Type Patterns

For specialized templates (Code Generation, Code Review, Debugging, Refactoring), see [task-patterns.md](./task-patterns.md).
