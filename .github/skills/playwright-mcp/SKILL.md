---
name: playwright-mcp
description: Browser automation via Playwright MCP tools. Covers navigation, inspection, interaction, debugging, and verification workflows. Use when inspecting UI, debugging frontend issues, verifying visual output, or interacting with a running web app through MCP browser tools.
---

# Playwright MCP Browser Automation

Master browser automation through the Playwright MCP server toolset. This skill teaches the **reconnaissance-then-action** workflow, element reference system, and token-efficient inspection patterns used by the MCP browser tools.

**Core invariant**: Always snapshot before acting — the accessibility tree provides the `ref` values that drive all interactions.

---

## When to Use This Skill

- Inspecting a running web application's UI state
- Debugging frontend rendering, layout, or interaction bugs
- Verifying that code changes produce correct visual output
- Filling forms, clicking buttons, or navigating multi-step flows
- Capturing console errors or network requests for diagnosis
- Generating Playwright locators for test authoring

---

## Tool Reference

### Inspection Tools (read-only)

| Tool | Purpose | Key Params |
|------|---------|------------|
| `browser_snapshot` | Accessibility tree with `ref` values | `filename?` |
| `browser_take_screenshot` | Visual PNG/JPEG capture | `type`, `fullPage?`, `element?`, `ref?` |
| `browser_console_messages` | JS console output | `level` (error/warning/info/debug) |
| `browser_network_requests` | HTTP request log | `includeStatic?` (default: false) |

### Navigation Tools

| Tool | Purpose | Key Params |
|------|---------|------------|
| `browser_navigate` | Go to URL | `url` |
| `browser_navigate_back` | Browser back button | — |
| `browser_tabs` | Tab management | `action` (list/create/close/select), `index?` |
| `browser_wait_for` | Wait for condition | `time?`, `text?`, `textGone?` |

### Interaction Tools

| Tool | Purpose | Key Params |
|------|---------|------------|
| `browser_click` | Click element | `element?`, `ref`, `doubleClick?`, `button?` |
| `browser_type` | Type text into field | `element?`, `ref`, `text`, `submit?`, `slowly?` |
| `browser_fill_form` | Fill multiple fields | `fields` (array) |
| `browser_select_option` | Select dropdown value | `element?`, `ref`, `values` |
| `browser_hover` | Hover over element | `element?`, `ref` |
| `browser_press_key` | Press keyboard key | `key` (e.g., "Enter", "ArrowDown") |
| `browser_drag` | Drag and drop | `startElement`, `startRef`, `endElement`, `endRef` |
| `browser_handle_dialog` | Accept/dismiss dialog | `accept`, `promptText?` |
| `browser_file_upload` | Upload file(s) | `paths` (array of absolute paths) |

### Advanced Tools

| Tool | Purpose | Key Params | Requires |
|------|---------|------------|----------|
| `browser_evaluate` | Run JS in page context | `function`, `element?`, `ref?` | — |
| `browser_run_code` | Run Playwright API code | `code` (async page function) | — |
| `browser_generate_locator` | Generate test locator | `element?`, `ref` | `--caps=testing` |
| `browser_resize` | Change viewport size | `width`, `height` | — |
| `browser_pdf_save` | Save page as PDF | `filename?` | `--caps=pdf` |

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

---

## Templates

### Template: Page Inspection

```
1. browser_navigate(url="http://localhost:5173")
2. browser_wait_for(time=2)
3. browser_snapshot()
4. browser_console_messages(level="error")
5. browser_take_screenshot(fullPage=true)
→ Report: page structure, visible elements, errors found
```

### Template: Form Submit Flow

```
1. browser_navigate(url="http://localhost:5173/orders/new")
2. browser_snapshot()                        → find form field refs
3. browser_fill_form(fields=[...])           → fill all fields
4. browser_click(element="Submit", ref="eN") → submit
5. browser_wait_for(text="Order Created")    → wait for success
6. browser_snapshot()                        → verify result
7. browser_console_messages(level="error")   → check for errors
```

### Template: Debug UI Issue

```
1. browser_navigate(url="<problem page>")
2. browser_snapshot()                        → inspect DOM structure
3. browser_console_messages(level="warning") → check JS warnings/errors
4. browser_network_requests()                → check failed API calls
5. browser_take_screenshot(fullPage=true)    → capture visual state
6. browser_evaluate(function="() => getComputedStyle(document.querySelector('.broken'))")
   → inspect computed styles
→ Compare findings against expected behavior
```

### Template: Multi-Page Navigation

```
1. browser_navigate(url="http://localhost:5173")
2. browser_snapshot()                         → find nav refs
3. browser_click(element="Orders link", ref="eN")
4. browser_wait_for(text="Order List")
5. browser_snapshot()                         → verify new page
6. browser_click(element="Order #123", ref="eM")
7. browser_wait_for(text="Order Details")
8. browser_snapshot()                         → inspect detail page
```

### Template: Responsive Design Check

```
1. browser_navigate(url="http://localhost:5173")
2. browser_resize(width=1920, height=1080)   → desktop
3. browser_take_screenshot(fullPage=true)
4. browser_resize(width=768, height=1024)    → tablet
5. browser_take_screenshot(fullPage=true)
6. browser_resize(width=375, height=812)     → mobile
7. browser_take_screenshot(fullPage=true)
→ Compare screenshots across viewports
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

- ❌ **Saving screenshots to workspace** — Screenshots are ephemeral artifacts, not project files. Always use `/tmp/playwright-captures/`
- ❌ **Acting without snapshot** — Never click/type without a fresh `browser_snapshot`; you won't have valid `ref` values
- ❌ **Screenshot for element discovery** — Screenshots don't provide `ref` values; use `browser_snapshot` instead
- ❌ **Stale refs after DOM change** — After any interaction that changes the page, re-run `browser_snapshot` to get fresh refs
- ❌ **Ignoring console errors** — Always check `browser_console_messages(level="error")` during debugging
- ❌ **Full-page screenshot on complex pages** — Use `browser_snapshot` for structure; reserve screenshots for visual verification
- ❌ **Guessing selectors** — Use `browser_snapshot` or `browser_generate_locator` to discover correct selectors
- ✅ **Reconnaissance-then-action** — Always: navigate → wait → snapshot → identify → act → verify
- ✅ **Snapshot + screenshot combo** — Snapshot for structure and refs, screenshot for visual confirmation
- ✅ **Re-snapshot after mutations** — Any DOM change invalidates previous `ref` values

---

## Configuration Reference

Key MCP server flags that affect tool behavior:

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
