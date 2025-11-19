/**
 * IHM Controller Service
 *
 * Manages component tool registration and execution via WebSocket.
 * Each registered tool creates a dedicated WebSocket subscription.
 */

import { WsAdapter, type WsAdapterType } from '@/plugins/wsAdapter'
import type { ToolCommandWrapper, ToolHandler, ToolResponseWrapper, ToolSchema } from '@/types/ihmController'

/**
 * Registered tool entry with schema and handler
 */
export interface RegisteredTool {
  schema: ToolSchema
  handler: ToolHandler<any, any>  // eslint-disable-line @typescript-eslint/no-explicit-any
}

/**
 * IHM Controller Service - Singleton
 *
 * Allows Vue components to register "tools" (programmatic APIs) that can be
 * invoked remotely via WebSocket by external services (AI agents, automation, etc.).
 *
 * @example
 * ```typescript
 * // In a Vue component
 * import { ihmController } from '@/services/ihmControllerService'
 *
 * const schema: ToolSchema = {
 *   name: 'displayStockChart',
 *   description: 'Display stock chart',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       symbol: { type: 'string', description: 'Stock ticker' }
 *     },
 *     required: ['symbol']
 *   }
 * }
 *
 * const handler = async (params: { symbol: string }) => {
 *   await chartWidget.setSymbol(params.symbol)
 * }
 *
 * onMounted(() => {
 *   ihmController.registerTool(schema, handler)
 * })
 *
 * onUnmounted(() => {
 *   ihmController.unregisterTool('displayStockChart')
 * })
 * ```
 */
export class IHMControllerService {
  private static instance: IHMControllerService
  private registeredTools = new Map<string, RegisteredTool>()
  private wsAdapter: WsAdapterType

  private constructor() {
    this.wsAdapter = WsAdapter.getInstance()
  }

  /**
   * Get singleton instance
   */
  static getInstance(): IHMControllerService {
    if (!IHMControllerService.instance) {
      IHMControllerService.instance = new IHMControllerService()
    }
    return IHMControllerService.instance
  }

  /**
   * Register a component tool
   *
   * Creates a WebSocket subscription for the tool. The schema is sent as
   * subscription parameters, allowing the backend to route commands.
   *
   * @param schema - Tool schema (OpenAPI-style)
   * @param handler - Function to execute when tool is invoked
   *
   * @example
   * ```typescript
   * ihmController.registerTool(
   *   {
   *     name: 'displayChart',
   *     description: 'Display stock chart',
   *     parameters: {
   *       type: 'object',
   *       properties: {
   *         symbol: { type: 'string', description: 'Stock ticker' }
   *       },
   *       required: ['symbol']
   *     }
   *   },
   *   async (params) => {
   *     await chartWidget.setSymbol(params.symbol)
   *   }
   * )
   * ```
   */
  registerTool<TParams = Record<string, unknown>, TResult = void>(
    schema: ToolSchema,
    handler: ToolHandler<TParams, TResult>,
  ): void {
    console.log(`[IHMController] Registering tool: ${schema.name}`)

    // Check if tools client is available (backend ready)
    if (!this.wsAdapter.tools) {
      console.warn(`[IHMController] Tools client not available - tool registration skipped: ${schema.name}`)
      this.registeredTools.set(schema.name, { schema, handler })
      return
    }

    // Subscribe to tool-specific commands via WebSocket
    this.wsAdapter.tools
      .subscribe(
        'ihm-command',
        schema, // Schema sent as subscription params
        async (wrapper: ToolCommandWrapper) => {
          try {
            // TODO: Runtime type validation could be added here
            const params = wrapper.params as TParams

            console.log(`[IHMController] Executing tool: ${schema.name}`, params)

            // Execute handler
            const result = await handler(params)

            // Send success response
            const response: ToolResponseWrapper = {
              commandId: wrapper.commandId,
              tool: schema.name,
              success: true,
              result,
            }

            // Publish response if publish method exists
            if ('publish' in this.wsAdapter.tools! && typeof this.wsAdapter.tools.publish === 'function') {
              await (this.wsAdapter.tools.publish as (topic: string, data: unknown) => Promise<void>)(
                'ihm-response',
                response,
              )
            }
          } catch (error) {
            console.error(`[IHMController] Tool execution failed: ${schema.name}`, error)

            // Send error response
            const response: ToolResponseWrapper = {
              commandId: wrapper.commandId,
              tool: schema.name,
              success: false,
              error: error instanceof Error ? error.message : 'Unknown error',
            }

            // Publish response if publish method exists
            if ('publish' in this.wsAdapter.tools! && typeof this.wsAdapter.tools.publish === 'function') {
              await (this.wsAdapter.tools.publish as (topic: string, data: unknown) => Promise<void>)(
                'ihm-response',
                response,
              )
            }
          }
        },
      )
      .then(() => {
        this.registeredTools.set(schema.name, { schema, handler })
        console.log(`[IHMController] Tool registered: ${schema.name}`)
      })
      .catch((error: unknown) => {
        console.error(`[IHMController] Failed to register tool: ${schema.name}`, error)
      })
  }

  /**
   * Unregister a component tool
   *
   * Removes the tool and cleans up its WebSocket subscription.
   *
   * @param toolName - Name of the tool to unregister
   */
  async unregisterTool(toolName: string): Promise<void> {
    console.log(`[IHMController] Unregistering tool: ${toolName}`)

    // Unsubscribe from WebSocket if client available
    if (this.wsAdapter.tools) {
      await this.wsAdapter.tools.unsubscribe('ihm-command')
    }

    this.registeredTools.delete(toolName)

    console.log(`[IHMController] Tool unregistered: ${toolName}`)
  }

  /**
   * Get all registered tools (schemas and handlers)
   *
   * Useful for debugging and testing. Returns full tool information
   * including the handler function for direct invocation in tests.
   *
   * @returns Array of registered tools with schemas and handlers
   *
   * @example
   * ```typescript
   * // Get all tools
   * const tools = ihmController.getRegisteredTools()
   *
   * // Test a tool handler directly
   * const chartTool = tools.find(t => t.schema.name === 'displayStockChart')
   * if (chartTool) {
   *   await chartTool.handler({ symbol: 'AAPL', timeframe: '1D' })
   * }
   * ```
   */
  getRegisteredTools(): RegisteredTool[] {
    return Array.from(this.registeredTools.values())
  }
}

/**
 * Singleton instance export
 *
 * Import this to access the IHM Controller Service from anywhere.
 */
export const ihmController = IHMControllerService.getInstance()
