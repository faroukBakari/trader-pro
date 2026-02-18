## Plan Mode

**Plan file location**: Always write plan files to `docs/tmp/` (project root). Never create plans under `home/`, `.claude/plans/`, or any nested path outside the project. If `docs/tmp/` does not exist, create it before writing.

---

## Skill & Agent Routing

**Skill scan**: Every turn, check available skill descriptions. Match found → read the skill. No match → proceed without one.

**Cross-cutting skills** (load when trigger appears, regardless of primary task):
- `thinking-integration` → before subagent delegation, effort calibration
- `context-efficiency` → large files/output (>200 lines, >50KB), convergence stalls
- `command-execution` → Bash subagent delegation, complex shell commands
- `vscode-mcp-routing` → file moves/renames, diagnostics-driven edit loops

**Slash commands**: `/backend`, `/frontend` fork to project-level expert agents. `/research`, `/design`, and `/introspect` are available across all projects (user-level).

**Delegation**: For T1+ work, prefer subagents to preserve context. Default to `/research` for any investigation or evidence-gathering before implementation — it preserves main context and returns structured, cite-verified findings. Launch independent subtasks concurrently in a single message.

**Model selection**: Sonnet for implementation, research, and verification. Opus only for IA stack design (`.claude/` directory changes). Haiku for trivial lookups.

---

## Execution

**Convergence monitoring**:
- 8+ tool calls without deliverable progress → pause, reassess, ask user if stuck
- 12+ tool calls without concrete output → stop, surface status and blockers

**Tooling**: Use `Read`/`Write`/`Edit`/`Glob`/`Grep` over Bash equivalents. Use VS Code MCP tools (`move_file_code`, `rename_file_code`, `get_diagnostics_code`) for workspace-aware operations. Use env wrappers (`poetry run`, `make` targets) — never bare `pip`/`npm`/`python`.

**Quality gates**:
- Code → run type-check (`make -C backend type-check` for Python, `make -C frontend type-check` for TypeScript) + run tests (`make -C backend test` or `make -C frontend test`). Type-check is recommended for all code changes; tests are mandatory.
- New features / breaking refactors → run coverage (`make -C backend test-cov`) and check for gaps. Update relevant docs (module READMEs, `datastores/README.md`, architecture docs in `backend/docs/`).
- Docs → re-read after writing. Config → confirm changes took effect.

---

## Compact Instructions (FOR SUMMARIZER AGENT ONLY)

**Always preserve**: Current task goal, architectural decisions, file paths of in-progress changes, type mapping conventions, broker/provider patterns, user preferences.

**Safe to drop**: Full file contents already written, dead-end search results, verbose successful command output, resolved debugging steps.
