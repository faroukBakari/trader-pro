# Backend Manager Guide

**Version**: 1.0.0
**Last Updated**: November 3, 2025

---

## Overview

The Backend Manager (`scripts/backend_manager.py`) orchestrates multi-process backend deployment with nginx as a reverse proxy gateway. It provides a unified CLI for managing multiple uvicorn server instances, automatic nginx configuration generation, and process lifecycle management.

**Key Features**:

- Multi-process uvicorn servers with module-based routing
- Automatic nginx configuration generation
- PID file-based process tracking for detached mode
- Health check validation on startup
- Graceful shutdown with force-kill fallback
- Centralized logging with server prefixes
- Port conflict detection and cleanup

---

## Architecture

### Multi-Process Deployment

```
Client
  ↓
Nginx Gateway (port 8000)
  ├─> /api/v1/core/*     → broker_backend (8001)
  ├─> /api/v1/broker/*   → broker_backend (8001)
  └─> /api/v1/datafeed/* → datafeed_backend (8002)

Broker Server (8001)
  ├─ Modules: core + broker
  └─ Health: /api/v1/core/health

Datafeed Server (8002)
  ├─ Modules: core + datafeed
  └─ Health: /api/v1/core/health
```

**Key Concepts**:

- **Module-based routing**: Each module has dedicated REST and WebSocket endpoints
- **Core module**: Auto-included in all servers (provides health checks, version info, docs)
- **Load balancing**: Multiple instances per server supported
- **Detached mode**: Processes run in background, start command returns immediately

---

## Configuration

### Deployment Config (`dev-config.yaml`)

```yaml
# API base URL for all modules
api_base_url: "/api/v1"

# Nginx gateway
nginx:
  port: 8000
  worker_processes: 1
  worker_connections: 1024

# Server instances
servers:
  broker:
    port: 8001
    instances: 1
    modules:
      - core # Auto-included, explicit for clarity
      - broker
    reload: true # Enable uvicorn auto-reload

  datafeed:
    port: 8002
    instances: 1
    modules:
      - core
      - datafeed
    reload: true

# WebSocket routing
websocket:
  routing_strategy: "path" # "path" or "query_param"
  query_param_name: "type" # For query_param strategy

# Module to server mapping
websocket_routes:
  broker: broker
  datafeed: datafeed
```

**Configuration Fields**:

- `api_base_url`: API version prefix (default: `/api/v1`)
- `nginx.port`: Public gateway port
- `servers.{name}.port`: Starting port for server instances
- `servers.{name}.instances`: Number of uvicorn processes (for load balancing)
- `servers.{name}.modules`: List of modules to load (core auto-included)
- `servers.{name}.reload`: Enable uvicorn auto-reload for development
- `websocket.routing_strategy`: `"path"` for `/api/v1/{module}/ws` or `"query_param"` for `/api/v1/ws?type={route}`

---

## Usage

### Recommended: Makefile Commands

**Always use Makefile commands instead of direct script calls**:

```bash
# Start multi-process backend (detached mode)
make backend-manager-start

# With custom config
make backend-manager-start config=prod-config.yaml

# Stop all processes
make backend-manager-stop

# Check status
make backend-manager-status

# Restart (fast ~2s)
make backend-manager-restart

# Generate nginx config (debug)
make backend-manager-gen-nginx-conf

# Log management
make logs-tail              # Tail all server logs with prefixes
make logs-tail-nginx        # Tail nginx logs only
make logs-clean             # Truncate all log files
```

### Direct Script Usage (Advanced)

```bash
# Start backend
poetry run python scripts/backend_manager.py start [config]

# Options:
#   config              Deployment config file (default: dev-config.yaml)
#   --generate-nginx    Force regenerate nginx config
#   --validate          Validate nginx config before starting

# Examples
poetry run python scripts/backend_manager.py start
poetry run python scripts/backend_manager.py start prod-config.yaml --validate
```

**Other Commands**:

```bash
# Stop
poetry run python scripts/backend_manager.py stop [config]
# Options: --timeout SECONDS (default: 3)

# Status
poetry run python scripts/backend_manager.py status [config]

# Restart
poetry run python scripts/backend_manager.py restart [config]
# Options: --timeout, --generate-nginx, --validate

# Generate nginx config (debug)
poetry run python scripts/backend_manager.py gen-nginx-conf [config]
# Options:
#   -o, --output FILE    Output file (default: nginx-dev.conf)
#   --validate           Validate generated config
```

---

## Process Management

### Startup Sequence

1. **Port validation**: Check all required ports are available
2. **Nginx config generation**: Auto-generate if missing or invalid
3. **Server instances**: Start uvicorn processes (one per instance)
   - Set `ENABLED_MODULES` environment variable
   - Configure uvicorn logging to individual files
   - Enable reload with exclusion patterns
4. **Health checks**: Wait for all servers to respond (30 attempts, 0.5s delay)
5. **Nginx start**: Launch nginx gateway
6. **Final validation**: Verify nginx health check passes
7. **Detached mode**: Return immediately, processes run in background

**Detached Mode**:

- All processes run with `start_new_session=True`
- PID files track all processes
- Logs written to `.local/logs/`
- Start command returns immediately

### Shutdown Sequence

1. **Nginx stop**: Send SIGQUIT to nginx (graceful shutdown)
2. **Server instances**: Send SIGTERM to all uvicorn processes
3. **Wait**: 3s timeout with 0.1s polling
4. **Force kill**: SIGKILL if timeout exceeded
5. **Port cleanup**: Force kill any processes holding ports (with retry)
6. **PID cleanup**: Remove all PID files

**Graceful Shutdown**:

- 3s timeout per process (fast shutdown)
- Automatic force-kill fallback
- Port release detection with retry
- Total time: ~1-2s for clean shutdown

---

## Logging System

### Log Files

All logs stored in `backend/.local/logs/`:

```
.local/logs/
├── backend-unified.log        # All servers combined
├── broker-0.log               # Individual server logs
├── datafeed-0.log
├── nginx-access.log           # Nginx access log
└── nginx-error.log            # Nginx error log
```

### Log Format

**Unified log** (server prefixes aligned to 20 chars):

```
broker-0          >> [2025-11-03 10:15:30] [INFO] Server started on port 8001
datafeed-0        >> [2025-11-03 10:15:31] [INFO] Connected to market data
nginx             >> [2025-11-03 10:15:32] [INFO] Gateway ready on port 8000
```

**Individual logs** (standard format):

```
[2025-11-03 10:15:30] [INFO] uvicorn.error: Started server process [12345]
[2025-11-03 10:15:30] [INFO] uvicorn.error: Waiting for application startup
```

### Log Management

```bash
# Tail all server logs (unified view)
make logs-tail

# Tail nginx logs only
make logs-tail-nginx

# Truncate all logs (preserves files)
make logs-clean

# Direct file access
tail -f backend/.local/logs/backend-unified.log
tail -f backend/.local/logs/broker-0.log
```

---

## Auto-Reload & Watch Mode

### Development Workflow

The backend uses **uvicorn's built-in reload** with automatic spec/client generation:

**Initial Startup**:

1. Backend manager generates specs and clients
2. Uvicorn starts with `--reload` and exclusions
3. App lifespan regenerates specs on first load

**Code Change Cycle** (~2-3s):

1. Modify Python file (model, handler, endpoint)
2. Uvicorn detects change
3. Uvicorn reloads server
4. App lifespan regenerates specs
5. WebSocket routers auto-regenerate (if ws.py changed)
6. Server ready with updated code

**Exclusion Patterns**:

```bash
# These files do NOT trigger reload:
--reload-exclude "*/openapi.json"
--reload-exclude "*/asyncapi.json"
--reload-exclude "*/clients/*"
--reload-exclude "*/scripts/*"
--reload-exclude "*/.local/*"
--reload-exclude "*/.pids/*"
--reload-exclude "*/__pycache__/*"
--reload-exclude "*.pyc"
```

**Manual Client Generation**:

```bash
# Python clients (backend tests)
make generate-python-clients

# Frontend clients (Vue/TypeScript)
cd frontend && make generate-openapi-client
```

---

## Nginx Configuration

### Generation

Nginx config is **auto-generated** from `dev-config.yaml`:

1. On first start (if missing)
2. On restart with `--generate-nginx` flag
3. Manual: `make backend-manager-gen-nginx-conf`

**Generated config location**: `backend/.local/nginx.conf`

### Routing Logic

**REST API** (module prefix matching):

```nginx
# Core module
location /api/v1/core/ {
    proxy_pass http://broker_backend;
}

# Broker module
location /api/v1/broker/ {
    proxy_pass http://broker_backend;
}

# Datafeed module
location /api/v1/datafeed/ {
    proxy_pass http://datafeed_backend;
}
```

**WebSocket** (path-based routing):

```nginx
# Broker WebSocket
location /api/v1/broker/ws {
    proxy_pass http://broker_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

# Datafeed WebSocket
location /api/v1/datafeed/ws {
    proxy_pass http://datafeed_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

**Load Balancing** (multiple instances):

```nginx
upstream broker_backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;  # If instances=2
}
```

### Validation

```bash
# Validate generated config
poetry run python scripts/backend_manager.py gen-nginx-conf --validate

# Manual validation
nginx -t -c backend/.local/nginx.conf
```

---

## Troubleshooting

### Port Conflicts

**Symptom**: `Address already in use` error on startup

**Solution**:

```bash
# Check what's using the port
lsof -i :8000

# Stop backend (includes port cleanup)
make backend-manager-stop

# Or kill specific process
kill -9 $(lsof -ti :8000)

# Restart
make backend-manager-start
```

### Orphaned Processes

**Symptom**: Processes remain after crash or failed shutdown

**Solution**:

```bash
# Force cleanup all backend processes
pkill -9 -f "uvicorn.*trading_api"
pkill -9 -f "nginx.*nginx.conf"

# Or use backend manager (includes PID cleanup)
make backend-manager-stop

# Clean PID files manually if needed
rm -rf backend/.local/pids/*
```

### Health Checks Failing

**Symptom**: Server starts but health endpoint returns errors

**Solution**:

```bash
# Check individual server health
curl http://localhost:8001/api/v1/core/health
curl http://localhost:8002/api/v1/core/health

# Check nginx health
curl http://localhost:8000/api/v1/core/health

# Review server logs
make logs-tail

# Check specific server
tail -f backend/.local/logs/broker-0.log
```

### Nginx Config Errors

**Symptom**: Nginx validation fails

**Solution**:

```bash
# Regenerate config
make backend-manager-gen-nginx-conf

# Validate manually
nginx -t -c backend/.local/nginx.conf

# Check nginx error log
tail -f backend/.local/logs/nginx-error.log

# Verify config paths
cat backend/.local/nginx.conf | grep -E "location|proxy_pass"
```

### Reload Loop

**Symptom**: Server keeps reloading continuously

**Solution**:

```bash
# Check exclusion patterns
grep "reload-exclude" backend/scripts/backend_manager.py

# Verify no files being written to src/ during reload
make logs-tail

# Look for file generation messages in logs

# Restart with fresh state
make backend-manager-restart
```

### Slow Shutdown

**Symptom**: Stop/restart takes longer than expected

**Solution**:

```bash
# Reduce timeout (default is 3s)
poetry run python scripts/backend_manager.py stop --timeout 1

# Check for stuck processes
ps aux | grep uvicorn

# Force kill if needed
pkill -9 -f uvicorn
```

---

## Testing

### Unit Tests

```bash
# Port management
pytest tests/unit/test_backend_manager_port_management.py -v

# PID file management
pytest tests/unit/test_backend_manager_pid_files.py -v

# Nginx config generation
pytest tests/unit/test_backend_manager_nginx_config.py -v

# Configuration loading
pytest tests/unit/test_backend_manager_config.py -v

# All unit tests
pytest tests/unit/test_backend_manager*.py -v
```

### Integration Tests

```bash
# Full integration suite (slower, ~50s)
pytest tests/integration/test_backend_manager_integration.py -v

# Specific test
pytest tests/integration/test_backend_manager_integration.py::TestBackendManagerIntegration::test_01_start_all_servers_successfully -v
```

### Coverage

```bash
# Unit tests with coverage
pytest tests/unit/test_backend_manager*.py \
  --cov=scripts.backend_manager \
  --cov-report=term-missing

# All tests with coverage
pytest tests/ \
  --cov=scripts.backend_manager \
  --cov-report=html
```

---

## Implementation Details

### Process Tracking

**PID Files** (`.local/pids/`):

- `broker-0.pid`, `datafeed-0.pid`: Uvicorn instances
- `nginx.pid`: Nginx master process

**Process Lifecycle**:

1. Start: Write PID to file
2. Monitor: Check via `os.kill(pid, 0)`
3. Stop: Read PID, send SIGTERM, verify termination
4. Cleanup: Remove PID file

### Port Management

**Port Checking** (SO_REUSEADDR matching uvicorn):

```python
def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True
```

**Port Cleanup** (retry with force kill):

```python
async def _wait_for_ports_release(max_retries=3):
    # 1. Wait for graceful release
    # 2. Force kill holders if needed (lsof + SIGTERM)
    # 3. Force kill with SIGKILL if still stuck
    # 4. Retry with exponential backoff
```

### Health Checks

**Wait for Health** (30 attempts, 0.5s delay):

```python
async def wait_for_health(base_url: str) -> bool:
    for attempt in range(30):
        try:
            response = await client.get(f"{base_url}/api/v1/core/health")
            if response.status_code == 200:
                return True
        except (ConnectError, TimeoutException):
            await asyncio.sleep(0.5)
    return False
```

### Uvicorn Logging

**Log Config** (per instance):

```json
{
  "version": 1,
  "formatters": {
    "default": {
      "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    }
  },
  "handlers": {
    "file": {
      "class": "logging.FileHandler",
      "filename": ".local/logs/broker-0.log"
    }
  },
  "loggers": {
    "uvicorn": { "handlers": ["file"], "level": "INFO" }
  }
}
```

---

## Related Documentation

### Architecture & Design

- [Modular Backend Architecture](MODULAR_BACKEND_ARCHITECTURE.md) - Module system overview
- [Architecture Guide](../../docs/ARCHITECTURE.md) - Overall system architecture
- [Nginx Routing Implementation](tmp/nginx-routing-implementation-summary.md) - Nginx config generation design

### Testing & Development

- [Backend Testing Guide](BACKEND_TESTING.md) - Testing strategy
- [Backend Manager Test Guide](tmp/backend-manager-test-redesign.md) - Test implementation guide
- [Development Guide](../../docs/DEVELOPMENT.md) - Development workflows

### Configuration & Setup

- [Deployment Config Schema](../src/trading_api/shared/deployment/config_schema.py) - Config models
- [Makefile Guide](../../MAKEFILE-GUIDE.md) - All Makefile commands

---

## Best Practices

### Development

1. **Always use Makefile commands** (`make backend-manager-start` not direct script)
2. **Check status first** (`make backend-manager-status` before debugging)
3. **Review logs** (`make logs-tail` for real-time debugging)
4. **Clean shutdown** (`make backend-manager-stop` not Ctrl+C or kill)

### Configuration

1. **Keep core module explicit** in `dev-config.yaml` for clarity
2. **Use path-based WebSocket routing** for frontend compatibility
3. **Set reload: true** for development, `reload: false` for production
4. **Start ports at 8001+** to avoid common conflicts

### Production

1. **Disable reload** (`reload: false` in config)
2. **Increase worker_processes** (`worker_processes: auto`)
3. **Add multiple instances** for load balancing
4. **Monitor logs** with log aggregation tools
5. **Set proper timeouts** for graceful shutdown

### Testing

1. **Run unit tests frequently** (fast feedback)
2. **Run integration tests before commits** (comprehensive coverage)
3. **Clean up after tests** (`make backend-manager-stop`)
4. **Check for orphaned processes** (`ps aux | grep uvicorn`)

---

**Last Updated**: November 3, 2025
**Version**: 1.0.0
**Status**: ✅ Current Reference
