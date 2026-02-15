---
name: agentic-resources
description: Curated directory of online resources for discovering prompts, agents, skills, and MCP tools. Use when searching for reusable AI coding assets, evaluating skill/tool marketplaces, installing community skills, finding MCP servers, or recommending resources to users. Covers official vendor sources, community marketplaces, and CLI tooling with assessment criteria.
---

# Agentic Resources — Discover Prompts, Agents, Skills & MCP Tools

Structured reference of the best online sources for finding reusable AI coding assets across the agentic ecosystem. Covers official vendor resources, community-maintained marketplaces, CLI tools, and MCP server registries — with assessment criteria and usage patterns.

---

## When to Use This Skill

- Searching for existing skills, agents, or MCP tools before building custom ones
- Evaluating which marketplace or registry to query for a specific need
- Installing community skills into the workspace
- Recommending external resources to users exploring the agentic ecosystem
- Deciding between multiple skill/tool sources for the same capability
- Onboarding new team members to the agentic tooling landscape

---

## Resource Directory

### 1. MCP Tool Registries

| Resource | Type | Access | Description |
|----------|------|--------|-------------|
| **MCP Official Registry** | Official | API: `registry.modelcontextprotocol.io` | Canonical registry by Anthropic. 1000+ servers. Searchable via API. Reverse-DNS naming (`io.github.*/...`). |
| **Smithery** | Community | Web: `smithery.ai` | Hosted MCP server marketplace. Servers run remotely via `server.smithery.ai` — zero local install. |
| **mcp.so** | Community | Web: `mcp.so` | Aggregating directory with categories, search, and config snippets. No public API. |
| **Glama MCP Directory** | Community | Web: `glama.ai/mcp/servers` | Searchable catalog with install instructions for Claude Desktop, VS Code, etc. |
| **Awesome MCP Servers** | Community | GitHub: `punkpeye/awesome-mcp-servers` | Curated awesome-list. Categorized (databases, dev tools, web, etc.). |

**MCP registry MCP servers** (search registries from within agents):

| Server | Transport | Install |
|--------|-----------|---------|
| `io.github.formulahendry/mcp-server-mcp-registry` | stdio (npm) | `npx mcp-server-mcp-registry` |
| `io.github.wei/mcp-registry-mcp-server` | stdio (npm) | `npx mcp-registry-mcp-server` |
| `ai.shawndurrani/mcp-registry` | SSE (remote) | URL: `https://mcp-registry.shawndurrani.ai/sse` |

### 2. Skills Marketplaces

| Resource | Type | Size | Stars | Description |
|----------|------|------|-------|-------------|
| **SkillsMP** | Community | 375+ MCP skills, 130+ prompt skills | — | Largest marketplace. Search by keyword, sort by stars. Supports Claude Code, Copilot, Cursor, Roo, OpenCode. |
| **davila7/claude-code-templates** | Community | **634 skills** | 19.7k | Largest single collection. Agents, prompt engineering, LLM frameworks, memory systems, tool design. |
| **sickn33/antigravity-awesome-skills** | Community | Agent orchestration | 7.8k | Agent improvement and evaluation skills. |
| **NeoLabHQ/context-engineering-kit** | Community | Context engineering | 401 | Prompt engineering, agent evaluation, context patterns. |
| **openclaw/skills** | Community | Multi-domain | 723 | Community-contributed. Prompt engineering, security, various domains. |
| **mrgoonie/claudekit-skills** | Community | MCP management | 1.6k | MCP management + utility skills. |

**Top individual skills by stars:**

| Skill | Author | Stars | Purpose |
|-------|--------|-------|---------|
| `senior-prompt-engineer` | davila7 | 19.7k | Prompt patterns, LLM optimization, agent design |
| `prompt-engineering` | davila7 | 19.7k | Prompting strategies, debugging agent behavior |
| `fastmcp-client-cli` | jlowin | 22.7k | Query and invoke tools on MCP servers |
| `create-mcp-server` | RooCodeInc | 22.1k | Create MCP servers from scratch |
| `copilot-sdk` | github | 20.5k | Build agentic apps with GitHub Copilot SDK |
| `openai-knowledge` | openai | 18.8k | OpenAI API docs, Responses API, MCP integration |

### 3. Prompt Libraries

| Resource | Type | URL | Description |
|----------|------|-----|-------------|
| **Anthropic Prompt Library** | Official | `docs.anthropic.com/en/prompt-library` | Curated prompts for various tasks. |
| **Anthropic Prompt Engineering Guide** | Official | `docs.anthropic.com/en/docs/build-with-claude/prompt-engineering` | Claude-specific prompting techniques. |
| **OpenAI Prompt Engineering** | Official | `platform.openai.com/docs/guides/prompt-engineering` | GPT-family prompt best practices. |
| **Google AI Prompting Guide** | Official | `ai.google.dev/gemini-api/docs/prompting-intro` | Gemini prompting strategies. |
| **LangSmith Hub** | Community | `smith.langchain.com/hub` | Community-shared prompt templates for LangChain. |

### 4. Agent Frameworks & Collections

| Resource | Type | URL | Description |
|----------|------|-----|-------------|
| **VS Code Agent Mode** | Official | `.github/agents/*.agent.md` | Native agent definitions with YAML frontmatter + markdown. |
| **GitHub Copilot Extensions** | Official | `github.com/marketplace?type=apps&copilot_app=true` | Copilot-compatible extensions (agents-as-apps). |
| **Claude Code** | Official | `docs.anthropic.com/en/docs/claude-code` | CLI agent with `.claude/` skills/commands system. |
| **Cursor Rules** | Community | `cursor.directory` | Community-shared `.cursorrules` files by framework/language. |
| **RooCode** | Community | `github.com/RooCodeInc/Roo-Code` (22.1k stars) | VS Code agent with built-in skill system. |
| **OpenAI Agents SDK** | Official | `github.com/openai/openai-agents-python` (18.8k stars) | Python multi-agent orchestration + MCP integration. |

### 5. CLI Tools

| Tool | Command | Description |
|------|---------|-------------|
| **skills CLI** (Vercel) | `npx skills` | Install, search, update agent skills. Backend: `skills.sh`. |
| | `npx skills find [query]` | Search skills across registries. |
| | `npx skills add <owner/repo>` | Install skills from GitHub repos. |
| | `npx skills list` | List installed skills. |
| | `npx skills check` / `update` | Check for and apply updates. |
| **FastMCP CLI** | `fastmcp list <server>` | Query tools available on an MCP server. |
| | `fastmcp call <server> <tool>` | Invoke a tool on an MCP server. |

### 6. Curated Aggregators

| Resource | Type | URL |
|----------|------|-----|
| **awesome-mcp-servers** | Community | `github.com/punkpeye/awesome-mcp-servers` |
| **awesome-claude-code** | Community | `github.com/anthropics/awesome-claude-code` |
| **context-engineering-kit** | Community | `github.com/NeoLabHQ/context-engineering-kit` |

---

## Methodology

### Phase 1: Source Selection

Given a search need, pick the right source:

| Looking For | Primary Source | Secondary Source | CLI Shortcut |
|-------------|---------------|-----------------|--------------|
| MCP server to wrap an API | MCP Official Registry | mcp.so, Smithery | `mcp-registry` MCP server |
| Reusable coding skill | SkillsMP marketplace | davila7/claude-code-templates | `npx skills find <query>` |
| Prompt template | Anthropic Prompt Library | SkillsMP (`prompt-engineering`) | — |
| Agent definition reference | cursor.directory | VS Code agent mode docs | — |
| Claude-specific skill | davila7/claude-code-templates | mrgoonie/claudekit-skills | `npx skills add davila7/claude-code-templates` |

### Phase 2: Evaluate Before Installing

Not every skill or tool is worth adding. Apply assessment criteria:

| Factor | Install | Skip |
|--------|---------|------|
| **Relevance** | Directly matches a recurring task | Tangentially related |
| **Quality** | High stars, active maintenance, clear docs | No stars, abandoned, unclear |
| **Overlap** | No existing skill covers this | Already covered by workspace skills |
| **Portability** | Agent-agnostic, no hard dependencies | Tied to specific agent framework |
| **Size** | Focused, <200 lines | Bloated, kitchen-sink approach |

### Phase 3: Install and Verify

**Skills from GitHub repos:**
```bash
npx skills add <owner/repo>           # Interactive — pick skills to install
npx skills add <owner/repo> -y        # Auto-accept all
npx skills add <owner/repo> -g        # Install globally (user-level)
```

**MCP servers:**
```jsonc
// .vscode/mcp.json — add stdio servers
{
  "servers": {
    "<name>": {
      "type": "stdio",
      "command": "npx",
      "args": ["<package-name>"]
    }
  }
}

// Remote servers (no install)
{
  "servers": {
    "<name>": {
      "type": "http",        // VS Code uses "http" for streamable-http
      "url": "<server-url>"
    }
  }
}
```

**Verify after install:**
- Skills: check they appear in `.github/skills/` or agent's skill references
- MCP servers: VS Code Output → MCP panel → confirm "Running" state

---

## Known API Endpoints

Working APIs discovered during research that can be queried directly:

| API | Endpoint | Returns |
|-----|----------|---------|
| **skills.sh** | `GET https://skills.sh/api/search?q={query}` | `{ skills: [{ id, skillId, name, installs, source }], count }` |
| **MCP Registry** | `GET https://registry.modelcontextprotocol.io/v0/servers?search={query}&limit=N` | Server list with packages, transports, metadata |
| **SkillsMP** | Via `skillsmp-mcp-server` MCP tools | Search, AI search, get content, install, list repo skills |

---

## Anti-Patterns

- **Installing everything** — Skills bloat context. Install only what you'll use regularly.
- **Ignoring overlap** — Check workspace skills before adding external ones. Duplicates waste context budget.
- **Trusting star count alone** — High stars often reflect the repo's popularity, not the individual skill's quality. Read the actual SKILL.md.
- **Using `streamable-http` in VS Code config** — VS Code expects `"type": "http"`, not `"streamable-http"`. The registry uses different transport labels than VS Code's config schema.
- **Assuming remote MCP servers are reliable** — Community-hosted remote servers go down. Prefer stdio (local) for critical tools.

---

## Output Format

When recommending resources to a user:

```markdown
### Recommended Resources for {task}

| Resource | Why | Install |
|----------|-----|---------|
| {name} | {relevance to task} | {install command or URL} |
```
