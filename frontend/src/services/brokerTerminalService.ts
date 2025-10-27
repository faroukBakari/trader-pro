import type {
  AccountId,
  AccountManagerInfo,
  AccountMetainfo,
  ActionMetaInfo,
  Brackets,
  ConnectionStatus as ConnectionStatusType,
  CustomInputFieldsValues,
  DefaultContextMenuActionsParams,
  Execution,
  IBrokerConnectionAdapterHost,
  IBrokerWithoutRealtime,
  IDatafeedQuotesApi,
  InstrumentInfo,
  INumberFormatter,
  IsTradableResult,
  IWatchedValue,
  LeverageInfo,
  LeverageInfoParams,
  LeveragePreviewResult,
  LeverageSetParams,
  LeverageSetResult,
  Order,
  OrderPreviewResult,
  PlaceOrderResult,
  Position,
  PreOrder,
  TradeContext,
} from '@public/trading_terminal'

import { ApiAdapter, type ApiPromise } from '@/plugins/apiAdapter'
import { WsAdapter, WsFallback, type BrokerConnectionStatus, type EquityData, type WsAdapterType } from '@/plugins/wsAdapter'
import { ConnectionStatus, NotificationType, OrderStatus, Side, StandardFormatterName } from '@public/trading_terminal'


export interface ApiInterface {
  // Order operations
  previewOrder(order: PreOrder): ApiPromise<OrderPreviewResult>
  placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult>
  modifyOrder(order: Order, confirmId?: string): ApiPromise<void>
  cancelOrder(orderId: string): ApiPromise<void>
  getOrders(): ApiPromise<Order[]>
  getPositions(): ApiPromise<Position[]>
  getExecutions(symbol: string): ApiPromise<Execution[]>
  getAccountInfo(): ApiPromise<AccountMetainfo>

  // Position operations
  closePosition(positionId: string, amount?: number): ApiPromise<void>
  editPositionBrackets(positionId: string, brackets: Brackets, customFields?: CustomInputFieldsValues): ApiPromise<void>

  // Leverage operations
  leverageInfo(leverageInfoParams: LeverageInfoParams): ApiPromise<LeverageInfo>
  setLeverage(leverageSetParams: LeverageSetParams): ApiPromise<LeverageSetResult>
  previewLeverage(leverageSetParams: LeverageSetParams): ApiPromise<LeveragePreviewResult>
}

export class BrokerMock {
  protected _orderById = new Map<string, Order>()
  protected _positions = new Map<string, Position>()
  protected _executions: Execution[] = []
  protected _accountId: AccountId = 'DEMO-ACCOUNT' as AccountId // needs to match backend account
  protected _accountName = 'Demo Trading Account'
  protected _equity = 105000
  protected _balance = 100000
  protected _unrealizedPL = 5000
  protected _realizedPL = 0

  protected orderUpdates: Order[] = []
  protected executionUpdates: Execution[] = []
  protected positionUpdates: Position[] = []
  protected equityUpdates: { equity: number, balance: number, unrealizedPL: number, realizedPL: number }[] = [{
    equity: this._equity,
    balance: this._balance,
    unrealizedPL: this._unrealizedPL,
    realizedPL: this._realizedPL,
  }]
  protected connectionStatusUpdates: BrokerConnectionStatus[] = [{
    status: ConnectionStatus.Connected,
    message: 'Mock broker connected',
    timestamp: Date.now(),
  }]

  getAccountId(): AccountId {
    return this._accountId
  }

  getAccountName(): string {
    return this._accountName
  }

  getOrders(): Order[] {
    return Array.from(this._orderById.values()).map(order => ({ ...order }))
  }

  getOrderById(orderId: string): Order | undefined {
    const order = this._orderById.get(orderId)
    return order ? { ...order } : undefined
  }

  getPositions(): Position[] {
    return Array.from(this._positions.values()).map(pos => ({ ...pos }))
  }

  getPositionBySymbol(symbol: string): Position | undefined {
    const position = Array.from(this._positions.values()).find(pos => pos.symbol === symbol)
    return position ? { ...position } : undefined
  }

  getExecutions(): Execution[] {
    return this._executions.map(exec => ({ ...exec }))
  }

  getExecutionsBySymbol(symbol: string): Execution[] {
    return this._executions
      .filter(exec => exec.symbol === symbol)
      .map(exec => ({ ...exec }))
  }

  addOrder(order: Order): void {
    this._orderById.set(order.id, { ...order })
    this.orderUpdates.push({ ...order })
  }

  updateOrder(orderId: string, updates: Partial<Order>): void {
    const order = this._orderById.get(orderId)
    if (order) {
      Object.assign(order, updates)
      this.orderUpdates.push({ ...order })
    }
  }

  addPositionBracketOrders(positionId: string, updates: Partial<Position>): void {
    const position = this._positions.get(positionId)
    if (position) {
      Object.assign(position, updates)
      this.positionUpdates.push({ ...position })
    }
  }

  ordersMocker(): Order | undefined {
    const order = this.orderUpdates.shift()
    if (order) {
      const execution = {
        id: order.id,
        symbol: order.symbol,
        side: order.side,
        qty: order.qty,
        price: order.limitPrice || order.stopPrice || 0,
        time: Date.now(),
      }
      this._executions.push(execution)
      this.executionUpdates.push({ ...execution })
    }
    return order
  }

  executionsMocker(): Execution | undefined {
    const execution = this.executionUpdates.shift()
    if (execution) {
      // Update position based on execution
      const existingPosition = this._positions.get(execution.symbol)

      if (existingPosition) {
        // Position exists - update it
        const isSameSide = existingPosition.side === execution.side
        if (isSameSide) {
          // Add to position
          const totalQty = existingPosition.qty + execution.qty
          const totalValue = (existingPosition.avgPrice * existingPosition.qty) + (execution.price * execution.qty)
          const newAvgPrice = totalValue / totalQty

          Object.assign(existingPosition, {
            qty: totalQty,
            avgPrice: newAvgPrice,
          })
        } else {
          // Reduce or reverse position
          const netQty = existingPosition.qty - execution.qty
          if (netQty > 0) {
            // Reduce position
            Object.assign(existingPosition, { qty: netQty })
          } else if (netQty < 0) {
            // Reverse position
            Object.assign(existingPosition, {
              qty: Math.abs(netQty),
              side: execution.side,
              avgPrice: execution.price,
            })
          } else {
            Object.assign(existingPosition, {
              qty: 0,
            })
          }
        }

        if (this._positions.has(execution.symbol)) {
          this.positionUpdates.push({ ...existingPosition })
        }
      } else {
        // Create new position
        const newPosition: Position = {
          id: execution.symbol,
          symbol: execution.symbol,
          side: execution.side,
          qty: execution.qty,
          avgPrice: execution.price,
        }
        this._positions.set(execution.symbol, newPosition)
        this.positionUpdates.push({ ...newPosition })
      }
    }
    return execution
  }

  positionsMocker(): Position | undefined {
    const position = this.positionUpdates.shift()
    if (position) {

      this._unrealizedPL = Array.from(this._positions.values())
        .reduce((total, pos) => {
          const posUnrealized = pos.avgPrice * pos.qty * (pos.side === Side.Buy ? -1 : 1)
          return total + posUnrealized
        }, 0)

      this._realizedPL = this._executions
        .reduce((total, execution) => {
          const position = this._positions.get(execution.symbol)
          if (!position) {
            const pnl = execution.price * execution.qty * (execution.side === Side.Buy ? -1 : 1)
            return total + pnl
          }
          return total
        }, 0)

      this._equity = this._balance + this._unrealizedPL + this._realizedPL

      this.equityUpdates.push({
        equity: this._equity,
        balance: this._balance,
        unrealizedPL: this._unrealizedPL,
        realizedPL: this._realizedPL,
      })

    }
    return position
  }

  equityMocker(): EquityData | undefined {
    return this.equityUpdates.shift()
  }

  brokerConnectionMocker(): BrokerConnectionStatus | undefined {
    return this.connectionStatusUpdates.shift()
  }

  reset(): void {
    this._orderById.clear()
    this._positions.clear()
    this._executions.length = 0
    this.orderUpdates.length = 0
    this.executionUpdates.length = 0
    this.positionUpdates.length = 0
    this.equityUpdates.length = 0
    this._equity = 105000
    this._balance = 100000
    this._unrealizedPL = 5000
    this._realizedPL = 0
    this.connectionStatusUpdates.push({
      status: ConnectionStatus.Connected,
      message: 'Mock broker connected',
      timestamp: Date.now(),
    })
  }
}

class ApiFallback implements ApiInterface {
  private readonly brokerMock: BrokerMock

  constructor(brokerMock?: BrokerMock) {
    this.brokerMock = brokerMock ?? new BrokerMock()
  }

  async previewOrder(order: PreOrder): ApiPromise<OrderPreviewResult> {
    // Calculate order value and costs
    const estimatedPrice = order.limitPrice || order.stopPrice || 100.0
    const orderValue = order.qty * estimatedPrice
    const commission = orderValue * 0.001 // 0.1% commission
    const marginRequired = orderValue * 0.5 // 50% margin

    // Build preview sections
    const sections: OrderPreviewResult['sections'] = []

    // Section 1: Order Details
    const orderTypeMap: Record<number, string> = {
      1: 'Limit',
      2: 'Market',
      3: 'Stop',
      4: 'Stop Limit',
    }

    const orderDetailsRows = [
      { title: 'Symbol', value: order.symbol },
      { title: 'Side', value: order.side === 1 ? 'Buy' : 'Sell' },
      { title: 'Quantity', value: `${order.qty.toFixed(2)}` },
      { title: 'Order Type', value: orderTypeMap[order.type] || 'Unknown' },
    ]

    if (order.limitPrice) {
      orderDetailsRows.push({ title: 'Limit Price', value: `$${order.limitPrice.toFixed(2)}` })
    }
    if (order.stopPrice) {
      orderDetailsRows.push({ title: 'Stop Price', value: `$${order.stopPrice.toFixed(2)}` })
    }

    sections.push({
      header: 'Order Details',
      rows: orderDetailsRows,
    })

    // Section 2: Cost Analysis
    sections.push({
      header: 'Cost Analysis',
      rows: [
        { title: 'Estimated Price', value: `$${estimatedPrice.toFixed(2)}` },
        { title: 'Order Value', value: `$${orderValue.toFixed(2)}` },
        { title: 'Commission', value: `$${commission.toFixed(2)}` },
        { title: 'Margin Required', value: `$${marginRequired.toFixed(2)}` },
        { title: 'Total Cost', value: `$${(orderValue + commission).toFixed(2)}` },
      ],
    })

    // Section 3: Risk Management (if brackets exist)
    if (order.takeProfit || order.stopLoss) {
      const bracketRows = []

      if (order.takeProfit) {
        const potentialProfit = Math.abs((order.takeProfit - estimatedPrice) * order.qty)
        bracketRows.push({
          title: 'Take Profit',
          value: `$${order.takeProfit.toFixed(2)} (+$${potentialProfit.toFixed(2)})`,
        })
      }

      if (order.stopLoss) {
        const potentialLoss = Math.abs((order.stopLoss - estimatedPrice) * order.qty)
        bracketRows.push({
          title: 'Stop Loss',
          value: `$${order.stopLoss.toFixed(2)} (-$${potentialLoss.toFixed(2)})`,
        })
      }

      if (bracketRows.length > 0) {
        sections.push({
          header: 'Risk Management',
          rows: bracketRows,
        })
      }
    }

    // Generate confirmation ID
    const confirmId = `PREVIEW-${Date.now()}-${Math.random().toString(36).substring(7)}`

    // Add warnings
    const warnings: string[] = []
    if (order.type === 2) { // Market order
      warnings.push('Market orders execute immediately at current market price')
    }
    if (order.qty > 1000) {
      warnings.push('Large order size may experience slippage')
    }

    return {
      status: 200,
      data: {
        sections,
        confirmId,
        warnings: warnings.length > 0 ? warnings : undefined,
      },
    }
  }

  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const orderId = `ORDER-${this.brokerMock.getOrders().length + 1}`

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

    this.brokerMock.addOrder(newOrder)

    console.log(`[FallbackClient] Order created: ${orderId}`)

    return {
      status: 200,
      data: { orderId },
    }
  }

  async modifyOrder(order: Order, confirmId?: string): ApiPromise<void> {
    const orderId = confirmId ?? order.id
    const originalOrder = this.brokerMock.getOrderById(orderId)
    if (!originalOrder) {
      console.warn(`[FallbackClient] Order not found: ${orderId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    this.brokerMock.updateOrder(orderId, {
      qty: order.qty,
      limitPrice: order.limitPrice,
      stopPrice: order.stopPrice,
      takeProfit: order.takeProfit,
      stopLoss: order.stopLoss,
    })

    console.log(`[FallbackClient] Order modified: ${orderId}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async cancelOrder(orderId: string): ApiPromise<void> {
    const order = this.brokerMock.getOrderById(orderId)
    if (!order) {
      console.warn(`[FallbackClient] Order not found: ${orderId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    this.brokerMock.updateOrder(orderId, {
      status: OrderStatus.Canceled,
      updateTime: Date.now(),
    })

    console.log(`[FallbackClient] Order cancelled: ${orderId}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async getOrders(): ApiPromise<Order[]> {
    return {
      status: 200,
      data: this.brokerMock.getOrders(),
    }
  }

  async getPositions(): ApiPromise<Position[]> {
    return {
      status: 200,
      data: this.brokerMock.getPositions(),
    }
  }

  async getExecutions(symbol: string): ApiPromise<Execution[]> {
    return {
      status: 200,
      data: this.brokerMock.getExecutionsBySymbol(symbol),
    }
  }

  async getAccountInfo(): ApiPromise<AccountMetainfo> {
    return {
      status: 200,
      data: {
        id: this.brokerMock.getAccountId(),
        name: this.brokerMock.getAccountName(),
      },
    }
  }

  async closePosition(positionId: string, amount?: number): ApiPromise<void> {
    const position = this.brokerMock.getPositionBySymbol(positionId)
    if (!position) {
      console.warn(`[FallbackClient] Position not found: ${positionId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    const closeQty = amount !== undefined ? amount : position.qty
    const closingSide = position.side === Side.Buy ? Side.Sell : Side.Buy

    const closingOrder: Order = {
      id: `CLOSE-ORDER-${Date.now()}`,
      symbol: position.symbol,
      type: 2,
      side: closingSide,
      qty: closeQty,
      status: OrderStatus.Working,
    }

    this.brokerMock.addOrder(closingOrder)

    console.log(`[FallbackClient] Closing order created for position ${positionId}: ${closingOrder.id}, qty: ${closeQty}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async editPositionBrackets(positionId: string, brackets: Brackets, customFields?: CustomInputFieldsValues): ApiPromise<void> {
    const position = this.brokerMock.getPositionBySymbol(positionId)
    if (!position) {
      console.warn(`[FallbackClient] Position not found: ${positionId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    this.brokerMock.addPositionBracketOrders(positionId, {
      stopLoss: brackets.stopLoss,
      takeProfit: brackets.takeProfit,
    })

    console.log(`[FallbackClient] Position brackets edited: ${positionId}`, brackets, customFields)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async leverageInfo(leverageInfoParams: LeverageInfoParams): ApiPromise<LeverageInfo> {
    return {
      status: 200,
      data: {
        title: `Leverage for ${leverageInfoParams.symbol}`,
        leverage: 10,
        min: 1,
        max: 100,
        step: 1,
      },
    }
  }

  async setLeverage(leverageSetParams: LeverageSetParams): ApiPromise<LeverageSetResult> {
    console.log(`[FallbackClient] Leverage set: ${leverageSetParams.symbol} = ${leverageSetParams.leverage}x`)

    return {
      status: 200,
      data: {
        leverage: leverageSetParams.leverage,
      },
    }
  }

  async previewLeverage(leverageSetParams: LeverageSetParams): ApiPromise<LeveragePreviewResult> {
    const warnings: string[] = []
    const infos: string[] = []
    const errors: string[] = []

    infos.push(`Setting leverage to ${leverageSetParams.leverage}x for ${leverageSetParams.symbol}`)

    if (leverageSetParams.leverage > 50) {
      warnings.push('High leverage increases risk significantly')
    }

    if (leverageSetParams.leverage < 1 || leverageSetParams.leverage > 100) {
      errors.push('Leverage must be between 1x and 100x')
    }

    return {
      status: 200,
      data: {
        infos: infos.length > 0 ? infos : undefined,
        warnings: warnings.length > 0 ? warnings : undefined,
        errors: errors.length > 0 ? errors : undefined,
      },
    }
  }
}

export class BrokerTerminalService implements IBrokerWithoutRealtime {
  private readonly _hostAdapter: IBrokerConnectionAdapterHost

  private readonly _quotesProvider: IDatafeedQuotesApi

  // Client adapters
  private readonly _apiFallback?: ApiInterface
  private readonly apiAdapter: ApiInterface
  private readonly _wsAdapter: WsAdapter
  private readonly _wsFallback?: Partial<WsAdapterType>

  // UI state (managed by service, not client)
  private balance: IWatchedValue<number>
  private equity: IWatchedValue<number>
  private readonly startingBalance = 100000

  private readonly accountId: string
  private brokerConnectionStatus: ConnectionStatusType = ConnectionStatus.Disconnected

  constructor(
    host: IBrokerConnectionAdapterHost,
    quotesProvider: IDatafeedQuotesApi,
    brokerMock?: BrokerMock,
  ) {
    this._hostAdapter = host
    this._quotesProvider = quotesProvider
    this.apiAdapter = new ApiAdapter()
    this._wsAdapter = new WsAdapter()

    if (brokerMock) {
      this._apiFallback = new ApiFallback(brokerMock)
      this._wsFallback = new WsFallback(brokerMock)
    }

    // Initialize balance and equity first to ensure they exist before any UI calls
    this.balance = this._hostAdapter.factory.createWatchedValue(this.startingBalance)
    this.equity = this._hostAdapter.factory.createWatchedValue(this.startingBalance)

    // KNOWN ISSUE: listenerId must match currentAccount() return value
    // See BROKER-TERMINAL-SERVICE.md "Known Issues" section
    this.accountId = "ACCOUNT-01" // `ACCOUNT-${Math.random().toString(36).substring(2, 15)}`

    this.setupWebSocketHandlers()
      .then(() => {
        this.brokerConnectionStatus = ConnectionStatus.Connected
        console.log('[BrokerTerminalService] WebSocket subscriptions ready')
        this._hostAdapter.connectionStatusUpdate(this.brokerConnectionStatus, {
          message: 'Broker data subscriptions established'
        })
      })
      .catch((error) => {
        this.brokerConnectionStatus = ConnectionStatus.Error
        console.error('[BrokerTerminalService] WebSocket setup failed:', error)
        this._hostAdapter.connectionStatusUpdate(this.brokerConnectionStatus, {
          message: 'Failed to establish broker data subscriptions'
        })
      })

  }

  private _getApiAdapter(): ApiInterface {
    return this._apiFallback ?? this.apiAdapter
  }

  private _getWsAdapter(): WsAdapterType | Partial<WsAdapterType> {
    return this._wsFallback ?? this._wsAdapter
  }

  /**
   * Setup WebSocket subscription handlers for broker events
   * Subscribes to orders, positions, executions, equity, and broker connection status
   */
  private async setupWebSocketHandlers(): Promise<(void | undefined)[]> {
    // Order updates
    return Promise.all([
      this._getWsAdapter().orders?.subscribe(
        'orders',
        { accountId: this.accountId },
        (order: Order) => {
          console.log('Received order update via WebSocket:', order)
          this._hostAdapter.orderUpdate(order)

          // Show notification on fill
          if (order.status === OrderStatus.Filled) {
            this._hostAdapter.showNotification(
              'Order Filled',
              `${order.symbol} ${order.side === 1 ? 'Buy' : 'Sell'} ${order.qty} @ ${order.avgPrice ?? 'market'}`,
              NotificationType.Success
            )
          }
        }
      ).then((response) => {
        console.log('Subscribed to WebSocket order updates:', response)
      }).catch((error) => {
        console.error('Failed to subscribe to WebSocket order updates:', error)
      }),

      // Position updates
      this._getWsAdapter().positions?.subscribe(
        'positions',
        { accountId: this.accountId },
        (position: Position) => {
          console.log('Received position update via WebSocket:', position)
          this._hostAdapter.positionUpdate(position)
        }
      ).then((response) => {
        console.log('Subscribed to WebSocket position updates:', response)
      }).catch((error) => {
        console.error('Failed to subscribe to WebSocket position updates:', error)
      }),

      // Execution updates
      this._getWsAdapter().executions?.subscribe(
        'executions',
        { accountId: this.accountId },
        (execution: Execution) => {
          console.log('Received execution update via WebSocket:', execution)
          this._hostAdapter.executionUpdate(execution)
        }
      ).then((response) => {
        console.log('Subscribed to WebSocket execution updates:', response)
      }).catch((error) => {
        console.error('Failed to subscribe to WebSocket execution updates:', error)
      }),
      // Equity updates
      this._getWsAdapter().equity?.subscribe(
        'equity',
        { accountId: this.accountId },
        (data: EquityData) => {
          this._hostAdapter.equityUpdate(data.equity)

          // Update reactive balance/equity values
          if (data.balance !== undefined && data.balance !== null) {
            console.log('Updating balance to:', data.balance)
            this.balance.setValue(data.balance)
          }
          if (data.equity !== undefined && data.equity !== null) {
            console.log('Updating equity to:', data.equity)
            this.equity.setValue(data.equity)
          }
        }
      ).then((response) => {
        console.log('Subscribed to WebSocket equity updates:', response)
      }).catch((error) => {
        console.error('Failed to subscribe to WebSocket equity updates:', error)
      }),

      // Broker connection status (backend ↔ real broker)
      this._getWsAdapter().brokerConnection?.subscribe(
        'broker-connection',
        { accountId: this.accountId },
        (data: BrokerConnectionStatus) => {
          this.brokerConnectionStatus = data.status
          this._hostAdapter.connectionStatusUpdate(data.status, {
            message: data.message ?? undefined,
            disconnectType: data.disconnectType ?? undefined,
          })

          // Notify user on connection changes
          if (data.status === ConnectionStatus.Disconnected) {
            this._hostAdapter.showNotification(
              'Broker Disconnected',
              data.message ?? 'Connection to broker lost',
              NotificationType.Error
            )
          } else if (data.status === ConnectionStatus.Connected) {
            this._hostAdapter.showNotification(
              'Broker Connected',
              data.message ?? 'Successfully connected to broker',
              NotificationType.Success
            )
          }
        }
      ).then((response) => {
        console.log('Subscribed to WebSocket broker-connection updates:', response)
      }).catch((error) => {
        console.error('Failed to subscribe to WebSocket broker-connection updates:', error)
      }),
    ])
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
    const result = [response.data]
    console.log(`BrokerTerminalService.accountsMetainfo() => `, result)
    return result
  }

  async orders(): Promise<Order[]> {
    const response = await this._getApiAdapter().getOrders()
    console.log(`BrokerTerminalService.orders() => `, response.data)
    return response.data
  }

  async positions(): Promise<Position[]> {
    const response = await this._getApiAdapter().getPositions()
    console.log(`BrokerTerminalService.positions() => `, response.data)
    return response.data
  }

  async executions(symbol: string): Promise<Execution[]> {
    const response = await this._getApiAdapter().getExecutions(symbol)
    console.log(`BrokerTerminalService.executions[${symbol}] => `, response.data)
    return response.data
  }

  async symbolInfo(symbol: string): Promise<InstrumentInfo> {
    const mintick = await this._hostAdapter.getSymbolMinTick(symbol)
    const pipSize = mintick // Pip size can differ from minTick
    const accountCurrencyRate = 1 // Account currency rate
    const pointValue = 1 // USD value of 1 point of price

    const result = {
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
    console.debug(`BrokerTerminalService.symbolInfo[${symbol}] => ${JSON.stringify(result)}`)
    return result
  }

  async previewOrder(order: PreOrder): Promise<OrderPreviewResult> {
    const response = await this._getApiAdapter().previewOrder(order)
    console.debug(`BrokerTerminalService.previewOrder[${JSON.stringify(order)}] => `, response.data)
    return response.data
  }

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const response = await this._getApiAdapter().placeOrder(order)
    console.log(`BrokerTerminalService.placeOrder[${JSON.stringify(order)}] => `, response.data)
    return response.data
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    await this._getApiAdapter().modifyOrder(order, confirmId)
    console.log(`BrokerTerminalService.modifyOrder[order: ${JSON.stringify(order)}, confirmId: ${confirmId}] => completed`)
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this._getApiAdapter().cancelOrder(orderId)
    console.log(`BrokerTerminalService.cancelOrder[${orderId}] => completed`)
  }

  async chartContextMenuActions(
    context: TradeContext,
    options?: DefaultContextMenuActionsParams
  ): Promise<ActionMetaInfo[]> {
    const result = this._hostAdapter.defaultContextMenuActions(context, options)
    console.log(`BrokerTerminalService.chartContextMenuActions[${JSON.stringify(context)}] => `, result)
    return result
  }

  async isTradable(symbol: string): Promise<boolean | IsTradableResult> {
    console.log(`BrokerTerminalService.isTradable[${symbol}] => true`)
    return true
  }

  async formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter> {
    return this._hostAdapter.defaultFormatter(symbol, alignToMinMove)
  }

  currentAccount(): AccountId {
    // KNOWN ISSUE: This returns 'DEMO-ACCOUNT' but listenerId is dynamic (e.g., 'ACCOUNT-abc123')
    // causing AccountId mismatch between currentAccount() and WebSocket subscriptions.
    // This breaks Account Manager rendering with "Value is undefined" error.
    // See BROKER-TERMINAL-SERVICE.md "Known Issues" section for details.
    //
    // Must be synchronous (TradingView requirement) - cannot await backend call.
    // TODO: Fetch AccountId from backend during app initialization, store it,
    // and use the same value here and in WebSocket subscriptions.
    return 'DEMO-ACCOUNT' as AccountId
  }

  connectionStatus(): ConnectionStatusType {
    return ConnectionStatus.Connected // this.brokerConnectionStatus
  }

  async closePosition(positionId: string, amount?: number): Promise<void> {
    await this._getApiAdapter().closePosition(positionId, amount)
    console.log(`BrokerTerminalService.closePosition[${positionId}, amount: ${amount}] => completed`)
  }

  async editPositionBrackets(positionId: string, brackets: Brackets, customFields?: CustomInputFieldsValues): Promise<void> {
    await this._getApiAdapter().editPositionBrackets(positionId, brackets, customFields)
    console.log(`BrokerTerminalService.editPositionBrackets[${positionId}] => brackets: ${JSON.stringify(brackets)}, customFields: ${JSON.stringify(customFields)} => completed`)
  }

  async leverageInfo(leverageInfoParams: LeverageInfoParams): Promise<LeverageInfo> {
    const response = await this._getApiAdapter().leverageInfo(leverageInfoParams)
    console.log(`BrokerTerminalService.leverageInfo[${JSON.stringify(leverageInfoParams)}] => ${JSON.stringify(response.data)}`)
    return response.data
  }

  async setLeverage(leverageSetParams: LeverageSetParams): Promise<LeverageSetResult> {
    const response = await this._getApiAdapter().setLeverage(leverageSetParams)
    console.log(`BrokerTerminalService.setLeverage[${JSON.stringify(leverageSetParams)}] => ${JSON.stringify(response.data)}`)
    return response.data
  }

  async previewLeverage(leverageSetParams: LeverageSetParams): Promise<LeveragePreviewResult> {
    const response = await this._getApiAdapter().previewLeverage(leverageSetParams)
    console.log(`BrokerTerminalService.previewLeverage[${JSON.stringify(leverageSetParams)}] => ${JSON.stringify(response.data)}`)
    return response.data
  }
}
