---
name: backend-testing
description: Pytest patterns for trader-pro modular backend. Load when writing, debugging, or analyzing backend test coverage
user-invocable: false
---

# Backend Testing

Pytest-specific testing methodology for the trader-pro modular backend. Covers fixture selection, test hierarchy, provider mocking, and project-specific conventions. Apply `test-strategy` skill first for general methodology, then this skill for pytest patterns.

---

## When to Use This Skill

- Writing new backend tests (unit, integration, module, provider)
- Selecting the right fixture pattern for a test target
- Mocking external boundaries (TWS, OAuth, datastores)
- Analyzing backend test coverage gaps
- Debugging pytest failures or fixture issues

---

## Test Hierarchy

| Tier | Location | Purpose | Command |
|------|----------|---------|---------|
| Boundary | `tests/` | Import isolation, registry, config | `make test-boundaries` |
| Unit (manager) | `tests/unit/` | Backend manager logic | `poetry run pytest tests/unit/ -v` |
| Module unit | `modules/<mod>/tests/` | Module endpoints & logic | `make test-module-{name}` |
| Integration | `tests/integration/` | Multi-process, cross-module | `make test-integration` |
| Provider | `providers/<name>/tests/` | Provider capabilities | `make test-provider-{name}` |
| Datastore | `datastores/<impl>/tests/` | Implementation-specific | `make test-datastores` |
| Contract | `tests/integration/test_datastore_contract.py` | Interface compliance | (included in integration) |

---

## Fixture Selection

Classify the test target → select the right fixture pattern:

| Target | Fixture | Scope |
|--------|---------|-------|
| REST API endpoint | `async_client: AsyncClient` | function |
| WebSocket endpoint | `client: TestClient` | function |
| Module isolation | `create_test_app(enabled_modules=[...])` | session |
| Production-like (build_modules) | Pattern 1 (full ModularApp) | session |
| Mock providers | Pattern 3 (provider injection) | function |
| TWS trackers | `mock_ibsocket` with `MagicMock(spec=IbSocketWiringInterface)` | function |
| PostgreSQL | `test_settings` → `postgres_datastore` | session |

### Session-Scoped (shared across all tests)

- `test_settings` — Settings SSOT (PostgreSQL auto-provisioned)
- `apps` — Full ModularApp with all modules
- `broker_only_app` / `datafeed_only_app` — Isolated module apps
- `event_loop` — Required for session-scoped async fixtures

### Function-Scoped (fresh per test)

- `async_client` — AsyncClient with `raise_app_exceptions=False`
- `client` — TestClient with `raise_server_exceptions=False`
- `tmp_path` — Temporary directory (pytest built-in)

---

## Common Patterns

### TWS Provider Test

```python
from unittest.mock import MagicMock, PropertyMock
from trading_api.providers.tws.wiring_interfaces import IbSocketWiringInterface

@pytest.fixture
def mock_ibsocket():
    mock = MagicMock(spec=IbSocketWiringInterface)
    counter = {"value": 0}
    def get_next_id():
        counter["value"] += 1
        return counter["value"]
    type(mock).next_req_id = PropertyMock(side_effect=get_next_id)
    mock.send_message = MagicMock()
    return mock
```

### Auth Mocking

```python
@pytest.fixture
def mock_google_oauth(monkeypatch):
    async def mock_parse_id_token(token, claims_options):
        return {"sub": "test_user_id", "email": "test@example.com", "email_verified": True}
    monkeypatch.setattr("authlib.integrations...", mock_parse_id_token)
```

### Datastore Contract Testing

Use parametrized `any_datastore` fixture to run against all implementations (InMemory + Postgres). Use `reset()` for test isolation. Protected by `DATASTORE_ALLOW_RESET=True`.

### PostgreSQL Dual-Path

| Environment | Source | Detection |
|-------------|--------|-----------|
| Local | testcontainers (auto) | `DATASTORE_POSTGRES_DSN` not set |
| CI | Service container | `DATASTORE_POSTGRES_DSN` set |

Both flow through `test_settings` session fixture in `backend/conftest.py`.

---

## Conventions

- **Naming**: `test_{behavior}_when_{condition}`
- **Structure**: Group related tests in `class Test{Feature}:`
- **Pattern**: Arrange → Act → Assert
- **Mocking**: `monkeypatch` over `unittest.mock.patch` when possible
- **Async**: `@pytest.mark.asyncio` for all async tests
- **Docstrings**: Every test gets a docstring explaining the scenario
- **Error testing**: `raise_app_exceptions=False` / `raise_server_exceptions=False`
- **Boundary**: Mock external boundaries (TWS API, Google OAuth), not internal services

### Performance Targets

| Scope | Target |
|-------|--------|
| Unit test | < 100ms each |
| Module suite | < 5 seconds |
| Integration | < 1 minute |
| Full suite | < 2 minutes |

---

## Make Targets

```bash
make -C backend test                  # All tests (incremental/testmon)
make -C backend test-full             # All tests (complete, no testmon)
make -C backend test-modules          # Module tests only
make -C backend test-module-broker    # Specific module
make -C backend test-integration      # Integration tests
make -C backend test-providers        # All provider tests
make -C backend test-provider-tws     # Specific provider
make -C backend test-datastores       # Datastore tests
make -C backend test-boundaries       # Boundary tests
make -C backend test-cov              # With coverage report
```

---

## Testmon Awareness (Incremental Testing)

Default `make test` uses `pytest-testmon` for incremental runs — only re-runs tests affected by changed files. This is fast but has **blind spots**.

### Known Blind Spots

| Changed | Testmon Misses | Explicit Supplement |
|---------|---------------|---------------------|
| `conftest.py` fixtures | Tests using fixtures indirectly (via other fixtures) | `make test-full` for the affected scope |
| Provider callbacks / capabilities | Tests in modules consuming that provider | `make test-module-{consumer}` |
| Pydantic models in `models/` | Tests importing via re-exports or using serialized forms | `make test-modules` |
| `dev-config.yaml` / settings | Tests relying on config values | `make test-boundaries` |
| Dynamic file scanning (boundaries) | Already handled — boundaries always runs explicitly | N/A (built into Makefile) |
| Datastore interface changes | Contract tests + implementation tests | `make test-datastores` |

### Gap Analysis Recipe

After a testmon-incremental run, assess coverage gaps:

1. **List changed files** — `git diff --name-only HEAD~1` (or vs. branch)
2. **Classify each file** — model / fixture / provider / module / config
3. **Check blind spot table** — does the file type have a known blind spot?
4. **Run supplements** — execute the explicit supplement command for any matched blind spot
5. **Verify** — confirm testmon ran + supplements cover the change surface

### Make Targets

```bash
make -C backend test                  # Incremental (testmon) — fast, may miss gaps
make -C backend test-full             # Complete suite — no gaps, slower
make -C backend testmon-forcerun      # Rebuild testmon DB + run all
make -C backend testmon-reset         # Clear testmon DB
make -C backend testmon-status        # Check if DB exists
```

**When to use `test-full` over `test`**: After modifying fixtures, models shared across modules, config files, or provider interfaces.

---

## Anti-Patterns

- ❌ Testing private internals (`__method()`) — test public API instead
- ❌ Mocking internal services — mock external boundaries only
- ❌ Aiming for 100% coverage — prioritize business logic and error paths
- ❌ Using raw `poetry run pytest` — use `make` targets for consistency
- ❌ Trusting testmon blindly after cross-cutting changes — check blind spot table
- ✅ Read sibling test files first to match existing patterns
