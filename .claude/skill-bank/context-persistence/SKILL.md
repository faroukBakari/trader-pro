---
disable-model-invocation: true
name: context-persistence
description: Filesystem-based context sharing across subagent invocations. Load when coordinating multi-step subagent workflows
keywords: [persistence, context-sharing, subagent, filesystem, multi-invocation]
category: workflow
---

# Context Persistence — Filesystem-Based Agent/Subagent State Sharing

Provides a lightweight filesystem protocol for persisting and sharing context between agents and subagents across multiple `runSubagent` invocations. Eliminates the need to re-include full prior findings in every subagent prompt by storing intermediate state in structured files that subsequent invocations can read on demand.

---

## When to Use This Skill

- **Sequential subagent chains** — Subagent A produces findings that Subagent B needs as input
- **Iterative refinement** — Same subagent invoked multiple times, each building on previous results
- **Large context accumulation** — Prior findings exceed what fits efficiently in an inline prompt
- **Multi-perspective analysis** — Multiple subagents contribute independent findings to a shared workspace
- **Cross-turn continuity** — Parent agent needs to resume a multi-step workflow after user interaction

**Do NOT use when:**
- Single subagent invocation with self-contained scope (just use inline prompt)
- Context fits comfortably in 1–2 paragraphs (inline is simpler and cheaper)
- Subagent task is fully independent with no upstream/downstream dependencies

---

## Methodology

### Phase 1: Decide — Inline vs Persisted Context

Before invoking a subagent, evaluate whether to use inline prompting or filesystem persistence:

| Signal | Route |
|--------|-------|
| First subagent invocation, context < 500 tokens | **Inline** — pass context directly in prompt |
| Subagent output will be consumed by another subagent | **Persist** — write to workspace |
| Accumulating findings across 3+ invocations | **Persist** — prevents prompt bloat |
| Output is a one-shot answer consumed only by parent | **Inline** — no persistence needed |
| Parent will re-invoke same subagent to deepen analysis | **Persist** — enables incremental work |

**Rule of thumb**: If you're about to copy-paste a previous subagent's full output into the next subagent's prompt, use persistence instead.

### Phase 2: Initialize Workspace

Create a session workspace directory when persistence is needed. Use a task-descriptive name, not timestamps (agents reason about names better than IDs).

**Directory convention:**
```
.context/
  {task-slug}/
    README.md            # Session manifest: objective, participants, status
    findings/            # Subagent outputs (one file per invocation)
      {agent}-{step}.md  # e.g., research-codebase-scan.md
    state.md             # Running state: decisions, open questions, next steps
```

**Session manifest** (`README.md`):
```markdown
# Context: {Task Description}

**Objective**: {What the parent agent is trying to accomplish}
**Status**: in-progress | completed | abandoned
**Parent agent**: {agent name}
**Participants**: {list of subagents that will read/write}

## Scope
{Brief scope description — what's in, what's out}

## File Index
- `findings/research-codebase-scan.md` — Initial codebase analysis
- `state.md` — Running decisions and next steps
```

**Running state** (`state.md`):
```markdown
# State

## Decisions Made
- {Decision 1}: {choice} — {rationale}

## Open Questions
- {Question that needs resolution}

## Next Steps
- [ ] {Next action}

## Key References
- {file path or code location relevant to the task}
```

### Phase 3: Write — Subagent Output Persistence

After a subagent returns, the **parent agent** writes the relevant output to the session workspace.

**Writing rules:**
1. **Parent writes, not subagent** — Subagents return via `runSubagent` output; the parent decides what to persist
2. **One file per invocation** — Name descriptively: `{agent}-{action}.md`
3. **Structured content** — Use headers and sections, not raw dumps
4. **Include metadata header** — Agent name, timestamp, and task focus

**Finding file template:**
```markdown
# {Agent}: {Task Summary}

**Agent**: {subagent name}
**Focus**: {what was asked}
**Status**: complete | partial | failed

## Findings
{Extracted, relevant findings — not raw output}

## Key Insights
- {Insight 1}
- {Insight 2}

## Open Items
- {Anything unresolved or needing follow-up}
```

### Phase 4: Read — Context Loading for Subsequent Invocations

When invoking a subsequent subagent that needs prior context, use **file references** instead of inline content.

**Invocation pattern with file references:**
```
{Task description}
- {Specific action items}

Context files (read these for prior findings):
- `.context/{task}/state.md` — Current decisions and open questions
- `.context/{task}/findings/{agent}-{step}.md` — Prior findings from {agent}

Return: {What the caller needs back}
```

**Progressive loading** — Point subagents to only the files they need:
- If subagent needs overall state → reference `state.md`
- If subagent needs specific prior work → reference the specific finding file
- If subagent needs everything → reference the `README.md` file index

### Phase 5: Update State

After each significant subagent return, update `state.md`:
1. **Add decisions** — Any choices made based on findings
2. **Resolve questions** — Mark answered questions
3. **Update next steps** — Reflect what remains
4. **Cross-reference** — Link new finding file in `README.md` file index

### Phase 6: Cleanup

When the parent agent's task completes:
- **Completed sessions** — Keep if findings have long-term value; otherwise delete the `.context/{task}/` directory
- **Abandoned sessions** — Delete immediately to avoid stale context confusion
- **General rule** — `.context/` is ephemeral scratch space, not permanent storage

---

## Patterns

### Pattern A: Sequential Chain (Research → Verification)

```
Parent agent: any orchestrating agent
Task: Evaluate WebSocket reconnection strategy

Step 1: Invoke research subagent
  → "Research WebSocket reconnection patterns in our codebase..."
  → Parent writes output to .context/ws-reconnect/findings/research-codebase.md
  → Parent updates .context/ws-reconnect/state.md with decisions

Step 2: Invoke verification subagent (needs research findings)
  → "Verify the reconnection implementation against the patterns found:
     Context files:
     - .context/ws-reconnect/state.md
     - .context/ws-reconnect/findings/research-codebase.md
     Return: Pass/fail verdict for each pattern"
  → Parent writes output to .context/ws-reconnect/findings/verify-patterns.md
```

### Pattern B: Multi-Perspective (Code Analysis + UI Inspection)

```
Parent agent: any orchestrating agent
Task: Evaluate frontend order flow

Step 1: Invoke research subagent
  → "Research order placement code flow in frontend..."
  → Parent writes to .context/order-flow/findings/research-code-analysis.md

Step 2: Invoke browser automation subagent (reads research findings for targeted inspection)
  → "Inspect the order placement UI:
     - URL: http://localhost:5173/orders
     - Action: navigate-flow
     - Details: Follow the order placement flow identified in prior analysis

     Context files:
     - .context/order-flow/findings/research-code-analysis.md

     Return: UI state matches, form validation behavior, error handling UX"
  → Parent writes to .context/order-flow/findings/browser-ui-inspection.md

Step 3: Parent synthesizes both finding files without re-reading raw outputs
```

### Pattern C: Iterative Deepening (Same Subagent, Multiple Passes)

```
Parent agent: any orchestrating agent
Task: Debug authentication failure

Step 1: Invoke research subagent (broad scan)
  → Write to .context/auth-debug/findings/research-broad-scan.md

Step 2: Invoke research subagent (targeted — reads own prior findings)
  → "Deepen investigation into the OAuth token refresh path:
     Context files:
     - .context/auth-debug/findings/research-broad-scan.md
     Focus: Token refresh implementation only"
  → Write to .context/auth-debug/findings/research-token-refresh.md
```

---

## Anti-Patterns

- ❌ **Subagent writes directly** — Subagents return output to the parent via `runSubagent`; they cannot write to the filesystem in our runtime. Parent must write.
- ❌ **Persisting everything** — Only persist what downstream invocations actually need. A subagent's full raw output rarely needs full persistence.
- ❌ **Skipping the state file** — The `state.md` file is the coordination point. Without it, each finding is isolated and the overall narrative is lost.
- ❌ **Huge finding files** — If a finding file exceeds ~200 lines, extract only the relevant sections. Subagents loading bloated files waste tokens.
- ❌ **Using persistence for single-shot tasks** — If there's only one subagent invocation with no follow-up, inline context is simpler and cheaper.
- ❌ **Stale context directories** — Forgetting to clean up `.context/` directories after task completion leads to confusion in future sessions.
- ✅ **Selective persistence** — Write curated summaries of subagent findings, not verbatim output
- ✅ **File references in prompts** — Point subagents to files rather than pasting content inline
- ✅ **State tracking** — Keep `state.md` updated as the single source of truth for the workflow

---

## Adoption Guide

This skill is designed for **progressive adoption** — agents can opt in one at a time.

### Level 0: No Change (Default)
Agents continue using inline context passing. No filesystem involvement.

### Level 1: Simple Persistence (Minimal Change)
Parent agent creates `.context/{task}/` directory and writes subagent findings to files. References files in subsequent subagent prompts. No changes to subagent definitions needed — subagents just read files they're pointed to.

**Agent changes required**: Add `context-persistence` to skill references in constraints. Add "consider persistence" checkpoint before multi-subagent workflows in methodology.

### Level 2: Full Protocol (Structured)
Parent agent maintains `README.md`, `state.md`, and structured findings. Uses the complete Phase 1–6 methodology.

**Agent changes required**: Same as Level 1, plus explicit Phase in methodology for workspace initialization and cleanup.

---

## Output Format

When this skill produces a workspace, the directory structure looks like:

```
.context/
  {task-slug}/
    README.md
    state.md
    findings/
      {agent}-{step}.md
      {agent}-{step}.md
```

All files are markdown. No JSON, no YAML — markdown is the most readable format for both agents and humans reviewing the context.
