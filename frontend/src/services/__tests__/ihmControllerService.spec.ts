import { WsAdapter } from '@/plugins/wsAdapter'
import type { ToolSchema } from '@/types/ihmController'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IHMControllerService } from '../ihmControllerService'

describe('IHMControllerService', () => {
  let service: IHMControllerService

  beforeEach(() => {
    service = IHMControllerService.getInstance()
  })

  describe('Singleton Pattern', () => {
    it('should be a singleton', () => {
      const instance1 = IHMControllerService.getInstance()
      const instance2 = IHMControllerService.getInstance()
      expect(instance1).toBe(instance2)
    })
  })

  describe('Tool Registration', () => {
    it('should register a tool with schema and handler', () => {
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      }
      const handler = vi.fn().mockResolvedValue(undefined)

      expect(() => {
        service.registerTool(schema, handler)
      }).not.toThrow()
    })

    it('should store registered tool schema and handler', () => {
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      }
      const handler = vi.fn().mockResolvedValue(undefined)

      service.registerTool(schema, handler)

      const registeredTools = service.getRegisteredTools()
      expect(registeredTools).toHaveLength(1)
      expect(registeredTools[0].schema).toEqual(schema)
      expect(registeredTools[0].handler).toBe(handler)
    })
  })

  describe('Tool Unregistration', () => {
    it('should unregister a tool', async () => {
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      }
      const handler = vi.fn().mockResolvedValue(undefined)

      service.registerTool(schema, handler)
      expect(service.getRegisteredTools()).toHaveLength(1)

      await service.unregisterTool('testTool')
      expect(service.getRegisteredTools()).toHaveLength(0)
    })
  })

  describe('WebSocket Integration', () => {
    it('should handle tools client not being available gracefully', () => {
      const wsAdapter = WsAdapter.getInstance()

      // Tools client should not be available (backend not ready)
      expect(wsAdapter.tools).toBeUndefined()

      // Registration should still work but skip WebSocket subscription
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      }
      const handler = vi.fn().mockResolvedValue(undefined)

      service.registerTool(schema, handler)

      // Tool should be registered even without WebSocket
      const registeredTools = service.getRegisteredTools()
      expect(registeredTools).toHaveLength(1)
    })

    it('should create WebSocket subscription when tools client is available', async () => {
      const wsAdapter = WsAdapter.getInstance()

      // Mock tools client
      const mockSubscribe = vi.fn().mockResolvedValue(undefined)
      const mockUnsubscribe = vi.fn().mockResolvedValue(undefined)
      wsAdapter.tools = {
        subscribe: mockSubscribe,
        unsubscribe: mockUnsubscribe,
      } as never

      const schema: ToolSchema = {
        name: 'displayChart',
        description: 'Display stock chart',
        parameters: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: 'Stock ticker' },
          },
          required: ['symbol'],
        },
      }
      const handler = vi.fn().mockResolvedValue(undefined)

      service.registerTool(schema, handler)

      // Wait for async subscribe to complete
      await vi.waitFor(() => {
        expect(mockSubscribe).toHaveBeenCalledExactlyOnceWith(
          'ihm-command',
          schema,
          expect.any(Function),
        )
      })

      // Cleanup
      wsAdapter.tools = undefined
    })

    it('should execute handler when receiving tool command', async () => {
      const wsAdapter = WsAdapter.getInstance()

      // Mock tools client with callback capture
      let capturedCallback: ((wrapper: { commandId: string; params: unknown }) => Promise<void>) | undefined
      const mockSubscribe = vi.fn().mockImplementation(
        async (
          _topic: string,
          _schema: ToolSchema,
          callback: (wrapper: { commandId: string; params: unknown }) => Promise<void>,
        ) => {
          capturedCallback = callback
        },
      )
      const mockPublish = vi.fn().mockResolvedValue(undefined)

      wsAdapter.tools = {
        subscribe: mockSubscribe,
        unsubscribe: vi.fn().mockResolvedValue(undefined),
        publish: mockPublish,
      } as never

      const handler = vi.fn().mockResolvedValue({ status: 'ok' })
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: 'Stock ticker' },
          },
          required: ['symbol'],
        },
      }

      service.registerTool(schema, handler)

      // Wait for registration to complete
      await vi.waitFor(() => {
        expect(capturedCallback).toBeDefined()
      })

      // Simulate WebSocket message
      const mockCommand = {
        commandId: 'cmd-123',
        params: { symbol: 'AAPL' },
      }

      // Execute the captured callback
      await capturedCallback!(mockCommand)

      // Handler should have been called with params
      expect(handler).toHaveBeenCalledExactlyOnceWith({ symbol: 'AAPL' })

      // Cleanup
      wsAdapter.tools = undefined
    })

    it('should send success response after handler execution', async () => {
      const wsAdapter = WsAdapter.getInstance()

      // Mock tools client with callback capture
      let capturedCallback: ((wrapper: { commandId: string; params: unknown }) => Promise<void>) | undefined
      const mockSubscribe = vi.fn().mockImplementation(
        async (
          _topic: string,
          _schema: ToolSchema,
          callback: (wrapper: { commandId: string; params: unknown }) => Promise<void>,
        ) => {
          capturedCallback = callback
        },
      )
      const mockPublish = vi.fn().mockResolvedValue(undefined)

      wsAdapter.tools = {
        subscribe: mockSubscribe,
        unsubscribe: vi.fn().mockResolvedValue(undefined),
        publish: mockPublish,
      } as never

      const handler = vi.fn().mockResolvedValue({ status: 'ok' })
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      }

      service.registerTool(schema, handler)

      // Wait for registration
      await vi.waitFor(() => {
        expect(capturedCallback).toBeDefined()
      })

      // Simulate command
      await capturedCallback!({ commandId: 'cmd-456', params: {} })

      // Success response should be published
      expect(mockPublish).toHaveBeenCalledExactlyOnceWith('ihm-response', {
        commandId: 'cmd-456',
        tool: 'testTool',
        success: true,
        result: { status: 'ok' },
      })

      // Cleanup
      wsAdapter.tools = undefined
    })

    it('should send error response if handler throws', async () => {
      const wsAdapter = WsAdapter.getInstance()

      // Mock tools client with callback capture
      let capturedCallback: ((wrapper: { commandId: string; params: unknown }) => Promise<void>) | undefined
      const mockSubscribe = vi.fn().mockImplementation(
        async (
          _topic: string,
          _schema: ToolSchema,
          callback: (wrapper: { commandId: string; params: unknown }) => Promise<void>,
        ) => {
          capturedCallback = callback
        },
      )
      const mockPublish = vi.fn().mockResolvedValue(undefined)

      wsAdapter.tools = {
        subscribe: mockSubscribe,
        unsubscribe: vi.fn().mockResolvedValue(undefined),
        publish: mockPublish,
      } as never

      const handler = vi.fn().mockRejectedValue(new Error('Test error'))
      const schema: ToolSchema = {
        name: 'testTool',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      }

      service.registerTool(schema, handler)

      // Wait for registration
      await vi.waitFor(() => {
        expect(capturedCallback).toBeDefined()
      })

      // Simulate command
      await capturedCallback!({ commandId: 'cmd-789', params: {} })

      // Error response should be published
      expect(mockPublish).toHaveBeenCalledExactlyOnceWith('ihm-response', {
        commandId: 'cmd-789',
        tool: 'testTool',
        success: false,
        error: 'Test error',
      })

      // Cleanup
      wsAdapter.tools = undefined
    })

    it('should cleanup WebSocket subscription on unregister', async () => {
      const wsAdapter = WsAdapter.getInstance()

      const mockUnsubscribe = vi.fn().mockResolvedValue(undefined)
      wsAdapter.tools = {
        subscribe: vi.fn().mockResolvedValue(undefined),
        unsubscribe: mockUnsubscribe,
      } as never

      await service.unregisterTool('testTool')

      expect(mockUnsubscribe).toHaveBeenCalledExactlyOnceWith('ihm-command')

      // Cleanup
      wsAdapter.tools = undefined
    })
  })
})
