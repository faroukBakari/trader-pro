# InMemoryDatastore

**Status**: ✅ Production Ready  
**Last Updated**: January 27, 2026

## Overview

The `InMemoryDatastore` provides dict-based storage for MVP and testing with:

- Per-table read-write locks for concurrent access
- Async CRUD operations with Pydantic model validation
- Secondary indexing (1:N field → keys mapping)
- Unique indexing (1:1 field → key mapping with constraint enforcement)
- Auto-indexing on `set()` for all registered indexes

## Architecture

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

## API Reference

### TableInterface Methods

| Method                            | Lock  | Description                                   |
| --------------------------------- | ----- | --------------------------------------------- |
| `get(key, index=None)`            | Read  | Get value by key or indexed field             |
| `get_all(key, index=None)`        | Read  | Get all values matching indexed field         |
| `set(key, value)`                 | Write | Store value, auto-index all registered fields |
| `delete(key, index=None)`         | Write | Delete by key or indexed field                |
| `exists(key, index=None)`         | Read  | Check if key/indexed value exists             |
| `keys(index=None)`                | Read  | Get all keys or indexed field values          |
| `values()`                        | Read  | Get all values (deep copies)                  |
| `clear()`                         | Write | Remove all entries and indexes                |
| `count()`                         | Read  | Get entry count                               |
| `iterate()`                       | Read  | Async iterate over key-value pairs            |
| `create_index(field_name)`        | Write | Create secondary index (1:N)                  |
| `create_unique_index(field_name)` | Write | Create unique index (1:1)                     |

### DatastoreInterface Methods

| Method        | Description                               |
| ------------- | ----------------------------------------- |
| `table(name)` | Get or create a named table (thread-safe) |

## Indexing

### Secondary Index (1:N)

Multiple records can share the same field value:

```python
table = datastore.table("users")
await table.create_index("category")

await table.set("1", User(id="1", name="Alice", category="admin"))
await table.set("2", User(id="2", name="Bob", category="admin"))

# Get all admins
admins = await table.get_all("admin", index="category")  # Returns [Alice, Bob]
```

### Unique Index (1:1)

Enforces uniqueness constraint - raises `ValueError` on duplicate:

```python
await table.create_unique_index("email")

await table.set("1", User(id="1", email="alice@example.com"))
await table.set("2", User(id="2", email="alice@example.com"))  # Raises ValueError!
```

### Auto-Indexing

When `set()` is called, all registered indexes are automatically updated:

```python
await table.create_index("category")
await table.create_unique_index("email")

# Both indexes updated automatically
await table.set("1", User(id="1", category="admin", email="alice@example.com"))
```

## Concurrency Model

### RWLock Pattern

- **Read operations**: Concurrent access allowed (multiple readers)
- **Write operations**: Exclusive access (single writer, no readers)
- **Writer priority**: Writers are prioritized to prevent starvation

### Threading Lock

Additional `threading.Lock` for cross-thread synchronization with TWS connection callbacks:

```python
async with self.__lock.write(self.timeout):
    with self.__threading_lock:
        # Safe for both async and sync callback contexts
        self.__data[key] = value
```

## Usage Example

```python
from trading_api.datastores import InMemoryDatastore
from pydantic import BaseModel

class User(BaseModel):
    id: str
    name: str
    email: str
    role: str = "user"

# Create datastore with 1-second lock timeout
datastore = InMemoryDatastore(timeout=1.0)
users = datastore.table("users")

# Create indexes before inserting data
await users.create_unique_index("email")
await users.create_index("role")

# CRUD operations
await users.set("user-1", User(id="user-1", name="Alice", email="alice@example.com", role="admin"))
await users.set("user-2", User(id="user-2", name="Bob", email="bob@example.com", role="admin"))

# Lookup by primary key
user = await users.get("user-1")

# Lookup by unique index
user = await users.get("alice@example.com", index="email")

# Lookup all by secondary index
admins = await users.get_all("admin", index="role")

# Check existence
exists = await users.exists("alice@example.com", index="email")

# Iterate all
async for key, user in users.iterate():
    print(f"{key}: {user.name}")
```

## Testing

Comprehensive test suite in `tests/test_inmemory_datastore.py`:

- **CRUD Tests** (9 tests): Basic operations, edge cases
- **Indexing Tests** (5 tests): Secondary lookup, index updates on overwrite
- **Unique Index Tests** (5 tests): Constraint enforcement, cleanup on delete
- **Concurrency Tests** (2 tests): Concurrent reads, serialized writes
- **Edge Cases** (2 tests): Model copy isolation, table retrieval

Run tests:

```bash
cd backend && poetry run pytest src/trading_api/datastores/tests/ -v
```

## Related Documentation

- [datastore_interface.py](../../shared/datastore_interface.py) - Abstract interface definition
- [MODULAR_BACKEND_ARCHITECTURE.md](../../../docs/MODULAR_BACKEND_ARCHITECTURE.md) - Service datastore injection
