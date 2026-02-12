---
name: tradingview-api
description: TradingView Trading Terminal API patterns and type conventions. Load when implementing broker/datafeed or TV integration
keywords: [tradingview, api, charting, broker-integration, widget]
category: tradingview
disable-model-invocation: true
---

# TradingView API Integration

Routes to the correct TradingView interface, type, and documentation for feature implementation tasks. Provides quick-reference patterns and critical pitfalls for the forked Trading Terminal (TT v28.3.0, no vendor support).

---

## When to Use This Skill

- Implementing or extending broker service methods (orders, positions, executions)
- Implementing or extending datafeed service (bars, quotes, symbol resolution)
- Configuring widget options in `TraderChartContainer.vue`
- Working with TradingView type definitions (`.d.ts` files)
- Adding type mappers between backend and TradingView types
- Debugging type mismatches or silent failures in TV callbacks

---

## Architecture Quick Reference

```
Backend (Pydantic) → OpenAPI Specs → Generated TS Clients → Mappers → TV Types → Services → Widget
```

| Layer | Files | Responsibility |
|-------|-------|----------------|
| **Widget** | `TraderChartContainer.vue` | Initializes `widget()`, wires broker + datafeed |
| **Broker Service** | `brokerTerminalService.ts` (~1,200 lines) | Implements `IBrokerWithoutRealtime` |
| **Datafeed Service** | `datafeedService.ts` (~620 lines) | Implements `IBasicDataFeed` + `IDatafeedQuotesApi` |
| **Mappers** | `mappers.ts` (~210 lines) | Backend ↔ TradingView type conversion |
| **API Adapter** | `apiAdapter.ts` | REST client wrapper |
| **WS Adapter** | `wsAdapter.ts` | WebSocket client wrapper |

**Isolation rule**: Services use ONLY TradingView types. Mappers handle ALL conversions at boundaries.

---

## Task → Interface Routing

| Task | Interface to Implement | Key Methods | Primary Doc |
|------|----------------------|-------------|-------------|
| Place/modify/cancel orders | `IBrokerWithoutRealtime` | `placeOrder()`, `modifyOrder()`, `cancelOrder()` | BROKER-INTEGRATION.md |
| Push updates TO widget | `IBrokerConnectionAdapterHost` | `orderUpdate()`, `positionUpdate()`, `executionUpdate()` | BROKER-CONNECTION-ADAPTER.md |
| Serve historical bars | `IBasicDataFeed` | `getBars()`, `resolveSymbol()`, `onReady()` | TYPE-DEFINITIONS.md |
| Stream live quotes | `IDatafeedQuotesApi` | `getQuotes()`, `subscribeQuotes()` | TYPE-DEFINITIONS.md |
| Stream live bars | `IBasicDataFeed` | `subscribeBars()`, `unsubscribeBars()` | TYPE-DEFINITIONS.md |
| Create reactive values | `host.factory` | `createWatchedValue()`, `createDelegate()` | BROKER-CONNECTION-ADAPTER.md |
| Show dialogs/notifications | `IBrokerConnectionAdapterHost` | `showNotification()`, `showOrderDialog()` | BROKER-CONNECTION-ADAPTER.md |
| Configure widget | `TradingTerminalWidgetOptions` | `broker_factory`, `datafeed`, `customUI` | TraderChartContainer.vue |

---

## Import Conventions

```typescript
// Chart/datafeed types — use @public/trading_terminal/charting_library
import type {
  Bar, LibrarySymbolInfo, ResolutionString,
  TradingTerminalWidgetOptions, IChartingLibraryWidget,
} from '@public/trading_terminal/charting_library'

// Broker/trading types — use @public/trading_terminal
import type {
  IBrokerConnectionAdapterHost, IBrokerWithoutRealtime,
  Order, Position, Execution, PreOrder, Brackets,
} from '@public/trading_terminal'

// Enums (value imports, not type-only)
import { OrderStatus, OrderType, Side, ConnectionStatus } from '@public/trading_terminal'
```

**Mapper naming convention** (enforced in `mappers.ts`):
```typescript
import type { PreOrder as PreOrder_Api_Backend } from '@clients/trader-client-broker_v1'
import type { PlacedOrder as PlacedOrder_Ws_Backend } from '@clients/ws-types-broker_v1'
// Suffix format: {TypeName}_{Source}_{Layer} → e.g., PreOrder_Api_Backend
```

---

## Critical Pitfalls

### 1. Time Format: Seconds, NOT Milliseconds
```typescript
// ❌ WRONG
const bar: Bar = { time: Date.now(), ... }
// ✅ CORRECT
const bar: Bar = { time: Math.floor(Date.now() / 1000), ... }
```

### 2. Nullish Fields Break Discriminated Unions
TradingView uses **key presence** for structural typing. Null keys cause silent failures:
```typescript
// ❌ WRONG — parentId key EXISTS → TradingView treats as BracketOrder
const order = { id: '123', symbol: 'AAPL', parentId: null, parentType: null }

// ✅ CORRECT — use omitNullish() before passing to TV host methods
import { omitNullish } from './brokerTerminalService'
host.orderUpdate(omitNullish(order) as Order)
```
Affected unions: `Order = PlacedOrder | BracketOrder` (parentId, parentType)

### 3. Bracket Pre-Population
Position dialogs receive **empty brackets** from `showPositionDialog`. Enrich manually:
```typescript
// Fetch bracket orders linked to position, build { stopLoss, takeProfit }
// See TraderChartContainer.vue customUI.showPositionDialog hook
```

### 4. LibrarySymbolInfo — All Required Fields
Missing fields cause silent rendering failures. Always provide: `name`, `description`, `type`, `session`, `timezone`, `ticker`, `exchange`, `listed_exchange`, `format`, `minmov`, `pricescale`.

---

## Type Definition Files

| File | Lines | Contents |
|------|-------|----------|
| `charting_library.d.ts` | ~29,000 | Widget, chart, UI, configuration types |
| `broker-api.d.ts` | ~2,600 | Broker, order, position, execution types |
| `datafeed-api.d.ts` | ~1,100 | Datafeed, bar, symbol info types |

Location: `frontend/public/trading_terminal/`

---

## External References

- **API Reference**: https://www.tradingview.com/charting-library-docs/latest/api/
- **Trading Concepts**: https://www.tradingview.com/charting-library-docs/latest/trading_terminal/trading-concepts/
- **Datafeed API**: https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
- **Tutorials**: https://www.tradingview.com/charting-library-docs/latest/tutorials/

---

## Resources

Detailed documentation (read when needed, not upfront):

- [TYPE-DEFINITIONS.md](../../../../frontend/docs/tradingview/TYPE-DEFINITIONS.md) — Full type reference with examples
- [BROKER-CONNECTION-ADAPTER.md](../../../../frontend/docs/tradingview/BROKER-CONNECTION-ADAPTER.md) — Trading Host API (~2,000 lines)
- [BROKER-INTEGRATION.md](../../../../frontend/docs/BROKER-INTEGRATION.md) — Complete broker integration guide (~1,800 lines)
- [UI-USAGE-GUIDE.md](../../../../frontend/docs/tradingview/UI-USAGE-GUIDE.md) — Playwright-based UI interaction patterns
- [tradingview/README.md](../../../../frontend/docs/tradingview/README.md) — Documentation index
