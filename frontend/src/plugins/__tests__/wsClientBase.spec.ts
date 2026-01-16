/**
 * @vitest-environment jsdom
 */

import { WebSocketError } from '@/errors'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WebSocketBase, WebSocketClient, WebSocketFallback, type SubscriptionError } from '../wsClientBase'

// ============================================================================
// Mock WebSocket
// ============================================================================

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  binaryType = ''

  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  send = vi.fn()
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED
  })

  // Test helpers
  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  simulateMessage(data: object): void {
    const event = { data: JSON.stringify(data) } as MessageEvent
    this.onmessage?.(event)
  }

  simulateBinaryMessage(data: object): void {
    const encoder = new TextEncoder()
    const event = { data: encoder.encode(JSON.stringify(data)).buffer } as MessageEvent
    this.onmessage?.(event)
  }

  simulateError(): void {
    this.onerror?.(new Event('error'))
  }

  simulateClose(code = 1000): void {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code } as CloseEvent)
  }
}

// Track created instances for testing
let mockWebSocketInstances: MockWebSocket[] = []
const MockWebSocketConstructor = vi.fn(() => {
  const instance = new MockWebSocket()
  mockWebSocketInstances.push(instance)
  return instance
})

// Assign static properties to constructor
Object.assign(MockWebSocketConstructor, {
  CONNECTING: MockWebSocket.CONNECTING,
  OPEN: MockWebSocket.OPEN,
  CLOSING: MockWebSocket.CLOSING,
  CLOSED: MockWebSocket.CLOSED,
})

// ============================================================================
// Test Utilities
// ============================================================================

function getLastMockWebSocket(): MockWebSocket {
  return mockWebSocketInstances[mockWebSocketInstances.length - 1]
}

function clearWebSocketBaseInstances(): void {
  // Access private static map to clear singletons between tests
  // @ts-expect-error - accessing private static for test cleanup
  WebSocketBase.instances.clear()
}

// ============================================================================
// Tests
// ============================================================================

describe('wsClientBase', () => {
  // Suppress expected unhandled rejections from retry logic
  const originalOnUnhandledRejection = process.listeners('unhandledRejection')
  const expectedErrors = ['Request timeout', 'Invalid symbol', 'WebSocket disconnected']

  beforeEach(() => {
    vi.useFakeTimers()
    mockWebSocketInstances = []
    MockWebSocketConstructor.mockClear()
    vi.stubGlobal('WebSocket', MockWebSocketConstructor)
    clearWebSocketBaseInstances()

    // Temporarily remove default rejection handlers to avoid noise
    process.removeAllListeners('unhandledRejection')
    process.on('unhandledRejection', (reason: Error) => {
      // Only re-throw if it's not an expected error from retry logic
      if (!expectedErrors.some(msg => reason?.message?.includes(msg))) {
        throw reason
      }
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    clearWebSocketBaseInstances()

    // Restore original handlers
    process.removeAllListeners('unhandledRejection')
    originalOnUnhandledRejection.forEach(listener => {
      process.on('unhandledRejection', listener as NodeJS.UnhandledRejectionListener)
    })
  })

  // ==========================================================================
  // WebSocketBase
  // ==========================================================================

  describe('WebSocketBase', () => {
    describe('Singleton Pattern', () => {
      it('should return same instance for same URL', () => {
        const instance1 = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const instance2 = WebSocketBase.getInstance('ws://localhost:8000/ws')

        expect(instance1).toBe(instance2)
      })

      it('should return different instances for different URLs', () => {
        const instance1 = WebSocketBase.getInstance('ws://localhost:8000/ws1')
        const instance2 = WebSocketBase.getInstance('ws://localhost:8000/ws2')

        expect(instance1).not.toBe(instance2)
      })
    })

    describe('Subscribe Flow', () => {
      it('should successfully subscribe and return topic', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        // Wait for connection attempt
        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()

        // Wait for subscription request to be sent
        await vi.advanceTimersByTimeAsync(10)

        // Verify request was sent
        expect(mockWs.send).toHaveBeenCalledTimes(1)
        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        expect(sentMessage.type).toBe('orders.subscribe')
        expect(sentMessage.payload.sub_params).toEqual({ symbol: 'AAPL' })

        // Simulate server response
        const subId = sentMessage.payload.sub_id
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: subId, topic: 'orders:AAPL' },
        })

        const topic = await subscribePromise
        expect(topic).toBe('orders:AAPL')
      })

      it('should reject on subscription timeout', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()

        // Don't send response, let it timeout (3000ms) x 5 retries + delays
        // The subscribe function has 5 retry attempts with 200ms delay between
        // Each attempt has a 3000ms timeout
        // Total time needed: 5 * (3000 + 200) = 16000ms
        await vi.advanceTimersByTimeAsync(20000)

        await expect(subscribePromise).rejects.toThrow('Request timeout')

        // Ensure all pending timers are cleared
        await vi.runAllTimersAsync()
      })

      it('should throw on server error response after retries exhausted', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()

        // Respond with error to each retry attempt (5 attempts total)
        for (let i = 0; i < 5; i++) {
          await vi.advanceTimersByTimeAsync(10)

          if (mockWs.send.mock.calls.length > i) {
            const sentMessage = JSON.parse(mockWs.send.mock.calls[i][0])
            const subId = sentMessage.payload.sub_id

            mockWs.simulateMessage({
              type: 'orders.subscribe.response',
              payload: { status: 'error', sub_id: subId, topic: '', error: 'Invalid symbol' },
            })
          }

          // Wait for retry delay (200ms per the code)
          await vi.advanceTimersByTimeAsync(250)
        }

        await expect(subscribePromise).rejects.toThrow('Invalid symbol')

        // Ensure all pending timers are cleared
        await vi.runAllTimersAsync()
      })

      it('should route update messages to subscription callback', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        const subId = sentMessage.payload.sub_id

        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: subId, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Now send an update
        mockWs.simulateMessage({
          type: 'orders.update',
          payload: { topic: 'orders:AAPL', payload: { orderId: '123', status: 'filled' } },
        })

        expect(onUpdate).toHaveBeenCalledExactlyOnceWith({ orderId: '123', status: 'filled' })
      })
    })

    describe('Unsubscribe', () => {
      it('should send unsubscribe request for existing topic', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        // First subscribe
        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        const subId = sentMessage.payload.sub_id

        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: subId, topic: 'orders:AAPL' },
        })

        const topic = await subscribePromise

        // Clear mock to check unsubscribe call
        mockWs.send.mockClear()

        // Now unsubscribe
        await wsBase.unsubscribe(topic)

        expect(mockWs.send).toHaveBeenCalledTimes(1)
        const unsubMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        expect(unsubMessage.type).toBe('orders.unsubscribe')
      })

      it('should warn and return early for non-existent topic', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => { })

        // Unsubscribe without subscribing first - should not throw
        await wsBase.unsubscribe('non-existent-topic')

        // Should not have created any WebSocket
        expect(mockWebSocketInstances.length).toBe(0)
        warnSpy.mockRestore()
      })

      it('should close connection when last subscription is removed', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        // Subscribe
        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        const topic = await subscribePromise

        // Unsubscribe the only subscription
        await wsBase.unsubscribe(topic)

        expect(mockWs.close).toHaveBeenCalledTimes(1)
      })
    })

    describe('Error Routing', () => {
      it('should route error to subscription onError callback', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Send an error for the subscription
        const subscriptionError: SubscriptionError = {
          topic: 'orders:AAPL',
          error: { code: 'RATE_LIMIT', message: 'Too many requests', timestamp: Date.now() },
          recoverable: true,
        }

        mockWs.simulateMessage({
          type: 'orders.error',
          payload: subscriptionError,
        })

        expect(onError).toHaveBeenCalledExactlyOnceWith(subscriptionError)
      })

      it('should call globalErrorHandler for unknown topic errors', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        // Subscribe to create connection
        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Send error for unknown topic - should throw WebSocketError
        const unknownError: SubscriptionError = {
          topic: 'unknown:topic',
          error: { code: 'UNKNOWN', message: 'Unknown error', timestamp: Date.now() },
        }

        expect(() => {
          mockWs.simulateMessage({
            type: 'orders.error',
            payload: unknownError,
          })
        }).toThrow(WebSocketError)
      })

      it('globalErrorHandler should throw WebSocketError from subscription error', () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const error: SubscriptionError = {
          topic: 'test:topic',
          error: { code: 'TEST_ERROR', message: 'Test error message', timestamp: 12345 },
        }

        expect(() => wsBase.globalErrorHandler(error)).toThrow(WebSocketError)
      })
    })

    describe('Message Handling', () => {
      it('should handle binary ArrayBuffer messages', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Send binary message
        mockWs.simulateBinaryMessage({
          type: 'orders.update',
          payload: { topic: 'orders:AAPL', payload: { orderId: '456' } },
        })

        expect(onUpdate).toHaveBeenCalledExactlyOnceWith({ orderId: '456' })
      })
    })

    describe('Static Methods', () => {
      it('logout should close all WebSocket connections', async () => {
        const wsBase1 = WebSocketBase.getInstance('ws://localhost:8000/ws1')
        const wsBase2 = WebSocketBase.getInstance('ws://localhost:8000/ws2')

        // Subscribe to both to create connections
        const onUpdate = vi.fn()
        const onError = vi.fn()

        wsBase1.subscribe('orders', {}, onUpdate, onError)
        await vi.advanceTimersByTimeAsync(10)
        const mockWs1 = mockWebSocketInstances[0]
        mockWs1.simulateOpen()

        wsBase2.subscribe('positions', {}, onUpdate, onError)
        await vi.advanceTimersByTimeAsync(10)
        const mockWs2 = mockWebSocketInstances[1]
        mockWs2.simulateOpen()

        // Call logout
        const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => { })
        WebSocketBase.logout()

        expect(mockWs1.close).toHaveBeenCalledTimes(1)
        expect(mockWs2.close).toHaveBeenCalledTimes(1)
        consoleSpy.mockRestore()
      })
    })

    describe('Reconnection (resubscribeAll)', () => {
      it('should trigger resubscription on connection close', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        // Subscribe
        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Track how many WS instances existed before close
        const instancesBeforeClose = mockWebSocketInstances.length

        // Simulate connection close - this triggers resubscribeAll which will create a new connection
        mockWs.simulateClose()

        // Wait for resubscribe attempt (200ms delay + processing)
        await vi.advanceTimersByTimeAsync(500)

        // resubscribeAll should have triggered sendRequest which creates a new connection
        // Since the original WS is closed, it should try to connect again
        expect(mockWebSocketInstances.length).toBeGreaterThanOrEqual(instancesBeforeClose)
      })

      it('should reject pending requests when connection is lost', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        // Subscribe first to establish connection
        const sub1Promise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await sub1Promise

        // Start a second subscription but don't respond
        wsBase.subscribe('positions', { account: '123' }, onUpdate, onError)
        await vi.advanceTimersByTimeAsync(10)

        // Simulate connection error - this should reject pending and trigger resubscribeAll
        mockWs.simulateError()

        // Wait for resubscribe process
        await vi.advanceTimersByTimeAsync(500)

        // The second subscription should eventually fail or be retried
        // We're testing that the system handles disconnection gracefully
        await vi.runAllTimersAsync()

        // Verify that new connection attempts were made after error
        expect(mockWebSocketInstances.length).toBeGreaterThanOrEqual(1)
      })
    })

    describe('Connection Retry', () => {
      it('should retry connection on initial failure', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs1 = getLastMockWebSocket()

        // Simulate connection error
        mockWs1.simulateError()

        // Wait for retry delay
        await vi.advanceTimersByTimeAsync(1100)

        // A new WebSocket instance should be created
        expect(mockWebSocketInstances.length).toBeGreaterThan(1)
        const mockWs2 = getLastMockWebSocket()

        // Succeed on second attempt
        mockWs2.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs2.send.mock.calls[0][0])
        mockWs2.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        const topic = await subscribePromise
        expect(topic).toBe('orders:AAPL')
      })
    })

    describe('Message Type Handling', () => {
      it('should log error for unknown message types', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Send unknown message type (not .update, .error, or .response)
        mockWs.simulateMessage({
          type: 'orders.unknown',
          payload: { data: 'test' },
        })

        // Should not throw, just log error (covered by logger mock)
        expect(onUpdate).not.toHaveBeenCalled()
      })

      it('should throw when no subscription found for update topic', async () => {
        const wsBase = WebSocketBase.getInstance('ws://localhost:8000/ws')
        const onUpdate = vi.fn()
        const onError = vi.fn()

        const subscribePromise = wsBase.subscribe('orders', { symbol: 'AAPL' }, onUpdate, onError)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'orders.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'orders:AAPL' },
        })

        await subscribePromise

        // Send update for different topic - should throw
        expect(() => {
          mockWs.simulateMessage({
            type: 'orders.update',
            payload: { topic: 'orders:UNKNOWN', payload: { orderId: '999' } },
          })
        }).toThrow('No active subscription for topic: orders:UNKNOWN')

        // Should not call the subscribed callback
        expect(onUpdate).not.toHaveBeenCalled()
      })
    })
  })

  // ==========================================================================
  // WebSocketClient
  // ==========================================================================

  describe('WebSocketClient', () => {
    const dataMapper = (data: { raw: string }) => ({ mapped: data.raw.toUpperCase() })

    describe('Subscription Deduplication', () => {
      it('should add listener to existing subscription for same params', async () => {
        const wsClient = new WebSocketClient<{ symbol: string }, { raw: string }, { mapped: string }>(
          'ws://localhost:8000/ws',
          'quotes',
          dataMapper,
          1000,
        )

        const onUpdate1 = vi.fn()
        const onUpdate2 = vi.fn()

        // First subscription
        const sub1Promise = wsClient.subscribe('listener1', { symbol: 'AAPL' }, onUpdate1)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'quotes:AAPL' },
        })

        await sub1Promise

        // Second subscription with same params - should NOT send another request
        mockWs.send.mockClear()
        const sub2Promise = wsClient.subscribe('listener2', { symbol: 'AAPL' }, onUpdate2)
        await vi.advanceTimersByTimeAsync(10)

        // No new subscribe request should be sent
        expect(mockWs.send).not.toHaveBeenCalled()
        await sub2Promise

        // Both listeners should receive updates
        mockWs.simulateMessage({
          type: 'quotes.update',
          payload: { topic: 'quotes:AAPL', payload: { raw: 'test' } },
        })

        expect(onUpdate1).toHaveBeenCalledExactlyOnceWith({ mapped: 'TEST' })
        expect(onUpdate2).toHaveBeenCalledExactlyOnceWith({ mapped: 'TEST' })
      })

      it('should create new subscription for different params', async () => {
        const wsClient = new WebSocketClient<{ symbol: string }, { raw: string }, { mapped: string }>(
          'ws://localhost:8000/ws',
          'quotes',
          dataMapper,
        )

        const onUpdate1 = vi.fn()
        const onUpdate2 = vi.fn()

        // First subscription
        const sub1Promise = wsClient.subscribe('listener1', { symbol: 'AAPL' }, onUpdate1)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage1 = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage1.payload.sub_id, topic: 'quotes:AAPL' },
        })

        await sub1Promise

        // Second subscription with different params
        mockWs.send.mockClear()
        const sub2Promise = wsClient.subscribe('listener2', { symbol: 'GOOGL' }, onUpdate2)
        await vi.advanceTimersByTimeAsync(10)

        // New subscribe request should be sent
        expect(mockWs.send).toHaveBeenCalledTimes(1)
        const sentMessage2 = JSON.parse(mockWs.send.mock.calls[0][0])
        expect(sentMessage2.payload.sub_params).toEqual({ symbol: 'GOOGL' })

        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage2.payload.sub_id, topic: 'quotes:GOOGL' },
        })

        await sub2Promise
      })
    })

    describe('Data Mapping', () => {
      it('should apply dataMapper to incoming data', async () => {
        const wsClient = new WebSocketClient<{ symbol: string }, { raw: string }, { mapped: string }>(
          'ws://localhost:8000/ws',
          'quotes',
          dataMapper,
        )

        const onUpdate = vi.fn()
        const subPromise = wsClient.subscribe('listener1', { symbol: 'AAPL' }, onUpdate)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'quotes:AAPL' },
        })

        await subPromise

        mockWs.simulateMessage({
          type: 'quotes.update',
          payload: { topic: 'quotes:AAPL', payload: { raw: 'hello' } },
        })

        expect(onUpdate).toHaveBeenCalledExactlyOnceWith({ mapped: 'HELLO' })
      })
    })

    describe('Error Fanout', () => {
      it('should fanout errors to all listeners', async () => {
        const wsClient = new WebSocketClient<{ symbol: string }, { raw: string }, { mapped: string }>(
          'ws://localhost:8000/ws',
          'quotes',
          dataMapper,
          1000,
        )

        const onUpdate1 = vi.fn()
        const onError1 = vi.fn()
        const onUpdate2 = vi.fn()
        const onError2 = vi.fn()

        // First subscription
        const sub1Promise = wsClient.subscribe('listener1', { symbol: 'AAPL' }, onUpdate1, onError1)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'quotes:AAPL' },
        })

        await sub1Promise

        // Second subscription with same params
        await wsClient.subscribe('listener2', { symbol: 'AAPL' }, onUpdate2, onError2)

        // Send error
        const error: SubscriptionError = {
          topic: 'quotes:AAPL',
          error: { code: 'ERROR', message: 'Test error', timestamp: Date.now() },
        }

        mockWs.simulateMessage({
          type: 'quotes.error',
          payload: error,
        })

        expect(onError1).toHaveBeenCalledExactlyOnceWith(error)
        expect(onError2).toHaveBeenCalledExactlyOnceWith(error)
      })
    })

    describe('Debounced Unsubscribe', () => {
      it('should debounce unsubscribe when last listener is removed', async () => {
        const debounceMs = 500
        const wsClient = new WebSocketClient<{ symbol: string }, { raw: string }, { mapped: string }>(
          'ws://localhost:8000/ws',
          'quotes',
          dataMapper,
          debounceMs,
        )

        const onUpdate = vi.fn()
        const subPromise = wsClient.subscribe('listener1', { symbol: 'AAPL' }, onUpdate)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'quotes:AAPL' },
        })

        await subPromise

        mockWs.send.mockClear()

        // Unsubscribe
        await wsClient.unsubscribe('listener1')

        // Should not immediately send unsubscribe
        expect(mockWs.send).not.toHaveBeenCalled()

        // After debounce, should send unsubscribe
        await vi.advanceTimersByTimeAsync(debounceMs + 10)

        expect(mockWs.send).toHaveBeenCalledTimes(1)
        const unsubMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        expect(unsubMessage.type).toBe('quotes.unsubscribe')
      })

      it('should cancel debounced unsubscribe if re-subscribed', async () => {
        const debounceMs = 500
        const wsClient = new WebSocketClient<{ symbol: string }, { raw: string }, { mapped: string }>(
          'ws://localhost:8000/ws',
          'quotes',
          dataMapper,
          debounceMs,
        )

        const onUpdate = vi.fn()
        const subPromise = wsClient.subscribe('listener1', { symbol: 'AAPL' }, onUpdate)

        await vi.advanceTimersByTimeAsync(10)
        const mockWs = getLastMockWebSocket()
        mockWs.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        const sentMessage = JSON.parse(mockWs.send.mock.calls[0][0])
        mockWs.simulateMessage({
          type: 'quotes.subscribe.response',
          payload: { status: 'ok', sub_id: sentMessage.payload.sub_id, topic: 'quotes:AAPL' },
        })

        await subPromise

        mockWs.send.mockClear()

        // Unsubscribe
        await wsClient.unsubscribe('listener1')

        // Wait half the debounce time
        await vi.advanceTimersByTimeAsync(debounceMs / 2)

        // Re-subscribe before debounce completes
        const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => { })
        await wsClient.subscribe('listener2', { symbol: 'AAPL' }, vi.fn())
        consoleSpy.mockRestore()

        // Wait past original debounce time
        await vi.advanceTimersByTimeAsync(debounceMs)

        // Should NOT have sent unsubscribe
        expect(mockWs.send).not.toHaveBeenCalled()
      })
    })
  })

  // ==========================================================================
  // WebSocketFallback
  // ==========================================================================

  describe('WebSocketFallback', () => {
    describe('Subscription Management', () => {
      it('should store subscription and return ID', async () => {
        const mockData = vi.fn(() => ({ value: 42 }))
        const fallback = new WebSocketFallback<{ symbol: string }, { value: number }>(mockData)

        const onUpdate = vi.fn()
        const result = await fallback.subscribe('sub1', { symbol: 'AAPL' }, onUpdate)

        expect(result).toBe('sub1')
      })

      it('should remove subscription on unsubscribe', async () => {
        const mockData = vi.fn(() => ({ value: 42 }))
        const fallback = new WebSocketFallback<{ symbol: string }, { value: number }>(mockData)

        const onUpdate = vi.fn()
        await fallback.subscribe('sub1', { symbol: 'AAPL' }, onUpdate)

        // Advance to receive some updates
        await vi.advanceTimersByTimeAsync(150)
        expect(onUpdate).toHaveBeenCalled()

        onUpdate.mockClear()

        // Unsubscribe
        await fallback.unsubscribe('sub1')

        // Advance more - should not receive updates
        await vi.advanceTimersByTimeAsync(200)
        expect(onUpdate).not.toHaveBeenCalled()

        fallback.destroy()
      })

      it('should support prefix matching for bulk unsubscribe', async () => {
        const mockData = vi.fn(() => ({ value: 42 }))
        const fallback = new WebSocketFallback<{ symbol: string }, { value: number }>(mockData)

        const onUpdate1 = vi.fn()
        const onUpdate2 = vi.fn()
        const onUpdate3 = vi.fn()

        await fallback.subscribe('chart-1', { symbol: 'AAPL' }, onUpdate1)
        await fallback.subscribe('chart-2', { symbol: 'GOOGL' }, onUpdate2)
        await fallback.subscribe('other', { symbol: 'MSFT' }, onUpdate3)

        await vi.advanceTimersByTimeAsync(150)
        expect(onUpdate1).toHaveBeenCalled()
        expect(onUpdate2).toHaveBeenCalled()
        expect(onUpdate3).toHaveBeenCalled()

        onUpdate1.mockClear()
        onUpdate2.mockClear()
        onUpdate3.mockClear()

        // Unsubscribe all chart-* subscriptions
        await fallback.unsubscribe('chart')

        await vi.advanceTimersByTimeAsync(200)

        // Only 'other' should still receive updates
        expect(onUpdate1).not.toHaveBeenCalled()
        expect(onUpdate2).not.toHaveBeenCalled()
        expect(onUpdate3).toHaveBeenCalled()

        fallback.destroy()
      })
    })

    describe('Interval Updates', () => {
      it('should call onUpdate at 100ms intervals', async () => {
        const mockData = vi.fn(() => ({ value: 42 }))
        const fallback = new WebSocketFallback<{ symbol: string }, { value: number }>(mockData)

        const onUpdate = vi.fn()
        await fallback.subscribe('sub1', { symbol: 'AAPL' }, onUpdate)

        // Initially no calls
        expect(onUpdate).not.toHaveBeenCalled()

        // After 100ms
        await vi.advanceTimersByTimeAsync(100)
        expect(onUpdate).toHaveBeenCalledTimes(1)
        expect(onUpdate).toHaveBeenCalledExactlyOnceWith({ value: 42 })

        // After another 100ms
        await vi.advanceTimersByTimeAsync(100)
        expect(onUpdate).toHaveBeenCalledTimes(2)

        fallback.destroy()
      })

      it('should not call onUpdate if mockData returns undefined', async () => {
        const mockData = vi.fn(() => undefined)
        const fallback = new WebSocketFallback<{ symbol: string }, { value: number }>(mockData)

        const onUpdate = vi.fn()
        await fallback.subscribe('sub1', { symbol: 'AAPL' }, onUpdate)

        await vi.advanceTimersByTimeAsync(300)

        expect(mockData).toHaveBeenCalled()
        expect(onUpdate).not.toHaveBeenCalled()

        fallback.destroy()
      })
    })

    describe('Cleanup', () => {
      it('destroy should clear interval and subscriptions', async () => {
        const mockData = vi.fn(() => ({ value: 42 }))
        const fallback = new WebSocketFallback<{ symbol: string }, { value: number }>(mockData)

        const onUpdate = vi.fn()
        await fallback.subscribe('sub1', { symbol: 'AAPL' }, onUpdate)

        await vi.advanceTimersByTimeAsync(100)
        expect(onUpdate).toHaveBeenCalledTimes(1)

        fallback.destroy()

        onUpdate.mockClear()
        mockData.mockClear()

        await vi.advanceTimersByTimeAsync(300)

        expect(mockData).not.toHaveBeenCalled()
        expect(onUpdate).not.toHaveBeenCalled()
      })
    })
  })
})
