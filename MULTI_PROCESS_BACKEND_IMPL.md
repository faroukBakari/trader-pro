# Multi-Process Backend Implementation

**Goal**: Multi-process backend with nginx routing (dev-only, no SSL)

```
Before: FastAPI (8000) → All modules
After:  Nginx (8000) → Broker (8001) + Datafeed (8002) + Core (8003)
```

**Status**: ✅ **Phase 2 COMPLETE** - Ready for Phase 3

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

- `backend/scripts/gen_nginx_conf.py` ✅
- `backend/scripts/install_nginx.py` ✅ (NEW - standalone nginx installer)
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
poetry run python scripts/gen_nginx_conf.py dev-config.yaml -o nginx-dev.conf --validate
```

**Validation Results**:

- ✅ nginx 1.28.0 installed successfully
- ✅ Configuration syntax valid
- ✅ WebSocket routing matches frontend URLs
- ✅ REST API routing configured correctly

---

### Phase 3: Server Manager 🏗️

**Commit**: "Add multi-process server manager"  
**Time**: 6-8 hours (most complex)

**Files**:

- `backend/src/trading_api/shared/deployment/server_manager.py`
- `backend/scripts/run_multiprocess.py`

**Critical enhancements**:

1. **Port checking before startup**:

```python
def check_all_ports(config):
    blocked = []
    for name, server in config.servers.items():
        for i in range(server.instances):
            port = server.port + i
            if is_port_in_use(port):
                blocked.append((f"{name}-{i}", port))
    return len(blocked) == 0
```

2. **Ordered shutdown**: nginx → functional modules → core
3. **Timeout handling**: Force kill after 10s

**Test**:

```bash
cd backend && make run config=dev-config.yaml
# Verify processes: ps aux | grep uvicorn
# Test shutdown: Ctrl+C (check no orphans)
```

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

- ✅ Nginx config generator created (`gen_nginx_conf.py`)
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
