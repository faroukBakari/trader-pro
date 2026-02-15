# Playwright MCP Configuration Reference

Key MCP server flags that affect tool behavior. Use this reference when configuring the Playwright MCP server or troubleshooting setup issues.

---

## Required Flags (Extension Mode)

These flags are **always required** — the server runs in extension mode connecting to an existing Chrome via CDP:

| Flag | Why Required |
|------|-------------|
| `--extension` | Connects to existing Chrome via CDP instead of launching a new browser |
| `--allow-unrestricted-file-access` | Without this, file access is restricted to MCP server's cwd (defaults to `C:\Windows\System32` when launched via `cmd.exe` from WSL) |
| `--grant-permissions clipboard-read,clipboard-write` | Without this, Chrome shows a clipboard permission popup that blocks automation (needed for file upload workaround) |

---

## All Server Flags

| Flag | Effect | Default |
|------|--------|---------|
| `--headed` | Show visible browser window | headless |
| `--console-level` | Filter console capture level | error |
| `--save-trace` | Record Playwright traces | off |
| `--save-video=WxH` | Record session video | off |
| `--caps=testing` | Enable test assertion + locator tools | off |
| `--caps=vision` | Enable coordinate-based mouse tools | off |
| `--caps=pdf` | Enable PDF generation | off |
| `--storage-state=file` | Persist auth cookies between sessions | none |
| `--test-id-attribute` | Custom test ID attribute | data-testid |
| `--timeout-action` | Action timeout (ms) | 5000 |
| `--timeout-navigation` | Navigation timeout (ms) | 60000 |
| `--extension` | Connect to existing Chrome via CDP (extension mode) | off |
| `--allow-unrestricted-file-access` | Remove cwd restriction on file access | off |
| `--grant-permissions` | Pre-grant browser permissions (comma-separated) | none |

---

## Extension Mode Config (WSL)

When running Playwright MCP in `--extension` mode from WSL, the `cmd.exe` launch requires a `cd /d` prefix to avoid UNC path errors. Recommended config:

```json
{
  "type": "stdio",
  "command": "cmd.exe",
  "args": [
    "/c",
    "cd /d C:\\temp && node C:\\temp\\pw-mcp\\node_modules\\@playwright\\mcp\\cli.js --extension --console-level=info --save-trace --allow-unrestricted-file-access --grant-permissions clipboard-read,clipboard-write"
  ]
}
```

---

## Extension Mode Flag Explanations

| Flag | Problem Solved |
|------|---------------|
| `--allow-unrestricted-file-access` | Without this, file access is restricted to MCP server's cwd (defaults to `C:\Windows\System32` when launched via `cmd.exe` from WSL) |
| `--grant-permissions clipboard-read,clipboard-write` | Without this, Chrome shows a clipboard permission popup that blocks automation |
| `cd /d C:\temp &&` prefix in args | Without this, `cmd.exe` launched from WSL gets a UNC path (`\\wsl.localhost\...`) as cwd, which causes an error |

---

## Config Anti-Pattern

- **Editing `~/.claude.json` directly** — Claude Code continuously reads/rewrites its own config file, causing "File has been modified since read" race conditions. Use `claude mcp add/remove` CLI instead
