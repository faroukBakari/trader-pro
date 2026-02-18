---
name: python-typing-patterns
description: Type-first Python with Pydantic, Protocol, and discriminated unions. Load when writing models or enforcing typing
user-invocable: false
---

# Python Typing Patterns

Type-first development methodology for Python backends using Pydantic models, Protocol-based interfaces, and strict type enforcement. Adapted from industry best practices for contract-first architectures.

---

## <when_to_use>

Apply when:
- Defining Pydantic models or data schemas
- Writing service interfaces or provider contracts
- Adding type hints to new or existing code
- Reviewing code for typing violations
- Building discriminated unions or domain primitives

Do NOT use:
- For TypeScript typing (see `typescript-contract-types`)
- For test-specific patterns (see `backend-testing`)

</when_to_use>

---

## <methodology>

### Type-First Workflow

Types define the contract before implementation:

1. **Define data models** — Pydantic BaseModel or dataclass first
2. **Define function signatures** — parameter and return type hints
3. **Implement to satisfy types** — let the type checker guide completeness
4. **Validate at boundaries** — runtime checks where data enters the system

### Zero-Tolerance Enforcement

| Rule | Rationale |
|------|-----------|
| No `Any` | Defeats the type system — use `object` or `unknown` generics |
| No `# type: ignore` without comment | Must explain why suppression is unavoidable |
| Full return types | Every function declares its return type |
| No untyped `def` | Parameters and returns always annotated |

### Pydantic Model Patterns

**Base model with strict config:**
```python
from pydantic import BaseModel, Field, ConfigDict

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
```

**Discriminated unions with Literal:**
```python
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field

class MarketOrder(BaseModel):
    type: Literal["market"] = "market"
    quantity: int

class LimitOrder(BaseModel):
    type: Literal["limit"] = "limit"
    quantity: int
    price: float

Order = Annotated[
    Union[MarketOrder, LimitOrder],
    Field(discriminator="type"),
]

# Pydantic auto-selects the right model based on `type` field
```

**NewType for domain primitives:**
```python
from typing import NewType

OrderId = NewType("OrderId", int)
AccountId = NewType("AccountId", str)

def get_order(order_id: OrderId) -> Order:
    # Type checker prevents passing AccountId here
    ...
```

**SQLModel table classes with complex fields:**
```python
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

class MyTable(SQLModel, table=True):
    # Pydantic BaseModel fields need sa_column — SQLModel can't auto-map them
    metadata: Optional[MyPydanticModel] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
```

**Annotated for validation metadata:**
```python
from typing import Annotated
from pydantic import BaseModel, Field

class Position(BaseModel):
    symbol: Annotated[str, Field(min_length=1, max_length=10)]
    quantity: Annotated[int, Field(gt=0)]
    price: Annotated[float, Field(ge=0.0)]
```

### Protocol for Structural Typing

Use Protocol to define interfaces without inheritance coupling:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class OrderExecutor(Protocol):
    async def place_order(self, order: Order) -> OrderId: ...
    async def cancel_order(self, order_id: OrderId) -> bool: ...

class ServiceInterface(Protocol):
    """Base protocol for module services."""
    async def health_check(self) -> dict[str, str]: ...
```

**When to use Protocol vs ABC:**

| Use Protocol when | Use ABC when |
|-------------------|-------------|
| Defining capability contracts | Providing shared implementation |
| Consumer doesn't control producer | Enforcing inheritance hierarchy |
| Multiple unrelated implementors | Single implementation chain |
| Testing with lightweight mocks | Need `super()` calls in chain |

### Exhaustive Match Handling

```python
from typing import Never

def handle_order(order: Order) -> str:
    match order:
        case MarketOrder():
            return "executing at market"
        case LimitOrder():
            return f"queued at {order.price}"
        case _ as unreachable:
            assert_never(unreachable)

def assert_never(value: Never) -> Never:
    raise AssertionError(f"Unhandled value: {value!r}")
```

### Exception Propagation

```python
# Always chain with `from` to preserve traceback
try:
    data = parse_message(raw)
except ValueError as err:
    raise InvalidOrderError(f"bad order payload: {err}") from err

# Every code path returns a value or raises
def resolve_symbol(raw: str) -> str:
    if not raw:
        raise ValueError("empty symbol")
    return raw.upper().strip()
```

### Abstract Collection Types for Parameters

```python
from collections.abc import Iterable, Sequence, Mapping

# Accept broad types in parameters
def process_orders(orders: Iterable[Order]) -> list[OrderId]:
    return [execute(o) for o in orders]

# Return concrete types
def get_positions() -> list[Position]:
    ...
```

</methodology>

---

## <decision_shortcuts>

| Situation | Pattern |
|-----------|---------|
| "New data model" | Pydantic BaseModel with ConfigDict |
| "Multiple variants of same concept" | Discriminated union with Literal + Field(discriminator=) |
| "ID that shouldn't mix with other IDs" | NewType |
| "Interface for capability injection" | Protocol (runtime_checkable if needed) |
| "Dict with known keys from external data" | TypedDict (not BaseModel — no validation overhead) |
| "Constant that shouldn't change" | Final |
| "Function parameter is any collection" | Iterable/Sequence/Mapping from collections.abc |
| "Need to narrow type in conditional" | TypeGuard or isinstance |
| "Match must cover all cases" | assert_never in default case |

</decision_shortcuts>

---

## <anti_patterns>

| Anti-Pattern | Fix |
|-------------|-----|
| `Any` as parameter or return type | Use specific type, `object`, or bounded TypeVar |
| `dict` without key/value types | `dict[str, int]` or TypedDict |
| `# type: ignore` without explanation | Add comment: `# type: ignore[assignment]  # reason` |
| Bare `except Exception` swallowing errors | Re-raise with context or return meaningful result |
| Mutable default arguments (`def f(x=[])`) | Use `None` default + create inside function |
| Protocol with `__init__` | Protocols define behavior, not construction |
| Dataclass for API boundary data | Use Pydantic BaseModel (validation + serialization) |
| `isinstance` checks on Pydantic unions | Use discriminator field instead |

</anti_patterns>
