---
disable-model-invocation: true
name: vscode-integration
description: VS Code IDE runtime tool selection and usage patterns. Load when using VS Code sub-tools or IDE integration features
keywords: [vscode, ide, tools, extensions, workspace]
category: workflow
---

# VS Code Integration Skill

The `vscode` tool is the **core IDE integration layer** for all agents and subagents. It exposes VS Code's native capabilities through structured sub-tools. This skill documents each sub-tool's contract, constraints, and usage patterns.

**Rule**: Every agent/subagent MUST include `'vscode'` in its `tools:` list.

---

## Sub-Tool Reference

### 1. `askQuestions` — Interactive User Input

Renders native VS Code quick-pick widgets and returns structured JSON responses. **Primary mechanism for gathering user preferences, clarifications, and decisions.**

#### Schema

```
ask_questions({
  questions: [                      // 1–4 questions per call
    {
      header: "string",             // ≤12 chars — UI label AND response key (REQUIRED)
      question: "string",           // Full question text (REQUIRED)
      multiSelect: boolean,         // true = checkboxes, false = single-select (default: false)
      allowFreeformInput: boolean,  // true = user can type custom text (default: false)
      options: [                    // 0–6 options; omit/empty = free text input only
        {
          label: "string",          // Option text (REQUIRED)
          description: "string",    // Secondary text shown below label (optional)
          recommended: boolean      // Pre-selects option, shows recommended badge (optional)
        }
      ]
    }
  ]
})
```

#### Response

```json
{
  "answers": {
    "<header>": {
      "selected": ["Label A", "Label B"],
      "freeText": "user typed text or null",
      "skipped": false
    }
  }
}
```

#### Hard Constraints

| Parameter | Limit | Failure Mode |
|-----------|-------|-------------|
| `header` | ≤12 characters | **Validation error** — tool call fails |
| `questions` | 1–4 per call | **Validation error** — tool call fails |
| `options` | 0–6 per question | **Validation error** — tool call fails |
| `recommended` | Max 1 per question | UX confusion — multiple pre-selected |
| `recommended` | **NEVER** on quiz/poll options | Reveals answer — pre-selects it |

#### Patterns

**Single-select decision:**
```
ask_questions({ questions: [{
  header: "Approach",
  question: "Which implementation approach?",
  options: [
    { label: "Option A", description: "Fast, less flexible", recommended: true },
    { label: "Option B", description: "Slower, extensible" },
    { label: "Skip", description: "Keep current" }
  ]
}]})
```

**Multi-select priorities:**
```
ask_questions({ questions: [{
  header: "Focus",
  question: "Which areas to prioritize?",
  multiSelect: true,
  options: [
    { label: "Performance", recommended: true },
    { label: "Security" },
    { label: "UX" }
  ]
}]})
```

**Free text with suggestions:**
```
ask_questions({ questions: [{
  header: "Name",
  question: "Module name?",
  allowFreeformInput: true,
  options: [
    { label: "analytics", description: "Based on described functionality" },
    { label: "reporting", description: "Matches naming convention" }
  ]
}]})
```

**Pure free text (no presets):**
```
ask_questions({ questions: [{
  header: "Details",
  question: "Describe the expected behavior."
}]})
```

**Batched wizard (max 4):**
```
ask_questions({ questions: [
  { header: "Scope", question: "...", options: [...] },
  { header: "Priority", question: "...", multiSelect: true, options: [...] },
  { header: "Timeline", question: "...", options: [...] }
]})
```

---

### 2. `runCommand` — VS Code Command Execution

Executes any VS Code command by its command ID. Maps to `vscode.commands.executeCommand()`.

#### Schema

```
run_vscode_command({
  commandId: "string",   // VS Code command ID (REQUIRED)
  name: "string",        // Human-readable description (REQUIRED)
  args: ["string"]       // Arguments array (optional)
})
```

#### Useful Command IDs

**File Operations:**

| Command ID | Purpose |
|-----------|---------|
| `workbench.action.files.save` | Save active file |
| `workbench.action.files.saveAll` | Save all files |
| `workbench.action.files.newUntitledFile` | Create new untitled file |
| `workbench.action.closeActiveEditor` | Close active editor |
| `workbench.action.closeAllEditors` | Close all editors |
| `workbench.action.revertFile` | Revert file to saved |

**Editor:**

| Command ID | Purpose |
|-----------|---------|
| `editor.action.formatDocument` | Format active document |
| `editor.action.organizeImports` | Organize imports |
| `editor.action.commentLine` | Toggle line comment |
| `editor.action.triggerSuggest` | Trigger autocomplete |
| `editor.action.rename` | Rename symbol |
| `editor.action.revealDefinition` | Go to definition |

**Terminal:**

| Command ID | Purpose |
|-----------|---------|
| `workbench.action.terminal.new` | Create new terminal |
| `workbench.action.terminal.kill` | Kill active terminal |
| `workbench.action.terminal.clear` | Clear terminal |
| `workbench.action.terminal.focus` | Focus terminal panel |

**Workspace & Layout:**

| Command ID | Purpose |
|-----------|---------|
| `workbench.action.toggleSidebarVisibility` | Toggle sidebar |
| `workbench.action.togglePanel` | Toggle bottom panel |
| `workbench.action.toggleZenMode` | Toggle Zen mode |
| `workbench.action.maximizeEditor` | Maximize editor |
| `workbench.action.newWindow` | Open new VS Code window |

**Tasks & Testing:**

| Command ID | Purpose |
|-----------|---------|
| `workbench.action.tasks.runTask` | Run specific task |
| `workbench.action.tasks.build` | Run build task |
| `testing.runAll` | Run all tests |
| `testing.reRunLastRun` | Re-run last test run |

**Git:**

| Command ID | Purpose |
|-----------|---------|
| `git.stage` | Stage file |
| `git.stageAll` | Stage all changes |
| `git.commit` | Commit staged changes |
| `git.push` | Push to remote |
| `workbench.view.scm` | Open source control view |

**Search:**

| Command ID | Purpose |
|-----------|---------|
| `workbench.action.findInFiles` | Open workspace search |
| `editor.action.startFindReplaceAction` | Find and replace in file |
| `workbench.action.quickOpen` | Quick open file (Ctrl+P) |
| `workbench.action.showAllSymbols` | Go to symbol in workspace |

---

### 3. `extensions` — Marketplace Search

Search the VS Code extension marketplace for extensions.

#### Schema

```
vscode_searchExtensions_internal({
  category: "string",   // Extension category (optional, enum below)
  keywords: ["string"], // Search keywords (optional)
  ids: ["string"]       // Specific extension IDs to look up (optional)
})
```

**Category enum:** `AI`, `Azure`, `Chat`, `Data Science`, `Debuggers`, `Extension Packs`, `Education`, `Formatters`, `Keymaps`, `Language Packs`, `Linters`, `Machine Learning`, `Notebooks`, `Programming Languages`, `SCM Providers`, `Snippets`, `Testing`, `Themes`, `Visualization`, `Other`

#### When to Use

- User asks "what extension for X?"
- Need to verify an extension exists before recommending
- Comparing extensions for a specific purpose

---

### 4. `openSimpleBrowser` — In-Editor URL Preview

Opens a URL in VS Code's built-in Simple Browser panel.

#### Schema

```
open_simple_browser({
  url: "string"   // HTTP or HTTPS URL (REQUIRED)
})
```

#### When to Use

- Preview locally hosted dev servers (`http://localhost:5173`)
- View generated documentation or reports
- Quick-check a web resource without leaving the editor

---

### 5. `vscodeAPI` — Extension Development Docs

Query VS Code API documentation for extension development guidance.

#### Schema

```
get_vscode_api({
  query: "string"   // API query with specific names/concepts (REQUIRED)
})
```

#### When to Use

- User is developing a VS Code extension
- Need to look up specific API interfaces, methods, or contribution points
- Questions about proposed vs stable APIs

**Not for**: General VS Code usage questions, agent configuration, or non-extension tasks.

---

### 6. `installExtension` — Install Extensions

Install a VS Code extension by its marketplace ID.

#### Schema

```
install_extension({
  id: "string",     // Extension ID: publisher.extension (REQUIRED)
  name: "string"    // Human-readable name (REQUIRED)
})
```

#### When to Use

- Part of new workspace/project setup
- User explicitly requests extension installation
- Project requires specific tooling extensions

---

### 7. `newWorkspace` — Project Scaffolding

Create a new project workspace with full structure.

#### Schema

```
create_new_workspace({
  query: "string"   // Project description (REQUIRED)
})
```

#### When to Use

- User wants to create a new project from scratch
- Setting up framework-based projects (React, Next.js, etc.)
- Initializing MCP servers or VS Code extensions

**Not for**: Creating single files, adding to existing projects, or simple code snippets.

---

### 8. `getProjectSetupInfo` — Setup Information

Get project setup steps for specific project types.

#### Schema

```
get_project_setup_info({
  projectType: "string"   // Project type enum (REQUIRED)
})
```

**Project type enum:** `python-script`, `python-project`, `mcp-server`, `model-context-protocol-server`, `vscode-extension`, `next-js`, `vite`, `other`

**Prerequisite**: Must call `create_new_workspace` first.

---

## Decision Table: Which Sub-Tool?

| Need | Sub-Tool | Example |
|------|----------|---------|
| Get user preference / clarification | `askQuestions` | "Which approach should I use?" |
| Execute IDE action programmatically | `runCommand` | Format document, save all |
| Find/recommend extensions | `extensions` | "Best Python linter extension?" |
| Preview a local URL | `openSimpleBrowser` | View dev server at localhost |
| Look up VS Code extension API | `vscodeAPI` | "How does TreeDataProvider work?" |
| Install an extension | `installExtension` | Set up project tooling |
| Scaffold a new project | `newWorkspace` | "Create a new Next.js app" |
| Get project setup steps | `getProjectSetupInfo` | Setup info for Python project |

---

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Use markdown-formatted questions for user input | Use `askQuestions` with native widgets |
| Guess user preferences when ambiguous | Ask via `askQuestions` with recommended defaults |
| Run terminal commands for VS Code actions | Use `runCommand` with proper command ID |
| Hard-code command IDs without checking | Verify command IDs from the reference tables above |
| Use `vscodeAPI` for non-extension questions | Use `search` or `read` tools instead |
| Use `newWorkspace` for adding files to existing projects | Use `create_file` tool instead |
| Use `askQuestions` when intent is obvious | Infer and proceed — don't over-ask |

---

## Integration Notes

- **`askQuestions`** wraps `vscode.window.showQuickPick()` and similar native UI APIs
- **`runCommand`** wraps `vscode.commands.executeCommand()`
- **`extensions`** wraps VS Code marketplace search API
- **`openSimpleBrowser`** wraps the `simpleBrowser.open` internal command
- All sub-tools return structured data — handle responses as JSON
- Sub-tools are available in **all agent modes** (user-facing and subagent)
