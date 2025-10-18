import type {
    Execution,
    IBrokerConnectionAdapterHost,
    IDatafeedQuotesApi,
    IWatchedValue,
    Order, Position,
} from '@public/trading_terminal'
import { OrderStatus, OrderType, Side } from '@public/trading_terminal'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BrokerTerminalService } from '../brokerTerminalService'

/**
 * Test suite for BrokerTerminalService
 *
 * Tests position management logic, particularly:
 * - Opening long/short positions
 * - Closing long/short positions
 * - Partial position closes
 * - Position reversals
 */
describe('BrokerTerminalService', () => {
    let brokerService: BrokerTerminalService
    let mockHost: IBrokerConnectionAdapterHost
    let mockDatafeed: IDatafeedQuotesApi
    let orderUpdateSpy: ReturnType<typeof vi.fn>
    let positionUpdateSpy: ReturnType<typeof vi.fn>
    let executionUpdateSpy: ReturnType<typeof vi.fn>

    beforeEach(() => {
        // Setup spies
        orderUpdateSpy = vi.fn()
        positionUpdateSpy = vi.fn()
        executionUpdateSpy = vi.fn()

        // Mock TradingView host
        mockHost = {
            orderUpdate: orderUpdateSpy,
            positionUpdate: positionUpdateSpy,
            executionUpdate: executionUpdateSpy,
            defaultContextMenuActions: vi.fn().mockResolvedValue([]),
            defaultFormatter: vi.fn(),
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

        brokerService = new BrokerTerminalService(mockHost, mockDatafeed)

        // Clear all mocks
        vi.clearAllMocks()
    })

    describe('Position Management - Opening Positions', () => {
        it('should create a new long position when buying', async () => {
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })

            // Wait for simulated execution
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position update should be called with new long position
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(100)
            expect(lastPositionUpdate.side).toBe(Side.Buy)
        })

        it('should create a new short position when selling', async () => {
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })

            // Wait for simulated execution
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position update should be called with new short position
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(100)
            expect(lastPositionUpdate.side).toBe(Side.Sell)
        })
    })

    describe('Position Management - Closing Positions', () => {
        it('should close a long position completely when selling the same quantity', async () => {
            // Open long position: Buy 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Close position: Sell 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be closed (qty: 0)
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(0)
        })

        it('should close a short position completely when buying the same quantity', async () => {
            // Open short position: Sell 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Close position: Buy 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be closed (qty: 0)
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(0)
        })
    })

    describe('Position Management - Partial Closes', () => {
        it('should reduce a long position when selling less than the full quantity', async () => {
            // Open long position: Buy 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Partial close: Sell 50
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 50,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be reduced to 50
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(50)
            expect(lastPositionUpdate.side).toBe(Side.Buy)
        })

        it('should reduce a short position when buying less than the full quantity', async () => {
            // Open short position: Sell 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Partial close: Buy 50
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 50,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be reduced to 50 (still short)
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(50)
            expect(lastPositionUpdate.side).toBe(Side.Sell)
        })
    })

    describe('Position Management - Position Reversals', () => {
        it('should reverse from long to short when selling more than the current position', async () => {
            // Open long position: Buy 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Reverse to short: Sell 150
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 150,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be short 50
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(50)
            expect(lastPositionUpdate.side).toBe(Side.Sell)
        })

        it('should reverse from short to long when buying more than the current position', async () => {
            // Open short position: Sell 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Reverse to long: Buy 150
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 150,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be long 50
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(50)
            expect(lastPositionUpdate.side).toBe(Side.Buy)
        })
    })

    describe('Position Management - Increasing Positions', () => {
        it('should increase a long position when buying more', async () => {
            // Open long position: Buy 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Add to position: Buy 50
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 50,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be long 150
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(150)
            expect(lastPositionUpdate.side).toBe(Side.Buy)
        })

        it('should increase a short position when selling more', async () => {
            // Open short position: Sell 100
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Clear previous calls
            positionUpdateSpy.mockClear()

            // Add to position: Sell 50
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 50,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Position should be short 150
            const positionUpdateCalls = positionUpdateSpy.mock.calls
            const lastPositionUpdate = positionUpdateCalls[positionUpdateCalls.length - 1][0] as Position

            expect(lastPositionUpdate.symbol).toBe('AAPL')
            expect(lastPositionUpdate.qty).toBe(150)
            expect(lastPositionUpdate.side).toBe(Side.Sell)
        })
    })

    describe('Order and Execution Tracking', () => {
        it('should create order and execution records', async () => {
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })

            // Wait for simulated execution
            await new Promise((resolve) => setTimeout(resolve, 300))

            // Verify order updates
            expect(orderUpdateSpy).toHaveBeenCalled()
            const orderCalls = orderUpdateSpy.mock.calls
            const filledOrder = orderCalls.find(
                (call) => (call[0] as Order).status === OrderStatus.Filled,
            )?.[0] as Order

            expect(filledOrder).toBeDefined()
            expect(filledOrder.symbol).toBe('AAPL')
            expect(filledOrder.qty).toBe(100)
            expect(filledOrder.filledQty).toBe(100)

            // Verify execution update
            expect(executionUpdateSpy).toHaveBeenCalled()
            const execution = executionUpdateSpy.mock.calls[0][0] as Execution

            expect(execution.symbol).toBe('AAPL')
            expect(execution.qty).toBe(100)
            expect(execution.side).toBe(Side.Buy)
        })

        it('should maintain order history', async () => {
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            const orders = await brokerService.orders()
            expect(orders.length).toBeGreaterThan(0)
            expect(orders[0].symbol).toBe('AAPL')
            expect(orders[0].status).toBe(OrderStatus.Filled)
        })

        it('should maintain execution history', async () => {
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            const executions = await brokerService.executions('AAPL')
            expect(executions.length).toBeGreaterThan(0)
            expect(executions[0].symbol).toBe('AAPL')
            expect(executions[0].qty).toBe(100)
        })
    })

    describe('Position Queries', () => {
        it('should return empty positions list initially', async () => {
            const positions = await brokerService.positions()
            expect(positions).toEqual([])
        })

        it('should return positions after trades', async () => {
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            const positions = await brokerService.positions()
            expect(positions.length).toBe(1)
            expect(positions[0].symbol).toBe('AAPL')
            expect(positions[0].qty).toBe(100)
            expect(positions[0].side).toBe(Side.Buy)
        })

        it('should not return closed positions', async () => {
            // Open and close position
            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Buy,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            await brokerService.placeOrder({
                symbol: 'AAPL',
                type: OrderType.Market,
                side: Side.Sell,
                qty: 100,
            })
            await new Promise((resolve) => setTimeout(resolve, 300))

            const positions = await brokerService.positions()
            // Position should be removed from internal map after closing
            // We send a 0-qty update to TradingView, but don't keep it in our map
            expect(positions.length).toBe(0)
        })
    })
})
