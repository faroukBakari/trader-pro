# Backend Generation Commands Assessment

## Current Generation Infrastructure

### 1. **Generation Commands (Makefile)**

Located in: `backend/Makefile`

| Command                        | Script                               | Output Location                              | Description                                      |
| ------------------------------ | ------------------------------------ | -------------------------------------------- | ------------------------------------------------ |
| `make export-openapi-spec`     | `scripts/export_openapi_spec.py`     | `modules/{module}/specs/openapi.json`        | Generates OpenAPI specs per module               |
| `make export-asyncapi-spec`    | `scripts/export_asyncapi_spec.py`    | `modules/{module}/specs/asyncapi.json`       | Generates AsyncAPI specs per module              |
| `make generate-python-clients` | `scripts/generate_python_clients.py` | `src/trading_api/clients/{module}_client.py` | Generates Python HTTP clients from OpenAPI specs |
| `make generate-ws-routers`     | Uses `module_router_generator.py`    | `modules/{module}/ws_generated/`             | Generates WebSocket router classes               |
| `make clean-generated`         | N/A (Makefile only)                  | Removes all `*_generated*` files             | Cleanup command                                  |

### 2. **Current Generation Flow**

#### **Standalone Scripts Approach**

```
Manual Command (make)
    ↓
Script Execution
    ↓
File Generation
    ↓
Separate Formatting/Validation
```

#### **Module.gen_specs_and_clients() Approach**

```
Module Lifespan Event
    ↓
gen_specs_and_clients() [automatic]
    ↓
- Generate OpenAPI spec
- Compare with existing (smart updates)
- Generate Python client
- Format generated code
- Update __init__.py
- Generate AsyncAPI spec (if ws_app provided)
```

---

## Key Differences

### **Standalone Scripts**

- ✅ Can run offline (without starting server)
- ✅ Suitable for CI/CD pipelines
- ✅ Explicit control over when generation happens
- ❌ Separate from module lifecycle
- ❌ Duplicate logic across scripts
- ❌ Manual orchestration required
- ❌ No smart diff detection (export\_\*\_spec.py don't compare)

### **Module.gen_specs_and_clients()**

- ✅ Integrated into module lifecycle
- ✅ Smart diff detection (only updates when needed)
- ✅ Automatic formatting and validation
- ✅ Single source of truth for generation logic
- ✅ Auto-updates **init**.py
- ❌ Requires app startup (not offline)
- ❌ Currently only called during lifespan event

---

## Generation Outputs & Patterns

### **Output Directories (using `*_generated*` pattern)**

1. **WebSocket Routers**

   - Location: `modules/{module}/ws_generated/`
   - Pattern: `*_generated*` ✅
   - Contains: `{RouterName}.py`, `__init__.py`

2. **OpenAPI Specs**

   - Location: `modules/{module}/specs_generated/`
   - Pattern: `*_generated*` ✅
   - Contains: `{module}_openapi.json`

3. **AsyncAPI Specs**

   - Location: `modules/{module}/specs_generated/`
   - Pattern: `*_generated*` ✅
   - Contains: `{module}_asyncapi.json`

4. **Python HTTP Clients**
   - Location: `src/trading_api/client_generated/`
   - Pattern: `*_generated*` ✅
   - Contains: `{module}_client.py`, `__init__.py`

**Note:** All outputs now follow `*_generated*` naming pattern for consistent cleanup!

---

## Services & Utilities

### **ClientGenerationService**

Location: `src/trading_api/shared/client_generation_service.py`

**Methods:**

- `generate_module_client()` - Generate client from OpenAPI spec
- `update_clients_index()` - Update **init**.py with all clients
- `format_generated_code()` - Format with autoflake/black/isort
- `_verify_all_routes_generated()` - Validate completeness

**Used by:**

- `Module.gen_specs_and_clients()` ✅
- `scripts/generate_python_clients.py` ❌ (duplicates logic)

### **Module Router Generator**

Location: `src/trading_api/shared/ws/module_router_generator.py`

**Functions:**

- `generate_module_routers()` - Generate WS routers for a module
- `parse_router_specs_from_file()` - Parse TypeAlias from ws.py
- Quality checks: Black, Ruff, Flake8, Mypy, Isort

**Used by:**

- `make generate-ws-routers` ✅
- Not integrated into `Module.gen_specs_and_clients()` ❌

---

## Opportunities for Consolidation

### **1. Leverage `gen_specs_and_clients()` as Primary Interface**

**Current Issues:**

- Duplicate logic between `export_openapi_spec.py` and `gen_specs_and_clients()`
- No smart diff detection in export scripts
- Manual formatting orchestration in scripts
- Scattered validation logic

**Proposed Solution:**

```bash
# Unified generation command
make generate                           # Generate for all modules (auto-discovered)
make generate modules=broker            # Generate for specific module
make generate modules=broker,datafeed   # Generate for multiple modules
make list-modules                       # List all discovered modules
```

### **2. Integrate WebSocket Router Generation**

**Gap:** `gen_specs_and_clients()` doesn't generate WS routers

**Proposed Enhancement:**

```python
class Module:
    def gen_specs_and_clients(
        self,
        api_app: FastAPI,
        ws_app: FastWSAdapter | None = None,
        clean_first: bool = False,
        output_dir: Path | None = None,
        generate_ws_routers: bool = True,  # NEW
    ) -> None:
        # ... existing logic ...

        # NEW: Generate WS routers if requested
        if generate_ws_routers and self.ws_routers:
            from trading_api.shared.ws.module_router_generator import generate_module_routers
            generate_module_routers(self.name, silent=False)
```

### **3. Create Offline Generation Script**

**Gap:** `gen_specs_and_clients()` requires app startup

**Proposed Solution:**

```makefile
# No separate script needed! Call Module.gen_specs_and_clients() directly from Makefile
generate:
	@for module in $(SELECTED_MODULES); do \
		poetry run python -c "
		import sys;
		from pathlib import Path;
		sys.path.insert(0, str(Path.cwd() / 'src'));
		# ... load module and call gen_specs_and_clients() ...
		"; \
	done
```

### **4. Consolidate Script Logic**

**Scripts to Simplify/Remove:**

- `export_openapi_spec.py` → Use `gen_specs_and_clients()` via Makefile
- `export_asyncapi_spec.py` → Use `gen_specs_and_clients()` via Makefile
- `generate_python_clients.py` → Use `gen_specs_and_clients()` via Makefile
- No need for `generate_all.py` → Call directly from Makefile

**Keep:**

- `verify_ws_routers.py` → Validation tool (different purpose)
- `validate_modules.py` → Validation tool (different purpose)

---

## Recommended Architecture

### **Unified Generation Flow**

```
┌─────────────────────────────────────┐
│  make list-modules                  │  ← List all discovered modules
│  make generate                      │  ← Generate all modules (auto-discovered)
│  make generate modules=broker       │  ← Generate specific module
│  make generate modules=broker,data* │  ← Generate multiple modules (comma-separated)
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Makefile inline Python code        │
│  - Loop through SELECTED_MODULES    │
│  - Load module class dynamically    │
│  - Create minimal app (no lifespan) │
│  - Call gen_specs_and_clients()     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Module.gen_specs_and_clients()     │
│  - Generate OpenAPI spec            │
│  - Generate AsyncAPI spec           │
│  - Generate Python clients          │
│  - Generate WS routers (NEW)        │
│  - Smart diff detection             │
│  - Auto-formatting                  │
│  - Auto-validation                  │
└─────────────────────────────────────┘
```

### **Benefits**

1. ✅ **Single source of truth** for generation logic
2. ✅ **Smart updates** (diff detection prevents unnecessary regeneration)
3. ✅ **Consistent formatting** (all generated code formatted the same way)
4. ✅ **Automatic validation** (routes verified, quality checks run)
5. ✅ **Simplified Makefile** (fewer commands, clearer intent)
6. ✅ **Easier maintenance** (update logic in one place)
7. ✅ **Better CI/CD** (offline generation without full server startup)

---

## Detailed Makefile Design

### **New Commands**

```makefile
# Module discovery (similar to existing DISCOVERED_MODULES pattern)
MODULES_DIR = src/trading_api/modules
DISCOVERED_MODULES = $(shell find $(MODULES_DIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | grep -v __pycache__ || echo "")

# Module selection for generation
ifdef modules
	SELECTED_MODULES = $(subst $(comma), ,$(modules))
else
	SELECTED_MODULES = $(DISCOVERED_MODULES)
endif
comma := ,

# List all discovered modules
list-modules:
	@echo "📦 Discovered modules:"
	@for module in $(DISCOVERED_MODULES); do \
		echo "  - $$module"; \
	done

# Unified generation command
generate:
	@echo "🔨 Generating for modules: $(SELECTED_MODULES)"
	@for module in $(SELECTED_MODULES); do \
		echo ""; \
		echo "======================================================================"; \
		echo "🔨 Generating for module: $$module"; \
		echo "======================================================================"; \
		poetry run python -c "\
import sys; \
from pathlib import Path; \
sys.path.insert(0, str(Path.cwd() / 'src')); \
module_path = 'trading_api.modules.$$module'; \
module_class_name = '$$module'.capitalize() + 'Module'; \
module_pkg = __import__(module_path, fromlist=[module_class_name]); \
module_class = getattr(module_pkg, module_class_name); \
module = module_class(); \
api_app, ws_app = module.create_app(base_path='/api/v1'); \
module.gen_specs_and_clients(api_app=api_app, ws_app=ws_app, clean_first=False); \
print('✅ Successfully generated for $$module');" || { echo "❌ Failed for $$module"; exit 1; }; \
	done
	@echo ""
	@echo "======================================================================"
	@echo "✅ Generation complete for all modules"
	@echo "======================================================================"

# Deprecated commands (backward compatibility with warnings)
export-openapi-spec:
	@echo "⚠️  DEPRECATED: 'make export-openapi-spec' is deprecated"
	@echo "   Use: make generate modules=<module_name>"
	@echo "   Or:  make generate  (for all modules)"
	@echo ""
	@sleep 2
	@poetry run python scripts/export_openapi_spec.py

export-asyncapi-spec:
	@echo "⚠️  DEPRECATED: 'make export-asyncapi-spec' is deprecated"
	@echo "   Use: make generate modules=<module_name>"
	@echo "   Or:  make generate  (for all modules)"
	@echo ""
	@sleep 2
	@poetry run python scripts/export_asyncapi_spec.py

generate-python-clients:
	@echo "⚠️  DEPRECATED: 'make generate-python-clients' is deprecated"
	@echo "   Use: make generate modules=<module_name>"
	@echo "   Or:  make generate  (for all modules)"
	@echo ""
	@sleep 2
	@poetry run python scripts/generate_python_clients.py

generate-ws-routers:
	@echo "⚠️  DEPRECATED: 'make generate-ws-routers' is deprecated"
	@echo "   Use: make generate modules=<module_name>"
	@echo "   Or:  make generate  (for all modules)"
	@echo ""
	@sleep 2
	@if [ -n "$(module)" ]; then \
		echo "Generating WebSocket routers for module: $(module)"; \
		poetry run python -c "from trading_api.shared.ws.module_router_generator import generate_module_routers; ..."; \
	else \
		echo "Generating WebSocket routers for all modules..."; \
		for mod in $(DISCOVERED_MODULES); do \
			poetry run python -c "from trading_api.shared.ws.module_router_generator import generate_module_routers; ..."; \
		done; \
	fi
```

### **Usage Examples**

```bash
# List available modules
make list-modules
# Output:
# 📦 Discovered modules:
#   - broker
#   - datafeed

# Generate everything (auto-discover all modules)
make generate

# Generate specific module
make generate modules=broker

# Generate multiple modules
make generate modules=broker,datafeed

# Clean and regenerate
make clean-generated && make generate

# Old commands still work but show deprecation warnings
make export-openapi-spec  # Shows warning, then runs old script
```

---

## Implementation Plan

### **Phase 1: Enhance gen_specs_and_clients()**

1. Add WebSocket router generation support
2. Add configurable output directories
3. Add validation hooks

### **Phase 2: Implement Makefile Generation**

1. Add inline Python code to `generate` target
2. Loop through SELECTED_MODULES and call `gen_specs_and_clients()` for each
3. Handle errors gracefully with proper exit codes
4. No separate script needed!

### **Phase 3: Update Makefile**

1. Add `list-modules` command (auto-discover and display modules)
2. Add unified `generate` command:
   - No params → generate all discovered modules
   - `modules=broker` → generate single module
   - `modules=broker,datafeed` → generate multiple modules
3. Deprecate old commands with helpful migration messages
4. Update documentation and help text

### **Phase 4: Remove Old Scripts**

1. Mark old scripts as deprecated
2. Remove after transition period
3. Update CI/CD to use new commands

### **Phase 5: Testing**

1. Verify all generation outputs match old behavior
2. Test in CI/CD pipelines
3. Test both single-module and all-module modes
4. Verify clean-generated still works

---

## Current State Summary

**What Works Well:**

- ✅ `Module.gen_specs_and_clients()` provides excellent smart update logic
- ✅ `ClientGenerationService` is well-designed and reusable
- ✅ `module_router_generator` handles WS router generation cleanly
- ✅ All outputs follow `*_generated*` pattern for cleanup

**What Needs Improvement:**

- ❌ Duplicate logic across standalone scripts and `gen_specs_and_clients()`
- ❌ No smart diff detection in standalone scripts
- ❌ WS router generation not integrated into `gen_specs_and_clients()`
- ❌ Complex orchestration in Makefile (4 separate commands)
- ❌ No offline generation using `gen_specs_and_clients()` logic

**Next Steps:**

1. Review this assessment
2. Decide on consolidation approach
3. Implement unified generation script
4. Update Makefile and documentation
