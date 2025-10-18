/**
 * Mock Broker Terminal Service for testing TradingView Trading Platform
 *
 * Refactored to use actual TradingView library types instead of custom interfaces.
 * Following patterns from reference implementation for proper type management.
 */

import type {
  AccountId,
  AccountManagerInfo,
  AccountMetainfo,
  ActionMetaInfo,
  ConnectionStatus,
  Execution,
  IBrokerConnectionAdapterHost,
  IBrokerWithoutRealtime, // IBrokerTerminal,
  IDatafeedQuotesApi,
  InstrumentInfo,
  INumberFormatter,
  IWatchedValue,
  Order,
  PlaceOrderResult,
  Position,
  PreOrder,
  TradeContext,
} from '@public/trading_terminal'

import { OrderStatus, OrderType, Side, StandardFormatterName } from '@public/trading_terminal'

/**
 * Mock Broker Terminal Service using actual TradingView types
 *
 * Features:
 * - Uses private readonly properties for data management
 * - Implements proper IBrokerTerminal interface
 * - Manages orders, positions, and executions using official TradingView types
 * - Follows reference implementation patterns
 */
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly host: IBrokerConnectionAdapterHost
  private readonly datafeed: IDatafeedQuotesApi

  // Private data management using actual TradingView types
  private readonly _orders = new Map<string, Order>()
  private readonly _positions = new Map<string, Position>()
  private readonly _executions: Execution[] = []
  private readonly balance: IWatchedValue<number>
  private readonly equity: IWatchedValue<number>

  // Counters and account info
  private orderCounter = 1
  private readonly accountId: AccountId = 'DEMO-001' as AccountId
  private readonly accountName = 'Demo Trading Account'
  private readonly startingBalance = 100000

  constructor(host: IBrokerConnectionAdapterHost, datafeed: IDatafeedQuotesApi) {
    this.host = host
    this.datafeed = datafeed
    this.balance = host.factory.createWatchedValue(this.startingBalance)
    this.equity = host.factory.createWatchedValue(this.startingBalance)
  }

  // IBrokerTerminal interface implementation
  accountManagerInfo(): AccountManagerInfo {
    return {
      accountTitle: 'Mock Trading Account',
      summary: [
        {
          text: 'Balance',
          wValue: this.balance,
          isDefault: true,
          formatter: StandardFormatterName.FixedInCurrency,
        },
        {
          text: 'Equity',
          wValue: this.equity,
          isDefault: true,
          formatter: StandardFormatterName.FixedInCurrency,
        },
      ],
      orderColumns: [
        {
          label: 'Symbol',
          id: 'symbol',
          dataFields: ['symbol', 'symbol'],
          formatter: StandardFormatterName.Symbol,
        },
        {
          label: 'Side',
          id: 'side',
          dataFields: ['side'],
          formatter: StandardFormatterName.Side,
        },
        {
          label: 'Quantity',
          id: 'qty',
          dataFields: ['qty'],
          formatter: StandardFormatterName.FormatQuantity,
        },
        {
          label: 'Status',
          id: 'status',
          dataFields: ['status'],
          formatter: StandardFormatterName.Status,
        },
      ],
      positionColumns: [
        {
          label: 'Symbol',
          id: 'symbol',
          dataFields: ['symbol', 'symbol'],
          formatter: StandardFormatterName.Symbol,
        },
        {
          label: 'Side',
          id: 'side',
          dataFields: ['side'],
          formatter: StandardFormatterName.PositionSide,
        },
        {
          label: 'Quantity',
          id: 'qty',
          dataFields: ['qty'],
          formatter: StandardFormatterName.FormatQuantity,
        },
        {
          label: 'Avg Price',
          id: 'avgPrice',
          dataFields: ['avgPrice'],
          formatter: StandardFormatterName.FormatPrice,
        },
      ],
      pages: [],
    }
  }

  async accountsMetainfo(): Promise<AccountMetainfo[]> {
    return [
      {
        id: this.accountId as AccountId, // TradingView uses complex AccountId type
        name: this.accountName,
      },
    ]
  }

  async orders(): Promise<Order[]> {
    return Array.from(this._orders.values())
  }

  async positions(): Promise<Position[]> {
    return Array.from(this._positions.values())
  }

  async executions(symbol: string): Promise<Execution[]> {
    return this._executions.filter((exec) => exec.symbol === symbol)
  }

  async symbolInfo(symbol: string): Promise<InstrumentInfo> {
    const mintick = await this.host.getSymbolMinTick(symbol);
    const pipSize = mintick; // Pip size can differ from minTick
    const accountCurrencyRate = 1; // Account currency rate
    const pointValue = 1; // USD value of 1 point of price

    return {
      qty: {
        min: 1,
        max: 1e12,
        step: 1,
      },
      pipValue: pipSize * pointValue * accountCurrencyRate || 1,
      pipSize: pipSize,
      minTick: mintick,
      description: '',
    };
  }

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    console.log('[Broker] Attempting to place order:', order)

    const orderId = `ORDER-${this.orderCounter++}`

    const newOrder: Order = {
      id: orderId,
      symbol: order.symbol,
      type: order.type || OrderType.Market,
      side: order.side || Side.Buy,
      qty: order.qty || 100,
      status: OrderStatus.Working,
      limitPrice: order.limitPrice,
      stopPrice: order.stopPrice,
      updateTime: Date.now(),
    }

    this._orders.set(orderId, newOrder)

    // Notify TradingView that the order was created
    this.host.orderUpdate(newOrder)

    // Simulate order execution after a short delay
    setTimeout(() => {
      this.simulateOrderExecution(orderId)
    }, 200)

    console.log(`[Broker] Mock order placed: ${orderId}`, newOrder)
    return { orderId }
  }

  private simulateOrderExecution(orderId: string): void {
    const order = this._orders.get(orderId)
    if (!order) return

    // Mark order as filled
    const filledOrder: Order = {
      ...order,
      status: OrderStatus.Filled,
      filledQty: order.qty,
      avgPrice: order.limitPrice || 100.0, // Use limit price or default
      updateTime: Date.now(),
    }
    this._orders.set(orderId, filledOrder)

    // Notify TradingView that the order was filled
    this.host.orderUpdate(filledOrder)

    // Create execution record
    const execution: Execution = {
      symbol: order.symbol,
      price: filledOrder.avgPrice || 100.0,
      qty: order.qty,
      side: order.side,
      time: Date.now(),
    }
    this._executions.push(execution)
    this.host.executionUpdate(execution)

    // Update or create position
    this.updatePosition(order)

    console.log(`Order executed: ${orderId}`, execution)
  }

  private updatePosition(order: Order): void {
    const positionId = `${order.symbol}-POS`
    const existingPosition = this._positions.get(positionId)

    if (existingPosition) {
      // Calculate net position considering both existing position side and order side
      // For long positions (Buy side): qty is positive
      // For short positions (Sell side): qty is negative
      const existingQty = existingPosition.side === Side.Buy ? existingPosition.qty : -existingPosition.qty
      const orderQty = order.side === Side.Buy ? order.qty : -order.qty
      const totalQty = existingQty + orderQty

      // If position is completely closed, remove it
      if (totalQty === 0) {
        this._positions.delete(positionId)
        // Notify TradingView that the position was closed
        // TradingView expects a position update with 0 qty to close it
        const closedPosition: Position = {
          ...existingPosition,
          qty: 0,
          side: existingPosition.side,
        }
        this.host.positionUpdate(closedPosition)
      } else {
        // Update existing position
        const updatedPosition: Position = {
          ...existingPosition,
          qty: Math.abs(totalQty),
          side: totalQty > 0 ? Side.Buy : Side.Sell,
        }
        this._positions.set(positionId, updatedPosition)
        // Notify TradingView that the position was updated
        this.host.positionUpdate(updatedPosition)
      }
    } else {
      // Create new position
      const newPosition: Position = {
        id: positionId,
        symbol: order.symbol,
        qty: order.qty,
        side: order.side,
        avgPrice: order.avgPrice || order.limitPrice || 100.0,
      }
      this._positions.set(positionId, newPosition)
      // Notify TradingView that the position was created
      this.host.positionUpdate(newPosition)
    }
  }

  async modifyOrder(order: Order): Promise<void> {
    if (this._orders.has(order.id)) {
      const updatedOrder = { ...order, updateTime: Date.now() }
      this._orders.set(order.id, updatedOrder)
      // Notify TradingView that the order was modified
      this.host.orderUpdate(updatedOrder)
      console.log(`Order modified: ${order.id}`)
    }
  }

  async cancelOrder(orderId: string): Promise<void> {
    const order = this._orders.get(orderId)
    if (order) {
      const cancelledOrder: Order = {
        ...order,
        status: OrderStatus.Canceled,
        updateTime: Date.now(),
      }
      this._orders.set(orderId, cancelledOrder)
      // Notify TradingView that the order was cancelled
      this.host.orderUpdate(cancelledOrder)
      console.log(`Order cancelled: ${orderId}`)
    }
  }

  async chartContextMenuActions(context: TradeContext): Promise<ActionMetaInfo[]> {
    return this.host.defaultContextMenuActions(context)
  }

  async isTradable(): Promise<boolean> {
    // All symbols are tradable in our mock
    return true
  }

  async formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter> {
    return this.host.defaultFormatter(symbol, alignToMinMove)
  }

  currentAccount(): AccountId {
    return this.accountId
  }

  // subscribeRealtime(symbol: string): void {
  //   console.log('Mock realtime subscription started for symbol:', symbol)
  // }

  // unsubscribeRealtime(symbol: string): void {
  //   console.log('Mock realtime subscription stopped for symbol:', symbol)
  // }

  connectionStatus(): ConnectionStatus {
    return 1 // Connected status
  }
}
