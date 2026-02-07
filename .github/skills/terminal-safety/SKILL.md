---
name: terminal-safety
description: Terminal command safety with timeout guards, pipe behavior, and output truncation strategies. Applies when running shell commands, using pipes with output limiters, or executing long-running processes.
---

# Terminal Command Safety

## <when_to_use>

Auto-loads when:
- Keywords: timeout, command, terminal, shell, pipe, execute, hang, slow
- Phrases: "run command", "execute in terminal", "pipe output"
- Contexts: Before using `execute` tool, when planning shell commands

</when_to_use>

---

## <scope>

### IN SCOPE:
- Timeout guard patterns for long-running commands
- Pipe behavior and source termination issues
- Output truncation strategies (head/tail/grep optimization)
- Command efficiency (limiting scope, avoiding unbounded operations)
- Error handling (exit codes, stderr redirection)

### OUT OF SCOPE:
- Shell scripting tutorials → See bash/zsh documentation
- Specific tool syntax details → See man pages
- Performance profiling → See project-specific docs

</scope>

---

## <quick_reference>

### Pre-Command Reasoning (Apply ALWAYS)

Before executing ANY terminal command, check these 3 things:

| Check | Think Through | If Yes |
|-------|---------------|--------|
| **1. Makefile First** | "Is there a `make` target that already does this?" | Use the make target instead |
| **2. Env-Aware** | "Am I using the project's environment wrappers?" | Must use `make`, `poetry run`, or `nvm use &&` |
| **3. Timeout Guard** | "If I'm limiting output with `head`/`tail`/`more`, could the source hang?" | Add `timeout N` before the command |

### Timeout Decision Tree

```
┌─ Does command produce bounded output naturally?
│   └─ YES (e.g., echo, cat small-file) → No timeout needed
│   └─ NO ↓
├─ Am I using output limiters (head/tail/grep/more)?
│   └─ YES → MUST add timeout (pipe doesn't kill source)
│   └─ NO ↓
├─ Could command run indefinitely?
│   └─ YES (git --all, docker build, npm install) → Add timeout
│   └─ NO ↓
└─ Uncertain? → Add timeout (better safe than hung)
```

### Command Safety Checklist

- [ ] Timeout added if using head/tail/grep with unbounded source
- [ ] Scope limited (avoid --all, use -n limits, specify paths)
- [ ] Error handling present (2>&1 for stderr capture if relevant)
- [ ] Environment wrapper used (make, poetry run, not bare npm/pip)

</quick_reference>

---

## <methodology>

### Phase 1: Pre-Execution Reasoning

**Example thought process:**
```
I need to see last 50 lines of git log...
→ Check 1: Is there a make target? NO (specific inspection)
→ Check 2: git is environment-agnostic, OK
→ Check 3: Am I using tail/head? YES. Could git log hang? YES (--all searches entire history)
→ Decision: Add timeout before git command
```

### Phase 2: Timeout Selection

**Timeout values:**

| Command Type | Typical Duration | Timeout Value | Reasoning |
|--------------|------------------|---------------|-----------|
| File reads | <1s | 5s | Should be instant |
| Git lookups | 1-10s | 30s | May scan history |
| Builds (incremental) | 10-60s | 120s | Allow for compilation |
| Builds (clean) | 1-5min | 300s | Full rebuild time |
| Tests | 10-60s | 120s | Suite execution |
| npm/pip install | 30-180s | 300s | Network + install |
| docker build | 2-10min | 600s | Image layers + network |

**Rule:** Be conservative—allow 2-3x estimated duration for low-end machines.

### Phase 3: Output Management Strategies

**Pattern 1: Stream Truncation (Common Case)**
```bash
# ❌ WRONG: Source doesn't terminate
git log --all -p | head -50

# ✅ CORRECT: Timeout kills hanging source
timeout 30 git log --all -p | head -50

# ✅ BETTER: Optimize source to avoid timeout
git log -n 50 -p  # Native limit, no full scan
```

**Pattern 2: Search in Large Output**
```bash
# ❌ WRONG: Unbounded search
docker build . 2>&1 | grep error

# ✅ CORRECT: Timeout with pattern
timeout 180 docker build . 2>&1 | grep error

# ✅ BEST: Save output, then search
timeout 180 docker build . 2>&1 > build.log && grep error build.log
```

**Pattern 3: Live Monitoring**
```bash
# ✅ For watching progress without hanging
timeout 60 npm run build 2>&1 | tail -20
```

### Phase 4: Error Handling

**Capture exit codes:**
```bash
# Check if timeout triggered
timeout 30 command args
if [ $? -eq 124 ]; then
  echo "Command timed out after 30s"
fi
```

**Stderr redirection:**
```bash
# Capture both stdout and stderr
timeout 60 pytest 2>&1

# Separate streams
timeout 60 command 2> errors.log 1> output.log
```

</methodology>

---

## <patterns>

### Git Command Optimization

| ❌ Slow (unbounded) | ✅ Fast (bounded) |
|---------------------|-------------------|
| `git log --all -p` | `git log -n 50 -p` |
| `git log --all -S "term"` | `git log -n 100 -S "term" -- path/to/file` |
| `git grep term` (all history) | `git grep term HEAD` (current only) |

**With timeout guards:**
```bash
# Still need timeout for large repos even with -n
timeout 30 git log -n 100 -p -S "search_term" -- specific/file.py | head -50
```

### Build Tool Safety

```bash
# Python (backend)
timeout 120 make -C backend test          # Bounded by makefile
timeout 300 poetry install                # Network-dependent

# TypeScript (frontend)
timeout 120 make -C frontend build        # Vite build
timeout 180 npm install                   # Use make instead when possible

# Docker
timeout 600 docker build -t image .       # Large images
timeout 30 docker ps                      # Should be instant
```

### Test Execution

```bash
# Backend tests
timeout 120 make -C backend test                                    # Full suite
timeout 60 poetry run pytest tests/path/test_file.py               # Single file

# Frontend tests
timeout 120 make -C frontend test                                  # Full suite
timeout 60 make -C frontend test VITEST_ARGS="path/test.spec.ts"  # Single file
```

### Log Analysis

```bash
# ❌ WRONG: Reads entire file, then shows last 50
timeout 10 cat huge.log | tail -50

# ✅ CORRECT: tail optimizes reading from end
tail -50 huge.log

# ❌ WRONG: grep reads entire file
timeout 30 cat huge.log | grep ERROR

# ✅ CORRECT: grep can stop early with context
grep -m 10 -A 5 -B 5 ERROR huge.log  # Stop after 10 matches
```

</patterns>

---

## <anti_patterns>

### ❌ Don't: Pipe Unbounded Source to head/tail Without Timeout

```bash
# BAD: If build hangs, waits forever
docker build . 2>&1 | tail -50

# BAD: git log scans entire history even though head stops
git log --all -p | head -100
```

**Why it fails:** Pipes don't send termination signals upstream. The source command runs to completion (or forever) regardless of downstream consumer stopping.

### ❌ Don't: Use --all or Unbounded Searches

```bash
# BAD: Scans every commit in every branch
git log --all -S "term"

# GOOD: Limit scope
git log -n 50 -S "term" -- specific/path/
```

### ❌ Don't: Ignore Exit Codes

```bash
# BAD: Timeout happened but you don't know
timeout 30 command && echo "Success"

# GOOD: Check exit code
timeout 30 command
if [ $? -eq 124 ]; then
  echo "⚠️ Command timed out (may need longer duration or optimization)"
elif [ $? -eq 0 ]; then
  echo "✅ Success"
else
  echo "❌ Command failed"
fi
```

### ❌ Don't: Use Bare npm/pip/python Commands

```bash
# BAD: Ignores project environment
npm install
python -m pytest

# GOOD: Use make targets (env-aware)
make -C frontend install
make -C backend test
```

---

## <related_skills>

- [mode-readonly](../mode-readonly/SKILL.md): When NOT to execute commands (read-only constraints)
- [agent-routing](../agent-routing/SKILL.md): When to delegate command execution to subagents

</related_skills>
