---
agent: "agent"
model: "Claude Opus 4.5"
name: "follow-plan-v2.1"
description: "Follow a predefined plan step-by-step with validation and a clear action hierarchy."
---

We have defined and validated a plan that I need you to follow. You must adhere to the following Operational Constraints and Execution Workflow strictly.

# I. Operational Constraints (Terminal & Environment)

**CRITICAL:** Before executing **ANY** terminal command, you must follow this priority logic. Do not bypass this structure.

1.  **Identify the Target:**
    * Declare your intent: "I need to run [action]."
    * Check for a `Makefile` in the project root/module.

2.  **Select the Command Strategy (Priority Order):**
    * **Priority 1: Makefile Target (MANDATORY).** If a target exists (e.g., `make test`, `make format`), you *must* use it.
    * **Priority 2: Environment-Aware Package Managers.** If no Makefile target exists:
        * *Python:* You **MUST** use `poetry run [cmd]` (or `pipenv run`).
        * *Node/TS:* You **MUST** explicitly call the executable (e.g., `nvm use && npm run [script]`) or use `node_modules/.bin/[cmd]`.
    * **Priority 3: System Commands (Last Resort).** Only use raw system commands (git, docker, etc.) if no project-specific alternative exists.

# II. Core Execution Workflow

Follow these phases in strict sequential order.

### Phase 1: Setup

1.  **Persist the Plan:**
    * If the plan is not already saved, save it immediately to `./.cursor/plans/${PLAN_NAME}.md` or a relevant `./docs/` path. Do not reuse old plan files. if naming conflicts arise, clear the old file.
    * **Action:** Tell me the path where the file is saved.

2.  **Initialize Progress Tracking:**
    * Read the plan file. If a "Progress" or "Checklist" section does not exist, **add one** at the top of the file.
    * Convert every main step and sub-step into a Markdown checkbox (e.g., `- [ ] Step 1: ...`).

### Phase 2: Execution Loop

3.  **Assess and Resume:**
    * Read the plan and analyze the current project state.
    * Mark off any steps that are *already completed* in the plan file.
    * Identify the **first uncompleted step** and begin there.

4.  **Strict Sequential Execution:**
    * Execute steps exactly in the order written.
    * Do not skip steps or jump ahead unless explicitly instructed.

5.  **Validate Before Completing (The "Definition of Done"):**
    * You are NOT allowed to check off a step until you run a **Comprehensive Validation**:
    * **Code Changes:** Run relevant tests (pytest/vitest), type checks, and linters.
    * **Documentation:** Verify internal links, heading hierarchy, and rendering.
    * **Correction:** If validation fails, you must fix the issue immediately. Do not proceed to the next step until validation passes.

### Phase 3: Reporting & State Management

6.  **Update Progress File (CRITICAL):**
    * *Immediately* after a step passes validation (Rule 5), update the plan file on disk.
    * Mark the specific step as checked `[x]`.

7.  **Milestone Reporting:**
    * Only *after* updating the file, provide a status report to the user.
    * **Report Format:**
        * ✅ **Completed:** [List step(s) finished]
        * ⏭️ **Next:** [The exact next step you will start]
    * *Constraint:* Do not provide a narrative summary of the whole project. Keep it atomic.

### Phase 4: Maintenance

8.  **Dynamic Amendments:**
    * If user feedback requires changing the plan, you must update the plan file text and the checkboxes **before** writing any code for the new requirements.