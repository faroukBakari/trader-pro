# WebSocket Client Auto-Generation Plan

**Date**: October 13, 2025
**Status**: 📋 Planning Document
**Version**: 1.0.0

## 🎯 Objective

Automate the generation of type-safe WebSocket clients from the backend AsyncAPI specification, following the established pattern documented in `WEBSOCKET-CLIENT-PATTERN.md`.

## 📦 What Currently Exists

### Manual Implementation ✅

- **Base Layer**: `wsClientBase.ts` - Generic WebSocket client foundation
- **Client Layer**: `barsClient.ts` - Bars-specific factory implementation
- **Type Layer**: `ws-types.ts` - Manual type definitions
- **Pattern**: Fully documented and production-ready

### Current Workflow

```
1. Backend defines AsyncAPI spec
2. Frontend manually creates types (ws-types.ts)
3. Frontend manually creates factory (barsClient.ts)
4. Frontend uses factory in services
```

**Problem**: Manual steps 2-3 are repetitive and error-prone.

## 🎨 Auto-Generation Vision

### Target Workflow

```
1. Backend defines AsyncAPI spec
2. Run: npm run generate-ws-client
3. ✅ Types generated automatically
4. ✅ Factories generated automatically
5. Frontend uses generated factories in services
```

## 🏗️ Architecture

### Input: AsyncAPI Specification

**Source**: Backend exposes AsyncAPI spec at `/api/v1/ws/asyncapi.json`

### ⭐ Key Variables for Client Generation

For each WebSocket route, we need to extract **3 critical variables** from the AsyncAPI spec:

1. **Subscription Route Prefix** (string)
   - Example: `'bars'`
   - Used as: Topic prefix and client name
   - Extracted from: Channel name in AsyncAPI spec

2. **Subscription Request Type** (TypeScript interface)
   - Example: `BarsSubscriptionRequest`
   - Used as: Generic parameter `<TRequest, ...>`
   - Extracted from: `subscribe` operation message payload schema

3. **Subscription Data Model** (TypeScript interface)
   - Example: `Bar`
   - Used as: Generic parameter `<..., TData>`
   - Extracted from: `publish` operation message payload schema

**Generation Formula**:
```typescript
### Generation Template

**Target**: `src/plugins/generated/{Variable1}Client.ts`

**Template with 3 Variables**:
```typescript
// Replace {Variable1}, {Variable2}, {Variable3} with extracted values

import type { {Variable2}, {Variable3} } from '../ws-types-generated'
import type { WebSocketInterface } from '../wsClientBase'
import { WebSocketClientBase } from '../wsClientBase'

export type {CapitalizedVariable1}WebSocketInterface = WebSocketInterface<{Variable2}, {Variable3}>

export function {CapitalizedVariable1}WebSocketClientFactory(): {CapitalizedVariable1}WebSocketInterface {
  return new WebSocketClientBase<{Variable2}, {Variable3}>('{Variable1}')
}
```

**Variable Mapping**:
- `{Variable1}` → Route prefix (e.g., 'bars', 'quotes', 'trades')
- `{CapitalizedVariable1}` → Capitalized route prefix (e.g., 'Bars', 'Quotes', 'Trades')
- `{Variable2}` → Request type name (e.g., 'BarsSubscriptionRequest')
- `{Variable3}` → Data model name (e.g., 'Bar')
```

**Example Structure**:
```json
{
  "asyncapi": "2.4.0",
  "info": {
    "title": "Trading WebSockets",
    "version": "1.0.0"
  },
  "channels": {
    "bars": {
      "subscribe": {
        "message": {
          "name": "BarsSubscriptionRequest",
          "payload": {
            "$ref": "#/components/schemas/BarsSubscriptionRequest"
          }
        }
      },
      "publish": {
        "message": {
          "name": "Bar",
          "payload": {
            "$ref": "#/components/schemas/Bar"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "BarsSubscriptionRequest": {
        "type": "object",
        "properties": {
          "symbol": { "type": "string" },
          "resolution": { "type": "string" }
        },
        "required": ["symbol", "resolution"]
      },
      "Bar": {
        "type": "object",
        "properties": {
          "time": { "type": "integer" },
          "open": { "type": "number" },
          "high": { "type": "number" },
          "low": { "type": "number" },
          "close": { "type": "number" },
          "volume": { "type": "integer" }
        }
      }
    }
  }
}
```

### Output: Generated Files

**1. Type Definitions** (`src/plugins/ws-types-generated.ts`):
```typescript
// Auto-generated from AsyncAPI specification
// DO NOT EDIT MANUALLY

/**
 * Request type for 'bars' route (Variable 2)
 * Used as first generic parameter: WebSocketClientBase<BarsSubscriptionRequest, Bar>
 */
export interface BarsSubscriptionRequest {
  symbol: string
  resolution: string
}

/**
 * Data model for 'bars' route (Variable 3)
 * Used as second generic parameter: WebSocketClientBase<BarsSubscriptionRequest, Bar>
 */
export interface Bar {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/**
 * Request type for 'quotes' route (Variable 2)
 */
export interface QuotesSubscriptionRequest {
  symbol: string
}

/**
 * Data model for 'quotes' route (Variable 3)
 */
export interface Quote {
  symbol: string
  bid: number
  ask: number
  last: number
}
```

**2. Client Factories** (`src/plugins/generated/`):

```typescript
// src/plugins/generated/barsClient.ts
// Auto-generated from AsyncAPI specification
// DO NOT EDIT MANUALLY
//
// Generation variables extracted from AsyncAPI:
//   ⭐ Route Prefix: 'bars'
//   ⭐ Request Type: BarsSubscriptionRequest
//   ⭐ Data Model: Bar

import type { BarsSubscriptionRequest, Bar } from '../ws-types-generated'
import type { WebSocketInterface } from '../wsClientBase'
import { WebSocketClientBase } from '../wsClientBase'

/**
 * WebSocket client interface for bars data
 * 
 * Generation template:
 * - Route prefix: 'bars' (Variable 1)
 * - Request type: BarsSubscriptionRequest (Variable 2)
 * - Data model: Bar (Variable 3)
 */
export type BarsWebSocketInterface = WebSocketInterface<
  BarsSubscriptionRequest,  // Variable 2
  Bar                       // Variable 3
>

/**
 * Factory function for creating Bars WebSocket client
 * 
 * @returns WebSocket client for bars data
 */
export function BarsWebSocketClientFactory(): BarsWebSocketInterface {
  return new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
  //                              ^^^^^^^^^^^^^^^^^^^^  ^^^   ^^^^^^
  //                              Variable 2            Var3  Variable 1
}
```

```typescript
// src/plugins/generated/quotesClient.ts
// Auto-generated from AsyncAPI specification
// DO NOT EDIT MANUALLY
//
// Generation variables extracted from AsyncAPI:
//   ⭐ Route Prefix: 'quotes'
//   ⭐ Request Type: QuotesSubscriptionRequest
//   ⭐ Data Model: Quote

import type { QuotesSubscriptionRequest, Quote } from '../ws-types-generated'
import type { WebSocketInterface } from '../wsClientBase'
import { WebSocketClientBase } from '../wsClientBase'

/**
 * WebSocket client interface for quotes data
 * 
 * Generation template:
 * - Route prefix: 'quotes' (Variable 1)
 * - Request type: QuotesSubscriptionRequest (Variable 2)
 * - Data model: Quote (Variable 3)
 */
export type QuotesWebSocketInterface = WebSocketInterface<
  QuotesSubscriptionRequest,  // Variable 2
  Quote                       // Variable 3
>

/**
 * Factory function for creating Quotes WebSocket client
 * 
 * @returns WebSocket client for quotes data
 */
export function QuotesWebSocketClientFactory(): QuotesWebSocketInterface {
  return new WebSocketClientBase<QuotesSubscriptionRequest, Quote>('quotes')
  //                              ^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^   ^^^^^^^^
  //                              Variable 2                 Var3   Variable 1
}
```

**3. Index File** (`src/plugins/generated/index.ts`):
```typescript
// Auto-generated index
// DO NOT EDIT MANUALLY

export * from './barsClient'
export * from './quotesClient'
export * from './tradesClient'
export * from './ordersClient'
```

## 🛠️ Generator Implementation

### Reference Implementation: barsClient.ts

**Current Manual Implementation** (serves as generation template):

```typescript
// frontend/src/plugins/barsClient.ts
import type { BarsSubscriptionRequest, Bar } from './ws-types'
import type { WebSocketInterface } from './wsClientBase'
import { WebSocketClientBase } from './wsClientBase'

export type BarsWebSocketInterface = WebSocketInterface<BarsSubscriptionRequest, Bar>

export function BarsWebSocketClientFactory(): BarsWebSocketInterface {
  return new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
}
```

**3 Key Variables in This Example**:
1. ⭐ **Route Prefix**: `'bars'` (used as topic prefix and in function name)
2. ⭐ **Request Type**: `BarsSubscriptionRequest` (first generic parameter)
3. ⭐ **Data Model**: `Bar` (second generic parameter)

**Generation Pattern**: This exact structure will be replicated for every WebSocket route, with only these 3 variables changing.

### Generator Script

**File**: `scripts/generate-ws-client.mjs`

**Responsibilities**:
1. Fetch AsyncAPI spec from backend
2. Parse channels and extract the **3 key variables** per route
3. Generate TypeScript type definitions from AsyncAPI schemas
4. Generate client factory modules using the 3 variables
5. Generate index file
6. Write files to output directory

**CLI Usage**:
```bash
# Generate from URL (preferred)
npm run generate-ws-client

# Generate from local file
npm run generate-ws-client -- --from-file ./asyncapi.json

# Dry run (preview without writing)
npm run generate-ws-client -- --dry-run

# Verbose output
npm run generate-ws-client -- --verbose
```

### Generator Algorithm

```javascript
// Pseudo-code for generator

async function generateWebSocketClients(asyncApiUrl, outputDir) {
  // 1. Fetch AsyncAPI spec
  const spec = await fetchAsyncAPI(asyncApiUrl)
  
  // 2. Extract channels
  const channels = spec.channels
  
  // 3. For each channel, extract the 3 key variables:
  //    ⭐ Variable 1: Subscription route prefix (channel name)
  //    ⭐ Variable 2: Subscription request type (subscribe message schema)
  //    ⭐ Variable 3: Subscription data model (publish message schema)
  const clients = []
  
  for (const [channelName, channel] of Object.entries(channels)) {
    const subscribeMsg = channel.subscribe?.message
    const publishMsg = channel.publish?.message
    
    if (!subscribeMsg || !publishMsg) continue
    
    // ⭐ Extract the 3 key variables
    const routePrefix = channelName                              // e.g., 'bars'
    const requestType = extractTypeName(subscribeMsg.payload.$ref) // e.g., 'BarsSubscriptionRequest'
    const dataModel = extractTypeName(publishMsg.payload.$ref)     // e.g., 'Bar'
    
    clients.push({
      routePrefix,    // Variable 1: Route prefix
      requestType,    // Variable 2: Request type
      dataModel,      // Variable 3: Data model
    })
  }
  
  // 4. Generate type definitions from AsyncAPI schemas
  const typeDefs = generateTypeDefinitions(spec.components.schemas)
  await writeFile(`${outputDir}/ws-types-generated.ts`, typeDefs)
  
  // 5. Generate client factories using the 3 variables
  for (const client of clients) {
    const clientCode = generateClientFactory(
      client.routePrefix,  // Variable 1
      client.requestType,  // Variable 2
      client.dataModel     // Variable 3
    )
    await writeFile(
      `${outputDir}/generated/${client.routePrefix}Client.ts`,
      clientCode
    )
  }
  
  // 6. Generate index
  const indexCode = generateIndex(clients)
  await writeFile(`${outputDir}/generated/index.ts`, indexCode)
  
  console.log(`✅ Generated ${clients.length} WebSocket clients`)
}

/**
 * Extract type name from AsyncAPI $ref
 * Example: '#/components/schemas/BarsSubscriptionRequest' -> 'BarsSubscriptionRequest'
 */
function extractTypeName(ref) {
  return ref.split('/').pop()
}
```

### Type Generation

```javascript
function generateTypeDefinitions(schemas) {
  let code = `// Auto-generated from AsyncAPI specification\n`
  code += `// DO NOT EDIT MANUALLY\n\n`
  
  for (const [name, schema] of Object.entries(schemas)) {
    code += generateInterface(name, schema)
    code += `\n`
  }
  
  return code
}

function generateInterface(name, schema) {
  let code = `export interface ${name} {\n`
  
  for (const [propName, propSchema] of Object.entries(schema.properties)) {
    const tsType = mapJsonSchemaTypeToTS(propSchema.type)
    const required = schema.required?.includes(propName)
    const optional = required ? '' : '?'
    
    code += `  ${propName}${optional}: ${tsType}\n`
  }
  
  code += `}\n`
  return code
}

function mapJsonSchemaTypeToTS(jsonType) {
  const typeMap = {
    'string': 'string',
    'integer': 'number',
    'number': 'number',
    'boolean': 'boolean',
    'array': 'any[]',
    'object': 'object',
  }
  return typeMap[jsonType] || 'any'
}
```

### Client Factory Generation

```javascript
/**
 * Generate client factory from the 3 key variables
 * 
 * @param {string} routePrefix - Variable 1: Route prefix (e.g., 'bars')
 * @param {string} requestType - Variable 2: Request type (e.g., 'BarsSubscriptionRequest')
 * @param {string} dataModel - Variable 3: Data model (e.g., 'Bar')
 */
function generateClientFactory(routePrefix, requestType, dataModel) {
  const clientName = capitalize(routePrefix) // 'bars' -> 'Bars'
  
  return `// Auto-generated from AsyncAPI specification
// DO NOT EDIT MANUALLY

import type { ${requestType}, ${dataModel} } from '../ws-types-generated'
import type { WebSocketInterface } from '../wsClientBase'
import { WebSocketClientBase } from '../wsClientBase'

/**
 * WebSocket client interface for ${routePrefix} data
 * 
 * Uses:
 * - Route prefix: '${routePrefix}'
 * - Request type: ${requestType}
 * - Data model: ${dataModel}
 */
export type ${clientName}WebSocketInterface = WebSocketInterface<
  ${requestType},
  ${dataModel}
>

/**
 * Factory function for creating ${clientName} WebSocket client
 * 
 * @returns WebSocket client for ${routePrefix} data
 * 
 * @example
 * const client = ${clientName}WebSocketClientFactory()
 * await client.subscribe(
 *   { /* ${requestType} properties *\/ },
 *   (data: ${dataModel}) => console.log(data)
 * )
 */
export function ${clientName}WebSocketClientFactory(): ${clientName}WebSocketInterface {
  return new WebSocketClientBase<${requestType}, ${dataModel}>('${routePrefix}')
}
`
}

/**
 * Capitalize first letter
 * Example: 'bars' -> 'Bars'
 */
function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}
```

## 📋 Implementation Checklist

### Phase 1: Basic Generator ⏳

- [ ] Create `scripts/generate-ws-client.mjs`
- [ ] Implement AsyncAPI spec fetching (HTTP)
- [ ] Implement channel parsing
- [ ] Implement type definition generation
- [ ] Implement client factory generation
- [ ] Implement index generation
- [ ] Add CLI arguments support
- [ ] Add error handling
- [ ] Add validation (ensure spec is valid)

### Phase 2: Integration ⏳

- [ ] Add npm script: `generate-ws-client`
- [ ] Update `.gitignore` (ignore generated files)
- [ ] Update build process (generate before build)
- [ ] Create documentation for generator usage
- [ ] Add pre-commit hook (optional: regenerate on backend change)

### Phase 3: Advanced Features ⏳

- [ ] Support for nested schemas
- [ ] Support for enums
- [ ] Support for arrays and unions
- [ ] Support for generic parameters
- [ ] Generate mock implementations
- [ ] Generate integration tests
- [ ] Generate JSDoc comments
- [ ] Support for custom templates

### Phase 4: Testing ⏳

- [ ] Unit tests for generator functions
- [ ] Integration tests (generate from real spec)
- [ ] Validation tests (verify generated code compiles)
- [ ] Snapshot tests (ensure consistent output)

## 🎯 Success Criteria

### Must Have ✅

- [ ] Generate types from AsyncAPI schemas
- [ ] Generate client factories for all channels
- [ ] Generated code compiles without errors
- [ ] Generated code follows established pattern
- [ ] Include header comments ("DO NOT EDIT")
- [ ] Support for basic JSON Schema types

### Should Have 📝

- [ ] CLI with flags (--dry-run, --verbose, etc.)
- [ ] Error handling and validation
- [ ] Progress reporting
- [ ] Support for nested schemas
- [ ] Generate index file

### Nice to Have 🎁

- [ ] Generate mock implementations
- [ ] Generate tests
- [ ] Generate JSDoc comments
- [ ] Watch mode (regenerate on spec change)
- [ ] Diff reporting (show what changed)

## 🔄 Workflow Integration

### Development Workflow

```bash
# 1. Backend developer updates AsyncAPI spec
cd backend
# Edit src/trading_api/ws/datafeed.py
make dev

# 2. Frontend developer generates clients
cd frontend
npm run generate-ws-client

# 3. Generated files appear in src/plugins/generated/
# 4. Use generated clients in services
import { BarsWebSocketClientFactory } from '@/plugins/generated'

const wsClient = BarsWebSocketClientFactory()
```

### CI/CD Integration

```yaml
# .github/workflows/frontend.yml

jobs:
  build:
    steps:
      - name: Generate WebSocket clients
        run: |
          cd frontend
          npm run generate-ws-client
      
      - name: Type check
        run: |
          cd frontend
          npm run type-check
      
      - name: Build
        run: |
          cd frontend
          npm run build
```

## 📁 Directory Structure

```
frontend/
├── scripts/
│   └── generate-ws-client.mjs       ⭐ Generator script
├── src/
│   └── plugins/
│       ├── wsClientBase.ts          ✅ Manual (base class)
│       ├── ws-types-generated.ts    🤖 Generated (types)
│       └── generated/               🤖 Generated (factories)
│           ├── index.ts
│           ├── barsClient.ts
│           ├── quotesClient.ts
│           └── tradesClient.ts
└── package.json
    └── scripts:
        └── "generate-ws-client": "node scripts/generate-ws-client.mjs"
```

## 🎓 Learning from Phase 1

### What Worked Well ✅

From `WS-CLIENT-GENERATION-PHASE1.md`, we learned:

1. **Custom generator is better** - Lighter than AsyncAPI official tools
2. **Interface-based design is key** - Enables flexibility and testing
3. **Native WebSocket API** - Zero dependencies, works everywhere
4. **TypeScript-first** - Full type safety from backend to frontend
5. **Composition over inheritance** - Easier to test and maintain

### What to Improve 📈

1. **Automate type generation** - Currently manual
2. **Automate client generation** - Currently manual
3. **Better error messages** - Guide developers when things fail
4. **Watch mode** - Auto-regenerate on spec changes
5. **Validation** - Ensure spec matches expected structure

## 🔗 Related Documentation

- **Pattern**: [WEBSOCKET-CLIENT-PATTERN.md](./WEBSOCKET-CLIENT-PATTERN.md)
- **Summary**: [WEBSOCKET-IMPLEMENTATION-SUMMARY.md](./WEBSOCKET-IMPLEMENTATION-SUMMARY.md)
- **Phase 1**: [WS-CLIENT-GENERATION-PHASE1.md](./WS-CLIENT-GENERATION-PHASE1.md)
- **Backend API**: [../backend/docs/websockets.md](../backend/docs/websockets.md)

## 📊 Estimated Effort

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| **Phase 1: Basic Generator** | Core generation logic | 4-6 hours |
| **Phase 2: Integration** | Build integration, docs | 2-3 hours |
| **Phase 3: Advanced Features** | Nested schemas, enums, etc. | 4-6 hours |
| **Phase 4: Testing** | Unit + integration tests | 3-4 hours |
| **Total** | | **13-19 hours** |

## 🚀 Next Steps

1. **Create generator script** - `scripts/generate-ws-client.mjs`
2. **Implement basic generation** - Types + factories
3. **Test with real AsyncAPI spec** - Use backend spec
4. **Integrate with build process** - Add npm scripts
5. **Document usage** - Update README
6. **Add tests** - Ensure reliability
7. **Announce to team** - Share pattern and generator

## 💡 Example Usage (After Implementation)

```bash
# Generate WebSocket clients
npm run generate-ws-client

# Output:
# ✅ Fetched AsyncAPI spec from http://localhost:8000/api/v1/ws/asyncapi.json
# ✅ Found 4 channels: bars, quotes, trades, orders
# ✅ Generated types: ws-types-generated.ts
# ✅ Generated factories:
#    - generated/barsClient.ts
#    - generated/quotesClient.ts
#    - generated/tradesClient.ts
#    - generated/ordersClient.ts
# ✅ Generated index: generated/index.ts
# 🎉 Done! Generated 4 WebSocket clients
```

Then in your code:

```typescript
import { 
  BarsWebSocketClientFactory,
  QuotesWebSocketClientFactory,
  TradesWebSocketClientFactory,
  OrdersWebSocketClientFactory,
} from '@/plugins/generated'

// All generated automatically from AsyncAPI spec!
const barsClient = BarsWebSocketClientFactory()
const quotesClient = QuotesWebSocketClientFactory()
const tradesClient = TradesWebSocketClientFactory()
const ordersClient = OrdersWebSocketClientFactory()
```

---

**Status**: 📋 Planning Document - Ready for Implementation
**Version**: 1.0.0
**Date**: October 13, 2025
**Next**: Begin Phase 1 implementation
