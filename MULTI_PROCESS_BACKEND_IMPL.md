# Multi-Process Backend Implementation

**Goal**: Multi-process backend with nginx routing (dev-only, no SSL)

```
Before: FastAPI (8000) → All modules
After:  Nginx (8000) → Broker (8001) + Datafeed (8002) + Core (8003)
```

**Status**: ✅ Ready for implementation - No critical blockers

---

## Prerequisites

### 1. Install nginx

```bash
# Ubuntu/Debian/WSL
sudo apt update && sudo apt install nginx -y

# Verify
nginx -v
```

### 2. Add nginx verification to Makefile

```makefile
# backend/Makefile
verify-nginx:
	@if ! command -v nginx >/dev/null 2>&1; then \
		echo "❌ nginx not found! Install: sudo apt install nginx"; exit 1; \
	else echo "✅ nginx available: $$(nginx -v 2>&1)"; fi
```

### 3. Verify WebSocket routing strategy

Check frontend WebSocket URLs to determine routing approach:

```bash
grep -r "new WebSocket" frontend/src/ --include="*.ts" --include="*.vue"
```

Choose: Query params (`?type=orders`) or path-based (`/ws/orders`)

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

### Phase 2: Nginx Generator 🔄

**Commit**: "Add nginx config generator"  
**Time**: 4-5 hours

**Files**:

- `backend/scripts/gen_nginx_conf.py`

**Key points**:

- WebSocket routing based on `type` query parameter
- Must use absolute paths in `nginx -t` validation
- Upstreams created for all servers with instance scaling

**Test**: `python scripts/gen_nginx_conf.py dev-config.yaml -o nginx-dev.conf && nginx -t -c $(pwd)/nginx-dev.conf`

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

- [ ] Config loads from YAML
- [ ] Port conflict detection works
- [ ] All tests pass

### Phase 2

- [ ] Generated config passes `nginx -t`
- [ ] Upstreams include all servers
- [ ] WebSocket routing matches frontend format

### Phase 3

- [ ] All servers start successfully
- [ ] Health checks respond on all ports
- [ ] Graceful shutdown (no orphaned processes)
- [ ] Core server stops last
- [ ] Port pre-check prevents partial startup

### Phase 4

- [ ] Frontend client regenerates on spec change
- [ ] Python client regenerates without loops
- [ ] Changes detected within 2s

### Phase 5

- [ ] Multi-process mode works end-to-end
- [ ] Single-process mode still works
- [ ] All existing tests pass
- [ ] WebSockets work through nginx

---

## Summary

**Total time**: ~28 hours (3.5-4 days)  
**Architecture**: Leverages existing modular backend with `ENABLED_MODULES`  
**Risk level**: Low - no critical blockers identified  
**Rollback**: Keep single-process as default, multi-process opt-in

**Order**: Config → Nginx → Server Manager → Watchers → Integration

Each phase is independent, committable, and reversible.
