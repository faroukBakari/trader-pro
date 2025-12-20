---
agent: "agent"
name: "plan-v1"
model: "Claude Opus 4.5"
description: "Generate a step-by-step TDD action plan ONLY. Do not implement or modify code. Save plan to docs/tmp/, and report the file path."
---

## Feature Implementation Planner

Generate a detailed, actionable implementation plan designed for a follow-up "Executor" agent. Your **final action** must be to save this plan to a file and output the path. 
**Constraint**: This agent must not implement or modify code. Output is limited to the saved plan path.

## Inputs

1. **Feature Description**: (string) The high-level description of the feature to be built.
2. **User Materials**: (string, optional) Additional context, designs, or notes.

---

### Step 1: Analyze Context

1. **Architecture**: Review `docs/DOCUMENTATION-GUIDE.md` and relevant methodology docs (e.g., `PROVIDER-SYSTEM.md`, `MODULAR_BACKEND_ARCHITECTURE.md`).
2. **Requirements**: Internalize the **Feature Description** and constraints.
3. **Discovery**: Search `@workspace` for similar patterns and identify exact file paths, modules, and dependencies.

---

### Step 2: Generate Plan Content

Deconstruct the feature into logical implementation phases. Each phase must focus on a completed unit of work.

For each task within a phase, specify:
* **Agent**: The subagent best suited for the task (e.g., `@codeWriter`, `@tester`).
* **File paths**: Exact file locations.
* **Actions**: Specific, executable instructions (e.g., "Define interface in `types.ts`").
* **Verification**: Command to run (e.g., `make test`, `npm run build`).
* **Expected result**: What constitutes a successful completion of the step.

---

### Step 3: Format, Save, and Report

1. **Determine Filename**: Prefix with `plan_`, use snake_case based on the feature, and end with `.md`. (e.g., `plan_add_auth_logging.md`).
2. **Target Directory**: `docs/tmp/`
3. **Final Output**: You must output a **single line** confirming the save: 
   `Plan saved to docs/tmp/[filename].md`

#### Plan Output Format

```markdown
### Implementation Plan: [Feature Name]

**Methodology**: [Context Link]
**Target Module**: [Path]

#### Phase 1: [Phase Name - e.g., Infrastructure/Types]
- [ ] **Agent**: `[@codeWriter]`
    * **Action**: Create/Update (`path/to/file`): [Specific instruction]
    * **Verify**: [Command] -> Expected: Success / Pass

#### Phase 2: [Phase Name - e.g., Logic/Integration]
- [ ] **Agent**: `[@codeWriter]`
    * **Action**: Implement logic in (`path/to/file`)
    * **Verify**: [Command] -> Expected: Success / Pass

#### Final Validation
- [ ] **Agent**: `[@tester]`
    * **Action**: Run full suite and linting
    * **Verify**: `npm run test && npm run lint`
```

---

⚠️ **IMPORTANT**: Do not write or modify any source code. Only generate the plan document.