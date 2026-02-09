---
name: learn-api
description: Evaluate external APIs for usefulness and create MCP server wrappers to make them persistent workspace tools. Trigger when discovering a useful REST/GraphQL API during research, when the user asks to interact with an external service, or when an API would benefit from permanent access rather than one-off HTTP calls. Use to assess API value, locate specs (OpenAPI/Swagger), generate MCP servers, and configure VS Code integration.
---

# Learn API — Turn Useful APIs into Permanent MCP Tools

Evaluate external APIs encountered during work and, when they provide recurring value, wrap them as MCP servers so they become persistent workspace tools. Covers API assessment, spec discovery, server generation with FastMCP, route filtering, custom tool augmentation, path encoding pitfalls, VS Code stdio configuration, and common errors with solutions.

---

## When to Use This Skill

- An external API is discovered during research or user request that would be useful to have permanently
- The user asks to interact with / connect to an external service (e.g., "search NPM", "check GitHub", "query Jira")
- An API was useful for a task and should be "learned" for future sessions
- Wrapping a REST API as an MCP server for workspace-wide access
- Troubleshooting an existing MCP server wrapping an external API
- Deciding whether an API is worth wrapping vs. using ad-hoc HTTP calls

---

## Methodology

### Phase 0: Assess API Value

Before building anything, evaluate whether the API is worth wrapping as a persistent MCP tool.

**Assessment criteria:**

| Factor | Worth Wrapping | Not Worth Wrapping |
|--------|---------------|-------------------|
| **Usage frequency** | Recurring across tasks/sessions | One-off lookup |
| **Scope** | Multiple useful endpoints | Single narrow query |
| **Spec availability** | OpenAPI/Swagger spec exists | No spec, undocumented |
| **Auth complexity** | Public or simple API key | Complex OAuth flows requiring user interaction |
| **Data freshness** | Live data matters (registries, status) | Static/archival data |

**Decision:**
- 3+ factors favor wrapping → **proceed** — create MCP server
- 1-2 factors favor wrapping → **suggest** to user, let them decide
- 0 factors → **skip** — use ad-hoc HTTP calls instead

**When proceeding**, present to user: "This API ({name}) would be useful as a permanent workspace tool. Want me to create an MCP server for it?"

### Phase 1: Choose Your Approach

| Scenario | Approach | Effort |
|----------|----------|--------|
| REST API with an OpenAPI spec available | `FastMCP.from_openapi()` auto-generation | Low — minutes |
| API without spec, or highly custom tool logic | Hand-crafted `@mcp.tool()` decorators | Medium |
| Hybrid: spec-based + custom overrides | `from_openapi()` + `@server.tool()` additions | Low-Medium |
| Existing FastAPI application | `FastMCP.from_fastapi(app)` conversion | Low |

**Decision rule**: If the API has an OpenAPI spec → always start with `from_openapi()`. Add custom tools only where auto-generation falls short (path encoding, response transformation, multi-step orchestration).

### Phase 2: Set Up the Server

**Install dependencies:**
```bash
pip install fastmcp httpx
# Add pyyaml if spec is YAML format
pip install pyyaml
```

**Minimal hand-crafted server:**
```python
from fastmcp import FastMCP

mcp = FastMCP("My Server")

@mcp.tool()
async def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```

**OpenAPI auto-generated server:**
```python
from __future__ import annotations
import httpx
import yaml  # or json
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

def _load_spec() -> dict:
    """Fetch and parse the OpenAPI spec."""
    resp = httpx.get("https://api.example.com/openapi.yaml", timeout=30.0)
    resp.raise_for_status()
    return yaml.safe_load(resp.text)  # or resp.json() for JSON specs

def _create_client() -> httpx.AsyncClient:
    """Create the shared async HTTP client."""
    return httpx.AsyncClient(base_url="https://api.example.com", timeout=30.0)

def create_server() -> FastMCP:
    spec = _load_spec()
    client = _create_client()

    server = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="My API Server",
        route_maps=[
            # All GET endpoints → tools (default behavior)
            RouteMap(methods=["GET"], mcp_type=MCPType.TOOL),
        ],
    )
    return server

# Module-level export — REQUIRED for stdio transport and FastMCP Cloud
mcp = create_server()

if __name__ == "__main__":
    mcp.run()
```

### Phase 3: Filter Routes with RouteMap

RouteMap controls which OpenAPI endpoints become MCP tools, resources, or are excluded. Patterns are evaluated in order — first match wins.

**Route filtering patterns:**

```python
route_maps=[
    # 1. Exclude auth/admin endpoints (security)
    RouteMap(pattern=r".*/auth/.*", mcp_type=MCPType.EXCLUDE),
    RouteMap(pattern=r".*/admin/.*", mcp_type=MCPType.EXCLUDE),

    # 2. Exclude write operations (read-only server)
    RouteMap(methods=["PUT", "POST", "DELETE", "PATCH"], mcp_type=MCPType.EXCLUDE),

    # 3. Exclude duplicate API versions
    RouteMap(pattern=r"/v0\.1/.*", mcp_type=MCPType.EXCLUDE),

    # 4. Exclude endpoints you'll replace with custom tools
    RouteMap(pattern=r".*/items/\{itemId\}.*", mcp_type=MCPType.EXCLUDE),

    # 5. Catch-all: remaining GET → tools
    RouteMap(methods=["GET"], mcp_type=MCPType.TOOL),
]
```

**MCPType options:**
| Type | Effect |
|------|--------|
| `MCPType.TOOL` | Expose as callable tool |
| `MCPType.RESOURCE` | Expose as readable resource |
| `MCPType.RESOURCE_TEMPLATE` | Expose as parameterized resource template |
| `MCPType.EXCLUDE` | Skip entirely |

### Phase 4: Add Custom Tools (Hybrid Pattern)

After `from_openapi()`, you can add custom `@server.tool()` decorators to the same server. This is essential when:
- Path parameters contain special characters (e.g., `/` in identifiers)
- You need response transformation or aggregation
- Multi-step orchestration across endpoints

```python
server = FastMCP.from_openapi(openapi_spec=spec, client=client, name="API")

# Add custom tool alongside auto-generated ones
@server.tool()
async def get_item_details(item_name: str) -> dict:
    """Get details for an item whose name may contain slashes.

    Args:
        item_name: Full item name (e.g. 'com.example/my-item')
    """
    from urllib.parse import quote
    encoded = quote(item_name, safe="")
    resp = await client.get(f"/v1/items/{encoded}")
    resp.raise_for_status()
    return resp.json()
```

### Phase 5: Configure VS Code

Add a server entry to the workspace MCP configuration:

```jsonc
// .vscode/mcp.json
{
    "servers": {
        "my-server": {
            "type": "stdio",
            "command": "python3",
            "args": ["${workspaceFolder}/mcp-servers/my-server/server.py"]
        }
    }
}
```

**Verify the server works:**
```bash
# Quick smoke test — should print tool list to stderr and exit
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | python3 server.py
```

### Phase 6: Test and Iterate

1. **Start the server** via VS Code MCP panel or terminal
2. **List tools** — verify expected tools appear with correct names and descriptions
3. **Call each tool** — test with representative inputs
4. **Check edge cases** — special characters in parameters, empty results, error responses

---

## Key Patterns

### Path Parameter Encoding (Critical)

**Problem**: REST APIs with path parameters containing `/` (e.g., reverse-DNS identifiers like `io.github.user/my-server`) break when FastMCP auto-generates tool calls — the slash is treated as a path separator.

**Solution**: Exclude these endpoints from auto-generation and create custom tools with explicit URL encoding:

```python
from urllib.parse import quote

# Exclude the auto-generated endpoint
RouteMap(pattern=r".*/servers/\{serverName\}.*", mcp_type=MCPType.EXCLUDE),

# Replace with custom tool
@server.tool()
async def get_server(server_name: str) -> dict:
    """Get server details. Name uses reverse-DNS format (e.g. 'io.github.user/repo')."""
    encoded = quote(server_name, safe="")  # safe="" encodes ALL special chars including /
    resp = await client.get(f"/v0/servers/{encoded}")
    resp.raise_for_status()
    return resp.json()
```

### Server Lifespans (Resource Management)

For servers that hold connections or caches, use the lifespan pattern:

```python
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class ServerContext:
    client: httpx.AsyncClient

@asynccontextmanager
async def server_lifespan(server: FastMCP):
    client = httpx.AsyncClient(base_url="https://api.example.com", timeout=30.0)
    try:
        yield ServerContext(client=client)
    finally:
        await client.aclose()

mcp = FastMCP("Server", lifespan=server_lifespan)
```

### Module-Level Export

The server object **must** be assigned at module level for stdio transport to work:

```python
# ✅ CORRECT
def create_server() -> FastMCP:
    ...
    return server

mcp = create_server()  # Module-level assignment

# ❌ WRONG — server only exists inside function scope
def create_server():
    server = FastMCP("Server")
    server.run()  # Won't be found by stdio transport
```

---

## Error Catalog

### Startup & Import Errors

| Error | Cause | Solution |
|-------|-------|---------|
| `ModuleNotFoundError: No module named 'fastmcp'` | Not installed in active Python environment | `pip install fastmcp` in the correct venv |
| `ImportError: cannot import name 'MCPType'` | Wrong import path | `from fastmcp.server.openapi import MCPType, RouteMap` |
| `RuntimeError: No server object found at module level` | Server created inside function, not exported | Assign to module-level variable: `mcp = create_server()` |

### OpenAPI Integration Errors

| Error | Cause | Solution |
|-------|-------|---------|
| `httpx.HTTPStatusError: 404` on spec fetch | Wrong spec URL or spec moved | Verify URL; check if spec is at `/openapi.json`, `/openapi.yaml`, `/swagger.json`, or `/api-docs` |
| `yaml.YAMLError` on spec parse | Spec is JSON but parsed as YAML, or vice versa | Use `resp.json()` for JSON specs, `yaml.safe_load(resp.text)` for YAML |
| No tools generated from spec | All routes filtered by RouteMap exclusions | Review RouteMap order — first match wins; ensure at least one catch-all `MCPType.TOOL` |
| Duplicate tool names | Multiple API versions expose same operation names | Exclude duplicate versions: `RouteMap(pattern=r"/v0\.1/.*", mcp_type=MCPType.EXCLUDE)` |

### Runtime Errors

| Error | Cause | Solution |
|-------|-------|---------|
| `httpx.HTTPStatusError: 404` on tool call | Path parameter not URL-encoded | Use `quote(param, safe="")` for params with special characters |
| `httpx.ReadTimeout` | API response too slow | Increase timeout: `httpx.AsyncClient(timeout=60.0)` |
| `TypeError: 'coroutine' object is not subscriptable` | Missing `await` on async call | Add `await`: `resp = await client.get(...)` |
| Tool runs but returns empty/null | API returns 204 No Content or empty body | Check `resp.status_code` before `resp.json()` |

### VS Code Configuration Errors

| Error | Cause | Solution |
|-------|-------|---------|
| Server doesn't appear in MCP panel | Invalid JSON in `mcp.json` | Validate JSON syntax (watch for trailing commas in JSONC) |
| `python3: command not found` | Wrong Python command for OS | Use `python` on Windows, `python3` on macOS/Linux |
| Server starts then immediately exits | Crash during spec fetch (network/timeout) | Test server standalone: `python3 server.py` and check stderr |

---

## Anti-Patterns

- ❌ **Auto-generate everything** — Blindly using `from_openapi()` without RouteMap filtering exposes write/auth endpoints as tools. Always exclude dangerous operations.
- ❌ **Ignoring path encoding** — Assuming FastMCP handles special characters in path parameters. It doesn't — `/` in path params silently breaks routing.
- ❌ **Hardcoding base URLs** — Embedding API URLs as string literals. Use environment variables or config for deployability.
- ❌ **No timeout on HTTP client** — Letting `httpx.AsyncClient` use default (5s) timeout. Set explicit `timeout=30.0` or higher.
- ❌ **Creating client per tool call** — Instantiating `httpx.AsyncClient` inside each tool function. Create once and share via lifespan or module scope.
- ✅ **Hybrid approach** — Use `from_openapi()` for the bulk, add `@server.tool()` for edge cases requiring custom logic.
- ✅ **Read-only by default** — Exclude write methods unless explicitly needed. MCP tools are invoked by LLMs — keep the blast radius small.
- ✅ **Descriptive docstrings** — LLMs read tool docstrings to decide when/how to call them. Invest in clear `Args:` sections.

---

## Templates

### Complete OpenAPI-to-MCP Server

```python
"""
{Service Name} MCP Server — wraps {API Name} as MCP tools via FastMCP.
"""
from __future__ import annotations
from urllib.parse import quote

import httpx
import yaml
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

BASE_URL = "https://api.example.com"
SPEC_URL = f"{BASE_URL}/openapi.yaml"


def _load_spec() -> dict:
    resp = httpx.get(SPEC_URL, timeout=30.0)
    resp.raise_for_status()
    return yaml.safe_load(resp.text)


def _create_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)


def create_server() -> FastMCP:
    spec = _load_spec()
    client = _create_client()

    server = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="{Service Name}",
        route_maps=[
            # Exclude auth and write endpoints
            RouteMap(pattern=r".*/auth/.*", mcp_type=MCPType.EXCLUDE),
            RouteMap(methods=["PUT", "POST", "DELETE", "PATCH"], mcp_type=MCPType.EXCLUDE),
            # Exclude endpoints needing custom handling
            RouteMap(pattern=r".*/items/\{itemId\}.*", mcp_type=MCPType.EXCLUDE),
            # All remaining GET → tools
            RouteMap(methods=["GET"], mcp_type=MCPType.TOOL),
        ],
    )

    # Custom tools for endpoints needing special handling
    @server.tool()
    async def get_item(item_id: str) -> dict:
        """Get item by ID. IDs may contain slashes (e.g. 'org/name').

        Args:
            item_id: The item identifier, URL-encoded automatically.
        """
        encoded = quote(item_id, safe="")
        resp = await client.get(f"/v1/items/{encoded}")
        resp.raise_for_status()
        return resp.json()

    return server


mcp = create_server()

if __name__ == "__main__":
    mcp.run()
```

### VS Code MCP Configuration Entry

```jsonc
{
    "servers": {
        "{server-name}": {
            "type": "stdio",
            "command": "python3",
            "args": ["${workspaceFolder}/mcp-servers/{server-name}/server.py"]
        }
    }
}
```

---

## Quick Reference

| Task | Command / Code |
|------|---------------|
| Install FastMCP | `pip install fastmcp` |
| Install with YAML support | `pip install fastmcp httpx pyyaml` |
| Run server standalone | `python3 server.py` |
| Run with inspector | `fastmcp dev server.py` |
| Install to Claude Desktop | `fastmcp install server.py` |
| Debug logging | `FASTMCP_LOG_LEVEL=DEBUG python3 server.py` |

| FastMCP Version | Key Feature |
|-----------------|-------------|
| v2.14.0 | Background tasks (`task=True`), breaking changes (see docs) |
| v2.14.1 | Sampling with tools, Python 3.13 support |
| v2.14.2 | MCP SDK pinned <2.x, OpenAPI 3.1 support |
| v3.0.0 (beta) | Provider architecture, transforms, component versioning |
