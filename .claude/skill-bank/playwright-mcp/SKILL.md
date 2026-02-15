---
name: playwright-mcp
description: Browser automation via Playwright MCP tools. Load when inspecting UI, debugging frontend, or using extension mode
keywords: [playwright, browser, automation, ui-inspection, mcp, extension-mode, cdp, file-upload, clipboard]
category: testing
disable-model-invocation: true
---

# Playwright MCP Browser Automation

Master browser automation through the Playwright MCP server toolset. This skill teaches the **reconnaissance-then-action** workflow, element reference system, and token-efficient inspection patterns used by the MCP browser tools.

**Core invariant**: Always snapshot before acting — the accessibility tree provides the `ref` values that drive all interactions.

**Runtime mode**: The Playwright MCP server runs in `--extension` mode — it connects to an existing Chrome instance via CDP rather than launching its own browser. This has implications for which tools work and which require workarounds (see Tool Reference below).

---

## Mandatory Loading Directives

These sub-files contain step-by-step templates and detailed reference. Load them based on the task at hand:

| Task Signal | File | Directive |
|-------------|------|-----------|
| Executing any browser automation workflow (inspect, fill, click, navigate, file upload) | [`templates.md`](./templates.md) | **MUST load** before starting the automation sequence |
| Configuring MCP server flags OR troubleshooting server setup OR WSL config | [`config-reference.md`](./config-reference.md) | **MUST load** before writing or modifying config |

**Rule**: When in doubt about whether a sub-file applies, load it. The cost of an unnecessary read is far lower than the cost of missing a critical template or workaround.

---

## When to Use This Skill

- Inspecting a running web application's UI state
- Debugging frontend rendering, layout, or interaction bugs
- Verifying that code changes produce correct visual output
- Filling forms, clicking buttons, or navigating multi-step flows
- Capturing console errors or network requests for diagnosis
- Generating Playwright locators for test authoring
- Uploading files via clipboard injection (extension mode workaround)
- Interacting with external sites via the existing Chrome instance

---

## Extension Mode: Required Config

The MCP server always connects to an existing Chrome instance via CDP. These flags are always required:

| Flag | Why Required |
|------|-------------|
| `--extension` | Connects to existing Chrome via CDP instead of launching a new browser |
| `--allow-unrestricted-file-access` | Without this, file access is restricted to MCP server's cwd (defaults to `C:\Windows\System32` when launched via `cmd.exe` from WSL) |
| `--grant-permissions clipboard-read,clipboard-write` | Without this, Chrome shows a clipboard permission popup that blocks automation (needed for file upload workaround) |

> For full flag reference, WSL config JSON, and setup details, load [`config-reference.md`](./config-reference.md).

---

## Tool Reference

### Inspection Tools (read-only)

| Tool | Purpose | Key Params | Ext Status |
|------|---------|------------|------------|
| `browser_snapshot` | Accessibility tree with `ref` values | `filename?` | Working |
| `browser_take_screenshot` | Visual PNG/JPEG capture | `type`, `fullPage?`, `element?`, `ref?` | Working |
| `browser_console_messages` | JS console output | `level` (error/warning/info/debug) | Working |
| `browser_network_requests` | HTTP request log | `includeStatic?` (default: false) | Working |

### Navigation Tools

| Tool | Purpose | Key Params | Ext Status |
|------|---------|------------|------------|
| `browser_navigate` | Go to URL | `url` | Working |
| `browser_navigate_back` | Browser back button | — | Working |
| `browser_tabs` | Tab management | `action` (list/create/close/select), `index?` | Working |
| `browser_wait_for` | Wait for condition | `time?`, `text?`, `textGone?` | Working |

### Interaction Tools

| Tool | Purpose | Key Params | Ext Status |
|------|---------|------------|------------|
| `browser_click` | Click element | `element?`, `ref`, `doubleClick?`, `button?` | Working |
| `browser_type` | Type text into field | `element?`, `ref`, `text`, `submit?`, `slowly?` | Working |
| `browser_fill_form` | Fill multiple fields | `fields` (array) | Working |
| `browser_select_option` | Select dropdown value | `element?`, `ref`, `values` | Working |
| `browser_hover` | Hover over element | `element?`, `ref` | Working |
| `browser_press_key` | Press keyboard key | `key` (e.g., "Enter", "ArrowDown") | Working |
| `browser_drag` | Drag and drop | `startElement`, `startRef`, `endElement`, `endRef` | Working |
| `browser_handle_dialog` | Accept/dismiss dialog | `accept`, `promptText?` | Working |
| `browser_file_upload` | Upload file(s) | `paths` (array of absolute paths) | **BROKEN** — use clipboard injection template |

### Advanced Tools

| Tool | Purpose | Key Params | Ext Status |
|------|---------|------------|------------|
| `browser_evaluate` | Run JS in page context | `function`, `element?`, `ref?` | **KEY** — workaround tool for clipboard injection |
| `browser_run_code` | Run Playwright API code | `code` (async page function) | **BROKEN** with `setInputFiles` (times out) |
| `browser_generate_locator` | Generate test locator | `element?`, `ref` | Working (needs `--caps=testing`) |
| `browser_resize` | Change viewport size | `width`, `height` | Working |
| `browser_pdf_save` | Save page as PDF | `filename?` | Working (needs `--caps=pdf`) |

### Extension Mode: Tools That Fail

These are CDP-level restrictions, not bugs. They fail silently or with cryptic errors:

| Tool / API | Failure Mode | Root Cause |
|-----------|--------------|------------|
| `browser_file_upload` | "no related modal state" error | Extension mode does not intercept native OS file dialogs |
| `setInputFiles` via `browser_run_code` | Times out (locator resolves but action hangs) | `DOM.setFileInputFiles` CDP command is restricted in extension mode |
| `page.waitForEvent('filechooser')` | Times out | Extension mode does not emit filechooser events for native dialogs |
| `browserContext.newCDPSession(page)` | "Not allowed" error | `Target.attachToBrowserTarget` is not permitted in extension mode |
| `fetch('http://localhost/...')` from HTTPS page | CORS / mixed-content block | Browser enforces mixed-content policy; cannot fetch HTTP from an HTTPS page context |

> **File upload workaround**: Use the base64-via-clipboard injection template in [`templates.md`](./templates.md). This is the only confirmed working pattern for file uploads.

---

## Core Concept: The Element Reference System

Every interaction tool requires a `ref` — a machine-parseable element reference from `browser_snapshot`.

```
browser_snapshot() → returns accessibility tree:

  - heading "Dashboard" [ref=e1]
  - navigation "Main Menu" [ref=e2]
    - link "Orders" [ref=e3]
    - link "Settings" [ref=e4]
  - button "New Order" [ref=e5]
  - textbox "Search" [ref=e6]

browser_click(element="New Order button", ref="e5")  → clicks the button
browser_type(element="Search field", ref="e6", text="AAPL") → types into field
```

**Dual parameter pattern**:
- `element` (optional): Human-readable description — shown for user permission
- `ref` (required): Exact reference from snapshot — ensures precise targeting

---

## Methodology

### Phase 1: Reconnaissance

**Goal**: Understand the current page state before any interaction.

```
1. browser_navigate(url)           → load the target page
2. browser_wait_for(text="...")    → wait for key content to render
3. browser_snapshot()              → get accessibility tree with refs
4. browser_console_messages(level="error")  → check for JS errors
```

**Decision: Snapshot vs Screenshot**

| Need | Use | Why |
|------|-----|-----|
| Identify elements to interact with | `browser_snapshot` | Provides `ref` values; structured text; low token cost |
| Verify visual layout/styling | `browser_take_screenshot` | Visual verification; catches CSS issues invisible in a11y tree |
| Debug complex rendering | Both | Snapshot for structure + screenshot for visual confirmation |

### Phase 2: Interaction

**Goal**: Perform actions using `ref` values from Phase 1.

```
1. Parse snapshot → identify target element refs
2. browser_click(element="Submit button", ref="e12")
3. browser_wait_for(text="Success")     → wait for result
4. browser_snapshot()                    → verify new state
```

**Form filling pattern:**
```
browser_fill_form(fields=[
  { element: "Username", ref: "e3", value: "testuser" },
  { element: "Password", ref: "e4", value: "pass123" }
])
browser_click(element="Login button", ref="e5")
browser_wait_for(text="Dashboard")
```

### Phase 3: Verification

**Goal**: Confirm the result of interactions.

```
1. browser_snapshot()                → check updated a11y tree
2. browser_take_screenshot(fullPage=true)  → visual confirmation
3. browser_console_messages(level="error") → check for new errors
4. browser_network_requests()        → verify API calls succeeded
```

### Phase 4: Iteration

**Goal**: Repeat the cycle for multi-step workflows.

```
Reconnaissance → Interaction → Verification → Reconnaissance → ...

Each cycle:
  - Always re-snapshot after actions (refs may change after DOM updates)
  - Check console errors between steps
  - Screenshot before and after for comparison
```

> **IMPORTANT**: For step-by-step workflow templates (page inspection, form submission, debugging, navigation, responsive checks, file upload), you **MUST** also load [`templates.md`](./templates.md).

---

## Extension Mode Decision Tree

```
Need file upload?
  ├─ Is <input type="file"> visible in snapshot?
  │   ├─ YES → Use clipboard injection template (templates.md)
  │   └─ NO → Click trigger button → re-snapshot → find input → then inject
  │
Need to run code against the page?
  ├─ Read-only JS (query DOM, get styles) → browser_evaluate (WORKS)
  └─ Playwright API (setInputFiles, waitForEvent) → BROKEN — find alternative approach
```

---

## File Management

Screenshots and other captured artifacts (traces, PDFs) MUST be saved to a **temporary directory**, never to the workspace root or any project directory.

**Temp directory**: `/tmp/playwright-captures/`

**Rules:**
1. **Create before saving**: `mkdir -p /tmp/playwright-captures/` before the first screenshot
2. **Save all artifacts there**: Pass `/tmp/playwright-captures/{descriptive-name}.png` as the filename
3. **Return temp paths to callers**: The full `/tmp/` path is sufficient for callers to reference or display the file — no need to copy into the workspace
4. **No workspace pollution**: Never save screenshots, traces, or PDFs into the project tree — they are ephemeral verification artifacts, not source-controlled assets
5. **Auto-cleanup**: Files in `/tmp/` are cleaned on system restart; no manual cleanup needed

**Screenshot naming convention**: Use descriptive kebab-case names that identify the captured state:
```
/tmp/playwright-captures/order-form-filled.png
/tmp/playwright-captures/dashboard-loaded.png
/tmp/playwright-captures/chart-panel-expanded.png
```

---

## Anti-Patterns

- **Saving screenshots to workspace** — Screenshots are ephemeral artifacts, not project files. Always use `/tmp/playwright-captures/`
- **Acting without snapshot** — Never click/type without a fresh `browser_snapshot`; you won't have valid `ref` values
- **Screenshot for element discovery** — Screenshots don't provide `ref` values; use `browser_snapshot` instead
- **Stale refs after DOM change** — After any interaction that changes the page, re-run `browser_snapshot` to get fresh refs
- **Ignoring console errors** — Always check `browser_console_messages(level="error")` during debugging
- **Full-page screenshot on complex pages** — Use `browser_snapshot` for structure; reserve screenshots for visual verification
- **Guessing selectors** — Use `browser_snapshot` or `browser_generate_locator` to discover correct selectors
- **Using `browser_file_upload` for file uploads** — It fails in extension mode ("no related modal state"). Use the clipboard injection template in [`templates.md`](./templates.md)
- **Using `setInputFiles` via `browser_run_code`** — It silently hangs (locator resolves but action never completes). Use the clipboard injection template instead
- **Using `certutil -encode` for base64** — It adds certificate headers that break `atob()`. Use `base64 -w0` from WSL
- **Editing `~/.claude.json` directly** — Race conditions with Claude Code's config reads/writes. Use `claude mcp add/remove` CLI instead
- **Skipping the trigger click before file injection** — Many sites create `<input type="file">` dynamically. Always: snapshot -> click trigger -> re-snapshot -> find input -> inject
- **Fetching HTTP from HTTPS page context** — Mixed-content policy blocks this. Use a same-origin approach or browser-side workaround

**Do instead:**
- **Reconnaissance-then-action** — Always: navigate -> wait -> snapshot -> identify -> act -> verify
- **Snapshot + screenshot combo** — Snapshot for structure and refs, screenshot for visual confirmation
- **Re-snapshot after mutations** — Any DOM change invalidates previous `ref` values
- **Clipboard injection for file uploads** — The only confirmed working pattern in extension mode

---

## Sub-Files

| File | Content | Lines |
|------|---------|-------|
| [`templates.md`](./templates.md) | Step-by-step workflow templates (file upload via clipboard injection, page inspection, form submit, debug UI, multi-page navigation, responsive design) | ~175 |
| [`config-reference.md`](./config-reference.md) | MCP server flags, WSL extension mode config JSON, flag explanations | ~70 |
