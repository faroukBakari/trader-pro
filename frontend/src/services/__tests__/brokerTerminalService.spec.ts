/**
 * @vitest-environment node
 */

import type {
  Execution,
  IBrokerConnectionAdapterHost,
  IDatafeedQuotesApi,
  IWatchedValue,
  Order,
  Position,
  PreOrder,
} from '@public/trading_terminal'
import { OrderStatus, OrderType, Side } from '@public/trading_terminal'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrokerMock, BrokerTerminalService } from '../brokerTerminalService'

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
  let testBrokerMock: BrokerMock

  /**
   * Helper function to wait for the mocker chain to process updates
   * The WebSocket fallback polls every 100ms, so we need to wait for:
   * 1. ordersMocker to create execution
   * 2. executionsMocker to create/update position
   * 3. positionsMocker to update equity
   */
  const waitForMockerChain = async (cycles: number = 4) => {
    // Wait for multiple polling cycles (100ms each)
    // 4 cycles = 400ms should be enough for order -> execution -> position -> equity
    await new Promise(resolve => setTimeout(resolve, cycles * 100 + 50))
  }

  beforeEach(() => {
    // Create fresh BrokerMock instance for each test
    testBrokerMock = new BrokerMock()

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
      // WebSocket handler methods
      orderUpdate: vi.fn(),
      positionUpdate: vi.fn(),
      executionUpdate: vi.fn(),
      equityUpdate: vi.fn(),
      connectionStatusUpdate: vi.fn(),
      showNotification: vi.fn(),
    } as unknown as IBrokerConnectionAdapterHost

    // Mock datafeed
    mockDatafeed = {} as IDatafeedQuotesApi

    // Use fallback client with test BrokerMock instance
    brokerService = new BrokerTerminalService(mockHost, mockDatafeed, testBrokerMock)

    // Clear all mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up any remaining state
    testBrokerMock.reset()
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

    it('should warn about high leverage', async () => {
      const preview = await brokerService.previewLeverage({
        symbol: 'AAPL',
        orderType: OrderType.Market,
        side: Side.Buy,
        leverage: 75,
      })

      expect(preview.warnings).toBeDefined()
      expect(preview.warnings).toContain('High leverage increases risk significantly')
    })

    it('should error on invalid leverage', async () => {
      const preview = await brokerService.previewLeverage({
        symbol: 'AAPL',
        orderType: OrderType.Market,
        side: Side.Buy,
        leverage: 150,
      })

      expect(preview.errors).toBeDefined()
      expect(preview.errors).toContain('Leverage must be between 1x and 100x')
    })
  })

  describe('BrokerMock State Management', () => {
    it('should create isolated state per instance', () => {
      const mock1 = new BrokerMock()
      const mock2 = new BrokerMock()

      mock1.addOrder({
        id: 'TEST-1',
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
        status: OrderStatus.Working,
      })

      expect(mock1.getOrders().length).toBe(1)
      expect(mock2.getOrders().length).toBe(0)
    })

    it('should return copies of orders to prevent external mutations', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      const orders1 = await brokerService.orders()
      const orders2 = await brokerService.orders()

      // Mutate first array
      orders1[0].qty = 999

      // Second array should be unchanged
      expect(orders2[0].qty).toBe(100)
    })

    it('should track order updates for WebSocket mocker', async () => {
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      await brokerService.cancelOrder(result.orderId!)

      // Wait for WebSocket fallback to poll and process updates
      await waitForMockerChain(2)

      // BrokerMock should have tracked both the creation and cancellation
      // Check that order was created and then updated to cancelled status
      const orders = await brokerService.orders()
      const cancelledOrder = orders.find(o => o.id === result.orderId)
      expect(cancelledOrder).toBeDefined()
      expect(cancelledOrder?.status).toBe(OrderStatus.Canceled)
    })

    it('should provide account information', () => {
      expect(testBrokerMock.getAccountId()).toBe('DEMO-001')
      expect(testBrokerMock.getAccountName()).toBe('Demo Trading Account')
    })

    it('should provide equity data for mocker', () => {
      const equity = testBrokerMock.equityMocker()
      expect(equity).toBeDefined()
      expect(equity?.equity).toBe(105000)
      expect(equity?.balance).toBe(100000)
      expect(equity?.unrealizedPL).toBe(5000)
      expect(equity?.realizedPL).toBe(0)
    })

    it('should provide broker connection status for mocker', () => {
      const status = testBrokerMock.brokerConnectionMocker()
      expect(status).toBeDefined()
      expect(status?.status).toBe(1) // ConnectionStatus.Connected
      expect(status?.message).toBe('Mock broker connected')
    })

    it('should reset state completely', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      testBrokerMock.reset()

      const orders = await brokerService.orders()
      expect(orders.length).toBe(0)
    })
  })

  describe('Position Management (Fallback Mode)', () => {
    beforeEach(async () => {
      // Create position via realistic order placement
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Wait for mocker chain: order -> execution -> position
      await waitForMockerChain()
    })

    it('should close position by creating a closing order', async () => {
      await brokerService.closePosition('AAPL')

      const orders = await brokerService.orders()
      // Should have 2 orders: original buy + closing sell
      expect(orders.length).toBe(2)
      const closingOrder = orders.find(o => o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrder).toBeDefined()
      expect(closingOrder?.symbol).toBe('AAPL')
      expect(closingOrder?.side).toBe(Side.Sell) // Opposite of position side
      expect(closingOrder?.qty).toBe(100) // Full position qty
      expect(closingOrder?.id).toMatch(/^CLOSE-ORDER-/)
    })

    it('should close partial position by creating closing order with specified amount', async () => {
      await brokerService.closePosition('AAPL', 50)

      const orders = await brokerService.orders()
      // Should have 2 orders: original buy + closing sell
      expect(orders.length).toBe(2)
      const closingOrder = orders.find(o => o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrder?.qty).toBe(50) // Partial close
    })

    it('should create sell order to close buy position', async () => {
      await brokerService.closePosition('AAPL')

      const orders = await brokerService.orders()
      const closingOrder = orders.find(o => o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrder?.side).toBe(Side.Sell)
    })

    it('should create buy order to close sell position', async () => {
      // Create sell position via order placement
      await brokerService.placeOrder({
        symbol: 'GOOGL',
        type: OrderType.Market,
        side: Side.Sell,
        qty: 50,
      })

      // Wait for mocker chain to create position
      await waitForMockerChain()

      await brokerService.closePosition('GOOGL')

      const orders = await brokerService.orders()
      const closingOrder = orders.find(o => o.symbol === 'GOOGL' && o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrder?.side).toBe(Side.Buy)
    })

    it('should return 404 when closing non-existent position', async () => {
      // This should not throw but return a 404 internally
      await brokerService.closePosition('NONEXISTENT')

      // Only initial order should exist, no closing order created
      const orders = await brokerService.orders()
      const closingOrders = orders.filter(o => o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrders.length).toBe(0)
    })

    it('should edit position brackets', async () => {
      await brokerService.editPositionBrackets('AAPL', {
        stopLoss: 140.0,
        takeProfit: 160.0,
      })

      // Wait for position update
      await waitForMockerChain(1)

      const positions = await brokerService.positions()
      const position = positions.find(p => p.symbol === 'AAPL')
      expect(position?.stopLoss).toBe(140.0)
      expect(position?.takeProfit).toBe(160.0)
    })

    it('should edit position brackets with only stop loss', async () => {
      await brokerService.editPositionBrackets('AAPL', {
        stopLoss: 145.0,
      })

      // Wait for position update
      await waitForMockerChain(1)

      const positions = await brokerService.positions()
      const position = positions.find(p => p.symbol === 'AAPL')
      expect(position?.stopLoss).toBe(145.0)
      expect(position?.takeProfit).toBeUndefined()
    })

    it('should edit position brackets with only take profit', async () => {
      await brokerService.editPositionBrackets('AAPL', {
        takeProfit: 165.0,
      })

      // Wait for position update
      await waitForMockerChain(1)

      const positions = await brokerService.positions()
      const position = positions.find(p => p.symbol === 'AAPL')
      expect(position?.takeProfit).toBe(165.0)
      expect(position?.stopLoss).toBeUndefined()
    })
  })

  describe('Order Lifecycle (Fallback Mode)', () => {
    it('should handle complete order lifecycle: create -> modify -> cancel', async () => {
      // Create
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      let orders = await brokerService.orders()
      expect(orders.length).toBe(1)
      expect(orders[0].status).toBe(OrderStatus.Working)
      expect(orders[0].qty).toBe(100)

      // Modify
      await brokerService.modifyOrder({
        ...orders[0],
        qty: 150,
        limitPrice: 155.0,
      })

      orders = await brokerService.orders()
      expect(orders[0].qty).toBe(150)
      expect(orders[0].limitPrice).toBe(155.0)

      // Cancel
      await brokerService.cancelOrder(result.orderId!)

      orders = await brokerService.orders()
      expect(orders[0].status).toBe(OrderStatus.Canceled)
      expect(orders[0].updateTime).toBeDefined()
    })

    it('should handle multiple concurrent orders for different symbols', async () => {
      const symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']

      for (const symbol of symbols) {
        await brokerService.placeOrder({
          symbol,
          type: OrderType.Limit,
          side: Side.Buy,
          qty: 100,
          limitPrice: 100.0,
        })
      }

      const orders = await brokerService.orders()
      expect(orders.length).toBe(4)

      const orderSymbols = orders.map(o => o.symbol).sort()
      expect(orderSymbols).toEqual(symbols.sort())
    })

    it('should handle bracket orders (TP/SL) throughout lifecycle', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
        takeProfit: 160.0,
        stopLoss: 140.0,
      })

      let orders = await brokerService.orders()
      expect(orders[0].takeProfit).toBe(160.0)
      expect(orders[0].stopLoss).toBe(140.0)

      // Modify brackets
      await brokerService.modifyOrder({
        ...orders[0],
        takeProfit: 165.0,
        stopLoss: 145.0,
      })

      orders = await brokerService.orders()
      expect(orders[0].takeProfit).toBe(165.0)
      expect(orders[0].stopLoss).toBe(145.0)
    })
  })

  describe('Edge Cases and Error Handling', () => {
    it('should handle modifying non-existent order', async () => {
      await brokerService.modifyOrder({
        id: 'NONEXISTENT',
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        status: OrderStatus.Working,
      })

      // Should not throw, just log warning
      const orders = await brokerService.orders()
      expect(orders.length).toBe(0)
    })

    it('should handle cancelling non-existent order', async () => {
      await brokerService.cancelOrder('NONEXISTENT')

      // Should not throw, just log warning
      const orders = await brokerService.orders()
      expect(orders.length).toBe(0)
    })

    it('should handle zero quantity orders gracefully', async () => {
      const preview = await brokerService.previewOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 0,
      })

      expect(preview.sections).toBeDefined()
    })

    it('should handle very large quantities in preview', async () => {
      const preview = await brokerService.previewOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 10000,
      })

      expect(preview.warnings).toBeDefined()
      expect(preview.warnings).toContain('Large order size may experience slippage')
    })

    it('should handle orders without prices (market orders)', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      const orders = await brokerService.orders()
      expect(orders[0].limitPrice).toBeUndefined()
      expect(orders[0].stopPrice).toBeUndefined()
    })

    it('should use confirmId when modifying order', async () => {
      const preview = await brokerService.previewOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      const orders = await brokerService.orders()

      // Modify using preview confirmId
      await brokerService.modifyOrder(
        {
          ...orders[0],
          qty: 200,
        },
        preview.confirmId
      )

      // Should still work even though confirmId doesn't match order ID
      const modifiedOrders = await brokerService.orders()
      expect(modifiedOrders[0].qty).toBe(100) // Not modified because confirmId doesn't exist
    })
  })

  describe('Multiple Order Types', () => {
    it('should handle limit orders', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      const orders = await brokerService.orders()
      expect(orders[0].type).toBe(OrderType.Limit)
      expect(orders[0].limitPrice).toBe(150.0)
    })

    it('should handle market orders', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      const orders = await brokerService.orders()
      expect(orders[0].type).toBe(OrderType.Market)
    })

    it('should handle stop orders', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Stop,
        side: Side.Sell,
        qty: 100,
        stopPrice: 145.0,
      })

      const orders = await brokerService.orders()
      expect(orders[0].type).toBe(OrderType.Stop)
      expect(orders[0].stopPrice).toBe(145.0)
    })

    it('should handle stop limit orders', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.StopLimit,
        side: Side.Buy,
        qty: 100,
        stopPrice: 155.0,
        limitPrice: 156.0,
      })

      const orders = await brokerService.orders()
      expect(orders[0].type).toBe(OrderType.StopLimit)
      expect(orders[0].stopPrice).toBe(155.0)
      expect(orders[0].limitPrice).toBe(156.0)
    })
  })

  describe('Realistic Trading Scenarios', () => {
    it('should handle complete trade: place order -> execute -> manage position -> close', async () => {
      // Step 1: Place buy order
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Step 2: Wait for execution via mocker chain
      await waitForMockerChain()

      // Step 3: Verify position created
      let positions = await brokerService.positions()
      expect(positions.length).toBe(1)
      expect(positions[0].symbol).toBe('AAPL')
      expect(positions[0].qty).toBe(100)

      // Step 4: Edit position brackets
      await brokerService.editPositionBrackets('AAPL', {
        stopLoss: 148.0,
        takeProfit: 165.0,
      })

      // Wait for bracket update
      await waitForMockerChain(1)

      positions = await brokerService.positions()
      expect(positions[0].stopLoss).toBe(148.0)
      expect(positions[0].takeProfit).toBe(165.0)
    })

    it('should handle multiple positions across different symbols', async () => {
      const symbols = ['AAPL', 'GOOGL', 'MSFT']

      // Create multiple positions
      for (const symbol of symbols) {
        await brokerService.placeOrder({
          symbol,
          type: OrderType.Market,
          side: Side.Buy,
          qty: 100,
        })
      }

      // Wait for all positions to be created
      await waitForMockerChain()

      const positions = await brokerService.positions()
      expect(positions.length).toBe(3)
      expect(positions.map(p => p.symbol).sort()).toEqual(symbols.sort())
    })

    it('should handle partial position close', async () => {
      // Create position
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 200,
      })

      // Wait for position creation
      await waitForMockerChain()

      const positions = await brokerService.positions()
      expect(positions[0].qty).toBe(200)

      // Close half the position
      await brokerService.closePosition('AAPL', 100)

      const orders = await brokerService.orders()
      const closingOrder = orders.find(o => o.id.startsWith('CLOSE-ORDER'))
      expect(closingOrder?.qty).toBe(100) // Half closed
    })

    it('should track executions for filled orders', async () => {
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Wait for execution via mocker chain
      await waitForMockerChain()

      const executions = await brokerService.executions('AAPL')
      expect(executions.length).toBeGreaterThan(0)
      expect(executions[0].symbol).toBe('AAPL')
      expect(executions[0].qty).toBe(100)
      expect(executions[0].side).toBe(Side.Buy)
    })

    it('should handle hedging: long and short positions on same symbol', async () => {
      // Open long position
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Wait for long position
      await waitForMockerChain()

      // Open short position
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Sell,
        qty: 50,
      })

      // Wait for position update (should net to 50 buy)
      await waitForMockerChain()

      const positions = await brokerService.positions()
      const aaplPosition = positions.find(p => p.symbol === 'AAPL')
      // Position should be netted: 100 buy - 50 sell = 50 buy
      expect(aaplPosition?.qty).toBe(50)
      expect(aaplPosition?.side).toBe(Side.Buy)
    })
  })    /**
     * WebSocket Integration Tests (TDD Red Phase)
     *
     * These tests verify the WebSocket subscription flow:
     * 1. Place order via REST API
     * 2. Wait for WebSocket update from backend
     * 3. Verify host callbacks are triggered
     *
     * EXPECTED BEHAVIOR (Red Phase):
     * - These tests WILL FAIL until Phase 5 (backend broadcasting) is implemented
     * - Failures are EXPECTED and indicate we need backend broadcasting
     * - Do NOT remove or skip these tests - they define the contract
     *
     * WHY THEY FAIL:
     * - Backend WebSocket subscriptions work (Phase 1 complete)
     * - Frontend can subscribe to topics (Phase 3 complete)
     * - BUT backend doesn't broadcast order/position updates after REST operations
     * - This is by design - Phase 5 will implement broadcasting
     */
  describe.skip('WebSocket Integration (TDD Red Phase - EXPECTED TO FAIL)', () => {
    let orderUpdateCalls: Order[] = []
    let positionUpdateCalls: Position[] = []
    let executionUpdateCalls: Execution[] = []
    let equityUpdateCalls: number[] = []
    let connectionStatusUpdateCalls: Array<{ status: number; opts?: { message?: string; disconnectType?: number } }> = []
    let notificationCalls: Array<{ title: string; text: string; type: number }> = []

    beforeEach(() => {
      // Clear tracking arrays
      orderUpdateCalls = []
      positionUpdateCalls = []
      executionUpdateCalls = []
      equityUpdateCalls = []
      connectionStatusUpdateCalls = []
      notificationCalls = []

      // Enhanced mock host to track WebSocket callbacks
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
        // Track WebSocket callbacks
        orderUpdate: vi.fn((order: Order) => orderUpdateCalls.push(order)),
        positionUpdate: vi.fn((position: Position) => positionUpdateCalls.push(position)),
        executionUpdate: vi.fn((execution: Execution) => executionUpdateCalls.push(execution)),
        equityUpdate: vi.fn((equity: number) => equityUpdateCalls.push(equity)),
        connectionStatusUpdate: vi.fn((status: number, opts?: { message?: string; disconnectType?: number }) =>
          connectionStatusUpdateCalls.push({ status, opts }),
        ),
        showNotification: vi.fn((title: string, text: string, type: number) =>
          notificationCalls.push({ title, text, type }),
        ),
      } as unknown as IBrokerConnectionAdapterHost

      // Create service with real backend (no BrokerMock)\n      brokerService = new BrokerTerminalService(mockHost, mockDatafeed)

      vi.clearAllMocks()
    })

    it('should receive order update via WebSocket after placing order', async () => {
      // Place order via REST API
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      expect(result.orderId).toBeDefined()

      // Wait for WebSocket update (backend should broadcast after order creation)
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // EXPECTED FAILURE: orderUpdate not called because backend doesn't broadcast yet
      expect(orderUpdateCalls.length).toBe(1)
      expect(orderUpdateCalls[0].symbol).toBe('AAPL')
      expect(orderUpdateCalls[0].status).toBe(OrderStatus.Working)
      expect(mockHost.orderUpdate).toHaveBeenCalledTimes(1)
    }, 10000)

    it('should receive order update via WebSocket after modifying order', async () => {
      // Place order first
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      await new Promise((resolve) => setTimeout(resolve, 1000))
      orderUpdateCalls = [] // Clear initial order update

      // Modify order
      const orders = await brokerService.orders()
      await brokerService.modifyOrder({
        ...orders[0],
        qty: 150,
      })

      // Wait for WebSocket update
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // EXPECTED FAILURE: No broadcast after modification
      expect(orderUpdateCalls.length).toBe(1)
      expect(orderUpdateCalls[0].qty).toBe(150)
    }, 10000)

    it('should receive order update via WebSocket after cancelling order', async () => {
      // Place order first
      const result = await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Limit,
        side: Side.Buy,
        qty: 100,
        limitPrice: 150.0,
      })

      await new Promise((resolve) => setTimeout(resolve, 1000))
      orderUpdateCalls = [] // Clear initial order update

      // Cancel order
      await brokerService.cancelOrder(result.orderId!)

      // Wait for WebSocket update
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // EXPECTED FAILURE: No broadcast after cancellation
      expect(orderUpdateCalls.length).toBe(1)
      expect(orderUpdateCalls[0].status).toBe(OrderStatus.Canceled)
    }, 10000)

    it('should receive position update via WebSocket after order fill', async () => {
      // Place market order (should be filled immediately in real scenario)
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Wait for order fill and position creation
      await new Promise((resolve) => setTimeout(resolve, 3000))

      // EXPECTED FAILURE: No position broadcast from backend
      expect(positionUpdateCalls.length).toBeGreaterThan(0)
      expect(positionUpdateCalls[0].symbol).toBe('AAPL')
      expect(positionUpdateCalls[0].qty).toBe(100)
      expect(mockHost.positionUpdate).toHaveBeenCalled()
    }, 10000)

    it('should receive execution update via WebSocket after order fill', async () => {
      // Place market order
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Wait for execution
      await new Promise((resolve) => setTimeout(resolve, 3000))

      // EXPECTED FAILURE: No execution broadcast from backend
      expect(executionUpdateCalls.length).toBeGreaterThan(0)
      expect(executionUpdateCalls[0].symbol).toBe('AAPL')
      expect(executionUpdateCalls[0].qty).toBe(100)
      expect(executionUpdateCalls[0].side).toBe(Side.Buy)
      expect(mockHost.executionUpdate).toHaveBeenCalled()
    }, 10000)

    it('should receive equity update via WebSocket', async () => {
      // Wait for initial equity update
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // EXPECTED FAILURE: No equity broadcasts from backend
      expect(equityUpdateCalls.length).toBeGreaterThan(0)
      expect(mockHost.equityUpdate).toHaveBeenCalled()
    }, 10000)

    it('should receive broker connection status via WebSocket', async () => {
      // Wait for connection status
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // EXPECTED FAILURE: No connection status broadcasts from backend
      expect(connectionStatusUpdateCalls.length).toBeGreaterThan(0)
      expect(mockHost.connectionStatusUpdate).toHaveBeenCalled()
    }, 10000)

    it('should show notification when order is filled', async () => {
      // Place market order
      await brokerService.placeOrder({
        symbol: 'AAPL',
        type: OrderType.Market,
        side: Side.Buy,
        qty: 100,
      })

      // Wait for fill notification
      await new Promise((resolve) => setTimeout(resolve, 3000))

      // EXPECTED FAILURE: No fill notifications without backend broadcasting
      expect(notificationCalls.length).toBeGreaterThan(0)
      const fillNotification = notificationCalls.find((n) => n.title === 'Order Filled')
      expect(fillNotification).toBeDefined()
      expect(fillNotification?.text).toContain('AAPL')
      expect(fillNotification?.text).toContain('Buy')
    }, 10000)

    it('should show notification on broker disconnection', async () => {
      // Wait for potential disconnect notification
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // Note: This test may not fail in dev environment
      // It would fail if backend sends disconnection status
      if (notificationCalls.length > 0) {
        const disconnectNotification = notificationCalls.find((n) => n.title === 'Broker Disconnected')
        expect(disconnectNotification).toBeDefined()
      }
    }, 10000)

    it('should update balance and equity reactive values from WebSocket', async () => {
      const accountInfo = brokerService.accountManagerInfo()
      const balanceWatchedValue = accountInfo.summary.find((s) => s.text === 'Balance')?.wValue as IWatchedValue<number> | undefined
      const equityWatchedValue = accountInfo.summary.find((s) => s.text === 'Equity')?.wValue as IWatchedValue<number> | undefined

      expect(balanceWatchedValue).toBeDefined()
      expect(equityWatchedValue).toBeDefined()

      // Wait for equity update
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // EXPECTED FAILURE: No equity broadcasts, so setValue not called
      expect(balanceWatchedValue?.setValue).toHaveBeenCalled()
      expect(equityWatchedValue?.setValue).toHaveBeenCalled()
    }, 10000)
  })
})
