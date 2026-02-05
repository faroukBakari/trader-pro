# Skill Examples

Complete examples demonstrating skill creation patterns.

> ⚠️ **VS Code / GitHub Copilot Compatibility**: Only `name` and `description` are reliably supported. Examples use the official agentskills.io specification.

> 🚨 **FILE FORMAT**: SKILL.md files must **NOT** have code fence wrappers (no ` ```yaml `, ` ```markdown `, ` ```skill `).
> The file must start directly with `---` (YAML frontmatter). Code fences in examples below are for **documentation display only**.

---

## Example 1: Reference Skill (Background Knowledge)

**Request:** "Create a skill for read-only investigation constraints"

### Organization Analysis

| Attribute              | Value               |
| ---------------------- | ------------------- |
| **Layer**              | Base (1)            |
| **Domain**             | `mode-`             |
| **Dependencies**       | None (foundational) |
| **Description Length** | 142 chars           |

### Output

```yaml
---
name: mode-readonly
description: Read-only investigation constraints. Apply when analyzing, debugging, reviewing code, or performing RCA without modifications.
---

# Read-Only Investigation Mode

Enforces non-destructive constraints for analysis tasks.

## Critical Constraints

CRITICAL — DO NOT violate:
- DO NOT create, edit, delete, move, or rename any file
- DO NOT run git state-changing commands: `checkout`, `stash`, `commit`, `reset`, `push`, `pull`
- DO NOT run destructive commands: `rm`, `mv`, `cp` on project files

## Allowed Operations

| Category | Allowed | Examples |
|----------|---------|----------|
| **File reading** | ✅ | `read_file`, `grep_search`, `file_search` |
| **Git inspection** | ✅ | `git status`, `git log`, `git diff`, `git blame` |
| **Tool inspection** | ✅ | `make --dry-run`, `npm run --dry-run` |
| **File modification** | ❌ | Any write operation |
| **Git modification** | ❌ | `add`, `commit`, `push`, `checkout` |

## Pre-Command Check

Before ANY terminal command, verify:
1. Does this alter files? → DO NOT RUN
2. Does this change git state? → DO NOT RUN
3. Does this modify system state? → DO NOT RUN
```

**Why this works:**

- Layer 1 (Base) — foundational constraint used by many prompts
- Description has clear trigger keywords: "analyzing", "debugging", "reviewing", "RCA"
- Constraints documented in skill body (not frontmatter)

---

## Example 2: Task Skill (Workflow)

**Request:** "Create a skill for debugging test failures"

### Organization Analysis

| Attribute              | Value                                 |
| ---------------------- | ------------------------------------- |
| **Layer**              | Task (3)                              |
| **Domain**             | `test-`                               |
| **Dependencies**       | References `mode-readonly` implicitly |
| **Description Length** | 98 chars                              |

### Output

````yaml
---
name: test-debug
description: Debug failing tests. Use when pytest fails, tests are red, CI is failing, or "why is this test broken".
---

# Debug Test Failure

Systematic approach to diagnosing and fixing failing tests.

## Input

Provide the test name or file to debug when invoking this skill.

## Steps

1. **Reproduce the failure**
   ```bash
   make -C backend test PYTEST_ARGS="-k '<test-name>' -v --tb=short"
   ```
````

2. **Analyze the output**
   - Identify: assertion error, exception, or fixture issue
   - Note: expected vs actual values
   - Check: stack trace for origin

3. **Check recent changes**

   ```bash
   git log --oneline -10 -- $(find . -name "*<test-name>*" -type f)
   ```

4. **Form hypothesis**
   List 2-3 possible causes ranked by likelihood

5. **Investigate top hypothesis**
   - What evidence would confirm/refute?
   - Gather that evidence

6. **Fix or escalate**
   - If root cause found: propose fix
   - If unclear: document findings, suggest next steps

## Success Criteria

- [ ] Test passes locally, OR
- [ ] Root cause identified with fix recommendation
- [ ] No unrelated tests broken

````

**Why this works:**
- Layer 3 (Task) — actionable workflow
- Description has action verbs and trigger phrases: "debug", "pytest fails", "tests are red", "CI is failing"
- Input documented in skill body (not argument-hint frontmatter)
- Clear steps with concrete commands

---

## Example 3: Domain Skill (Context-Specific)

**Request:** "Create conventions skill for TWS provider development"

### Organization Analysis

| Attribute | Value |
|-----------|-------|
| **Layer** | Domain (2) |
| **Domain** | `tws-` |
| **Dependencies** | None |
| **Description Length** | 134 chars |

### Output

```yaml
---
name: tws-conventions
description: TWS provider patterns and conventions. Apply when working with IBSocket, TWSClient, or TWS callbacks.
---

# TWS Provider Conventions

Patterns for Interactive Brokers TWS API integration.

## Architecture Layers

| Layer | Class | Responsibility |
|-------|-------|----------------|
| Provider | `TWSDatafeedProvider` | Capability interface |
| Client | `TWSClient` | Business logic, request orchestration |
| Socket | `IBSocket` | Raw TWS connection, threading |

## Callback Patterns

- All TWS callbacks run on IBSocket's reader thread
- Use `asyncio.run_coroutine_threadsafe()` to bridge to async
- Trackers own callback routing (QuoteTracker, BarsTracker, etc.)

## Naming Conventions

| Pattern | Example | Usage |
|---------|---------|-------|
| `req{Action}` | `reqQuote`, `reqBars` | Request methods |
| `{action}_cb` | `quote_cb`, `bars_cb` | Callback parameters |
| `Tracked{Entity}` | `TrackedOrder` | State-holding dataclass |

## Anti-Patterns

- ❌ Direct IBSocket access from provider layer
- ❌ Blocking calls on reader thread
- ❌ Shared mutable state without locks
````

**Why this works:**

- Layer 2 (Domain) — context-specific but reusable
- Referenced by Layer 3 skills like `tws-debug`
- Concise patterns, not exhaustive documentation
- Description has technology keywords: "IBSocket", "TWSClient", "TWS callbacks"

---

## Skill Comparison Matrix

| Skill             | Layer | Type      | Description Strategy                                |
| ----------------- | ----- | --------- | --------------------------------------------------- |
| `mode-readonly`   | 1     | Reference | Analysis keywords ("analyzing", "debugging", "RCA") |
| `tws-conventions` | 2     | Reference | Technology keywords ("IBSocket", "TWSClient")       |
| `test-debug`      | 3     | Task      | Action verbs ("debug", "pytest fails")              |

## Field Usage Summary

| Field           | Support         | Notes                                        |
| --------------- | --------------- | -------------------------------------------- |
| `name`          | ✅ Required     | All skills must have unique name             |
| `description`   | ✅ Required     | Single-line, trigger keywords, max 150 chars |
| `allowed-tools` | ⚠️ Experimental | May not work in all implementations          |

### ❌ Unsupported Fields (Ignored in VS Code)

| Field                      | Effect                                         |
| -------------------------- | ---------------------------------------------- |
| `user-invocable: false`    | Ignored — all skills are discoverable          |
| `disable-model-invocation` | Ignored — all skills can auto-trigger          |
| `argument-hint`            | Ignored — document input in skill body instead |
| `context: fork`            | Ignored                                        |
| `agent`                    | Ignored                                        |
