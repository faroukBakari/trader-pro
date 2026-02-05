---
name: mode-readonly
description: Read-only investigation constraints. Apply when analyzing, studying, planning, debugging, reviewing code, or performing RCA without modifications.
---

# Read-Only Investigation Mode

Enforces non-destructive constraints for analysis tasks.

## Critical Constraints

CRITICAL — Violations break trust and session integrity:

- DO NOT create, edit, delete, move, or rename any file
- DO NOT run git state-changing commands: `checkout`, `stash`, `clean`, `restore`, `add`, `commit`, `reset`, `rebase`, `merge`, `push`, `pull`
- DO NOT run destructive commands: `rm`, `mv`, `cp` on project files, `docker rm/prune`
- ALWAYS verify before any terminal command: "Does this alter files, git state, or system state?" — if yes, DO NOT RUN

## Allowed vs Forbidden Operations

| Category | Allowed | Forbidden |
|----------|---------|-----------|
| **File ops** | `read_file`, `grep_search`, `file_search` | Any write/create/edit |
| **Git inspection** | `status`, `log`, `diff`, `branch -l`, `show`, `blame` | `checkout`, `stash`, `add`, `commit`, `push`, `pull`, `reset` |
| **Tool inspection** | `make --dry-run`, `npm run --dry-run` | Actual execution that modifies state |

## Pre-Command Check

Before ANY terminal command, verify:

1. Does this alter files? → DO NOT RUN
2. Does this change git state? → DO NOT RUN  
3. Does this modify system state? → DO NOT RUN

## Efficiency Guidelines

IMPORTANT — Maintain investigation quality:

- Prefer Makefile targets over raw commands (e.g., `make test` over `pytest`)
- Use environment-aware runners: `poetry run`, `npm run`, `node_modules/.bin/`
- Avoid re-running expensive commands — cache mental model of results
- Filter large outputs (logs, test results) to relevant portions

## Investigation Aids

GUIDELINES — Best practices:

- Consider using `git blame` to understand change history around suspect code
- When practical, check recent commits touching affected files
- Summarize intermediate findings to maintain investigation momentum
