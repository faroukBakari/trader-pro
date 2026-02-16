---
name: claude-history-traces
description: Session history search, file recovery, and trace analytics. Load when recovering files or searching past conversations
user-invocable: false
---

# Claude History & Traces

Unified access to three complementary history capabilities: **file-history snapshots**, **cross-session search** (claude-code-history MCP), and **session analytics** (/insights).

## Routing Table

| "I need to..." | Tool | Section |
|-----------------|------|---------|
| Recover a previous version of a file | File-History Snapshots | Phase 2A |
| Find what I said or decided in a past session | History MCP (`search_conversations`) | Phase 2B |
| List all sessions for a project | History MCP (`list_sessions`) | Phase 2B |
| See what projects have history | History MCP (`list_projects`) | Phase 2B |
| Get full conversation transcript | History MCP (`get_conversation_history`) | Phase 2B |
| Understand session patterns and productivity | `/insights` | Phase 2C |
| Trace when a bug was introduced | Cross-reference (Phase 3) | Phase 3 |
| Audit what changes were made in a session | Cross-reference (Phase 3) | Phase 3 |

## Methodology

### Phase 1: Classify the Question

Before using any tool, classify the question into one or more categories:

| Category | Signal Words | Primary Tool |
|----------|-------------|--------------|
| **File Recovery** | "restore", "previous version", "undo", "what did X look like before" | File-History Snapshots |
| **Session Search** | "when did I", "find the conversation where", "what did we decide" | History MCP |
| **Analytics** | "how productive", "session summary", "patterns", "insights" | `/insights` |
| **Compound** | "when was the bug introduced", "trace the change history" | Multiple tools |

### Phase 2A: File-History Recovery

Claude Code maintains **content-addressed snapshots** of files modified via `Edit` or `Write` tools. Snapshots are stored at `~/.claude/filehistory/`.

**Workflow:**

```
1. Identify the target file's absolute path
2. Compute the storage path:
   ~/.claude/filehistory/<path-segments>/<filename>/
   (forward slashes in the path become directory separators)
3. List available snapshots:
   Glob: ~/.claude/filehistory/**/<filename>/*.snapshot
4. Read snapshot metadata (timestamps in filenames)
5. Read the desired snapshot content
6. Compare with current file content if needed (diff)
7. Restore by writing snapshot content back to the original path
```

**Key constraints:**
- Only files modified via `Edit`/`Write` tools have snapshots (not manual edits)
- ~30-day retention (content-addressed, deduplicated)
- Snapshot filenames encode timestamps for chronological ordering

### Phase 2B: History MCP Search

The `claude-code-history` MCP server provides four tools for cross-session search:

| Tool | Purpose | Key Params |
|------|---------|------------|
| `list_projects` | Discover all projects with history | none |
| `list_sessions` | List sessions, optionally filtered | `projectPath?`, `startDate?`, `endDate?`, `timezone?` |
| `get_conversation_history` | Paginated transcript retrieval | `sessionId?`, `messageTypes?`, `limit?`, `offset?` |
| `search_conversations` | Full-text keyword search | `query`, `projectPath?`, `startDate?`, `endDate?`, `limit?` |

**Workflow:**

```
1. Start broad: list_projects → identify relevant project
   ⚠ projectPath format is NOT the filesystem path — it uses its own encoding
     (no leading /, hyphens may become /). Copy the exact string from list_projects output.
2. Narrow scope: list_sessions(projectPath=<exact string from step 1>, startDate=...) → find candidate sessions
3. Search or browse:
   - Keyword known → search_conversations(query="...", projectPath=<exact string>)
   - Session known → get_conversation_history(sessionId=..., messageTypes=["user","assistant"])
4. Paginate if needed: use offset/limit for large result sets
```

**Scoping strategy** (most to least efficient):
1. `search_conversations` with `projectPath` + date range — fastest
2. `list_sessions` then `get_conversation_history` per session — moderate
3. `search_conversations` without filters — broadest, slowest

**Message type filtering:**
- `["user"]` — just user prompts (default, lowest volume)
- `["user", "assistant"]` — full conversation (higher volume)
- `["user", "assistant", "result"]` — includes tool results (highest volume)

### Phase 2C: /insights Analytics

The built-in `/insights` command provides multi-stage session analytics (duration, tool usage, error rates, productivity). Invoke via `Skill` tool with `skill: "insights"` or inform the user to run `/insights` directly.

### Phase 3: Cross-Reference (Compound Questions)

For questions that span multiple tools, combine results:

**Pattern: "When was this bug introduced?"**
```
1. File-History: List snapshots of the affected file → identify change dates
2. History MCP: search_conversations(query="<function or feature name>") → find sessions
3. Correlate: Match snapshot timestamps with session dates
4. Deep-dive: get_conversation_history(sessionId=...) for the suspect session
```

**Pattern: "What changes were made in session X?"**
```
1. History MCP: get_conversation_history(sessionId=..., messageTypes=["user","assistant"])
2. Extract: Identify file paths mentioned in tool calls
3. File-History: Check snapshots for those files around the session date
4. Diff: Compare pre/post snapshots for each modified file
```

## Templates

### Template: Recover a File

```
1. Glob: ~/.claude/filehistory/**/<filename>/*.snapshot → list versions
2. Read: newest snapshot → inspect content
3. (Optional) Diff against current file
4. Write: restore snapshot content to original path
```

### Template: Find a Past Decision

```
1. search_conversations(query="<decision keyword>", projectPath="<project>")
2. Review matching snippets → identify the session
3. get_conversation_history(sessionId=..., messageTypes=["user","assistant"])
4. Locate the decision context in the full transcript
```

### Template: Audit a Session

```
1. list_sessions(projectPath="<project>", startDate="<date>")
2. get_conversation_history(sessionId=..., messageTypes=["user","assistant","result"])
3. Extract: files modified, commands run, decisions made
4. Cross-reference with file-history snapshots for changed files
```

### Template: Diagnose a Regression

```
1. Identify the affected file and function
2. Glob: ~/.claude/filehistory/**/<filename>/*.snapshot → list all versions
3. Binary search snapshots to find when the regression appeared
4. search_conversations(query="<function name>", startDate=..., endDate=...)
5. get_conversation_history for the suspect session → find the causal change
```

## Limitations & Gotchas

### File-History Snapshots

| Limitation | Impact |
|-----------|--------|
| Edit/Write only | Manual editor saves, git checkouts, and external tools are not tracked |
| ~30-day retention | Older snapshots are garbage-collected |
| Content-addressed | Identical content = single snapshot (no duplicate timestamps) |
| No directory snapshots | Only individual files; no tree-level recovery |

### History MCP

| Limitation | Impact |
|-----------|--------|
| **projectPath format** | Paths use `/`-separated segments with NO leading slash, and hyphens in directory names become `/` separators. E.g., filesystem path `/home/farouk/trader-pro` → `home/farouk/trader/pro`. **Always call `list_projects` first** to discover the exact `projectPath` string, then pass it verbatim to other tools. |
| Text search only | No regex, no semantic search — use specific keywords |
| Session-level granularity | Cannot search within a specific turn; must paginate full sessions |
| Date filtering is inclusive | Boundary dates are included in results |
| Large transcripts | Use `limit`/`offset` pagination; avoid unbounded `get_conversation_history` |

### /insights

| Limitation | Impact |
|-----------|--------|
| Current session focus | Analyzes the active session; cross-session comparison is limited |
| Invocation only | Must be invoked via Skill tool or `/insights` command; not an MCP tool |

## Anti-Patterns

- **Guessing projectPath** — NEVER construct `projectPath` from the filesystem path; always call `list_projects` first and use the exact string returned (encoding differs: no leading `/`, hyphens may become `/`)
- **Searching without scoping** — Always provide `projectPath` and/or date range to History MCP searches; unscoped searches are slow and noisy
- **Reading full transcripts first** — Use `search_conversations` to find relevant sessions before pulling full history with `get_conversation_history`
- **Expecting manual edits in file-history** — Only `Edit`/`Write` tool operations create snapshots; files changed outside Claude Code have no history
- **Unbounded pagination** — Always set `limit` on `get_conversation_history`; default is 20, which is usually sufficient
- **Conflating session ID with project** — Sessions are unique IDs, not project names; use `list_sessions` to discover valid session IDs
- **Using file-history for git history** — File-history snapshots are orthogonal to git; use `git log` for commit history
- **Skipping Phase 1 classification** — Jumping to a tool without classifying the question often leads to using the wrong capability
