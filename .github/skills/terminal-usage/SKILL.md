---
name: terminal-usage
description: Terminal command guidelines — pre-command safety checks for direct execution and delegation routing to command subagent for complex scenarios. Applies when running shell commands or deciding whether to delegate command execution.
---

# Terminal Usage

Lightweight guidance for all agents executing terminal commands. Covers the universal safety checks every agent must apply for direct execution, plus a routing heuristic for when to delegate to a dedicated command executor.

---

## <when_to_use>

Apply when:
- About to use the `execute` tool (run_in_terminal)
- Deciding whether to run a command directly or delegate
- Planning shell commands that involve pipes, output limiters, or long-running processes

</when_to_use>

---

## <pre_command_checks>

**Apply ALWAYS before ANY terminal command — direct or delegated.**

| Check | Think Through | If Yes |
|-------|---------------|--------|
| **1. Makefile First** | "Is there a `make` target that already does this?" | Use the make target instead |
| **2. Env-Aware** | "Am I using the project's environment wrappers?" | Must use `make`, `poetry run`, or `nvm use &&` — never bare `npm`, `pip`, `python` |
| **3. Timeout Guard** | "If I'm using output limiters (`head`/`tail`/`more`), could the source hang?" | Add `timeout N` before the command — pipes don't kill the source process |

**Why timeout with output limiters?**
```bash
# ❌ WRONG: Pipe doesn't kill source — if build hangs, waits forever
docker build . 2>&1 | tail -50

# ✅ CORRECT: Timeout terminates hung process
timeout 120 docker build . 2>&1 | tail -50
```

### Quick Timeout Reference

| Command Type | Timeout |
|---|---|
| File reads, simple git ops | 5–30s |
| Tests, incremental builds | 120s |
| Clean builds, installs | 300s |
| Docker builds | 600s |

**Rule**: Allow 2-3x estimated duration. Always use `2>&1` to capture stderr.

</pre_command_checks>

---

## <delegation_routing>

### When to Run Directly (parent agent)

- Single command with predictable, small output (<5KB)
- Parent already knows the exact command — no discovery needed
- Quick inspection: `ls`, `cat`, `git status`, `make -C backend test`

### When to Delegate to Command Executor

| Signal | Why Delegate |
|--------|-------------|
| Expected output >5KB | Keeps parent context clean — executor summarizes findings |
| 3+ commands to run | Parallelization and batch cleanup value |
| Daemon/server lifecycle | Reliable start → capture → kill lifecycle management |
| Process group management | Trap patterns for child process cleanup |
| Large build output | File redirection + post-capture extraction |
| Command requires Makefile discovery | Only if parent doesn't already know the target |

### Routing Decision Tree

```
Single command, output <5KB, command known?
  └── YES → Run directly (apply pre-command checks above)
  └── NO ↓
Multiple commands needing parallel execution?
  └── YES → Delegate to command executor
  └── NO ↓
Expected output >5KB or needs post-capture extraction?
  └── YES → Delegate to command executor
  └── NO ↓
Daemon lifecycle (start, observe, kill)?
  └── YES → Delegate to command executor
  └── NO → Run directly
```

</delegation_routing>

---

## <anti_patterns>

| Don't | Do Instead |
|-------|------------|
| `npm run build` (bare command) | `make -C frontend build` (env-aware) |
| `git log --all -p \| head -50` (no timeout) | `timeout 30 git log -n 50 -p` (bounded + timeout) |
| Delegate a simple `make test` to command executor | Run directly — delegation overhead exceeds value |
| Run 5 parallel commands manually in parent | Delegate — executor handles parallel launch + batch cleanup |
| Ignore exit codes after timeout | Check `$? -eq 124` to detect timeout vs failure |

</anti_patterns>
