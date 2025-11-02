# Multi-Process Backend Implementation

**Goal**: Multi-process backend with nginx routing (dev-only, no SSL)

```
Before: FastAPI (8000) → All modules
After:  Nginx (8000) → Broker (8001) + Datafeed (8002) + Core (8003)
```

**Status**: ✅ **Phase 4 COMPLETE** - Watch Mode Implemented

**Last Updated**: November 1, 2025 - Updated to reflect automatic WebSocket router generation (no separate watchers needed)

---

## ✅ Backend Manager - Unified CLI

**New unified script**: `backend/scripts/backend_manager.py`

Consolidates all multi-process backend management:

- ✅ Start/stop/restart multi-process backend
- ✅ Generate and validate nginx configuration
- ✅ Check status of running processes
- ✅ PID file tracking for all processes

**Commands**:

```bash
# Using Makefile (recommended)
make backend-manager-start              # Start backend (config=dev-config.yaml)
make backend-manager-stop               # Stop all processes
make backend-manager-status             # Show process status
make backend-manager-restart            # Restart all processes
make backend-manager-gen-nginx-conf     # Generate nginx config (debug)

# Log management (NEW)
make logs-tail                          # Tail unified log (all servers)
make logs-tail-nginx                    # Tail nginx logs only
make logs-clean                         # Truncate all log files

# Using script directly
poetry run python scripts/backend_manager.py start [config]
poetry run python scripts/backend_manager.py stop [config]
poetry run python scripts/backend_manager.py status [config]
poetry run python scripts/backend_manager.py restart [config]
poetry run python scripts/backend_manager.py gen-nginx-conf [config] -o [output]

# Examples
poetry run python scripts/backend_manager.py start dev-config.yaml
poetry run python scripts/backend_manager.py status
poetry run python scripts/backend_manager.py stop
poetry run python scripts/backend_manager.py restart dev-config.yaml --generate-nginx
poetry run python scripts/backend_manager.py gen-nginx-conf dev-config.yaml -o nginx-dev.conf --validate
```

**Removed scripts** (consolidated into backend-manager):

- `backend/scripts/run_multiprocess.py` - Removed (use `backend_manager.py start`)
- `backend/scripts/gen_nginx_conf.py` - Removed (use `backend_manager.py gen-nginx-conf`)

---

## ✅ Resolved: WebSocket Routing Mismatch

**Solution implemented**: Updated nginx config to use path-based routing (matches frontend)

- **Frontend URLs**: `/api/v1/broker/ws` and `/api/v1/datafeed/ws`
- **Nginx routing**: Path-based (`/api/v1/{module}/ws`)
- **Config updated**: `dev-config.yaml` uses `routing_strategy: "path"`
- **Status**: ✅ Configuration validated and working

---

## Prerequisites

### 1. Install nginx ✅ COMPLETE

**Nginx installation is now integrated into `make install`**:

```bash
# Install all dependencies (including optional nginx prompt)
cd backend && make install
```

The `make install` command will:

1. Check Python 3.11+ availability
2. Check Poetry installation
3. Install Python dependencies via Poetry
4. **Prompt to install nginx** (optional, for multi-process mode)

**Manual nginx installation** (if you skipped the prompt):

```bash
# Run backend manager with nginx generation
make backend-manager-start  # Will check for nginx and offer to install if needed
```

**Alternative (system install)**:

```bash
# Ubuntu/Debian/WSL
sudo apt update && sudo apt install nginx -y
```

### 2. Nginx verification integrated into backend-manager ✅ COMPLETE

Nginx verification is now handled automatically by the backend manager:

- **Start command**: Checks nginx availability before starting
- **Restart command**: Verifies nginx before restarting processes
- **Install target**: Prompts for nginx installation during `make install`

### 3. WebSocket routing strategy ✅ RESOLVED

- **Verified**: Frontend uses path-based routing (`/api/v1/broker/ws`, `/api/v1/datafeed/ws`)
- **Updated**: `dev-config.yaml` configured with `routing_strategy: "path"`
- **Implemented**: nginx generator supports path-based WebSocket routing

---

## Watch Mode Strategy ✅ IMPLEMENTED

**Philosophy**: Leverage Uvicorn's built-in watch mode with strategic pre-generation and lifecycle generation

### Architecture

We use a **two-phase generation strategy** to optimize development workflow:

1. **Pre-startup generation** (backend_manager): Generate specs and clients once before uvicorn starts
2. **Lifecycle generation** (app lifespan): Regenerate OpenAPI + per-module AsyncAPI specs on every app start/reload
3. **Automatic WS router generation**: Routers auto-generate during module loading (before app starts)
4. **Uvicorn's `--reload`**: Native file watching for code changes
5. **Exclude generated artifacts**: Prevent reload loops from spec/client generation
6. **Simple and reliable**: Fewer moving parts, less complexity

### Two-Phase Generation Strategy

**Phase 1: Pre-Startup (backend_manager.py)**

```
Before starting uvicorn:
1. Export OpenAPI spec (openapi.json) - all modules
2. Export AsyncAPI spec (asyncapi.json) - legacy format
3. Generate Python HTTP clients (src/trading_api/clients/)

Why: Ensures specs and clients are ready before server starts, no race conditions
```

**Phase 2: App Lifecycle (app_factory.py lifespan)**

```
Every app start/reload:
1. Validate response models
2. Generate OpenAPI spec (openapi.json) - for file-based watching
3. Generate per-module AsyncAPI specs (modules/{module}/specs/asyncapi.json)

Why: Keeps specs in sync with running app state, enables runtime consistency
Note: Python clients are NOT regenerated here (avoids race conditions with uvicorn)
```

**Phase 0: Module Loading (before app factory)**

```
During module initialization (ws.py files):
1. Auto-generate WebSocket routers from ws_generated/
2. Happens BEFORE uvicorn starts
3. No file watching needed

Why: Routers must exist before app loads them, automatic on every server start
```

### How It Works

**Initial Startup Sequence**:

```
1. Run: make backend-manager-start
2. backend_manager generates specs and clients (Phase 1)
3. backend_manager starts uvicorn with --reload and exclusions
4. App lifespan generates specs (Phase 2 - first run)
5. Server ready with fresh specs and clients
```

**Code Change Workflow**:

```
1. Developer modifies model in src/trading_api/models/ or ws.py handlers
2. Uvicorn detects .py file change
3. Uvicorn triggers reload
4. Module loading: WS routers auto-regenerate (if ws.py changed)
5. App lifespan regenerates OpenAPI + AsyncAPI specs (Phase 2)
6. Server ready with updated specs and routers (~2-3s)
7. Python clients: Manual regeneration via make generate-python-clients
8. Frontend clients: Manual regeneration via make generate-openapi-client
```

**Uvicorn Exclusion Patterns**:

```bash
--reload-exclude "*/openapi.json"      # Specs don't trigger reload
--reload-exclude "*/asyncapi.json"     # Specs don't trigger reload
--reload-exclude "*/clients/*"         # Generated HTTP clients don't trigger reload
--reload-exclude "*/scripts/*"         # Management scripts don't trigger reload
--reload-exclude "*/.local/*"          # Logs and runtime artifacts
--reload-exclude "*/.pids/*"           # PID files
--reload-exclude "*/__pycache__/*"     # Python cache
--reload-exclude "*.pyc"               # Compiled Python

Note: ws_generated/ is NOT excluded - WS routers auto-regenerate on module load
```

### Benefits

✅ **No separate watchers** - Uvicorn handles file watching  
✅ **Always fresh** - Specs and routers regenerated on every start  
✅ **No loops** - Exclusions prevent infinite reloads  
✅ **No race conditions** - Clients generated before uvicorn starts  
✅ **Fast feedback** - Changes detected instantly  
✅ **Simpler architecture** - Fewer processes to manage  
✅ **Reliable** - Built-in Uvicorn watching is battle-tested  
✅ **Runtime consistency** - Specs always match app state  
✅ **Automatic WS routers** - No manual generation needed

### What Gets Watched and What Doesn't

**Watched by Uvicorn** (triggers reload):

- `src/trading_api/**/*.py` - All Python source files (including ws.py handlers)
- `src/trading_api/**/ws_generated/**` - Generated WS routers (triggers reload but regenerate on startup)
- Model changes, API changes, WebSocket handler changes
- Anything that affects runtime behavior

**Excluded from Uvicorn** (no reload):

- `openapi.json`, `asyncapi.json` - Generated specs (regenerate in lifespan)
- `modules/*/specs/*.json` - Per-module AsyncAPI specs
- `src/trading_api/clients/**` - Generated Python HTTP clients
- `scripts/` - Backend management scripts
- `.local/`, `.pids/` - Runtime artifacts

**Auto-Generated on Module Load** (before reload loop):

- `src/trading_api/modules/*/ws_generated/**` - WebSocket routers
  - Generated during `ws.py` RouterFactory initialization
  - Happens BEFORE imports, no race conditions
  - Changes to ws.py trigger reload → routers regenerate → server starts

### Manual Client Generation

**Why not auto-generate clients on every reload?**

**Python clients:**

- Pre-generated before server starts (no race conditions)
- Used by tests, not by running server
- Manual regeneration gives explicit control
- Reduces reload overhead (client generation is slower than specs)
- Command: `make generate-python-clients`

**Frontend clients:**

- Frontend build is separate from backend reload
- Frontend has its own dev server with hot reload
- Explicit generation gives developer control
- Avoids cross-component coupling
- Command: `make generate-openapi-client`

### Developer Workflow

```bash
# Start backend (specs + clients pre-generated, then uvicorn starts)
make backend-manager-start

# Modify Python code → Uvicorn auto-reloads → Specs regenerated
vim src/trading_api/models/broker.py

# Modify WebSocket handlers → Uvicorn auto-reloads → Routers + Specs regenerated
vim src/trading_api/modules/broker/ws.py

# Manually regenerate Python clients (if needed)
make generate-python-clients

# Manually regenerate frontend clients (if needed)
cd frontend && make generate-openapi-client
```

### WebSocket Router Generation

WebSocket routers are **automatically generated** during module loading:

```python
# modules/{module}/ws.py - RouterFactory.__init__()
generate_module_routers(module_name)  # Creates ws_generated/
from .ws_generated import BarWsRouter  # Import succeeds!
```

**Manual generation** (optional, for debugging or fresh clone):

```bash
# Generate for all modules
make generate-ws-routers

# Generate for specific module
make generate-ws-routers module=broker
```

**Key Points**:

- ✅ Routers auto-generate on **every server start** (before imports)
- ✅ No file watching needed - happens during module initialization
- ✅ Changes to `ws.py` trigger uvicorn reload → routers regenerate → server starts
- ✅ Manual generation useful for pre-commit checks or CI/CD
- ✅ See `SYSTEMATIC_WS_ROUTER_GEN.md` for implementation details

---

## Implementation Phases

### Phase 1: Config Schema 🔧

**Commit**: "Add deployment config schema"  
**Time**: 3-4 hours

**Files**:

- `backend/dev-config.yaml`
- `backend/src/trading_api/shared/deployment/config_schema.py`
- `backend/src/trading_api/shared/deployment/__init__.py`
- `backend/tests/test_deployment_config.py`

**Key points**:

- PyYAML already in dependencies (no install needed)
- Port conflict validation critical
- Core server has empty modules list (common features only)

**Test**: `pytest tests/test_deployment_config.py -v`

---

### Phase 2: Nginx Generator 🔄 ✅ COMPLETE

**Commit**: "Add nginx config generator with standalone installer"  
**Time**: 5-6 hours (completed)

**Files**:

- ~~`backend/scripts/gen_nginx_conf.py`~~ ✅ (consolidated into backend_manager.py)
- `backend/scripts/install_nginx.py` ✅ (standalone nginx installer)
- `backend/dev-config.yaml` ✅ (updated with path-based routing)

**Key points**:

- ✅ Path-based WebSocket routing (`/api/v1/{module}/ws`)
- ✅ Standalone nginx installer (no sudo required)
- ✅ Auto-detects OS and architecture (Linux, macOS, Windows)
- ✅ Downloads from https://github.com/jirutka/nginx-binaries
- ✅ Local log paths (`backend/.local/logs/`)
- ✅ Uses local nginx binary if available, falls back to system nginx
- ✅ Upstreams created for all servers with instance scaling

**Test**:

```bash
# Install nginx
cd backend && make install-nginx

# Generate and validate config
poetry run python scripts/backend_manager.py gen-nginx-conf dev-config.yaml -o nginx-dev.conf --validate
```

**Validation Results**:

- ✅ nginx 1.28.0 installed successfully
- ✅ Configuration syntax valid
- ✅ WebSocket routing matches frontend URLs
- ✅ REST API routing configured correctly

---

### Phase 3: Server Manager 🏗️ ✅ COMPLETE

**Commit**: "Add backend-manager: unified CLI for multi-process management"
**Time**: Completed

**Files**:

- ✅ `backend/scripts/backend_manager.py` (unified CLI with nginx generation and server management)
- ❌ `backend/scripts/run_multiprocess.py` (REMOVED - consolidated)
- ❌ `backend/scripts/gen_nginx_conf.py` (REMOVED - consolidated)
- ❌ `backend/scripts/server_manager.py` (REMOVED - merged into backend_manager.py)

**Features**:

- ✅ Unified CLI with commands: start, stop, status, restart, gen-nginx-conf
- ✅ PID file tracking for all processes (nginx and backend instances)
- ✅ Status reporting with health checks
- ✅ Standalone stop/status commands (works without active manager instance)
- ✅ Port checking before startup
- ✅ Ordered shutdown: nginx → functional modules → core
- ✅ Timeout handling: Force kill after 3s (optimized from 10s)
- ✅ Auto-nginx config generation on start
- ✅ **Centralized logging with server prefixes** (NEW)
- ✅ **Detached background mode** - start returns immediately (NEW)
- ✅ **Fast stop/restart** - optimized shutdown with port release detection (NEW)

**Logging System**:

The backend manager now includes a centralized logging system:

- **Unified log file**: `backend/.local/logs/backend-unified.log` - Combined output from all servers
- **Individual logs**: `backend/.local/logs/{server-name}.log` - Per-server log files
- **Fixed-width prefixes**: Server names formatted to 20 characters for aligned log output
  ```
  broker-0          >> [INFO] Server started on port 8001
  datafeed-0        >> [INFO] Connecting to market data feed
  nginx             >> [INFO] Server listening on 0.0.0.0:8000
  ```
- **Real-time streaming**: Background threads stream output to both unified and individual logs
- **Detached mode**: Backend runs in background (like nohup), start command returns immediately

**Log Management Commands**:

```bash
# Tail all server logs with prefixes
make logs-tail

# Tail nginx logs only
make logs-tail-nginx

# Clean/truncate all log files (preserves files)
make logs-clean
```

**Performance Optimizations**:

- **Fast shutdown**: Reduced timeout from 10s to 3s with 0.05s polling intervals (~1 second total)
- **Fast restart**: Port release detection ensures clean restart without conflicts (~2 seconds total)
- **Detached startup**: Start command returns immediately, processes run in background

**Test**:

```bash
# Start backend (detached mode - returns immediately)
make backend-manager-start
# or: poetry run python scripts/backend_manager.py start

# Start in foreground mode (interactive)
poetry run python scripts/backend_manager.py start --foreground

# Check status
make backend-manager-status
# or: poetry run python scripts/backend_manager.py status

# Tail logs (all servers with prefixes)
make logs-tail

# Tail nginx logs only
make logs-tail-nginx

# Stop backend (fast - ~1 second)
make backend-manager-stop
# or: poetry run python scripts/backend_manager.py stop

# Restart backend (fast - ~2 seconds)
make backend-manager-restart
# or: poetry run python scripts/backend_manager.py restart

# Generate nginx config (debug)
make backend-manager-gen-nginx-conf
# or: poetry run python scripts/backend_manager.py gen-nginx-conf --validate

# Clean log files
make logs-clean

# Verify processes: ps aux | grep uvicorn
# Test shutdown: Ctrl+C (check no orphans)
```

**Checklist**:

- [x] All servers start successfully
- [x] Health checks respond on all ports
- [x] Graceful shutdown (no orphaned processes)
- [x] Core server stops last
- [x] Port pre-check prevents partial startup
- [x] Status command shows running processes
- [x] Stop command works from separate invocation
- [x] PID files properly cleaned up
- [x] **Unified logging with server prefixes** (NEW)
- [x] **Detached background mode** (NEW)
- [x] **Fast stop/restart with port release detection** (NEW)
- [x] **Log management commands** (logs-tail, logs-tail-nginx, logs-clean) (NEW)

---

### Phase 4: Watch Mode with Auto-Generation 👁️ ✅ COMPLETE

**Commit**: "Add startup auto-generation with Uvicorn watch mode"  
**Time**: ✅ **COMPLETE**

**Architecture**:

- ✅ **Leverage Uvicorn's built-in `--reload` mode** - native file watching for code changes
- ✅ **Auto-generate specs in FastAPI app startup** - part of lifespan event
- ✅ **Pre-generate clients before uvicorn starts** - handled by backend_manager
- ✅ **Exclude generated files from Uvicorn watchers** - prevents reload loops
- ✅ **Use `--reload-exclude` patterns** to ignore spec and client generation artifacts

**Implementation**:

1. **Pre-startup sequence** (in `backend_manager.py` before uvicorn):

   - Export OpenAPI spec (`openapi.json`)
   - Export AsyncAPI specs (per module in `modules/{module}/specs/asyncapi.json`)
   - Generate Python HTTP clients (`src/trading_api/clients/`)
   - This runs ONCE before starting uvicorn servers

2. **App startup sequence** (in `app_factory.py` lifespan event):

   - Validate response models for OpenAPI compliance
   - Generate OpenAPI spec (`openapi.json`)
   - Generate AsyncAPI specs (per module in `modules/{module}/specs/asyncapi.json`)
   - This runs EVERY time the FastAPI app starts (including on uvicorn reload)
   - Note: Python clients are NOT regenerated here (no race conditions with uvicorn)

3. **Uvicorn exclusion patterns** (in `backend_manager.py`):

   - `--reload-exclude "*/openapi.json"`
   - `--reload-exclude "*/asyncapi.json"`
   - `--reload-exclude "*/clients/*"`
   - `--reload-exclude "*/.local/*"`
   - `--reload-exclude "*/.pids/*"`
   - `--reload-exclude "*/scripts/*"`
   - `--reload-exclude "*/__pycache__/*"`
   - `--reload-exclude "*.pyc"`

4. **Developer workflow**:

   ```
   1. Start backend: make backend-manager-start
      → backend_manager generates specs and clients
      → Uvicorn starts with --reload and exclusions
      → App lifespan generates specs (for runtime consistency)

   2. Modify model in src/trading_api/models/
      → Uvicorn detects change, reloads server
      → App lifespan regenerates specs on reload
      → Clients: manual regeneration via make generate-python-clients

   3. Frontend gets fresh OpenAPI spec for client generation
      → Run: make generate-openapi-client (manual)
   ```

**Benefits**:

✅ **Uvicorn handles file watching** - no separate watcher processes needed  
✅ **Always fresh** - specs regenerated on every reload  
✅ **No loops** - exclusions prevent generated files from triggering reload  
✅ **No race conditions** - clients generated once before uvicorn starts  
✅ **Fast feedback** - changes detected and processed in ~2-3 seconds  
✅ **Simpler architecture** - generation is part of app lifecycle  
✅ **Reliable** - built-in Uvicorn watching is battle-tested

**Files Modified**:

- ✅ `backend/src/trading_api/app_factory.py` - Specs generated in lifespan startup
- ✅ `backend/scripts/backend_manager.py` - Pre-generates specs/clients + reload exclusions

**What Gets Watched**:

**Watched by Uvicorn** (triggers reload → app restart → spec regeneration):

- `src/trading_api/**/*.py` - All Python source files (except exclusions)
- Model changes, API changes, WebSocket changes
- Anything that affects runtime behavior

**Excluded from Uvicorn** (no reload trigger):

- `openapi.json`, `asyncapi.json` - Generated specs
- `src/trading_api/clients/**` - Generated Python clients
- `scripts/` - Management scripts
- `.local/`, `.pids/` - Runtime artifacts
- `__pycache__/`, `*.pyc` - Compiled Python

**Frontend Integration**:

Frontend client generation remains separate (not auto-triggered):

```bash
# Manual frontend client generation
cd frontend && make generate-openapi-client

# Or via project-level command
make -f project.mk generate-openapi-client
```

**Why not auto-generate frontend clients?**

- Frontend build is separate from backend reload
- Frontend has its own dev server with hot reload
- Explicit generation gives developer control
- Avoids cross-component coupling

**Why not auto-regenerate Python clients on reload?**

- Pre-generated before uvicorn starts (no race conditions)
- Clients are used by tests, not by running server
- Manual regeneration gives explicit control: `make generate-python-clients`
- Reduces reload overhead (specs are fast, client generation is slower)

**Test Results**:

```bash
# ✅ Specs and clients generated before first start (backend_manager)
# ✅ Specs regenerated on app startup (lifespan)
# ✅ Model changes trigger uvicorn reload
# ✅ Reload regenerates specs (lifespan)
# ✅ Spec changes do NOT trigger reload (excluded)
# ✅ Client changes do NOT trigger reload (excluded)
# ✅ Script changes do NOT trigger reload (excluded)
# ✅ No infinite reload loops
# ✅ Fast feedback (<3s from change to reload complete)
# ✅ No race conditions with client generation
```

**Verification**:

```bash
# Start backend and verify generation
make backend-manager-start
# Check logs: should see "Generating OpenAPI specification..."
#              "Generating AsyncAPI specification..."
#              "Generating Python HTTP clients..."
#              "📝 Generated OpenAPI spec: ..."
#              "📝 Generated AsyncAPI spec for 'broker': ..."

# Modify a model file
# Check logs: should see server reload
#             Should see "📝 Generated OpenAPI spec: ..." again

# Verify exclusions work (no reload loops)
# Touch a spec file: touch backend/openapi.json
# No reload should occur

# Stop backend
make backend-manager-stop
```

---

### Phase 5: Integration 🔗

**Commit**: "Integrate multi-process with workflows"  
**Time**: 3-4 hours

**Files**:

- `project.mk`
- `scripts/dev-fullstack.sh` (or create `dev-fullstack-multi.sh`)

**Key points**:

- Keep single-process mode as default (backward compatibility)
- Add `--multi` flag to dev script
- Ensure all existing tests pass

**Test**: `make -f project.mk dev-fullstack-multi` and verify full-stack operation

---

## Common Issues & Solutions

### Port already in use

```bash
# Find process
lsof -Pi :8000 -sTCP:LISTEN

# Kill if needed
kill -9 $(lsof -ti :8000)

# Or use backend manager restart (includes port release detection)
make backend-manager-restart
```

### Orphaned processes after crash

```bash
# Force cleanup
pkill -9 -f "uvicorn.*trading_api"
pkill -9 -f "nginx.*nginx-generated"

# Or use backend manager stop (includes PID cleanup)
make backend-manager-stop
```

### WebSocket routing fails

- Verify query parameter format in frontend
- Check nginx routing rules match WebSocket URL structure
- Test direct connection: `wscat -c ws://localhost:8000/api/v1/ws?type=orders`

### Logs not appearing

```bash
# Check if backend is running
make backend-manager-status

# Tail logs to see output
make logs-tail

# Check individual server logs
tail -f backend/.local/logs/broker-0.log

# Restart backend to reinitialize logging
make backend-manager-restart
```

### Restart fails with port conflicts

The backend manager includes automatic port release detection. If restart still fails:

```bash
# Stop backend
make backend-manager-stop

# Wait a moment for ports to release
sleep 1

# Start backend
make backend-manager-start
```

### Uvicorn not reloading on changes

**Symptoms**: File changes not triggering server reload

**Solutions**:

```bash
# 1. Check if reload is enabled (should see --reload in process)
make backend-manager-status
ps aux | grep uvicorn

# 2. Verify file is not excluded
# Check that changed file doesn't match exclusion patterns:
# - */openapi.json
# - */asyncapi.json
# - */clients/*  (Generated HTTP clients)
# - */scripts/*
# - */.local/*
# - */.pids/*
# Note: ws_generated/ is NOT excluded - routers regenerate on module load

# 3. Check file system events (Linux)
# Install inotify-tools if needed
sudo apt install inotify-tools

# Watch for file events
inotifywait -m -r backend/src/trading_api/

# 4. Restart with fresh reload
make backend-manager-restart
```

### Infinite reload loop

**Symptoms**: Server keeps reloading continuously

**Causes**:

- Generated files triggering reload (specs/clients)
- Log files being written in watched directories
- Temp files created during reload

**Solutions**:

```bash
# 1. Check exclusion patterns in backend_manager.py
grep "reload-exclude" backend/scripts/backend_manager.py

# Should see all exclusions:
# --reload-exclude */openapi.json
# --reload-exclude */asyncapi.json
# --reload-exclude */clients/*
# --reload-exclude */scripts/*
# --reload-exclude */.local/*
# --reload-exclude */.pids/*
# --reload-exclude */__pycache__/*
# --reload-exclude *.pyc

# 2. Verify no files being written to src/ during reload
make logs-tail
# Look for file write operations in src/ directory

# 3. Check if scripts are triggering reload
# Scripts should be excluded - verify in backend_manager.py
grep "scripts" backend/scripts/backend_manager.py
# Should see: --reload-exclude */scripts/*
```

### Specs not regenerating on reload

**Symptoms**: Stale specs after code changes and server reload

**Solutions**:

```bash
# 1. Check if lifespan event is running
make logs-tail
# Look for: "📝 Generated OpenAPI spec: ..."
#           "📝 Generated AsyncAPI spec for 'broker': ..."

# 2. Verify spec generation in app_factory.py
grep -A 20 "async def lifespan" backend/src/trading_api/app_factory.py

# 3. Test manual generation
cd backend
make export-openapi-spec
make export-asyncapi-spec

# 4. Restart backend to trigger fresh generation
make backend-manager-restart
```

### Clients not available after restart

**Symptoms**: Python clients missing or outdated after restart

**Solutions**:

```bash
# 1. Check if pre-generation ran (in backend_manager)
make logs-tail
# Look for: "Generating Python HTTP clients..."

# 2. Verify client files exist
ls -la backend/src/trading_api/clients/

# 3. Manually regenerate clients
cd backend
make generate-python-clients

# 4. Check backend_manager has generation call
grep "_generate_specs_and_clients" backend/scripts/backend_manager.py

# 5. Restart with verbose logging
cd backend
poetry run python scripts/backend_manager.py start --verbose
```

### Script changes triggering reload

**Symptoms**: Modifying backend management scripts triggers server reload

**Solution**:

```bash
# 1. Verify scripts exclusion is in place
grep "reload-exclude.*scripts" backend/scripts/backend_manager.py

# Should see: --reload-exclude */scripts/*

# 2. If not present, add to backend_manager.py uvicorn command:
# --reload-exclude */scripts/*

# 3. Restart backend
make backend-manager-restart
```

### WebSocket routers not regenerating

**Symptoms**: Changes to ws.py handlers not reflected in ws_generated/

**Solutions**:

```bash
# 1. Check if routers are being generated on module load
make logs-tail
# Look for generation messages during module loading

# 2. Manually regenerate routers (for debugging)
cd backend
make generate-ws-routers

# 3. Check for generation errors
make generate-ws-routers module=broker
# Look for syntax errors or import issues

# 4. Verify ws.py file has proper TypeAlias definitions
# RouterFactory looks for: TypeAlias = Annotated[...]

# 5. Restart backend to trigger fresh generation
make backend-manager-restart
```

### WebSocket router import errors

**Symptoms**: ImportError from ws_generated/ after code changes

**Solutions**:

```bash
# 1. Routers regenerate automatically on module load
# Just restart the backend:
make backend-manager-restart

# 2. If error persists, check router generation manually
cd backend
make generate-ws-routers module=broker

# 3. Look for syntax errors in generated code
cat src/trading_api/modules/broker/ws_generated/routers.py

# 4. Check quality checks pass
cd backend
poetry run python -c "
from trading_api.shared.ws.module_router_generator import generate_module_routers
result = generate_module_routers('broker', silent=False, skip_quality_checks=False)
print('Success!' if result else 'Failed!')
"
```

---

## Testing Checklist

### Phase 1

- [x] Config loads from YAML
- [x] Port conflict detection works
- [x] All tests pass

### Phase 2 ✅ COMPLETE

- [x] Generated config passes `nginx -t`
- [x] Upstreams include all servers
- [x] WebSocket routing matches frontend format (path-based)
- [x] Standalone nginx installer created
- [x] Local log paths configured
- [x] Config validated successfully

### Phase 3

- [x] All servers start successfully
- [x] Health checks respond on all ports
- [x] Graceful shutdown (no orphaned processes)
- [x] Core server stops last
- [x] Port pre-check prevents partial startup
- [x] Unified logging with server prefixes
- [x] Detached background mode
- [x] Fast stop (~1s) and restart (~2s)
- [x] Log management commands

**Status**: ✅ **COMPLETE** (All features implemented and tested)

### Phase 4 ✅ COMPLETE

- [x] Specs pre-generated before uvicorn starts (backend_manager)
- [x] Specs auto-generated on app startup (lifespan - OpenAPI + per-module AsyncAPI)
- [x] Python HTTP clients pre-generated before uvicorn starts
- [x] WebSocket routers auto-generate during module loading (before app starts)
- [x] Uvicorn reload excludes generated specs and clients
- [x] Model/handler changes trigger Uvicorn reload
- [x] App regenerates specs + WS routers on reload
- [x] Spec changes do NOT trigger reload
- [x] Client changes do NOT trigger reload
- [x] Script changes do NOT trigger reload
- [x] No infinite reload loops
- [x] Fast feedback (<3s from change to reload complete)
- [x] No race conditions with client or router generation
- [x] No separate file watchers for WebSocket routers

**Status**: ✅ **COMPLETE** (Watch mode with automatic generation fully implemented)

### Phase 5

- [ ] Multi-process mode works end-to-end
- [ ] Single-process mode still works
- [ ] All existing tests pass
- [ ] WebSockets work through nginx

**Status**: Not started (waiting for Phase 3 & 4)

---

## Progress Summary

**Phase 1: Config Schema** ✅ **COMPLETE**

- All files created and tested
- Tests passing (verified via `make test`)
- Port conflict validation working
- Files: `dev-config.yaml`, `config_schema.py`, `test_deployment_config.py`

**Phase 2: Nginx Generator** ✅ **COMPLETE**

- ✅ Nginx config generation integrated into backend_manager.py (Phase 2 logic consolidated)
- ✅ Standalone nginx installer integrated into `make install` (optional prompt)
- ✅ WebSocket routing fixed (path-based routing)
- ✅ Config validation passing (`nginx -t`)
- ✅ Local log paths configured
- ✅ Multi-platform support (Linux, macOS, Windows)

**Completed items:**

- Fixed WebSocket routing mismatch
- Installed nginx 1.28.0 standalone binary
- Generated valid nginx configuration
- Updated `dev-config.yaml` with path-based routing
- Verified configuration with `nginx -t`
- Integrated nginx installation into `make install`

**Phase 3: Server Manager** ✅ **COMPLETE**

- ✅ Backend manager with unified CLI (start, stop, status, restart)
- ✅ Process orchestration for multiple uvicorn instances
- ✅ PID file tracking for all processes
- ✅ Port conflict checking before startup
- ✅ Graceful shutdown handling (nginx → modules → core)
- ✅ Fast shutdown with 3s timeout (optimized from 10s)
- ✅ Auto-nginx config generation on start
- ✅ **Centralized logging system** (NEW)
- ✅ **Detached background mode** - start returns immediately (NEW)
- ✅ **Fast restart with port release detection** (~2s total) (NEW)
- ✅ **Log management Makefile targets** (NEW)

**Logging Features**:

- Unified log file: `backend/.local/logs/backend-unified.log`
- Individual server logs: `backend/.local/logs/{server-name}.log`
- Fixed-width 20-char server prefixes for aligned output
- Real-time log streaming via background threads
- Makefile commands: `logs-tail`, `logs-tail-nginx`, `logs-clean`

**Performance**:

- Start: Returns immediately (detached mode)
- Stop: ~1 second (3s timeout, 0.05s polling)
- Restart: ~2 seconds (includes port release detection)

**Files**:

- ✅ `backend/scripts/backend_manager.py` (unified CLI with nginx generation, server management, and logging)
- ❌ `backend/scripts/run_multiprocess.py` (REMOVED - consolidated)
- ❌ `backend/scripts/gen_nginx_conf.py` (REMOVED - consolidated)

**Phase 4: Watch Mode with Auto-Generation** ✅ **COMPLETE**

- ✅ Specs/clients pre-generated before uvicorn starts (backend_manager)
- ✅ Specs auto-generated in FastAPI lifespan (on every app start/reload)
- ✅ Uvicorn reload exclusion patterns configured (specs, clients, scripts, logs, pids, cache)
- ✅ Tested: specs regenerate on code changes via uvicorn reload
- ✅ Tested: generated files do NOT trigger reload loops
- ✅ Tested: no race conditions with client generation
- ✅ Fast feedback: <3s from change to reload complete

**Completed items:**

- Moved Python client generation to backend_manager (pre-startup)
- Kept spec generation in app_factory.py lifespan (for runtime consistency)
- Configured comprehensive reload exclusions
- Verified auto-regeneration on uvicorn reload
- Verified no infinite reload loops
- Verified scripts directory excluded from reload (prevents manager script changes from triggering reload)

**Phase 5: Integration** ❌ **NOT STARTED**

- Waiting for Phase 3 & 4
- Files to update:
  - `project.mk`
  - `scripts/dev-fullstack.sh`

---

## Next Steps

**Current**: Phase 4 Complete ✅ - Ready for Phase 5 (Integration)

**Phase 4 Achievements**:

- ✅ Three-phase generation strategy (module loading + pre-startup + lifecycle)
- ✅ Automatic WebSocket router generation on module load
- ✅ Uvicorn watch mode with comprehensive exclusions
- ✅ No race conditions with client or router generation
- ✅ Fast feedback (<3s reload cycle)
- ✅ Specs and routers always in sync with running app
- ✅ No infinite reload loops
- ✅ No separate file watchers needed
- ✅ Management scripts excluded from reload

**Phase 5: Integration** (Next):

1. **Update project-level Makefile** (`project.mk`):

   - Add multi-process targets
   - Keep single-process as default (backward compatibility)
   - Add `dev-fullstack-multi` target

2. **Update fullstack dev script** (`scripts/dev-fullstack.sh`):

   - Add `--multi` flag for multi-process mode
   - Default to single-process mode
   - Coordinate frontend + backend multi-process startup

3. **Ensure backward compatibility**:

   - Single-process mode must continue to work
   - All existing tests must pass
   - WebSocket functionality verified end-to-end

4. **End-to-end testing**:

   - Full-stack operation with nginx routing
   - WebSocket connections through nginx
   - Health checks across all servers
   - API requests through nginx gateway

5. **Documentation updates**:
   - Update relevant README files with multi-process instructions
   - Document watch mode behavior and workflows
   - Add troubleshooting guide for multi-process issues

---

## Summary

**Total time**: ~25 hours (3+ days)  
**Architecture**: Leverages existing modular backend with `ENABLED_MODULES`  
**Watch Mode**: Uvicorn built-in reload with startup auto-generation  
**Risk level**: Low - no critical blockers identified  
**Rollback**: Keep single-process as default, multi-process opt-in

**Order**: Config → Nginx → Server Manager → Watch Mode → Integration

Each phase is independent, committable, and reversible.
