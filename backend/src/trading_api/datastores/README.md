# Datastores

**Status**: ✅ Production Ready
**Last Updated**: February 2026

## Overview

The datastore layer provides a minimal abstraction for data persistence that enables:

- Testability via dependency injection
- PostgreSQL support via `PostgresDatastore` with typed SQLModel columns
- Per-table read-write locks for concurrent access
- Auto-discovery via `DatastoreRegistry`
- Feature detection via `has_persistence` and `has_transactions` properties
- **SQLModel + Alembic migrations** for schema management

## Directory Structure

```
datastores/
├── __init__.py           # Re-exports for backward compatibility
├── README.md             # This file
├── _utils.py             # Shared utilities (extract_indexes)
├── duckdb/               # DuckDBDatastore implementation
│   ├── __init__.py       # Exports DuckDBDatastore, DuckDBTable
│   └── tests/
└── postgres/             # PostgresDatastore implementation
    ├── __init__.py       # Exports PostgresDatastore, SQLModelTable
    ├── datastore.py      # SQLModel tables via SQLModelTable
    ├── engine.py         # AsyncEngineFactory singleton (SQLAlchemy)
    └── sqlmodel_table.py # SQLModelTable implementation
```

## Feature Detection

Use `has_capability(name)` to detect datastore capabilities:

```python
datastore = registry.get_datastores(names=["postgres"])[0]

# Check if data survives restarts
if datastore.has_capability("persistence"):
    logger.info("Using persistent datastore")

# Check if ACID transactions are supported
if datastore.has_capability("transactions"):
    logger.info("Transactions available")
```

| Capability Name   | DuckDB | Postgres |
| ----------------- | ------ | -------- |
| `"persistence"`   | ❌     | ✅       |
| `"transactions"` | ❌     | ✅       |
| `"exclusion"`     | ❌     | ✅       |
| `"timeseries"`    | ✅     | ✅       |
| `"rangequery"`    | ❌     | ✅       |

**`"exclusion"`**: Database-level exclusion constraints (e.g., PostgreSQL `EXCLUDE USING GIST`) that atomically prevent overlapping ranges. Used for cache metadata tables like `PendingRange` and `CoveredRange`.

**`"transactions"`**: ACID transactions via session injection pattern. Enables atomic multi-table operations.

**`"timeseries"`**: Time-series operations via `TimeSeriesTableInterface`. When available, `timeseries_table()` returns a table with `get_time_range()` and `set_batch()` methods for efficient time-indexed queries. Otherwise, use standard `TableInterface` with manual filtering.

**`"rangequery"`**: Range query operations via `RangeQueryTableInterface`. When available, `rangequery_table()` returns a table with `get_missing_ranges()` for accurate gap detection using PostgreSQL multirange subtraction. Otherwise, fall back to boundary-based algorithms (which may miss internal gaps).

---

## Capability-Based Datastore Selection

Services declare their required datastore capabilities via `datastore_capabilities()`, and the system automatically selects a compatible datastore. This mirrors the provider capability pattern.

### Service Declaration

```python
# modules/datafeed/service.py
from trading_api.models.common import DatastoreCapabilitySpec

class DatafeedService(ServiceInterface):
    @classmethod
    def datastore_capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """Declare required datastore capabilities.

        Returns:
            timeseries (optional): Enhanced time-range queries if available
        """
        return [DatastoreCapabilitySpec(name="timeseries", optional=True)]
```

### Capability Matching

The `DatastoreCapabilitySpec` model supports:

| Field      | Type   | Description                                         |
| ---------- | ------ | --------------------------------------------------- |
| `name`     | `str`  | Capability name (e.g., "persistence", "timeseries") |
| `optional` | `bool` | If `True`, capability is preferred but not required |

**Matching behavior**:

- Required capabilities (`optional=False`) must be provided by the datastore
- Optional capabilities (`optional=True`) are used if available, but fallback is acceptable
- If no datastore matches required capabilities, service initialization fails

### PostgresDatastore Capabilities

```python
# PostgresDatastore.capabilities() returns:
[
    DatastoreCapabilitySpec(name="persistence"),
    DatastoreCapabilitySpec(name="transactions"),
    DatastoreCapabilitySpec(name="timeseries"),
    DatastoreCapabilitySpec(name="rangequery"),
    DatastoreCapabilitySpec(name="exclusion"),
]
```

### DuckDBDatastore Capabilities

```python
# DuckDBDatastore.capabilities() returns:
[DatastoreCapabilitySpec(name="timeseries")]
```

### AppFactory Integration

The `AppFactory` aggregates capabilities from all enabled modules and filters datastores accordingly:

```python
# ModuleRegistry collects required capabilities
required_caps = module_registry.required_datastore_capabilities()

# DatastoreRegistry filters by capabilities
datastores = datastore_registry.get_datastores(
    names=["postgres", "duckdb"],
    required_capabilities=required_caps,
)
```

---

## Transaction Support (Session Injection)

Datastores with the `"transactions"` capability support atomic multi-operation transactions via **session injection**.

### Session Factory Property

```python
from trading_api.datastores import PostgresDatastore

datastore = await PostgresDatastore.create()

# Get session factory for transaction support
if datastore.has_capability("transactions") and datastore.session_factory:
    async with datastore.session_factory() as session:
        # Multiple operations in one transaction
        await table1.set("key1", model1, session=session)
        await table2.delete("key2", session=session)
        await session.commit()  # Atomic commit
```

### Session Ownership Semantics

All `TableInterface` CRUD methods accept an optional `session` parameter:

| Caller Provides            | Behavior                                                 |
| -------------------------- | -------------------------------------------------------- |
| `session=None` (default)   | Method creates internal session, auto-commits on success |
| `session=external_session` | Method uses provided session, **caller owns commit**     |

**Pattern**: "Unit of Work propagation" - the outermost caller controls transaction boundaries.

```python
# Single operation - auto-commits
await table.set("key", model)  # Committed immediately

# Multi-operation transaction - caller controls commit
async with datastore.session_factory() as session:
    await table1.set("a", model_a, session=session)  # Not committed yet
    await table2.set("b", model_b, session=session)  # Not committed yet
    # Both visible within this session ("read your writes")
    result = await table1.get("a", session=session)  # Sees uncommitted data
    await session.commit()  # Atomic commit of both operations
```

### Rollback Behavior

If an exception is raised before commit, the transaction rolls back automatically:

```python
async with datastore.session_factory() as session:
    await table.set("key", model, session=session)
    raise ValueError("Oops")  # Session rolls back automatically
# "key" was never persisted
```

## DatastoreRegistry

The `DatastoreRegistry` mirrors the `ProviderRegistry` pattern with auto-discovery from the `datastores/` directory.

### Usage in AppFactory

```python
from trading_api.shared import DatastoreRegistry

# Registry auto-discovers from datastores/ subdirectories
registry = DatastoreRegistry()
registry.auto_discover()  # Finds duckdb/, postgres/, etc.

# Get all registered datastores
datastores = registry.get_datastores()  # [DuckDBDatastore()]

# Get specific datastore by name
datastores = registry.get_datastores(names=["duckdb"])
```

### AppFactory Integration

The `AppFactory.create_app()` method now uses `DatastoreRegistry`:

```python
factory = AppFactory()
app = await factory.create_app(
    enabled_module_names=["broker", "auth"],
    enabled_provider_names=["fakebroker", "google"],
    enabled_datastores=["duckdb"],  # NEW: filter datastores
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

## DuckDBDatastore

SQL-backed storage via DuckDB for prototyping and testing with:

- In-memory (`:memory:`) or file-based DuckDB backend
- Per-table threading.Lock for concurrent access
- Async CRUD via `asyncio.to_thread()` wrapping sync SQL
- Secondary indexing via SQL CREATE INDEX
- Unique constraint enforcement with pre-check pattern
- Time-series support via `DuckDBTimeSeriesTable`

### Architecture

```
DuckDBDatastore
└── _tables: dict[str, DuckDBTable]
        │
        ├── _conn: duckdb.DuckDBPyConnection    # DuckDB connection
        ├── _lock: threading.Lock               # Per-table thread safety
        ├── _model_columns: list[str]           # Model field names
        ├── _indexes: set[str]                  # Secondary index columns
        └── _unique_indexes: set[str]           # Unique constraint columns
```

### API Reference

#### TableInterface[T] Methods

`TableInterface` is generic over `T` (a Pydantic `BaseModel`), enabling type-safe returns:

| Method                                   | Lock | Return Type                   | Description                                   |
| ---------------------------------------- | ---- | ----------------------------- | --------------------------------------------- |
| `get(key, index=None, session=None)`     | Lock | `T \| None`                   | Get value by key or indexed field             |
| `get_all(key, index=None, session=None)` | Lock | `list[T]`                     | Get all values matching indexed field         |
| `set(key, value, session=None)`          | Lock | `None`                        | Store value, auto-index all registered fields |
| `delete(key, index=None, session=None)`  | Lock | `bool`                        | Delete by key or indexed field                |
| `exists(key, index=None, session=None)`  | Lock | `bool`                        | Check if key/indexed value exists             |
| `keys(index=None)`                       | Lock | `list[str]`                   | Get all keys or indexed field values          |
| `values()`                               | Lock | `list[T]`                     | Get all values (deep copies)                  |
| `clear(session=None)`                    | Lock | `None`                        | Remove all entries and indexes                |
| `count()`                                | Lock | `int`                         | Get entry count                               |
| `iterate()`                              | Lock | `AsyncIterator[tuple[str,T]]` | Async iterate over key-value pairs            |
| `is_empty` (property)                    | Lock | `bool`                        | Returns True if table has zero entries        |

> **Note**: The `session` parameter enables transaction batching (see [Transaction Support](#transaction-support-session-injection)). When `session=None`, each operation auto-commits. When provided, caller controls commit.

> **Note**: Indexes are declared via `Field(index=True, unique=True)` metadata in model classes. The deprecated `create_index()` and `create_unique_index()` methods have been removed from `TableInterface`.

#### DatastoreInterface Methods

| Method                           | Description                                                            |
| -------------------------------- | ---------------------------------------------------------------------- |
| `table(model_class)`             | Get or create table for model class (auto-extracts indexes from Field) |
| `datastore_name()` (classmethod) | Canonical name for registry lookup (e.g., "duckdb")                    |
| `list_tables(prefix)`            | List all table names, optionally filtered by prefix                    |
| `drop_table(name)`               | Drop a table by name (returns True if dropped, False if not found)     |

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

- **All operations**: Serialized via `threading.Lock` (one operation at a time)
- **Async bridging**: `asyncio.to_thread()` prevents blocking the event loop
- **Thread safety**: Supports TWS callback threads via the same threading.Lock

### Exclusion Constraint Limitations

**DuckDBDatastore does NOT support exclusion constraints.** Models that declare exclusion requirements via `__table_args__["info"]["exclusion"]` will raise `NotImplementedError` when passed to `table()`:

```python
from trading_api.models.market import PendingRange  # Has exclusion constraint

# DuckDBDatastore rejects models requiring exclusion constraints
duckdb_ds = DuckDBDatastore()
duckdb_ds.table(PendingRange)  # Raises NotImplementedError!

# Use PostgresDatastore for such models
postgres_ds = await PostgresDatastore.create()
postgres_ds.table(PendingRange)  # Works - creates EXCLUDE USING GIST constraint
```

**Rationale**: Exclusion constraints require database-level atomic enforcement to prevent overlapping ranges across concurrent writes. DuckDBDatastore cannot provide this guarantee.

---

## PostgresDatastore

PostgreSQL datastore using **psycopg3** with typed column storage via SQLModel. Provides real persistence with ACID transactions.

**Features**:

- Native PostgreSQL range type support (`int8range`, `tstzrange`, `daterange`) via TypeDecorators
- Declarative exclusion constraints via `__table_args__["info"]["exclusion"]` metadata
- GiST index auto-creation for range columns

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

- **Typed Column Storage**: All models use SQLModel with `table=True` for typed PostgreSQL columns
- **Async Factory Pattern**: Pool creation is async, use `PostgresDatastore.create()` factory
- **No-Op RWLock**: PostgreSQL MVCC provides transaction isolation, app-level locks are redundant
- **Typed Model Returns**: `get()`, `get_all()`, `values()` return validated Pydantic model instances (same as DuckDBDatastore)
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

---

## SQLModelTable

**Typed column storage** using SQLModel ORM for entities requiring schema enforcement and SQL queries.

### Overview

`SQLModelTable[T]` provides typed column storage for SQLModel entities with:

- **Typed columns**: Direct PostgreSQL column types (TEXT, TIMESTAMPTZ, BOOLEAN)
- **Native SQL indexes**: Standard B-tree indexes on columns
- **Schema validation**: Database-level NOT NULL constraints
- **Query flexibility**: Full SQL capabilities via SQLAlchemy

### Usage

```python
from trading_api.models.auth import User
from trading_api.datastores.postgres import PostgresDatastore

# Create datastore (initializes psycopg3 pool and SQLAlchemy engine)
datastore = await PostgresDatastore.create()

# Get table - requires SQLModel with table=True
users = datastore.table(User)

# Store SQLModel instance directly
await users.set("user123", user)

# Retrieve as typed model
user = await users.get("user123")  # Returns User | None
```

### Architecture

```
PostgresDatastore
├── _pool (psycopg3)                # Connection pool for raw SQL operations
├── _session_factory (SQLAlchemy)   # SQLModel tables via AsyncSessionFactory
└── _tables: dict[str, SQLModelTable[Any]]
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

### Range Types & GiST Indexes

SQLModelTable auto-detects range columns and creates GiST indexes for efficient overlap queries:

```python
from sqlmodel import Field, SQLModel
from trading_api.types import Int8RangeType, TimeRange

class PendingRange(SQLModel, table=True):
    __tablename__ = "pending_ranges"

    id: str = Field(primary_key=True)
    lookup_key: str = Field(index=True)
    # Range column with TypeDecorator - triggers GiST index creation
    time_range: TimeRange = Field(sa_type=Int8RangeType)
```

**Auto-Detection**: TypeDecorators with `requires_gist_index = True` marker are detected in `_detect_range_columns()`. GiST indexes are created during `_ensure_table()`.

**Available Range TypeDecorators** (from `trading_api.types`):

| TypeDecorator   | PostgreSQL Type | Application Type        |
| --------------- | --------------- | ----------------------- |
| `Int8RangeType` | `int8range`     | `IntRange`, `TimeRange` |
| `TstzRangeType` | `tstzrange`     | `DateTimeRange`         |
| `DateRangeType` | `daterange`     | `DateOnlyRange`         |

---

## Exclusion Constraints

PostgreSQL exclusion constraints prevent overlapping ranges atomically at the database level. SQLModelTable supports declarative exclusion via model metadata.

### Declarative Pattern

Models declare exclusion requirements via `__table_args__["info"]["exclusion"]`:

```python
from typing import Any, cast
from sqlmodel import Field, SQLModel
from trading_api.types import Int8RangeType, TimeRange

class PendingRange(SQLModel, table=True):
    __tablename__ = cast(Any, "pending_ranges")
    __table_args__ = {
        "info": {"exclusion": {"range_field": "time_range", "group": "lookup_key"}}
    }

    id: str = Field(primary_key=True)
    lookup_key: str = Field(index=True)  # Grouping column
    time_range: TimeRange = Field(sa_type=Int8RangeType)  # Range column
```

### How It Works

1. **Listener Registration**: `PostgresDatastore.create()` registers `exclusion_listener` before `SQLModel.metadata.create_all()`
2. **Constraint Creation**: After table creation, listener reads `__table_args__["info"]["exclusion"]` and creates:
   ```sql
   ALTER TABLE pending_ranges
   ADD CONSTRAINT pending_ranges_no_overlap
   EXCLUDE USING GIST (lookup_key WITH =, time_range WITH &&)
   ```
3. **Extension**: `btree_gist` extension is auto-created (required for text column in GiST index)
4. **Idempotent**: Checks `pg_constraint` before creating to avoid duplicates

### Exclusion Config Keys

| Key           | Required | Description                                   |
| ------------- | -------- | --------------------------------------------- |
| `range_field` | Yes      | Column name containing the range type         |
| `group`       | No       | Column for grouping (default: `"lookup_key"`) |

### Constraint Behavior

- **Within same group**: Ranges cannot overlap (`&&` operator)
- **Across groups**: No constraint (different `lookup_key` values can have overlapping ranges)
- **Violation**: PostgreSQL raises exclusion violation error on conflicting INSERT/UPDATE

---

## Interface Segregation

The datastore layer uses **Interface Segregation Pattern (ISP)** to decouple specialized operations from the base interface.

### TimeSeriesTableInterface

For time-indexed data (bars, trades, etc.), use `TimeSeriesTableInterface[T]` which extends `TableInterface[T]`:

| Method                                        | Description                                      |
| --------------------------------------------- | ------------------------------------------------ |
| `get_time_range(from_time, to_time, session)` | Efficient B-tree range scan on time column       |
| `set_batch(values, session) -> int`           | Bulk INSERT...ON CONFLICT, returns new row count |

### Factory Method

Use `datastore.timeseries_table(model_class)` to get a `TimeSeriesTableInterface`:

```python
from trading_api.shared import TimeSeriesTableInterface

# PostgresDatastore supports timeseries tables
ts_table: TimeSeriesTableInterface[Bar] = datastore.timeseries_table(BarModel)

# Efficient time-range query
bars = await ts_table.get_time_range(from_time=1704067200000, to_time=1704153600000)

# Bulk insert with conflict handling
new_count = await ts_table.set_batch(bars)
```

### Usage in Repository Pattern

```python
from trading_api.shared import DatastoreInterface, TimeSeriesTableInterface

class BarRepository:
    def __init__(self, datastore: DatastoreInterface) -> None:
        self._datastore = datastore
        self._ts_cache: dict[str, TimeSeriesTableInterface[Bar]] = {}

    def _get_timeseries_table(self, symbol: str) -> TimeSeriesTableInterface[Bar]:
        """Get timeseries table for efficient time-range queries."""
        if symbol not in self._ts_cache:
            self._ts_cache[symbol] = self._datastore.timeseries_table(self._model_cache[symbol])
        return self._ts_cache[symbol]

    async def store_bars(self, symbol: str, bars: list[Bar]) -> int:
        # Capability check: use has_timeseries for early routing
        if self._datastore.has_timeseries:
            ts_table = self._get_timeseries_table(symbol)
            return await ts_table.set_batch(bars)

        # Fallback for datastores without timeseries support
        table = self._datastore.table(self._model_cache[symbol])
        for bar in bars:
            await table.set(str(bar.time), bar)
        return len(bars)
```

**Pattern**: Use `has_timeseries` property for capability detection instead of try/except around `timeseries_table()`. This provides clearer intent and avoids exception overhead.

### RangeQueryTableInterface

For metadata with range columns (cache coverage tracking, etc.), use `RangeQueryTableInterface[T]` which extends `TableInterface[T]`:

| Method                                                 | Description                                              |
| ------------------------------------------------------ | -------------------------------------------------------- |
| `get_missing_ranges(lookup_key, query_range, session)` | PostgreSQL multirange subtraction to find uncovered gaps |

### Factory Method

Use `datastore.rangequery_table(model_class)` to get a `RangeQueryTableInterface`:

```python
from trading_api.shared import RangeQueryTableInterface
from trading_api.datastores.postgres.types import IntRange

# PostgresDatastore supports range query tables
rq_table: RangeQueryTableInterface[CoveredRange] = datastore.rangequery_table(CoveredRange)

# Find gaps using PostgreSQL multirange operations
# Example: existing coverage [100-200], [300-400], query [50-500]
# Returns: [50-100), [200-300), [400-500)
gaps = await rq_table.get_missing_ranges(lookup_key="key", query_range=IntRange(50, 500))
```

### Algorithm

The `get_missing_ranges()` method uses PostgreSQL's native multirange operations:

```sql
-- Conceptual SQL (actual uses SQLAlchemy expression API)
SELECT (int8multirange(int8range(50, 500, '[]')) - range_agg(range_col))::int8range[]
FROM covered_ranges
WHERE lookup_key = 'key'
```

This performs:

1. Aggregate all matching ranges into a single multirange via `range_agg()`
2. Wrap query range in `int8multirange()` for compatible subtraction
3. Subtract aggregated coverage from query multirange
4. Cast result to array for row-by-row iteration

### Usage in BarCacheManager

```python
if self._datastore.has_rangequery:
    # Delegate to PostgreSQL multirange subtraction
    rq_table = self._datastore.rangequery_table(CoveredRange)
    gaps = await rq_table.get_missing_ranges(lookup_key=key, query_range=query_range)
    return [TimeRange(start=gap.start, end=gap.end) for gap in gaps]

# Fallback for datastores without rangequery support
return await self.__find_missing_ranges_fallback(...)
```

**Pattern**: Use `has_rangequery` property for capability detection. This enables PostgreSQL's efficient set operations while maintaining fallback compatibility for datastores without range query support.

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
   - DuckDB: threading.Lock serialization, SQL semantics, timeseries batch ops
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
# All contract tests (DuckDB + Postgres)
cd backend && poetry run pytest tests/integration/test_datastore_contract.py -v

# DuckDB-specific tests
cd backend && poetry run pytest src/trading_api/datastores/duckdb/tests/ -v

# PostgreSQL-specific tests (uses testcontainers)
cd backend && poetry run pytest src/trading_api/datastores/postgres/tests/ -v

# Full datastore test suite
cd backend && poetry run pytest src/trading_api/datastores/ tests/integration/test_datastore*.py -v
```

## Related Documentation

- [datastore_interface.py](../shared/datastore_interface.py) - Abstract interface definition
- [datastore_registry.py](../shared/datastore_registry.py) - Registry for auto-discovery
- [MODULAR_BACKEND_ARCHITECTURE.md](../../docs/MODULAR_BACKEND_ARCHITECTURE.md) - Service datastore injection
