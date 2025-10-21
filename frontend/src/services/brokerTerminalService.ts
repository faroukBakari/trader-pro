/**
 * Broker Terminal Service for TradingView Trading Platform
 *
 * This service acts as an adapter between TradingView's broker interface
 * and our broker client implementations (fallback mock or real backend).
 * It delegates broker operations to the injected client while managing
 * TradingView-specific concerns like host notifications and UI configuration.
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
  IBrokerWithoutRealtime,
  IDatafeedQuotesApi,
  InstrumentInfo,
  INumberFormatter,
  IsTradableResult,
  IWatchedValue,
  Order,
  PlaceOrderResult,
  Position,
  PreOrder,
  TradeContext
} from '@public/trading_terminal'

import { ApiAdapter, type ApiPromise } from '@/plugins/apiAdapter'
import { ConnectionStatus, OrderStatus, Side, StandardFormatterName } from '@public/trading_terminal'

// ============================================================================
// BROKER CLIENT INTERFACE
// ============================================================================

/**
 * Broker client interface
 * Contract that all broker clients (fallback, real backend) must implement
 *
 * This interface defines the core broker operations that both the mock fallback client
 * and the real backend client must support. It ensures type-safe communication and
 * allows for seamless switching between mock and real implementations.
 */
export interface ApiInterface {
  // Order operations
  placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult>
  modifyOrder(order: Order, confirmId?: string): ApiPromise<void>
  cancelOrder(orderId: string): ApiPromise<void>
  getOrders(): ApiPromise<Order[]>

  // Position operations
  getPositions(): ApiPromise<Position[]>

  // Execution operations
  getExecutions(symbol: string): ApiPromise<Execution[]>

  // Account operations
  getAccountInfo(): ApiPromise<AccountMetainfo>
}

// ============================================================================
// FALLBACK CLIENT (MOCK IMPLEMENTATION)
// ============================================================================

/**
 * Fallback broker client with mock implementation
 * Implements the broker interface contract for offline development
 *
 * This client provides a complete mock implementation of broker functionality,
 * simulating order execution, position management, and trade history.
 * It uses private members and methods to encapsulate the mock logic,
 * following the same patterns as the original brokerTerminalService.
 */
class BrokerFallbackClient implements ApiInterface {
  private readonly _host: IBrokerConnectionAdapterHost
  private readonly _quotesProvider: IDatafeedQuotesApi

  // Private state management
  private readonly _orderById = new Map<string, Order>()
  private readonly _positions = new Map<string, Position>()
  private readonly _executions: Execution[] = []

  // Counters and account info
  private orderCounter = 1
  private readonly accountId: AccountId = 'DEMO-001' as AccountId
  private readonly accountName = 'Demo Trading Account'

  constructor(host: IBrokerConnectionAdapterHost, datafeed: IDatafeedQuotesApi) {
    this._host = host
    this._quotesProvider = datafeed
  }

  // Public API methods (interface contract)

  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const orderId = `ORDER-${this.orderCounter++}`

    const newOrder: Order = {
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

    // Simulate execution asynchronously
    await this.simulateOrderExecution(orderId)

    console.log(`[FallbackClient] Order created: ${orderId}`)

    return {
      status: 200,
      data: { orderId },
    }
  }

  async modifyOrder(order: Order, confirmId?: string): ApiPromise<void> {
    const originalOrder = this._orderById.get(confirmId ?? order.id)
    if (!originalOrder) {
      console.warn(`[FallbackClient] Order not found: ${confirmId ?? order.id}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    // Only update specific fields, not entire order
    originalOrder.qty = order.qty
    originalOrder.limitPrice = order.limitPrice
    originalOrder.stopPrice = order.stopPrice

    this._host.orderUpdate(originalOrder)

    // Re-simulate execution for modified order
    await this.simulateOrderExecution(originalOrder.id)

    console.log(`[FallbackClient] Order modified: ${originalOrder.id}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async cancelOrder(orderId: string): ApiPromise<void> {
    const order = this._orderById.get(orderId)
    if (!order) {
      console.warn(`[FallbackClient] Order not found: ${orderId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    const cancelledOrder: Order = {
      ...order,
      status: OrderStatus.Canceled,
      updateTime: Date.now(),
    }

    this._orderById.set(orderId, cancelledOrder)
    this._host.orderUpdate(cancelledOrder)

    console.log(`[FallbackClient] Order cancelled: ${orderId}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async getOrders(): ApiPromise<Order[]> {
    return {
      status: 200,
      data: Array.from(this._orderById.values()),
    }
  }

  async getPositions(): ApiPromise<Position[]> {
    return {
      status: 200,
      data: Array.from(this._positions.values()),
    }
  }

  async getExecutions(symbol: string): ApiPromise<Execution[]> {
    return {
      status: 200,
      data: this._executions.filter((exec) => exec.symbol === symbol),
    }
  }

  async getAccountInfo(): ApiPromise<AccountMetainfo> {
    return {
      status: 200,
      data: {
        id: this.accountId as AccountId,
        name: this.accountName,
      },
    }
  }

  // Private methods (mock logic)

  private async simulateOrderExecution(orderId: string): Promise<void> {
    const order = this._orderById.get(orderId)
    if (!order) return

    // Determine execution price
    if (!order.limitPrice) {
      try {
        const quote: DatafeedQuoteValues = await new Promise((resolve, reject) => {
          this._quotesProvider.getQuotes(
            [order.symbol],
            (quotes) => {
              if (quotes && quotes.length > 0 && quotes[0].s === 'ok') {
                resolve(quotes[0].v)
              } else {
                reject(new Error('No quote available'))
              }
            },
            (error) => {
              reject(error)
            }
          )
        })

        // Use bid/ask price based on order side for market execution
        order.limitPrice = order.side === Side.Buy ? quote.ask : quote.bid
      } catch (error) {
        console.warn('[FallbackClient] Failed to get quote, using default price:', error)
        // Fallback to a default price if quote fetch fails
        order.limitPrice = 100
      }
    }

    // Simulate execution delay
    await new Promise((resolve) => setTimeout(resolve, 200))

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

      // Update position
      this.updatePosition(execution)

      // Mark order as filled
      const filledOrder: Order = {
        ...order,
        status: OrderStatus.Filled,
        filledQty: order.qty,
        avgPrice: order.limitPrice,
        updateTime: Date.now(),
      }

      this._orderById.set(orderId, filledOrder)
      this._host.orderUpdate(filledOrder)

      console.log(`[FallbackClient] Order executed: ${orderId}`, execution)
    }
  }

  private updatePosition(execution: Execution): void {
    const positionId = `${execution.symbol}-POS`
    const existingPosition = this._positions.get(positionId)

    if (existingPosition) {
      // Calculate new position quantity considering sides
      const newPositionQty = Math.abs(
        existingPosition.side * existingPosition.qty + execution.side * execution.qty
      )

      if (newPositionQty > 0) {
        // Determine new position side
        const newPositionSide =
          existingPosition.side * existingPosition.qty + execution.side * execution.qty > 0
            ? Side.Buy
            : Side.Sell

        // Calculate new average price
        existingPosition.avgPrice =
          (existingPosition.side * existingPosition.avgPrice * existingPosition.qty +
            execution.side * execution.price * execution.qty) /
          newPositionQty

        existingPosition.side = newPositionSide
        existingPosition.qty = newPositionQty
        this._host.positionUpdate(existingPosition)
      } else {
        // Position closed - set qty to 0 before notification
        existingPosition.qty = 0
        this._host.positionUpdate(existingPosition)
        this._positions.delete(positionId)
      }
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
}

// ============================================================================
// BROKER TERMINAL SERVICE
// ============================================================================

/**
 * Broker Terminal Service using client delegation pattern
 *
 * Features:
 * - Delegates broker operations to ApiInterface interface
 * - Manages TradingView host notifications
 * - Provides account manager UI configuration
 * - Supports both mock (fallback) and real backend clients
 */

// TODO: study interface IBrokerConnectionAdapterHost as there are some asyncapi calls to wire up
// Reverse engineer from TradingView docs and existing implementations and the need for realtime broker
export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _host: IBrokerConnectionAdapterHost
  private readonly _quotesProvider: IDatafeedQuotesApi

  // Client adapters
  private readonly apiFallback: ApiInterface
  private readonly apiAdapter: ApiAdapter

  // Mock flag
  private mock: boolean

  // UI state (managed by service, not client)
  private readonly balance: IWatchedValue<number>
  private readonly equity: IWatchedValue<number>
  private readonly startingBalance = 100000

  constructor(
    host: IBrokerConnectionAdapterHost,
    datafeed: IDatafeedQuotesApi,
    mock: boolean = true // Default to fallback for safety
  ) {
    this._host = host
    this._quotesProvider = datafeed
    this.mock = mock

    // Initialize clients
    this.apiFallback = new BrokerFallbackClient(host, datafeed)
    this.apiAdapter = new ApiAdapter()

    // Initialize UI state
    this.balance = host.factory.createWatchedValue(this.startingBalance)
    this.equity = host.factory.createWatchedValue(this.startingBalance)
  }

  /**
   * Get broker client based on mock flag
   * Same pattern as datafeedService._getApiAdapter()
   */
  private _getApiAdapter(mock: boolean = this.mock): ApiInterface {
    return mock ? this.apiFallback : this.apiAdapter
  }

  // IBrokerWithoutRealtime interface implementation

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
    const response = await this._getApiAdapter().getAccountInfo()
    return [response.data]
  }

  async orders(): Promise<Order[]> {
    const response = await this._getApiAdapter().getOrders()
    return response.data
  }

  async positions(): Promise<Position[]> {
    const response = await this._getApiAdapter().getPositions()
    return response.data
  }

  async executions(symbol: string): Promise<Execution[]> {
    const response = await this._getApiAdapter().getExecutions(symbol)
    return response.data
  }

  async symbolInfo(symbol: string): Promise<InstrumentInfo> {
    const mintick = await this._host.getSymbolMinTick(symbol)
    const pipSize = mintick // Pip size can differ from minTick
    const accountCurrencyRate = 1 // Account currency rate
    const pointValue = 1 // USD value of 1 point of price

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
    }
  }

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    // Delegate to client
    const response = await this._getApiAdapter().placeOrder(order)
    const result = response.data

    // Notify TradingView host about order updates
    const ordersResponse = await this._getApiAdapter().getOrders()
    const placedOrder = ordersResponse.data.find((o) => o.id === result.orderId)
    if (placedOrder) {
      this._host.orderUpdate(placedOrder)
    }

    return result
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    // Delegate to client
    await this._getApiAdapter().modifyOrder(order, confirmId)

    // Notify TradingView host about updates
    const ordersResponse = await this._getApiAdapter().getOrders()
    const modifiedOrder = ordersResponse.data.find((o) => o.id === (confirmId ?? order.id))
    if (modifiedOrder) {
      this._host.orderUpdate(modifiedOrder)
    }
  }

  async cancelOrder(orderId: string): Promise<void> {
    // Delegate to client
    await this._getApiAdapter().cancelOrder(orderId)

    // Notify TradingView host about updates
    const ordersResponse = await this._getApiAdapter().getOrders()
    const cancelledOrder = ordersResponse.data.find((o) => o.id === orderId)
    if (cancelledOrder) {
      this._host.orderUpdate(cancelledOrder)
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
    // Get account ID from client
    // For now, return a default value synchronously
    // In a real implementation, this could be cached from accountsMetainfo()
    return 'DEMO-001' as AccountId
  }

  // Fix connectionStatus
  connectionStatus(): ConnectionStatusType {
    return ConnectionStatus.Connected
  }
}
