# Datastores

**Status**: ✅ Production Ready  
**Last Updated**: January 2026

## Overview

The datastore layer provides a minimal abstraction for data persistence that enables:

- Testability via dependency injection
- PostgreSQL support via `PostgresDatastore` (Wave 2A)
- Per-table read-write locks for concurrent access
- Auto-discovery via `DatastoreRegistry`
- Feature detection via `has_persistence` and `has_transactions` properties

## Directory Structure

```
datastores/
├── __init__.py           # Re-exports for backward compatibility
├── README.md             # This file
├── inmemory/             # InMemoryDatastore implementation
│   ├── __init__.py       # Exports InMemoryDatastore, InMemoryTable
│   └── tests/
└── postgres/             # PostgresDatastore implementation
    ├── __init__.py       # Exports PostgresDatastore, PostgresTable
    └── datastore.py      # Implementation with asyncpg + JSONB
```

## Feature Detection

Datastores expose properties to detect capabilities:

```python
datastore = registry.get_datastores(names=["postgres"])[0]

# Check if data survives restarts
if datastore.has_persistence:
    logger.info("Using persistent datastore")

# Check if ACID transactions are supported
if datastore.has_transactions:
    logger.info("Transactions available")
```

| Property           | InMemory | Postgres |
| ------------------ | -------- | -------- |
| `has_persistence`  | `False`  | `True`   |
| `has_transactions` | `False`  | `True`   |

Services can access persistent storage via `persistent_datastore` property:

```python
class MyService(ServiceInterface):
    async def backup_critical_data(self) -> None:
        store = self.persistent_datastore
        if store is None:
            raise RuntimeError("No persistent datastore available")
        # Use store for critical operations
```

## DatastoreRegistry

The `DatastoreRegistry` mirrors the `ProviderRegistry` pattern with auto-discovery from the `datastores/` directory.

### Usage in AppFactory

```python
from trading_api.shared import DatastoreRegistry

# Registry auto-discovers from datastores/ subdirectories
registry = DatastoreRegistry()
registry.auto_discover()  # Finds inmemory/, postgres/, etc.

# Get all registered datastores
datastores = registry.get_datastores()  # [InMemoryDatastore()]

# Get specific datastore by name
datastores = registry.get_datastores(names=["inmemory"])
```

### AppFactory Integration

The `AppFactory.create_app()` method now uses `DatastoreRegistry`:

```python
factory = AppFactory()
app = await factory.create_app(
    enabled_module_names=["broker", "auth"],
    enabled_provider_names=["fakebroker", "google"],
    enabled_datastore_names=["inmemory"],  # NEW: filter datastores
)
```

### Adding New Datastores

1. Create subdirectory: `datastores/{name}/`
2. Add `__init__.py` with `DatastoreInterface` subclass
3. Export via `__all__` for auto-discovery

```python
# datastores/postgres/__init__.py
from trading_api.shared import DatastoreInterface

__all__ = ["PostgresDatastore"]

class PostgresDatastore(DatastoreInterface):
    ...
```

---

## InMemoryDatastore

Dict-based storage for MVP and testing with:

- Per-table read-write locks for concurrent access
- Async CRUD operations with Pydantic model validation
- Secondary indexing (1:N field → keys mapping)
- Unique indexing (1:1 field → key mapping with constraint enforcement)
- Auto-indexing on `set()` for all registered indexes

### Architecture

```
InMemoryDatastore
└── _tables: dict[str, InMemoryTable]
        │
        ├── __data: dict[str, BaseModel]           # Primary storage
        ├── __indexes: dict[str, dict[str, set[str]]]  # Secondary indexes (1:N)
        ├── __unique_indexes: dict[str, dict[str, str]] # Unique indexes (1:1)
        ├── __lock: RWLock                         # Async read-write lock
        └── __threading_lock: threading.Lock       # Cross-thread sync (TWS)
```

### API Reference

#### TableInterface[T] Methods

`TableInterface` is generic over `T` (a Pydantic `BaseModel`), enabling type-safe returns:

| Method                            | Lock  | Return Type                   | Description                                   |
| --------------------------------- | ----- | ----------------------------- | --------------------------------------------- |
| `get(key, index=None)`            | Read  | `T \| None`                   | Get value by key or indexed field             |
| `get_all(key, index=None)`        | Read  | `list[T]`                     | Get all values matching indexed field         |
| `set(key, value)`                 | Write | `None`                        | Store value, auto-index all registered fields |
| `delete(key, index=None)`         | Write | `bool`                        | Delete by key or indexed field                |
| `exists(key, index=None)`         | Read  | `bool`                        | Check if key/indexed value exists             |
| `keys(index=None)`                | Read  | `list[str]`                   | Get all keys or indexed field values          |
| `values()`                        | Read  | `list[T]`                     | Get all values (deep copies)                  |
| `clear()`                         | Write | `None`                        | Remove all entries and indexes                |
| `count()`                         | Read  | `int`                         | Get entry count                               |
| `iterate()`                       | Read  | `AsyncIterator[tuple[str,T]]` | Async iterate over key-value pairs            |
| `create_index(field_name)`        | Write | `None`                        | Create secondary index (1:N)                  |
| `create_unique_index(field_name)` | Write | `None`                        | Create unique index (1:1)                     |

#### DatastoreInterface Methods

| Method                                              | Description                                                   |
| --------------------------------------------------- | ------------------------------------------------------------- |
| `table(name, *, indexes=None, unique_indexes=None)` | Get or create a named table with optional index configuration |
| `datastore_name()` (classmethod)                    | Canonical name for registry lookup (e.g., "inmemory")         |

### Indexing

#### Construction-Time Index Configuration (Preferred)

Configure indexes when obtaining the table - sync registration, no async calls needed:

```python
# Unique indexes (1:1) and secondary indexes (1:N) at construction
users = datastore.table(
    "users",
    unique_indexes=["email", "google_id"],  # Raises ValueError on duplicate
    indexes=["role"],                         # Multiple records can share value
)
```

#### Unique Index (1:1)

Enforces uniqueness constraint - raises `ValueError` on duplicate:

```python
await table.create_unique_index("email")
await table.set("1", User(id="1", email="alice@example.com"))
await table.set("2", User(id="2", email="alice@example.com"))  # Raises ValueError!
```

### Type-Safe Tables

Use `TableInterface[T]` for compile-time type checking:

```python
from trading_api.shared import DatastoreInterface, TableInterface
from trading_api.models.auth import UserData

class UserRepository:
    def __init__(self, datastore: DatastoreInterface) -> None:
        # Type-safe: users table returns UserData
        self._users: TableInterface[UserData] = datastore.table(
            "users",
            unique_indexes=["email", "google_id"],
        )

    async def get_user(self, user_id: str) -> UserData | None:
        return await self._users.get(user_id)  # Returns UserData | None

    async def list_users(self) -> list[UserData]:
        return await self._users.values()  # Returns list[UserData]
```

### Concurrency Model

- **Read operations**: Concurrent access allowed (multiple readers)
- **Write operations**: Exclusive access (single writer, no readers)
- **Writer priority**: Writers are prioritized to prevent starvation

---

## PostgresDatastore

PostgreSQL datastore using **asyncpg + JSONB** storage pattern. Provides real persistence with ACID transactions.

### Key Design Decisions

- **JSONB Storage**: Schema-flexible storage - each table stores `key TEXT` + `value JSONB`
- **Async Factory Pattern**: Pool creation is async, use `PostgresDatastore.create()` factory
- **No-Op RWLock**: PostgreSQL MVCC provides transaction isolation, app-level locks are redundant
- **Dict Return Type**: `get()` returns dict (not BaseModel) - caller uses `model_validate()` for conversion

### Usage

```python
from trading_api.datastores.postgres import PostgresDatastore

# Create with async factory (required for asyncpg pool)
datastore = await PostgresDatastore.create()

# Or with custom DSN
datastore = await PostgresDatastore.create(
    dsn="postgresql://user:pass@localhost:5432/db",
    min_size=2,
    max_size=10,
)

# Get table with indexes
users = datastore.table(
    "users",
    unique_indexes=["email", "google_id"],
    indexes=["role"],
)

# Store Pydantic model
await users.set("user123", user_model)

# Retrieve as dict, convert to model
data = await users.get("user123")
if data:
    user = User.model_validate(data)
```

### Environment Configuration

Set PostgreSQL connection via environment variables:

```bash
# Option 1: Full DSN
export DATASTORE_POSTGRES_DSN=postgresql://user:pass@localhost:5432/dbname

# Option 2: Individual variables
export DATASTORE_POSTGRES_USER=postgres
export DATASTORE_POSTGRES_PASSWORD=secret
export DATASTORE_POSTGRES_HOST=localhost
export DATASTORE_POSTGRES_PORT=5432
export DATASTORE_POSTGRES_DB=traderpro
```

### Registry Integration

The registry handles async initialization automatically:

```python
registry = DatastoreRegistry()
registry.auto_discover()  # Detects postgres/ requires async init

# Use async getter for datastores requiring async init
datastores = await registry.get_datastores_async(names=["postgres"])
```

### JSONB Table Schema

Each PostgresTable creates this schema on first access:

```sql
CREATE TABLE IF NOT EXISTS {table_name} (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Indexes are created via JSONB field extraction:

```sql
-- Secondary index (1:N)
CREATE INDEX idx_{table}_{field} ON {table} ((value->>'{field}'));

-- Unique index (1:1)
CREATE UNIQUE INDEX uidx_{table}_{field} ON {table} ((value->>'{field}'));
```

---

## Testing

Run tests:

```bash
cd backend && poetry run pytest src/trading_api/datastores/inmemory/tests/ -v
```

## Related Documentation

- [datastore_interface.py](../shared/datastore_interface.py) - Abstract interface definition
- [datastore_registry.py](../shared/datastore_registry.py) - Registry for auto-discovery
- [MODULAR_BACKEND_ARCHITECTURE.md](../../docs/MODULAR_BACKEND_ARCHITECTURE.md) - Service datastore injection
