---
name: context-budget
description: Large data volume handling — detection triggers, delegation protocols, and convergence gates for files, diffs, search results, and command output. Use when processing >200-line files, large git diffs, bulk search results, or extended investigations without convergence.
---

# Context Budget — Large Data Management

Runtime protocols for handling high-volume data in agent workflows. Covers detection, routing, delegation to subagents, and convergence enforcement.

**Scope boundary**: This skill covers *volume-aware runtime behavior* (what to do when data is large). For prompt *design* patterns (context structuring, token budgets), apply `prompt-context-efficiency`. For model *selection* cost tradeoffs, apply `model-selection`.

---

## When to Use This Skill

- Reading files exceeding 200 lines
- Processing git diffs spanning multiple files or >500 changed lines
- Search results returning >20 hits before deduplication
- Command output exceeding 50KB
- Investigation exceeding 8 tool calls without convergence toward a deliverable
- Delegating to research or command-execution subagents for large-data scenarios

---

## Phase 1: Volume Detection

Before processing data, classify its volume tier:

| Tier | Signal | Examples |
|------|--------|----------|
| **Normal** | File <200 lines, <20 search hits, <50KB output | Single module file, focused grep |
| **Large** | File 200–800 lines, 20–50 hits, 50–200KB output | Full service class, multi-file diff |
| **Bulk** | File >800 lines, >50 hits, >200KB output | Generated code, monolith file, full test suite output |

**Detection triggers** — apply volume protocol when ANY of these fire:

| Trigger | Threshold | Immediate Action |
|---------|-----------|------------------|
| File line count | >200 lines | Read structure/signatures first (Phase 2A) |
| Git diff scope | >3 files changed OR >500 lines total | Use `--stat` first (Phase 2B) |
| Search result count | >20 matches | Deduplicate and rank before deep-reading (Phase 2C) |
| Command output size | >50KB expected | Redirect to temp file (Phase 2D) |
| Tool call count | >8 calls without convergent progress | Convergence gate (Phase 3) |

---

## Phase 2: Volume Routing

### 2A: Large File Protocol

```
1. Read STRUCTURE first — function/class signatures, imports, section headers
   → Use grep for def/class/export patterns, or read first 30 + last 10 lines
2. IDENTIFY relevant sections from structure scan
3. Read TARGETED ranges only — the specific sections needed
4. Never read >150 lines in a single read_file call on a large file
   unless the entire range is confirmed relevant from step 2
```

**Delegation trigger**: If the file is part of a multi-file investigation involving 3+ large files → delegate to a research-role subagent with explicit file list and relevance anchor.

### 2B: Large Diff Protocol

```
1. Run `git diff --stat` (or `git diff --cached --stat`) FIRST
   → Gives file-level summary: which files changed, lines added/removed
2. TRIAGE files by relevance to the task — skip test fixtures, generated code, lockfiles
3. Read diffs for RELEVANT files only: `git diff -- path/to/relevant/file.py`
4. For files with >200 changed lines, use `git diff --no-context -- file` to minimize
```

**Delegation trigger**: If diff spans >10 files or >1000 total changed lines → delegate to a command-execution subagent:
```
Execute: `git diff --stat` [timeout: 10s]
Then for each relevant file: `git diff -- {file}` [timeout: 10s]
Extract: changed function signatures, new/removed exports, error pattern changes
Context: {why the diff matters to the current task}
```

### 2C: Bulk Search Results

```
1. SCAN result list — note file paths and match counts per file
2. DEDUPLICATE — group matches from the same file, skip generated code directories
3. RANK by relevance to task context — prioritize source over test, implementation over config
4. DEEP-READ top 5 matches only — remaining matches get one-line summary or omit
```

### 2D: Large Command Output

```
1. PRE-ESTIMATE output size before running:
   - Test suites → 50-200KB typical
   - Docker builds → 100KB-1MB
   - Git log/diff → proportional to history/changes
2. REDIRECT to temp file: `command > /tmp/cmd-{label}.log 2>&1`
3. READ selectively: `read_file` on relevant sections (errors, summary, final status)
4. CLEAN UP temp files after extraction
```

**Delegation trigger**: Any command expected to produce >50KB output → delegate to a command-execution subagent (captures full output without masking pipes).

---

## Phase 3: Convergence Gates

After every 8 tool calls, pause and assess:

| Check | Question | If NO |
|-------|----------|-------|
| **Progress** | Have findings moved closer to the deliverable? | Reassess approach — wrong search terms? wrong files? |
| **Relevance** | Are recent findings on the critical path? | Stop exploring tangents — return to stated goal |
| **Diminishing returns** | Is each new finding adding signal? | Summarize what you have and proceed to synthesis |
| **Delegation** | Would a subagent handle the remaining scope more efficiently? | Delegate with accumulated context |

**Hard gate at 12 tool calls**: If 12 tool calls have been made without producing a concrete deliverable artifact (code change, analysis section, decision), you MUST either:
1. Produce intermediate output with what you have, OR
2. Delegate remaining investigation to a subagent with clear extraction criteria

---

## Phase 4: Delegation Enrichment

When delegating large-data scenarios to subagents, always include volume context:

### Research-Role Subagent — Large File Delegation

```
Research [topic]:
- [Specific questions]

Context: {why this matters}
Volume: {N} files over 200 lines — use structure-first scanning.
Files: [list of specific files with line counts if known]
Priority: {which files are most likely relevant and why}
```

### Command-Execution Subagent — Large Output Delegation

```
Execute: {command} [timeout: {N}s]
Extract: {specific patterns to find — errors, summaries, metrics}
Context: {what the output will be used for}
Volume: Output expected >50KB — use file redirection.
```

---

## Anti-Patterns

- ❌ **Full-file reads on large files** — Reading 500+ lines when 30 lines of signatures would identify the relevant section. Use structure-first scanning.
- ❌ **Unfiltered diff dumps** — Piping entire multi-file diffs into context. Use `--stat` triage first.
- ❌ **Sequential search rabbit holes** — 15+ grep calls narrowing progressively. Batch with regex alternation, set a convergence gate.
- ❌ **Output masking during execution** — Using `head`/`tail`/`grep` on live command output. Capture full, extract post-hoc.
- ❌ **Delegation without volume context** — Spawning a research subagent for 5 large files without telling it which files or what to prioritize. Include explicit file list + relevance anchor.
- ❌ **Ignoring convergence gates** — Continuing past 12 tool calls without progress check. The gate exists to prevent unbounded exploration.
- ✅ **Structure → Target → Extract** — Scan structure, identify relevant sections, read only those sections. Every data access earns its token cost.
