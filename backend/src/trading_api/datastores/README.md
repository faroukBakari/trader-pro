# Datastores

**Status**: ✅ Production Ready  
**Last Updated**: January 2026

## Overview

The datastore layer provides a minimal abstraction for data persistence that enables:

- Testability via dependency injection
- PostgreSQL support via `PostgresDatastore` (Wave 2A + 2B)
- Per-table read-write locks for concurrent access
- Auto-discovery via `DatastoreRegistry`
- Feature detection via `has_persistence` and `has_transactions` properties
- **SQLModel + Alembic migrations** for typed column storage (Wave 2B)

## Directory Structure

```
datastores/
├── __init__.py           # Re-exports for backward compatibility
├── README.md             # This file
├── inmemory/             # InMemoryDatastore implementation
│   ├── __init__.py       # Exports InMemoryDatastore, InMemoryTable
│   └── tests/
└── postgres/             # PostgresDatastore implementation
    ├── __init__.py       # Exports PostgresDatastore, PostgresTable, SQLModelTable
    ├── datastore.py      # Dual-mode: JSONB tables + SQLModel tables
    ├── engine.py         # AsyncEngineFactory singleton (SQLAlchemy)
    └── sqlmodel_table.py # SQLModelTable implementation
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
    enabled_datastores=["inmemory"],  # NEW: filter datastores
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
| `is_empty` (property)             | Read  | `bool`                        | Returns True if table has zero entries        |

#### DatastoreInterface Methods

| Method                            | Description                                                            |
| --------------------------------- | ---------------------------------------------------------------------- |
| `table(model_class, primary_key)` | Get or create table for model class (auto-extracts indexes from Field) |
| `datastore_name()` (classmethod)  | Canonical name for registry lookup (e.g., "inmemory")                  |
| `list_tables(prefix)`             | List all table names, optionally filtered by prefix                    |
| `drop_table(name)`                | Drop a table by name (returns True if dropped, False if not found)     |

### Indexing via Field() Metadata

Indexes are declared in the model class using SQLModel's `Field()` metadata:

```python
from sqlmodel import Field, SQLModel

class User(SQLModel):
    id: str = Field(primary_key=True)
    email: str = Field(unique=True)      # Unique index (1:1)
    google_id: str = Field(unique=True)  # Unique index (1:1)
    role: str = Field(index=True)        # Secondary index (1:N)

# table() auto-extracts index configuration from Field() metadata
users = datastore.table(User)
```

#### Unique Index (1:1)

Enforces uniqueness constraint - raises `ValueError` on duplicate:

````python
# Declared via Field(unique=True) in model
await table.set("1", User(id="1", email="alice@example.com"))
await table.set("2", User(id="2", email="alice@example.com"))  # Raises ValueError!

### Type-Safe Tables

Use `TableInterface[T]` for compile-time type checking:

```python
from trading_api.shared import DatastoreInterface, TableInterface
from trading_api.models.auth import User

class UserRepository:
    def __init__(self, datastore: DatastoreInterface) -> None:
        # Type-safe: users table returns User
        # Indexes auto-extracted from Field(index=True, unique=True)
        self._users: TableInterface[User] = datastore.table(User)

    async def get_user(self, user_id: str) -> User | None:
        return await self._users.get(user_id)  # Returns User | None

    async def list_users(self) -> list[User]:
        return await self._users.values()  # Returns list[User]
````

### Concurrency Model

- **Read operations**: Concurrent access allowed (multiple readers)
- **Write operations**: Exclusive access (single writer, no readers)
- **Writer priority**: Writers are prioritized to prevent starvation

---

## PostgresDatastore

PostgreSQL datastore using **psycopg3 + JSONB** storage pattern. Provides real persistence with ACID transactions.

### Startup Errors

The datastore implements **fail-fast startup** with clear error messages:

| Exception                | Code                           | Cause                             | Fix                                   |
| ------------------------ | ------------------------------ | --------------------------------- | ------------------------------------- |
| `DatabaseNotFoundError`  | `DATASTORE_DATABASE_NOT_FOUND` | Target database doesn't exist     | Create DB or reset Docker volume      |
| `ConnectionTimeoutError` | `DATASTORE_CONNECTION_TIMEOUT` | Server unreachable within timeout | Start Docker container (`make db-up`) |

```python
from trading_api.datastores.postgres import (
    PostgresDatastore,
    DatabaseNotFoundError,
    ConnectionTimeoutError,
    check_database_exists,  # Pre-flight check utility
)

try:
    datastore = await PostgresDatastore.create()
except DatabaseNotFoundError as e:
    print(f"Database missing: {e.db_name}")
except ConnectionTimeoutError as e:
    print(f"Connection timeout after {e.timeout}s")
```

See [postgres/README.md](postgres/README.md) for detailed error messages and remediation steps.

### Key Design Decisions

- **JSONB Storage**: Schema-flexible storage - each table stores `key TEXT` + `value JSONB`
- **Async Factory Pattern**: Pool creation is async, use `PostgresDatastore.create()` factory
- **No-Op RWLock**: PostgreSQL MVCC provides transaction isolation, app-level locks are redundant
- **Typed Model Returns**: `get()`, `get_all()`, `values()` return validated Pydantic model instances (same as InMemoryDatastore)
- **SQL Injection Safety**: All queries use `psycopg.sql.SQL/Identifier/Literal` for safe dynamic SQL composition

### Usage

```python
from trading_api.datastores.postgres import PostgresDatastore

# Create with async factory (reads config from settings - 12-Factor compliant)
datastore = await PostgresDatastore.create()

# For tests: inject custom config
from trading_api.shared.config import Settings
test_settings = Settings(DATASTORE_POSTGRES_DSN="postgresql://test:test@localhost:5432/test_db")
datastore = await PostgresDatastore.create(config=test_settings)

# Get table - indexes auto-extracted from Field() metadata
users = datastore.table(User)

# Store SQLModel instance
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

## SQLModelTable (Wave 2B)

**Typed column storage** using SQLModel ORM for entities requiring schema enforcement and SQL queries.

### Overview

`SQLModelTable[T]` provides an alternative to JSONB storage for entities that benefit from:

- **Typed columns**: Direct PostgreSQL column types (TEXT, TIMESTAMPTZ, BOOLEAN)
- **Native SQL indexes**: Standard B-tree indexes on columns
- **Schema validation**: Database-level NOT NULL constraints
- **Query flexibility**: Full SQL capabilities via SQLAlchemy

### Usage

```python
from trading_api.models.auth import User
from trading_api.datastores.postgres import PostgresDatastore

# Create datastore (initializes both psycopg3 pool and SQLAlchemy engine)
datastore = await PostgresDatastore.create()

# Get table - auto-detects storage mode from model class
# table=True models use typed columns, table=False uses JSONB
users = datastore.table(User)

# Store SQLModel instance directly
await users.set("user123", user)

# Retrieve as typed model
user = await users.get("user123")  # Returns User | None
```

### Architecture

```
PostgresDatastore
├── _pool (psycopg3)                # JSONB tables via PostgresTable
├── _session_factory (SQLAlchemy)   # SQLModel tables via AsyncSessionFactory
└── _typed_tables: dict[str, SQLModelTable[T]]
        │
        └── SQLModelTable[T]
            ├── _model_class: type[SQLModel]  # User, RefreshTokenData, etc.
            ├── _pk_field: str                # Primary key column name
            └── Uses INSERT...ON CONFLICT for upserts
```

### SQLModel Entity Definition

Entities must inherit from `SQLModel` with `table=True`:

```python
from sqlmodel import Field, SQLModel
from datetime import datetime

class User(SQLModel, table=True):
    """User model - unified API and database representation."""
    __tablename__ = "users"

    id: str = Field(primary_key=True)
    email: str = Field(index=True)
    google_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
```

### Table Schema

SQLModel creates typed columns automatically:

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    google_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_google_id ON users (google_id);
```

### Alembic Migrations

Schema changes are managed via Alembic migrations in `backend/alembic/`:

```bash
# Check current migration state
make alembic-current

# Apply pending migrations
make alembic-upgrade

# Roll back one migration
make alembic-downgrade

# Create new migration (autogenerate from model changes)
make alembic-revision msg="add user preferences"

# Reset database (destroys data!)
make db-reset
```

Migration files are in `backend/alembic/versions/`. See `001_migrate_jsonb_to_typed.py` for the initial JSONB → typed column migration example.

### Dual-Mode Datastore

`PostgresDatastore.table()` auto-detects storage mode based on the model class:

```python
from trading_api.models.auth import User  # has table=True
from trading_api.models.orders import Order  # has table=False

# SQLModel table=True → typed column storage (SQLModelTable)
users = datastore.table(User)

# SQLModel table=False or Pydantic → JSONB storage (PostgresTable)
# Indexes extracted from Field(index=True, unique=True)
orders = datastore.table(Order)
```

This enables gradual migration from JSONB to typed columns per entity.

---

## Testing

### Test Architecture

The datastore tests follow a three-tier structure:

1. **Contract Tests** (`tests/integration/test_datastore_contract.py`):
   - Parametrized tests that run against ALL datastore implementations
   - Validates `TableInterface` and `DatastoreInterface` contracts
   - Uses `drop_table()` and `list_tables()` for test isolation
   - Source of truth for expected behavior

2. **Implementation-Specific Tests** (`datastores/{impl}/tests/test_{impl}_specific.py`):
   - Tests unique features of each implementation
   - InMemory: RWLock behavior, BaseModel return type, deep copy
   - Postgres: psycopg exceptions, connection pool, model validation

3. **Integration Tests** (`tests/integration/test_datastore_integration.py`):
   - End-to-end tests with repositories and services

### Test Settings

Tests use a session-scoped `test_settings` fixture that:

- Configures minimal pool sizes for efficiency
- Ensures CI pipelines are config-agnostic

```python
@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        DATASTORE_POSTGRES_POOL_MAX_SIZE=2,
        # ... other test-specific config
    )
```

### Test Isolation with `drop_table()`

Use `list_tables()` and `drop_table()` to clean up dynamically-created tables between tests:

```python
# Test fixture pattern for bar tables
@pytest.fixture
async def clean_bar_tables(datastore: DatastoreInterface) -> AsyncIterator[None]:
    yield
    # Cleanup: drop all bar tables created during test
    for table_name in await datastore.list_tables(prefix="bars_"):
        await datastore.drop_table(table_name)
```

### Running Tests

```bash
# All contract tests (InMemory + Postgres)
cd backend && poetry run pytest tests/integration/test_datastore_contract.py -v

# InMemory-specific tests
cd backend && poetry run pytest src/trading_api/datastores/inmemory/tests/ -v

# PostgreSQL-specific tests (uses testcontainers)
cd backend && poetry run pytest src/trading_api/datastores/postgres/tests/ -v

# Full datastore test suite
cd backend && poetry run pytest src/trading_api/datastores/ tests/integration/test_datastore*.py -v
```

## Related Documentation

- [datastore_interface.py](../shared/datastore_interface.py) - Abstract interface definition
- [datastore_registry.py](../shared/datastore_registry.py) - Registry for auto-discovery
- [MODULAR_BACKEND_ARCHITECTURE.md](../../docs/MODULAR_BACKEND_ARCHITECTURE.md) - Service datastore injection
