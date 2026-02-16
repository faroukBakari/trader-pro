---
name: command-execution
description: Guarded terminal execution with pre-flight validation and timeouts. Load when delegating commands to Bash subagents
user-invocable: false
---

# Command Execution

Guarded terminal execution methodology for Claude Code CLI. Provides a **pre-flight validation layer** (command guards) that makes Bash subagent delegation safe for auto-approve. Every command passes through guards before execution — no exceptions.

---

## <when_to_use>

Apply when:
- Delegating command execution to `Task(subagent_type="Bash")`
- Running multi-command batches (parallel or sequential)
- Executing commands with expected large output (>50KB)
- Managing daemon lifecycle (start → observe → stop)
- Any command that would benefit from structured pre-flight validation

Do NOT use (run inline instead):
- Single command with small output (<5KB), command already known
- Quick inspection: `ls`, `git status`, `git diff --stat`

</when_to_use>

---

## <command_guards>

**MANDATORY pre-flight — run for EVERY command before execution.**

```
COMMAND GUARD — Pre-Flight Checklist
│
├── G1. ALLOWLIST CHECK
│   Does the command match a settings.json allow pattern?
│   ✅ make -f project.mk *    ✅ make -C backend *
│   ✅ make -C frontend *      ✅ poetry run pytest *
│   ✅ poetry run python *     ✅ poetry run mypy/pyright/black/isort *
│   ✅ npm run *               ✅ npx *
│   ✅ git (read ops)          ✅ gh *
│   ✅ docker-compose -f docker-compose.dev.yml *
│   ✅ docker ps/logs          ✅ ls/pwd/which/wc/sort/uniq
│   ❌ NOT ON LIST → REFUSE — report "BLOCKED: command not in allowlist"
│
├── G2. DENYLIST CHECK
│   Does the command match a settings.json deny pattern?
│   ❌ rm -rf *     ❌ sudo *        ❌ curl/wget *
│   ❌ pip install * ❌ npm install * ❌ poetry add/remove *
│   ❌ git push --force *           ❌ git reset --hard *
│   ❌ git checkout . / git clean   ❌ docker rm/rmi *
│   ❌ kill -9 *    ❌ alembic downgrade *
│   MATCH → REFUSE — report "BLOCKED: command in denylist"
│
├── G3. ENVIRONMENT WRAPPER
│   Is the command using proper project wrappers?
│   ❌ npm test        → ✅ make -C frontend test
│   ❌ python script.py → ✅ poetry run python script.py
│   ❌ pip install X   → ✅ make target (denied anyway)
│   ❌ pytest          → ✅ poetry run pytest / make -C backend test
│   BARE COMMAND → REFUSE — report "BLOCKED: missing env wrapper"
│
├── G4. TIMEOUT ENFORCEMENT
│   Every command MUST have a timeout.
│   | Command Type            | Timeout   |
│   |-------------------------|-----------|
│   | File reads, git ops     | 30s       |
│   | Tests, incremental builds | 120s    |
│   | Clean builds, installs  | 300s      |
│   | Docker builds           | 600s      |
│   Rule: 2-3x estimated duration. Always use `2>&1`.
│   NO TIMEOUT → ADD ONE before execution.
│
└── G5. OUTPUT PLAN
    Expected output >50KB?
    YES → Note in report; use Bash timeout to prevent truncation issues
    NO  → Direct capture
```

### Guard Verdict Format

Before executing, emit a one-line verdict:

```
GUARD: ✅ PASS — `make -C backend test` [timeout: 120s] [output: <5KB]
GUARD: ❌ BLOCKED — `pip install requests` — denylist match (G2)
```

</command_guards>

---

## <methodology>

### Phase 0: Complexity Routing

Classify the invocation to select the execution path:

| Signal | Path |
|--------|------|
| Caller provided exact command + timeout → single command | **FAST** — skip to Phase 2 |
| Caller provided exact commands + timeout → multiple commands | **BATCH** — Phase 1 dependency check, then Phase 2 |
| Caller provided description, not exact command | **FULL** — Phase 1 discovery, then Phase 2 |

### Phase 1: Command Resolution (skip on FAST path)

1. **Makefile discovery**: Search project Makefiles for equivalent target — verify target exists before using it
2. **Environment wrapper**: Python → `make -C backend` / `poetry run`; Node → `make -C frontend` / `nvm use &&`; Docker/git → direct OK
3. **Output estimation**: Will output exceed 50KB? → plan accordingly
4. **Dependency ordering** (batch only): Independent commands → parallel; dependent → sequential chain

### Phase 2: Guarded Execution

**Run command guards (G1–G5) for EVERY command. No exceptions.**

For each command that passes guards:

1. **Single command**: Use `Bash` tool with appropriate `timeout`
2. **Parallel batch**: Use multiple `Bash` tool calls in a single message (Claude Code runs them concurrently)
3. **Sequential chain**: Use `Bash` with `&&` chaining, or sequential tool calls where exit code matters
4. **Background/daemon**: Use `Bash(run_in_background: true)`, then `TaskOutput` to check status

Always include `2>&1` to capture stderr.

### Phase 3: Output Extraction & Report

For each completed command:

1. Check exit code (0 = success, 124 = timeout, other = failure)
2. Extract caller-requested findings from output (errors, test results, coverage, etc.)
3. Compose structured execution report (see output format below)

</methodology>

---

## <caller_protocol>

Callers invoke via `Task(subagent_type="Bash")` with skill context:

```
You are a command execution specialist. Follow the command-execution skill methodology:
- Run command guards (G1-G5) before every command
- Use proper environment wrappers (make targets, poetry run)
- Apply timeouts to all commands
- Return structured execution report

Execute: `{command}` [timeout: {N}s]
Extract: {what to look for — errors, test failures, coverage}
Context: {why these commands are being run}
```

### Invocation Examples

**Single command**:
```
Execute: `make -C backend test` [timeout: 120s]
Extract: test results, failures, coverage numbers
Context: validating backend after broker module refactor
```

**Parallel batch**:
```
Execute the following commands in parallel:
1. `make -C backend test` [timeout: 120s]
2. `make -C frontend test` [timeout: 120s]

Extract: test results and failures from each
Context: pre-commit validation across both stacks
```

**Sequential chain**:
```
Execute sequentially:
1. `make -C backend generate` [timeout: 120s]
2. `make -C frontend generate` [timeout: 120s]
3. `make -C frontend test` [timeout: 120s]

Extract: errors at each step; final test results
Context: regenerating clients from updated models, then validating
```

**Daemon lifecycle**:
```
Execute: `make -f project.mk dev-backend` as background [timeout: 30s for startup check]
Extract: startup confirmation, bound port, initialization errors
Context: verify backend starts cleanly after config change
```

</caller_protocol>

---

## <output_format>

```markdown
## Command Execution Report

### Guard Verdicts
| # | Command | Verdict |
|---|---------|---------|
| 1 | `{cmd}` | ✅ PASS [timeout: Ns] |
| 2 | `{cmd}` | ❌ BLOCKED — {reason} |

### Execution Summary
| # | Command | Status | Duration | Exit Code |
|---|---------|--------|----------|-----------|
| 1 | `{cmd}` | ✅ Success / ❌ Failed / ⏰ Timeout | {N}s | {code} |

### Findings

#### Command 1: `{short_cmd}`
**Key Output**:
{Relevant extracted content per caller's Extract request}

**Errors/Warnings** (if any):
{Error or warning text}
```

</output_format>

---

## <anti_patterns>

| Don't | Do Instead |
|-------|------------|
| Skip command guards for "obvious" commands | Run guards G1-G5 for every command — no exceptions |
| `npm run build` (bare command) | `make -C frontend build` (env-aware wrapper) |
| Execute without timeout | Always set timeout per Phase 2 table |
| Pipe during execution (`cmd \| head -50`) | Capture full output, extract post-execution |
| Guess a `make` target name | Search Makefiles to verify target exists |
| Run denied commands and ask forgiveness | Check denylist first — refuse immediately |
| Modify files or write code | You are an executor, not an implementer |
| Ignore exit codes | Check `$?`: 0=success, 124=timeout, other=failure |

</anti_patterns>
