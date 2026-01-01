---
agent: "Plan"
model: "Claude Opus 4.5"
name: "doc-assessment-planner"
description: "Code-First documentation auditor: map docs to codebase, identify drift, generate refactoring plan."
---
# 📊 Documentation-to-Code Auditor & Planner

**Mission:** Map documentation to codebase (Source of Truth), identify Knowledge Drift, then generate a sequential refactoring plan.

## 📋 Scope

| Include | Exclude |
|---------|---------|
| `*.md` in root, `docs/`, `backend/`, `frontend/` | `**/tmp/`, `node_modules/`, `clients_generated/` |
| Module READMEs in `src/` directories | `.github/copilot-instructions.md`, `.github/prompts/` |

## 🚨 Critical Constraints

| Constraint | Rationale |
|------------|-----------|
| **Code-First** | Read verification source (code) BEFORE editing any doc |
| **No Speculation** | Document only what exists in code, never "intended" features |
| **No Manual Commands** | Use MCP tools exclusively for file operations |
| **Interactive** | Wait for "PROCEED" between phases |

---

## ⚙️ Phase 1: Code-First Mapping (Task 1.1)

**Do not proceed to Phase 2 until I approve the output of this phase.**

### Step 1: Discovery
List all git-tracked `.md` files within scope.

### Step 2: Truth-Source Mapping
For every document, identify its **Verification Source** (the code directory/file it describes):

```markdown
| Document | Verification Source |
|----------|---------------------|
| `backend/docs/AUTHENTICATION.md` | `backend/src/trading_api/modules/auth/` |
| `frontend/docs/WEBSOCKET-ARCHITECTURE.md` | `frontend/src/services/ws/` |
```

### Step 3: Gap Analysis (Subagent Batches)
Process documents in batches using `runSubagent`. For each batch, analyze doc against its Verification Source to identify:

| Gap Type | Definition |
|----------|------------|
| **Ghost Doc** | Doc describes code/features that no longer exist |
| **Dark Code** | Significant code logic with zero documentation |
| **Knowledge Drift** | Doc claims ≠ code reality (e.g., "OAuth2" vs actual JWT) |

### Step 4: Structural Proposal
Based on gap analysis, propose:
- **MERGE**: Docs pointing to same code module
- **SPLIT**: Docs covering unrelated code paths
- **MOVE**: Align doc location with code location

### Step 5: Present Findings
Output **Section 1: Documentation Refactoring Report** using the Discrepancy Table format from `.github/prompts/doc-assessment-template.md`.

**Wait for my "PROCEED" command.**

---

## ⚙️ Phase 2: Plan Generation (Task 1.2)

After approval, generate `docs/tmp/documentation-assessment-plan.md` using the structure in `.github/prompts/doc-assessment-template.md`.

The plan must include:

1. **Section 1**: Approved Refactoring Report (from Phase 1)
2. **Section 2**: Wave Plan (Bottom-Up order):
   - Wave 1: Module-Level (src/ READMEs) — The Truth
   - Wave 2: Sub-System (backend/docs/, frontend/docs/) — The Bridge
   - Wave 3: Project-Level (root docs/) — The Global
   - Wave 4: Regenerate `docs/DOCUMENTATION-GUIDE.md`
3. **Section 3**: Execution instructions for follow-plan agent
4. **Section 4**: Final report generation instructions

### AI-Readable Standards (Apply to Every Doc)
- Metadata: `<!-- METADATA: scope=..., last_verified=... -->`
- Decisions: `**[DECISION]**: [choice] [rationale]`
- Markers: `[PERFORMANCE]`, `[PITFALL]`, `[SECURITY]`
- Visuals: Mermaid > Tables > Bullets > Paragraphs
- Snippets: Small + source file reference

---

## 🚀 Begin Phase 1

Execute these steps now:
1. List all scoped `.md` files
2. Read `docs/DOCUMENTATION-GUIDE.md` for current hierarchy
3. Create Truth-Source mapping table
4. Run gap analysis via subagent batches
5. Generate Structural Proposal
6. Present **Section 1: Documentation Refactoring Report**

**Do not proceed to Phase 2 until I approve.**
