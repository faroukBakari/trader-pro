# IBrokerConnectionAdapterHost - Trading Host API Reference

**Version**: 1.0.0  
**Last Updated**: November 11, 2025  
**Type**: Interface (provided by TradingView)  
**Location**: `frontend/public/trading_terminal/charting_library.d.ts`

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Responsibilities](#core-responsibilities)
- [API Reference](#api-reference)
  - [Factory Property](#factory-property)
  - [State Update Methods](#state-update-methods)
  - [UI Helper Methods](#ui-helper-methods)
  - [Formatter Methods](#formatter-methods)
  - [Configuration Methods](#configuration-methods)
  - [Visibility Methods](#visibility-methods)
  - [Account Manager Methods](#account-manager-methods)
- [Usage Patterns](#usage-patterns)
- [Best Practices](#best-practices)
- [Common Scenarios](#common-scenarios)
- [Integration with Broker API](#integration-with-broker-api)
- [References](#references)

---

## Overview

`IBrokerConnectionAdapterHost` is the **Trading Host** interface provided by TradingView. It serves as the **primary communication channel** from your Broker API implementation back to the TradingView library.

### Purpose

- **Push Updates**: Send real-time updates from your backend to the TradingView UI
- **Factory Access**: Create library-compatible reactive values and formatters
- **UI Integration**: Display dialogs, notifications, and manage UI state
- **Configuration**: Update broker configuration and settings dynamically

### Key Characteristics

- 🔄 **Bidirectional**: Complements `IBrokerWithoutRealtime` (library → you) with updates (you → library)
- 📡 **Event-Driven**: Notify the library of state changes it didn't request
- 🏭 **Factory Pattern**: Provides factory methods for creating library-compatible objects
- 🎨 **UI Access**: Methods to show dialogs, notifications, and manage UI visibility
- ⚙️ **Configuration**: Dynamic broker configuration updates

### Terminology

| Term             | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| **Trading Host** | The `IBrokerConnectionAdapterHost` interface                      |
| **Broker API**   | Your implementation of `IBrokerWithoutRealtime`/`IBrokerTerminal` |
| **Library**      | TradingView Charting Library / Trading Terminal                   |
| **Backend**      | Your trading server/API                                           |

---

## Architecture

### Component Relationship

```
┌─────────────────────────────────────────────────────────────────┐
│                    TradingView Trading Terminal                 │
│                       (Library Code)                            │
└─────────────────────┬───────────────────────┬───────────────────┘
                      │                       │
                      │ Requests              │ Provides
                      │ (Pull)                │ (Host Instance)
                      ▼                       ▼
            ┌─────────────────────────────────────────────┐
            │   Your Broker API Implementation            │
            │   (IBrokerWithoutRealtime)                  │
            │                                             │
            │   private readonly _host:                   │
            │     IBrokerConnectionAdapterHost            │
            └─────────────────────┬───────────────────────┘
                                  │
                                  │ Updates
                                  │ (Push)
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│               IBrokerConnectionAdapterHost                      │
│                  (Trading Host Methods)                         │
│                                                                 │
│  • orderUpdate()           - Push order changes                │
│  • positionUpdate()        - Push position changes             │
│  • executionUpdate()       - Push trade executions             │
│  • plUpdate()              - Push P&L updates                  │
│  • equityUpdate()          - Push equity updates               │
│  • connectionStatusUpdate() - Update connection state          │
│  • showNotification()      - Display notifications             │
│  • factory.*               - Create reactive values            │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Backend Event → Your Broker API → Trading Host → TradingView UI
     ↓                ↓                 ↓              ↓
Order Filled    orderUpdate()    Host processes    UI updates
                                 the change        automatically
```

### Integration Pattern

```typescript
// TradingView creates your broker and passes the host
broker_factory: function(tradingHost: IBrokerConnectionAdapterHost) {
  // tradingHost is the Trading Host instance
  return new YourBrokerService(tradingHost, datafeed);
}

// Your broker implementation
export class YourBrokerService implements IBrokerWithoutRealtime {
  private readonly _host: IBrokerConnectionAdapterHost;

  constructor(
    host: IBrokerConnectionAdapterHost,
    datafeed: IDatafeedQuotesApi
  ) {
    // Store the host for later use
    this._host = host;

    // Use factory to create reactive values
    this.balance = this._host.factory.createWatchedValue(100000);
    this.equity = this._host.factory.createWatchedValue(100000);
  }

  // When backend sends order update:
  private handleBackendOrderUpdate(order: Order): void {
    // Push update to TradingView
    this._host.orderUpdate(order);
  }
}
```

---

## Core Responsibilities

### 1. Real-Time State Updates

Push updates to the library when your backend state changes:

| Data Type  | Method                    | When to Call                              |
| ---------- | ------------------------- | ----------------------------------------- |
| Orders     | `orderUpdate()`           | Order created, modified, filled, canceled |
| Positions  | `positionUpdate()`        | Position opened, modified, closed         |
| Executions | `executionUpdate()`       | Trade executed                            |
| P&L        | `plUpdate()`              | Position profit/loss changed              |
| Equity     | `equityUpdate()`          | Account equity changed                    |
| Margin     | `marginAvailableUpdate()` | Available margin changed                  |
| Balance    | `cryptoBalanceUpdate()`   | Crypto balance changed                    |

### 2. Factory Access

Create library-compatible objects:

```typescript
// Reactive values (auto-update UI)
const balance = host.factory.createWatchedValue<number>(100000)

// Event delegates
const delegate = host.factory.createDelegate<() => void>()

// Price formatters
const formatter = host.factory.createPriceFormatter(
  100, // priceScale
  1, // minMove
  false, // fractional
  0, // minMove2
  undefined, // variableMinTick
)
```

### 3. UI Management

Display dialogs and manage UI state:

- Show order dialogs
- Display notifications
- Show confirmation dialogs
- Manage Account Manager visibility
- Access trading properties

### 4. Configuration

Update broker settings dynamically:

- Patch configuration flags
- Set order duration options
- Update order ticket settings

---

## API Reference

### Factory Property

#### `factory: IBrokerConnectionAdapterFactory`

Factory object for creating library-compatible types.

**Methods**:

```typescript
interface IBrokerConnectionAdapterFactory {
  // Create reactive value (auto-updates UI)
  createWatchedValue<T>(value?: T): IWatchedValue<T>

  // Create event delegate
  createDelegate<T extends Function>(): IDelegate<T>

  // Create price formatter
  createPriceFormatter(
    priceScale?: number,
    minMove?: number,
    fractional?: boolean,
    minMove2?: number,
    variableMinTick?: string,
  ): IPriceFormatter
}
```

**Example**:

```typescript
// Reactive balance (changes auto-update UI)
this.balance = this._host.factory.createWatchedValue(100000)

// Later, update the value
this.balance.setValue(105000) // UI updates automatically

// Event delegate for notifications
this.orderDelegate = this._host.factory.createDelegate<(order: Order) => void>()
```

---

### State Update Methods

These methods notify TradingView that data has changed.

#### `orderUpdate(order: Order): void`

Call when an order is added or changed.

**When to use**:

- Order placed successfully
- Order status changed (Working → Filled)
- Order modified (price, quantity)
- Order canceled

**Parameters**:

- `order: Order` - Complete order object with all fields

**Example**:

```typescript
async placeOrder(preOrder: PreOrder): Promise<PlaceOrderResult> {
  // Create order
  const order: Order = {
    id: 'ORDER-1',
    symbol: preOrder.symbol,
    status: OrderStatus.Working,
    // ... other fields
  };

  // Notify TradingView
  this._host.orderUpdate(order);

  return { orderId: order.id };
}

// When backend notifies order filled
private onOrderFilled(orderId: string): void {
  const order = this._orders.get(orderId);
  if (order) {
    order.status = OrderStatus.Filled;
    this._host.orderUpdate(order); // UI updates
  }
}
```

**Important**: You **must** call this after `placeOrder()`, `modifyOrder()`, and `cancelOrder()` methods, otherwise the library will timeout.

---

#### `orderPartialUpdate(id: string, orderChanges: Partial<Order>): void`

Call when only specific order fields changed (custom fields).

**When to use**:

- Only custom fields changed (not standard fields like status, price, qty)
- Want to update UI without re-sending entire order object

**Parameters**:

- `id: string` - Order ID
- `orderChanges: Partial<Order>` - Only the changed fields

**Example**:

```typescript
// Custom field update (e.g., commission calculated)
this._host.orderPartialUpdate('ORDER-1', {
  commission: 2.5,
  notes: 'Commission updated',
})
```

---

#### `positionUpdate(position: Position, isHistoryUpdate?: boolean): void`

Call when a position is added or changed.

**When to use**:

- Position opened
- Position quantity changed
- Position average price changed
- Position closed

**Parameters**:

- `position: Position` - Complete position object
- `isHistoryUpdate?: boolean` - Set to `true` for historical updates

**Example**:

```typescript
async closePosition(positionId: string, amount?: number): Promise<void> {
  const position = this._positions.get(positionId);

  if (position) {
    if (amount && amount < position.qty) {
      // Partial close
      position.qty -= amount;
      this._host.positionUpdate(position);
    } else {
      // Full close - remove position
      this._positions.delete(positionId);
      position.qty = 0;
      this._host.positionUpdate(position);
    }
  }
}
```

**Important**: Call this after `closePosition()`, `editPositionBrackets()`, and `reversePosition()` methods.

---

#### `positionPartialUpdate(id: string, positionChanges: Partial<Position>): void`

Call when only specific position fields changed (custom fields).

**When to use**:

- Only custom fields changed
- Want to update UI without re-sending entire position object

**Parameters**:

- `id: string` - Position ID
- `positionChanges: Partial<Position>` - Only the changed fields

---

#### `individualPositionUpdate(individualPosition: IndividualPosition, isHistoryUpdate?: boolean): void`

Call when an individual position is added or changed (for position netting).

**Required if**: `BrokerConfigFlags.supportPositionNetting` is `true`

**Parameters**:

- `individualPosition: IndividualPosition` - Complete individual position object
- `isHistoryUpdate?: boolean` - Set to `true` for historical updates

---

#### `individualPositionPartialUpdate(id: string, changes: Partial<IndividualPosition>): void`

Call when only specific individual position fields changed.

**Parameters**:

- `id: string` - Individual position ID
- `changes: Partial<IndividualPosition>` - Only the changed fields

---

#### `executionUpdate(execution: Execution): void`

Call when a trade execution occurs.

**When to use**:

- Order filled (fully or partially)
- Trade executed on backend

**Parameters**:

- `execution: Execution` - Execution record with price, qty, side, time

**Example**:

```typescript
private onOrderFilled(order: Order): void {
  // Create execution record
  const execution: Execution = {
    symbol: order.symbol,
    price: order.avgPrice || order.limitPrice || 100,
    qty: order.qty,
    side: order.side,
    time: Date.now(),
  };

  // Notify TradingView
  this._host.executionUpdate(execution);
}
```

**Required if**: `BrokerConfigFlags.supportExecutions` is `true`

---

#### `currentAccountUpdate(): void`

Call when the user account has been changed synchronously.

**When to use**:

- User switches accounts
- Account credentials updated

**Effect**: The terminal will re-request all displayed information (orders, positions, executions).

**Example**:

```typescript
async setCurrentAccount(accountId: AccountId): Promise<void> {
  this._currentAccountId = accountId;

  // Trigger full data refresh
  this._host.currentAccountUpdate();
}
```

---

#### `plUpdate(positionId: string, pl: number): void`

Call when a position's profit/loss value changes.

**Required if**: `BrokerConfigFlags.supportPLUpdate` is `true`

**When to use**:

- Real-time P&L calculation based on market prices
- Position mark-to-market updates

**Parameters**:

- `positionId: string` - Position ID
- `pl: number` - Updated profit/loss value

**Example**:

```typescript
private onMarketPriceUpdate(symbol: string, price: number): void {
  const position = this._positions.get(`${symbol}-POS`);

  if (position) {
    // Calculate P&L
    const pl = (price - position.avgPrice) * position.qty * (position.side === Side.Buy ? 1 : -1);

    // Push update
    this._host.plUpdate(position.id, pl);
  }
}
```

---

#### `equityUpdate(equity: number): void`

Call when account equity changes.

**Required for**: Standard Order Ticket risk calculations

**When to use**:

- Balance changes
- P&L updates affecting equity
- Account value updates

**Parameters**:

- `equity: number` - Updated equity value (Balance + Unrealized P&L)

**Example**:

```typescript
subscribeEquity(): void {
  // Start subscribing to equity updates
  this._equitySubscription = setInterval(() => {
    const totalPL = this.calculateTotalPL();
    const equity = this._balance + totalPL;

    this._host.equityUpdate(equity);
  }, 1000);
}
```

**Important**: Library subscribes via `IBrokerWithoutRealtime.subscribeEquity()`.

---

#### `marginAvailableUpdate(marginAvailable: number): void`

Call when available margin changes.

**Required if**: `BrokerConfigFlags.supportMargin` is `true`

**When to use**:

- Margin calculation changes
- Account margin updates

**Parameters**:

- `marginAvailable: number` - Updated available margin

**Example**:

```typescript
subscribeMarginAvailable(symbol: string): void {
  // Subscribe to margin updates for symbol
  this._marginSubscription = setInterval(() => {
    const margin = this.calculateAvailableMargin(symbol);
    this._host.marginAvailableUpdate(margin);
  }, 1000);
}
```

**Important**: Library subscribes via `IBrokerWithoutRealtime.subscribeMarginAvailable()`.

---

#### `cryptoBalanceUpdate(symbol: string, balance: CryptoBalance): void`

Call when cryptocurrency balance changes.

**Required if**: `BrokerConfigFlags.supportBalances` is `true`

**When to use**:

- Crypto balance updates
- Available/reserved balance changes

**Parameters**:

- `symbol: string` - Symbol ID (e.g., "BTC", "ETH")
- `balance: CryptoBalance` - Updated crypto balance

**Example**:

```typescript
interface CryptoBalance {
  symbol: string;
  total: number;
  available: number;
  reserved?: number;
  value?: number;
  valueCurrency?: string;
}

private onCryptoBalanceUpdate(balance: CryptoBalance): void {
  this._host.cryptoBalanceUpdate(balance.symbol, balance);
}
```

---

#### `realtimeUpdate(symbol: string, data: TradingQuotes): void`

Call when real-time trading quotes update.

**When to use**:

- Real-time bid/ask updates
- Quote data changes

**Parameters**:

- `symbol: string` - Symbol identifier
- `data: TradingQuotes` - Updated quote data

---

#### `pipValueUpdate(symbol: string, pipValues: PipValues): void`

Call when pip values update for a symbol.

**When to use**:

- Pip value calculation changes
- Currency conversion rates update

**Parameters**:

- `symbol: string` - Symbol identifier
- `pipValues: PipValues` - Updated pip values

**Example**:

```typescript
interface PipValues {
  // Pip value fields
}

subscribePipValue(symbol: string): void {
  // Calculate and send pip values
  const pipValues = this.calculatePipValues(symbol);
  this._host.pipValueUpdate(symbol, pipValues);
}
```

**Important**: Library subscribes via `IBrokerWithoutRealtime.subscribePipValue()`.

---

#### `domUpdate(symbol: string, data: DOMData): void`

Update Depth of Market data.

**Required if**: `BrokerConfigFlags.supportLevel2Data` is `true`

**Parameters**:

- `symbol: string` - Symbol identifier
- `data: DOMData` - Depth of Market data

---

#### `connectionStatusUpdate(status: ConnectionStatus, info?: DisconnectionInfo): void`

Trigger a connection status update.

**When to use**:

- WebSocket connection lost
- Reconnection established
- Authentication expired

**Parameters**:

- `status: ConnectionStatus` - New connection status (1=Connected, 2=Connecting, 3=Disconnected, 4=Error)
- `info?: DisconnectionInfo` - Additional disconnection details

**Example**:

```typescript
private onWebSocketClose(): void {
  this._host.connectionStatusUpdate(
    ConnectionStatus.Disconnected,
    {
      message: 'WebSocket connection lost',
      disconnectType: DisconnectType.BrokenConnection
    }
  );
}

private onWebSocketOpen(): void {
  this._host.connectionStatusUpdate(ConnectionStatus.Connected);
}
```

**Important**: This re-invokes your `IBrokerCommon.connectionStatus()` method.

---

### UI Helper Methods

#### `showOrderDialog<T extends PreOrder>(order: T, focus?: OrderTicketFocusControl): Promise<boolean>`

Show the standard Order Ticket dialog.

**Parameters**:

- `order: PreOrder` - Order to display/edit
- `focus?: OrderTicketFocusControl` - Control to focus on open

**Returns**: `Promise<boolean>` - `true` if user confirmed, `false` if canceled

**Example**:

```typescript
async showOrderTicket(symbol: string): Promise<void> {
  const order: PreOrder = {
    symbol,
    type: OrderType.Limit,
    side: Side.Buy,
    qty: 100,
  };

  const confirmed = await this._host.showOrderDialog(order, OrderTicketFocusControl.LimitPrice);

  if (confirmed) {
    // User confirmed, place the order
    await this.placeOrder(order);
  }
}
```

---

#### `showNotification(title: string, text: string, notificationType?: NotificationType): void`

Display a notification to the user.

**Parameters**:

- `title: string` - Notification title
- `text: string` - Notification content
- `notificationType?: NotificationType` - Type (Error=0, Success=1)

**Example**:

```typescript
private onOrderPlaced(orderId: string): void {
  this._host.showNotification(
    'Order Placed',
    `Order ${orderId} placed successfully`,
    NotificationType.Success
  );
}

private onOrderFailed(error: string): void {
  this._host.showNotification(
    'Order Failed',
    error,
    NotificationType.Error
  );
}
```

---

#### `showCancelOrderDialog(orderId: string, handler: () => Promise<void>): Promise<void>`

Show cancel order confirmation dialog.

**Parameters**:

- `orderId: string` - Order to cancel
- `handler: () => Promise<void>` - Called if user confirms

**Example**:

```typescript
async requestCancelOrder(orderId: string): Promise<void> {
  await this._host.showCancelOrderDialog(orderId, async () => {
    // User confirmed cancellation
    await this.cancelOrder(orderId);
  });
}
```

---

#### `showCancelMultipleOrdersDialog(symbol: string, side: Side, qty: number, handler: () => Promise<void>): Promise<void>`

Show dialog to cancel multiple orders.

**Parameters**:

- `symbol: string` - Symbol
- `side: Side` - Order side
- `qty: number` - Total quantity
- `handler: () => Promise<void>` - Called if user confirms

---

#### `showCancelBracketsDialog(orderId: string, handler: () => Promise<void>): Promise<void>`

Show cancel brackets confirmation dialog.

**Parameters**:

- `orderId: string` - Order with brackets
- `handler: () => Promise<void>` - Called if user confirms

---

#### `showReversePositionDialog(positionId: string, handler: () => Promise<boolean>): Promise<boolean>`

Show reverse position confirmation dialog.

**Parameters**:

- `positionId: string` - Position to reverse
- `handler: () => Promise<boolean>` - Called if user confirms

**Returns**: `Promise<boolean>` - Result from handler

---

#### `showPositionBracketsDialog(position: Position | IndividualPosition, brackets: Brackets, focus: OrderTicketFocusControl): Promise<boolean>`

Show position brackets (SL/TP) editing dialog.

**Parameters**:

- `position: Position | IndividualPosition` - Position to edit
- `brackets: Brackets` - Current brackets
- `focus: OrderTicketFocusControl` - Control to focus

**Returns**: `Promise<boolean>` - `true` if confirmed

---

#### `showMessageDialog(title: string, text: string, textHasHTML?: boolean): void`

Display a message dialog.

**Parameters**:

- `title: string` - Dialog title
- `text: string` - Message text
- `textHasHTML?: boolean` - Whether text contains HTML

---

#### `showConfirmDialog(title: string, content: string | string[], mainButtonText?: string, cancelButtonText?: string, showDisableConfirmationsCheckbox?: boolean): Promise<boolean>`

Display a confirmation dialog.

**Parameters**:

- `title: string` - Dialog title
- `content: string | string[]` - Dialog content
- `mainButtonText?: string` - Main button text (default: "OK")
- `cancelButtonText?: string` - Cancel button text (default: "Cancel")
- `showDisableConfirmationsCheckbox?: boolean` - Show "Don't show again" checkbox

**Returns**: `Promise<boolean>` - `true` if confirmed

---

#### `showSimpleConfirmDialog(title: string, content: string | string[], mainButtonText?: string, cancelButtonText?: string, showDisableConfirmationsCheckbox?: boolean): Promise<boolean>`

Display a simple confirmation dialog.

**Parameters**: Same as `showConfirmDialog()`

**Returns**: `Promise<boolean>` - `true` if confirmed

---

### Formatter Methods

#### `defaultFormatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter>`

Get default value formatter for a symbol.

**Parameters**:

- `symbol: string` - Symbol identifier
- `alignToMinMove: boolean` - Align to minimum tick size

**Returns**: `Promise<INumberFormatter>` - Formatter for the symbol

---

#### `numericFormatter(decimalPlaces: number): Promise<INumberFormatter>`

Get number formatter with specific decimal places.

**Parameters**:

- `decimalPlaces: number` - Number of decimal places

**Returns**: `Promise<INumberFormatter>` - Formatter

---

#### `quantityFormatter(decimalPlaces?: number): Promise<INumberFormatter>`

Get quantity formatter.

**Parameters**:

- `decimalPlaces?: number` - Number of decimal places

**Returns**: `Promise<INumberFormatter>` - Formatter

---

### Configuration Methods

#### `patchConfig(config: Partial<BrokerConfigFlags>): void`

Update broker configuration flags dynamically.

**Parameters**:

- `config: Partial<BrokerConfigFlags>` - Configuration changes

**Example**:

```typescript
// Enable position brackets after initialization
this._host.patchConfig({
  supportPositionBrackets: true,
  supportOrderBrackets: true,
})
```

---

#### `setDurations(durations: OrderDurationMetaInfo[]): void`

Set order expiration duration options.

**Parameters**:

- `durations: OrderDurationMetaInfo[]` - Duration options

**Example**:

```typescript
this._host.setDurations([
  {
    id: 'DAY',
    name: 'Day',
    default: true,
  },
  {
    id: 'GTC',
    name: 'Good Till Canceled',
  },
  {
    id: 'GTT',
    name: 'Good Till Time',
    hasDatePicker: true,
    hasTimePicker: true,
  },
])
```

---

#### `getOrderTicketSetting<K extends keyof OrderTicketSettings>(settingName: K): Promise<OrderTicketSettings[K]>`

Get current Order Ticket setting value.

**Parameters**:

- `settingName: K` - Setting name

**Returns**: `Promise<OrderTicketSettings[K]>` - Setting value

---

#### `setOrderTicketSetting<K extends keyof OrderTicketSettings>(settingName: K, value: OrderTicketSettings[K]): Promise<void>`

Update Order Ticket setting.

**Parameters**:

- `settingName: K` - Setting name
- `value: OrderTicketSettings[K]` - New value

**Returns**: `Promise<void>`

---

### Visibility Methods

#### `sellBuyButtonsVisibility(): IWatchedValue<boolean> | null`

Get buy/sell buttons visibility state.

**Returns**: `IWatchedValue<boolean> | null` - Reactive visibility state

---

#### `domPanelVisibility(): IWatchedValue<boolean> | null`

Get DOM panel visibility state.

**Returns**: `IWatchedValue<boolean> | null` - Reactive visibility state

---

#### `orderPanelVisibility(): IWatchedValue<boolean> | null`

Get order panel visibility state.

**Returns**: `IWatchedValue<boolean> | null` - Reactive visibility state

---

#### `silentOrdersPlacement(): IWatchedValue<boolean>`

Check if orders can be sent without showing order ticket.

**Returns**: `IWatchedValue<boolean>` - Reactive silent placement state

---

### Account Manager Methods

#### `getAccountManagerVisibilityMode(): IWatchedValueReadonly<BottomWidgetBarMode>`

Get current Account Manager visibility mode.

**Returns**: `IWatchedValueReadonly<BottomWidgetBarMode>` - Current mode (Minimized, Normal, Maximized)

---

#### `setAccountManagerVisibilityMode(mode: BottomWidgetBarMode): void`

Set Account Manager visibility mode.

**Parameters**:

- `mode: BottomWidgetBarMode` - New mode

**Example**:

```typescript
// Show Account Manager in maximized mode
this._host.setAccountManagerVisibilityMode(BottomWidgetBarMode.Maximized)
```

---

#### `activateBottomWidget(): Promise<void>` (Deprecated)

Activate bottom widget (Account Manager).

**⚠️ Deprecated**: Use `setAccountManagerVisibilityMode()` instead.

---

#### `showTradingProperties(): void`

Show trading properties dialog.

---

### Helper Methods

#### `defaultContextMenuActions(context: TradeContext, params?: DefaultContextMenuActionsParams): Promise<ActionMetaInfo[]>`

Get default chart context menu actions (Buy/Sell/Properties).

**Parameters**:

- `context: TradeContext` - Chart context
- `params?: DefaultContextMenuActionsParams` - Optional parameters

**Returns**: `Promise<ActionMetaInfo[]>` - Default actions

**Example**:

```typescript
async chartContextMenuActions(context: TradeContext): Promise<ActionMetaInfo[]> {
  // Return default actions
  return await this._host.defaultContextMenuActions(context);
}
```

---

#### `defaultDropdownMenuActions(options?: Partial<DefaultDropdownActionsParams>): ActionMetaInfo[]`

Get default dropdown menu actions.

**Parameters**:

- `options?: Partial<DefaultDropdownActionsParams>` - Menu options

**Returns**: `ActionMetaInfo[]` - Default dropdown actions

---

#### `getSymbolMinTick(symbol: string): Promise<number>`

Get symbol's minimum tick size.

**Parameters**:

- `symbol: string` - Symbol identifier

**Returns**: `Promise<number>` - Minimum tick size

---

#### `setQty(symbol: string, quantity: number): void`

Set suggested quantity for a symbol.

**Parameters**:

- `symbol: string` - Symbol
- `quantity: number` - Quantity

---

#### `getQty(symbol: string): Promise<number>`

Get suggested quantity for a symbol.

**Parameters**:

- `symbol: string` - Symbol

**Returns**: `Promise<number>` - Quantity

---

#### `subscribeSuggestedQtyChange(symbol: string, listener: SuggestedQtyChangedListener): void`

Subscribe to quantity change notifications.

**Parameters**:

- `symbol: string` - Symbol
- `listener: SuggestedQtyChangedListener` - Callback

---

#### `unsubscribeSuggestedQtyChange(symbol: string, listener: SuggestedQtyChangedListener): void`

Unsubscribe from quantity change notifications.

**Parameters**:

- `symbol: string` - Symbol
- `listener: SuggestedQtyChangedListener` - Callback to remove

---

## Usage Patterns

### Pattern 1: Order Lifecycle Management

```typescript
export class BrokerService implements IBrokerWithoutRealtime {
  private readonly _host: IBrokerConnectionAdapterHost

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    // 1. Create order
    const newOrder: Order = {
      id: this.generateOrderId(),
      ...order,
      status: OrderStatus.Working,
    }

    // 2. Store locally
    this._orders.set(newOrder.id, newOrder)

    // 3. Notify TradingView immediately
    this._host.orderUpdate(newOrder)

    // 4. Send to backend asynchronously
    this.sendOrderToBackend(newOrder).then(() => {
      // 5. Update status when backend confirms
      newOrder.status = OrderStatus.Filled
      this._host.orderUpdate(newOrder)

      // 6. Create execution
      const execution: Execution = {
        symbol: newOrder.symbol,
        price: newOrder.limitPrice || 100,
        qty: newOrder.qty,
        side: newOrder.side,
        time: Date.now(),
      }
      this._host.executionUpdate(execution)

      // 7. Update position
      this.updatePosition(newOrder)
    })

    return { orderId: newOrder.id }
  }
}
```

### Pattern 2: Real-Time Updates via WebSocket

```typescript
export class BrokerService implements IBrokerWithoutRealtime {
  private _websocket: WebSocket

  private connectWebSocket(): void {
    this._websocket = new WebSocket('wss://backend/orders')

    this._websocket.onmessage = (event) => {
      const update = JSON.parse(event.data)

      switch (update.type) {
        case 'ORDER_UPDATE':
          this._host.orderUpdate(update.order)
          break

        case 'POSITION_UPDATE':
          this._host.positionUpdate(update.position)
          break

        case 'EXECUTION':
          this._host.executionUpdate(update.execution)
          break

        case 'PL_UPDATE':
          this._host.plUpdate(update.positionId, update.pl)
          break

        case 'EQUITY_UPDATE':
          this._host.equityUpdate(update.equity)
          break
      }
    }

    this._websocket.onclose = () => {
      this._host.connectionStatusUpdate(ConnectionStatus.Disconnected, {
        message: 'WebSocket disconnected',
      })
    }
  }
}
```

### Pattern 3: Using Factory for Reactive Values

```typescript
export class BrokerService implements IBrokerWithoutRealtime {
  private readonly balance: IWatchedValue<number>
  private readonly equity: IWatchedValue<number>

  constructor(host: IBrokerConnectionAdapterHost) {
    this._host = host

    // Create reactive values using factory
    this.balance = host.factory.createWatchedValue(100000)
    this.equity = host.factory.createWatchedValue(100000)
  }

  accountManagerInfo(): AccountManagerInfo {
    return {
      accountTitle: 'Trading Account',
      summary: [
        {
          text: 'Balance',
          wValue: this.balance, // Reactive - UI auto-updates
          formatter: StandardFormatterName.FixedInCurrency,
        },
        {
          text: 'Equity',
          wValue: this.equity, // Reactive - UI auto-updates
          formatter: StandardFormatterName.FixedInCurrency,
        },
      ],
      // ... rest of config
    }
  }

  // Update values - UI updates automatically
  private onBalanceChange(newBalance: number): void {
    this.balance.setValue(newBalance)
  }

  private onEquityChange(newEquity: number): void {
    this.equity.setValue(newEquity)
  }
}
```

---

## Best Practices

### ✅ Do's

1. **Always call update methods after modifying data**:

   ```typescript
   async modifyOrder(order: Order): Promise<void> {
     // Update local state
     this._orders.set(order.id, order);

     // MUST notify TradingView
     this._host.orderUpdate(order);
   }
   ```

2. **Use reactive values for frequently changing data**:

   ```typescript
   // Good - UI auto-updates
   this.balance = host.factory.createWatchedValue(100000);

   // Bad - manual updates needed
   private _balance: number = 100000;
   ```

3. **Handle connection state changes**:

   ```typescript
   private onConnectionLost(): void {
     this._host.connectionStatusUpdate(
       ConnectionStatus.Disconnected,
       { message: 'Connection lost' }
     );
   }
   ```

4. **Use partial updates for custom fields only**:

   ```typescript
   // Good - only custom fields changed
   this._host.orderPartialUpdate('ORDER-1', { customField: 'value' })

   // Bad - use orderUpdate() for standard fields
   this._host.orderPartialUpdate('ORDER-1', { status: OrderStatus.Filled })
   ```

5. **Show notifications for important events**:
   ```typescript
   private onOrderFilled(orderId: string): void {
     this._host.showNotification(
       'Order Filled',
       `Order ${orderId} executed successfully`,
       NotificationType.Success
     );
   }
   ```

### ❌ Don'ts

1. **Don't forget to call update methods**:

   ```typescript
   // BAD - TradingView won't know order changed
   async cancelOrder(orderId: string): Promise<void> {
     const order = this._orders.get(orderId);
     order.status = OrderStatus.Canceled;
     // Missing: this._host.orderUpdate(order);
   }
   ```

2. **Don't modify objects without notifying**:

   ```typescript
   // BAD - direct mutation without notification
   this._orders.get(orderId).status = OrderStatus.Filled

   // GOOD - update and notify
   const order = this._orders.get(orderId)
   order.status = OrderStatus.Filled
   this._host.orderUpdate(order)
   ```

3. **Don't use partialUpdate for standard fields**:

   ```typescript
   // BAD - use orderUpdate() instead
   this._host.orderPartialUpdate(id, { status: OrderStatus.Filled })

   // GOOD
   order.status = OrderStatus.Filled
   this._host.orderUpdate(order)
   ```

4. **Don't ignore connection status**:

   ```typescript
   // BAD - library will show spinner forever
   connectionStatus(): ConnectionStatus {
     return ConnectionStatus.Connecting; // Always connecting
   }

   // GOOD - update status dynamically
   private updateConnectionStatus(status: ConnectionStatus): void {
     this._connectionStatus = status;
     this._host.connectionStatusUpdate(status);
   }
   ```

---

## Common Scenarios

### Scenario 1: Order Placed and Filled

```typescript
// 1. User places order
async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
  const newOrder: Order = {
    id: 'ORDER-1',
    status: OrderStatus.Working,
    ...order,
  };

  // 2. Notify UI immediately
  this._host.orderUpdate(newOrder);

  // 3. Simulate fill after delay
  setTimeout(() => {
    newOrder.status = OrderStatus.Filled;
    this._host.orderUpdate(newOrder); // UI updates

    // 4. Create execution
    this._host.executionUpdate({
      symbol: order.symbol,
      price: order.limitPrice || 100,
      qty: order.qty,
      side: order.side,
      time: Date.now(),
    });
  }, 3000);

  return { orderId: newOrder.id };
}
```

### Scenario 2: Position Updated from Backend

```typescript
// Backend sends position update via WebSocket
private onWebSocketMessage(data: any): void {
  if (data.type === 'POSITION_UPDATE') {
    const position: Position = {
      id: data.positionId,
      symbol: data.symbol,
      qty: data.quantity,
      side: data.side,
      avgPrice: data.avgPrice,
    };

    // Push update to TradingView
    this._host.positionUpdate(position);
  }
}
```

### Scenario 3: Account Switch

```typescript
async setCurrentAccount(accountId: AccountId): Promise<void> {
  // Update internal state
  this._currentAccountId = accountId;

  // Clear local cache
  this._orders.clear();
  this._positions.clear();

  // Notify TradingView to re-request all data
  this._host.currentAccountUpdate();
}
```

### Scenario 4: Real-Time P&L Updates

```typescript
subscribeEquity(): void {
  // Start real-time equity updates
  this._equityInterval = setInterval(() => {
    // Calculate total P&L from positions
    let totalPL = 0;
    for (const position of this._positions.values()) {
      const currentPrice = this.getCurrentPrice(position.symbol);
      const pl = (currentPrice - position.avgPrice) * position.qty *
                 (position.side === Side.Buy ? 1 : -1);
      totalPL += pl;

      // Update position P&L
      this._host.plUpdate(position.id, pl);
    }

    // Update equity
    const equity = this._balance + totalPL;
    this._host.equityUpdate(equity);
  }, 1000);
}
```

---

## Integration with Broker API

### Complete Integration Example

```typescript
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _host: IBrokerConnectionAdapterHost
  private readonly _quotesProvider: IDatafeedQuotesApi

  // State
  private readonly _orders = new Map<string, Order>()
  private readonly _positions = new Map<string, Position>()
  private readonly _executions: Execution[] = []

  // Reactive values
  private readonly balance: IWatchedValue<number>
  private readonly equity: IWatchedValue<number>

  constructor(host: IBrokerConnectionAdapterHost, quotesProvider: IDatafeedQuotesApi) {
    this._host = host
    this._quotesProvider = quotesProvider

    // Create reactive values
    this.balance = host.factory.createWatchedValue(100000)
    this.equity = host.factory.createWatchedValue(100000)
  }

  // ============================================================
  // Broker API Implementation (Library calls these)
  // ============================================================

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const newOrder: Order = this.createOrder(order)
    this._orders.set(newOrder.id, newOrder)

    // Notify TradingView
    this._host.orderUpdate(newOrder)

    // Simulate execution
    this.scheduleExecution(newOrder.id)

    return { orderId: newOrder.id }
  }

  async modifyOrder(order: Order): Promise<void> {
    this._orders.set(order.id, order)

    // Notify TradingView
    this._host.orderUpdate(order)
  }

  async cancelOrder(orderId: string): Promise<void> {
    const order = this._orders.get(orderId)
    if (order) {
      order.status = OrderStatus.Canceled

      // Notify TradingView
      this._host.orderUpdate(order)
    }
  }

  async orders(): Promise<Order[]> {
    return Array.from(this._orders.values())
  }

  async positions(): Promise<Position[]> {
    return Array.from(this._positions.values())
  }

  async executions(symbol: string): Promise<Execution[]> {
    return this._executions.filter((e) => e.symbol === symbol)
  }

  // ============================================================
  // Internal Methods (use Trading Host to push updates)
  // ============================================================

  private scheduleExecution(orderId: string): void {
    setTimeout(() => {
      const order = this._orders.get(orderId)
      if (!order) return

      // Update order
      order.status = OrderStatus.Filled
      order.avgPrice = order.limitPrice || 100
      this._host.orderUpdate(order)

      // Create execution
      const execution: Execution = {
        symbol: order.symbol,
        price: order.avgPrice,
        qty: order.qty,
        side: order.side,
        time: Date.now(),
      }
      this._executions.push(execution)
      this._host.executionUpdate(execution)

      // Update position
      this.updatePosition(order)

      // Show notification
      this._host.showNotification(
        'Order Filled',
        `Order ${orderId} executed`,
        NotificationType.Success,
      )
    }, 3000)
  }

  private updatePosition(order: Order): void {
    const positionId = `${order.symbol}-POS`
    const existing = this._positions.get(positionId)

    if (existing) {
      // Update existing position
      const totalQty = existing.qty + (order.side === Side.Buy ? order.qty : -order.qty)
      existing.qty = Math.abs(totalQty)
      existing.side = totalQty >= 0 ? Side.Buy : Side.Sell
    } else {
      // Create new position
      this._positions.set(positionId, {
        id: positionId,
        symbol: order.symbol,
        qty: order.qty,
        side: order.side,
        avgPrice: order.avgPrice || 100,
      })
    }

    // Notify TradingView
    const position = this._positions.get(positionId)
    if (position) {
      this._host.positionUpdate(position)
    }
  }
}
```

---

## References

### Official Documentation

- **Trading Host API**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerConnectionAdapterHost/
- **Trading Concepts**: https://www.tradingview.com/charting-library-docs/latest/trading_terminal/trading-concepts/
- **Broker API**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerWithoutRealtime/

### Local Files

- **Type Definitions**: `../public/trading_terminal/charting_library.d.ts`
- **Broker Service**: `../src/services/brokerTerminalService.ts`
- **Broker Documentation**: `./BROKER-TERMINAL-SERVICE.md`

### Related Interfaces

- `IBrokerWithoutRealtime` - Broker API (library → you)
- `IBrokerTerminal` - Broker API with real-time (extends IBrokerWithoutRealtime)
- `IBrokerConnectionAdapterFactory` - Factory for creating library objects
- `IWatchedValue<T>` - Reactive value wrapper
- `INumberFormatter` - Number formatting interface

---

**Version**: 1.0.0  
**Last Updated**: November 11, 2025  
**Maintained by**: Development Team
