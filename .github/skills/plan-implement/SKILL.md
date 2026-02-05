---
name: plan-implement
description: Implementation planning before code changes. Use when creating action plans, outlining features, or validating implementation choices before coding.
---

# Implementation Planning

Generate actionable implementation plans for validation before code changes.

## Scope

Applies when:
- Planning a new feature implementation
- Outlining multi-step code changes
- Validating implementation choices before writing code
- Creating executor-ready action plans

## Critical Constraints

CRITICAL:

- DO NOT create, edit, or delete any files — planning only
- DO NOT implement or modify code
- ALWAYS output the plan in conversation and stop

IMPORTANT:

- Search documentation before proposing approaches
- Identify exact file paths, modules, and dependencies
- Verify requirements and compliance for each step

## Execution Protocol

### Phase 1: Query Analysis

Parse the user's request deeply:
- Extract requirements and constraints
- Identify any attached context or references
- Note explicit and implicit acceptance criteria

### Phase 2: Documentation Review

1. Search `docs/DOCUMENTATION-GUIDE.md` for relevant documentation
2. Scan and internalize relevant sections
3. Check `.github/copilot-instructions.md` for immutable rules and patterns

### Phase 3: Codebase Research

1. Search workspace for similar features or patterns
2. Identify exact file paths, modules, and dependencies
3. Note existing conventions to follow

### Phase 4: Gap Analysis

Evaluate documentation against request:
- Identify potential conflicts
- Flag deprecations or outdated patterns
- Note logic gaps or missing requirements

### Phase 5: Refinement Loop

1. **Macro Planning:** Draft high-level step sequence
2. **Feasibility Check:** For each step, verify:
   - Requirements satisfied
   - Compliance with conventions
   - Risk level assessment
3. **Pivot if needed:** If complexity/risk high, revise immediately
4. **Confirm:** Continue until entire sequence is feasible

## Output Format

```markdown
**1- [Step Title]:** `[Risk: Low|Medium|High]`
- [Task description]
    * [Mermaid UML if logic is complex]
    * [Code snippet for illustration only]
    * [Command template if needed]
- [Next task description]

**2- [Step Title]:** `[Risk: Low|Medium|High]`
- [Task description]
```

## Risk Classification

| Level | Criteria | Guidance |
|-------|----------|----------|
| **Low** | Follows existing patterns, minimal dependencies | Proceed with confidence |
| **Medium** | New patterns or moderate dependencies | Document assumptions |
| **High** | Breaking changes, complex integrations | Consider alternatives |

## Guidelines

- Use Mermaid diagrams for complex logic flows
- Include illustrative code snippets (not implementation)
- Provide command templates where applicable
- Express wordings to clarify design choices
