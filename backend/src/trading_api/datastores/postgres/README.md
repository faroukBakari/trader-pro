# PostgreSQL Datastore

**Status**: ✅ Production Ready  
**Last Updated**: January 2026

## Overview

PostgreSQL datastore implementation using **psycopg3** with typed column storage:

- **SQLModelTable**: Typed column storage for SQLModel entities
- **Native Range Types**: `int8range`, `tstzrange`, `daterange` via TypeDecorators (Wave 2C)
- **Exclusion Constraints**: Declarative non-overlapping range constraints via `exclusion_listener.py` (Wave 2C)

## Directory Structure

```
postgres/
├── __init__.py           # Exports PostgresDatastore, SQLModelTable
├── datastore.py          # Main datastore + table() API
├── engine.py             # AsyncEngineFactory singleton (SQLAlchemy)
├── exclusion_listener.py # SQLAlchemy event listener for EXCLUDE USING GIST
├── sql_safe.py           # SQL injection protection utilities
├── sqlmodel_table.py     # SQLModelTable implementation
├── README.md             # This file
├── adapters/             # Reserved for future psycopg3 type adapters
│   └── __init__.py       # Empty (Range types use SQLAlchemy TypeDecorators)
└── tests/
    └── test_postgres_specific.py
```

## Model Requirements

All models must:

- Use `SQLModel` with `table=True`
- Define a primary key via `Field(primary_key=True)`

```python
from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(primary_key=True)  # Required!
    email: str = Field(unique=True)
    name: str
```

## SQL Injection Protection

All dynamic SQL uses psycopg3's safe composition utilities via `sql_safe.py`.

### Defense-in-Depth Validation

```python
from .sql_safe import validate_identifier

# Validates identifier format before use
validate_identifier(table_name, "table name")  # Raises ValueError if invalid

# Pattern: ^[a-zA-Z_][a-zA-Z0-9_]*$
# Max length: 63 characters (PostgreSQL limit)
```

### Safe SQL Composition

```python
from psycopg import sql
from .sql_safe import validate_identifier

# ✅ SAFE: Uses sql.Identifier for table/column names
query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))

# ✅ SAFE: Uses sql.Literal for JSONB field access
query = sql.SQL("SELECT value FROM {} WHERE value->>{} = %s").format(
    sql.Identifier(table_name),
    sql.Literal(field_name),
)

# ❌ UNSAFE: Never use f-strings or string concatenation
# query = f"SELECT * FROM {table_name}"  # SQL INJECTION RISK!
```

### Composition Patterns

| Component          | Purpose                     | Example                               |
| ------------------ | --------------------------- | ------------------------------------- |
| `sql.SQL()`        | Static SQL template         | `sql.SQL("SELECT * FROM {}")`         |
| `sql.Identifier()` | Table/column names (quoted) | `sql.Identifier("users")` → `"users"` |
| `sql.Literal()`    | Literal values in SQL       | `sql.Literal("email")` → `'email'`    |
| `%s` placeholder   | Query parameters (values)   | `cursor.execute(query, (value,))`     |

### When to Use Each

- **`sql.Identifier`**: Table names, column names, index names
- **`sql.Literal`**: JSONB field paths (`value->>'field'`), enum values in SQL
- **`%s` parameters**: User-provided values, search terms, IDs

## Range Types

Native PostgreSQL range type support via psycopg3 adapters and SQLAlchemy TypeDecorators.

### Supported Mappings

| Application Type | PostgreSQL Type | TypeDecorator   |
| ---------------- | --------------- | --------------- |
| `IntRange`       | `int8range`     | `Int8RangeType` |
| `TimeRange`      | `int8range`     | `Int8RangeType` |
| `DateTimeRange`  | `tstzrange`     | `TstzRangeType` |
| `DateOnlyRange`  | `daterange`     | `DateRangeType` |

### How It Works

**1. TypeDecorator (SQLAlchemy DDL + Query Compilation)**

TypeDecorators in `types/range.py` handle:

- DDL generation: `CREATE TABLE ... (column int8range)`
- Query compilation: Type coercion in WHERE clauses
- Value conversion via `process_bind_param()` / `process_result_value()`

```python
from trading_api.types import Int8RangeType, TimeRange
from sqlmodel import Field, SQLModel

class PendingRange(SQLModel, table=True):
    time_range: TimeRange = Field(sa_type=Int8RangeType)
```

**2. Canonical Form Handling**

PostgreSQL canonicalizes discrete ranges (int, date) to `[)` bounds:

- `[1, 10]` → `[1, 11)` (stored internally)
- Adapters handle this: `Range(start=1, end=10)` round-trips correctly

### GiST Index Markers

TypeDecorators with `requires_gist_index = True` attribute trigger automatic GiST index creation:

```python
class Int8RangeType(TypeDecorator[Range[int]]):
    impl = INT8RANGE
    cache_ok = True
    requires_gist_index: ClassVar[bool] = True  # ← Marker
```

`SQLModelTable._detect_range_columns()` scans for this marker and `_create_gist_index()` creates indexes during table initialization.

## Exclusion Constraints

PostgreSQL exclusion constraints (`EXCLUDE USING GIST`) prevent overlapping ranges at the database level.

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

### exclusion_listener.py

The listener is registered before `SQLModel.metadata.create_all()` in `PostgresDatastore.create()`:

1. **Event Registration**: `register_exclusion_listener()` hooks into `after_create` event
2. **Extension Creation**: Auto-creates `btree_gist` extension (required for text + range GiST index)
3. **Constraint Creation**: For each table with exclusion metadata:
   ```sql
   ALTER TABLE pending_ranges
   ADD CONSTRAINT pending_ranges_no_overlap
   EXCLUDE USING GIST (
       ("lookup_key") WITH =,
       "time_range" WITH &&
   )
   ```
4. **Idempotent**: Checks `pg_constraint` catalog before creating

### Exclusion Config Keys

| Key           | Required | Default        | Description                          |
| ------------- | -------- | -------------- | ------------------------------------ |
| `range_field` | Yes      | —              | Column containing the range type     |
| `group`       | No       | `"lookup_key"` | Column for grouping (equality check) |

### Constraint Semantics

- **Within same group**: Ranges cannot overlap (`&&` operator returns true)
- **Across groups**: No constraint (different `lookup_key` values are independent)
- **Violation**: PostgreSQL raises `ExclusionViolation` on conflicting INSERT/UPDATE

### Usage in Services

```python
# Attempting to insert overlapping range raises psycopg3 exception
from psycopg.errors import ExclusionViolation

try:
    await pending_table.set("id2", PendingRange(
        lookup_key="AAPL_1D",
        time_range=TimeRange(start=100, end=200),  # Overlaps existing!
    ))
except ExclusionViolation:
    logger.warning("Range overlap detected - request already pending")
```

## Session Scope Pattern (SQLModelTable)

`SQLModelTable` implements an internal `_session_scope()` context manager for ownership-based transaction control.

### Ownership Semantics

| Session Provided? | Behavior                 | Who Commits?                             |
| ----------------- | ------------------------ | ---------------------------------------- |
| `None` (default)  | Creates internal session | `_session_scope` auto-commits on success |
| External session  | Uses provided session    | Caller must commit                       |

### Internal Implementation

```python
@asynccontextmanager
async def _session_scope(self, session: AsyncSession | None = None):
    """Context manager with ownership-based commit."""
    if session is not None:
        # Caller owns transaction - yield without commit
        yield session
    else:
        # We own transaction - commit on success
        async with self._session_factory() as owned_session:
            yield owned_session
            await owned_session.commit()
```

### Single Operation (Auto-Commit)

```python
# Each call creates its own session and commits
await table.set("key1", model1)  # Committed immediately
await table.set("key2", model2)  # Committed immediately
```

### Multi-Operation Transaction

```python
# Batch operations atomically
async with datastore.session_factory() as session:
    await table1.set("key1", model1, session=session)
    await table2.delete("key2", session=session)
    await table3.set("key3", model3, session=session)
    await session.commit()  # All three operations committed atomically
```

### Read Your Writes

Within the same session, uncommitted writes are visible to subsequent reads:

```python
async with datastore.session_factory() as session:
    await table.set("new_key", model, session=session)

    # Same session can read uncommitted data
    result = await table.get("new_key", session=session)  # Returns model
    exists = await table.exists("new_key", session=session)  # True

    # Different session (or no session) cannot see it yet
    external_result = await table.get("new_key")  # None (not committed)

    await session.commit()
```

### Rollback on Exception

Exceptions trigger automatic rollback:

```python
try:
    async with datastore.session_factory() as session:
        await table.set("will_rollback", model, session=session)
        raise ValueError("Simulated error")
except ValueError:
    pass

# "will_rollback" was never persisted
result = await table.get("will_rollback")  # None
```

## Configuration

PostgreSQL configuration follows the **SSOT (Single Source of Truth)** pattern—all variables are defined in `.env` and consumed by both Python (`pydantic-settings`) and Docker Compose.

> **📖 Full Guide**: See [BACKEND_CONFIG.md](../../../docs/BACKEND_CONFIG.md) for complete configuration management philosophy, patterns, and guidelines.

### Environment Variables

```bash
# Option 1: Full DSN (takes precedence)
DATASTORE_POSTGRES_DSN=postgresql://user:pass@localhost:5433/dbname

# Option 2: Individual components (recommended for docker-compose compatibility)
DATASTORE_POSTGRES_USER=trader
DATASTORE_POSTGRES_PASSWORD=trader_dev
DATASTORE_POSTGRES_HOST=localhost
DATASTORE_POSTGRES_PORT=5433
DATASTORE_POSTGRES_DB=trader_pro

# Pool configuration
DATASTORE_POSTGRES_POOL_MAX_SIZE=10
DATASTORE_POSTGRES_POOL_RECONNECT_TIMEOUT=5.0  # Per-attempt timeout (seconds)
DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT=30.0      # Total startup timeout (seconds)
```

### Access via Settings

```python
# ✅ CORRECT: Always use settings singleton
from trading_api.shared.config import settings

dsn = settings.postgres_dsn  # Built from components or DATASTORE_POSTGRES_DSN
timeout = settings.DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT

# ❌ PROHIBITED: Never use os.environ directly
# host = os.environ.get("DATASTORE_POSTGRES_HOST")  # Don't do this!
```

## Startup Behavior (Fail-Fast)

The datastore implements **fail-fast startup** following 12-Factor App principles:

1. **Pre-flight database check**: Before opening the connection pool, `check_database_exists()` verifies the target database exists
2. **Bounded timeout**: Pool opening is wrapped with `asyncio.wait_for()` using `POOL_OPEN_TIMEOUT` (default: 30s)
3. **Clear error messages**: Custom exceptions provide actionable remediation steps

```python
from trading_api.datastores.postgres import (
    check_database_exists,
    DatabaseNotFoundError,
    ConnectionTimeoutError,
)

# Manual pre-flight check (optional - datastore does this automatically)
check_database_exists(dsn)  # Raises DatabaseNotFoundError if DB missing
```

### Why Fail-Fast?

- **Prevents infinite hangs**: psycopg3's pool retries indefinitely without a total timeout cap
- **Clear diagnostics**: Developers see actionable error messages instead of mysterious hangs
- **Signal responsive**: Bounded timeout allows Ctrl+C to work during startup

## Error Handling

### DatabaseNotFoundError

Raised when the configured database doesn't exist on the PostgreSQL server:

```
DATASTORE_DATABASE_NOT_FOUND: Database 'trader_pro' does not exist on localhost:5433.

To fix this, either:
  1. Recreate the Docker volume (loses data):
     make db-down && docker volume rm backend_postgres_data && make db-up

  2. Create the database manually (preserves existing data):
     docker-compose -f docker-compose.dev.yml exec postgres \
       psql -U trader -d postgres -c 'CREATE DATABASE trader_pro;'
```

**Common cause**: Database was renamed in config but the Docker volume still has the old database.

### ConnectionTimeoutError

Raised when the database server is unreachable within the timeout period:

```
DATASTORE_CONNECTION_TIMEOUT: Could not connect to PostgreSQL at localhost:5433 within 30.0s.

Possible causes:
  1. Database server is not running:
     make db-up

  2. Wrong host/port configuration:
     Check DATASTORE_POSTGRES_HOST and DATASTORE_POSTGRES_PORT in .env
```

**Common cause**: Docker container not running (`make db-up` to start).

## Testing

```bash
# Run PostgreSQL datastore tests (requires running database)
cd backend && poetry run pytest src/trading_api/datastores/postgres/tests/ -v

# Start test database
make db-up

# Run with coverage
poetry run pytest src/trading_api/datastores/postgres/tests/ --cov=trading_api.datastores.postgres
```

## Related Documentation

- [datastores/README.md](../README.md) - Parent datastore documentation
- [datastore_interface.py](../../shared/datastore_interface.py) - Abstract interface
- [MODULAR_BACKEND_ARCHITECTURE.md](../../../docs/MODULAR_BACKEND_ARCHITECTURE.md) - Service integration
