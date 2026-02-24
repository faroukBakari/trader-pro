# Learn API — Templates

## Complete OpenAPI-to-MCP Server

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

## VS Code MCP Configuration Entry

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
