# Specs and Client Generation Guide

**Version**: 1.0.0  
**Date**: November 11, 2025  
**Status**: ✅ Current Reference

---

## Overview

This document explains the automatic generation of OpenAPI/AsyncAPI specifications and Python HTTP clients in the modular backend. Generation happens at **two levels**:

1. **Module Level** - Each module generates its own specs and clients
2. **Modular App Level** - Main app merges all module specs

### Primary Command: `make generate`

**`make generate` is the single point of access for all client generation operations.**

```bash
# Generate everything for all modules
make generate

# Generate for specific module(s)
make generate modules=broker
make generate modules=broker,datafeed

# Generate to custom output directory
make generate output_dir=/tmp/specs
```

This unified command handles:

- ✅ OpenAPI specification generation
- ✅ AsyncAPI specification generation
- ✅ Python HTTP client generation
- ✅ WebSocket router generation (automatic)
- ✅ Client index updates

**See the [Manual Generation](#manual-generation---make-generate) section for complete usage details.**

### What Gets Generated

**Per Module**:

- `specs_generated/{module}_openapi.json` - REST API specification
- `specs_generated/{module}_asyncapi.json` - WebSocket API specification (if WS routers exist)
- `client_generated/{module}_client.py` - Python HTTP client

**App Level**:

- `/api/v1/openapi.json` - Merged OpenAPI from all modules
- `/api/v1/ws/asyncapi.json` - Merged AsyncAPI from all modules (if WS endpoints exist)

---

## Generation Levels

### Level 1: Module-Scoped Generation

Each module's specs are generated via the `ModuleApp` wrapper class, which creates versioned FastAPI and FastWSAdapter instances.

**Trigger**: Manual generation via `make generate` (primary method)  
**Location**: `ModuleApp.gen_specs_and_clients()` in `shared/module_interface.py`  
**Output**: Module's `specs_generated/` and `client_generated/` directories

```python
# In scripts/module_codegen.py (called by make generate)
module = BrokerModule()            # Module instantiation
module_app = ModuleApp(module)     # Create versioned apps
module_app.gen_specs_and_clients() # Generate specs and clients
```

**Process**:

1. Generate OpenAPI spec from module's FastAPI app
2. Compare with existing spec (detect changes)
3. Write spec if changes detected
4. Generate Python HTTP client from updated spec
5. Format generated code (autoflake, black, isort)
6. Update clients index (`__init__.py`)
7. If `ws_app` exists, generate AsyncAPI spec

**Change Detection**:

- Compares new spec with existing file
- Logs specific differences (endpoints, models, properties)
- Only regenerates on meaningful changes
- Ignores metadata (timestamps, etc.)

### Level 2: App-Level Merged Specs

The `ModularApp` class merges all module specs on-demand.

**Trigger**: Access to `/api/v1/openapi.json` or `/api/v1/ws/asyncapi.json`  
**Location**: `ModularApp.openapi()` and `ModularApp.asyncapi()` in `app_factory.py`  
**Output**: Cached merged specifications

```python
class ModularApp(FastAPI):
    def openapi(self) -> dict[str, Any]:
        """Merge OpenAPI specs from all modules."""
        # Merges paths with mount path prefix
        # Merges components (schemas, security schemes)

    def asyncapi(self) -> dict[str, Any]:
        """Merge AsyncAPI specs from all modules."""
        # Merges channels with actual WS endpoint paths
        # Merges component schemas and messages
```

**Merge Strategy**:

**OpenAPI**:

- Paths: Prefixed with `/api/v1/{module}` mount path
- Components: Deduplicated and merged
- Tags: Collected from all modules

**AsyncAPI**:

- Channels: Corrected to actual endpoint paths (`/api/v1/{module}/ws`)
- Schemas: Deduplicated and merged
- Messages: Deduplicated and merged

---

## Generation Flow

### Manual Generation Flow (Primary Method)

```
make generate modules=broker
├─ 1. Makefile invokes: poetry run python scripts/module_codegen.py broker
│
├─ 2. Module Instantiation
│  ├─ Import BrokerModule class
│  ├─ module = BrokerModule()
│  │  ├─ Module.__init__() creates service
│  │  ├─ Imports API routers from api/v1.py
│  │  └─ Imports WS routers from ws/v1/__init__.py
│  │     └─ ⚡ WS router generation happens during import
│  │        ├─ WsRouters.__init__() calls generate_routers(__file__)
│  │        └─ Generates concrete classes in ws_generated/
│
├─ 3. App Creation
│  ├─ module_app = ModuleApp(module)
│  ├─ For each version (v1, v2, ...):
│  │  ├─ Create FastAPI app
│  │  ├─ Include API routers
│  │  ├─ Create FastWSAdapter (if WS routers exist)
│  │  └─ Include WS routers
│
└─ 4. Spec and Client Generation
   └─ module_app.gen_specs_and_clients()
      ├─ For each version:
      │  ├─ Extract OpenAPI spec from FastAPI app
      │  ├─ Compare with existing spec
      │  ├─ Write if changed: {module}_v{N}_openapi.json
      │  ├─ Generate Python client from spec
      │  ├─ Format: autoflake → black → isort
      │  └─ If WS app exists:
      │     ├─ Extract AsyncAPI spec
      │     ├─ Compare with existing spec
      │     └─ Write if changed: {module}_v{N}_asyncapi.json
      │
      └─ Update global client index
```

### Manual Generation - `make generate`

---

> **🎯 PRIMARY COMMAND: `make generate`**
>
> **The single point of access for all spec and client generation operations.**
>
> This command is your go-to tool for generating OpenAPI/AsyncAPI specs and Python clients.

---

#### Command Syntax

```bash
make generate [modules=<modules>] [output_dir=<path>]
```

#### Command Variables

| Variable     | Type   | Default                | Description                                                                     |
| ------------ | ------ | ---------------------- | ------------------------------------------------------------------------------- |
| `modules`    | string | All discovered modules | Comma-separated list of modules to generate (e.g., `broker`, `broker,datafeed`) |
| `output_dir` | path   | Module directory       | Custom output directory for generated files                                     |

**Module Discovery**: The Makefile automatically discovers all modules in `src/trading_api/modules/` (excluding `__pycache__`).

#### What Gets Generated

This unified command generates **all artifacts** for selected modules:

| Artifact          | File Pattern             | Description                                                 |
| ----------------- | ------------------------ | ----------------------------------------------------------- |
| **OpenAPI Spec**  | `{module}_openapi.json`  | REST API specification with all endpoints and models        |
| **AsyncAPI Spec** | `{module}_asyncapi.json` | WebSocket specification (only if module has WS routers)     |
| **Python Client** | `{module}_client.py`     | Type-safe async HTTP client using httpx                     |
| **Client Index**  | `__init__.py`            | Global index exporting all available clients                |
| **WS Routers**    | `ws_generated/*.py`      | Auto-generated concrete router classes (during module init) |

---

#### Usage Examples

##### Example 1: Generate All Modules (Default)

**Command**:

```bash
cd backend
make generate
```

**What happens**:

- Discovers all modules: `core`, `broker`, `datafeed`
- Generates specs and clients for each module
- Updates global client index

**Expected Output**:

```
🔨 Generating for modules: core broker datafeed

======================================================================
🔨 Generating for module: core
======================================================================
📝 Creating new OpenAPI spec for 'core'
✅ Updated OpenAPI spec: .../core/specs_generated/core_openapi.json
✅ Generated Python client for 'core'
✅ Updated clients index: 3 clients

======================================================================
🔨 Generating for module: broker
======================================================================
🔄 OpenAPI spec changes detected for 'broker':
   • Added endpoints: /orders/{orderId}/brackets
   • Added models: PositionBrackets
✅ Updated OpenAPI spec: .../broker/specs_generated/broker_openapi.json
✅ Generated Python client for 'broker'
📝 Creating new AsyncAPI spec for 'broker'
✅ Updated AsyncAPI spec: .../broker/specs_generated/broker_asyncapi.json
✅ Updated clients index: 3 clients

======================================================================
🔨 Generating for module: datafeed
======================================================================
✅ No changes in OpenAPI spec for 'datafeed'
✅ No changes in AsyncAPI spec for 'datafeed'

======================================================================
✅ Generation complete for all modules
======================================================================
```

##### Example 2: Generate Single Module

**Command**:

```bash
make generate modules=broker
```

**What happens**:

- Generates only for `broker` module
- Faster than generating all modules
- Useful after making changes to specific module

**Use case**: You just added a new endpoint to broker API

##### Example 3: Generate Multiple Specific Modules

**Command**:

```bash
make generate modules=broker,datafeed
```

**Important**:

- ✅ NO spaces after comma: `broker,datafeed`
- ❌ WITH spaces will fail: `broker, datafeed`

**What happens**:

- Generates for `broker` and `datafeed` only
- Skips `core` module (unless it has changes)

##### Example 4: Generate to Custom Directory

**Command**:

```bash
make generate output_dir=/tmp/specs
```

**What happens**:

- All modules generated to `/tmp/specs/` instead of module directories
- Useful for CI/CD or external package distribution

**Output structure**:

```
/tmp/specs/
├── specs_generated/
│   ├── core_openapi.json
│   ├── broker_openapi.json
│   ├── broker_asyncapi.json
│   ├── datafeed_openapi.json
│   └── datafeed_asyncapi.json
└── client_generated/
    ├── core_client.py
    ├── broker_client.py
    ├── datafeed_client.py
    └── __init__.py
```

##### Example 5: Combine Module Selection + Custom Output

**Command**:

```bash
make generate modules=broker output_dir=/tmp/broker-specs
```

**What happens**:

- Generates only broker module
- Outputs to `/tmp/broker-specs/`
- Perfect for distributing broker client separately

**Output structure**:

```
/tmp/broker-specs/
├── specs_generated/
│   ├── broker_openapi.json
│   └── broker_asyncapi.json
└── client_generated/
    ├── broker_client.py
    └── __init__.py
```

---

#### Variable Details

##### `modules` Variable

**Syntax**: `modules=<module1>,<module2>,...`

**Behavior**:

- If **NOT specified**: Generates for ALL discovered modules
- If **specified**: Generates only for listed modules
- **Auto-discovery**: Uses `find` to discover modules in `src/trading_api/modules/`

**Module Discovery Logic** (from Makefile):

```makefile
MODULES_DIR = src/trading_api/modules
DISCOVERED_MODULES = $(shell find $(MODULES_DIR) -mindepth 1 -maxdepth 1 -type d \
                      -exec basename {} \; 2>/dev/null | grep -v __pycache__)
```

**List available modules**:

```bash
make list-modules
```

Output:

```
📦 Discovered modules:
  - core
  - broker
  - datafeed
```

**Examples**:

```bash
# Single module
make generate modules=broker

# Multiple modules (NO spaces!)
make generate modules=broker,datafeed
make generate modules=core,broker,datafeed

# All modules (explicit)
make generate modules=core,broker,datafeed

# All modules (implicit - same result)
make generate
```

##### `output_dir` Variable

**Syntax**: `output_dir=<absolute_or_relative_path>`

**Behavior**:

- If **NOT specified**: Uses module's directory (default)
- If **specified**: Generates all output to custom directory

**Default output locations** (when `output_dir` NOT specified):

```
modules/broker/
├── specs_generated/      # Specs go here
│   ├── broker_openapi.json
│   └── broker_asyncapi.json
└── client_generated/     # Clients go here
    ├── broker_client.py
    └── __init__.py
```

**Custom output locations** (when `output_dir=/custom/path`):

```
/custom/path/
├── specs_generated/      # All module specs
│   ├── core_openapi.json
│   ├── broker_openapi.json
│   └── datafeed_openapi.json
└── client_generated/     # All module clients
    ├── core_client.py
    ├── broker_client.py
    ├── datafeed_client.py
    └── __init__.py
```

**Examples**:

```bash
# Absolute path
make generate output_dir=/tmp/specs

# Relative path
make generate output_dir=./build/specs

# User home
make generate output_dir=~/specs

# With module selection
make generate modules=broker output_dir=/tmp/broker
```

**Use cases**:

- ✅ CI/CD artifact generation
- ✅ Distributing clients to external packages
- ✅ Generating to shared network location
- ✅ Creating backup before regeneration

---

#### Generation Workflow

**Internal Process** (what happens when you run `make generate`):

```
1. Module Discovery
   ├─ Scan: src/trading_api/modules/
   ├─ Find: All directories (exclude __pycache__)
   ├─ Result: DISCOVERED_MODULES = core broker datafeed
   └─ Filter: Apply modules variable if specified

2. Module Selection
   ├─ If modules=broker,datafeed → SELECTED_MODULES = broker datafeed
   └─ Else → SELECTED_MODULES = DISCOVERED_MODULES (all)

3. For Each Selected Module
   ├─ Import module class dynamically
   │  └─ Example: broker → BrokerModule
   │
   ├─ Instantiate module
   │  ├─ Creates service instance
   │  ├─ Creates API routers
   │  └─ ⚡ Auto-generates WS routers (if ws.py exists)
   │     ├─ Parse TypeAlias from ws.py
   │     ├─ Generate concrete router classes
   │     └─ Save to ws_generated/
   │
   ├─ Create FastAPI apps
   │  ├─ api_app = FastAPI with REST routers
   │  └─ ws_app = FastWSAdapter with WS routers (if any)
   │
   ├─ Generate OpenAPI spec
   │  ├─ Extract: api_app.openapi()
   │  ├─ Compare with existing file
   │  ├─ Log differences if detected
   │  ├─ Write: {module}_openapi.json (if changes)
   │  └─ Skip if no changes
   │
   ├─ Generate Python HTTP client
   │  ├─ Parse OpenAPI spec
   │  ├─ Extract operations and parameters
   │  ├─ Collect model imports
   │  ├─ Render Jinja2 template
   │  ├─ Format code: autoflake → black → isort
   │  └─ Write: {module}_client.py
   │
   └─ Generate AsyncAPI spec (if ws_app exists)
      ├─ Extract: ws_app.asyncapi()
      ├─ Compare with existing file
      ├─ Log differences if detected
      ├─ Write: {module}_asyncapi.json (if changes)
      └─ Skip if no changes

4. Update Global Index
   └─ Regenerate: src/trading_api/clients/__init__.py
      ├─ Scan all *_client.py files
      ├─ Import all client classes
      └─ Export via __all__
```

---

#### Common Scenarios

##### Scenario 1: After Adding New API Endpoint

**Situation**: You added `GET /broker/positions/{id}/brackets`

**Command**:

```bash
make generate modules=broker
```

**What happens**:

1. Detects new endpoint in OpenAPI spec
2. Logs: "Added endpoints: /positions/{id}/brackets"
3. Regenerates `broker_client.py` with new method
4. Updates client index

**Verification**:

```bash
# Check generated client has new method
grep -n "getBrackets" modules/broker/client_generated/broker_client.py
```

##### Scenario 2: After Model Schema Change

**Situation**: You added `bracket_orders` field to `Position` model

**Command**:

```bash
make generate modules=broker
```

**What happens**:

1. Detects schema change in components
2. Logs: "Schema 'Position' properties changed"
3. Regenerates client with updated types
4. Updates spec files

##### Scenario 3: New Module Created

**Situation**: You created `modules/trading-signals/`

**Command**:

```bash
# First, verify it's discovered
make list-modules

# Then generate
make generate modules=trading-signals
```

**What happens**:

1. Module appears in discovered modules
2. Generates all artifacts from scratch
3. Adds to global client index

##### Scenario 4: CI/CD Pipeline

**Situation**: Automated spec generation in GitHub Actions

**Command**:

```bash
# In CI workflow
make generate
make lint
make type-check
```

**What happens**:

1. Generates all specs and clients
2. Validates code quality
3. Ensures type safety
4. Fails build if errors

##### Scenario 5: Client Distribution

**Situation**: You want to publish Python client to PyPI

**Command**:

```bash
# Generate to package directory
make generate output_dir=../python-trader-client/src

# Then publish
cd ../python-trader-client
poetry publish
```

##### Scenario 6: Clean Regeneration

**Situation**: Specs are corrupted or out of sync

**Commands**:

```bash
# Option 1: Remove and regenerate
rm -rf modules/broker/specs_generated/
rm -rf modules/broker/client_generated/
make generate modules=broker

# Option 2: Use clean-generated target
make clean-generated
make generate
```

---

#### Makefile Integration Details

**Module Discovery** (automatic):

```makefile
MODULES_DIR = src/trading_api/modules
DISCOVERED_MODULES = $(shell find $(MODULES_DIR) -mindepth 1 -maxdepth 1 -type d \
                      -exec basename {} \; 2>/dev/null | grep -v __pycache__)
```

**Module Selection** (conditional):

```makefile
ifdef modules
    SELECTED_MODULES = $(subst $(comma), ,$(modules))
else
    SELECTED_MODULES = $(DISCOVERED_MODULES)
endif
```

**Generation Loop**:

```makefile
generate:
    @for module in $(SELECTED_MODULES); do \
        if [ -n "$(output_dir)" ]; then \
            poetry run python scripts/module_codegen.py "$$module" "$(output_dir)"; \
        else \
            poetry run python scripts/module_codegen.py "$$module"; \
        fi; \
    done
```

**Error Handling**:

- If generation fails for any module → entire command fails
- Exit code 1 returned to caller
- Useful for CI/CD pipelines

1. **OpenAPI Specification** (`specs_generated/{module}_openapi.json`)

   - All REST endpoints with full request/response schemas
   - Shared models from `trading_api.models`
   - Tags and metadata

2. **AsyncAPI Specification** (`specs_generated/{module}_asyncapi.json`)

   - WebSocket channels and operations
   - Message schemas (subscribe, unsubscribe, data streaming)
   - Only generated if module has WebSocket routers

3. **Python HTTP Client** (`client_generated/{module}_client.py`)

   - Async HTTP client using `httpx`
   - Type-safe methods for all REST endpoints
   - Automatic serialization/deserialization
   - Context manager support

4. **Clients Index** (`src/trading_api/clients/__init__.py`)
   - Auto-updated with all available clients
   - Exports all client classes

**WebSocket Routers** (if `ws.py` exists):

- Generated automatically during module initialization
- Concrete classes in `ws_generated/` directory
- No manual generation needed (happens before spec generation)

#### Detailed Flow

```
make generate modules=broker
│
├─ 1. Module Discovery
│  └─ Validates module exists in modules/ directory
│
├─ 2. Module Instantiation
│  ├─ Import module class: BrokerModule
│  ├─ Instantiate: broker = BrokerModule()
│  └─ ⚡ Triggers WS router generation (if ws.py exists)
│     ├─ Parse TypeAlias declarations
│     ├─ Generate concrete router classes
│     └─ Save to ws_generated/
│
├─ 3. App Creation
│  ├─ api_app, ws_app = broker.create_app()
│  ├─ Include REST routers
│  └─ Include WS routers (from ws_generated/)
│
├─ 4. Spec Generation
│  ├─ Generate OpenAPI spec
│  │  ├─ Extract: api_app.openapi()
│  │  ├─ Compare with existing spec
│  │  ├─ Log differences if detected
│  │  └─ Write: broker_openapi.json
│  │
│  ├─ Generate Python Client
│  │  ├─ Parse OpenAPI spec
│  │  ├─ Extract operations and models
│  │  ├─ Render Jinja2 template
│  │  ├─ Format: autoflake → black → isort
│  │  └─ Write: broker_client.py
│  │
│  └─ Generate AsyncAPI spec (if ws_app)
│     ├─ Extract: ws_app.asyncapi()
│     ├─ Compare with existing spec
│     ├─ Log differences if detected
│     └─ Write: broker_asyncapi.json
│
└─ 5. Index Update
   └─ Update src/trading_api/clients/__init__.py
```

#### Use Cases

**1. After API Changes**

```bash
# Made changes to broker API endpoints
make generate modules=broker
```

**2. New Module Development**

```bash
# Created new trading-signals module
make generate modules=trading-signals
```

**3. Clean Regeneration**

```bash
# Remove old generated files
rm -rf modules/broker/specs_generated/
rm -rf modules/broker/client_generated/

# Regenerate fresh
make generate modules=broker
```

**4. Batch Regeneration**

```bash
# Regenerate all modules after model changes
make generate
```

**5. CI/CD Pipeline**

```bash
# In CI, generate and verify
make generate
make lint        # Verify generated code quality
make type-check  # Verify type safety
```

**6. Client Distribution**

```bash
# Generate clients to separate package directory
make generate output_dir=../python-trading-client/src
```

#### Alternative: Direct Script Usage

For advanced use cases, call the script directly:

```bash
cd backend

# Basic usage
poetry run python scripts/module_codegen.py broker

# With custom output directory
poetry run python scripts/module_codegen.py broker /tmp/output

# Multiple modules (requires loop)
for module in broker datafeed; do
    poetry run python scripts/module_codegen.py $module
done
```

**Script**: `backend/scripts/module_codegen.py`

**When to use direct script**:

- ✅ Custom automation scripts
- ✅ Integration with external tools
- ✅ Debugging generation issues
- ❌ **NOT** for normal development (use `make generate`)

#### Deprecated Commands

⚠️ **These commands are DEPRECATED** - use `make generate` instead:

```bash
# ✅ CURRENT APPROACH
make generate

# Note: The following commands have been removed:
# - make export-openapi-spec (removed)
# - make export-asyncapi-spec (removed)
# - make generate-python-clients (removed)
# - make generate-ws-routers (removed - now auto-generates on app startup)
```

#### Troubleshooting

**Issue: Module not found**

```bash
$ make generate modules=mymodule
# Error: Module 'mymodule' not found

# Solution: Check module exists
ls src/trading_api/modules/mymodule/
make list-modules  # See all available modules
```

**Issue: Generation fails with import error**

```bash
# Error: ModuleNotFoundError: No module named 'trading_api.models.Something'

# Solution: Ensure model exists
grep -r "class Something" src/trading_api/models/
```

**Issue: Syntax error in generated code**

```bash
# Error: SyntaxError in broker_client.py

# Solution: Check OpenAPI spec validity
cat modules/broker/specs_generated/broker_openapi.json | jq .
```

**Issue: Client not in index**

```bash
# Error: ImportError: cannot import name 'BrokerClient'

# Solution: Regenerate to update index
make generate modules=broker
cat src/trading_api/clients/__init__.py  # Verify export
```

#### Verification

**Check what will be generated**:

```bash
# List all available modules
make list-modules

# Expected output:
# 📦 Discovered modules:
#   - core
#   - broker
#   - datafeed
```

**Verify generated files**:

```bash
# After generation
ls modules/broker/specs_generated/     # broker_openapi.json, broker_asyncapi.json
ls modules/broker/client_generated/    # broker_client.py, __init__.py
ls modules/broker/ws_generated/        # Concrete router classes
```

**Test generated client**:

```bash
poetry run python -c "
from trading_api.clients import BrokerClient
print('✅ BrokerClient imported successfully')
print(BrokerClient.__doc__)
"
```

---

## Python Client Generation

### Client Structure

Generated clients are async HTTP clients using `httpx`:

```python
# Generated: client_generated/broker_client.py
from typing import Any
import httpx
from trading_api.models import PlacedOrder, PreOrder  # Shared models

class BrokerClient:
    """Auto-generated async HTTP client for broker module."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0
    ):
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout
        )

    async def placeOrder(self, order: PreOrder) -> PlacedOrder:
        """POST /api/v1/broker/orders"""
        response = await self._client.post(
            "/api/v1/broker/orders",
            json=order.model_dump(mode="json")
        )
        response.raise_for_status()
        return PlacedOrder.model_validate(response.json())

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
```

### Generation Service

**Location**: `shared/client_generation_service.py`

**Key Methods**:

- `generate_module_client()` - Generate client from OpenAPI spec
- `format_generated_code()` - Apply code formatters
- `update_clients_index()` - Update global `__init__.py`

**Template**: `shared/templates/python_client.py.j2`

**Features**:

- Type-safe parameters and return types
- Uses shared models from `trading_api.models`
- Async/await support with `httpx.AsyncClient`
- Context manager support for cleanup
- Configurable base URL and timeout

### Usage Patterns

**Context Manager (Recommended)**:

```python
from trading_api.clients import BrokerClient

async with BrokerClient(base_url="http://broker:8000") as client:
    health = await client.getHealthStatus()
    positions = await client.getPositions()
# Client automatically closed
```

**Manual Lifecycle**:

```python
client = BrokerClient(base_url="http://broker:8000")
try:
    result = await client.placeOrder(order=PreOrder(...))
finally:
    await client.close()
```

---

## WebSocket Router Generation

**Separate Process**: WebSocket routers are generated during module initialization, NOT during spec generation.

**Trigger**: `WsRouters` class instantiation in module's `__init__.py`  
**Location**: `shared/ws/module_router_generator.py`  
**Documentation**: See `WS_ROUTERS_GEN.md`

**Flow**:

1. Module instantiated → `WsRouters.__init__()` called
2. Calls `generate_module_routers(module_name)`
3. Parses TypeAlias declarations from `ws.py`
4. Generates concrete router classes in `ws_generated/`
5. Module imports generated routers
6. Module instantiates routers with service

**Important**: WS router generation happens BEFORE `create_app()`, ensuring routers exist when AsyncAPI spec is generated.

---

## Creating Generation-Compliant Modules

### Checklist

**Required Files**:

- [ ] `modules/{module}/__init__.py` - Implements `Module` protocol
- [ ] `modules/{module}/service.py` - Business logic
- [ ] `modules/{module}/api.py` - REST endpoints (APIRouter)

**Optional for WebSocket Support**:

- [ ] `modules/{module}/ws.py` - WebSocket router TypeAlias declarations
- [ ] Service implements `WsRouteService` protocol (has `broadcast()` method)

**Generated Directories** (auto-created):

- `specs_generated/` - OpenAPI and AsyncAPI specs
- `client_generated/` - Python HTTP client
- `ws_generated/` - WebSocket routers (if ws.py exists)

### Module Template

```python
# modules/{module}/__init__.py
from pathlib import Path
from fastapi.routing import APIRouter
from trading_api.shared import Module
from trading_api.shared.ws.ws_route_interface import WsRouteInterface

from .api import {Module}Api
from .service import {Module}Service
from .ws import {Module}WsRouters  # Optional

class {Module}Module(Module):
    """Module description."""

    def __init__(self) -> None:
        super().__init__()
        self._service = {Module}Service()

        # No prefix - routes at root level within module app
        self._api_routers = [
            {Module}Api(service=self.service, prefix="", tags=[self.name])
        ]

        # Optional: WebSocket routers
        self._ws_routers = {Module}WsRouters(service=self.service)

    @property
    def name(self) -> str:
        return "{module}"

    @property
    def module_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def service(self) -> {Module}Service:
        return self._service

    @property
    def api_routers(self) -> list[APIRouter]:
        return self._api_routers

    @property
    def ws_routers(self) -> list[WsRouteInterface]:
        return self._ws_routers

    @property
    def tags(self) -> list[dict[str, str]]:
        return [{
            "name": "{module}",
            "description": "Module description"
        }]
```

### REST API Template

```python
# modules/{module}/api.py
from fastapi import APIRouter
from trading_api.models import SomeModel

class {Module}Api(APIRouter):
    """REST API endpoints for {module} module."""

    def __init__(self, service: {Module}Service, **kwargs):
        super().__init__(**kwargs)
        self.service = service

        # Register routes
        self.add_api_route("/resource", self.get_resource, methods=["GET"])

    async def get_resource(self) -> SomeModel:
        """Get resource."""
        return await self.service.get_resource()
```

### WebSocket Template

```python
# modules/{module}/ws.py
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.module_router_generator import generate_module_routers

if TYPE_CHECKING:
    # TypeAlias declarations for generation
    DataWsRouter: TypeAlias = WsRouter[DataRequest, DataResponse]

class {Module}WsRouters(list[WsRouteInterface]):
    def __init__(self, service: WsRouteService):
        # Generate routers from TypeAlias declarations
        module_name = os.path.basename(os.path.dirname(__file__))
        generate_module_routers(module_name)

        # Import generated routers
        if not TYPE_CHECKING:
            from .ws_generated import DataWsRouter

        # Instantiate routers
        data_router = DataWsRouter(route="data", service=service)
        super().__init__([data_router])
```

---

## Output Structure

### Module Directory After Generation

```
modules/{module}/
├── __init__.py                  # Module class
├── service.py                   # Business logic
├── api.py                       # REST endpoints
├── ws.py                        # WS router declarations (optional)
│
├── specs_generated/             # Generated specs
│   ├── {module}_openapi.json   # REST API spec
│   └── {module}_asyncapi.json  # WebSocket spec (if WS)
│
├── client_generated/            # Generated Python client
│   ├── {module}_client.py      # Async HTTP client
│   └── __init__.py              # Exports client class
│
├── ws_generated/                # Generated WS routers (if ws.py)
│   ├── __init__.py              # Exports all routers
│   └── {router}.py              # Concrete router classes
│
└── tests/                       # Module tests
    ├── test_api.py
    ├── test_service.py
    └── test_ws.py
```

### Global Clients Index

```python
# src/trading_api/clients/__init__.py (auto-generated)
from .broker_client import BrokerClient
from .datafeed_client import DatafeedClient
from .core_client import CoreClient

__all__ = ["BrokerClient", "DatafeedClient", "CoreClient"]
```

---

## Verification Commands

### Check Generated Files

```bash
# List module specs
ls backend/src/trading_api/modules/{module}/specs_generated/

# List module clients
ls backend/src/trading_api/modules/{module}/client_generated/

# List WS routers
ls backend/src/trading_api/modules/{module}/ws_generated/
```

### Validate Generated Code

```bash
# From backend/ directory
make lint        # Runs black, isort, ruff, flake8
make type-check  # Runs mypy, pyright
make test        # Runs all tests
```

### Test Client Import

```bash
cd backend
poetry run python -c "from trading_api.clients import BrokerClient; print(BrokerClient.__doc__)"
```

### View Merged Specs

```bash
# Start server
make dev

# Access merged specs
curl http://localhost:8000/api/v1/openapi.json
curl http://localhost:8000/api/v1/ws/asyncapi.json  # If WS endpoints exist
```

---

## Regeneration Triggers

### Automatic Triggers

**Module-Level Generation** (during startup):

- ✅ First module startup (no existing specs)
- ✅ API endpoint added/removed/modified
- ✅ Request/response model changes
- ✅ WebSocket channel added/removed
- ✅ Model schema changes (properties, types)

**NOT Triggered**:

- ❌ No spec changes detected
- ❌ Metadata-only changes (timestamps, descriptions)

### Manual Regeneration - Primary Method

**Use `make generate` for all manual regeneration needs:**

```bash
# Generate for specific module (most common)
make generate modules=broker

# Generate for multiple modules
make generate modules=broker,datafeed

# Generate all modules
make generate
```

**When to manually regenerate**:

- After making API changes (new endpoints, modified models)
- When specs are missing or corrupted
- For CI/CD pipelines
- When distributing clients to external packages
- After pulling changes from other developers

### Clean Regeneration

**Full cleanup and regeneration**:

```bash
# Option 1: Remove and regenerate specific module
rm -rf modules/broker/specs_generated/
rm -rf modules/broker/client_generated/
make generate modules=broker

# Option 2: Clean all generated files
make clean-generated
make generate

# Option 3: Restart server (auto-regenerates)
make dev
```

---

## Troubleshooting

### Issue: Client Generation Fails

**Symptom**: Error during module startup about client generation

**Causes**:

- OpenAPI spec malformed
- Invalid model references
- Template rendering error

**Solution**:

```bash
# Check OpenAPI spec validity
poetry run python -c "
import json
with open('modules/{module}/specs_generated/{module}_openapi.json') as f:
    spec = json.load(f)
    print('Valid JSON')
"

# Manually trigger generation with verbose output
poetry run python scripts/module_codegen.py {module}
```

### Issue: Spec Changes Not Detected

**Symptom**: Made API changes but spec not regenerated

**Causes**:

- Spec comparison not detecting changes
- Old cached spec file

**Solution**:

```bash
# Delete existing spec
rm modules/{module}/specs_generated/{module}_openapi.json

# Restart server
make dev
```

### Issue: Merged Spec Missing Paths

**Symptom**: `/api/v1/openapi.json` doesn't show all module endpoints

**Causes**:

- Module not enabled
- Module app not mounted
- Cached spec

**Solution**:

```bash
# Check enabled modules
grep -r "enabled_module_names" .

# Clear cache and restart
rm -rf **/__pycache__
make dev
```

### Issue: Client Import Fails

**Symptom**: `ModuleNotFoundError: No module named 'trading_api.clients.{module}_client'`

**Causes**:

- Client not generated
- Index not updated

**Solution**:

```bash
# Check if client exists
ls modules/{module}/client_generated/

# Regenerate
make generate modules={module}

# Verify index
cat src/trading_api/clients/__init__.py
```

---

## Related Documentation

**Core Architecture**:

- `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md` - Module system overview
- `backend/docs/WS_ROUTERS_GEN.md` - WebSocket router generation

**Implementation**:

- `shared/module_interface.py` - Module protocol and spec generation
- `shared/client_generation_service.py` - Client generation service
- `app_factory.py` - Merged spec generation
- `scripts/module_codegen.py` - Manual generation script

**Examples**:

- `modules/broker/` - Broker module (REST + WebSocket)
- `modules/datafeed/` - Datafeed module (REST + WebSocket)
- `modules/core/` - Core module (REST only)

**Testing**:

- `docs/TESTING.md` - Testing strategy
- `modules/{module}/tests/` - Module test examples

---

## Quick Reference

### Primary Command: `make generate`

**The single point of access for all generation operations.**

```bash
# Generate all modules (most common)
make generate

# Generate specific module(s)
make generate modules=broker
make generate modules=broker,datafeed

# Generate to custom location
make generate output_dir=/tmp/specs
make generate modules=broker output_dir=/tmp/broker
```

### Additional Commands

```bash
# List available modules
make list-modules

# Development server (triggers auto-generation on startup)
make dev

# Verify generated code
make lint        # Code quality
make type-check  # Type safety
make test        # All tests
```

### File Locations

```
# Module-level outputs
modules/{module}/specs_generated/{module}_openapi.json
modules/{module}/specs_generated/{module}_asyncapi.json
modules/{module}/client_generated/{module}_client.py
modules/{module}/ws_generated/{router}.py

# App-level merged specs (runtime)
/api/v1/openapi.json            # Merged OpenAPI
/api/v1/ws/asyncapi.json        # Merged AsyncAPI

# Global client index
src/trading_api/clients/__init__.py
```

### Key Classes

```python
# Module Protocol
Module.gen_specs_and_clients()  # Generate specs and client
Module.create_app()             # Create FastAPI app with lifespan

# App Factory
ModularApp.openapi()        # Merged OpenAPI spec
ModularApp.asyncapi()       # Merged AsyncAPI spec

# Client Generation
ClientGenerationService.generate_module_client()
ClientGenerationService.format_generated_code()
ClientGenerationService.update_clients_index()
```

---

**Last Updated**: November 2, 2025  
**Maintainer**: Backend Team  
**Status**: ✅ Production-ready
