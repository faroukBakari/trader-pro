# PostgreSQL Datastore

**Status**: ✅ Production Ready  
**Last Updated**: January 2026

## Overview

PostgreSQL datastore implementation using **psycopg3** with dual-mode storage:

- **PostgresTable**: JSONB storage for flexible schemas (Wave 2A)
- **SQLModelTable**: Typed column storage for SQLModel entities (Wave 2B)

## Directory Structure

```
postgres/
├── __init__.py           # Exports PostgresDatastore, PostgresTable, SQLModelTable
├── datastore.py          # Main datastore + JSONB table implementation
├── engine.py             # AsyncEngineFactory singleton (SQLAlchemy)
├── sql_safe.py           # SQL injection protection utilities
├── sqlmodel_table.py     # SQLModelTable implementation
├── README.md             # This file
└── tests/
    └── test_postgres_datastore.py
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

## Configuration

Environment variables for PostgreSQL connection (`.env` is the SSOT):

```bash
# Option 1: Full DSN (takes precedence)
DATASTORE_POSTGRES_DSN=postgresql://user:pass@localhost:5433/dbname

# Option 2: Individual components
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

Access via settings:

```python
from trading_api.shared.config import settings

dsn = settings.postgres_dsn  # Built from components or DATASTORE_POSTGRES_DSN
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
