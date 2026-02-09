---
name: fs-operations
description: Filesystem operation routing — decides between MCP filesystem tools, built-in editor tools, and terminal commands. Use when performing file/directory manipulation (move, copy, delete, create, find, bulk operations) to select the right tool layer for safety, atomicity, and efficiency.
---

# Filesystem Operation Routing

Routes filesystem operations to the correct tool layer based on operation type, safety requirements, and atomicity needs. Prevents misuse of heavy terminal commands for simple fs operations and ensures workspace-confined safety boundaries.

---

## When to Use This Skill

- Moving, copying, renaming, or deleting files or directories
- Creating directory structures or scaffolding
- Finding files by name, content, or metadata
- Performing bulk file operations (batch move/rename/delete)
- Deciding whether an fs operation needs terminal, MCP, or built-in editor tools
- Verifying file integrity (checksums)
- Analyzing disk usage or directory structures

---

## Methodology

### Phase 1: Classify the Operation

Identify the operation category:

| Category | Examples |
|----------|----------|
| **Content creation** | Write new file, write code, create config |
| **Content modification** | Edit file content, replace strings, patch code |
| **Structural mutation** | Move, copy, rename, delete files/dirs |
| **Bulk structural** | Batch move, pattern rename, multi-delete |
| **Search/discovery** | Find files by name/content/metadata |
| **Inspection** | Disk usage, directory listing, checksums |
| **Monitoring** | Watch for file changes, track modifications |

### Phase 2: Route to Tool Layer

Apply this decision table — first matching rule wins:

| Operation | Tool | Rationale |
|-----------|------|-----------|
| Create/write a new file | `create_file` (built-in) | Purpose-built, creates parent dirs automatically |
| Edit file content | `replace_string_in_file` / `multi_replace_string_in_file` (built-in) | Context-aware, supports batch editing |
| Read file content | `read_file` (built-in) | Line-range support, efficient |
| List directory | `list_dir` (built-in) | Simple, fast |
| Move single file/dir | `fs_batch_operations` (MCP) | Workspace-confined, atomic |
| Copy single file/dir | `fs_batch_operations` (MCP) | Workspace-confined, atomic |
| Delete single file/dir | `fs_batch_operations` (MCP) | Workspace-confined, prevents accidental system damage |
| Rename file/dir | `fs_batch_operations` (MCP) | Move with new name — atomic |
| Copy directory tree | `fs_copy_directory` (MCP) | Recursive with exclusions, preserves metadata |
| Sync directories | `fs_sync_directory` (MCP) | Copies only newer/missing files |
| Batch move/copy/delete | `fs_batch_operations` (MCP) | Atomic multi-op with rollback on failure |
| Find files by name | `file_search` (built-in) | Glob patterns, fast |
| Find files by content | `grep_search` (built-in) | Regex support, includes context |
| Find by metadata/size/date | `fs_search_files` (MCP) | Metadata filters, indexed search |
| Checksum / integrity | `fs_compute_checksum` / `fs_verify_checksum` (MCP) | md5/sha256 support |
| Disk usage analysis | `fs_analyze_disk_usage` (MCP) | Breakdown by path/type |
| Watch for changes | `fs_watch_directory` (MCP) | Real-time monitoring with filters |
| Create symlink | `fs_create_symlink` (MCP) | Workspace-confined link creation |
| Permissions / chmod | Terminal (`run_in_terminal`) | No MCP equivalent — use terminal |
| OS-specific operations | Terminal (`run_in_terminal`) | `ln -s` outside workspace, `chown`, etc. |

### Phase 3: Construct the Call

#### MCP `fs_batch_operations` (most common)

For move, copy, delete, rename — use a single batch call:

```
Operations array with entries:
  - type: "move" | "copy" | "delete"
  - source: relative or absolute path within workspace
  - destination: target path (for move/copy)
  - atomic: true (recommended — rolls back on failure)
```

**Rename pattern**: A rename is a `move` with the new name as destination.

**Multi-operation pattern**: Combine related operations into one batch call for atomicity. If any operation fails, all are rolled back.

#### MCP `fs_copy_directory`

For recursive directory copies:
- Set `exclusions` to skip `node_modules/`, `__pycache__/`, `.git/`, `*_generated/`
- Set `preserveMetadata: true` to keep timestamps

#### MCP `fs_search_files`

For advanced file discovery:
- Use `searchType: "name"` for filename patterns
- Use `searchType: "content"` for text search with metadata filters
- Use `fs_build_index` first for repeated searches on same directory

---

## Decision Shortcuts

Quick routing without the full decision table:

| If you're thinking... | Use |
|----------------------|-----|
| "I need to write/edit code" | Built-in editor tools (`replace_string_in_file`) |
| "I need to edit code across multiple files" | Built-in `multi_replace_string_in_file` (batch edits in one call) |
| "I need to move/copy/rename/delete" | MCP `fs_batch_operations` |
| "I need to copy a whole directory" | MCP `fs_copy_directory` |
| "I need to find files" | Built-in `file_search` (by name) or `grep_search` (by content) |
| "I need advanced search with filters" | MCP `fs_search_files` |
| "I need to do something OS-level" | Terminal |
| "I need atomicity across multiple ops" | MCP `fs_batch_operations` with `atomic: true` |

---

## Safety Guards

### Protected Paths (never mutate via any tool)

These paths should never be targets of move/delete/overwrite operations:

- `*_generated/` — generated client code (regenerate from source models instead)
- `.git/` — repository metadata
- `node_modules/` — dependency artifacts (use package manager instead)
- `__pycache__/` — Python bytecode cache (auto-regenerated)

### Pre-mutation Checklist

Before any destructive operation (delete, overwrite, move):

1. **Is the target generated?** → If path contains `_generated`, STOP — regenerate instead
2. **Is this reversible?** → Move/rename is; delete is not unless version-controlled
3. **Are there dependents?** → Check for imports/references to the file being moved/renamed
4. **Is atomicity needed?** → Multiple related ops → use single batch call

---

## Anti-Patterns

- ❌ Using `run_in_terminal` with `rm -rf` for simple file deletion — unsafe, no workspace boundary
- ❌ Using `command` subagent for a simple `mv` or `cp` — heavyweight overhead (background terminal, await, cleanup)
- ❌ Sequential terminal commands for multi-file operations — no atomicity, partial failure leaves inconsistent state
- ❌ Using MCP tools for file content editing — wrong tool; use `replace_string_in_file`
- ❌ Deleting `*_generated/` directories then recreating — regenerate from source models via `make generate`
- ✅ Using `fs_batch_operations` for structural mutations — workspace-confined, atomic, rollback on failure
- ✅ Using built-in editor tools for content operations — purpose-built with context awareness
- ✅ Combining related structural ops into single batch call — atomicity guarantee
