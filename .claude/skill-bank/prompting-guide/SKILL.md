---
name: prompting-guide
description: Canonical prompt structure, quality guards, and task templates. Primary entry point for all prompting work
keywords: [prompt-structure, quality-guards, templates, task-types, unconditional-gates, gate-design]
category: prompting
disable-model-invocation: true
---

# Coding Prompt Patterns

Canonical prompt structure, quality guard sections, and task-type templates for coding tasks. Defines the standard XML sections used across all models.

**Related skills** (progressive specialization):
- Model-specific calibration → `sonnet-prompting` (Sonnet 4.5 guard tuning), `haiku-prompting` (Haiku 4.5 guard tuning)
- Reasoning directive quality → `reasoning-calibration` (phrasing, format, timing)
- Prompt-level context design / token budgets → `prompt-context-efficiency`
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

## Gate Design: Unconditional vs Conditional

Process gates in system prompts control when the model must perform a step (check a resource, run a tool, consult a skill). Gate design determines whether the model can bypass the step based on its own assessment.

### The Conditional Gate Problem

Conditional gates use **qualifier words** that require the model to classify the task before deciding whether the gate applies:

```
# ❌ CONDITIONAL GATE (vulnerable to framing bias)
"Non-trivial tasks MUST check the skill glossary before writing code."
```

The model must answer "Is this task non-trivial?" **before** the gate fires. This classification is biased by user prompt framing (see `reasoning-strategy` § Framing Bias). Words like "typo", "quick", "minor" anchor the model's assessment toward "trivial", causing gate bypass on tasks that actually need the gate.

**Anthropic confirms the mechanism**: Opus 4.5/4.6 are "more responsive to the system prompt" — they parse qualifiers like "non-trivial" as genuine conditions to evaluate, not as soft suggestions. The more capable the model, the more faithfully it enforces the escape hatch.

### The Unconditional Gate Pattern

Replace complexity-gated triggers with **unconditional gates + fast exit**:

```
# ✅ UNCONDITIONAL GATE (domain-matched, bias-resistant)
"ALWAYS check the skill glossary before editing code.
 If no skill matches the task domain → proceed directly."
```

**How it works**:
1. Gate fires on every qualifying action (unconditional)
2. The gate body performs domain matching (not complexity assessment)
3. If no match → fast exit, near-zero cost
4. If match → skill loaded, process followed

**Why it's cheap**: If glossary descriptions are already in the system prompt, the "check" is pattern-matching against loaded context — zero extra tool calls for non-matching tasks.

### Qualifier Words to Avoid in Gates

| Qualifier | Problem | Replacement |
|---|---|---|
| "Non-trivial" | Model classifies based on user framing, not task reality | Remove qualifier; gate fires unconditionally |
| "When appropriate" | Model defaults to "not appropriate" for casual-framed tasks | State the specific condition: "when editing code" |
| "If needed" | Model interprets minimizing framing as "not needed" | State the trigger: "before running tests" |
| "Consider checking" | Weak verb + hedge = always skipped | "ALWAYS check" |
| "For complex tasks" | "Complex" is subjective and framing-biased | State objective criteria: "for tasks touching >1 file" |

### Gate Design Decision Table

| Gate Purpose | Pattern | Example |
|---|---|---|
| **Process compliance** (must do X before Y) | Unconditional + fast exit | "ALWAYS check glossary. If no match → proceed." |
| **Safety check** (prevent dangerous action) | Unconditional, no exit | "ALWAYS verify file exists before overwriting." |
| **Optimization** (skip expensive step when unneeded) | Conditional on **objective criteria** | "Run full test suite when changes touch >2 files." |
| **Escalation** (upgrade effort for harder tasks) | Conditional on **observable signals** | "Escalate to Opus if reasoning exceeds 3 hops." |

**Rule**: Process compliance gates should be **unconditional**. Only optimization and escalation gates should be conditional — and their conditions must be **objective** (file count, error count, hop count), never **subjective** (complexity, importance, triviality).

---

## Quality Guard Sections

For full guard XML blocks (anti-sycophancy, completeness, scope-fence, constraint-anchor), see [guards.md](./guards.md).

---

## Task-Type Patterns

For specialized templates (Code Generation, Code Review, Debugging, Refactoring), see [task-patterns.md](./task-patterns.md).
