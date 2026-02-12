---
name: typescript-contract-types
description: Contract-first TypeScript types for generated clients and mapper isolation. Load when writing mappers or API types
keywords: [typescript, types, mappers, generated-clients, contract-first, type-guards, imports]
category: frontend
disable-model-invocation: true
---

# TypeScript Contract Types

Type consumption and mapping patterns for contract-first architectures where backend models generate OpenAPI/AsyncAPI specs, which generate TypeScript clients. Frontend code never hand-writes API types — it consumes generated ones through mappers.

---

## <when_to_use>

Apply when:
- Writing or modifying type mappers (REST or WebSocket)
- Importing types from generated clients
- Defining frontend-only types (UI state, form data, component props)
- Adding type guards for API responses or WS messages
- Reviewing frontend code for type safety

Do NOT use:
- For Python/backend typing (see `python-typing-patterns`)
- For Vue component patterns (see `vue-frontend`)

</when_to_use>

---

## <methodology>

### The Contract-First Type Flow

```
Backend Pydantic Model → OpenAPI/AsyncAPI Spec → Generated TS Client → Mapper → Frontend Type
```

**Rules:**
1. **Never hand-write** types that exist in generated clients
2. **Never import** generated types directly in services or components — go through mappers
3. **Mappers are the only bridge** between backend and frontend type worlds

### Import Naming Convention

When a generated type name collides with a frontend type, use suffixed aliases:

```typescript
// REST client types: {TypeName}_Api_Backend
import type { PreOrder as PreOrder_Api_Backend } from "@clients/trader-client-broker_v1";
import type { Account as Account_Api_Backend } from "@clients/trader-client-broker_v1";

// WebSocket types: {TypeName}_Ws_Backend
import type { PlacedOrder as PlacedOrder_Ws_Backend } from "@clients/ws-types-broker_v1";
import type { BarData as BarData_Ws_Backend } from "@clients/ws-types-datafeed_v1";

// Frontend types (no suffix — these are the "native" types)
import type { PlacedOrder } from "@public/trading_terminal/charting_library";
```

**Suffix rules:**

| Source | Suffix | Example |
|--------|--------|---------|
| REST generated client | `_Api_Backend` | `PreOrder_Api_Backend` |
| WebSocket generated types | `_Ws_Backend` | `PlacedOrder_Ws_Backend` |
| Frontend / charting library | *(none)* | `PlacedOrder` |

**Wrong — missing or incomplete suffix:**
```typescript
// BAD: ambiguous — which PlacedOrder?
import type { PlacedOrder as PlacedOrder_Backend } from "...";

// BAD: no suffix at all when collision exists
import type { PlacedOrder } from "@clients/ws-types-broker_v1";
```

### Mapper Isolation Pattern

Services and components use **only** frontend types. Mappers handle all conversions:

```typescript
// mappers.ts — the ONLY file that imports from both worlds
import type { PreOrder as PreOrder_Api_Backend } from "@clients/trader-client-broker_v1";
import type { PreOrder } from "../types";

export function mapPreOrder(frontendOrder: PreOrder): PreOrder_Api_Backend {
    return {
        symbol: frontendOrder.symbol,
        quantity: frontendOrder.qty,
        order_type: frontendOrder.type,
    };
}

export function mapOrder(backendOrder: Order_Api_Backend): Order {
    return {
        id: backendOrder.id,
        symbol: backendOrder.symbol,
        qty: backendOrder.quantity,
        type: backendOrder.order_type,
        status: mapOrderStatus(backendOrder.status),
    };
}
```

**Service consumes only frontend types:**
```typescript
// orderService.ts — no generated client imports here
import type { PreOrder, Order } from "../types";
import { mapPreOrder, mapOrder } from "./mappers";

async function placeOrder(order: PreOrder): Promise<Order> {
    const response = await apiClient.createOrder(mapPreOrder(order));
    return mapOrder(response);
}
```

### WebSocket Adapter Pattern

WS adapters follow the same isolation — convert incoming WS messages to frontend types:

```typescript
// wsAdapter.ts
import type { PlacedOrder as PlacedOrder_Ws_Backend } from "@clients/ws-types-broker_v1";
import type { PlacedOrder } from "../types";

export function mapWsPlacedOrder(ws: PlacedOrder_Ws_Backend): PlacedOrder {
    return {
        id: ws.order_id,
        symbol: ws.symbol,
        filledQty: ws.filled_quantity,
        status: mapWsOrderStatus(ws.status),
    };
}
```

### Frontend-Only Type Patterns

Types that exist only in the frontend (UI state, form data, component props):

```typescript
// Use `interface` for object shapes
interface OrderFormData {
    symbol: string;
    quantity: number;
    orderType: "market" | "limit";
    limitPrice?: number;
}

// Use `type` for unions and aliases
type OrderTab = "open" | "filled" | "cancelled";
type LoadingState = "idle" | "loading" | "success" | "error";

// Props follow ComponentName + Props convention
interface OrderTableProps {
    orders: Order[];
    selectedTab: OrderTab;
    onSelect: (order: Order) => void;
}
```

### Utility Type Derivation

Derive types from base types instead of duplicating:

```typescript
// Create form data from entity by omitting server-generated fields
type OrderFormData = Omit<Order, "id" | "createdAt" | "status">;

// Partial update (all optional except ID)
type OrderUpdate = Partial<Omit<Order, "id">> & Pick<Order, "id">;

// Extract subset for display
type OrderSummary = Pick<Order, "id" | "symbol" | "status">;
```

### Type Guards

```typescript
// Discriminated union guard
interface MarketOrder { type: "market"; quantity: number }
interface LimitOrder { type: "limit"; quantity: number; price: number }
type Order = MarketOrder | LimitOrder;

function isLimitOrder(order: Order): order is LimitOrder {
    return order.type === "limit";
}

// API error guard
interface ApiError { error: { code: string; message: string } }

function isApiError(response: unknown): response is ApiError {
    return (
        typeof response === "object" &&
        response !== null &&
        "error" in response
    );
}

// Never use `any` — narrow from `unknown`
function parseWsMessage(raw: unknown): WsMessage {
    if (!isValidWsMessage(raw)) {
        throw new Error("Invalid WebSocket message");
    }
    return raw;
}
```

### No `any` Enforcement

| Instead of | Use |
|-----------|-----|
| `any` | `unknown` + type guard |
| `as any` | `as unknown as TargetType` (last resort, with comment) |
| `Function` | `(...args: unknown[]) => unknown` or specific signature |
| `object` (bare) | `Record<string, unknown>` |
| Untyped event handler | `(event: MouseEvent) => void` |

</methodology>

---

## <decision_shortcuts>

| Situation | Pattern |
|-----------|---------|
| "Need a backend type in frontend code" | Import via mapper, never directly |
| "Same type name in backend and frontend" | Suffix backend import: `_Api_Backend` or `_Ws_Backend` |
| "New frontend-only type" | `interface` for objects, `type` for unions |
| "Form data type from entity" | `Omit<Entity, "id" \| "createdAt" \| ...>` |
| "Optional update type" | `Partial<Omit<Entity, "id">> & Pick<Entity, "id">` |
| "Check API response shape" | Type guard function returning `response is T` |
| "Parse unknown WS message" | Narrow from `unknown` with type guard, never `any` |
| "Component props type" | `interface {ComponentName}Props` |
| "Constrained string values" | `type Foo = "a" \| "b" \| "c"` |

</decision_shortcuts>

---

## <anti_patterns>

| Anti-Pattern | Fix |
|-------------|-----|
| Importing generated types directly in components | Import through mappers only |
| `any` anywhere | `unknown` + type guard |
| Missing suffix on aliased backend import | Add `_Api_Backend` or `_Ws_Backend` |
| Hand-writing types that exist in generated clients | Import from generated client |
| Duplicating type definition instead of deriving | Use Omit/Pick/Partial from base type |
| Mapper that returns `any` or untyped object | Full return type annotation |
| Backend snake_case leaking into frontend types | Map to camelCase in mapper function |
| `as Type` assertion without validation | Type guard function or runtime check |

</anti_patterns>
