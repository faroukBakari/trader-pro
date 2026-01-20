# API Client Generation

**Last Updated**: January 2, 2026  
**Status**: ✅ Implemented | **Mode**: Per-Module Generation

## Overview

The Trading Pro frontend automatically generates type-safe TypeScript clients from backend API specifications. Specs are generated **per-module** in `backend/src/trading_api/modules/{module}/specs_generated/` and frontend clients are generated from these specs.

## How It Works

### Per-Module Generation

```bash
Backend: make generate → Per-module specs → Frontend: make generate → TypeScript clients
```

**Key Features:**

- ✅ Per-module spec generation (`modules/{module}/specs_generated/`)
- ✅ Versioned spec files (`{module}_v{N}_openapi.json`)
- ✅ Type-safe TypeScript clients auto-generated
- ✅ Works in all environments (local, CI)

### Generation Process

```
┌─────────────────────────────────────────┐
│ Backend: make generate                  │
│ • Runs scripts/module_codegen.py        │
│ • Generates per-module specs            │
│ • modules/broker/specs_generated/       │
│   ├── broker_v1_openapi.json            │
│   └── broker_v1_asyncapi.json           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Frontend: make generate                 │
│ • Reads per-module specs                │
│ • Generates TypeScript REST clients     │
│ • Generates WebSocket types             │
│ • Output: clients_generated/            │
└─────────────────────────────────────────┘
```

### REST API Client

### Package Name Validation

Before generating any clients, the system validates that package names are unique and follow module naming conventions:

**Validation Rules:**

1. **OpenAPI Clients**: Package names must follow `@trader-pro/client-{module}` pattern
2. **AsyncAPI Types**: Package names must follow `ws-types-{module}` pattern
3. **Python Clients**: Class names must follow `{Module}Client` pattern
4. **Uniqueness**: No duplicate package names across all client types
5. **Module Correspondence**: Package names must match their source module names

**Automatic Validation:**

Package name validation runs automatically before:

- Frontend OpenAPI client generation (`make generate-openapi-client`)
- Frontend AsyncAPI type generation (`make generate-asyncapi-types`)
- Backend code generation (`make generate` - unified command for all specs and clients)

**Example Output:**

```
🔍 Validating backend modules for generated clients...

======================================================================
📋 Package Name Validation Results
======================================================================

✅ OpenAPI Clients (2 modules):
   broker          → @trader-pro/client-broker
   datafeed        → @trader-pro/client-datafeed

✅ AsyncAPI Types (2 modules):
   broker          → ws-types-broker
   datafeed        → ws-types-datafeed

✅ Python Clients (2 modules):
   broker          → BrokerClient
   datafeed        → DatafeedClient

======================================================================
✅ All package name validations passed!
```

**Error Detection:**

The validation catches common issues:

- ❌ Duplicate package names
- ❌ Package names not matching module names
- ❌ Inconsistent naming conventions
- ⚠️ Spec titles not indicating module names

### REST API Client

### Generation Command (Unified - Recommended)

```bash
# Generate all clients (REST + WebSocket) - RECOMMENDED
make generate

# This runs both:
# 1. OpenAPI client generation (REST API)
# 2. AsyncAPI types generation (WebSocket)
```

#### Individual Commands (Still Available)

For specific needs or backward compatibility, you can use these commands, but they internally call `make generate`:

```bash
# These are aliases to the unified command
make generate-openapi-client  # Generates via 'make generate'
make generate-asyncapi-types  # Generates via 'make generate'
```

**Note**: The unified `make generate` is the recommended approach for most workflows. Individual commands exist for backward compatibility and CI flexibility.

### Generated Files

```
frontend/src/clients_generated/trader-client-generated/
├── api/           # API client classes
├── models/        # TypeScript types
├── configuration.ts
└── index.ts       # Unified exports
```

### Usage

```typescript
import { HealthApi, VersioningApi } from "@/clients/trader-client-generated";

// Use generated clients
const healthApi = new HealthApi();
const health = await healthApi.getHealth();
```

## WebSocket Client

### Generation Command

WebSocket types are generated alongside REST clients via the unified command:

```bash
# Unified generation (REST + WebSocket) - RECOMMENDED
make generate

# Or use the specific alias (also calls 'make generate')
make generate-asyncapi-types
```

### Generated Files

```
frontend/src/clients_generated/
└── ws-types-generated/     # TypeScript interfaces
    └── index.ts            # Bar, BarsSubscriptionRequest, etc.
```

### Usage

```typescript
import { WsAdapter } from "@/plugins/wsAdapter";
import type { BarsSubscriptionRequest } from "@/plugins/wsAdapter";

// Use the centralized adapter
const wsAdapter = new WsAdapter();

// Subscribe to bars with automatic type mapping
await wsAdapter.bars.subscribe(
  "listener-id",
  { symbol: "AAPL", resolution: "1" },
  (bar) => console.log("New bar:", bar)
);
```

### Data Mappers

Type-safe data transformations between backend and frontend types are centralized in `src/plugins/mappers.ts`.

#### ⚠️ STRICT NAMING CONVENTIONS ⚠️

**CRITICAL**: All mapper type imports MUST follow this exact naming pattern:

```typescript
// ✅ CORRECT: Strict naming pattern
import type {
  PreOrder as PreOrder_Api_Backend,
  QuoteData as QuoteData_Api_Backend,
} from "@clients/trader-client-generated";

import type {
  PlacedOrder as PlacedOrder_Ws_Backend,
  Position as Position_Ws_Backend,
  Execution as Execution_Ws_Backend,
} from "@clients/ws-types-generated";

import type {
  PreOrder,
  QuoteData,
  PlacedOrder,
  Position,
  Execution,
} from "@public/trading_terminal/charting_library";

// ❌ WRONG: Inconsistent naming
import type { PreOrder as PreOrder_Backend } from "@clients/trader-client-generated";
import type { PlacedOrder as Order_Backend } from "@clients/ws-types-generated";
```

**Naming Rules**:

1. **API Backend types**: Always suffix with `_Api_Backend`
2. **WebSocket Backend types**: Always suffix with `_Ws_Backend`
3. **Frontend types**: No suffix, just the type name

**Benefits**:

- **Instant Recognition**: Know the source of each type at a glance
- **Easy Maintenance**: Consistent pattern across entire codebase
- **Clear Separation**: Distinguish between API and WebSocket variants
- **Better Debugging**: Quickly identify type mismatches

#### Why Mappers?

Backend and frontend may use different type definitions for the same concepts:

- **Enums**: Backend uses string literals, frontend uses numeric or different string enums
- **Field Names**: Backend snake_case vs frontend camelCase
- **Nested Structures**: Different object hierarchies
- **Optional Fields**: Different null handling strategies

#### Available Mappers

**`mapQuoteData()`** - Backend → Frontend quote data:

```typescript
import { mapQuoteData } from "@/plugins/mappers";
import type { QuoteData as QuoteData_Api_Backend } from "@/clients/trader-client-generated";
import type { QuoteData as QuoteData_Ws_Backend } from "@/clients/ws-types-generated";
import type { QuoteData } from "@public/trading_terminal/charting_library";

// Works with both REST API and WebSocket backend types
const frontendQuote: QuoteData = mapQuoteData(backendQuote);

// Handles error vs success states
if (frontendQuote.s === "ok") {
  console.log("Last price:", frontendQuote.v.lp);
} else {
  console.log("Error:", frontendQuote.v);
}
```

**`mapPreOrder()`** - Frontend → Backend order:

```typescript
import { mapPreOrder } from "@/plugins/mappers";
import type { PreOrder } from "@public/trading_terminal/charting_library";
import type { PreOrder as PreOrder_Backend } from "@/clients/trader-client-generated";

const backendOrder: PreOrder_Backend = mapPreOrder(frontendOrder);

// Handles:
// - Enum conversions (type: 'market' | 'limit' | ...)
// - Side conversions (buy = 1, sell = -1)
// - Optional fields (limitPrice, stopPrice, etc.)
// - Null vs undefined handling
```

#### Integration with Clients

**REST API**:

```typescript
import { ApiAdapter } from "@/plugins/apiAdapter";
import { mapQuoteData } from "@/plugins/mappers";

const api = new ApiAdapter();
const response = await api.getQuotes(["AAPL", "GOOGL"]);
const quotes = response.data.map(mapQuoteData); // Transform all quotes
```

**WebSocket** (Automatic):

```typescript
import { WsAdapter } from "@/plugins/wsAdapter";

const wsAdapter = new WsAdapter(); // Mappers already integrated!

// Mapper applied automatically on every message
await wsAdapter.quotes.subscribe(
  "quotes-listener",
  { symbols: ["AAPL"] },
  (quote) => {
    // quote is already transformed to frontend type
    console.log(quote.v.lp);
  }
);
```

#### Creating New Mappers

When to create a mapper:

1. Backend and frontend use different type definitions
2. Enum values need conversion between systems
3. Field names or structures differ
4. Type is used in multiple places (REST + WebSocket)
5. Complex nested transformations needed

**Example: Adding a new mapper**

```typescript
// mappers.ts
import type { Position as Position_Backend } from "@/clients/trader-client-generated";
import type { Position } from "@public/trading_terminal/charting_library";

export function mapPosition(pos: Position_Backend): Position {
  return {
    id: pos.id,
    symbol: pos.symbol,
    qty: pos.quantity, // Field name mapping
    side: pos.side === "buy" ? 1 : -1, // Enum conversion
    avgPrice: pos.avg_price, // snake_case → camelCase
    unrealizedPl: pos.unrealized_pl ?? 0, // Null handling
  };
}
```

#### Mapper Best Practices

✅ **DO**:

- Keep mappers pure functions (no side effects)
- Handle both success and error cases
- Add type annotations for clarity
- Test each mapper thoroughly
- Document complex transformations

❌ **DON'T**:

- Import backend types in services (only in mappers)
- Perform async operations in mappers
- Mix business logic with mapping
- Skip null/undefined handling
- Leave enum conversions unhandled

#### Testing Mappers

```typescript
import { describe, it, expect } from "vitest";
import { mapQuoteData } from "@/plugins/mappers";

describe("mapQuoteData", () => {
  it("maps success quote correctly", () => {
    const backend = {
      s: "ok",
      n: "AAPL",
      v: { lp: 150.0, bid: 149.9, ask: 150.1, ch: 1.5, chp: 1.0 },
    };

    const result = mapQuoteData(backend);

    expect(result.s).toBe("ok");
    expect(result.n).toBe("AAPL");
    expect(result.v.lp).toBe(150.0);
    expect(result.v.bid).toBe(149.9);
  });

  it("maps error quote correctly", () => {
    const backend = { s: "error", n: "INVALID", v: { error: "Not found" } };
    const result = mapQuoteData(backend);

    expect(result.s).toBe("error");
    expect(result.v).toBe("Not found");
  });

  it("handles missing optional fields", () => {
    const backend = {
      s: "ok",
      n: "AAPL",
      v: { lp: 150.0 /* minimal fields */ },
    };

    const result = mapQuoteData(backend);
    expect(result.v.lp).toBe(150.0);
  });
});
```

## Automatic Integration

### NPM Scripts

Client generation runs automatically before build and dev:

```json
{
  # Client generation is now handled by Makefiles
  # Run: make generate-openapi-client && make generate-asyncapi-types
}
```

### CI/CD Integration

```yaml
# Frontend job depends on backend to access spec generation
frontend:
  needs: [backend]
  steps:
    - name: Install backend deps
      run: make install-ci
      working-directory: backend

    - name: Generate clients
      run: make generate-openapi-client && make generate-asyncapi-types
```

## Offline vs Live Mode

### Offline Mode (Current - Default)

**Advantages:**

- ✅ No server startup delays
- ✅ Works in all environments
- ✅ No network connectivity needed
- ✅ Consistent across local/CI
- ✅ Fast (< 1 second)

**Backend Script:**

```python
# backend/scripts/export_openapi.py
openapi_schema = apiApp.openapi()
asyncapi_schema = wsApp.asyncapi()
# Write to files
```

### Live Mode (Deprecated)

Previously required running backend server to download specs. No longer used.

## Environment Variables

```bash
# Optional: Override API base path
export TRADER_API_BASE_PATH="/api"

# Optional: Skip backend spec regeneration
export SKIP_SPEC_GENERATION="true"
```

## CI-Aware Behavior

Client generation is now handled explicitly via Makefile targets:

```makefile
# Generate OpenAPI client
generate-openapi-client:
	cd frontend && ./scripts/generate-openapi-client.sh

# Generate AsyncAPI types
generate-asyncapi-types:
	cd frontend && ./scripts/generate-asyncapi-types.sh
```

## Troubleshooting

### Specs Not Generated

```bash
cd backend
make generate
# Check modules/{module}/specs_generated/ directories
ls -la src/trading_api/modules/*/specs_generated/
```

### Client Generation Fails

```bash
# Clean and regenerate
rm -rf frontend/src/clients_generated/*
make generate-openapi-client
make generate-asyncapi-types
```

### Type Errors After Generation

```bash
cd frontend
npm run type-check
# Fix any import issues in services
```

## Related Documentation

- **Backend Spec Generation**: See [backend/docs/SPECS_AND_CLIENT_GEN.md](../backend/docs/SPECS_AND_CLIENT_GEN.md)
- **WebSocket Architecture**: See [frontend/docs/WEBSOCKET-ARCHITECTURE.md](../frontend/docs/WEBSOCKET-ARCHITECTURE.md)
- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
