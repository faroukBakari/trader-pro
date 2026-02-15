# Playwright MCP Workflow Templates

Step-by-step templates for common browser automation workflows. Each template follows the reconnaissance-then-action pattern from the core skill.

---

## Template: File Upload (Clipboard Injection)

The standard `browser_file_upload` tool is broken in extension mode. This clipboard injection workaround is the **only confirmed working pattern** for file uploads. It bypasses CDP restrictions by encoding the file to base64, loading it into the Windows clipboard, and injecting it via `browser_evaluate`.

**Prerequisites:**
- MCP config includes `--grant-permissions clipboard-read,clipboard-write`
- The hidden `<input type="file">` must exist in DOM before injection (click the trigger button first)

### Step 1: Locate and trigger the file input

```
1. browser_snapshot()                                  → find the upload trigger element
2. browser_click(element="Upload button", ref="eN")    → trigger file input creation
3. browser_snapshot()                                  → confirm <input type="file"> exists in DOM
```

### Step 2: Encode and transfer to clipboard (WSL/Bash side)

```bash
# Encode file to base64 (no line wrapping — critical)
base64 -w0 /path/to/file.pdf > /tmp/file_b64.txt

# Copy to Windows filesystem
cp /tmp/file_b64.txt /mnt/c/temp/file_b64.txt

# Load into Windows clipboard
powershell.exe -Command "Set-Clipboard -Value (Get-Content -Raw 'C:\temp\file_b64.txt')"
```

> **WARNING**: Do NOT use `certutil -encode` — it adds `-----BEGIN CERTIFICATE-----` headers that break `atob()`.

### Step 3: Inject via browser_evaluate

```javascript
async () => {
  const raw = await navigator.clipboard.readText();
  const b64 = raw.replace(/\s/g, '');
  const binaryStr = atob(b64);
  const bytes = new Uint8Array(binaryStr.length);
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i);
  }
  const file = new File([bytes], 'filename.pdf', { type: 'application/pdf' });
  const input = document.querySelector('input[type="file"]');  // adjust selector
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
  input.dispatchEvent(new Event('change', { bubbles: true }));
  return `SUCCESS: ${bytes.length} bytes`;
}
```

### Step 4: Verify

```
1. browser_snapshot()                                  → verify upload was accepted
```

> Adjust the CSS selector (`input[type="file"]`), filename, and MIME type for your use case.

**Confirmed working**: Tested with a 77KB PDF on collective.work.

### Complete sequence (condensed)

```
1. browser_snapshot()                        → find the upload trigger element
2. browser_click(element="Upload button", ref="eN")  → trigger file input creation
3. browser_snapshot()                        → confirm <input type="file"> exists in DOM
4. Bash: base64 -w0 /path/to/file > /tmp/file_b64.txt
5. Bash: cp /tmp/file_b64.txt /mnt/c/temp/file_b64.txt
6. Bash: powershell.exe -Command "Set-Clipboard -Value (Get-Content -Raw 'C:\temp\file_b64.txt')"
7. browser_evaluate(function="async () => {
     const raw = await navigator.clipboard.readText();
     const b64 = raw.replace(/\\s/g, '');
     const bin = atob(b64);
     const bytes = new Uint8Array(bin.length);
     for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
     const file = new File([bytes], 'file.pdf', { type: 'application/pdf' });
     const input = document.querySelector('input[type=\"file\"]');
     const dt = new DataTransfer();
     dt.items.add(file);
     input.files = dt.files;
     input.dispatchEvent(new Event('change', { bubbles: true }));
     return 'SUCCESS: ' + bytes.length + ' bytes';
   }")
8. browser_snapshot()                        → verify upload was accepted
→ Adjust selector, filename, and MIME type for your use case
```

---

## Template: Page Inspection

Use when you need to understand the current state of a page — structure, elements, errors.

```
1. browser_navigate(url="http://localhost:5173")
2. browser_wait_for(time=2)
3. browser_snapshot()
4. browser_console_messages(level="error")
5. browser_take_screenshot(fullPage=true)
→ Report: page structure, visible elements, errors found
```

---

## Template: Form Submit Flow

Use when filling and submitting a form, then verifying the result.

```
1. browser_navigate(url="http://localhost:5173/orders/new")
2. browser_snapshot()                        → find form field refs
3. browser_fill_form(fields=[...])           → fill all fields
4. browser_click(element="Submit", ref="eN") → submit
5. browser_wait_for(text="Order Created")    → wait for success
6. browser_snapshot()                        → verify result
7. browser_console_messages(level="error")   → check for errors
```

---

## Template: Debug UI Issue

Use when diagnosing a rendering, layout, or interaction bug.

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

---

## Template: Multi-Page Navigation

Use when testing navigation flows across multiple pages.

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

---

## Template: Responsive Design Check

Use when verifying layout across different viewport sizes.

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
