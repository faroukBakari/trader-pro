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
export class brokerTerminalService implements IBrokerWithoutRealtime {
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

    console.log('Mock Broker Service initialized with TradingView types')
    this.initializeBrokerData()
  }

  private initializeBrokerData(): void {
    // Create broker position using actual TradingView Position type
    const brokerPosition: Position = {
      id: 'AAPL-POS-1',
      symbol: 'AAPL',
      qty: 100,
      side: Side.Buy,
      avgPrice: 150.0,
    }
    this._positions.set(brokerPosition.id, brokerPosition)

    // Create broker order using actual TradingView Order type
    const brokerOrder: Order = {
      id: 'ORDER-1',
      symbol: 'TSLA',
      type: OrderType.Limit,
      side: Side.Buy,
      qty: 50,
      status: OrderStatus.Working,
      limitPrice: 200.0,
      updateTime: Date.now(),
    }
    this._orders.set(brokerOrder.id, brokerOrder)

    console.log('Sample trading data initialized')
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
    return {
      description: `Mock instrument for ${symbol}`,
      currency: 'USD',
      type: 'stock',
      minTick: 0.01,
      pipSize: 1,
      pipValue: 1,
      qty: {
        min: 1,
        max: 1000000,
        step: 1,
        default: 100,
      },
    }
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

    // Simulate order execution after a short delay
    setTimeout(() => {
      this.simulateOrderExecution(orderId)
    }, 1000)

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

    // Create execution record
    const execution: Execution = {
      symbol: order.symbol,
      price: filledOrder.avgPrice || 100.0,
      qty: order.qty,
      side: order.side,
      time: Date.now(),
    }
    this._executions.push(execution)

    // Update or create position
    this.updatePosition(order)

    console.log(`Order executed: ${orderId}`, execution)
  }

  private updatePosition(order: Order): void {
    const positionId = `${order.symbol}-POS`
    const existingPosition = this._positions.get(positionId)

    if (existingPosition) {
      // Update existing position
      const totalQty = existingPosition.qty + (order.side === Side.Buy ? order.qty : -order.qty)
      const updatedPosition: Position = {
        ...existingPosition,
        qty: Math.abs(totalQty),
        side: totalQty >= 0 ? Side.Buy : Side.Sell,
      }
      this._positions.set(positionId, updatedPosition)
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
    }
  }

  async modifyOrder(order: Order): Promise<void> {
    if (this._orders.has(order.id)) {
      this._orders.set(order.id, { ...order, updateTime: Date.now() })
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
