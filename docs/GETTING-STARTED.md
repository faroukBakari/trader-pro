# Getting Started with Trader Pro

**Version**: 1.0.0  
**Last Updated**: November 18, 2025  
**Status**: ✅ Current

> **Note**: This guide consolidates setup information from WORKSPACE-SETUP.md, HOOKS-SETUP.md, and ENVIRONMENT-CONFIG.md (archived November 18, 2025).

Complete setup guide for getting started with Trader Pro development environment, including VS Code workspace configuration, Git hooks, and environment variables.

---

## 📋 Quick Navigation

- [Prerequisites](#1-prerequisites)
- [Quick Setup](#2-quick-setup-5-minutes)
- [Environment Configuration](#3-environment-configuration)
- [VS Code Workspace Setup](#4-vs-code-workspace-setup)
- [Git Hooks Installation](#5-git-hooks-installation)
- [Verification & First Run](#6-verification--first-run)
- [Next Steps](#7-next-steps)
- [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

Before starting, ensure you have:

- **Python 3.11+** with Poetry installed
- **Node.js 22.20+** with nvm (recommended)
- **Git** configured
- **VS Code** (recommended IDE)
- **Make** utility (usually pre-installed on Linux/macOS)

---

## 2. Quick Setup (5 Minutes)

For experienced developers who want to get started immediately:

```bash
# 1. Clone and enter project
git clone <repository-url>
cd trader-pro

# 2. Install everything (dependencies + hooks)
make install

# 3. Open VS Code workspace
code trader-pro.code-workspace

# 4. Install recommended extensions when prompted

# 5. Start development
make dev-fullstack
```

That's it! Skip to [Next Steps](#7-next-steps) or continue reading for detailed explanations.

---

## 3. Environment Configuration

Environment variables configure ports, URLs, and settings across development, testing, and production environments.

### 3.1 Key Environment Variables

#### Backend

| Variable          | Default     | Description                                                       |
| ----------------- | ----------- | ----------------------------------------------------------------- |
| `BACKEND_PORT`    | `8000`      | FastAPI server port                                               |
| `ENABLED_MODULES` | all modules | Comma-separated list of modules to load (e.g., `broker,datafeed`) |

#### Frontend

| Variable        | Default                 | Description                            |
| --------------- | ----------------------- | -------------------------------------- |
| `FRONTEND_PORT` | `5173`                  | Vite dev server port                   |
| `VITE_API_URL`  | `http://localhost:8000` | API base URL (must start with `VITE_`) |
| `FRONTEND_URL`  | `http://localhost:5173` | Frontend URL for tests                 |

#### Bar Broadcaster

| Variable                      | Default           | Description                   |
| ----------------------------- | ----------------- | ----------------------------- |
| `BAR_BROADCASTER_ENABLED`     | `true`            | Enable/disable broadcaster    |
| `BAR_BROADCASTER_INTERVAL`    | `2.0`             | Broadcast interval (seconds)  |
| `BAR_BROADCASTER_SYMBOLS`     | `AAPL,GOOGL,MSFT` | Symbols to broadcast          |
| `BAR_BROADCASTER_RESOLUTIONS` | `1`               | Resolutions (comma-separated) |

#### Mock Services

| Variable                 | Default | Description               |
| ------------------------ | ------- | ------------------------- |
| `VITE_USE_MOCK_BROKER`   | `true`  | Use mock broker service   |
| `VITE_USE_MOCK_DATAFEED` | `true`  | Use mock datafeed service |

### 3.2 Configuration Files

#### `.env.example` (Git-tracked template)

The project includes a template with default values:

```bash
# Ports
BACKEND_PORT=8000
FRONTEND_PORT=5173

# URLs
VITE_API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
```

#### `.env.local` (Local overrides, not tracked)

Create this file for custom configurations:

```bash
cp .env.example .env.local
# Edit .env.local with your custom settings
```

**Note**: The project does not use a `.env` file by default. Use system environment variables or `.env.local` for customization.

### 3.3 Configuration Examples

#### Development with Custom Ports

```bash
export BACKEND_PORT=9000
export FRONTEND_PORT=3001
export VITE_API_URL=http://localhost:9000
export FRONTEND_URL=http://localhost:3001

make dev-fullstack
```

#### Production Configuration

```bash
export BACKEND_PORT=80
export VITE_API_URL=https://api.traderpro.com
export FRONTEND_URL=https://traderpro.com
export NODE_ENV=production
```

#### Fast Broadcasting for Testing

```bash
export BAR_BROADCASTER_INTERVAL=0.5
export BAR_BROADCASTER_SYMBOLS=AAPL,TSLA
make dev
```

#### Disable Mock Services

```bash
export VITE_USE_MOCK_BROKER=false
export VITE_USE_MOCK_DATAFEED=false
npm run dev
```

### 3.4 Environment Variable Precedence

1. System environment variables (highest)
2. `.env.local` (local overrides, if exists)
3. `.env.example` (template defaults, lowest)

### 3.5 Client Generation

The frontend uses an efficient file-based approach for API client generation:

1. **Auto-Generation**: Backend generates `backend/openapi.json` on startup
2. **File Watching**: Dev script watches file for changes (not server polling)
3. **Local Priority**: Uses local file when available, HTTP as fallback
4. **Relative URLs**: Generated client uses `basePath: ""` for same-origin requests

**Benefits**: No server spam, efficient file monitoring, only regenerates on actual schema changes, works offline after first generation.

---

## 4. VS Code Workspace Setup

### 4.1 Purpose

The multi-root workspace configuration solves TypeScript/Python resolution issues in VS Code by properly separating the backend and frontend contexts.

### 4.2 Opening the Workspace

#### Option 1: Open Workspace File (Recommended)

```bash
code trader-pro.code-workspace
```

#### Option 2: From VS Code UI

1. `File` → `Open Workspace from File...`
2. Select `trader-pro.code-workspace`

### 4.3 Workspace Structure

The workspace defines three folders:

```
🎯 Trader Pro (Root)     - Root-level files (Makefiles, docs, configs)
🔧 Backend API          - Python/FastAPI backend with isolated Python env
🎨 Frontend             - Vue/TypeScript frontend with isolated Node env
```

### 4.4 Benefits

#### TypeScript Resolution

- ✅ VS Code uses `frontend/tsconfig.json` correctly
- ✅ `import.meta.env` works without errors
- ✅ Vue components get proper type checking
- ✅ TypeScript SDK points to frontend's node_modules

#### Python Environment

- ✅ Correct virtualenv detection
- ✅ Pytest runs in backend context
- ✅ Black/isort formatting works properly
- ✅ Pylance uses backend's .venv

#### Developer Experience

- ✅ Separate terminal contexts for backend/frontend
- ✅ IntelliSense works correctly in each folder
- ✅ Debugging configurations for both stacks
- ✅ Task runner for dev/test commands

### 4.5 Recommended Extensions

The workspace will prompt you to install these extensions:

#### Python/Backend

- `ms-python.python` - Python language support
- `ms-python.vscode-pylance` - Fast Python IntelliSense
- `ms-python.black-formatter` - Black code formatter
- `ms-python.isort` - Import sorting
- `ms-python.mypy-type-checker` - Static type checking

#### TypeScript/Frontend

- `vue.volar` - Vue 3 language support
- `dbaeumer.vscode-eslint` - ESLint integration
- `esbenp.prettier-vscode` - Prettier formatter

#### General

- `editorconfig.editorconfig` - EditorConfig support
- `github.vscode-pull-request-github` - GitHub integration
- `eamodio.gitlens` - Git supercharged

### 4.6 Using the Workspace

#### Running Dev Servers

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

#### Running Tests

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

#### Debugging

Available debug configurations:

- **Backend: FastAPI Dev Server** - Debug backend API
- **Backend: Run Tests** - Debug pytest tests
- **Frontend: Vite Dev Server** - Debug frontend in Chrome
- **Full Stack: Backend + Frontend** - Debug both simultaneously

### 4.7 TypeScript SDK Configuration

The workspace automatically configures:

```json
"typescript.tsdk": "frontend/node_modules/typescript/lib"
```

This ensures VS Code uses the frontend's TypeScript version, not a global one.

#### Verify TypeScript is Working

1. Open `frontend/src/services/apiService.ts`
2. Hover over `import.meta.env.DEV`
3. Should see type: `boolean` (not an error)
4. Run: `Ctrl+Shift+P` → `TypeScript: Select TypeScript Version...`
5. Should show: `Use Workspace Version` (from frontend)

### 4.8 Settings Applied

#### Python (Backend)

- Auto-format on save with Black
- Auto-organize imports with isort
- Pytest test discovery enabled
- Type checking: basic mode

#### TypeScript/Vue (Frontend)

- Auto-format on save with Prettier
- Auto-organize imports
- Vue Volar for .vue files
- ESLint working directory: `./frontend`

---

## 5. Git Hooks Installation

Git hooks automatically validate code quality before commits, ensuring consistent standards across the team.

### 5.1 Installation Options

```bash
# Option 1: Install all (recommended for new setup)
make install

# Option 2: Install hooks only
make install-hooks

# Option 3: Manual
git config core.hooksPath .githooks
chmod +x .githooks/*
```

### 5.2 What Gets Checked

**Important**: The pre-commit hook automatically stashes any unstaged changes **and untracked files** before running checks and **always** restores them afterward, regardless of whether the checks pass or fail.

This ensures:

- Only staged changes are checked
- Your working directory changes are preserved
- Untracked files don't interfere with linting/type checking
- Failed checks don't lose your work
- You get warnings about untracked source files that aren't being committed

#### Backend (Python files)

- ✅ Black formatting
- ✅ isort import sorting
- ✅ Flake8 linting
- ✅ MyPy type checking
- ✅ Spec and client generation (`make generate` - unified command)
- ✅ Pytest tests (local only)

**Note on spec validation**:

- **OpenAPI spec validation** ensures all REST API models and routes can be exported without errors
- **AsyncAPI spec validation** ensures all WebSocket models are valid and checks that subscription request models have **required** parameters only (no optional/default values)
- Optional parameters in subscription requests cause topic mismatch issues between request and response
- These validations run on **every commit** to prevent committing invalid schemas that would fail in CI

#### Frontend (TypeScript/Vue files)

- ✅ ESLint linting & auto-fixing
- ✅ Prettier formatting
- ✅ TypeScript type checking
- ✅ Vitest unit tests (local only)

#### All Files

- ✅ Trailing whitespace
- ✅ Merge conflict markers
- ✅ JSON/YAML validation

### 5.3 Hook Structure

```
.githooks/
├── pre-commit      # Main dispatcher
├── shared-lib.sh   # Utility functions
└── README.md       # Documentation
```

### 5.4 Usage

#### Skip Hooks Temporarily

```bash
# Skip once
git commit --no-verify

# Skip with env variable
SKIP_HOOKS=true git commit
```

#### Run Checks Manually

```bash
make lint && make format && make test
```

### 5.5 Benefits

- ✅ **Cross-platform** - Works on Windows, macOS, Linux
- ✅ **Stack-agnostic** - No npm/Python pre-commit dependencies
- ✅ **Fast** - Only checks changed files
- ✅ **CI-friendly** - Auto-detects CI environment
- ✅ **Version-controlled** - Hook logic is committed
- ✅ **Easy onboarding** - Single command installation

---

## 6. Verification & First Run

After completing the setup, verify everything is working:

### 6.1 Check Environment

```bash
# Verify Python version and Poetry
python --version  # Should be 3.11+
poetry --version

# Verify Node.js version
node --version  # Should be 22.20+
npm --version

# Verify Git hooks are installed
git config core.hooksPath  # Should show: .githooks
```

### 6.2 Check VS Code Workspace

1. Open `trader-pro.code-workspace` in VS Code
2. Verify three workspace folders appear in sidebar
3. Check TypeScript version: `Ctrl+Shift+P` → `TypeScript: Select TypeScript Version...`
   - Should show: `Use Workspace Version`
4. Check Python interpreter: Look at status bar (bottom-right)
   - Should show: `.venv` from backend folder

### 6.3 Run Development Servers

```bash
# Start full-stack development mode
make dev-fullstack

# Or start individually:
# Backend only
cd backend && make dev

# Frontend only
cd frontend && npm run dev
```

### 6.4 Run Tests

```bash
# Run all tests
make test

# Backend tests only
cd backend && make test

# Frontend tests only
cd frontend && npm test

# Integration tests
make test-integration
```

### 6.5 Verify Git Hooks

```bash
# Make a trivial change and try to commit
echo "# test" >> README.md
git add README.md
git commit -m "test: verify hooks"

# Hooks should run automatically
# If they fail, that's expected - hooks are working!
# Revert the test change:
git reset HEAD~1
git checkout README.md
```

---

## 7. Next Steps

Now that your environment is set up, here's what to do next:

### 7.1 Essential Reading

1. **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development workflows and commands
2. **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture overview
3. **[MAKEFILE-GUIDE.md](MAKEFILE-GUIDE.md)** - Complete Makefile reference
4. **[TESTING.md](TESTING.md)** - Testing strategies and patterns

### 7.2 Role-Specific Guides

**Backend Developers:**

- [Backend Architecture](../backend/docs/MODULAR_BACKEND_ARCHITECTURE.md)
- [API Methodology](methodologies/API-METHODOLOGY.md)
- [WebSocket Methodology](methodologies/WEBSOCKET-METHODOLOGY.md)

**Frontend Developers:**

- [Frontend README](../frontend/README.md)
- [WebSocket Architecture](../frontend/docs/WEBSOCKET-ARCHITECTURE.md)
- [Broker Integration](../frontend/docs/BROKER-INTEGRATION.md)

**Full-Stack Developers:**

- [Full-Stack Dev Mode](FULLSTACK-DEV-MODE.md)
- [Client Generation](CLIENT-GENERATION.md)
- [WebSocket Architecture](frontend/docs/WEBSOCKET-ARCHITECTURE.md)

### 7.3 Start Coding

```bash
# Create a new feature branch
git checkout -b feature/your-feature-name

# Start development servers
make dev-fullstack

# Make changes, commit, and push
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature-name
```

---

## Troubleshooting

### VS Code Issues

#### TypeScript Showing Errors

1. Reload VS Code: `Ctrl+Shift+P` → `Developer: Reload Window`
2. Check TypeScript version: `Ctrl+Shift+P` → `TypeScript: Select TypeScript Version...`
   - Should show workspace version from frontend
3. Restart TS Server: `Ctrl+Shift+P` → `TypeScript: Restart TS Server`

#### Python Environment Not Detected

1. Open a Python file in backend folder
2. Check status bar (bottom-right) for Python interpreter
3. Click and select: `.venv` interpreter from backend folder
4. Or use: `Ctrl+Shift+P` → `Python: Select Interpreter`

#### Extensions Not Working

1. Install recommended extensions when prompted
2. Or: `Ctrl+Shift+P` → `Extensions: Show Recommended Extensions`
3. Install all workspace recommendations

#### Terminal in Wrong Context

1. Click the `+` dropdown in terminal panel
2. Select the specific workspace folder
3. Or split terminal and select different folders

### Git Hooks Issues

#### Hooks Not Running

```bash
# Verify hooks path is set
git config core.hooksPath

# Should output: .githooks
# If not, run:
git config core.hooksPath .githooks
```

#### Hooks Failing

```bash
# Run checks manually to see detailed errors
make lint
make format
make test

# Fix issues and try again
```

#### Need to Bypass Hooks Temporarily

```bash
# Skip once
git commit --no-verify

# Or use environment variable
SKIP_HOOKS=true git commit
```

### Environment Variable Issues

#### Variables Not Taking Effect

```bash
# Check if variable is set
echo $BACKEND_PORT

# Set in current shell
export BACKEND_PORT=9000

# Or add to .env.local for persistence
echo "BACKEND_PORT=9000" >> .env.local
```

#### Port Already in Use

```bash
# Find and kill process using port
lsof -ti:8000 | xargs kill -9

# Or use different port
export BACKEND_PORT=8001
```

### Migration from Single-Root

If you previously had `.vscode/settings.json`:

1. Those settings are now in the workspace file
2. You can delete `.vscode/settings.json` (workspace overrides it)
3. Or keep it for user-specific settings not in the workspace

---

## Additional Resources

### VS Code Documentation

- [Multi-Root Workspaces](https://code.visualstudio.com/docs/editor/multi-root-workspaces)
- [TypeScript and VS Code](https://code.visualstudio.com/docs/languages/typescript)
- [Python in VS Code](https://code.visualstudio.com/docs/languages/python)
- [Vue with Volar](https://github.com/vuejs/language-tools)

### Project Documentation

- [Documentation Guide](DOCUMENTATION-GUIDE.md) - Complete documentation index
- [README.md](../README.md) - Project overview
- [CI Troubleshooting](CI-TROUBLESHOOTING.md) - CI/CD issues and solutions

---

**For New Team Members**: Welcome! After completing this guide, you're ready to start contributing. If you have questions, check the [Documentation Guide](DOCUMENTATION-GUIDE.md) or ask the team.

---

**Last Updated**: November 18, 2025  
**Maintained by**: Development Team  
**Status**: ✅ Current (Consolidated from WORKSPACE-SETUP.md, HOOKS-SETUP.md, ENVIRONMENT-CONFIG.md)
