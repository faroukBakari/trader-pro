# Use Cases

Pattern catalog for common command execution scenarios. Each use case shows the execution strategy, key considerations, and the subagent phases involved.

---

## Use Case 1: Single Short Command

**Scenario**: Run a known `make` target with predictable small output.

**Routing decision**: Run directly in parent agent — delegation overhead exceeds value.

**Example**: `make -C backend test-broker`

**Why NOT delegate**: Output is <5KB, command is known, no cleanup complexity. Parent runs directly with `terminal-usage` pre-command checks.

---

## Use Case 2: Full Test Suite (Large Output)

**Scenario**: Run full backend or frontend test suite — output may exceed 60KB.

**Routing decision**: Delegate to command executor.

**Strategy**:

- Phase 0: FAST path (exact command provided)
- Phase 2: File-redirect output to `/tmp/cmd-test-suite.log`
- Phase 3: Extract failure summary, coverage numbers from log file
- Phase 4: Kill terminal, remove log

**Key patterns**:

```bash
make -C backend test > /tmp/cmd-backend-tests.log 2>&1; echo "CMD_EXIT_CODE=$?"
```

---

## Use Case 3: Parallel Module Tests

**Scenario**: Run backend and frontend tests simultaneously for pre-commit validation.

**Routing decision**: Delegate — parallelization value.

**Strategy**:

- Phase 0: BATCH path (multiple commands)
- Phase 1: Verify independence → parallel group
- Phase 2: Launch both as background terminals
- Phase 3: Await both, extract results from each
- Phase 4: Kill both terminals

**Execution flow**:

```
Terminal A: make -C backend test    ─┐
Terminal B: make -C frontend test   ─┤── await both
                                     └── extract + cleanup
```

---

## Use Case 4: Sequential Build Chain

**Scenario**: Generate specs, then generate clients, then run tests — each step depends on the previous.

**Routing decision**: Delegate — sequential dependency management + multi-step.

**Strategy**:

- Phase 0: FULL path (dependency ordering needed)
- Phase 1: Identify sequential dependency
- Phase 2: Launch step 1 → await → check exit code → launch step 2 → ...
- Phase 3: Extract errors from each step
- Phase 4: Kill all terminals

**Abort condition**: If any step fails (non-zero exit), stop the chain and report the failure point.

---

## Use Case 5: Daemon Lifecycle

**Scenario**: Start dev server, observe startup logs, verify it's healthy, then kill.

**Routing decision**: Delegate — daemon cleanup requires process group management.

**Strategy**:

- Phase 0: FULL path (daemon detection)
- Phase 1: Detect daemon spawning → prepare process group trap
- Phase 2: Launch with trap wrapper:
  ```bash
  trap 'kill $(jobs -p) 2>/dev/null' EXIT TERM INT HUP
  make -f project.mk dev-backend
  ```
- Phase 3: Await startup (short timeout: 15-30s), extract bound port and init logs
- Phase 4: Kill terminal (trap cleans up child processes)

---

## Use Case 6: Docker Build

**Scenario**: Build a Docker image — potentially very large output, may hang on network.

**Routing decision**: Delegate — large output + long timeout.

**Strategy**:

- Phase 0: FAST path (exact command known)
- Phase 2: File-redirect to `/tmp/cmd-docker-build.log`, timeout 600s
- Phase 3: Read log file, extract errors, warnings, image size
- Phase 4: Kill terminal, remove log

**Key patterns**:

```bash
docker build -t trader-pro . > /tmp/cmd-docker-build.log 2>&1; echo "CMD_EXIT_CODE=$?"
```

---

## Use Case 7: Makefile Discovery

**Scenario**: Caller says "run the backend linter" but doesn't know the exact make target.

**Routing decision**: Delegate — discovery needed before execution.

**Strategy**:

- Phase 0: FULL path (description, not command)
- Phase 1: `grep_search` for `lint` in `backend/Makefile` → discover target name
- Phase 2: Execute discovered target with appropriate timeout
- Phase 3: Extract lint errors/warnings
- Phase 4: Cleanup

**Anti-hallucination**: If target not found, report `NOT FOUND: lint target in backend/Makefile` — never fabricate.

---

## Routing Summary

| Use Case             | Delegate? | Path   | Key Value              |
| -------------------- | --------- | ------ | ---------------------- |
| Single short command | No        | Direct | Avoid overhead         |
| Large output suite   | Yes       | FAST   | Context hygiene        |
| Parallel modules     | Yes       | BATCH  | Speed                  |
| Sequential chain     | Yes       | FULL   | Dependency mgmt        |
| Daemon lifecycle     | Yes       | FULL   | Cleanup reliability    |
| Docker build         | Yes       | FAST   | Timeout + large output |
| Makefile discovery   | Yes       | FULL   | Target resolution      |
