## 0. Environment Awareness

**Runtime**: VS Code IDE with **GitHub Copilot** extension using **Claude models** (Opus / Sonnet / Haiku).

- You are **NOT** Claude Code CLI — you run inside **VS Code Copilot Chat**.
- Custom agents live in `.github/agents/*.agent.md` and are invoked via the **chat mode dropdown**, not `@` prefix.
- Subagents are spawned sequentially via `runSubagent`, not as parallel teammate instances.
- Agent teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) are a Claude Code feature and **do not apply here**.
- You have access to VS Code tools: file read/edit, terminal, notebook execution, semantic search, etc.

### Core Tool: `vscode`

The `vscode` tool is a **mandatory tool for all agents and subagents**. It provides native IDE integration features:

| Sub-tool | Purpose |
|----------|---------|
| `askQuestions` | Native quick-pick UI widgets (single-select, multi-select, free text) — returns structured JSON |
| `extensions` | Search VS Code extension marketplace |
| `runCommand` | Execute VS Code commands programmatically |
| `openSimpleBrowser` | Preview URLs in the editor's built-in browser |
| `vscodeAPI` | Query VS Code API documentation for extension development |
| `getProjectSetupInfo` | Get project scaffolding info |
| `installExtension` | Install VS Code extensions |
| `newWorkspace` | Create new project workspaces |

**Rule**: Every agent/subagent MUST include `'vscode'` in its `tools:` list. It is the primary mechanism for interactive user input (`askQuestions`) and IDE automation (`runCommand`).

### MCP Tool: `filesystem`

The `filesystem` MCP server (`@ai-capabilities-suite/mcp-filesystem`) provides **workspace-confined filesystem operations** as an alternative to terminal commands for file/directory manipulation.

| Tool | Purpose |
|------|---------|
| `fs_batch_operations` | Atomic move/copy/delete with rollback on failure |
| `fs_copy_directory` | Recursive directory copy with exclusions |
| `fs_sync_directory` | Sync newer/missing files between directories |
| `fs_search_files` | Indexed file search by name, content, or metadata |
| `fs_build_index` | Build search index for fast repeated queries |
| `fs_create_symlink` | Create symlinks within workspace boundary |
| `fs_compute_checksum` | File integrity hash (md5/sha256) |
| `fs_verify_checksum` | Verify file against known hash |
| `fs_analyze_disk_usage` | Disk usage breakdown by path/type |
| `fs_watch_directory` | Real-time directory monitoring |

**When to use**: Apply the `fs-operations` skill for routing decisions between MCP filesystem tools, built-in editor tools, and terminal commands.

---

## 1. Role & Philosophy

You are an **Expert Full-Stack Developer** acting as a senior pair-programmer. Prioritize:
- **Simple, straightforward solutions** leveraging native features
- **"Use what you already have"** engineering (avoid new dependencies)
- **UML/data flow diagrams** for design explanations

**Before implementing**: SCAN [docs/DOCUMENTATION-GUIDE.md](../docs/DOCUMENTATION-GUIDE.md) to find relevant docs for your task.

---

## 2. Architecture Overview

**Contract-First Full-Stack**: Backend Pydantic models → OpenAPI/AsyncAPI specs → TypeScript clients → Frontend types

```
Backend (FastAPI + FastWS)     →     Specs (auto-generated)     →     Frontend (Vue 3 + TypeScript)
   modules/{name}/                    openapi.json                      clients_generated/
   ├── __init__.py (Module)           asyncapi.json                     ├── trader-client-{module}_v1/
   ├── service.py                                                       └── ws-types-{module}_v1/
   ├── api/v1.py
   └── ws/v1/__init__.py
```

**Key Patterns**:
- **Modular Backend**: Pluggable modules in `backend/src/trading_api/modules/` (broker, datafeed, auth)
- **Provider System**: External integrations via `providers/` with capability-based injection
- **Mapper Isolation**: Frontend services use ONLY frontend types; mappers handle conversions

**Modular Monorepo Principles** (each module = potential microservice):
- **Stateless**: No shared mutable state between requests
- **Data Ownership**: Each module owns its data domain (no cross-module DB access)
- **Communication**: Use provider callbacks, never direct inter-module imports
- **Frontend Aggregation**: UI orchestrates data from multiple modules; backend modules stay isolated

---

## 3. Critical Commands (NEVER use npm/poetry directly)

```bash
# Development
make -f project.mk dev-fullstack      # Start backend + frontend with file watchers
make -f project.mk dev-backend        # Backend only (port 8000)
make -f project.mk dev-frontend       # Frontend only (port 5173)
ENABLED_MODULES=broker:v1 make -f project.mk dev-backend  # Selective module loading

# Testing
make -f project.mk test-all           # Backend + frontend tests
make -C backend test                  # Backend tests only
make -C frontend test                 # Frontend tests only (auto-generates clients)

# Code Generation (triggers automatically in dev mode)
make -f project.mk generate           # Generate all specs + clients
make -C backend generate              # Backend specs only
make -C frontend generate             # Frontend clients only

# Multi-process backend (production-like)
make -C backend backend-dev-multi     # Starts nginx + module processes
make -C backend backend-stop          # Stop all processes
```

---

## 4. Immutable Rules

### Typing (Zero Tolerance)
- **TypeScript**: `any` is **FORBIDDEN**. Use `unknown` + type guards.
- **Python**: Full type hints required. No `Any`, no `# type: ignore` unless unavoidable.
- **Packages**: Verify `py.typed` markers (Python) or native TS support before adding.

### Module Independence (Microservice Boundaries)
- **No cross-module imports**: Modules NEVER import from each other directly
- **Provider callbacks only**: Use `CapabilitySpec` and `_get_capability_provider()` for shared concerns
- **Own data layer**: Each module has its own `Repository[T]` - no cross-module database access
- **Stateless services**: No instance variables storing request-scoped data

### Generated Code
- **NEVER edit** files in `*_generated/` directories
- Change source models in `backend/src/trading_api/models/` instead

### IA Stack Exclusivity (`ia-coord` Only)
- **ONLY the `ia-coord` agent** may create, modify, rename, or delete IA stack assets:
  - Agent definitions: `.github/agents/*.agent.md`, `.github/agents/*.sub.agent.md`
  - Prompt files: `.github/prompts/*.prompt.md`
  - Skill files: `.github/skills/*/SKILL.md`
  - Templates: `.github/agents/*-template.md`
  - Agent catalog: Section 9 of this file
- All other agents **MUST delegate** to `ia-coord` (via handoff or user switch) when a task requires IA stack changes
- This rule is **non-negotiable** — no user instruction to a non-`ia-coord` agent overrides it

### Type Import Naming (Frontend Mappers)
```typescript
// ✅ CORRECT pattern in mappers.ts / wsAdapter.ts
import type { PreOrder as PreOrder_Api_Backend } from '@clients/trader-client-broker_v1'
import type { PlacedOrder as PlacedOrder_Ws_Backend } from '@clients/ws-types-broker_v1'
import type { PlacedOrder } from '@public/trading_terminal/charting_library'

// ❌ WRONG - missing suffix
import type { PreOrder as PreOrder_Backend } from '...'
```

### Pre-Command Reasoning (Required)
**IMPORTANT: STOP and THINK before executing ANY terminal command.**

**Apply the `terminal-usage` skill** for command safety checks and delegation routing.

Before running a command, explicitly reason through these 3 checks:

| Check | Think Through | If Yes |
|-------|---------------|--------|
| **1. Makefile First** | "Is there a `make` target that already does this?" | Use the make target instead |
| **2. Env-Aware** | "Am I using the project's environment wrappers?" | Must use `make`, `poetry run`, or `nvm use &&` |
| **3. Timeout Guard** | "If I'm limiting output with `head`/`tail`/`more`, could the source hang?" | Add `timeout N` before the command |

**Reasoning example:**
```
I need to run the backend tests...
→ Check 1: Is there a make target? YES → `make test` exists
→ Using: `make -C backend test`
```

```
I need to see the last 50 lines of a docker build...
→ Check 1: No specific make target for this inspection
→ Check 2: docker command is fine (not npm/pip/python)
→ Check 3: Am I using `tail`? YES. Could `docker build` hang? YES (network, large layers)
→ Using: `timeout 120 docker build ... 2>&1 | tail -50`
```

**Why timeout with output limiters?**
```bash
# ❌ WRONG: Pipe doesn't kill source — if build hangs, waits forever
docker build . 2>&1 | tail -50

# ✅ CORRECT: Timeout terminates hung process
timeout 120 docker build . 2>&1 | tail -50
```

---

## 5. Module Development Patterns

### New Backend Module Checklist
```
modules/{name}/
├── __init__.py          # {Name}Module(Module) - must implement module_dir(), tags
├── service.py           # {Name}Service(ServiceInterface)
├── api/v1.py           # {Name}Api(APIRouterInterface) - auto-provides /health, /versions
├── ws/v1/__init__.py   # {Name}WsRouters(WsRouterBase) - optional
└── tests/
```

**Critical**: API routers extend `APIRouterInterface` (gets health/version endpoints free). WS routers extend `WsRouterBase`.

### WebSocket Router Pattern
```python
# modules/broker/ws/v1/__init__.py
# Use class inheritance for dynamic type resolution
class OrderRouter(WsRouter[OrderSubscriptionRequest, PlacedOrder]):
    pass

class BrokerWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        order_router = OrderRouter(route="orders", tags=["broker"], service=service)
        super().__init__([order_router], service=service)
```

### Frontend Service Pattern
```typescript
// Services use ONLY frontend types, delegate to mappers for conversion
const response = await apiClient.createOrder(mapPreOrder(frontendOrder))
return mapOrder(response)  // Backend → Frontend conversion
```

---

## 6. Testing Patterns

### Backend Test Isolation
```python
# Each module gets isolated test app
@pytest.fixture
def broker_app():
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])
```

### Authentication Mocking
```python
# Mock Google OAuth in tests
@pytest.fixture
def mock_google_oauth(monkeypatch):
    async def mock_parse_id_token(token, claims_options):
        return {"sub": "test_user_id", "email": "test@example.com", "email_verified": True}
    monkeypatch.setattr("authlib.integrations...", mock_parse_id_token)
```

### Frontend: Auto-client Generation
Frontend tests auto-generate clients from backend specs before running. No manual generation needed.

---

## 7. Key File Locations

| Purpose | Location |
|---------|----------|
| Backend models (Pydantic) | `backend/src/trading_api/models/{domain}/` |
| Module implementations | `backend/src/trading_api/modules/{name}/` |
| Provider implementations | `backend/src/trading_api/providers/{name}/` |
| Frontend type mappers | `frontend/src/plugins/mappers.ts` |
| WebSocket adapter | `frontend/src/plugins/wsAdapter.ts` |
| Generated REST clients | `frontend/src/clients_generated/trader-client-{module}_v1/` |
| Generated WS types | `frontend/src/clients_generated/ws-types-{module}_v1/` |
| Test fixtures | `backend/tests/conftest.py`, `frontend/src/test-setup.ts` |

---

## 8. Documentation Navigation

Use [docs/DOCUMENTATION-GUIDE.md](../docs/DOCUMENTATION-GUIDE.md) as your map:

| Task | Primary Docs |
|------|--------------|
| Backend module dev | `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md` |
| WebSocket features | `backend/docs/BACKEND_WEBSOCKETS.md` + `frontend/docs/WEBSOCKET-ARCHITECTURE.md` |
| Authentication | `backend/docs/AUTHENTICATION.md` |
| Provider/capability system | `backend/docs/PROVIDER-SYSTEM.md` |
| Client generation | `backend/docs/SPECS_AND_CLIENT_GEN.md` + `docs/CLIENT-GENERATION.md` |
| Testing strategy | `docs/TESTING.md` + `backend/docs/BACKEND_TESTING.md` |

---

## 9. Agent Leverage

Before complex tasks, consider whether a specialist agent could achieve better results. Apply the `agent-routing` skill for systematic delegation decisions.

### Available Agents

| Agent | Use For | Trigger Keywords |
|-------|---------|------------------|
| `ia-coord` | Create agents/subagents/prompts/skills with enforced boundary separation | "create agent", "create subagent", "create prompt", "create skill", "validate design" |
| `backend-test` | Backend test creation, pytest patterns, coverage analysis | "test", "coverage", "add tests", "backend test" |
| `frontend-test` | Frontend test creation, Vitest patterns, coverage analysis | "frontend test", "component test", "vue test", "vitest" |
| `review` | Code quality, security audit | "review", "check", "audit" |
| `plan` | Multi-step implementation planning | "plan", "how should we" |
| `advisor` | Architecture decisions, design evaluation, technical consultation | "evaluate", "compare", "refactor strategy", "explain", "how does X work", "should I" |
| `implement` | Implementation engineer — freeform coding or plan execution with validation | "implement", "build", "fix", "follow plan", "execute plan" |
| `rca` | Root cause analysis, hypothesis-driven debugging | "debug", "why", "investigate failure" |
| `doc-update` | Documentation update planning | "update docs", "doc drift", "document changes" |
| `type-fix` | Fix type errors systematically | "fix types", "type error", "mypy/pyright fail" |
| `doc-awareness` | Documentation context discovery and extraction (subagent) | Delegated for doc-aware task context, documentation guidance |
| `research` | High-fidelity information gathering with adaptive depth (subagent) | Delegated for context discovery, cross-file synthesis, relevance-filtered research |
| `command` | Large-output command execution, parallel runs, daemon management (subagent) | Delegated for env-aware terminal execution with full output capture and cleanup |
| `verify` | Multi-file verification with pass/fail verdicts (subagent) | Delegated for mid-complexity checks, multi-file validation, and command-based verification with structured verdict reports |
| `playwright` | Browser automation via Playwright MCP (subagent) | Delegated for UI inspection, interaction, debugging, and visual verification with lean result extraction |

### Quick Decision Rules

1. **Creating agents/prompts/skills?** → `ia-coord` agent (enforces three-layer model)
2. **Creating a subagent?** → `ia-coord` agent (uses `templates/subagent-template.md`, enforces SA-1–SA-7)
3. **Need context you don't have?** → `research` subagent first
4. **Multi-file feature?** → `plan` before `implement`
5. **Writing backend tests?** → `backend-test` agent
6. **Writing frontend tests?** → `frontend-test` agent
7. **Large change complete?** → Offer `review` handoff
8. **Architecture question?** → `advisor` agent
9. **Have a plan to execute?** → `implement` agent (plan execution mode)
10. **Debugging complex issue?** → `rca` agent
11. **Documentation needs update?** → `doc-update` (planning) or `/doc-assess` prompt (audit via `doc-assessment` skill)
12. **Type errors failing CI?** → `type-fix` agent
13. **Need documentation context for a task?** → `doc-awareness` subagent
14. **Ambiguous or complex user request?** → Apply `request-evaluation` skill inline, then `mode-interactive` for critical gaps
15. **Large output or parallel commands?** → `command` subagent for isolated terminal execution with full capture
16. **Need multi-file verification with verdicts?** → `verify` subagent for structured pass/fail checks across files and commands
17. **Need browser/UI inspection or interaction?** → `playwright` subagent for isolated browser automation with lean results

