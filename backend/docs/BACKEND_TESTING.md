# Backend Testing Guide

**Version**: 2.0.0
**Date**: November 3, 2025
**Status**: ✅ Current Reference

---

## Overview

This document describes the comprehensive testing strategy for the backend, covering:

- **Unit Testing** - Fast, isolated module-level tests
- **Integration Testing** - Multi-process and session-based testing
- **Test Organization** - Test structure and fixture patterns
- **App Startup Flow** - Understanding codegen and initialization
- **Best Practices** - Writing efficient, maintainable tests

The backend uses pytest with async support for testing modular FastAPI applications with WebSocket endpoints.

---

## Table of Contents

1. [Test Organization](#test-organization)
2. [App Startup Flow](#app-startup-flow)
3. [Unit Testing](#unit-testing)
4. [Integration Testing](#integration-testing)
5. [Testing Overhead Analysis](#testing-overhead-analysis)
6. [Session-Based Testing Strategy](#session-based-testing-strategy)
7. [Test Autonomy Pattern](#test-autonomy-pattern)
8. [Optimal Test Organization](#optimal-test-organization)
9. [Cleanup and Resource Management](#cleanup-and-resource-management)
10. [Adding New Tests](#adding-new-tests)
11. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
12. [Related Documentation](#related-documentation)

---

## Test Organization

The backend has a three-tier test structure:

### 1. Root-Level Tests (`backend/tests/`)

Located in `backend/tests/`, these tests validate cross-cutting concerns:

```
backend/tests/
├── conftest.py                     # Shared fixtures for all tests
├── test_import_boundaries.py       # Module isolation validation
├── test_module_registry.py         # Module discovery and registration
├── test_deployment_config.py       # Configuration validation
└── integration/                    # Integration tests (see below)
```

**Purpose:**

- ✅ Validate module boundaries and import rules
- ✅ Test module registry and discovery
- ✅ Verify deployment configuration
- ✅ Ensure architectural constraints

**Run with:**

```bash
make test-boundaries
```

### 2. Module-Level Tests (`modules/*/tests/`)

Each module has its own test directory:

```
backend/src/trading_api/modules/
├── core/
│   └── tests/
│       ├── test_api_health.py      # Health endpoint tests
│       └── test_api_versioning.py  # Versioning endpoint tests
├── broker/
│   └── tests/
│       └── test_broker_api.py      # Broker-specific tests
└── datafeed/
    └── tests/
        └── test_ws_datafeed.py     # Datafeed WebSocket tests
```

**Purpose:**

- ✅ Test module-specific endpoints and logic
- ✅ Fast execution with isolated fixtures
- ✅ Use TestClient for synchronous testing
- ✅ No external dependencies

**Run with:**

```bash
# All module tests
make test-modules

# Specific module
make test-module-datafeed
make test-module-broker
```

### 3. Integration Tests (`backend/tests/integration/`)

Located in `backend/tests/integration/`, these tests verify system integration:

```
backend/tests/integration/
├── conftest.py                           # Integration fixtures
├── test_backend_manager_integration.py   # Multi-process backend testing
├── test_backend_manager_unit.py          # Backend manager unit tests
├── test_module_isolation.py              # Module isolation verification
├── test_multi_process_clients.py         # Cross-service communication
├── test_broker_datafeed_workflow.py      # End-to-end workflows
└── test_full_stack.py                    # Full stack integration
```

**Purpose:**

- ✅ Test multi-process server management
- ✅ Verify nginx routing and load balancing
- ✅ Test cross-module communication
- ✅ End-to-end workflow validation
- ✅ Real HTTP and WebSocket connections

**Run with:**

```bash
make test-integration
```

### Test Discovery and Execution

```bash
# Run all tests (boundaries + modules + integration)
make test

# Run with coverage
make test-cov

# Run specific test file
poetry run pytest tests/integration/test_module_isolation.py -v

# Run specific test
poetry run pytest tests/integration/test_module_isolation.py::TestModuleIsolation::test_broker_only_app -v
```

---

## App Startup Flow

Understanding the application startup flow is crucial for writing effective tests. This diagram shows the initialization sequence, including automatic code generation:

```mermaid
flowchart TB
    Start([Application Start]) --> LoadConfig[Load Configuration<br/>DeploymentConfig]
    LoadConfig --> CreateFactory[Create AppFactory]
    CreateFactory --> Discover[Auto-discover Modules<br/>from modules/]

    Discover --> Register[Register Modules<br/>in ModuleRegistry]
    Register --> Filter{Filter Enabled<br/>Modules}

    Filter -->|Core Always Included| EnabledModules[Get Enabled Modules]

    EnabledModules --> CreateModular[Create ModularApp]

    CreateModular --> InitModules[Initialize Each Module]

    InitModules --> CreateApp[Module.create_app]
    CreateApp --> Lifespan{Enter Lifespan<br/>Event}

    Lifespan --> GenSpecs[Generate OpenAPI Spec<br/>from FastAPI routes]
    GenSpecs --> CompareSpecs{Compare with<br/>Existing Spec}

    CompareSpecs -->|Changes Detected| WriteSpec[Write OpenAPI JSON<br/>to specs_generated/]
    CompareSpecs -->|No Changes| SkipGen[Skip Generation]

    WriteSpec --> GenClient[Generate Python Client<br/>from OpenAPI spec]
    GenClient --> FormatClient[Format Generated Code<br/>autoflake, black, isort]
    FormatClient --> UpdateIndex[Update __init__.py<br/>in client_generated/]

    UpdateIndex --> CheckWS{Has WebSocket<br/>App?}
    SkipGen --> CheckWS

    CheckWS -->|Yes| GenAsyncAPI[Generate AsyncAPI Spec<br/>from WS routes]
    CheckWS -->|No| MountModule

    GenAsyncAPI --> WriteAsyncAPI[Write AsyncAPI JSON<br/>to specs_generated/]
    WriteAsyncAPI --> SetupWS[Setup FastWSAdapter<br/>ws_app.setup]

    SetupWS --> MountModule[Mount Module at<br/>/api/v1/module_name]

    MountModule --> NextModule{More<br/>Modules?}
    NextModule -->|Yes| InitModules
    NextModule -->|No| AddMiddleware[Add CORS Middleware]

    AddMiddleware --> MergeSpecs[Merge All Module Specs<br/>into ModularApp]
    MergeSpecs --> ValidateModels[Validate Response Models<br/>for OpenAPI compliance]

    ValidateModels --> Ready([Application Ready<br/>for Requests])

    style Start fill:#e1f5e1
    style Ready fill:#e1f5e1
    style GenSpecs fill:#fff4e6
    style GenClient fill:#fff4e6
    style GenAsyncAPI fill:#fff4e6
    style CompareSpecs fill:#e3f2fd
    style CheckWS fill:#e3f2fd
```

### Key Points for Testing

**1. Codegen Happens During Lifespan**

- OpenAPI/AsyncAPI specs generated automatically
- Python clients created from specs
- WebSocket routers generated at module instantiation
- All codegen occurs **before** the app accepts requests

**2. Module Isolation**

- Each module generates its own specs and clients
- Modules can be selectively enabled/disabled
- Core module is always enabled (health, versioning)

**3. Test Implications**

- **Unit tests**: Use TestClient, no codegen needed
- **Integration tests**: Codegen runs during session setup
- **Session fixtures**: Share generated clients across tests
- **Clean generated**: Use `make clean-generated` between test runs

**4. Spec Change Detection**

- Compares new spec with existing file
- Only regenerates if meaningful changes detected
- Logs differences (endpoints, models, properties)
- Prevents unnecessary client regeneration

**5. Generated Artifacts**

Per module:

```
modules/<module>/
├── specs_generated/
│   ├── <module>_openapi.json     # REST API spec
│   └── <module>_asyncapi.json    # WebSocket spec (if WS exists)
└── client_generated/
    ├── <module>_client.py        # Python HTTP client
    └── __init__.py               # Client index
```

App level (merged):

```
/api/v1/openapi.json              # All REST endpoints
/api/v1/asyncapi.json             # All WebSocket channels
```

---

## Unit Testing

Unit tests are fast, isolated tests that run without external dependencies or HTTP servers.

### Module-Level Unit Tests

Each module has its own test suite located in `modules/<module>/tests/`:

**Example: Core Module Health Test**

```python
# backend/src/trading_api/modules/core/tests/test_api_health.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_healthcheck_returns_200_and_payload(async_client: AsyncClient) -> None:
    """Test health endpoint returns correct status and payload."""
    response = await async_client.get("/api/v1/core/health")

    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert payload["status"] == "healthy"
```

**Key Features:**

- ✅ Uses `AsyncClient` fixture (no HTTP server)
- ✅ Tests against FastAPI TestClient
- ✅ No database or external dependencies
- ✅ Fast execution (< 100ms per test)

### Using Test Fixtures

Tests use fixtures defined in `conftest.py` files:

**Root-level conftest** (`backend/tests/conftest.py`):

```python
@pytest.fixture(scope="session")
def apps() -> tuple[ModularApp, list[FastWSAdapter]]:
    """Full application with all modules enabled (shared across session)."""
    return create_test_app(enabled_modules=None)

@pytest.fixture(scope="session")
def app(apps) -> FastAPI:
    """FastAPI application instance."""
    api_app, _ = apps
    return api_app

@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

**Module-level conftest** (inherits from root):

```python
# backend/src/trading_api/conftest.py
@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync test client for WebSocket tests."""
    return TestClient(app)
```

### Creating Isolated Test Apps

Use `create_test_app` helper to test specific modules:

```python
from tests.conftest import create_test_app

def test_datafeed_only():
    """Test with only datafeed module enabled."""
    api_app, ws_apps = create_test_app(enabled_modules=["datafeed"])

    # datafeed endpoints available
    # broker endpoints NOT available
```

### WebSocket Unit Tests

Use `TestClient` for synchronous WebSocket testing:

```python
# backend/src/trading_api/modules/datafeed/tests/test_ws_datafeed.py
from fastapi.testclient import TestClient

def test_subscribe_to_bars(client: TestClient) -> None:
    """Test subscribing to bar updates via WebSocket."""
    with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
        # Send subscription request
        websocket.send_json({
            "type": "bars.subscribe",
            "payload": {"symbol": "AAPL", "resolution": "1"}
        })

        # Verify response
        response = websocket.receive_json()
        assert response["type"] == "bars.subscribe.response"
        assert response["payload"]["symbol"] == "AAPL"
```

### Running Unit Tests

```bash
# All module tests
make test-modules

# Specific module
make test-module-core
make test-module-datafeed
make test-module-broker

# With verbose output
poetry run pytest src/trading_api/modules/core/tests/ -v
```

---

## Integration Testing

Integration tests verify end-to-end behavior with real HTTP servers, nginx routing, and multi-process communication.

### Multi-Process Testing Patterns

Integration tests use three main patterns:

**1. Session Fixtures** - Shared services across tests
**2. Backend Manager** - Multi-process server orchestration
**3. Module Isolation** - Selective module loading

### Session-Scoped Service Fixtures

```python
# backend/tests/integration/conftest.py
@pytest.fixture(scope="session")
def broker_service():
    """Start broker service once per session."""
    port = 8001
    process = multiprocessing.Process(
        target=run_service,
        args=("broker", port)
    )
    process.start()

    # Wait for service availability
    base_url = f"http://127.0.0.1:{port}"
    wait_for_service_sync(base_url)

    yield base_url

    # Cleanup after session
    process.terminate()
    process.join(timeout=5)
```

**Benefits:**

- ✅ Start service once per test session
- ✅ Share across multiple tests
- ✅ Automatic cleanup
- ✅ Realistic HTTP communication

### Module Isolation Testing

```python
# backend/tests/integration/test_module_isolation.py
@pytest.fixture(scope="session")
def datafeed_only_app():
    """Session-scoped datafeed-only app for isolation tests."""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["datafeed"])

async def test_datafeed_only_app(datafeed_only_app):
    """Test that only datafeed endpoints are available."""
    api_app, _ = datafeed_only_app

    async with AsyncClient(app=api_app, base_url="http://test") as client:
        # Datafeed endpoint should be available
        response = await client.get("/api/v1/datafeed/symbols")
        assert response.status_code == 200

        # Broker endpoint should NOT be available
        response = await client.get("/api/v1/broker/accounts")
        assert response.status_code == 404
```

### Backend Manager Integration Testing

The backend manager (`scripts/backend_manager.py`) orchestrates multi-process servers with nginx. This approach is detailed in the following sections.

---

## Testing Overhead Analysis

### Startup Costs

Starting the backend involves several expensive operations:

1. **Spec & Client Generation** (~5-6 seconds)

   - OpenAPI spec generation from FastAPI routes
   - AsyncAPI spec generation from WebSocket endpoints
   - Python client code generation from specs
   - Frontend TypeScript client generation

2. **Server Process Startup** (~2-3 seconds per server)

   - Multiple uvicorn instances (broker, datafeed, etc.)
   - Module loading and dependency injection
   - Health check endpoints becoming ready

3. **Nginx Gateway Startup** (~1 second)

   - Configuration validation
   - Worker process initialization
   - Port binding and routing setup

4. **Health Check Validation** (~1-2 seconds)
   - Waiting for all servers to respond to health endpoints
   - Verifying routing through nginx

**Total Startup Overhead: ~10-15 seconds per backend instance**

### Why Overhead Matters

- Running tests repeatedly during development
- CI/CD pipeline execution time
- Developer productivity and feedback loops
- Resource consumption (CPU, memory, ports)

## Session-Based Testing Strategy

### Core Principle: Mutualize Expensive Operations

Instead of starting/stopping the backend for each test, we:

1. **Start once at session scope** - Single backend instance for all tests
2. **Share the session backend** - Most tests use the same running instance
3. **Test autonomy via helpers** - Each test can verify/restart if needed
4. **Clean up at session end** - Comprehensive cleanup ensures no leaks

### Session Fixture Pattern

```python
@pytest_asyncio.fixture(scope="session")
async def session_backend_manager(
    session_test_config: DeploymentConfig,
    tmp_path_factory: TempPathFactory
) -> AsyncGenerator[ServerManager, None]:
    """Session-scoped backend - starts once, shared by all tests."""

    # Setup: Create shared temp directory
    tmp_path = tmp_path_factory.mktemp("backend_manager_session")

    # Initialize manager with shared directories
    manager = ServerManager(config, nginx_config_path, detached=False)
    manager.pid_dir = tmp_path / ".pids"
    manager.log_dir = tmp_path / ".logs"

    # Start once for entire session
    success = await manager.start_all()
    if not success:
        raise RuntimeError("Failed to start backend for test session")

    yield manager  # All tests use this instance

    # Cleanup: Comprehensive process termination
    await _ensure_all_processes_killed(manager)
```

### Shared Working Directory

**Critical**: All tests in the session use the **same working directory**:

- `tmp_path/.pids/` - PID files for process management
- `tmp_path/.logs/` - Server logs for debugging
- `tmp_path/nginx-test.conf` - Nginx configuration
- `tmp_path/nginx.pid` - Nginx PID file

This enables:

- Simulating detached mode (stop_by_pid_files tests)
- Process management across test boundaries
- Realistic multi-process scenarios

## Test Autonomy Pattern

### The `ensure_started()` Helper

Each test should be autonomous and not assume server state. The `ensure_started()` helper provides this:

```python
async def ensure_started(manager: ServerManager) -> None:
    """Ensure backend is fully started and healthy.

    Checks status and restarts if needed. Makes tests autonomous.
    """
    status = await manager.get_status()

    # If fully running and healthy, nothing to do
    if status["running"] and status["nginx"]["healthy"]:
        all_healthy = all(
            inst["healthy"] for server in status["servers"].values()
            for inst in server
        )
        if all_healthy:
            return  # All good, backend is ready

    # Need to restart - clean up first
    manager._shutdown_requested = False
    await manager.stop_all(timeout=2.0)
    await asyncio.sleep(0.5)

    # Clear state and restart
    manager.processes.clear()
    manager.nginx_process = None

    success = await manager.start_all()
    if not success:
        raise RuntimeError("Failed to start backend")
```

**Usage in tests:**

```python
async def test_something(self, session_backend_manager: ServerManager) -> None:
    """Test description."""
    await ensure_started(session_backend_manager)  # Ensure ready

    # Test logic - backend is guaranteed to be running
    # ...
```

### When to Use `ensure_started()`

- ✅ **After destructive operations** (tests that stop/restart)
- ✅ **When test order is uncertain**
- ✅ **For test isolation and resilience**
- ❌ **NOT needed for initial tests** (session already started)
- ❌ **NOT needed for read-only operations** (if following test order)

## Optimal Test Organization

### Test Flow Strategy

Organize tests to minimize setup overhead by following session state:

```python
class TestBackendManagerIntegration:
    """Tests numbered for execution order."""

    # Phase 1: Verify Initial Startup (session already running)
    async def test_01_start_all_servers_successfully(...):
        # No ensure_started needed - session just started

    async def test_02_health_checks_pass(...):
        await ensure_started(...)  # Be safe

    async def test_03_processes_are_alive(...):
        await ensure_started(...)

    # Phase 2: State Mutations (may stop/restart)
    async def test_05_restart_workflow(...):
        await ensure_started(...)
        # Test restart logic

    # Phase 3: Read-Only Operations (leverage running state)
    async def test_06_broker_routes(...):
        await ensure_started(...)  # Ensure ready after restart

    async def test_07_datafeed_routes(...):
        await ensure_started(...)

    # Phase 4: Destructive Operations (at end)
    async def test_15_stop_all_servers(...):
        await ensure_started(...)
        # Stop and verify

    # Phase 5: Isolated Tests (unique ports, own instances)
    async def test_16_start_with_blocked_ports(self, tmp_path: Path):
        # Creates isolated manager with different ports
        # No session_backend_manager needed
```

### Test Ordering Best Practices

1. **Start with verification** - Confirm session backend is healthy
2. **Group by state** - Similar tests together (routing, isolation, etc.)
3. **Mutations in middle** - Restart tests after initial checks
4. **Destructive at end** - Stop tests before isolated tests
5. **Isolated last** - Tests with unique configs use `tmp_path`

### Numbering Convention

Use numbered test names for clear execution order:

```python
async def test_01_initial_check(...):
async def test_02_health_validation(...):
async def test_03_process_verification(...):
# ...
async def test_19_final_cleanup(...):
```

Benefits:

- Explicit execution order
- Easy to insert new tests
- Clear test flow in IDE/output

## Cleanup and Resource Management

### Session Cleanup Pattern

Comprehensive cleanup at session end prevents port/process leaks:

```python
async def _ensure_all_processes_killed(manager: ServerManager) -> None:
    """Ensure all backend processes are killed, including detached daemons.

    Performs:
    1. Normal stop_all() with graceful shutdown
    2. Force kill processes holding ports
    3. Clean up PID files
    4. Verify ports released
    """
    import os, signal

    # Step 1: Try normal stop
    try:
        await manager.stop_all(timeout=3.0)
    except Exception as e:
        print(f"Warning during stop_all: {e}")

    # Step 2: Force kill port holders
    all_ports = [port for _, port in manager.config.get_all_ports()]
    ports_in_use = [port for port in all_ports if is_port_in_use(port)]

    if ports_in_use:
        await manager._force_kill_port_holders(ports_in_use)
        await asyncio.sleep(0.5)

    # Step 3: Kill nginx by PID file
    if manager.nginx_pid_file.exists():
        try:
            nginx_pid = int(manager.nginx_pid_file.read_text().strip())
            os.kill(nginx_pid, signal.SIGKILL)
            manager.nginx_pid_file.unlink()
        except (ValueError, OSError, ProcessLookupError):
            pass

    # Step 4: Clean up server PID files
    for server_name, server_config in manager.config.servers.items():
        for instance_idx in range(server_config.instances):
            instance_name = f"{server_name}-{instance_idx}"
            pid_file = manager.pid_dir / f"{instance_name}.pid"

            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, signal.SIGKILL)
                    pid_file.unlink()
                except (ValueError, OSError, ProcessLookupError):
                    pass

    # Step 5: Verify cleanup
    await asyncio.sleep(0.3)
    remaining_ports = [port for port in all_ports if is_port_in_use(port)]
    if remaining_ports:
        print(f"WARNING: Ports still in use: {remaining_ports}")
```

### Why Comprehensive Cleanup Matters

- **Port conflicts** - Prevents "address already in use" errors
- **Zombie processes** - Ensures no orphaned uvicorn/nginx
- **Resource leaks** - Frees memory, file descriptors
- **Test isolation** - Clean slate for next test run
- **CI/CD reliability** - Prevents flaky test failures

## Adding New Tests

When adding new tests, choose the appropriate test level and follow the relevant guidelines:

### 1. Determine Test Type

**Unit Test** (Fast, isolated):

- Testing a single module's endpoints
- No external dependencies needed
- Uses FastAPI TestClient
- Located in `modules/<module>/tests/`

**Integration Test** (Real servers, multi-process):

- Testing cross-module communication
- Testing with real HTTP/WebSocket connections
- Testing nginx routing
- Located in `tests/integration/`

**Boundary Test** (Architectural validation):

- Testing import boundaries
- Testing module registry
- Testing configuration validation
- Located in `tests/` (root level)

### 2. Adding Unit Tests

**Step 1:** Create test file in module's test directory

```python
# backend/src/trading_api/modules/broker/tests/test_broker_orders.py
import pytest
from httpx import AsyncClient

class TestBrokerOrders:
    """Test broker order endpoints."""

    @pytest.mark.asyncio
    async def test_get_orders(self, async_client: AsyncClient) -> None:
        """Test fetching orders."""
        response = await async_client.get("/api/v1/broker/orders")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
```

**Step 2:** Run your module's tests

```bash
make test-module-broker
```

**Step 3:** Verify with coverage

```bash
poetry run pytest src/trading_api/modules/broker/tests/ --cov=trading_api.modules.broker
```

### 3. Adding Integration Tests

For backend manager integration tests, follow the existing pattern:

### 3a. Study Existing Test Flow

```bash
# Read the test file to understand current flow
cat tests/integration/test_backend_manager_integration.py

# Look for:
# - Current test numbering (01-19, etc.)
# - Phase grouping (startup, routing, stop, etc.)
# - Use of ensure_started()
```

### 3b. Determine Test Category

- **Read-only operation?** → Use session backend, add after routing tests
- **Mutations (restart)?** → Use session backend with ensure_started, add in middle
- **Destructive (stop)?** → Use session backend, add near test_15
- **Isolated (unique config)?** → Use tmp_path fixture, add at end

### 3c. Choose Appropriate Fixture

```python
# Most backend manager tests: Use session backend
async def test_XX_my_test(
    self, session_backend_manager: ServerManager
) -> None:
    await ensure_started(session_backend_manager)
    # Test logic

# Isolated tests: Use tmp_path for unique instance
async def test_XX_isolated_test(self, tmp_path: Path) -> None:
    # Create unique config with different ports
    config = DeploymentConfig(...)
    manager = ServerManager(config, ...)
    # Test logic
```

### 3d. For Multi-Process Service Tests

```python
# backend/tests/integration/test_cross_service.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_broker_to_datafeed(broker_service, datafeed_service):
    """Test communication between broker and datafeed services."""
    # Both services are already running (session fixtures)

    async with AsyncClient() as client:
        # Test broker service
        response = await client.get(f"{broker_service}/api/v1/broker/accounts")
        assert response.status_code == 200

        # Test datafeed service
        response = await client.get(f"{datafeed_service}/api/v1/datafeed/symbols")
        assert response.status_code == 200
```

### 3e. For Module Isolation Tests

```python
# backend/tests/integration/test_new_isolation.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_broker_isolation(broker_only_app):
    """Test that broker-only app has no datafeed endpoints."""
    api_app, _ = broker_only_app

    async with AsyncClient(app=api_app, base_url="http://test") as client:
        # Broker endpoints available
        response = await client.get("/api/v1/broker/accounts")
        assert response.status_code == 200

        # Datafeed endpoints NOT available
        response = await client.get("/api/v1/datafeed/symbols")
        assert response.status_code == 404
```

### 4. Adding Boundary Tests

```python
# backend/tests/test_new_boundary.py
import pytest

def test_module_imports():
    """Test that modules don't cross boundaries."""
    # Import module and verify its dependencies
    from trading_api.modules.broker import api

    # Verify broker doesn't import datafeed internals
    import sys
    assert "trading_api.modules.datafeed.services" not in sys.modules
```

### 5. Run Test Suite

```bash
# Run all tests
make test

# Run specific test level
make test-boundaries      # Root-level tests
make test-modules         # All module tests
make test-integration     # Integration tests

# Run specific module
make test-module-broker

# Run specific file
poetry run pytest tests/integration/test_module_isolation.py -v

# Run specific test
poetry run pytest tests/integration/test_module_isolation.py::TestModuleIsolation::test_broker_only_app -v
```

### 6. Verify Test Autonomy

- ✅ Test can run independently
- ✅ Uses appropriate fixtures
- ✅ Doesn't assume specific prior state
- ✅ Cleans up resources if creating new instances
- ✅ Follows existing naming conventions

---

## Performance Benchmarks

### Before Optimization (20 tests, separate instances)

- **Execution time**: ~66 seconds
- **Server startups**: ~8-10 instances
- **Spec generation**: ~8-10 times
- **Overhead**: ~80% of test time

### After Optimization (19 tests, session-based)

- **Execution time**: ~50 seconds
- **Server startups**: 2 instances (session + 1 restart test)
- **Spec generation**: 2 times
- **Overhead**: ~30% of test time
- **Improvement**: 25% faster, 75% fewer startups

## Common Pitfalls and Solutions

### Pitfall 1: Port Conflicts

**Problem**: Tests fail with "address already in use"

**Solution**:

- Ensure cleanup fixture is used
- Use unique ports for isolated tests
- Check for leaked processes: `lsof -i :19720`

### Pitfall 2: Test Order Dependency

**Problem**: Tests pass individually but fail together

**Solution**:

- Use `ensure_started()` in each test
- Don't assume server is running
- Avoid implicit state dependencies

### Pitfall 3: Slow Test Feedback

**Problem**: Tests take too long during development

**Solution**:

- Run specific test: `pytest tests/integration/test_backend_manager_integration.py::TestBackendManagerIntegration::test_XX_my_test`
- Use `-x` flag to stop on first failure
- Consider marking slow tests with `@pytest.mark.slow`

### Pitfall 4: Flaky Tests

**Problem**: Tests pass/fail randomly

**Solution**:

- Add proper waits after async operations
- Use health checks instead of sleep
- Ensure proper cleanup between tests
- Use `ensure_started()` for state verification

## Testing Constraints

### Port Allocation

- **Session backend**: 19000 + (pid % 100) \* 10
- **Function-scoped tests**: 19000 + (pid % 100) \* 10 + 100
- **Isolated tests**: 18000 or 20000 ranges

### Timeouts

- **Startup**: 10s for health checks
- **Shutdown**: 2-3s graceful, then force kill
- **HTTP requests**: 5s timeout
- **Process verification**: 0.3-0.5s waits

### Resource Limits

- **Max instances**: 3 brokers + 3 datafeeds = 6 servers
- **Nginx workers**: 1 (test mode)
- **Nginx connections**: 1024 (test mode)

## Recommendations

### For New Contributors

**Start with unit tests:**

1. **Read existing tests** - Understand patterns before adding
2. **Use appropriate test level** - Unit for modules, integration for workflows
3. **Follow test organization** - Place tests in correct directories
4. **Use proper fixtures** - async_client for API, client for WebSocket
5. **Test locally first** - Verify before CI/CD

**For integration tests:**

1. **Understand the startup flow** - Review the app startup diagram
2. **Use session fixtures** - Share expensive resources
3. **Make tests autonomous** - Use ensure_started() when needed
4. **Follow numbering conventions** - For backend manager tests

### For Test Maintenance

1. **Keep tests fast**

   - Prefer unit tests over integration tests
   - Use session fixtures to share resources
   - Minimize server restarts

2. **Organize logically**

   - Group related tests in classes
   - Follow test execution order
   - Use descriptive test names

3. **Clean up properly**

   - Use fixtures for resource management
   - Ensure processes are terminated
   - Check for port leaks

4. **Document complex tests**

   - Add docstrings explaining test purpose
   - Comment tricky test logic
   - Document test constraints

5. **Monitor performance**
   - Track test execution time
   - Identify slow tests
   - Optimize bottlenecks

### For CI/CD

1. **Separate test levels**

   - Run unit tests first (fast feedback)
   - Run integration tests separately
   - Use `make test-boundaries`, `make test-modules`, `make test-integration`

2. **Use pytest markers**

   - Mark integration tests: `@pytest.mark.integration`
   - Mark slow tests: `@pytest.mark.slow`
   - Skip slow tests in dev: `pytest -m "not slow"`

3. **Parallel execution**

   - Consider pytest-xdist for unit tests
   - Keep integration tests sequential (resource conflicts)
   - Use session fixtures to minimize overhead

4. **Resource cleanup**

   - Ensure CI runners terminate all processes
   - Check for port conflicts
   - Clean up temporary files

5. **Timeout protection**
   - Set max test duration in CI
   - Fail fast on hanging tests
   - Monitor test execution time

### For Debugging

**Unit tests:**

```bash
# Run with verbose output
poetry run pytest src/trading_api/modules/core/tests/ -v -s

# Run specific test
poetry run pytest src/trading_api/modules/core/tests/test_api_health.py::test_healthcheck_returns_200_and_payload -v

# Run with debugger
poetry run pytest --pdb
```

**Integration tests:**

```bash
# Run with verbose output
poetry run pytest tests/integration/ -v -s

# Run specific test file
poetry run pytest tests/integration/test_module_isolation.py -v

# Check logs
tail -f .local/logs/*.log
```

**Port conflicts:**

```bash
# Check ports in use
lsof -i :8000
lsof -i :19720

# Kill processes
make kill-dev
```

---

## Examples

### Example 1: Unit Test for New Endpoint

```python
# backend/src/trading_api/modules/broker/tests/test_positions.py
import pytest
from httpx import AsyncClient

class TestPositions:
    """Test position management endpoints."""

    @pytest.mark.asyncio
    async def test_get_positions(self, async_client: AsyncClient) -> None:
        """Test fetching all positions."""
        response = await async_client.get("/api/v1/broker/positions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_position_by_id(self, async_client: AsyncClient) -> None:
        """Test fetching a specific position."""
        position_id = "POS123"
        response = await async_client.get(f"/api/v1/broker/positions/{position_id}")

        assert response.status_code in [200, 404]
```

### Example 2: WebSocket Unit Test

```python
# backend/src/trading_api/modules/datafeed/tests/test_quotes.py
from fastapi.testclient import TestClient

def test_subscribe_to_quotes(client: TestClient) -> None:
    """Test subscribing to quote updates."""
    with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
        # Subscribe
        websocket.send_json({
            "type": "quotes.subscribe",
            "payload": {"symbols": ["AAPL", "GOOGL"]}
        })

        # Verify response
        response = websocket.receive_json()
        assert response["type"] == "quotes.subscribe.response"
        assert response["payload"]["success"] is True

        # Verify quote updates
        quote = websocket.receive_json()
        assert quote["type"] == "quotes.update"
        assert "symbol" in quote["payload"]
```

### Example 3: Integration Test for Module Isolation

```python
# backend/tests/integration/test_module_isolation.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_core_only_app(no_modules_app):
    """Test that core-only app has only shared infrastructure."""
    api_app, _ = no_modules_app

    async with AsyncClient(app=api_app, base_url="http://test") as client:
        # Core endpoints available
        health = await client.get("/api/v1/core/health")
        assert health.status_code == 200

        version = await client.get("/api/v1/core/version")
        assert version.status_code == 200

        # Module endpoints NOT available
        broker = await client.get("/api/v1/broker/accounts")
        assert broker.status_code == 404

        datafeed = await client.get("/api/v1/datafeed/symbols")
        assert datafeed.status_code == 404
```

### Example 4: Backend Manager Integration Test

```python
# backend/tests/integration/test_backend_manager_integration.py
async def test_08a_custom_module_routes(
    self, session_backend_manager: ServerManager
) -> None:
    """Test custom module routing through nginx."""
    await ensure_started(session_backend_manager)

    nginx_port = session_backend_manager.config.nginx.port

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://127.0.0.1:{nginx_port}/api/v1/broker/accounts",
            timeout=5.0
        )
        assert response.status_code == 200
```

### Example 5: Isolated Integration Test

```python
# backend/tests/integration/test_custom_config.py
async def test_custom_error_handling(tmp_path: Path) -> None:
    """Test error handling with custom configuration.

    Uses isolated instance with unique ports.
    """
    import os

    base_port = 21000 + (os.getpid() % 100) * 10

    config = DeploymentConfig(
        nginx=NginxConfig(port=base_port, ...),
        servers={...},
    )

    manager = ServerManager(config, ...)
    manager.pid_dir = tmp_path / ".pids"
    manager.log_dir = tmp_path / ".logs"

    try:
        # Test logic
        success = await manager.start_all()
        assert success
        # More assertions
    finally:
        await manager.stop_all(timeout=2.0)
```

---

## Related Documentation

### Testing Documentation

- [Testing Guide](../../docs/TESTING.md) - General testing strategies across backend and frontend
- [Backend Manager Unit Tests](../../tests/integration/test_backend_manager_unit.py) - Example unit tests

### Architecture and Design

- [Backend Architecture](../../ARCHITECTURE.md) - Overall system design
- [Modular Backend Architecture](MODULAR_BACKEND_ARCHITECTURE.md) - Module system and organization

### Code Generation

- [Backend Specs & Client Generation](SPECS_AND_CLIENT_GEN.md) - OpenAPI/AsyncAPI spec and client generation
- [WebSocket Router Generation](WS_ROUTERS_GEN.md) - WebSocket router generation guide

### Development

- [Development Guide](../../docs/DEVELOPMENT.md) - Development setup and workflows
- [Makefile Guide](../../MAKEFILE-GUIDE.md) - Build commands and targets

---

## Conclusion

The backend testing strategy provides a comprehensive approach to validating the modular FastAPI application:

**Three-Tier Test Structure:**

- **Unit tests** - Fast, isolated module validation
- **Integration tests** - Multi-process workflows and cross-module communication
- **Boundary tests** - Architectural constraint validation

**Key Principles:**

1. **Minimize overhead** - Use session fixtures to share expensive resources
2. **Maximize isolation** - Test modules independently with selective loading
3. **Ensure autonomy** - Tests should run independently in any order
4. **Clean up properly** - Prevent resource leaks and port conflicts

**Understanding Codegen:**

- OpenAPI/AsyncAPI specs generated during app startup
- Python clients created automatically from specs
- WebSocket routers generated at module instantiation
- All codegen happens before app accepts requests

**Best Practices:**

- Start with unit tests for new features
- Use integration tests for workflows
- Follow test organization conventions
- Use appropriate fixtures for each test type
- Monitor and optimize test performance

**Key Metric**: Aim for:

- Unit tests: < 100ms each
- Module test suite: < 5 seconds
- Integration tests: < 1 minute total
- Full test suite: < 2 minutes

By following these guidelines, you can write efficient, maintainable, and reliable tests that scale with the project.

---

**Last Updated**: November 3, 2025
**Version**: 2.0.0

**Key Metric**: Aim for <1 minute total integration test execution time as the codebase grows.
