# VS Code Multi-Root Workspace Setup# VS Code Multi-Root Workspace Setup

## Purpose## 🎯 Purpose

Solves TypeScript/Python resolution issues by properly separating backend and frontend contexts in a multi-root workspace.This workspace configuration solves TypeScript/Python resolution issues in VS Code by properly separating the backend and frontend contexts in a multi-root workspace.

## Quick Start## 🚀 Quick Start

````bash### Option 1: Open Workspace File (Recommended)

# Option 1: Command line (recommended)

code trader-pro.code-workspace1. Close the current VS Code window

2. Open the workspace file:

# Option 2: From VS Code   ```bash

File → Open Workspace from File... → Select trader-pro.code-workspace   code trader-pro.code-workspace

```   ```



## Workspace Structure### Option 2: From VS Code UI



```1. `File` → `Open Workspace from File...`

🎯 Trader Pro (Root)     - Root files (Makefiles, docs, configs)2. Select `trader-pro.code-workspace`

🔧 Backend API          - Python/FastAPI with isolated .venv

🎨 Frontend             - Vue/TypeScript with isolated node_modules## 📁 Workspace Structure

````

The workspace defines three folders:

## Benefits

````

### TypeScript🎯 Trader Pro (Root)     - Root-level files (Makefiles, docs, configs)

- ✅ Correct `tsconfig.json` usage🔧 Backend API          - Python/FastAPI backend with isolated Python env

- ✅ `import.meta.env` works without errors🎨 Frontend             - Vue/TypeScript frontend with isolated Node env

- ✅ Proper Vue component type checking```

- ✅ TypeScript SDK points to frontend's node_modules

## ✨ Benefits

### Python

- ✅ Correct virtualenv detection### TypeScript Resolution

- ✅ Pytest runs in backend context- ✅ VS Code uses `frontend/tsconfig.json` correctly

- ✅ Black/isort formatting works- ✅ `import.meta.env` works without errors

- ✅ Pylance uses backend's .venv- ✅ Vue components get proper type checking

- ✅ TypeScript SDK points to frontend's node_modules

### Developer Experience

- ✅ Separate terminal contexts### Python Environment

- ✅ Correct IntelliSense per folder- ✅ Correct virtualenv detection

- ✅ Debugging for both stacks- ✅ Pytest runs in backend context

- ✅ Integrated task runner- ✅ Black/isort formatting works properly

- ✅ Pylance uses backend's .venv

## Recommended Extensions

### Developer Experience

Install when prompted or via: `Ctrl+Shift+P` → `Extensions: Show Recommended Extensions`- ✅ Separate terminal contexts for backend/frontend

- ✅ IntelliSense works correctly in each folder

**Python/Backend**: python, pylance, black-formatter, isort, mypy-type-checker  - ✅ Debugging configurations for both stacks

**TypeScript/Frontend**: vue.volar, eslint, prettier-vscode  - ✅ Task runner for dev/test commands

**General**: editorconfig, github pull-request, gitlens

## 🔧 Recommended Extensions

## Usage

The workspace will prompt you to install these extensions:

### Running Dev Servers

### Python/Backend

**Backend**: Terminal → Select "🔧 Backend API" → `make dev`  - `ms-python.python` - Python language support

**Frontend**: Terminal → Select "🎨 Frontend" → `npm run dev`  - `ms-python.vscode-pylance` - Fast Python IntelliSense

**Both**: Debug panel → "Full Stack: Backend + Frontend" → F5- `ms-python.black-formatter` - Black code formatter

- `ms-python.isort` - Import sorting

### Running Tests- `ms-python.mypy-type-checker` - Static type checking



```bash### TypeScript/Frontend

# Backend- `vue.volar` - Vue 3 language support

cd backend && make test- `dbaeumer.vscode-eslint` - ESLint integration

- `esbenp.prettier-vscode` - Prettier formatter

# Frontend

cd frontend && npm run test:unit### General

- `editorconfig.editorconfig` - EditorConfig support

# Integration- `github.vscode-pull-request-github` - GitHub integration

make test-integration- `eamodio.gitlens` - Git supercharged

````

## 🎮 Using the Workspace

### Debugging

### Running Dev Servers

Available configurations:

- **Backend: FastAPI Dev Server** - Debug backend API**Backend Only:**

- **Backend: Run Tests** - Debug pytest1. Open integrated terminal

- **Frontend: Vite Dev Server** - Debug in Chrome2. Select "🔧 Backend API" from terminal dropdown

- **Full Stack** - Debug both simultaneously3. Run: `make dev`

## TypeScript Configuration**Frontend Only:**

1. Open integrated terminal

Workspace automatically configures:2. Select "🎨 Frontend" from terminal dropdown

```json3. Run: `npm run dev`

"typescript.tsdk": "frontend/node_modules/typescript/lib"

`````**Both Together:**

- Use the Debug panel

### Verify TypeScript- Select "Full Stack: Backend + Frontend"

- Press F5

1. Open `frontend/src/services/apiService.ts`

2. Hover over `import.meta.env.DEV` → Should show `boolean` type### Running Tests

3. `Ctrl+Shift+P` → `TypeScript: Select TypeScript Version...` → Should show "Use Workspace Version"

**Via Command Palette (Ctrl+Shift+P):**

## Troubleshooting- `Tasks: Run Task` → Select test task



### TypeScript errors persist?**Via Terminal:**

1. `Ctrl+Shift+P` → `Developer: Reload Window````bash

2. `Ctrl+Shift+P` → `TypeScript: Restart TS Server`# Backend tests

3. Verify workspace version selectedcd backend && make test



### Python environment not detected?# Frontend tests

1. Check status bar (bottom-right) for Python interpretercd frontend && npm run test:unit

2. Click and select `.venv` from backend folder

3. Or: `Ctrl+Shift+P` → `Python: Select Interpreter`# Integration tests

make test-integration

### Terminal in wrong context?```

1. Click `+` dropdown in terminal panel

2. Select specific workspace folder### Debugging

3. Or split terminal for different folders

Available debug configurations:

## Next Steps- **Backend: FastAPI Dev Server** - Debug backend API

- **Backend: Run Tests** - Debug pytest tests

1. Open workspace: `code trader-pro.code-workspace`- **Frontend: Vite Dev Server** - Debug frontend in Chrome

2. Install dependencies: `make -f project.mk install-all`- **Full Stack: Backend + Frontend** - Debug both simultaneously

3. Install recommended extensions

4. Verify TypeScript workspace version## 🔍 TypeScript SDK Configuration

5. Start coding! 🚀

The workspace automatically configures:

## Resources```json

"typescript.tsdk": "frontend/node_modules/typescript/lib"

- [VS Code Multi-Root Workspaces](https://code.visualstudio.com/docs/editor/multi-root-workspaces)```

- [TypeScript and VS Code](https://code.visualstudio.com/docs/languages/typescript)

- [Python in VS Code](https://code.visualstudio.com/docs/languages/python)This ensures VS Code uses the frontend's TypeScript version, not a global one.


### Verify TypeScript is Working

1. Open `frontend/src/services/apiService.ts`
2. Hover over `import.meta.env.DEV`
3. Should see type: `boolean` (not an error)
4. Run: `Ctrl+Shift+P` → `TypeScript: Select TypeScript Version...`
5. Should show: `Use Workspace Version` (from frontend)

## 📝 Settings Applied

### Python (Backend)
- Auto-format on save with Black
- Auto-organize imports with isort
- Pytest test discovery enabled
- Type checking: basic mode

### TypeScript/Vue (Frontend)
- Auto-format on save with Prettier
- Auto-organize imports
- Vue Volar for .vue files
- ESLint working directory: `./frontend`

## 🐛 Troubleshooting

### TypeScript still showing errors?

1. Reload VS Code: `Ctrl+Shift+P` → `Developer: Reload Window`
2. Check TypeScript version: `Ctrl+Shift+P` → `TypeScript: Select TypeScript Version...`
   - Should show workspace version from frontend
3. Restart TS Server: `Ctrl+Shift+P` → `TypeScript: Restart TS Server`

### Python environment not detected?

1. Open a Python file in backend folder
2. Check status bar (bottom-right) for Python interpreter
3. Click and select: `.venv` interpreter from backend folder
4. Or use: `Ctrl+Shift+P` → `Python: Select Interpreter`

### Extensions not working?

1. Install recommended extensions when prompted
2. Or: `Ctrl+Shift+P` → `Extensions: Show Recommended Extensions`
3. Install all workspace recommendations

### Terminal in wrong context?

1. Click the `+` dropdown in terminal panel
2. Select the specific workspace folder
3. Or split terminal and select different folders

## 🔄 Migration from Single-Root

If you previously had `.vscode/settings.json`:

1. Those settings are now in the workspace file
2. You can delete `.vscode/settings.json` (workspace overrides it)
3. Or keep it for user-specific settings not in the workspace

## 📚 Additional Resources

- [VS Code Multi-Root Workspaces](https://code.visualstudio.com/docs/editor/multi-root-workspaces)
- [TypeScript and VS Code](https://code.visualstudio.com/docs/languages/typescript)
- [Python in VS Code](https://code.visualstudio.com/docs/languages/python)
- [Vue with Volar](https://github.com/vuejs/language-tools)

## 🎉 Next Steps

1. Open the workspace file: `code trader-pro.code-workspace`
2. Install dependencies: `make -f project.mk install-all` (includes hooks)
3. Install recommended extensions when prompted
4. Verify TypeScript is using workspace version
5. Start coding without TypeScript errors! 🚀
`````
