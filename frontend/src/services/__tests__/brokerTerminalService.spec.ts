/**
 * @vitest-environment node
 */

import type {
  IBrokerConnectionAdapterHost,
  IDatafeedQuotesApi,
  IWatchedValue,
  PreOrder,
} from '@public/trading_terminal'
import { OrderStatus, OrderType, Side } from '@public/trading_terminal'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { addTestPosition, BrokerTerminalService, resetApiFallbackState } from '../brokerTerminalService'

/**
 * Test suite for BrokerTerminalService
 *
 * Tests the simplified fallback broker client logic:
 * - Order preview with detailed sections
 * - Order placement without execution simulation
 * - Order modification
 * - Order cancellation
 * - Account info retrieval
 * - Service configuration (mock vs backend)
 * - Position closing (full and partial)
 * - Position bracket editing
 * - Leverage operations
 *
 * NOTE: The ApiFallback no longer simulates order execution or position management.
 * It only stores order records and returns them when queried.
 */
describe('BrokerTerminalService', () => {
  let brokerService: BrokerTerminalService
  let mockHost: IBrokerConnectionAdapterHost
  let mockDatafeed: IDatafeedQuotesApi

  beforeEach(() => {
    // Reset ApiFallback state before each test
    resetApiFallbackState()

    // Mock TradingView host
    mockHost = {
      defaultContextMenuActions: vi.fn().mockResolvedValue([]),
      defaultFormatter: vi.fn().mockResolvedValue({
        format: vi.fn((value: number) => value.toFixed(2)),
      }),
      getSymbolMinTick: vi.fn().mockResolvedValue(0.01),
      factory: {
        createWatchedValue: vi.fn((value: number) => {
          const mock: IWatchedValue<number> = {
            value: () => value,
            setValue: vi.fn(),
            subscribe: vi.fn(),
            unsubscribe: vi.fn(),
            when: vi.fn(),
          }
          return mock
        }),
      },
    } as unknown as IBrokerConnectionAdapterHost

    // Mock datafeed
    mockDatafeed = {} as IDatafeedQuotesApi

    // Use fallback client (mock = true)
    brokerService = new BrokerTerminalService(mockHost, mockDatafeed, true)

    // Clear all mocks
    vi.clearAllMocks()
  })

  describe('Order Preview', () => {
    it('should generate order preview with order details section', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      }

      const preview = await brokerService.previewOrder(preOrder)

      expect(preview.sections).toBeDefined()
      expect(preview.sections.length).toBeGreaterThan(0)

      const orderDetailsSection = preview.sections.find((s) => s.header === 'Order Details')
      expect(orderDetailsSection).toBeDefined()
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Symbol', value: 'AAPL' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Side', value: 'Buy' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Quantity', value: '100.00' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Order Type', value: 'Limit' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Limit Price', value: '$150.00' })
    })

    it('should generate cost analysis section', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      }

      const preview = await brokerService.previewOrder(preOrder)

      const costSection = preview.sections.find((s) => s.header === 'Cost Analysis')
      expect(costSection).toBeDefined()
      expect(costSection?.rows.length).toBeGreaterThan(0)
      expect(costSection?.rows.some((r) => r.title === 'Estimated Price')).toBe(true)
      expect(costSection?.rows.some((r) => r.title === 'Order Value')).toBe(true)
      expect(costSection?.rows.some((r) => r.title === 'Commission')).toBe(true)
      expect(costSection?.rows.some((r) => r.title === 'Margin Required')).toBe(true)
      expect(costSection?.rows.some((r) => r.title === 'Total Cost')).toBe(true)
    })

    it('should generate risk management section when brackets are present', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
        takeProfit: 110.0,
        stopLoss: 90.0,
      }

      const preview = await brokerService.previewOrder(preOrder)

      const riskSection = preview.sections.find((s) => s.header === 'Risk Management')
      expect(riskSection).toBeDefined()
      expect(riskSection?.rows.some((r) => r.title === 'Take Profit')).toBe(true)
      expect(riskSection?.rows.some((r) => r.title === 'Stop Loss')).toBe(true)
    })

    it('should include confirmation ID in preview', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      }

      const preview = await brokerService.previewOrder(preOrder)

      expect(preview.confirmId).toBeDefined()
      expect(preview.confirmId).toMatch(/^PREVIEW-/)
    })

    it('should include warnings for market orders', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      }

      const preview = await brokerService.previewOrder(preOrder)

      expect(preview.warnings).toBeDefined()
      expect(preview.warnings?.length).toBeGreaterThan(0)
      expect(preview.warnings).toContain('Market orders execute immediately at current market price')
    })

    it('should include warnings for large orders', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 1500,
      }

      const preview = await brokerService.previewOrder(preOrder)

      expect(preview.warnings).toBeDefined()
      expect(preview.warnings).toContain('Large order size may experience slippage')
    })

    it('should handle stop orders correctly', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Stop,
        side: Side.Sell,
        qty: 50,
        stopPrice: 95.0,
      }

      const preview = await brokerService.previewOrder(preOrder)

      const orderDetailsSection = preview.sections.find((s) => s.header === 'Order Details')
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Order Type', value: 'Stop' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Stop Price', value: '$95.00' })
    })

    it('should handle stop limit orders correctly', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.StopLimit,
        side: Side.Buy,
        qty: 75,
        stopPrice: 105.0,
        limitPrice: 106.0,
      }

      const preview = await brokerService.previewOrder(preOrder)

      const orderDetailsSection = preview.sections.find((s) => s.header === 'Order Details')
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Order Type', value: 'Stop Limit' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Stop Price', value: '$105.00' })
      expect(orderDetailsSection?.rows).toContainEqual({ title: 'Limit Price', value: '$106.00' })
    })
  })

  describe('Order Placement', () => {
    it('should place order and return order ID', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      }

      const result = await brokerService.placeOrder(preOrder)

      expect(result.orderId).toBeDefined()
      expect(result.orderId).toMatch(/^ORDER-/)
    })

    it('should create order with Working status', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      }

      await brokerService.placeOrder(preOrder)

      const orders = await brokerService.orders()
      expect(orders.length).toBe(1)
      expect(orders[0].status).toBe(OrderStatus.Working)
      expect(orders[0].symbol).toBe('AAPL')
      expect(orders[0].qty).toBe(100)
    })

    it('should preserve order type and side', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Stop,
        side: Side.Sell,
        qty: 50,
        stopPrice: 95.0,
      }

      await brokerService.placeOrder(preOrder)

      const orders = await brokerService.orders()
      expect(orders[0].type).toBe(OrderType.Stop)
      expect(orders[0].side).toBe(Side.Sell)
      expect(orders[0].stopPrice).toBe(95.0)
    })

    it('should preserve bracket orders (TP/SL)', async () => {
      const preOrder: PreOrder = {
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
        takeProfit: 110.0,
        stopLoss: 90.0,
      }

      await brokerService.placeOrder(preOrder)

      const orders = await brokerService.orders()
      expect(orders[0].takeProfit).toBe(110.0)
      expect(orders[0].stopLoss).toBe(90.0)
    })

    it('should place multiple orders independently', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      await brokerService.placeOrder({
        symbol: 'GOOGL',
        type: OrderType.Limit,
        side: Side.Sell,
        qty: 50,
        limitPrice: 2500.0,
      })

      const orders = await brokerService.orders()
      expect(orders.length).toBe(2)
      expect(orders[0].symbol).toBe('AAPL')
      expect(orders[1].symbol).toBe('GOOGL')
    })
  })

  describe('Order Modification', () => {
    it('should modify order quantity', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      const orders = await brokerService.orders()
      const originalOrder = orders[0]

      await brokerService.modifyOrder({
        ...originalOrder,
        qty: 150,
      })

      const modifiedOrders = await brokerService.orders()
      expect(modifiedOrders[0].qty).toBe(150)
    })

    it('should modify limit price', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      const orders = await brokerService.orders()
      const originalOrder = orders[0]

      await brokerService.modifyOrder({
        ...originalOrder,
        limitPrice: 155.0,
      })

      const modifiedOrders = await brokerService.orders()
      expect(modifiedOrders[0].limitPrice).toBe(155.0)
    })

    it('should modify stop price', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Stop,
        side: Side.Sell,
        qty: 100,
        stopPrice: 95.0,
      })

      const orders = await brokerService.orders()
      const originalOrder = orders[0]

      await brokerService.modifyOrder({
        ...originalOrder,
        stopPrice: 93.0,
      })

      const modifiedOrders = await brokerService.orders()
      expect(modifiedOrders[0].stopPrice).toBe(93.0)
    })

    it('should use confirmId when provided', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      const orders = await brokerService.orders()
      const originalOrderId = orders[0].id

      // Modify using the confirmId (which should be the order ID)
      await brokerService.modifyOrder(
        {
          ...orders[0],
          qty: 200,
        },
        originalOrderId,
      )

      const modifiedOrders = await brokerService.orders()
      expect(modifiedOrders[0].qty).toBe(200)
    })
  })

  describe('Order Cancellation', () => {
    it('should cancel order by ID', async () => {
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      await brokerService.cancelOrder(result.orderId!)

      const orders = await brokerService.orders()
      expect(orders[0].status).toBe(OrderStatus.Canceled)
    })

    it('should set updateTime on cancelled order', async () => {
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      await brokerService.cancelOrder(result.orderId!)

      const orders = await brokerService.orders()
      expect(orders[0].updateTime).toBeDefined()
    })

    it('should keep cancelled order in order list', async () => {
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      await brokerService.cancelOrder(result.orderId!)

      const orders = await brokerService.orders()
      expect(orders.length).toBe(1)
      expect(orders[0].id).toBe(result.orderId)
    })
  })

  describe('Position Queries', () => {
    it('should return empty positions list initially', async () => {
      const positions = await brokerService.positions()
      expect(positions).toEqual([])
    })

    it('should return empty positions after placing orders (no execution simulation)', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      const positions = await brokerService.positions()
      expect(positions).toEqual([])
    })
  })

  describe('Execution Queries', () => {
    it('should return empty executions list initially', async () => {
      const executions = await brokerService.executions('AAPL')
      expect(executions).toEqual([])
    })

    it('should return empty executions after placing orders (no execution simulation)', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      const executions = await brokerService.executions('AAPL')
      expect(executions).toEqual([])
    })
  })

  describe('Account Information', () => {
    it('should return account metadata', async () => {
      const accounts = await brokerService.accountsMetainfo()

      expect(accounts).toBeDefined()
      expect(accounts.length).toBe(1)
      expect(accounts[0].id).toBe('DEMO-001')
      expect(accounts[0].name).toBe('Demo Trading Account')
    })

    it('should return current account ID', () => {
      const accountId = brokerService.currentAccount()
      expect(accountId).toBe('DEMO-001')
    })

    it('should return account manager info with balance and equity', () => {
      const accountInfo = brokerService.accountManagerInfo()

      expect(accountInfo.accountTitle).toBe('Mock Trading Account')
      expect(accountInfo.summary).toBeDefined()
      expect(accountInfo.summary.length).toBeGreaterThan(0)

      const balanceField = accountInfo.summary.find((s) => s.text === 'Balance')
      expect(balanceField).toBeDefined()
      expect(balanceField?.wValue).toBeDefined()

      const equityField = accountInfo.summary.find((s) => s.text === 'Equity')
      expect(equityField).toBeDefined()
      expect(equityField?.wValue).toBeDefined()
    })

    it('should configure order columns in account manager', () => {
      const accountInfo = brokerService.accountManagerInfo()

      expect(accountInfo.orderColumns).toBeDefined()
      expect(accountInfo.orderColumns.length).toBeGreaterThan(0)
      expect(accountInfo.orderColumns.some((col) => col.id === 'symbol')).toBe(true)
      expect(accountInfo.orderColumns.some((col) => col.id === 'side')).toBe(true)
      expect(accountInfo.orderColumns.some((col) => col.id === 'qty')).toBe(true)
      expect(accountInfo.orderColumns.some((col) => col.id === 'status')).toBe(true)
    })

    it('should configure position columns in account manager', () => {
      const accountInfo = brokerService.accountManagerInfo()

      expect(accountInfo.positionColumns).toBeDefined()
      expect(accountInfo.positionColumns!.length).toBeGreaterThan(0)
      expect(accountInfo.positionColumns!.some((col) => col.id === 'symbol')).toBe(true)
      expect(accountInfo.positionColumns!.some((col) => col.id === 'side')).toBe(true)
      expect(accountInfo.positionColumns!.some((col) => col.id === 'qty')).toBe(true)
      expect(accountInfo.positionColumns!.some((col) => col.id === 'avgPrice')).toBe(true)
    })
  })

  describe('Symbol Information', () => {
    it('should return symbol info with min/max quantity', async () => {
      const symbolInfo = await brokerService.symbolInfo('AAPL')

      expect(symbolInfo.qty).toBeDefined()
      expect(symbolInfo.qty.min).toBe(1)
      expect(symbolInfo.qty.max).toBe(1e12)
      expect(symbolInfo.qty.step).toBe(1)
    })

    it('should return pip and tick values', async () => {
      const symbolInfo = await brokerService.symbolInfo('AAPL')

      expect(symbolInfo.pipValue).toBeDefined()
      expect(symbolInfo.pipSize).toBeDefined()
      expect(symbolInfo.minTick).toBeDefined()
    })
  })

  describe('Trading Operations', () => {
    it('should report symbol as tradable', async () => {
      const isTradable = await brokerService.isTradable('AAPL')
      expect(isTradable).toBe(true)
    })

    it('should return formatter for symbol', async () => {
      const formatter = await brokerService.formatter('AAPL', false)
      expect(formatter).toBeDefined()
    })

    it('should return chart context menu actions', async () => {
      const actions = await brokerService.chartContextMenuActions({
        symbol: 'AAPL',
        displaySymbol: 'AAPL',
        value: 150.0,
        formattedValue: '$150.00',
        last: 150.0,
      })

      expect(actions).toBeDefined()
      expect(Array.isArray(actions)).toBe(true)
    })
  })

  describe('Connection Status', () => {
    it('should report connected status', () => {
      const status = brokerService.connectionStatus()
      expect(status).toBe(1) // ConnectionStatus.Connected
    })
  })

  describe('Position Closing', () => {
    it('should close position fully', async () => {
      addTestPosition('AAPL-POS-1', 'AAPL', 100, Side.Buy, 150.0)

      await brokerService.closePosition('AAPL-POS-1')

      const positions = await brokerService.positions()
      expect(positions.length).toBe(0)
    })

    it('should close position partially', async () => {
      addTestPosition('AAPL-POS-2', 'AAPL', 100, Side.Buy, 150.0)

      await brokerService.closePosition('AAPL-POS-2', 40)

      const positions = await brokerService.positions()
      expect(positions[0].qty).toBe(60)
    })
  })

  describe('Position Bracket Editing', () => {
    it('should edit position brackets', async () => {
      addTestPosition('AAPL-POS-3', 'AAPL', 100, Side.Buy, 150.0)

      await brokerService.editPositionBrackets('AAPL-POS-3', {
        stopLoss: 140.0,
        takeProfit: 160.0,
      })

      const positions = await brokerService.positions()
      expect(positions[0].stopLoss).toBe(140.0)
      expect(positions[0].takeProfit).toBe(160.0)
    })
  })

  describe('Leverage Operations', () => {
    it('should return leverage info', async () => {
      const leverageInfo = await brokerService.leverageInfo({
        symbol: 'AAPL',
        orderType: OrderType.Market,
        side: Side.Buy,
      })

      expect(leverageInfo.title).toBe('Leverage for AAPL')
      expect(leverageInfo.leverage).toBe(10)
      expect(leverageInfo.min).toBe(1)
      expect(leverageInfo.max).toBe(100)
      expect(leverageInfo.step).toBe(1)
    })

    it('should set leverage', async () => {
      const result = await brokerService.setLeverage({
        symbol: 'AAPL',
        orderType: OrderType.Market,
        side: Side.Buy,
        leverage: 20,
      })

      expect(result.leverage).toBe(20)
    })

    it('should preview leverage', async () => {
      const preview = await brokerService.previewLeverage({
        symbol: 'AAPL',
        orderType: OrderType.Market,
        side: Side.Buy,
        leverage: 10,
      })

      expect(preview.infos).toBeDefined()
    })
  })
})
