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
  ConnectionStatus as ConnectionStatusType,
  DatafeedQuoteValues,
  DefaultContextMenuActionsParams,
  Execution,
  IBrokerConnectionAdapterHost,
  IBrokerWithoutRealtime, // IBrokerTerminal,
  IDatafeedQuotesApi,
  InstrumentInfo,
  INumberFormatter,
  IsTradableResult,
  IWatchedValue,
  Order,
  PlacedOrder,
  PlaceOrderResult,
  Position,
  PreOrder,
  TradeContext
} from '@public/trading_terminal'

import { ConnectionStatus, OrderStatus, Side, StandardFormatterName } from '@public/trading_terminal'

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
  private readonly _host: IBrokerConnectionAdapterHost
  private readonly _quotesProvider: IDatafeedQuotesApi

  // Private data management using actual TradingView types
  private readonly _orderById = new Map<string, Order>()
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
    this._host = host
    this._quotesProvider = datafeed
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
    return Array.from(this._orderById.values())
  }

  async positions(): Promise<Position[]> {
    return Array.from(this._positions.values())
  }

  async executions(symbol: string): Promise<Execution[]> {
    return this._executions.filter((exec) => exec.symbol === symbol)
  }

  async symbolInfo(symbol: string): Promise<InstrumentInfo> {
    const mintick = await this._host.getSymbolMinTick(symbol);
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
    const orderId = `ORDER-${this.orderCounter++}`

    const newOrder: PlacedOrder = {
      id: orderId,
      symbol: order.symbol,
      type: order.type,
      side: order.side,
      qty: order.qty,
      status: OrderStatus.Working,
      limitPrice: order.limitPrice,
      stopPrice: order.stopPrice,
      takeProfit: order.takeProfit,
      stopLoss: order.stopLoss,
    }

    this._orderById.set(orderId, newOrder)
    this._host.orderUpdate(newOrder)
    await this.simulateOrderExecution(orderId)
    console.log(`Order created: ${orderId}`)

    return Promise.resolve({ orderId }); // Match reference implementation
  }

  private async simulateOrderExecution(orderId: string): Promise<void> {
    const order = this._orderById.get(orderId)
    if (!order) return

    if (!order.limitPrice) {
      // Get current market price from quotes provider as fallback
      try {
        const quote: DatafeedQuoteValues = await new Promise((resolve, reject) => {
          this._quotesProvider.getQuotes([order.symbol], (quotes) => {
            if (quotes && quotes.length > 0 && quotes[0].s === 'ok') {
              resolve(quotes[0].v)
            } else {
              reject(new Error('No quote available'))
            }
          }, (error) => {
            reject(error)
          })
        })

        // Use bid/ask price based on order side for market execution
        const executionPrice = order.side === Side.Buy ? quote.ask : quote.bid
        order.limitPrice = executionPrice
      } catch (error) {
        console.warn('Failed to get quote, using default price:', error)
        // Fallback to a default price if quote fetch fails
        order.limitPrice = 100
      }
    }

    // Simulate order execution delay
    await new Promise(resolve => setTimeout(resolve, 200))

    if (order.limitPrice) {
      // Create execution record
      const execution: Execution = {
        symbol: order.symbol,
        price: order.limitPrice,
        qty: order.qty,
        side: order.side,
        time: Date.now(),
      }
      this._executions.push(execution)
      this._host.executionUpdate(execution)
      this.updatePosition(execution)

      // Mark order as filled
      const filledOrder: Order = {
        ...order,
        status: OrderStatus.Filled,
        filledQty: order.qty,
        avgPrice: order.limitPrice, // Use limit price or default
        updateTime: Date.now(),
      }
      this._orderById.set(orderId, filledOrder)

      // Notify TradingView that the order was filled
      this._host.orderUpdate(filledOrder)

      console.log(`Order executed: ${orderId}`, execution)
    }
  }

  private updatePosition(execution: Execution): void {
    const positionId = `${execution.symbol}-POS`
    const existingPosition = this._positions.get(positionId)

    if (existingPosition) {
      const newPositionQty = Math.abs((existingPosition.side * existingPosition.qty) + (execution.side * execution.qty))

      if (newPositionQty > 0) {
        const newPositionSide = (existingPosition.side * existingPosition.qty) + (execution.side * execution.qty) > 0 ? Side.Buy : Side.Sell
        existingPosition.avgPrice = ((existingPosition.side * existingPosition.avgPrice * existingPosition.qty) + (execution.side * execution.price * execution.qty)) / newPositionQty
        existingPosition.side = newPositionSide
      } else {
        this._positions.delete(positionId)
      }

      existingPosition.qty = newPositionQty
      this._host.positionUpdate(existingPosition)
    } else {
      // Create new position
      const newPosition: Position = {
        id: positionId,
        symbol: execution.symbol,
        qty: execution.qty,
        side: execution.side,
        avgPrice: execution.price,
      }
      this._positions.set(positionId, newPosition)
      this._host.positionUpdate(newPosition)
    }
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    const originalOrder = this._orderById.get(confirmId ?? order.id)
    if (!originalOrder) return

    // Only update specific fields, not entire order
    originalOrder.qty = order.qty
    originalOrder.limitPrice = order.limitPrice
    originalOrder.stopPrice = order.stopPrice

    this._host.orderUpdate(originalOrder)
    await this.simulateOrderExecution(originalOrder.id)
    console.log(`Order modified: ${originalOrder.id}`)
  }

  async cancelOrder(orderId: string): Promise<void> {
    const order = this._orderById.get(orderId)
    if (order) {
      const cancelledOrder: Order = {
        ...order,
        status: OrderStatus.Canceled,
        updateTime: Date.now(),
      }
      this._orderById.set(orderId, cancelledOrder)
      // Notify TradingView that the order was cancelled
      this._host.orderUpdate(cancelledOrder)
      console.log(`Order cancelled: ${orderId}`)
    }
  }

  // Fix chartContextMenuActions
  async chartContextMenuActions(
    context: TradeContext,
    options?: DefaultContextMenuActionsParams
  ): Promise<ActionMetaInfo[]> {
    return this._host.defaultContextMenuActions(context, options)
  }

  // Fix isTradable signature
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async isTradable(symbol: string): Promise<boolean | IsTradableResult> {
    return true
  }

  async formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter> {
    return this._host.defaultFormatter(symbol, alignToMinMove)
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

  // Fix connectionStatus
  connectionStatus(): ConnectionStatusType {
    return ConnectionStatus.Connected
  }
}
