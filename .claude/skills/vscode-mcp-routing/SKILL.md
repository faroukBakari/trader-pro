---
name: vscode-mcp-routing
description: VS Code MCP tool routing and diagnostics-driven edit loops. Load when choosing between native and MCP workspace tools
user-invocable: false
---

# VS Code MCP Tool Routing

Routes editing, refactoring, and verification operations between Claude Code native tools and VS Code MCP server tools. Prevents common pitfalls (Write-guard failures, Edit uniqueness issues) by selecting the correct tool for each operation type.

---

## <when_to_use>

Apply when:
- Moving or renaming source files (need import tracking)
- Fixing errors at known line numbers (from diagnostics or LSP)
- Verifying edits before declaring a task complete
- Scaffolding new files idempotently
- Choosing between `Edit` vs `replace_lines_code`, or `Bash mv` vs `move_file_code`

Do NOT use (native tools suffice):
- Reading files (`Read`), searching files (`Glob`, `Grep`), simple unique-string edits (`Edit`)

</when_to_use>

---

## <tool_tiers>

### Tier 1 — HIGH value (always prefer over alternatives)

| Tool | Use For | Why |
|------|---------|-----|
| `get_diagnostics_code` | Verify edits, find errors | One call = all linter + type-checker errors. **Use after every edit batch** |
| `move_file_code` | Move files/directories | Auto-updates imports + avoids Write tool guard failure |
| `rename_file_code` | Rename files/directories | Auto-updates imports + avoids Write tool guard failure |

### Tier 2 — MEDIUM value (use when advantageous)

| Tool | Use For | Why |
|------|---------|-----|
| `replace_lines_code` | Fix at known line numbers | Bypasses Edit's uniqueness constraint; line numbers from diagnostics |
| `create_file_code` | Scaffold new files | `ignoreIfExists: true` for idempotent creation without clobbering |

### Tier 3 — LOW value (native tools preferred)

| MCP Tool | Native Alternative | Why Native Wins |
|----------|-------------------|-----------------|
| `list_files_code` | `Glob` | Pattern matching, sorted output |
| `search_symbols_code` | `LSP workspaceSymbol` | Same data, native integration |
| `get_document_symbols_code` | `LSP documentSymbol` | Same data, native integration |

### AVOID — native tool is strictly better

| MCP Tool | Use Instead | Why |
|----------|-------------|-----|
| `read_file_code` | `Read` | Handles PDFs, images, notebooks; no 100k char limit |
| `copy_file_code` | `Bash cp` | Handles directories, permissions, flags |
| `execute_shell_command_code` | `Bash` | 2min default timeout vs 10s; reliable output capture |
| `get_symbol_definition_code` | `LSP hover` | Identical capability, native integration |

</tool_tiers>

---

## <methodology>

### The Diagnostics-Driven Edit Loop

The optimal workflow when fixing errors at known line numbers:

```
1. get_diagnostics_code(path)    → error at line 52
2. Read file (lines 50-55)       → see context around error
3. replace_lines_code(50, 55)    → apply fix by line range
4. get_diagnostics_code(path)    → confirm clean
```

**Why this beats the Edit workflow:**
- No need to construct a unique `old_string` with surrounding context
- Line numbers come directly from diagnostics — no guessing
- `originalCode` validation prevents wrong-line edits

**When to use Edit instead:**
- Simple unique string replacements (old_string is naturally unique)
- Global rename across a file (`replace_all: true`)
- Line numbers are not available

### Mandatory Diagnostics Checkpoints

| Checkpoint | Scope | Severities |
|------------|-------|------------|
| After editing any source file | Single file (fast) | `[0, 1]` — errors + warnings |
| Before declaring task complete | Workspace-wide (comprehensive) | `[0, 1]` — errors + warnings |
| When debugging an issue | Target file first | `[0, 1, 2, 3]` — include info + hints |
| After code generation | Generated files | `[0, 1]` — verify clean compilation |

### Move & Rename: Reference-Aware Refactoring

**Always use `move_file_code` / `rename_file_code` instead of `Bash mv` for source files.** Two independent reasons:

1. **Import tracking** — VS Code's WorkspaceEdit API updates all import statements, re-exports, and path references across the workspace automatically.

2. **Write tool guard** — Claude Code's `Write` tool requires a prior `Read` at the exact path before allowing an overwrite. `Bash mv` moves the file on disk but does not register a `Read` at the new path — so a subsequent `Write` to the new path fails with "Error writing file". The MCP move/rename tools avoid this because the editor tracks the path change internally.

**Use `Bash mv` only for:** non-code assets you will not subsequently `Write` to (data files, binary assets, archives).

**Recovery if `Bash mv` was already used:** `Read` the file at its new path before `Write`-ing to it.

</methodology>

---

## <constraints>

### replace_lines_code

| Constraint | Detail |
|------------|--------|
| `originalCode` | Must match file content **exactly** — character-for-character |
| Pre-read required | Always `Read` the target lines first to get exact content |
| Line numbers | 1-based, inclusive on both ends |
| Drift on multi-edit | Line numbers shift after earlier edits in same file — re-read between successive edits |

**Best for:** Error fixes at specific lines, non-unique code patterns (`return None`, `pass`, duplicate signatures), blocks identified by symbol line ranges.

**Stick with Edit for:** Unique string replacements, global rename (`replace_all`), when line numbers are unknown.

### create_file_code

| Flag | Effect |
|------|--------|
| `ignoreIfExists: true` | Skip silently if file exists — safe for idempotent scaffolding |
| `overwrite: true` | Replace existing file — equivalent to `Write` but through MCP |

**Default to `ignoreIfExists: true`** when scaffolding directory structures to prevent accidental clobber.

</constraints>

---

## <decision_shortcuts>

Quick routing without the full methodology:

| Situation | Tool |
|-----------|------|
| "I just edited code — is it clean?" | `get_diagnostics_code` on the file |
| "Task is done — any regressions?" | `get_diagnostics_code` workspace-wide |
| "Diagnostic says error at line 42" | `Read` lines 40-45 → `replace_lines_code` → `get_diagnostics_code` |
| "Need to move/rename a source file" | `move_file_code` / `rename_file_code` |
| "Need to move a data/binary file" | `Bash mv` or `Bash cp` |
| "Edit fails — old_string not unique" | Switch to `replace_lines_code` with exact line range |
| "Creating file that might already exist" | `create_file_code` with `ignoreIfExists: true` |
| "Need to read a file" | `Read` (never `read_file_code`) |
| "Need to run a shell command" | `Bash` (never `execute_shell_command_code`) |

</decision_shortcuts>

---

## <anti_patterns>

| Anti-Pattern | Consequence | Fix |
|-------------|-------------|-----|
| `Bash mv` then `Write` | Write guard fails — "Error writing file" | Use `move_file_code` / `rename_file_code` |
| Skipping diagnostics after edits | Silent regressions discovered late | Run `get_diagnostics_code` after every edit batch |
| `replace_lines_code` without reading first | `originalCode` mismatch → tool failure | Always `Read` target lines before replacing |
| Multiple `replace_lines_code` without re-reading | Line numbers drift after each edit | Re-read file between successive line edits |
| `read_file_code` for reading files | 100k char limit, no PDF/image/notebook support | Use native `Read` tool |
| `execute_shell_command_code` for commands | 10s timeout, unreliable output | Use native `Bash` tool |
| `create_file_code` without `ignoreIfExists` for scaffolding | Clobbers existing files silently | Add `ignoreIfExists: true` |

</anti_patterns>
