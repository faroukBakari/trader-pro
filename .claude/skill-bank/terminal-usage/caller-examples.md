# Caller Examples

Invocation templates for parent agents delegating to the `command` subagent. Read this file BEFORE composing your delegation prompt to ensure structured invocation.

---

## Single Command — Simple

```
Execute: `make -C backend test` [timeout: 120s]
Extract: test results, failures, coverage numbers
Context: validating backend after broker module refactor
```

## Single Command — Large Output

```
Execute: `make -C backend test-all` [timeout: 300s]
Extract: failed test names, error tracebacks, total pass/fail counts
Context: full test suite run before PR merge — output expected >50KB
```

## Single Command — Docker Build

```
Execute: `docker build -t trader-pro .` [timeout: 600s]
Extract: build errors, final image size, cache hit/miss info
Context: CI image rebuild after dependency changes
```

## Parallel Batch — Independent Modules

```
Execute the following commands in parallel:
1. `make -C backend test` [timeout: 120s]
2. `make -C frontend test` [timeout: 120s]

Execution: parallel
Extract: test results and failures from each
Context: pre-commit validation across both stacks
```

## Sequential Chain — Build Then Test

```
Execute the following commands sequentially:
1. `make -C backend generate` [timeout: 120s]
2. `make -C frontend generate` [timeout: 120s]
3. `make -C frontend test` [timeout: 120s]

Execution: sequential
Extract: any errors or warnings at each step; final test results
Context: regenerating clients from updated backend models, then validating
```

## Daemon Lifecycle — Start, Observe, Kill

```
Execute: `make -f project.mk dev-backend` as daemon [timeout: 30s for startup]
Extract: startup confirmation (bound port), initialization errors
Context: need to verify backend starts cleanly after config change — kill after extraction
```

## Selective Module Loading

```
Execute: `ENABLED_MODULES=broker:v1 make -f project.mk dev-backend` as daemon [timeout: 30s for startup]
Extract: module registration logs, bound port, any import errors
Context: testing broker module isolation
```

## Code Generation Validation

```
Execute the following commands sequentially:
1. `make -f project.mk generate` [timeout: 180s]
2. `git diff --stat` [timeout: 10s]

Execution: sequential
Extract: generation errors/warnings; list of files changed by generation
Context: checking if model changes produced expected client updates
```

---

## Anti-Patterns in Invocation

| Bad Invocation              | Problem                                   | Better                                                                                |
| --------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------- |
| "Run some tests"            | No specific command, no extraction target | "Execute: `make -C backend test` [timeout: 120s]. Extract: failures."                 |
| "Check if things work"      | Unbounded scope                           | "Execute: `make -f project.mk dev-backend` as daemon. Extract: startup confirmation." |
| "Run `npm test`"            | Bare npm — no env wrapper                 | "Execute: `make -C frontend test`"                                                    |
| "Build and test everything" | No execution order, no timeouts           | Use sequential chain with explicit commands and timeouts                              |
