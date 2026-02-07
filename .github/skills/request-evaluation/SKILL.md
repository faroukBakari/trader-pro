---
name: request-evaluation
description: User request gap analysis and completeness evaluation. Use when analyzing a request for ambiguity, missing context, implicit assumptions, or deliverable vagueness before execution begins.
---

# Request Evaluation

Systematic methodology for detecting gaps in user requests that could lead to hallucination, scope slippage, or misaligned deliverables. Produces a structured gap report that enables informed bridging or targeted clarification.

---

## When to Use This Skill

- Before executing complex, multi-step tasks where requirements could be interpreted multiple ways
- When a request references external context (files, systems, prior conversations) without providing it
- When the deliverable format, scope, or acceptance criteria are unspecified
- When ambiguity could cause substantial rework if the wrong interpretation is chosen
- As a pre-flight check before planning or implementation phases

---

## Methodology

### Phase 1: Context Decomposition

Break the user request into its constituent elements:

**Steps:**
1. **Extract the action** — What is being asked? (create, fix, refactor, analyze, explain…)
2. **Extract the subject** — What artifact or system does it target? (file, module, feature, architecture…)
3. **Extract the scope** — Is there an explicit boundary? (one file, whole module, full stack…)
4. **Extract the constraints** — Are there stated constraints? (technology, patterns, conventions, time…)
5. **Extract the deliverable** — What is the expected output? (code, document, analysis, plan…)

**Output template:**
```
| Element      | Extracted Value               | Confidence   |
|--------------|-------------------------------|--------------|
| Action       | {verb}                        | High/Med/Low |
| Subject      | {target}                      | High/Med/Low |
| Scope        | {boundary or "unspecified"}    | High/Med/Low |
| Constraints  | {list or "none stated"}       | High/Med/Low |
| Deliverable  | {output or "unspecified"}     | High/Med/Low |
```

### Phase 2: Deliverable Analysis

Examine the expected deliverable for completeness:

**Steps:**
1. **Format clarity** — Is the output format specified? (code file, markdown doc, terminal output, PR…)
2. **Quality criteria** — Are acceptance criteria stated or inferable?
3. **Integration point** — Where does the deliverable land? (which file, which system, which workflow…)
4. **Dependencies** — Does the deliverable require inputs not yet available?

**Decision table:**

| Deliverable Aspect | Specified? | Risk if Unresolved |
|--------------------|------------|-------------------|
| Output format      | Yes/No     | Low — can infer from context / High — multiple valid formats |
| Acceptance criteria | Yes/No    | Low — standard applies / High — subjective quality |
| Integration point  | Yes/No     | Low — obvious target / High — multiple candidates |
| Dependencies       | Yes/No     | Low — self-contained / High — blocks execution |

### Phase 3: Gap Detection

Systematically scan for gaps across these categories:

**Gap Categories:**

| Category | What to Look For | Example Gap |
|----------|------------------|-------------|
| **Ambiguous terms** | Words with multiple valid interpretations in context | "Improve performance" — speed? memory? UX responsiveness? |
| **Missing scope** | No boundary on what's included/excluded | "Refactor the module" — which files? public API changes allowed? |
| **Implicit assumptions** | Things the requester assumes you know | "Use the standard pattern" — which pattern? |
| **Unstated preferences** | Choices where the requester has a preference but didn't state it | Error handling strategy, naming conventions, test coverage level |
| **Missing context** | References to things not provided | "Like we did last time" — no prior context available |
| **Conflicting signals** | Request elements that contradict each other | "Quick fix" + "comprehensive solution" |
| **Deliverable vagueness** | Unclear what "done" looks like | "Set up the integration" — config file? working e2e? docs? |

**Steps:**
1. Walk through each gap category against the decomposed request
2. For each detected gap, note:
   - **What** is missing or ambiguous
   - **Why** it matters (what goes wrong if guessed incorrectly)
   - **Impact** severity: `critical` (substantial deviation) / `moderate` (suboptimal result) / `low` (cosmetic)

### Phase 4: Gap Classification & Report

Classify each gap and produce a structured output:

**Classification criteria:**

| Classification | Definition | Action |
|----------------|------------|--------|
| **Bridgeable (auto)** | Only 1-2 reasonable interpretations; one is clearly superior | Bridge with best alternative, document assumption |
| **Bridgeable (limited)** | 2-3 options, all reasonable, difference is minor | Pick best default, document the choice and alternatives |
| **Critical** | Multiple valid interpretations with substantially different outcomes | Must be resolved before proceeding |

**Output template:**
```
### Bridged Assumptions
| Gap | Chosen Interpretation | Alternatives Considered | Rationale |
|-----|----------------------|------------------------|-----------|
| {gap description} | {chosen} | {alternatives} | {why this is best} |

### Critical Gaps (Require Clarification)
| # | Gap | Why It Matters | Impact | Suggested Question |
|---|-----|----------------|--------|--------------------|
| 1 | {gap} | {consequence of wrong guess} | Critical | {question to ask} |
| 2 | {gap} | {consequence of wrong guess} | Critical | {question to ask} |
```

---

## Anti-Patterns

- ❌ **Over-flagging** — Marking every tiny ambiguity as critical; this creates question fatigue and slows execution. Only flag gaps where the wrong guess leads to substantial rework.
- ❌ **Under-bridging** — Refusing to make any assumptions and asking the user about everything. Most gaps have a clearly best interpretation — use it.
- ❌ **Context blindness** — Evaluating the request in isolation without considering the workspace, open files, conversation history, or project conventions.
- ❌ **False precision** — Asking for details that don't affect the outcome (e.g., variable naming when the project has clear conventions).
- ✅ **Calibrated judgment** — Bridge confidently when the right answer is clear; flag only when the wrong guess would cause meaningful deviation.

---

## Output Format

The skill produces a **Gap Analysis Report**:

```markdown
## Request Evaluation Report

### Request Summary
{One-sentence restatement of the request}

### Context Decomposition
| Element | Value | Confidence |
|---------|-------|------------|
| Action | ... | ... |
| Subject | ... | ... |
| Scope | ... | ... |
| Constraints | ... | ... |
| Deliverable | ... | ... |

### Bridged Assumptions
| Gap | Chosen Interpretation | Alternatives | Rationale |
|-----|----------------------|--------------|-----------|
| ... | ... | ... | ... |

### Critical Gaps
| # | Gap | Why It Matters | Impact | Suggested Question |
|---|-----|----------------|--------|--------------------|
| ... | ... | ... | ... | ... |

### Verdict
- **Ready to proceed**: Yes / No (pending N critical gaps)
- **Assumptions made**: N bridged
- **Clarifications needed**: N critical
```
