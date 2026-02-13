## 0. Prompt Routing

Before your first action, route the request through these three steps. User framing ("typo", "quick", "simple") describes expectations, not task properties — classify by what the task requires.

### Step 1: Route to Skill (Unconditional)

ALWAYS scan category glossary descriptions (in the system-reminder skills list). Match → Read glossary → Follow load path to the skill. No match → proceed without skill.

| Task Signal                                    | Category             |
| ---------------------------------------------- | -------------------- |
| Debug, diagnose, root-cause                    | development          |
| Implement, modify, build, decompose            | development          |
| Type errors (Python / TS)                      | development          |
| WebSocket features                             | development          |
| Provider / integration                         | development          |
| Review, audit, quality, request analysis       | review               |
| Documentation                                  | review               |
| Session retrospective                          | review               |
| Test strategy, coverage, visual verification   | testing              |
| Frontend (Vue, TS, UI, UX, a11y)               | frontend             |
| Refactor                                       | development + review |
| Research, explain, compare                     | workflow             |
| Ambiguous / open-ended                         | workflow             |
| Runtime, config, VS Code, MCP routing          | workflow             |
| Session history, file recovery                 | workflow             |
| IA stack, skills, agents, audit                | ia-design            |
| Prompt engineering, model-specific tuning      | prompting            |
| Reasoning effort, calibration, model selection | reasoning            |
| TradingView charting, external API wrappers    | tradingview          |

**Composite requests** (e.g., "review X and fix Y"): decompose into sub-tasks, route each independently (including modifier check per sub-task), execute in logical order.

Applies to subagent delegation too — inject the matching skills into the subagent prompt.

### Step 2: Assess Complexity

| Tier | Signals                                              | Effort |
| ---- | ---------------------------------------------------- | ------ |
| T0   | Known file, known fix, <5 lines                      | low    |
| T1   | Single file, clear scope                             | medium |
| T2   | Multi-file or ambiguous scope                        | high   |
| T3   | Architecture decision or multi-step tool workflow    | high   |
| T4   | Adversarial, race condition, security, deep analysis | max    |

Scope and reasoning depth are independent — a single-file race condition is T1 scope but needs T4 reasoning. When they diverge, use the **higher** tier for effort calibration.

Ambiguous scope (e.g., "fix backend typo" with no file) → T2 minimum until clarified.

### Step 3: Auto-attach Modifiers

Cross-cutting skills that layer ON TOP of the primary skill when runtime signals appear during execution:

| Signal                       | Auto-load                               | When                             |
| ---------------------------- | --------------------------------------- | -------------------------------- |
| Delegating to subagent       | `agent-routing`, `thinking-integration` | Before any `Task` tool call      |
| Writing prompts for agents   | `prompting-guide` + model flaw catalog  | Prompt text in subagent prompt   |
| Large file / diff / output   | `runtime-efficiency`                    | >200 lines, >3 files, >50KB      |
| Mid-flight scope drift       | `drift-guard`                           | Blocker or scope change detected |
| Entering implementation      | `implementation-reasoning`              | After planning, before coding    |
| Bash command delegation      | `command-execution`, `terminal-usage`   | Bash subagent or complex shell   |
| Multi-step subagent workflow | `context-persistence`                   | 2+ sequential subagent calls     |
| Choosing model for subagent  | `model-selection`                       | `model:` parameter decision      |
| Ambiguous user request       | `request-evaluation`                    | Vague scope, missing specifics   |

### Skill Loading Mechanics

Skills live in **category glossaries** at `.claude/skills/{category}/SKILL.md`. Each glossary lists skills with descriptions and load paths.

| Step         | Action                                                    | Example                                |
| ------------ | --------------------------------------------------------- | -------------------------------------- |
| 1. **Scan**  | Check glossary descriptions in system-reminder            | See "Available skills" list            |
| 2. **Drill** | Read a category glossary for skills table + keyword index | `Read .claude/skills/testing/SKILL.md` |
| 3. **Load**  | Follow the load path to read the skill                    | Path shown in glossary header          |

**Multi-skill tasks**: When a single task requires more than one domain skill (same or different categories), load each — primary first, then additional matches. Distinct from composite requests (sequential sub-tasks) and auto-attach modifiers (orthogonal concerns).

---

## 1. Process Gates

### Behavioral Defaults

Cross-cutting principles applied regardless of active skill (detail: `engineering-principles` skill):

1. **Reuse before building** — search workspace, existing deps, and standard libraries first
2. **Align with industry standards** — follow RFCs, PEPs, OWASP, framework conventions; deviate only with justification
3. **Simplicity** — straightforward solutions leveraging native features; avoid over-engineering
4. **FinOps & token efficiency** — batch operations, filter output, checkpoint long investigations

### FinOps Checkpoints

Volume and convergence thresholds — for full handling protocols, load `runtime-efficiency` skill.

| Checkpoint             | Trigger                                    | Action                                                 |
| ---------------------- | ------------------------------------------ | ------------------------------------------------------ |
| **Large file**         | File >200 lines                            | Targeted read (line ranges); never full-file           |
| **Large diff**         | >3 files or >500 lines changed             | Delegate to subagent; chunk if inline                  |
| **Bulk search**        | >20 matches returned                       | Narrow query or delegate to `Explore`                  |
| **Large output**       | Command output >50KB expected              | Delegate to `Bash` subagent with filtered output       |
| **Convergence**        | 8+ tool calls without deliverable progress | Pause → reassess approach → `AskUserQuestion` if stuck |
| **Hard stop**          | 12+ tool calls without concrete output     | Stop → surface status and blockers to user             |
| **Effort calibration** | Subagent delegation                        | Match model + effort to task tier (§0 Step 2)          |

### Delivery Quality Gate (No Unverified Output)

- **Never deliver untested code**: Run relevant tests before presenting changes as complete
- **Never deliver unchecked docs**: Re-read updated documentation to verify accuracy and consistency
- **Never deliver unverified config**: Confirm changes took effect (build, lint, health check)
- Applies to **all deliverables** — if it can be verified, verify it before delivery

---

## 2. Architecture & Codebase

> Architecture details, file locations, and documentation navigation: `.claude/REFERENCE.md`

---

## 3. Runtime & Tools

**Runtime**: **Claude Code CLI** on **WSL2 (Ubuntu 22.04)** with full Windows interop. VS Code Remote-WSL.

- **Claude Code for VS Code**: CLI runs as the extension backend — inline chat, terminal panel, and diff review in-editor. MCP servers from `.vscode/mcp.json` auto-loaded alongside `.claude/settings.json` servers
- **VS Code MCP server**: `mcp__vscode-mcp-server__*` tools available (diagnostics, move, rename, replace)
- **Windows-side VS Code config writable** from WSL (settings, keybindings, MCP config)
- **WSL interop enabled**: Windows executables (`powershell.exe`, `explorer.exe`, `clip.exe`, Chrome) callable directly
- **Mirrored networking**: WSL and Windows share `localhost` — no port forwarding needed
- **GPU**: RTX 4090 + CUDA 12.4 available (Ollama running)

**Full inventory**: Detailed runtime awareness skill available.

### VS Code - IDE Integration

The VS Code MCP server (`mcp__vscode-mcp-server__*`) provides workspace-aware editing tools. Key routing:

| Tool                                  | When                                                | Instead Of                                            |
| ------------------------------------- | --------------------------------------------------- | ----------------------------------------------------- |
| `get_diagnostics_code`                | **After every edit batch** + before task completion | Running individual linters                            |
| `move_file_code` / `rename_file_code` | Moving/renaming **any source file**                 | `Bash mv` (breaks Write guard + skips import updates) |
| `replace_lines_code`                  | Fixing errors at known line numbers                 | `Edit` when `old_string` isn't unique                 |
| `create_file_code`                    | Scaffolding with `ignoreIfExists: true`             | `Write` when file might already exist                 |

**Critical**: Never `Bash mv` then `Write`. Use `move_file_code`/`rename_file_code` instead.

**Full methodology**: look for vscode mcp skill.

### Interaction Guidelines

- For user interaction, use `AskUserQuestion`.
- For subagent delegation, use `Task` tool with `subagent_type`.
- For browser automation, use `mcp__playwright__*` tools directly, or delegate via `general-purpose` subagent.
- For commands (`Bash`): check for a `make` target first; use env wrappers (`poetry run`, `make -C {stack}`) — never bare `npm`/`pip`/`python`; set `timeout`; append `2>&1`. Batch or large output → delegate to `Bash` subagent with `command-execution` skill.
- For filesystem operations, use `Read`/`Write`/`Edit`/`Glob` by default — see VS Code MCP Tools table above. For exceptions (`move`/`rename`, `diagnostics`, `line-targeted` fixes).

### Permission Matrix

Your permissions are governed by `.claude/settings.json` (project-level) and `.claude/settings.local.json` (user-level). Key rules:

- **Development commands via Makefiles** → auto-approved
- **Git read operations** → auto-approved
- **Git push** → denied (manual user push only)
- **Direct `pip`/`npm`/`poetry add`** → denied (use Makefile targets)

### IA Stack Ownership (GOVERNANCE)

- The Claude Code IA stack (`.claude/CLAUDE.md`, `.claude/skills/`) is the authoritative configuration for this runtime.
- Category glossaries at `.claude/skills/{category}/SKILL.md` are auto-generated — never hand-edit.
- For any IA stack modification (skills, categories, routing, rules), load `ia-stack-ops` via the `ia-design` glossary.

---

## 4. Task Delegation (CLI Subagents)

Use the `Task` tool to delegate work to specialized subagents when appropriate.

**Built-in Subagent Types** (only valid values for `subagent_type`):

| `subagent_type`   | Use For                                                       | Effort |
| ----------------- | ------------------------------------------------------------- | ------ |
| `Explore`         | Codebase search, file discovery, architecture understanding   | low    |
| `Plan`            | Implementation planning, architecture design                  | high   |
| `Bash`            | Terminal command execution                                    | low    |
| `general-purpose` | Multi-step research, complex searches, feature implementation | high   |

> **Effort column**: Recommended thinking effort per `thinking-integration` skill.

**Delegation Rules**:

| Task Type                                                                  | `subagent_type`                       | Notes                                         |
| -------------------------------------------------------------------------- | ------------------------------------- | --------------------------------------------- |
| IA stack artifact                                                          | **inline**                            | Load `ia-stack-ops` — never delegate          |
| Broad codebase search                                                      | `Explore`                             |                                               |
| Large-output commands                                                      | `Bash`                                | Inject `command-execution` skill              |
| Implementation planning                                                    | `Plan` or `EnterPlanMode`             |                                               |
| Single-file fix                                                            | `general-purpose` + `model: "sonnet"` |                                               |
| Research / doc gathering                                                   | `general-purpose`                     | Inject `research-methodology` skill           |
| Everything else (features, tests, reviews, debugging, browser, doc-update) | `general-purpose`                     | Default; use `model: "sonnet"` for doc-update |

---

## ROUTING REMINDER (Recency Anchor)

> Every user turn: scan glossary descriptions → match category → Read glossary → load skill → execute. No exceptions. If no skill matches, proceed — but the scan must happen.

---

## 5. Compact Instructions (FOR SUMMARIZER AGENT ONLY)

> Preservation priorities when context is compacted (manual `/compact` or auto-compression).

**Always preserve**:

- Current task goal and acceptance criteria
- Architectural decisions made during the session
- File paths and line numbers of in-progress changes
- Type mapping conventions and import naming patterns
- Broker/provider integration patterns discussed
- Any user preferences or corrections stated during the session

**Safe to drop**:

- Full file contents already committed or written (re-readable from disk)
- Exploratory search results that led to dead ends
- Verbose tool output from successful commands
- Intermediate debugging steps for resolved issues
