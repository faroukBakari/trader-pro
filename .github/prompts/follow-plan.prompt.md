---
agent: "agent"
name: "follow-plan-v2.1"
description: "Follow a predefined plan step-by-step with validation and a clear action hierarchy."
---
We have defined and validated this plan that I need you to follow.

### Core Execution Workflow (Rules 1-8)

If the OVERRIDE rule is not triggered, follow this workflow precisely.

#### Phase 1: Setup

1.  **Persist the Plan:** Before starting and if the plan is not already saved to a file, save it to the most relevant temporary working document location (e.g., `./docs/tmp/${PLAN_NAME}.md` or `path/to/dep/or/module/tmp/${PLAN_NAME}.md`). Let me know the path to the file you create.

2.  **Ensure Progress Tracker:**
    * Check the plan content. If a "Progress" or "Checklist" section with checkboxes does *not* already exist at the top, you must **add one**.
    * This progress section must list every main step and sub-step from the plan as a markdown checkbox (e.g., `[ ] Step 1: ...`).

#### Phase 2: Execution

3.  **Assess and Resume:**
    * Before starting any work, carefully read through the entire plan.
    * Analyze the current state of the project files to determine if any steps are already completed.
    * Update the checkboxes in the plan file to reflect this initial assessment (checking off any completed steps).
    * Begin your work from the **first uncompleted step**.

4.  **Strict Sequential Execution:** You must follow the plan steps *in the precise order they are written*. Do not skip steps or perform them out of order unless I explicitly instruct you to.

5.  **CRITICAL: Validate Before Completing:** After you believe you have completed the work for a step, you must run a **comprehensive validation** of the *entire* implementation so far.
    * This *must* include running any and all relevant tests if applicable (pytest / vitest) as well as types and format checks.
    * A step is **not complete** until this validation passes. If validation fails, you must debug and fix the issues *before* proceeding to Rule 6.

#### Phase 3: Reporting Cycle

6.  **CRITICAL: Update Progress File:** This is the most important standard rule.
    * *After* a step has been successfully **validated** (per Rule 5), you **must** update the progress tracking section in the plan file to accurately reflect the work you just completed.
    * This action **must** be completed *before* you report to me (Rule 7).

7.  **Report at Milestones:**
    * *After* completing, validating, and updating the progress file (per Rules 5 & 6), provide me with a status report.
    * This report must *only* contain:
        * A list of the main step(s) just completed.
        * The *next* step to be started.
    * (Do not provide a narrative summary of the *entire* project.)

#### Phase 4: Maintenance

8.  **Plan Amendments:** If we decide to change the plan while working, you must **immediately** update the plan file *and* the progress tracking section to reflect those changes.