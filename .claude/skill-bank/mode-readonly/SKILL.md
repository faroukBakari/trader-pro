---
name: mode-readonly
description: Non-destructive investigation constraints. Load when analyzing, debugging, reviewing, or performing RCA without edits
keywords: [readonly, investigation, diagnostics, non-destructive]
category: workflow
disable-model-invocation: true
---

# Read-Only Investigation Mode

Enforces non-destructive constraints for analysis tasks. Protects against state modification while permitting diagnostic command execution.

**Core invariant**: You may observe and diagnose — you may NOT alter.

---

## State Protection (Immutable Rules)

CRITICAL — Violations break trust and session integrity:

- DO NOT create, edit, delete, move, or rename any file
- DO NOT run git state-changing commands: `checkout`, `stash`, `clean`, `restore`, `add`, `commit`, `reset`, `rebase`, `merge`, `push`, `pull`
- DO NOT run destructive system commands: `rm`, `mv`, `cp` on project files, `docker rm/prune`
- DO NOT install or uninstall packages (`npm install`, `pip install`, `poetry add`)

---

## Command Classification

Before running ANY terminal command, classify it:

| Class | Definition | Policy | Examples |
|-------|-----------|--------|----------|
| **Inspection** | Read-only observation, zero side effects | ✅ ALWAYS ALLOWED | `cat`, `ls`, `grep`, `find`, `git log`, `git diff`, `git blame`, `head`, `tail`, `wc` |
| **Diagnostic** | Runs code but produces only stdout/stderr output | ✅ ALLOWED | `make test`, `make lint`, `pytest`, `vitest run`, `vue-tsc`, `mypy`, `curl`, `docker ps`, `docker logs` |
| **Generative** | Creates ephemeral artifacts as side effect of diagnostics | ⚠️ TOLERATED | `make test` (writes coverage/), `make generate` (writes specs) — tolerate build artifacts only |
| **Mutating** | Changes project files, git state, or system packages | ❌ FORBIDDEN | `git commit`, `rm`, file edits, `npm install`, `docker rm`, `eslint --fix`, `ruff --fix` |

### Pre-Command Decision Tree

```
Is this command MUTATING? (changes files, git state, packages, infra)
  → YES → DO NOT RUN
  → NO  ↓

Is this command INSPECTION or DIAGNOSTIC?
  → YES → RUN (apply terminal-usage: timeout guard, output limiting)
  → UNCERTAIN ↓

Could this command produce side effects beyond stdout/stderr?
  → YES, permanent files → DO NOT RUN
  → YES, ephemeral artifacts (coverage/, .cache/, __pycache__/) → TOLERATE
  → NO → RUN
```

---

## Allowed vs Forbidden Operations

| Category | Allowed | Forbidden |
|----------|---------|-----------|
| **File ops** | `read_file`, `grep_search`, `file_search`, `semantic_search` | Any write/create/edit/delete |
| **Git** | `status`, `log`, `diff`, `show`, `blame`, `branch -l`, `rev-parse` | `checkout`, `stash`, `add`, `commit`, `push`, `pull`, `reset`, `rebase` |
| **Testing** | `make test`, `pytest`, `vitest run` | Tests that modify fixtures or seed data |
| **Linting** | `make lint`, `eslint` (no --fix), `mypy`, `pyright`, `ruff check` | `eslint --fix`, `ruff --fix`, auto-formatters |
| **Type checking** | `vue-tsc --build`, `mypy`, `pyright` | — |
| **Network** | `curl`, `wget -O -`, health checks | `wget -O file` (writes to disk) |
| **Docker** | `docker ps`, `docker logs`, `docker inspect` | `docker rm`, `docker prune`, `docker build` |
| **Process** | `ps`, `top`, `lsof`, `netstat`, `ss` | `kill`, `pkill`, service restart |
| **Browser/MCP** | Screenshots, DOM snapshots, console capture, navigate | — |

---

## Efficiency Guidelines

IMPORTANT — Maintain investigation quality:

- Prefer Makefile targets over raw commands (e.g., `make test` over `pytest`)
- Use environment-aware runners: `poetry run`, `npm run`, `node_modules/.bin/`
- Apply `terminal-usage` patterns for timeout guards and output management
- Filter large outputs to relevant portions — don't dump entire logs
- Avoid re-running expensive commands — cache mental model of results

---

## Investigation Aids

GUIDELINES — Best practices:

- Use `git blame` to understand change history around suspect code
- Check recent commits touching affected files
- Run targeted test subsets rather than full suites when possible
- Summarize intermediate findings to maintain investigation momentum
