---
name: provider-development
description: Capability-based provider system patterns. Load when creating providers or wiring module-provider integration
user-invocable: false
---

# Provider Development

Methodology for creating, extending, and testing providers within the capability-based provider system. Covers the `Provider` base class, capability interfaces, auto-discovery, lifecycle management, service wiring, error handling, and configuration patterns.

---

## When to Use This Skill

- Creating a new provider (new external integration)
- Defining a new capability interface (new domain of functionality)
- Wiring a provider to a module service
- Debugging provider discovery, loading, or capability matching
- Writing provider tests (unit, integration, registry)
- Understanding the 4-phase application startup lifecycle

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│ Application Startup (4 Phases)                                      │
│                                                                     │
│  Phase 1: Discovery                                                 │
│    ModuleRegistry.auto_discover()     → registered module classes    │
│    ProviderRegistry.auto_discover()   → registered provider classes  │
│    DatastoreRegistry.auto_discover()  → registered datastore classes │
│                                                                     │
│  Phase 2: Static Analysis                                           │
│    module.service_class.provider_capabilities()  → required specs    │
│    provider_class.capabilities()                 → provided specs    │
│    (No instantiation — classmethods only)                           │
│                                                                     │
│  Phase 3: Provider Loading (lazy, thread-safe)                      │
│    ProviderRegistry.get_providers(required_capabilities)             │
│      → CapabilitySpec.matches() for each requirement                │
│      → _get_instance() with double-checked locking                  │
│      → List[Provider] (deduplicated)                                │
│                                                                     │
│  Phase 4: Module Instantiation                                      │
│    Module(providers=providers, datastores=datastores)                │
│      → Service.__init__() builds _capability_map                    │
│      → Fail-fast: raises if any required capability unmet           │
│                                                                     │
│  Shutdown:                                                          │
│    ModularApp.shutdown() → each provider.shutdown()                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Runtime**: API/WS Request → Service → `get_capability_provider(Capability)` → Provider method → External system. Module NEVER imports Provider directly.

---

## Core Concepts

### 1. Capability-Based Injection

The system uses a **capability** abstraction to decouple modules from providers:

```
Module declares: "I need capability X"     → ProviderCapabilitySpec(name="x")
Provider declares: "I provide capability X" → ProviderCapabilitySpec(name="x")
Registry matches: requirement ↔ provider   → CapabilitySpec.matches()
Service receives: typed provider instance   → get_capability_provider("x")
```

**CapabilitySpec matching rules**:
- Name must match exactly (e.g., `"broker"` == `"broker"`)
- If requirement specifies no version → any provider version matches
- If requirement specifies a version → only exact version matches
- The spec is a frozen dataclass (immutable after creation)

Current capability names: `"auth"`, `"broker"`, `"datafeed"` (defined as `Literal` type).

### 2. Module Isolation Principle

Services know capability interfaces, never concrete providers:

```python
# CORRECT — service uses capability interface
class BrokerService(ServiceInterface):
    @property
    def broker_provider(self) -> BrokerCapability:
        provider = self.get_capability_provider("broker")
        assert isinstance(provider, BrokerCapability)
        return provider

# WRONG — service imports concrete provider
from trading_api.providers.tws import TWSBrokerProvider  # NEVER DO THIS
```

This enables swapping providers without touching module code (e.g., `FakeBrokerProvider` for testing, `TWSBrokerProvider` for production).

### 3. Fail-Fast Validation

`ServiceInterface.__init__()` builds a `_capability_map` and validates ALL required capabilities are satisfied at startup — not at request time. If any capability is missing, the app fails to start with a clear error:

```
CommonException: Service 'broker' requires capability 'broker' but no provider found.
Available providers: ['GoogleProvider']
```

This guarantees that if the app starts, all capability requirements are met.

---

## Creating a New Provider

### Step 1: Define the Capability Interface (if new)

If the provider implements an existing capability, skip to Step 2.

```python
# capabilities/my_domain.py
from abc import ABC, abstractmethod

class MyDomainCapability(ABC):
    """My domain capability interface.

    [PROVIDER-AGNOSTIC]: All methods use domain models only.
    [ASYNC]: Data-fetching methods are async.
    [STREAMING]: Subscription methods use callback pattern.
    """

    # --- Snapshot methods (request/response) ---
    @abstractmethod
    async def get_something(self, id: str) -> Something: ...

    # --- Streaming methods (callback-based) ---
    @abstractmethod
    async def subscribe_something(
        self,
        callback: Callable[[Something], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]],
    ) -> str:  # returns subscription ID
        ...

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None: ...
```

**Two method categories** (this is a core pattern):

| Category | Signature | Use Case |
|----------|-----------|----------|
| **Snapshot** | `async def method(params) -> Result` | One-shot request/response |
| **Streaming** | `async def subscribe_*(callback, on_error) -> str` | Continuous data push |

Streaming methods:
- Take `callback` (data push) and `on_error` (error push) as async callables
- Return a `str` subscription ID for later unsubscribe
- The unsubscribe method is synchronous (`def`, not `async def`)

**Constraints**:
- Use only domain models in the interface (no provider-specific types)
- Every method that does I/O must be `async`
- Streaming callbacks may be invoked from provider threads — document `[THREAD-SAFE]`

Register the new capability name in the `ProviderCapabilityName` literal type.

### Step 2: Create the Provider Class

```
providers/
  my_provider/
    __init__.py          # exports MyProvider in __all__
    my_provider.py       # implementation (optional split)
    tests/
      test_my_provider.py
```

```python
# providers/my_provider/__init__.py
from pathlib import Path
from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.shared import Provider

__all__ = ["MyProvider"]

class MyProvider(Provider, MyDomainCapability):

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="my_domain")]

    @property
    def config(self) -> MyProviderConfig:
        return self._config

    def __init__(self, config: MyProviderConfig | None = None):
        self._config = config or MyProviderConfig()  # auto-loads from env

    def shutdown(self) -> None:
        # Cleanup: close connections, cancel tasks, etc.
        pass

    # Implement all MyDomainCapability abstract methods...
```

**Critical constraints**:

| Constraint | Why | Consequence if Violated |
|------------|-----|------------------------|
| `capabilities()` must be `@classmethod` | Registry introspects without instantiation (Phase 2) | Provider never discovered |
| `provider_dir()` must be `@classmethod` returning `Path(__file__).parent` | Canonical name derived from directory | Wrong name in logs/errors |
| `__all__` must list the provider class | Auto-discovery scans `__all__` for `Provider` subclasses | Provider silently ignored |
| Default constructor must work (`MyProvider()`) | Registry calls `provider_class()` with no args | Instantiation crash |
| `config` parameter allows test injection | Tests pass mock config without env vars | Untestable provider |

### Step 3: Create Provider Configuration

```python
# models/providers/my_provider_configs.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from trading_api.models.common import ProviderConfig

class MyProviderConfig(ProviderConfig):
    host: str = "127.0.0.1"
    port: int = 8080
    api_key: str = ""

    model_config = SettingsConfigDict(
        env_prefix="MY_PROVIDER_",       # MY_PROVIDER_HOST, MY_PROVIDER_PORT, etc.
        env_file=".env.local",
        extra="ignore",
    )
```

**Pattern**: All configs extend `ProviderConfig` (which extends `BaseSettings` and provides `enabled: bool = True`). Environment variables auto-populate fields via `env_prefix`.

**Test override**: Pass a config object to bypass env vars:
```python
provider = MyProvider(config=MyProviderConfig(host="test", port=9999))
```

### Step 4: Wire to Module Service

In the module's service, declare the capability requirement and create a typed property:

```python
class MyModuleService(ServiceInterface):

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        return [ProviderCapabilitySpec(name="my_domain")]

    @property
    def my_provider(self) -> MyDomainCapability:
        provider = self.get_capability_provider("my_domain")
        assert isinstance(provider, MyDomainCapability)
        return provider

    async def do_something(self, id: str) -> Something:
        return await self.my_provider.get_something(id)
```

**The typed property pattern**:
1. `get_capability_provider(name)` → O(1) lookup from pre-built `_capability_map`
2. `isinstance()` assert narrows `Provider` → specific capability type
3. Service methods delegate to the typed property

### Step 5: Multi-Capability Providers

A single provider directory can export multiple `Provider` subclasses, each implementing different capabilities:

```python
# providers/my_system/__init__.py
__all__ = ["MySystemDataProvider", "MySystemBrokerProvider"]

class MySystemDataProvider(Provider, DatafeedCapability):
    @classmethod
    def capabilities(cls):
        return [CapabilitySpec(name="datafeed")]
    # ...

class MySystemBrokerProvider(Provider, BrokerCapability):
    @classmethod
    def capabilities(cls):
        return [CapabilitySpec(name="broker")]
    # ...
```

Both providers are auto-discovered from the same directory. They may share internal infrastructure (client connections, utilities) but are independent `Provider` instances with separate lifecycles.

**Use separate client connections** when the external system requires distinct sessions (e.g., TWS uses `client_id=1` for datafeed, `client_id=2` for broker).

---

## Error Handling

### Exception Hierarchy

```
TradingApiException (base)
├── CommonException         COMMON_{DOMAIN}_{ERROR_TYPE}
├── ServiceException        SERVICE_{MODULE}_{ERROR_TYPE}
├── DatastoreException      DATASTORE_{OPERATION}_{ERROR_TYPE}
└── ProviderException       PROVIDER_{CAPABILITY}_{ERROR_TYPE}
```

### ProviderException Convention

```python
raise ProviderException(
    provider="tws",           # provider name (from provider_dir().name)
    capability="datafeed",    # capability name
    code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
    message="Symbol 'XYZ' not found",
)
```

**Code format**: `PROVIDER_{CAPABILITY}_{ERROR_TYPE}` — uppercase, underscore-separated.

### Error Classification at Service Level

Services classify provider errors into recoverable/unrecoverable for WebSocket streaming:

```python
_RECOVERABLE_ERROR_CODES = frozenset({
    "PROVIDER_BROKER_TIMEOUT",
    "PROVIDER_BROKER_CONNECTION_LOST",
    "PROVIDER_BROKER_RATE_LIMIT",
})
```

The `_RECOVERABLE_ERROR_CODES` frozenset determines whether a streaming error keeps the subscription alive (with retry hint) or kills the topic. This classification is a **service concern**, not a provider concern — different services may classify the same error code differently.

### Capability-Not-Found Errors

Two levels of protection:
1. **Registry level**: `ProviderRegistry.get_providers()` raises `COMMON_CAPABILITY_NOT_FOUND` if no provider matches
2. **Service level**: `ServiceInterface._resolve_provider_capabilities()` raises the same at init time

Both are fail-fast — the app refuses to start rather than failing at request time.

---

## Provider Lifecycle

| Phase | What Happens | Key Method |
|-------|-------------|------------|
| **Discovery** | Directory scan, `__all__` introspection | `ProviderRegistry.auto_discover()` |
| **Registration** | Class stored by name, no instantiation | `ProviderRegistry.register()` |
| **Static Analysis** | `capabilities()` classmethod called for matching | `CapabilitySpec.matches()` |
| **Lazy Loading** | First `get_providers()` call creates instance | `_get_instance()` with asyncio.Lock |
| **Injection** | Instance passed to Module → Service | `Module.__init__(providers=...)` |
| **Runtime** | Service calls capability methods | `get_capability_provider()` |
| **Shutdown** | Cleanup hook called | `Provider.shutdown()` |

**Lazy loading** uses double-checked locking:
1. Fast path: check `_instances` dict (no lock)
2. Slow path: acquire `asyncio.Lock`, check again, then instantiate
3. Instance cached for all subsequent requests

**Shutdown** is called from `ModularApp.shutdown()` for every loaded provider instance. Use it to close connections, cancel background tasks, release resources.

---

## Internal Provider Architecture

For complex providers with background threads, connection lifecycle, and event callbacks (e.g., TWS provider), see `providers/tws/` as the reference implementation:
- Background thread → `loop.call_soon_threadsafe()` → async boundary
- Wiring interfaces for component communication (not callback injection)
- Tracker pattern for stateful subscriptions (lazy-init via client properties)

---

## Testing Patterns

### Provider Unit Tests
Test capability methods with injected config -- mock external boundaries only.
```python
@pytest.fixture
def provider(mock_config):
    return MyProvider(config=mock_config)

def test_capability_method(provider):
    result = provider.some_method(...)
    assert result == expected
```

### Registry and Fail-Fast Tests
```python
def test_provider_discovered():
    assert MyProvider in ProviderRegistry._providers

def test_missing_capability_fails_fast():
    with pytest.raises(CapabilityNotFoundError):
        service.get_capability_provider(UnprovidedCapability)
```

### Mock Provider for Module Tests
```python
class MockBroker(BrokerCapability):
    """Minimal mock implementing capability interface for module isolation tests."""
    @classmethod
    def capabilities(cls) -> frozenset[type]:
        return frozenset({BrokerCapability})
    # Implement all abstract methods with test doubles
```

---

## Checklist: New Provider

- [ ] Capability interface exists (or create new one in `capabilities/`)
- [ ] Provider directory: `providers/{name}/__init__.py` with `__all__`
- [ ] Provider class extends `Provider` + capability interface(s)
- [ ] `provider_dir()` returns `Path(__file__).parent` (classmethod)
- [ ] `capabilities()` returns list of `CapabilitySpec` (classmethod)
- [ ] `config` property returns typed config
- [ ] Default constructor works without arguments (`MyProvider()`)
- [ ] Config class extends `ProviderConfig`/`BaseSettings` with `env_prefix`
- [ ] `shutdown()` cleans up resources (connections, tasks, files)
- [ ] Service declares `provider_capabilities()` with matching spec
- [ ] Service has typed property: `self.get_capability_provider(name)` + `isinstance` assert
- [ ] Error codes follow `PROVIDER_{CAPABILITY}_{ERROR_TYPE}` convention
- [ ] Unit tests with mock config injection
- [ ] Registry tests: discovery, capability matching
- [ ] Integration test: `AppFactory.create_app()` succeeds

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `capabilities()` as instance method | Add `@classmethod` -- registry calls it without instantiation |
| Missing `__all__` export | Add class to `__all__` -- auto-discovery scans it |
| Constructor requires arguments | Make all params optional -- registry calls `cls()` with no args |
| Importing concrete provider in service | Use capability interface + `get_capability_provider()` |
| No `shutdown()` cleanup | Implement cleanup for connections, threads, tasks |
| Config without `env_prefix` | Set unique `env_prefix` to avoid env var collisions |
| Error code without `PROVIDER_` prefix | Follow `PROVIDER_{CAPABILITY}_{TYPE}` convention |
| All errors classified as recoverable | Only `_RECOVERABLE_ERROR_CODES` entries should be recoverable |
| Testing without config injection | Accept optional `config` param in `__init__` |
