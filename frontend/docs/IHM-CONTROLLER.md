# IHM Controller Service

**Version**: 1.0.1  
**Last Updated**: November 30, 2025  
**Status**: ✅ Frontend Implementation Complete | ⚠️ Backend Module Pending

---

## Overview

The **IHM Controller Service** enables Vue components to expose programmatic APIs ("tools") that can be invoked remotely via WebSocket by external services such as AI agents, automation systems, or remote control interfaces.

**Key Design Principle**: Leverage existing WebSocket infrastructure - each tool is just another WebSocket channel type (like `orders`, `bars`, `quotes`).

### Use Cases

- **AI Agent Integration**: Allow AI to control UI elements (e.g., "show AAPL chart", "switch to 1H timeframe")
- **Automation Scripts**: Programmatically control frontend features
- **Remote Control**: Enable external systems to invoke UI actions
- **Testing/QA**: Automated UI interaction without Playwright/Selenium

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend Application                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────┐                                            │
│  │  Vue Component      │                                            │
│  │  (TraderChart)      │                                            │
│  └──────────┬──────────┘                                            │
│             │ 1. registerTool(schema, handler)                      │
│             │ 2. onUnmounted → unregisterTool(name)                 │
│             ↓                                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  IHMControllerService (Singleton)                            │   │
│  │  ─────────────────────────────────────────────────────────  │   │
│  │  • registeredTools: Map<string, ToolSchema>                 │   │
│  │  • registerTool(schema, handler)                            │   │
│  │  • unregisterTool(toolName)                                 │   │
│  │  • getRegisteredTools()                                     │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │ 3. subscribe(channel, schema, callback)│
│                             ↓                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  WsAdapter (WebSocket Client Manager)                       │   │
│  │  ─────────────────────────────────────────────────────────  │   │
│  │  • tools?: WebSocketInterface<TRequest, TData>              │   │
│  │  • bars, quotes, orders, positions, etc.                    │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │ 4. WebSocket connection              │
│                             ↓                                        │
└─────────────────────────────┼────────────────────────────────────────┘
                              │
                              │ ws://backend/v1/ihm/ws
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         Backend Application                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  IHM Module (Future Implementation)                         │   │
│  │  ─────────────────────────────────────────────────────────  │   │
│  │  • WebSocket router for tool commands                       │   │
│  │  • Validates tool schemas                                   │   │
│  │  • Routes commands to registered tools                      │   │
│  │  • Receives responses from frontend                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                             ↑                                        │
│                             │ External integrations                 │
│  ┌──────────────────────────┴──────────────────────────────────┐   │
│  │  AI Agent / Automation Service                              │   │
│  │  ─────────────────────────────────────────────────────────  │   │
│  │  • Discovers available tools via schema introspection       │   │
│  │  • Sends tool commands with parameters                      │   │
│  │  • Receives success/error responses                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Class Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     IHMControllerService                         │
├─────────────────────────────────────────────────────────────────┤
│ - static instance: IHMControllerService                         │
│ - registeredTools: Map<string, ToolSchema>                      │
│ - wsAdapter: WsAdapterType                                      │
├─────────────────────────────────────────────────────────────────┤
│ + static getInstance(): IHMControllerService                    │
│ + registerTool<TParams, TResult>(                               │
│     schema: ToolSchema,                                         │
│     handler: ToolHandler<TParams, TResult>                      │
│   ): void                                                        │
│ + unregisterTool(toolName: string): Promise<void>               │
│ + getRegisteredTools(): RegisteredTool[]                        │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ uses
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                         WsAdapter                                │
├─────────────────────────────────────────────────────────────────┤
│ + tools?: WebSocketInterface<ToolCommandRequest, ToolCommandData>│
│ + bars: WebSocketInterface<...>                                 │
│ + quotes: WebSocketInterface<...>                               │
│ + orders: WebSocketInterface<...>                               │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ implements
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              WebSocketInterface<TParams, TData>                  │
├─────────────────────────────────────────────────────────────────┤
│ + subscribe(                                                     │
│     channel: string,                                            │
│     params: TParams,                                            │
│     callback: (data: TData) => void                             │
│   ): Promise<void>                                               │
│ + unsubscribe(channel: string): Promise<void>                   │
│ + publish?(topic: string, data: unknown): Promise<void>         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Tool Registration Flow

```
┌──────────────┐
│ Component    │
│ Mount        │
└──────┬───────┘
       │
       │ 1. onMounted() or onChartReady()
       ↓
┌──────────────────────────────────────────────────────────────┐
│ ihmController.registerTool(schema, handler)                   │
└──────┬───────────────────────────────────────────────────────┘
       │
       │ 2. Check if wsAdapter.tools exists
       ↓
   ┌───────┐ NO
   │ tools?├────→ Log warning, store schema only, return
   └───┬───┘
       │ YES
       │ 3. Create WebSocket subscription
       ↓
┌────────────────────────────────────────────────────────────────┐
│ wsAdapter.tools.subscribe(                                     │
│   'ihm-command',                                               │
│   schema,  // Schema as subscription params                    │
│   async (wrapper: ToolCommandWrapper) => {                     │
│     // Command handler                                         │
│   }                                                             │
│ )                                                               │
└──────┬─────────────────────────────────────────────────────────┘
       │
       │ 4. On success
       ↓
┌────────────────────────────────────────────────────────────────┐
│ registeredTools.set(schema.name, schema)                       │
│ console.log('[IHMController] Tool registered')                 │
└────────────────────────────────────────────────────────────────┘
```

### Tool Invocation Flow

```
┌──────────────────┐
│ External Service │
│ (AI Agent)       │
└────────┬─────────┘
         │
         │ 1. Send tool command via backend
         ↓
┌──────────────────────────────────────────────────────────────────┐
│ Backend IHM Module                                               │
│ ──────────────────────────────────────────────────────────────  │
│ POST /v1/ihm/execute                                             │
│ { toolName: "displayStockChart", params: { symbol: "AAPL" } }   │
└────────┬─────────────────────────────────────────────────────────┘
         │
         │ 2. Forward to WebSocket
         ↓
┌──────────────────────────────────────────────────────────────────┐
│ WsAdapter.tools receives message:                                │
│ {                                                                 │
│   commandId: "cmd-123",                                          │
│   params: { symbol: "AAPL", timeframe: "1D" }                   │
│ }                                                                 │
└────────┬─────────────────────────────────────────────────────────┘
         │
         │ 3. Invoke registered callback
         ↓
┌──────────────────────────────────────────────────────────────────┐
│ IHMController Command Handler                                    │
│ ──────────────────────────────────────────────────────────────  │
│ try {                                                             │
│   const result = await handler(params)  // Execute tool         │
│   // Send success response                                       │
│   wsAdapter.tools.publish('ihm-response', {                     │
│     commandId: 'cmd-123',                                        │
│     tool: 'displayStockChart',                                   │
│     success: true,                                               │
│     result                                                        │
│   })                                                              │
│ } catch (error) {                                                 │
│   // Send error response                                         │
│   wsAdapter.tools.publish('ihm-response', {                     │
│     commandId: 'cmd-123',                                        │
│     tool: 'displayStockChart',                                   │
│     success: false,                                              │
│     error: error.message                                         │
│   })                                                              │
│ }                                                                 │
└────────┬─────────────────────────────────────────────────────────┘
         │
         │ 4. Response flows back
         ↓
┌──────────────────────────────────────────────────────────────────┐
│ Backend IHM Module receives response                             │
└────────┬─────────────────────────────────────────────────────────┘
         │
         │ 5. Return to external service
         ↓
┌──────────────────┐
│ External Service │
│ (AI Agent)       │
└──────────────────┘
```

### Tool Unregistration Flow

```
┌──────────────┐
│ Component    │
│ Unmount      │
└──────┬───────┘
       │
       │ 1. onUnmounted()
       ↓
┌──────────────────────────────────────────────────────────────┐
│ ihmController.unregisterTool('displayStockChart')             │
└──────┬───────────────────────────────────────────────────────┘
       │
       │ 2. Unsubscribe from WebSocket (if client available)
       ↓
┌────────────────────────────────────────────────────────────────┐
│ wsAdapter.tools?.unsubscribe('ihm-command')                    │
└──────┬─────────────────────────────────────────────────────────┘
       │
       │ 3. Remove from registry
       ↓
┌────────────────────────────────────────────────────────────────┐
│ registeredTools.delete('displayStockChart')                    │
│ console.log('[IHMController] Tool unregistered')               │
└────────────────────────────────────────────────────────────────┘
```

---

## Type Definitions

### Core Types

Located in `frontend/src/types/ihmController.ts`:

```typescript
/**
 * Tool schema - OpenAPI-style tool description
 */
export interface ToolSchema {
  /** Unique tool identifier (e.g., 'displayStockChart') */
  name: string

  /** Human-readable description for AI agents and documentation */
  description: string

  /** Parameter schema (OpenAPI-style) */
  parameters: {
    type: 'object'
    properties: Record<string, ToolParameterDefinition>
    required?: string[]
  }
}

/**
 * Tool parameter property definition
 */
export interface ToolParameterDefinition {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array'
  description: string
  enum?: string[]
  default?: unknown
  pattern?: string
  items?: ToolParameterDefinition
  properties?: Record<string, ToolParameterDefinition>
}

/**
 * Tool handler function signature
 */
export type ToolHandler<TParams = Record<string, unknown>, TResult = void> = (
  params: TParams,
) => Promise<TResult>

/**
 * Tool command wrapper (WebSocket message from backend)
 */
export interface ToolCommandWrapper<TParams = unknown> {
  /** Unique command ID for response correlation */
  commandId: string

  /** Tool invocation parameters */
  params: TParams
}

/**
 * Tool response wrapper (WebSocket message to backend)
 */
export interface ToolResponseWrapper {
  /** Command ID from request (for correlation) */
  commandId: string

  /** Tool name that was executed */
  tool: string

  /** Success flag */
  success: boolean

  /** Tool result (if successful) */
  result?: unknown

  /** Error message (if failed) */
  error?: string
}
```

---

## Usage Guide

### Basic Pattern

```typescript
import { onMounted, onUnmounted } from 'vue'
import { ihmController } from '@/services/ihmControllerService'
import type { ToolSchema } from '@/types/ihmController'

// 1. Define tool schema (OpenAPI-style)
const myToolSchema: ToolSchema = {
  name: 'myTool',
  description: 'Description for AI agents',
  parameters: {
    type: 'object',
    properties: {
      param1: {
        type: 'string',
        description: 'Parameter description',
      },
    },
    required: ['param1'],
  },
}

// 2. Define handler
const myToolHandler = async (params: { param1: string }) => {
  // Execute tool logic
  console.log('Tool called with:', params.param1)
  return { success: true }
}

// 3. Register on mount
onMounted(() => {
  ihmController.registerTool(myToolSchema, myToolHandler)
})

// 4. Unregister on unmount
onUnmounted(async () => {
  await ihmController.unregisterTool('myTool')
})
```

### Real-World Example: Chart Control

**Location**: `frontend/src/components/TraderChartContainer.vue`

```typescript
import { ihmController } from '@/services/ihmControllerService'
import type { ToolSchema } from '@/types/ihmController'

// Tool schema with validation rules
const displayStockChartSchema: ToolSchema = {
  name: 'displayStockChart',
  description: 'Display stock chart. Use for "show AAPL chart" or "plot TSLA".',
  parameters: {
    type: 'object',
    properties: {
      symbol: {
        type: 'string',
        description: 'Stock ticker symbol (e.g., "AAPL", "TSLA")',
        pattern: '^[A-Z]{1,5}$', // Regex validation
      },
      timeframe: {
        type: 'string',
        description: 'Chart interval',
        enum: ['1', '5', '15', '60', '1D', '1W', '1M'], // Allowed values
        default: '1D',
      },
    },
    required: ['symbol'], // symbol is required, timeframe is optional
  },
}

// Handler with type-safe parameters
const displayStockChartHandler = async (params: { symbol: string; timeframe?: string }) => {
  if (!chartWidget) {
    throw new Error('Chart not ready')
  }

  // Use TradingView API to change symbol
  await new Promise<void>((resolve) => {
    chartWidget.setSymbol(params.symbol, (params.timeframe || '1D') as ResolutionString, () => {
      console.log(`[Chart] Switched to ${params.symbol} ${params.timeframe}`)
      resolve()
    })
  })
}

// Register when chart is ready (not on mount!)
chartWidget.onChartReady(() => {
  ihmController.registerTool(displayStockChartSchema, displayStockChartHandler)
})

// Cleanup on unmount
onUnmounted(async () => {
  await ihmController.unregisterTool('displayStockChart')
})
```

**Key Points:**

1. ✅ **Register when ready**: Register tool when chart is ready, not on mount
2. ✅ **Type-safe params**: Use TypeScript generics for type safety
3. ✅ **Error handling**: Throw errors - service will send error response automatically
4. ✅ **Async handlers**: Handlers are always async (return Promise)
5. ✅ **Cleanup**: Always unregister on unmount to prevent memory leaks

---

## API Reference

### IHMControllerService

**Location**: `frontend/src/services/ihmControllerService.ts`

#### `getInstance(): IHMControllerService`

Get singleton instance.

```typescript
import { IHMControllerService } from '@/services/ihmControllerService'

const controller = IHMControllerService.getInstance()
```

Or use the exported singleton:

```typescript
import { ihmController } from '@/services/ihmControllerService'
```

#### `registerTool<TParams, TResult>(schema: ToolSchema, handler: ToolHandler<TParams, TResult>): void`

Register a component tool with the IHM Controller.

**Parameters:**

- `schema`: OpenAPI-style tool description
- `handler`: Async function to execute when tool is invoked

**Behavior:**

1. Checks if WebSocket tools client is available
2. If available: Creates WebSocket subscription with schema as params
3. If unavailable: Logs warning and stores schema only (graceful degradation)
4. Stores tool schema in registry

**Example:**

```typescript
ihmController.registerTool(
  {
    name: 'setTheme',
    description: 'Change UI theme',
    parameters: {
      type: 'object',
      properties: {
        theme: {
          type: 'string',
          enum: ['light', 'dark'],
          description: 'Theme name',
        },
      },
      required: ['theme'],
    },
  },
  async (params: { theme: string }) => {
    document.documentElement.classList.toggle('dark', params.theme === 'dark')
  },
)
```

#### `unregisterTool(toolName: string): Promise<void>`

Unregister a tool and clean up its WebSocket subscription.

**Parameters:**

- `toolName`: Name of the tool to unregister

**Behavior:**

1. Unsubscribes from WebSocket (if client available)
2. Removes tool from registry
3. Logs completion

**Example:**

```typescript
await ihmController.unregisterTool('displayStockChart')
```

#### `getRegisteredTools(): RegisteredTool[]`

Get all registered tools (schemas + handlers) for debugging/inspection.

**Returns:**

- Array of `RegisteredTool` objects with structure:
  ```typescript
  interface RegisteredTool {
    schema: ToolSchema // Tool name, description, parameters
    handler: ToolHandler<any, any> // Actual handler function
  }
  ```

**Example:**

```typescript
const tools = ihmController.getRegisteredTools()

// List tool names
console.log(`Registered tools: ${tools.map((t) => t.schema.name).join(', ')}`)

// Invoke a handler directly (useful for browser console testing)
const chartTool = tools.find((t) => t.schema.name === 'displayStockChart')
if (chartTool) {
  await chartTool.handler({ symbol: 'AAPL', timeframe: '1D' })
}
```

---

## Testing

### Unit Tests

**Location**: `frontend/src/services/__tests__/ihmControllerService.spec.ts`

```bash
# Run IHM Controller service tests
npm run test:unit -- ihmControllerService

# Run all service tests
npm run test:unit -- services
```

**Test Coverage:**

- ✅ Singleton pattern
- ✅ Tool registration/unregistration
- ✅ WebSocket integration (mocked)
- ✅ Handler execution and response sending
- ✅ Error handling
- ✅ Graceful degradation when backend unavailable

### Component Integration Tests

**Location**: `frontend/src/components/__tests__/TraderChartContainer.spec.ts`

```bash
# Run component integration tests
npm run test:unit -- TraderChartContainer
```

**Test Coverage:**

- ✅ Tool registration on chart ready
- ✅ Tool unregistration on component unmount
- ✅ Correct schema structure with required parameters

---

## Current State & Roadmap

### ✅ Completed (v1.0.0)

- [x] Frontend service implementation
- [x] Type definitions with comprehensive JSDoc
- [x] WebSocket integration (placeholder mode)
- [x] Component integration example (TraderChartContainer)
- [x] Unit tests (7 tests, all passing)
- [x] Component integration tests (3 tests, all passing)
- [x] Documentation (this file + services README)
- [x] Graceful degradation when backend unavailable

### ⚠️ Pending

- [ ] Backend IHM module implementation
- [ ] AsyncAPI spec generation for IHM module
- [ ] Generated WebSocket types (replace placeholders)
- [ ] Backend integration tests
- [ ] AI agent integration examples

### 🔮 Future Enhancements (v2.0)

- [ ] Runtime parameter validation (JSON Schema validation)
- [ ] Tool discovery API (introspection endpoint)
- [ ] Tool versioning support
- [ ] Permission/authorization for tool execution
- [ ] Tool execution history/logging
- [ ] Rate limiting per tool
- [ ] Tool execution metrics (success rate, latency)

---

## Backend Integration (When Ready)

### Step 1: Create Backend IHM Module

```
backend/src/trading_api/modules/ihm/
├── __init__.py              # Module registration
├── service.py               # IHMService (WsRouteService)
├── ws.py                    # WebSocket router factory
├── models.py                # Pydantic models
└── tests/
    └── test_ws_ihm.py       # Integration tests
```

### Step 2: Generate AsyncAPI Spec

```bash
cd backend
make generate-asyncapi-specs
```

### Step 3: Generate Frontend Types

```bash
cd frontend
make generate-asyncapi-types
```

### Step 4: Enable WebSocket Client

Update `frontend/src/plugins/wsAdapter.ts`:

```typescript
// Replace placeholder
const ihmWsUrl = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + '/v1/ihm/ws'
this.tools = new WebSocketClient<ToolCommandRequest, ToolCommandData>(
  ihmWsUrl,
  'ihm-command',
  (data) => data,
)
```

### Step 5: Replace Placeholder Types

Replace placeholder types in `wsAdapter.ts` with generated types from:

```typescript
import type { ToolCommandRequest, ToolCommandData } from '@/clients_generated/ws-types-ihm_v1'
```

---

## Manual Testing (Browser Console)

You can test the IHM Controller Service directly from the browser console to verify it's working correctly.

### Step 1: Access the Service

Open browser DevTools (F12) and in the Console:

```javascript
// Import the service (if using dev mode with HMR)
// The service is a singleton, so you can access it directly
const { ihmController } = await import('/src/services/ihmControllerService.ts')

// Or if you exposed it globally (recommended for testing)
// Add to your main.ts: window.ihmController = ihmController
const controller = window.ihmController
```

**Recommended**: Expose service globally for testing by adding to `main.ts`:

```typescript
import { ihmController } from '@/services/ihmControllerService'

// Development only - expose for console testing
if (import.meta.env.DEV) {
  window.ihmController = ihmController
}
```

Then declare in `env.d.ts`:

```typescript
declare global {
  interface Window {
    ihmController?: typeof ihmController
  }
}
```

### Step 2: Check Registered Tools

```javascript
// List all registered tools
const tools = window.ihmController.getRegisteredTools()
console.table(
  tools.map((t) => ({
    name: t.schema.name,
    description: t.schema.description,
    hasHandler: !!t.handler,
  })),
)

// Expected output (if TraderChartContainer is mounted):
// [
//   {
//     name: 'displayStockChart',
//     description: 'Display stock chart. Use for "show AAPL chart" or "plot TSLA".',
//     hasHandler: true
//   }
// ]

// Full tool structure
console.log('Tool details:', tools[0])
// {
//   schema: { name, description, parameters },
//   handler: async function(params) { ... }
// }
```

### Step 3: Register a Test Tool

```javascript
// Define a simple test tool
const testToolSchema = {
  name: 'consoleTest',
  description: 'Test tool for console debugging',
  parameters: {
    type: 'object',
    properties: {
      message: {
        type: 'string',
        description: 'Message to log',
      },
      count: {
        type: 'number',
        description: 'Number of times to log',
        default: 1,
      },
    },
    required: ['message'],
  },
}

const testToolHandler = async (params) => {
  for (let i = 0; i < (params.count || 1); i++) {
    console.log(`[Test Tool] ${params.message}`)
  }
  return { logged: params.count || 1 }
}

// Register the tool
window.ihmController.registerTool(testToolSchema, testToolHandler)

// Check it was registered
console.log(
  'Registered tools:',
  window.ihmController.getRegisteredTools().map((t) => t.schema.name),
)
// Expected: ['displayStockChart', 'consoleTest']
```

### Step 4: Test Tool Handler Directly

Now you can invoke the handler directly to test it:

```javascript
// Get the registered tool
const tools = window.ihmController.getRegisteredTools()
const testTool = tools.find((t) => t.schema.name === 'consoleTest')

if (testTool) {
  // Invoke the handler directly
  const result = await testTool.handler({ message: 'Hello from console!', count: 3 })
  console.log('Handler result:', result)

  // Expected console output:
  // [Test Tool] Hello from console!
  // [Test Tool] Hello from console!
  // [Test Tool] Hello from console!
  // Handler result: { logged: 3 }
}
```

### Step 5: Test Chart Tool (Real Example)

Test the actual displayStockChart tool handler:

```javascript
// Find the chart tool
const tools = window.ihmController.getRegisteredTools()
const chartTool = tools.find((t) => t.schema.name === 'displayStockChart')

if (chartTool) {
  console.log('Chart tool schema:', chartTool.schema)

  // IMPORTANT: The chart must be fully loaded first!
  // Check if TradingView chart is ready
  if (!window.tradingViewChart) {
    console.error('❌ Chart widget not loaded yet. Wait for chart to appear on screen.')
  } else {
    // Test the handler directly - this will actually change the chart!
    try {
      await chartTool.handler({ symbol: 'TSLA', timeframe: '1H' })
      console.log('✅ Chart changed to TSLA 1H')
    } catch (error) {
      console.error('❌ Handler failed:', error.message)
      console.log('💡 Make sure the chart is fully loaded before calling the handler')
    }
  }
}
```

**Common Issues:**

- **"Chart not ready" error**: The TradingView widget hasn't finished loading yet. Wait a few seconds and try again.
- **Chart doesn't change**: Check `window.tradingViewChart` exists before calling handler
- **Handler not found**: Make sure you're on a page with `TraderChartContainer` component mounted

### Step 6: Verify Console Output

After registration, you should see:

```
[IHMController] Registering tool: consoleTest
[IHMController] Tools client not available - tool registration skipped: consoleTest
```

### Step 6: Verify Console Output

After registration, you should see:

```
[IHMController] Registering tool: consoleTest
[IHMController] Tools client not available - tool registration skipped: consoleTest
```

This is **expected** because the backend IHM module isn't running yet. The tool is still registered in the local registry.

### Step 7: Test Tool Unregistration

```javascript
// Unregister the test tool
await window.ihmController.unregisterTool('consoleTest')

// Verify it was removed
const remainingTools = window.ihmController.getRegisteredTools()
console.log(
  'Remaining tools:',
  remainingTools.map((t) => t.schema.name),
)
// Expected: ['displayStockChart'] (if chart is still mounted)
```

### Expected Console Output (Full Flow)

```
[IHMController] Registering tool: consoleTest
[IHMController] Tools client not available - tool registration skipped: consoleTest
Registered tools: ['displayStockChart', 'consoleTest']

[Test Tool] Hello from console!
[Test Tool] Hello from console!
[Test Tool] Hello from console!
Handler result: { logged: 3 }

✅ Chart changed to TSLA 1H

[IHMController] Unregistering tool: consoleTest
[IHMController] Tool unregistered: consoleTest
Remaining tools: ['displayStockChart']
```

```
[IHMController] Registering tool: consoleTest
[IHMController] Tools client not available - tool registration skipped: consoleTest
Registered tools: ['displayStockChart', 'consoleTest']

✅ Chart tool schema validation passed

[IHMController] Unregistering tool: consoleTest
[IHMController] Tool unregistered: consoleTest
Remaining tools: ['displayStockChart']
```

### Testing with Backend (When Available)

Once the backend IHM module is ready:

```javascript
// 1. Check WebSocket client is available
console.log('WsAdapter tools client:', window.ihmController.wsAdapter?.tools)
// Should show WebSocket client instance, not undefined

// 2. Register tool - should create WebSocket subscription
window.ihmController.registerTool(testToolSchema, testToolHandler)
// Expected: [IHMController] Tool registered: consoleTest (no warning)

// 3. Backend can now send commands via WebSocket
// The handler will be invoked automatically
// You'll see: [IHMController] Executing tool: consoleTest
```

### Quick Test Script

Copy-paste this into browser console for quick testing:

```javascript
// Quick IHM Controller Test
;(async () => {
  const ctrl = window.ihmController

  if (!ctrl) {
    console.error('❌ ihmController not exposed globally. Add to main.ts:')
    console.log('window.ihmController = ihmController')
    return
  }

  console.log('✅ IHM Controller found')

  const tools = ctrl.getRegisteredTools()
  console.log(`📦 ${tools.length} tool(s) registered:`)
  tools.forEach((t) => console.log(`  - ${t.schema.name}: ${t.schema.description}`))

  // Test registration
  const testSchema = {
    name: 'browserTest',
    description: 'Browser console test',
    parameters: {
      type: 'object',
      properties: { msg: { type: 'string', description: 'Test message' } },
      required: ['msg'],
    },
  }

  const testHandler = async (params) => {
    console.log(`🧪 Test executed with: ${params.msg}`)
    return { echo: params.msg }
  }

  ctrl.registerTool(testSchema, testHandler)
  console.log('✅ Test tool registered')

  // Test handler directly
  const testTool = ctrl.getRegisteredTools().find((t) => t.schema.name === 'browserTest')
  if (testTool) {
    const result = await testTool.handler({ msg: 'Hello from test!' })
    console.log('✅ Handler executed, result:', result)
  }

  // Cleanup
  await ctrl.unregisterTool('browserTest')
  console.log('✅ Test tool unregistered')

  console.log('🎉 IHM Controller is working correctly!')
})()
```

---

## Troubleshooting

### Tools client not available

**Symptom:**

```
[IHMController] Tools client not available - tool registration skipped: displayStockChart
```

**Cause:** Backend IHM module not running or `wsAdapter.tools` not initialized

**Resolution:**

- This is normal during development
- Backend module not required yet
- Tools are registered in registry but won't receive WebSocket commands

### Tool registration fails

**Symptom:**

```
[IHMController] Failed to register tool: displayStockChart
```

**Cause:** WebSocket subscription error

**Resolution:**

- Check backend WebSocket availability
- Verify schema validity
- Check browser console for WebSocket connection errors

### Handler throws error

**Symptom:**

```
[IHMController] Tool execution failed: displayStockChart
Error: Chart not ready
```

**Expected Behavior:** Service automatically catches errors and sends error response to backend

**Resolution:**

- This is working as designed
- External service will receive error response
- Add defensive checks in handler (e.g., check if `chartWidget` exists)

### "Chart not ready" error when testing in console

**Symptom:**

```javascript
displayStockChart.handler({ symbol: 'MSFT' })
// Uncaught (in promise) Error: Chart not ready
```

**Cause:** TradingView widget hasn't finished initializing when you call the handler

**Resolution:**

```javascript
// 1. Wait for chart to load (check global widget reference)
if (!window.tradingViewChart) {
  console.error('Chart not loaded yet. Wait a few seconds and try again.')
} else {
  // 2. Now safe to call handler
  const tools = window.ihmController.getRegisteredTools()
  const chartTool = tools.find((t) => t.schema.name === 'displayStockChart')
  await chartTool.handler({ symbol: 'MSFT' })
  console.log('✅ Chart changed to MSFT')
}
```

**Prevention:**

- Always check `window.tradingViewChart` exists before calling chart-related handlers
- Wait for page to fully load before testing tools
- Tools invoked via WebSocket will work correctly (component handles initialization)

---

## Best Practices

### ✅ DO

- **Register when ready**: Register tools when underlying resource is ready (e.g., chart loaded), not on mount
- **Use TypeScript generics**: Type-safe handlers with `ToolHandler<TParams, TResult>`
- **Throw errors**: Let service handle error response formatting
- **Validate in schema**: Use `pattern`, `enum`, `required` for validation
- **Cleanup on unmount**: Always unregister tools to prevent memory leaks
- **Document parameters**: Add clear descriptions for AI agent consumption

### ❌ DON'T

- **Don't register on mount**: Wait for resources to be ready
- **Don't catch errors silently**: Throw errors - service will send error response
- **Don't use `any` types**: Use proper TypeScript types for params and results
- **Don't forget cleanup**: Memory leaks if tools not unregistered
- **Don't skip descriptions**: AI agents need good descriptions to use tools correctly

---

## Related Documentation

- **[Services README](../src/services/README.md)** - Service layer overview with IHM Controller section
- **[WebSocket Architecture](./WEBSOCKET-ARCHITECTURE.md)** - WebSocket patterns and client implementation
- **[Type Definitions](../src/types/ihmController.ts)** - TypeScript types with JSDoc
- **[Service Implementation](../src/services/ihmControllerService.ts)** - Full source code
- **[Component Example](../src/components/TraderChartContainer.vue)** - Real-world usage

---

## License

This feature is part of Trader Pro and follows the project's license terms.
