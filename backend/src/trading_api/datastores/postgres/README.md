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

| Component | Purpose | Example |
|-----------|---------|---------|
| `sql.SQL()` | Static SQL template | `sql.SQL("SELECT * FROM {}")` |
| `sql.Identifier()` | Table/column names (quoted) | `sql.Identifier("users")` → `"users"` |
| `sql.Literal()` | Literal values in SQL | `sql.Literal("email")` → `'email'` |
| `%s` placeholder | Query parameters (values) | `cursor.execute(query, (value,))` |

### When to Use Each

- **`sql.Identifier`**: Table names, column names, index names
- **`sql.Literal`**: JSONB field paths (`value->>'field'`), enum values in SQL
- **`%s` parameters**: User-provided values, search terms, IDs

## Configuration

Environment variables for PostgreSQL connection:

```bash
# Option 1: Full DSN (takes precedence)
DATASTORE_POSTGRES_DSN=postgresql://user:pass@localhost:5433/dbname

# Option 2: Individual components
DATASTORE_POSTGRES_USER=trader
DATASTORE_POSTGRES_PASSWORD=trader_dev
DATASTORE_POSTGRES_HOST=localhost
DATASTORE_POSTGRES_PORT=5433
DATASTORE_POSTGRES_DB=trader_bars

# Pool configuration
DATASTORE_POSTGRES_POOL_MAX_SIZE=10
DATASTORE_POSTGRES_POOL_RECONNECT_TIMEOUT=5.0
```

Access via settings:

```python
from trading_api.shared.config import settings

dsn = settings.postgres_dsn  # Built from components or DATASTORE_POSTGRES_DSN
```

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
