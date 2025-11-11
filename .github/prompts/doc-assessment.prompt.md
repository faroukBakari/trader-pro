---
agent: "Plan"
name: "doc-assessment"
description: "Conduct a comprehensive assessment of project documentation for accuracy and update it to reflect the current codebase."
---
# 📊 Documentation Assessment & Update Request

You are a technical documentation specialist. I need you to conduct a comprehensive accuracy assessment of all project documentation and update it to reflect the current codebase.

## 🎯 Objectives

1.  **Assess** all git-tracked documentation files for accuracy against actual code
2.  **Identify** inconsistencies, outdated information, and missing updates
3.  **Create** a detailed assessment plan with progress tracking
4.  **Update** all inaccurate documentation following the Specific-to-Global strategy
5.  **Generate** a final assessment report with quality metrics

## 📋 Scope

-   **Include**: All git-tracked `.md` files (root, `docs/`, `backend/`, `frontend/`, etc.)
-   **Exclude**:
    -   Files in `**/tmp/` directories (temporary/scratch files)
    -   Auto-generated docs in `frontend/src/clients_generated/` (verified by generation process only)
    -   Third-party documentation (verify references only, don't assess content)

## 🚨 Critical Rules

All updates must follow these principles:

-   **Accuracy First**: Documentation must precisely match actual code implementation
-   **No Speculation**: Do not document future plans or assumptions
-   **Cross-Reference**: Update all related docs when making changes
-   **Relative Links**: All internal documentation references use relative links
-   **Simple, Specific, Short**: Content must be easy to understand, unambiguous, and concise
-   **Code Snippets**: Use illustrative snippets with source references, not raw code dumps
-   **Exclude tmp/ Files**: Files in `**/tmp/` directories are out of scope

## ⚙️ Workflow

### Phase 1: Create Assessment Plan

1.  **Read `docs/DOCUMENTATION-GUIDE.md`** to understand:
    -   Documentation hierarchy and organization rules
    -   All documentation files that need assessment
    -   Update strategy (Specific-to-Global approach)

2.  **Create Assessment Plan** at `docs/tmp/documentation-assessment-plan.md` (remove/overwrite if exists):
    -   List ALL git-tracked documentation files organized by wave
    -   Include progress tracking with checkboxes for each file
    -   Define verification sources (code files to cross-reference)
    -   Document known inconsistencies to verify
    -   Follow wave structure:
        -   **Wave 1**: Leaf Documentation (implementation details in module READMEs)
        -   **Wave 2**: Intermediate Docs (module & feature guides)
        -   **Wave 3**: Integration Docs (workflows & cross-cutting)
        -   **Wave 4**: Summary Docs (high-level overviews)
        -   **Wave 5**: Supporting Docs (setup & configuration)
        -   **Wave 6**: Specialized Docs (domain-specific)
        -   **Wave 7**: Final Report Generation
        -   **Wave 8**: Documentation Index Verification
        -   **Wave 9**: Structure Compliance Check

3.  **Present the plan** to me for review before proceeding

### Phase 2: Execute Assessment Plan

Once I approve the plan, use the **follow-plan** workflow:

1.  Save the plan to `docs/tmp/documentation-assessment-plan.md`
2.  Ensure progress tracking checkboxes exist for every step
3.  For each document in order:
    -   **Understand**: Read document and cross-reference with actual code
    -   **Verify**: Identify gaps, outdated info, inconsistencies
    -   **Propose**: Document specific changes needed (inline in plan)
    -   **Apply**: Update documentation with verified information
    -   **Validate**: Ensure links, cross-references, formatting are correct
4.  **Update progress** in the plan file after completing each document
5.  **Summarize** progress after each wave completion

### Phase 3: Generate Final Report

After all waves complete:

1.  **Compile findings** from all assessment waves
2.  **Create final report** at `docs/tmp/documentation-assessment-report.md`:
    -   Executive summary with statistics
    -   Overall quality grade and accuracy rate
    -   Detailed findings by category
    -   Prioritized recommendations
    -   Documents requiring future rewrite/removal
3.  **Update DOCUMENTATION-GUIDE.md** with assessment results

## 🎯 Expected Deliverables

1.  ✅ **Assessment Plan** (`docs/tmp/documentation-assessment-plan.md`)
2.  ✅ **All Updated Documentation** (following Specific-to-Global strategy)
3.  ✅ **Final Report** (`docs/tmp/documentation-assessment-report.md`)
4.  ✅ **Updated Documentation Guide** with quality metrics

## 🔍 Assessment Categorization

For each document, categorize as:

-   **UP-TO-DATE** ✅: All references verified, no issues
-   **INCONSISTENT** ⚠️: Contains deprecated refs, terminology conflicts, broken links
-   **NEEDS-VERIFICATION** 🔍: Missing dates, complex cross-refs needing validation
-   **EXTERNAL** 📦: Third-party docs (verify references only)

## 💡 Specific-to-Global Update Strategy

When updating documentation, follow this order:

**Phase 1: Module & Implementation Docs (The "Specific")**
-   Document implementation details in module-level READMEs
-   Target: `backend/src/module/README.md`, `frontend/src/component/README.md`

**Phase 2: Sub-System & Architecture Docs (The "Summary")**
-   Summarize changes in area-specific documentation
-   Target: `backend/README.md`, `backend/docs/*.md`, `frontend/README.md`, `frontend/docs/*.md`

**Phase 3: Root & Project-Wide Docs (The "Global")**
-   Update cross-cutting documentation
-   Target: `README.md`, `docs/*.md`

## 🚀 Begin Assessment

**Your first task is to execute Phase 1 only:**
1.  Read the `docs/DOCUMENTATION-GUIDE.md` using `@workspace`.
2.  Generate the complete `docs/tmp/documentation-assessment-plan.md` file, listing all documentation files in their respective waves.

**Present this plan to me for approval.** Do not proceed to Phase 2 or make any documentation updates until I approve the plan. After approval, I will ask you to assess files one by one.