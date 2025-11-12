# VS Code Multi-Root Workspace Setup

**Last Updated:** November 11, 2025

## 🎯 Purpose

This workspace configuration solves TypeScript/Python resolution issues in VS Code by properly separating the backend and frontend contexts in a multi-root workspace.

## 🚀 Quick Start

### Option 1: Open Workspace File (Recommended)

1. Close the current VS Code window
2. Open the workspace file:

   ```bash
   code trader-pro.code-workspace
   ```

### Option 2: From VS Code UI

1. `File` → `Open Workspace from File...`
2. Select `trader-pro.code-workspace`

## 📁 Workspace Structure

The workspace defines three folders:

```
🎯 Trader Pro (Root)     - Root-level files (Makefiles, docs, configs)
🔧 Backend API          - Python/FastAPI backend with isolated Python env
🎨 Frontend             - Vue/TypeScript frontend with isolated Node env
```

## ✨ Benefits

### TypeScript Resolution

- ✅ VS Code uses `frontend/tsconfig.json` correctly
- ✅ `import.meta.env` works without errors
- ✅ Vue components get proper type checking
- ✅ TypeScript SDK points to frontend's node_modules

### Python Environment

- ✅ Correct virtualenv detection
- ✅ Pytest runs in backend context
- ✅ Black/isort formatting works properly
- ✅ Pylance uses backend's .venv

### Developer Experience

- ✅ Separate terminal contexts for backend/frontend
- ✅ IntelliSense works correctly in each folder
- ✅ Debugging configurations for both stacks
- ✅ Task runner for dev/test commands

## 🔧 Recommended Extensions

The workspace will prompt you to install these extensions:

### Python/Backend

- `ms-python.python` - Python language support
- `ms-python.vscode-pylance` - Fast Python IntelliSense
- `ms-python.black-formatter` - Black code formatter
- `ms-python.isort` - Import sorting
- `ms-python.mypy-type-checker` - Static type checking

### TypeScript/Frontend

- `vue.volar` - Vue 3 language support
- `dbaeumer.vscode-eslint` - ESLint integration
- `esbenp.prettier-vscode` - Prettier formatter

### General

- `editorconfig.editorconfig` - EditorConfig support
- `github.vscode-pull-request-github` - GitHub integration
- `eamodio.gitlens` - Git supercharged

## 🎮 Using the Workspace

### Running Dev Servers

**Backend Only:**

1. Open integrated terminal
2. Select "🔧 Backend API" from terminal dropdown
3. Run: `make dev`

**Frontend Only:**

1. Open integrated terminal
2. Select "🎨 Frontend" from terminal dropdown
3. Run: `npm run dev`

**Both Together:**

- Use the Debug panel
- Select "Full Stack: Backend + Frontend"
- Press F5

### Running Tests

**Via Command Palette (Ctrl+Shift+P):**

- `Tasks: Run Task` → Select test task

**Via Terminal:**

```bash
# Backend tests
cd backend && make test

# Frontend tests
cd frontend && npm run test:unit

# Integration tests
make test-integration
```

### Debugging

Available debug configurations:

- **Backend: FastAPI Dev Server** - Debug backend API
- **Backend: Run Tests** - Debug pytest tests
- **Frontend: Vite Dev Server** - Debug frontend in Chrome
- **Full Stack: Backend + Frontend** - Debug both simultaneously

## 🔍 TypeScript SDK Configuration

The workspace automatically configures:

```json
"typescript.tsdk": "frontend/node_modules/typescript/lib"
```

This ensures VS Code uses the frontend's TypeScript version, not a global one.

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
2. Install dependencies: `make install` (includes hooks)
3. Install recommended extensions when prompted
4. Verify TypeScript is using workspace version
5. Start coding without TypeScript errors! 🚀
