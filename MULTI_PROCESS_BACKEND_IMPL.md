# Multi-Process Backend Implementation

**Goal**: Multi-process backend with nginx routing (dev-only, no SSL)

```
Before: FastAPI (8000) → All modules
After:  Nginx (8000) → Broker (8001) + Datafeed (8002) + Core (8003)
```

**Status**: ✅ **Phase 3 COMPLETE** - Backend Manager Consolidated

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

**Standalone nginx installer** (no sudo required):

```bash
# Install nginx binary to backend/.local/bin/
cd backend && make install-nginx

# Verify installation
make check-nginx
```

**Alternative (system install)**:

```bash
# Ubuntu/Debian/WSL
sudo apt update && sudo apt install nginx -y
```

### 2. Nginx verification added to Makefile ✅ COMPLETE

```makefile
# backend/Makefile
install-nginx:  # Install standalone nginx binary
check-nginx:    # Check if nginx is installed (local or system)
verify-nginx:   # Verify nginx is available
```

### 3. WebSocket routing strategy ✅ RESOLVED

- **Verified**: Frontend uses path-based routing (`/api/v1/broker/ws`, `/api/v1/datafeed/ws`)
- **Updated**: `dev-config.yaml` configured with `routing_strategy: "path"`
- **Implemented**: nginx generator supports path-based WebSocket routing

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

- ✅ `backend/scripts/backend_manager.py` (NEW - unified CLI with nginx generation)
- ✅ `backend/src/trading_api/shared/deployment/server_manager.py` (enhanced with status/PID tracking)
- ❌ `backend/scripts/run_multiprocess.py` (REMOVED - consolidated)
- ❌ `backend/scripts/gen_nginx_conf.py` (REMOVED - consolidated)

**Features**:

- ✅ Unified CLI with commands: start, stop, status, restart, gen-nginx-conf
- ✅ PID file tracking for all processes (nginx and backend instances)
- ✅ Status reporting with health checks
- ✅ Standalone stop/status commands (works without active manager instance)
- ✅ Port checking before startup
- ✅ Ordered shutdown: nginx → functional modules → core
- ✅ Timeout handling: Force kill after 10s
- ✅ Auto-nginx config generation on start

**Test**:

```bash
# Start backend
make backend-manager-start
# or: poetry run python scripts/backend_manager.py start

# Check status
make backend-manager-status
# or: poetry run python scripts/backend_manager.py status

# Stop backend
make backend-manager-stop
# or: poetry run python scripts/backend_manager.py stop

# Restart backend
make backend-manager-restart
# or: poetry run python scripts/backend_manager.py restart

# Generate nginx config (debug)
make backend-manager-gen-nginx-conf
# or: poetry run python scripts/backend_manager.py gen-nginx-conf --validate

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

---

### Phase 4: Spec Watchers 👁️

**Commit**: "Add spec watchers with client generation"  
**Time**: 4-5 hours

**Files**:

- `backend/scripts/watch_specs_frontend.py`
- `backend/scripts/watch_specs_python.py`

**Key points**:

- Debouncing via `_gen` flag prevents infinite loops
- Python watcher must detect its own spec changes
- Frontend watcher triggers `make generate-clients`

**Test**: `make watch-specs-frontend` in separate terminal, modify model

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
```

### Orphaned processes after crash

```bash
# Force cleanup
pkill -9 -f "uvicorn.*trading_api"
pkill -9 -f "nginx.*nginx-generated"
```

### WebSocket routing fails

- Verify query parameter format in frontend
- Check nginx routing rules match WebSocket URL structure
- Test direct connection: `wscat -c ws://localhost:8000/api/v1/ws?type=orders`

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

- [ ] All servers start successfully
- [ ] Health checks respond on all ports
- [ ] Graceful shutdown (no orphaned processes)
- [ ] Core server stops last
- [ ] Port pre-check prevents partial startup

**Status**: Ready to start (Phase 2 complete)

### Phase 4

- [ ] Frontend client regenerates on spec change
- [ ] Python client regenerates without loops
- [ ] Changes detected within 2s

**Status**: Not started (waiting for Phase 3)

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
- ✅ Standalone nginx installer created (`install_nginx.py`)
- ✅ WebSocket routing fixed (path-based routing)
- ✅ Config validation passing (`nginx -t`)
- ✅ Makefile targets added (`install-nginx`, `check-nginx`, `verify-nginx`)
- ✅ Local log paths configured
- ✅ Multi-platform support (Linux, macOS, Windows)

**Completed items:**

- Fixed WebSocket routing mismatch
- Installed nginx 1.28.0 standalone binary
- Generated valid nginx configuration
- Updated `dev-config.yaml` with path-based routing
- Verified configuration with `nginx -t`

**Phase 3: Server Manager** ❌ **NOT STARTED**

- Ready to implement (no blockers)
- Files needed:
  - `backend/src/trading_api/shared/deployment/server_manager.py`
  - `backend/scripts/run_multiprocess.py`

**Phase 4: Spec Watchers** ❌ **NOT STARTED**

- Waiting for Phase 3
- Files needed:
  - `backend/scripts/watch_specs_frontend.py`
  - `backend/scripts/watch_specs_python.py`

**Phase 5: Integration** ❌ **NOT STARTED**

- Waiting for Phase 3 & 4
- Files to update:
  - `project.mk`
  - `scripts/dev-fullstack.sh`

---

## Next Steps

**Current**: Ready to implement Phase 3 (Server Manager)

1. **Implement Server Manager** (`backend/src/trading_api/shared/deployment/server_manager.py`):

   - Process orchestration for multiple uvicorn instances
   - Port conflict checking before startup
   - Graceful shutdown handling (nginx → modules → core)
   - Timeout handling with force kill after 10s

2. **Create Multi-Process Runner** (`backend/scripts/run_multiprocess.py`):

   - CLI interface for starting multi-process mode
   - Integration with server manager
   - Process monitoring and health checks

3. **Test Server Manager**:

   ```bash
   cd backend && python scripts/run_multiprocess.py dev-config.yaml
   # Verify all processes start
   # Test graceful shutdown with Ctrl+C
   ```

4. **Complete Phase 3 checklist** before moving to Phase 4

---

## Summary

**Total time**: ~28 hours (3.5-4 days)  
**Architecture**: Leverages existing modular backend with `ENABLED_MODULES`  
**Risk level**: Low - no critical blockers identified  
**Rollback**: Keep single-process as default, multi-process opt-in

**Order**: Config → Nginx → Server Manager → Watchers → Integration

Each phase is independent, committable, and reversible.
