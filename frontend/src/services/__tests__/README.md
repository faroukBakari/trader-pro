# Services Testing Guide

**Version**: 2.0.1  
**Last Updated**: November 11, 2025  
**Status**: ✅ Current - Includes WebSocket Integration Tests

## Overview

This guide covers testing strategies for all services in the Trading Pro frontend, including REST API services, WebSocket clients, and broker integration services.

---

## ApiService Tests

### Overview

Comprehensive tests for the `ApiService` class that leverage its built-in fallback mechanism instead of requiring mocks.

### Test Coverage

#### Core Functionality Tests

- **Health Status Endpoint** (`getHealthStatus()`)
  - Response structure validation
  - Consistency across multiple calls
  - Performance/timing validation
  - Concurrent request handling

- **API Versions Endpoint** (`getAPIVersions()`)
  - Response structure validation
  - Version information integrity
  - Current version consistency
  - Performance/timing validation

- **Client Type Detection** (`getClientType()`)
  - Valid return values ('server', 'mock', 'unknown')
  - Consistency across calls
  - Synchronous behavior validation

#### Integration Tests

- Cross-endpoint consistency (health.api_version === versions.current_version)
- Client type and response correlation
- Multiple service instance independence

#### Resilience Tests

- Rapid successive API calls
- Mixed sequential/parallel call patterns
- Service integrity after client type checks

#### Response Validation Tests

- Interface compliance (`HealthResponse`, `APIMetadata`)
- Required vs optional field validation
- Type safety verification

### Key Features

#### No Mocking Required

The tests work directly with the `ApiService` and its fallback mechanism:

- Uses real `TraderPlugin` with fallback to `FallbackApiService`
- Tests both successful fallback behavior and actual API structure
- Leverages built-in mock delays and realistic responses

#### Comprehensive Coverage

- 20 test cases covering all public methods
- Edge cases and error conditions
- Performance and timing validation
- Response structure validation

---

## WebSocket Integration Tests

### Overview

WebSocket integration tests validate the broker WebSocket client integration with TradingView Trading Terminal. These tests follow **TDD (Test-Driven Development)** patterns and are currently in the **Red Phase** (failing until backend broadcasting is implemented).

### Test Coverage

#### Order WebSocket Tests

Tests for real-time order updates via WebSocket:

\`\`\`typescript
describe('BrokerTerminalService - Order WebSocket Integration', () => {
let broker: BrokerTerminalService
let mockHost: IBrokerConnectionAdapterHost
const orderUpdates: Order[] = []

beforeEach(() => {
mockHost = {
orderUpdate: vi.fn((order) => orderUpdates.push(order)),
positionUpdate: vi.fn(),
executionUpdate: vi.fn(),
equityUpdate: vi.fn(),
connectionStatusUpdate: vi.fn(),
showNotification: vi.fn(),
factory: {
createWatchedValue: vi.fn((val) => ({
setValue: vi.fn(),
value: () => val
})),
},
} as any

    broker = new BrokerTerminalService(mockHost, mockQuotesProvider)

})

it('should receive order update after placing order', async () => {
// Place order via REST
await broker.placeOrder({
symbol: 'AAPL',
type: OrderType.Market,
side: Side.Buy,
qty: 100
})

    // Wait for WebSocket update
    await new Promise(resolve => setTimeout(resolve, 2000))

    // Verify orderUpdate was called
    expect(orderUpdates.length).toBe(1)
    expect(orderUpdates[0].symbol).toBe('AAPL')
    expect(orderUpdates[0].status).toBe(OrderStatus.Working)

})
})
\`\`\`

#### Position WebSocket Tests

Tests for real-time position updates:

\`\`\`typescript
it('should receive position update after order fill', async () => {
const positionUpdates: Position[] = []
mockHost.positionUpdate = vi.fn((pos) => positionUpdates.push(pos))

// Place and wait for fill
await broker.placeOrder({
symbol: 'AAPL',
type: OrderType.Market,
side: Side.Buy,
qty: 100
})

await new Promise(resolve => setTimeout(resolve, 3000))

// Verify position created
expect(positionUpdates.length).toBeGreaterThan(0)
expect(positionUpdates[0].symbol).toBe('AAPL')
expect(positionUpdates[0].qty).toBe(100)
})
\`\`\`

#### Execution WebSocket Tests

Tests for trade execution updates:

\`\`\`typescript
it('should receive execution update when order fills', async () => {
const executions: Execution[] = []
mockHost.executionUpdate = vi.fn((exec) => executions.push(exec))

await broker.placeOrder({
symbol: 'AAPL',
type: OrderType.Market,
side: Side.Buy,
qty: 100
})

await new Promise(resolve => setTimeout(resolve, 3000))

expect(executions.length).toBe(1)
expect(executions[0].symbol).toBe('AAPL')
expect(executions[0].qty).toBe(100)
expect(executions[0].side).toBe(Side.Buy)
})
\`\`\`

#### Equity WebSocket Tests

Tests for real-time equity updates:

\`\`\`typescript
it('should receive equity updates', async () => {
const equityUpdates: number[] = []
mockHost.equityUpdate = vi.fn((equity) => equityUpdates.push(equity))

// Subscribe to equity updates
broker.subscribeEquity()

await new Promise(resolve => setTimeout(resolve, 2000))

expect(equityUpdates.length).toBeGreaterThan(0)
expect(typeof equityUpdates[0]).toBe('number')
})
\`\`\`

#### Connection Status Tests

Tests for broker connection status updates:

\`\`\`typescript
it('should handle connection status updates', async () => {
const statusUpdates: ConnectionStatus[] = []
mockHost.connectionStatusUpdate = vi.fn((status) => statusUpdates.push(status))

// Simulate connection change
// (Backend broadcasts connection status via WebSocket)

await new Promise(resolve => setTimeout(resolve, 1000))

expect(statusUpdates.length).toBeGreaterThan(0)
})
\`\`\`

### WebSocket Test Patterns

#### Mock IBrokerConnectionAdapterHost

Always mock the Trading Host interface with \`vi.fn()\`:

\`\`\`typescript
const mockHost: IBrokerConnectionAdapterHost = {
orderUpdate: vi.fn((order: Order) => {
// Store for assertions
receivedOrders.push(order)
}),
positionUpdate: vi.fn((position: Position) => {
receivedPositions.push(position)
}),
executionUpdate: vi.fn((execution: Execution) => {
receivedExecutions.push(execution)
}),
equityUpdate: vi.fn((equity: number) => {
receivedEquityValues.push(equity)
}),
connectionStatusUpdate: vi.fn((status: ConnectionStatus) => {
currentStatus = status
}),
showNotification: vi.fn(),
factory: {
createWatchedValue: vi.fn((val) => ({
setValue: vi.fn(),
value: () => val,
})),
},
} as any
\`\`\`

#### Wait for WebSocket Updates

WebSocket updates are asynchronous, use appropriate delays:

\`\`\`typescript
// Wait for WebSocket subscription confirmation
await new Promise(resolve => setTimeout(resolve, 500))

// Wait for backend broadcast
await new Promise(resolve => setTimeout(resolve, 2000))

// Or use retry logic
async function waitForUpdate(check: () => boolean, timeout = 5000) {
const start = Date.now()
while (!check() && Date.now() - start < timeout) {
await new Promise(resolve => setTimeout(resolve, 100))
}
}

await waitForUpdate(() => orderUpdates.length > 0)
\`\`\`

#### Test WebSocket Client Selection

Test both mock and real WebSocket clients:

\`\`\`typescript
describe('WebSocket Client Selection', () => {
it('should use mock WebSocket when brokerMock provided', () => {
const broker = new BrokerTerminalService(
mockHost,
mockQuotesProvider,
true // mock = true
)

    // Verify uses WsFallback
    // Internal implementation check

})

it('should use real WebSocket when brokerMock absent', () => {
const broker = new BrokerTerminalService(
mockHost,
mockQuotesProvider,
false // mock = false
)

    // Verify uses WsAdapter
    // Internal implementation check

})
})
\`\`\`

### TDD Status

**Current Phase**: 🔴 **Red Phase** (Tests Fail)

These tests are **expected to fail** until Phase 5 (Backend Broadcasting) is implemented. This is intentional TDD workflow:

1. ✅ **Phase 4 Complete**: Frontend integration, tests written (Red Phase)
2. ⏳ **Phase 5 Pending**: Backend broadcasting implementation (Green Phase)
3. ⏳ **Phase 6 Pending**: Full stack validation and refactoring

**When tests will pass**: After backend implements broadcasting logic in:

- \`backend/src/trading_api/core/broker_service.py\`
- Backend broadcasts order/position/execution/equity updates via WebSocket

---

## Running Tests

### Run All Tests

\`\`\`bash

# Run all service tests

npm run test:unit src/services/**tests**/

# Run all tests

npm run test:unit
\`\`\`

### Run Specific Test Suites

\`\`\`bash

# ApiService tests only

npm run test:unit src/services/**tests**/apiService.spec.ts

# Broker WebSocket integration tests (currently skipped)

npm run test:unit src/services/**tests**/brokerTerminalService.spec.ts

# Datafeed service tests

npm run test:unit src/services/**tests**/datafeedService.spec.ts
\`\`\`

### Run with Coverage

\`\`\`bash
npm run test:unit -- --coverage
\`\`\`

---

## Test Results

### ApiService Tests

- ✅ All 28 tests passing
- ✅ No mocking dependencies
- ✅ Realistic test scenarios using fallback mechanism
- ✅ Fast execution (under 3 seconds for full suite)

### WebSocket Integration Tests

- ⏭️ 10 tests currently skipped (Phase 5 pending)
- 🔴 Expected to fail until backend broadcasting implemented
- ✅ Test infrastructure ready
- ✅ Mock patterns established

---

## Best Practices

### General Testing

1. **No Hard Mocking**: Leverage service fallback mechanisms
2. **Type Safety**: Use proper TypeScript types from TradingView
3. **Realistic Scenarios**: Test actual usage patterns
4. **Async Handling**: Proper async/await and promise handling

### WebSocket Testing

1. **Mock the Host**: Always mock \`IBrokerConnectionAdapterHost\`
2. **Use vi.fn()**: Track callback invocations
3. **Wait for Updates**: Use appropriate delays or retry logic
4. **Test Both Modes**: Mock and real WebSocket clients
5. **Verify Callbacks**: Check host methods are called correctly

### TDD Workflow

1. **Red Phase**: Write failing tests first (current state for WebSocket)
2. **Green Phase**: Implement minimal code to pass tests
3. **Refactor Phase**: Optimize while keeping tests green

---

## References

- **WebSocket Integration**: See `../../../docs/BROKER-WEBSOCKET-INTEGRATION.md`
- **Trading Host API**: See `../../../docs/IBROKERCONNECTIONADAPTERHOST.md`
- **Broker Service**: See `../../../docs/BROKER-TERMINAL-SERVICE.md`
- **WebSocket Clients**: See `../../../../docs/WEBSOCKET-CLIENTS.md`
- **Testing Strategy**: See `../../../../docs/TESTING.md`

---

**Version**: 2.0.1  
**Last Updated**: November 11, 2025  
**Maintained by**: Frontend Team
