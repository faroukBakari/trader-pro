# Full-Stack Development Mode

**Last Updated:** November 11, 2025

## Overview

The full-stack development mode (`make dev-fullstack`) provides an integrated development environment with automatic code generation, hot-reloading, and synchronized backend-frontend updates.

**Note**: This mode runs the backend in **single-process mode** with all modules in one Uvicorn process for simplicity and faster iteration. For production-like multi-process deployment with nginx gateway, see [backend/docs/BACKEND_MANAGER_GUIDE.md](../backend/docs/BACKEND_MANAGER_GUIDE.md).

## Quick Start

```bash
# Start full-stack development environment
make dev-fullstack

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000/api/docs
# Python Debugger: localhost:5678
```

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│            Dev Fullstack (3 Main Processes)              │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼──────────────┐
        ▼                 ▼              ▼
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Backend  │────▶│  Spec    │────▶│ Frontend │
  │   Dev    │     │ Watcher  │     │   Dev    │
  └──────────┘     └──────────┘     └──────────┘
   PID tracked      PID tracked      PID tracked
        │                 │              │
   make -C backend   watch_specs()  make -C frontend
        dev          function            dev
        │                 │              │
        ▼                 ▼              ▼
  Auto-generates    Watches specs    Auto-reloads on
  specs on change   → triggers        client changes
                    client regen
```

### Process Hierarchy

```
make dev-fullstack
  └─ scripts/dev-fullstack.sh
       ├─ Process 1: Backend Dev Server [PID tracked]
       │   └─ make -C backend dev
       │       └─ Uvicorn + debugpy (auto-generates specs)
       │
       ├─ Process 2: Spec Watcher [PID tracked]
       │   └─ watch_specs() function
       │       ├─ Watches backend/openapi.json
       │       └─ Watches backend/asyncapi.json
       │       └─ Triggers frontend client regeneration
       │
       └─ Process 3: Frontend Dev Server [PID tracked]
           └─ make -C frontend dev
               └─ Vite HMR (auto-reloads on client changes)
```

### Watch Chain Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Development Watch Chain                      │
└─────────────────────────────────────────────────────────────────┘

Backend Python File Change
   ↓
1. Uvicorn --reload detects change
   ↓
2. Backend restarts
   ↓
3. FastAPI lifespan event triggers
   ↓
4. app.gen_module_specs_and_clients() executes
   ↓
5. Backend regenerates specs:
   - backend/openapi.json
   - backend/asyncapi.json
   - backend/src/trading_api/modules/*/specs_generated/*
   ↓
6. Spec watcher detects change (content-based)
   ↓
7. Watcher triggers frontend client regeneration:
   - make generate-openapi-client (if openapi.json changed)
   - make generate-asyncapi-types (if asyncapi.json changed)
   ↓
8. Frontend clients updated:
   - frontend/src/clients_generated/*/
   ↓
9. Vite HMR detects client file changes
   ↓
10. Browser hot-reloads automatically

Frontend File Change (TypeScript/Vue)
   ↓
Vite HMR detects change
   ↓
Browser hot-reloads (no full refresh)
```

### Key Design Principles

1. **Backend Autonomy** - Backend generates its own specs on startup and file changes
2. **Frontend Reactivity** - Frontend auto-reloads when generated clients change (Vite HMR)
3. **Watcher as Bridge** - Spec watcher bridges backend specs → frontend client regeneration
4. **No Circular Dependencies** - One-way flow prevents double-regeneration
5. **Clean State** - All generated artifacts cleaned before starting

## Startup Sequence

### Phase 0: Pre-flight Checks

```bash
# Port availability check
- Backend port 8000 must be free
- Frontend port 5173 must be free
# Exits immediately if ports are blocked
```

**Purpose:** Prevents startup failures and port conflicts.

### Phase 1: Clean All Generated Artifacts

```bash
# Clean backend generated files
make -C backend clean-generated
  └─ Removes all *_generated* files/directories
     - backend/openapi.json
     - backend/asyncapi.json
     - backend/src/trading_api/modules/*/specs_generated/
     - backend/src/trading_api/modules/*/ws_generated/

# Clean frontend generated files
make -C frontend clean-generated
  └─ Removes all generated clients
     - frontend/src/clients_generated/*
     - frontend/dist/
     - frontend/node_modules/.vite/
```

**Purpose:** Ensures clean state, prevents stale artifacts from causing issues.

**Why this matters:**

- Old generated files can cause type mismatches
- Stale specs can lead to inconsistent behavior
- Clean slate ensures synchronization between backend and frontend

### Phase 2: Start Backend Server (Process 1)

```bash
make -C backend dev
  ↓
poetry run python -m debugpy --listen 0.0.0.0:5678 \
  -m uvicorn "trading_api.main:app" \
  --reload \
  --reload-exclude '**/ws_generated/*' \
  --reload-exclude '**/.local/*' \
  --reload-exclude '**/scripts/*' \
  --host 0.0.0.0 \
  --port 8000
```

**Features:**

- 🐛 **Debugpy** on port 5678 for VS Code debugging
- 🔄 **Auto-reload** on Python file changes
- 📋 **Excludes** generated files from reload triggers
- 🔧 **Auto-generates specs** on startup via lifespan event

**Backend Initialization:**

1. FastAPI lifespan event triggers
2. Validates all routes have `response_model`
3. Calls `app.gen_module_specs_and_clients()`
4. Generates `backend/openapi.json` and `backend/asyncapi.json`
5. Starts all modules

**Wait Time:** 5 seconds (allows backend to stabilize and generate specs)

### Phase 3: Start Spec Watcher (Process 2)

```bash
watch_specs() {
    # Unified function watching both specs

    # Initialize baseline state
    OPENAPI_FILE="backend/openapi.json"
    ASYNCAPI_FILE="backend/asyncapi.json"
    OPENAPI_LAST_CONTENT=$(cat "$OPENAPI_FILE" 2>/dev/null || echo "")
    ASYNCAPI_LAST_CONTENT=$(cat "$ASYNCAPI_FILE" 2>/dev/null || echo "")

    # Watch loop (1 second interval)
    while true; do
        # Check OpenAPI spec
        if [ -f "$OPENAPI_FILE" ]; then
            CURRENT_CONTENT=$(cat "$OPENAPI_FILE")
            if [ "$CURRENT_CONTENT" != "$OPENAPI_LAST_CONTENT" ]; then
                make -C frontend generate-openapi-client
                OPENAPI_LAST_CONTENT="$CURRENT_CONTENT"
            fi
        fi

        # Check AsyncAPI spec
        if [ -f "$ASYNCAPI_FILE" ]; then
            CURRENT_CONTENT=$(cat "$ASYNCAPI_FILE")
            if [ "$CURRENT_CONTENT" != "$ASYNCAPI_LAST_CONTENT" ]; then
                make -C frontend generate-asyncapi-types
                ASYNCAPI_LAST_CONTENT="$CURRENT_CONTENT"
            fi
        fi

        sleep 1
    done
}
```

**Features:**

- 📊 **Content-Based Detection** - Prevents false positives from timestamp-only checks
- ⚡ **1-Second Polling** - Fast enough for dev, simple and portable
- 🔄 **Triggers Frontend Regeneration** - Only when actual content changes

**Why Content-Based Detection?**

- Backend restart may touch files without changing content
- Prevents unnecessary client regeneration
- Reduces CPU usage and Vite HMR noise

### Phase 4: Start Frontend Server (Process 3)

```bash
make -C frontend dev
  ↓
npm run dev  # Vite development server
```

**Features:**

- ⚡ **Vite HMR** (Hot Module Replacement)
- 🔄 **Auto-reload** on TypeScript/Vue file changes
- 📦 **Auto-reload on client changes** - Detects generated client updates
- 📱 **Port 5173** with CORS configured

**Frontend Initialization:**

1. Vite starts development server
2. Loads existing generated clients (if any)
3. Watches for file changes (including generated clients)
4. Hot-reloads browser on any change

### Phase 5: Process Monitoring

```bash
# Monitor all three processes
while true; do
    # Check backend (Process 1)
    if ! is_process_running "$BACKEND_PID"; then
        print_error "Backend process exited unexpectedly!"
        exit 1
    fi

    # Check spec watcher (Process 2)
    if ! is_process_running "$WATCHER_PID"; then
        print_error "Spec watcher exited unexpectedly!"
        exit 1
    fi

    # Check frontend (Process 3)
    if ! is_process_running "$FRONTEND_PID"; then
        print_error "Frontend process exited unexpectedly!"
        exit 1
    fi

    sleep 1
done
```

**Purpose:** Exits immediately if any critical process dies, preventing zombie states.

## Environment Variables

| Variable        | Default                 | Description                  |
| --------------- | ----------------------- | ---------------------------- |
| `BACKEND_PORT`  | `8000`                  | Backend server port          |
| `FRONTEND_PORT` | `5173`                  | Frontend dev server port     |
| `VITE_API_URL`  | `http://localhost:8000` | Backend API URL for frontend |
| `FRONTEND_URL`  | `http://localhost:5173` | Frontend URL                 |

## Process Management

### Three Tracked Processes

```bash
BACKEND_PID=""    # Process 1: make -C backend dev
WATCHER_PID=""    # Process 2: watch_specs function
FRONTEND_PID=""   # Process 3: make -C frontend dev
```

**Why Three Processes?**

- **Simplicity** - Clear separation of concerns
- **Debuggability** - Easy to identify which process failed
- **Clean Shutdown** - Deterministic cleanup order

### Process Group Tracking

```bash
# Script creates its own process group
set -m
SCRIPT_PGID=$$

# All child processes inherit this group
# Enables clean shutdown of entire process tree
```

### Cleanup on Exit (Ctrl+C or Error)

```bash
cleanup() {
    print_step "🛑 Shutting down full-stack development environment..."

    # Step 1: Kill tracked processes with SIGTERM (graceful)
    # Order: Frontend → Watcher → Backend (dependency order)

    if [ ! -z "$FRONTEND_PID" ]; then
        print_step "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill_process_tree "$FRONTEND_PID" "TERM"
    fi

    if [ ! -z "$WATCHER_PID" ]; then
        print_step "Stopping spec watcher (PID: $WATCHER_PID)..."
        kill_process_tree "$WATCHER_PID" "TERM"
    fi

    if [ ! -z "$BACKEND_PID" ]; then
        print_step "Stopping backend server (PID: $BACKEND_PID)..."
        kill_process_tree "$BACKEND_PID" "TERM"
    fi

    # Step 2: Wait for graceful shutdown
    sleep 2

    # Step 3: Kill remaining process group members
    print_step "Cleaning up any remaining processes..."
    for pid in $(get_process_group_pids); do
        kill -TERM $pid 2>/dev/null || true
    done

    # Step 4: Force kill stubborn processes
    sleep 2
    for pid in $(get_process_group_pids); do
        kill -KILL $pid 2>/dev/null || true
    done

    print_success "All processes stopped. Environment cleaned up."
}

trap cleanup EXIT INT TERM
```

**Features:**

- 🎯 **Three Clear Targets** - Backend, Watcher, Frontend
- 🌳 **Recursive Tree Kill** - Handles daemon forks and child processes
- 🛑 **Graceful Shutdown** - SIGTERM first, allows cleanup
- 💀 **Force Kill Fallback** - SIGKILL for stubborn processes
- 🧹 **No Orphans** - Process group cleanup catches stragglers

## Debugging

### Backend Python Debugging

**VS Code Configuration (`.vscode/launch.json`):**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Attach to Backend",
      "type": "debugpy",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/backend",
          "remoteRoot": "."
        }
      ]
    }
  ]
}
```

**Usage:**

1. Start dev-fullstack: `make dev-fullstack`
2. In VS Code: Run → Start Debugging → "Attach to Backend"
3. Set breakpoints in Python files
4. Make requests to trigger breakpoints

### Frontend Debugging

**Browser DevTools:**

- TypeScript source maps enabled automatically
- Original source files visible in debugger
- Hot reload preserves debugging session

**VS Code Debugging:**

- Install "Vite" extension
- Use browser debugging with source maps

### Spec Watcher Debugging

**View Watcher Output:**

The watcher function (`watch_specs`) runs as Process 2 and outputs to the terminal:

```bash
⚠️  OpenAPI file changed! Regenerating REST client...
✅ Frontend REST client regenerated successfully

⚠️  AsyncAPI file changed! Regenerating WebSocket types...
✅ Frontend WebSocket types regenerated successfully
```

**Manual Verification:**

```bash
# Check if specs exist
ls -lh backend/openapi.json backend/asyncapi.json

# Verify client generation
ls -lh frontend/src/clients_generated/

# Test watcher function manually
cd /path/to/trader-pro
source scripts/dev-fullstack.sh  # Load the watch_specs function
watch_specs  # Run watcher manually
```

**Common Watcher Issues:**

| Issue                               | Cause                           | Solution                                       |
| ----------------------------------- | ------------------------------- | ---------------------------------------------- |
| Watcher not detecting changes       | Content hasn't actually changed | Check file hash: `md5sum backend/openapi.json` |
| False positives (too many triggers) | Using timestamp-only detection  | Verify content-based detection is active       |
| Watcher exited unexpectedly         | Syntax error in function        | Check terminal output for errors               |

## Troubleshooting

### Port Already in Use

**Error:**

```
❌ Backend port 8000 is already in use!
```

**Solutions:**

```bash
# Option 1: Kill existing process
make kill-dev

# Option 2: Use different port
export BACKEND_PORT=8001
make dev-fullstack

# Option 3: Find and kill manually
lsof -ti :8000 | xargs kill -9
```

### Backend Won't Start

**Check:**

```bash
# Verify Python environment
cd backend
poetry env info

# Verify dependencies
poetry install

# Check for Python errors
poetry run python -m trading_api.main
```

### Frontend Clients Not Regenerating

**Debug:**

```bash
# Check if specs exist
ls backend/*.json

# Manually trigger generation
make generate-openapi-client
make generate-asyncapi-types

# Check watcher logs (in dev-fullstack terminal)
# Look for "file changed" messages
```

### Changes Not Reflected

**Backend changes:**

```bash
# Check Uvicorn reload is working
# Terminal should show: "Detected file change, reloading..."

# Verify excluded paths (these WON'T trigger reload):
# - backend/src/trading_api/modules/*/ws_generated/*
# - backend/.local/*
# - backend/scripts/*
```

**Frontend changes:**

```bash
# Vite should show HMR update in terminal
# Check browser console for HMR messages
```

## File Structure

### Generated Files

```
backend/
├── openapi.json              # Merged OpenAPI spec (all modules)
├── asyncapi.json             # Merged AsyncAPI spec (all WebSockets)
└── src/trading_api/modules/
    ├── broker/
    │   └── specs_generated/
    │       ├── broker_openapi.json
    │       ├── broker_asyncapi.json
    │       └── rest_generated/  # Python REST client
    └── datafeed/
        └── specs_generated/
            ├── datafeed_openapi.json
            ├── datafeed_asyncapi.json
            └── rest_generated/  # Python REST client

frontend/
└── src/
    └── clients_generated/
        ├── broker_rest/        # TypeScript REST client
        ├── broker_ws/          # TypeScript WS types
        ├── datafeed_rest/      # TypeScript REST client
        └── datafeed_ws/        # TypeScript WS types
```

### Excluded from Watch

**Backend (`--reload-exclude`):**

- `**/ws_generated/*` - Generated WebSocket routers
- `**/.local/*` - Local nginx/logs
- `**/.pids/*` - Process ID files
- `**/scripts/*` - Python scripts
- `**/__pycache__/*` - Python cache
- `**/*.pyc` - Compiled Python

**Frontend (Vite default excludes):**

- `node_modules/`
- `.git/`
- `dist/`

## Performance Optimization

### Current Implementation

- ✅ Content-based change detection (no false positives)
- ✅ Excludes generated files from reload triggers
- ✅ Parallel process execution
- ✅ 1-second polling interval (acceptable for dev)

### Potential Improvements

#### 1. Event-Driven Watching (inotifywait)

```bash
# Install: sudo apt install inotify-tools

# Replace polling with events
inotifywait -m -e modify,close_write backend/openapi.json | \
while read; do
    make generate-openapi-client
done
```

**Benefits:**

- Instant change detection
- No CPU waste on polling
- More responsive

**Trade-offs:**

- Requires system package installation
- Linux-specific (not portable to macOS/Windows)

#### 2. Debouncing

```bash
# Prevent rapid regeneration during backend restart
LAST_REGEN=0
DEBOUNCE_SECONDS=2

if file_changed && time_since_last_regen > $DEBOUNCE_SECONDS; then
    regenerate_client
    LAST_REGEN=$(date +%s)
fi
```

**Benefits:**

- Prevents duplicate regeneration
- Reduces CPU usage during rapid changes

#### 3. Smart Health Check

```bash
# Replace sleep 5 with actual health polling
wait_for_backend() {
    for i in {1..30}; do
        if curl -f -s http://localhost:8000/api/docs >/dev/null 2>&1; then
            echo "Backend ready after ${i}s"
            return 0
        fi
        sleep 1
    done
    return 1
}
```

**Benefits:**

- Faster startup when backend is quick
- More reliable than fixed delay

## Integration with CI/CD

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
- name: Start Backend for Tests
  run: make -C backend dev-ci

- name: Generate Frontend Clients
  run: make generate

- name: Run Frontend Tests
  run: make -C frontend test

- name: Stop Backend
  run: make -C backend kill-dev
```

**Differences from dev-fullstack:**

- Uses `dev-ci` instead of `dev` (no debugpy, runs in background)
- No file watchers (one-time generation)
- Health checks before proceeding

## Related Documentation

- [Backend Testing](../backend/docs/BACKEND_TESTING.md) - Backend test setup
- [API Methodology](../API-METHODOLOGY.md) - REST API patterns
- [WebSocket Methodology](../WEBSOCKET-METHODOLOGY.md) - WebSocket patterns
- [Client Generation](CLIENT-GENERATION.md) - OpenAPI/AsyncAPI client generation
- [Makefile Guide](../MAKEFILE-GUIDE.md) - All available make targets

## Common Workflows

### Add New Backend Endpoint

1. Create endpoint in module (e.g., `backend/src/trading_api/modules/broker/api/v1/routes.py`)
2. Save file → Uvicorn restarts automatically
3. Specs regenerate automatically
4. Frontend client updates automatically
5. Use new endpoint in frontend (TypeScript autocomplete available)

### Add New WebSocket Message

1. Define message in module (e.g., `broker/ws/v1/messages.py`)
2. Save file → Backend restarts
3. AsyncAPI spec updates
4. Frontend WebSocket types regenerate
5. Use new message types in frontend

### Debug Backend Issue

1. Start dev-fullstack: `make dev-fullstack`
2. Attach VS Code debugger (port 5678)
3. Set breakpoints
4. Make request from frontend or API docs
5. Step through code

### Test Full Flow

1. Start dev-fullstack: `make dev-fullstack`
2. Make backend change → verify specs update
3. Check frontend client regeneration logs
4. Verify browser auto-refreshes
5. Test new functionality

## Best Practices

### Do's ✅

- Use `make dev-fullstack` for integrated development
- Let watchers handle regeneration automatically
- Use debugpy for backend debugging
- Check terminal output for regeneration messages
- Use `make kill-dev` to stop cleanly

### Don'ts ❌

- Don't run backend/frontend separately (use dev-fullstack)
- Don't manually regenerate clients (watchers do it)
- Don't edit generated files (they'll be overwritten)
- Don't kill processes with `kill -9` directly (use make kill-dev)
- Don't commit generated files (they're in .gitignore)

## FAQ

**Q: Why does the backend generate specs on every restart?**  
A: Backend autonomously generates specs via FastAPI lifespan events. This ensures specs are always in sync with the code.

**Q: Can I disable the spec watcher?**  
A: Not recommended. The watcher is the bridge between backend specs and frontend clients. Without it, frontend clients won't update automatically.

**Q: How do I add a new module?**  
A: Create module in `backend/src/trading_api/modules/`, restart dev-fullstack. Auto-discovery handles the rest.

**Q: Why use content-based detection instead of timestamp?**  
A: Backend restart may touch files without changing content. Content comparison prevents false regeneration and unnecessary Vite HMR triggers.

**Q: What happens if I delete generated files while running?**  
A: Backend will regenerate specs on next file change. Watcher will detect and trigger frontend client regeneration. System self-heals.

**Q: Can I run multiple instances?**  
A: Yes, use different ports:

```bash
BACKEND_PORT=8001 FRONTEND_PORT=5174 make dev-fullstack
```

**Q: How do I clean everything and restart?**  
A:

```bash
make kill-dev
make -f project.mk clean-all
make dev-fullstack
```

**Q: Why three separate processes instead of more?**  
A: Three processes provide the perfect balance:

- **Process 1 (Backend):** Self-contained, generates specs
- **Process 2 (Watcher):** Bridge between backend and frontend
- **Process 3 (Frontend):** Self-contained, consumes generated clients

More processes would add complexity without benefit.
