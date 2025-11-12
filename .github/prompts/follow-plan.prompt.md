---
agent: "agent"
name: "follow-plan"
description: "Follow a predefined plan step-by-step."
---
We have defined and validated this plan that I need you to follow.

**You must follow these instructions *exactly*:**

1.  **Persist the Plan:** Before starting and if the plan is not already saved to a file, save it to the most relevant temporary working location (e.g., `./tmp/${PLAN_NAME}.md`, `backend/tmp/${PLAN_NAME}.md`, or `frontend/tmp/${PLAN_NAME}.md`). Let me know the path to the file you create.

2.  **Ensure Progress Tracking:**
    * Check the plan content. If a "Progress" or "Checklist" section with checkboxes does *not* already exist at the top, you must **add one**.
    * This progress section must list every main step and sub-step from the plan as a markdown checkbox (e.g., `[ ] Step 1: ...`).

3.  **Assess and Resume:**
    * Before starting any work, carefully read through the entire plan.
    * Analyze the current state of the project files to determine if any steps are already completed.
    * Update the checkboxes in the plan file to reflect this initial assessment (checking off any completed steps).
    * Begin your work from the **first uncompleted step**.

4.  **Strict Sequential Execution:** You must follow the plan steps *in the precise order they are written*. Do not skip steps or perform them out of order unless I explicitly instruct you to.

5.  **Summarize at Milestones:** After completing any major phase, critical step, or logical group of tasks, provide me with a brief summary of the progress made and the changes implemented.

6.  **Plan Amendments:** If we decide to change the plan while working, you must **immediately** update the plan file *and* the progress tracking section to reflect those changes.

7.  **CRITICAL: Always Update Progress Before Responding:** This is the most important rule. Before you finish your response and return control to me, you **must** update the progress tracking section in the plan file to accurately reflect the work you just completed.

8.  **CRITICAL: Context Window Guard:** If you determine the conversation context is nearing its limit, you must **immediately stop** your current work (even if you are in the middle of a step).
    * You must **avoid summarization** or any other conversational response.
    * Your **only** action before stopping must be to update the progress tracking file (as per Rule 8) to reflect all work completed up to this exact moment.
    * After updating the file, return control to me. Your *only* response should be to state: "Context window is nearly full. I have updated the progress file and am stopping to prevent context loss."
