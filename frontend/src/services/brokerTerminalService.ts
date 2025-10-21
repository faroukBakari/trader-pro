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
import { ConnectionStatus, OrderStatus, StandardFormatterName } from '@public/trading_terminal'
import { DatafeedService } from './datafeedService.js'

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

// Private state management
const _orderById = new Map<string, Order>()
const _positions = new Map<string, Position>()
const _executions: Execution[] = []
const _accountId: AccountId = 'DEMO-001' as AccountId
const _accountName = 'Demo Trading Account'

/**
 * Reset fallback state for testing purposes
 * ONLY use this in test environments
 */
export function resetApiFallbackState(): void {
  _orderById.clear()
  _positions.clear()
  _executions.length = 0
}

/**
 * Add a test position to fallback state
 * ONLY use this in test environments
 */
export function addTestPosition(positionId: string, symbol: string, qty: number, side: number, avgPrice: number = 150.0): void {
  _positions.set(positionId, {
    id: positionId,
    symbol,
    qty,
    side,
    avgPrice,
  })
}

class ApiFallback implements ApiInterface {

  constructor() { }

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
    const orderId = `ORDER-${_orderById.size + 1}`

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

    _orderById.set(orderId, newOrder)

    console.log(`[FallbackClient] Order created: ${orderId}`)

    return {
      status: 200,
      data: { orderId },
    }
  }

  async modifyOrder(order: Order, confirmId?: string): ApiPromise<void> {
    const originalOrder = _orderById.get(confirmId ?? order.id)
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

    console.log(`[FallbackClient] Order modified: ${originalOrder.id}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async cancelOrder(orderId: string): ApiPromise<void> {
    const order = _orderById.get(orderId)
    if (!order) {
      console.warn(`[FallbackClient] Order not found: ${orderId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    order.status = OrderStatus.Canceled
    order.updateTime = Date.now()

    console.log(`[FallbackClient] Order cancelled: ${orderId}`)

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async getOrders(): ApiPromise<Order[]> {
    return {
      status: 200,
      data: Array.from(_orderById.values()),
    }
  }

  async getPositions(): ApiPromise<Position[]> {
    return {
      status: 200,
      data: Array.from(_positions.values()),
    }
  }

  async getExecutions(symbol: string): ApiPromise<Execution[]> {
    return {
      status: 200,
      data: _executions.filter((exec) => exec.symbol === symbol),
    }
  }

  async getAccountInfo(): ApiPromise<AccountMetainfo> {
    return {
      status: 200,
      data: {
        id: _accountId as AccountId,
        name: _accountName,
      },
    }
  }

  async closePosition(positionId: string, amount?: number): ApiPromise<void> {
    const position = _positions.get(positionId)
    if (!position) {
      console.warn(`[FallbackClient] Position not found: ${positionId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    if (amount !== undefined) {
      if (amount >= position.qty) {
        _positions.delete(positionId)
        console.log(`[FallbackClient] Position fully closed: ${positionId}`)
      } else {
        position.qty -= amount
        console.log(`[FallbackClient] Position partially closed: ${positionId}, reduced by ${amount}, remaining: ${position.qty}`)
      }
    } else {
      _positions.delete(positionId)
      console.log(`[FallbackClient] Position fully closed: ${positionId}`)
    }

    return {
      status: 200,
      data: undefined as void,
    }
  }

  async editPositionBrackets(positionId: string, brackets: Brackets, customFields?: CustomInputFieldsValues): ApiPromise<void> {
    const position = _positions.get(positionId)
    if (!position) {
      console.warn(`[FallbackClient] Position not found: ${positionId}`)
      return {
        status: 404,
        data: undefined as void,
      }
    }

    position.stopLoss = brackets.stopLoss
    position.takeProfit = brackets.takeProfit

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
  private readonly _quotesFallback: IDatafeedQuotesApi

  // Client adapters
  private readonly apiFallback: ApiInterface
  private readonly apiAdapter: ApiInterface

  // Mock flag
  private readonly mock: boolean

  // UI state (managed by service, not client)
  private readonly balance: IWatchedValue<number>
  private readonly equity: IWatchedValue<number>
  private readonly startingBalance = 100000

  constructor(
    host: IBrokerConnectionAdapterHost,
    quotesProvider: IDatafeedQuotesApi,
    mock: boolean = true // Default to fallback for safety
  ) {
    this.mock = mock
    this._hostAdapter = host
    this._quotesProvider = quotesProvider
    this._quotesFallback = new DatafeedService({ mock: true })
    this.apiAdapter = new ApiAdapter()
    this.apiFallback = new ApiFallback()

    // TODO setup subscriptions for these values from client
    this.balance = this._hostAdapter.factory.createWatchedValue(this.startingBalance)
    this.equity = this._hostAdapter.factory.createWatchedValue(this.startingBalance)
  }

  private _getApiAdapter(mock: boolean = this.mock): ApiInterface {
    return mock ? this.apiFallback : this.apiAdapter
  }

  private _getQuotesProvider(mock: boolean = this.mock): IDatafeedQuotesApi {
    return mock ? this._quotesFallback : this._quotesProvider
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
    const mintick = await this._hostAdapter.getSymbolMinTick(symbol)
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

  async previewOrder(order: PreOrder): Promise<OrderPreviewResult> {
    const response = await this._getApiAdapter().previewOrder(order)
    return response.data
  }

  async placeOrder(order: PreOrder): Promise<PlaceOrderResult> {
    const response = await this._getApiAdapter().placeOrder(order)
    return response.data
  }

  async modifyOrder(order: Order, confirmId?: string): Promise<void> {
    await this._getApiAdapter().modifyOrder(order, confirmId)
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this._getApiAdapter().cancelOrder(orderId)
  }

  async chartContextMenuActions(
    context: TradeContext,
    options?: DefaultContextMenuActionsParams
  ): Promise<ActionMetaInfo[]> {
    return this._hostAdapter.defaultContextMenuActions(context, options)
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async isTradable(symbol: string): Promise<boolean | IsTradableResult> {
    return true
  }

  async formatter(symbol: string, alignToMinMove: boolean): Promise<INumberFormatter> {
    return this._hostAdapter.defaultFormatter(symbol, alignToMinMove)
  }

  currentAccount(): AccountId {
    return 'DEMO-001' as AccountId
  }

  connectionStatus(): ConnectionStatusType {
    return ConnectionStatus.Connected
  }

  async closePosition(positionId: string, amount?: number): Promise<void> {
    await this._getApiAdapter().closePosition(positionId, amount)
  }

  async editPositionBrackets(positionId: string, brackets: Brackets, customFields?: CustomInputFieldsValues): Promise<void> {
    await this._getApiAdapter().editPositionBrackets(positionId, brackets, customFields)
  }

  async leverageInfo(leverageInfoParams: LeverageInfoParams): Promise<LeverageInfo> {
    const response = await this._getApiAdapter().leverageInfo(leverageInfoParams)
    return response.data
  }

  async setLeverage(leverageSetParams: LeverageSetParams): Promise<LeverageSetResult> {
    const response = await this._getApiAdapter().setLeverage(leverageSetParams)
    return response.data
  }

  async previewLeverage(leverageSetParams: LeverageSetParams): Promise<LeveragePreviewResult> {
    const response = await this._getApiAdapter().previewLeverage(leverageSetParams)
    return response.data
  }
}
