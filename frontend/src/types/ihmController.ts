/**
 * IHM Controller Service Type Definitions
 *
 * Types for component tool registration and remote invocation via WebSocket.
 * Allows Vue components to expose programmatic APIs that can be called by
 * external services (WebSocket handlers, AI agents, automation tools).
 */

/**
 * Tool parameter property definition (OpenAPI-style)
 */
export interface ToolParameterDefinition {
    type: 'string' | 'number' | 'boolean' | 'object' | 'array'
    description: string
    enum?: string[]
    default?: unknown
    pattern?: string
    items?: ToolParameterDefinition
    properties?: Record<string, ToolParameterDefinition>
}

/**
 * Tool schema - OpenAPI-style tool description
 *
 * Used for:
 * - WebSocket subscription parameters
 * - AI agent tool discovery
 * - Auto-generated documentation
 *
 * @example
 * ```typescript
 * const displayChartSchema: ToolSchema = {
 *   name: 'displayStockChart',
 *   description: 'Display stock chart. Use for "show AAPL chart" or "plot TSLA".',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       symbol: {
 *         type: 'string',
 *         description: 'Stock ticker symbol (e.g., "AAPL", "TSLA")',
 *         pattern: '^[A-Z]{1,5}$'
 *       },
 *       timeframe: {
 *         type: 'string',
 *         description: 'Chart interval',
 *         enum: ['1', '5', '15', '60', '1D', '1W', '1M'],
 *         default: '1D'
 *       }
 *     },
 *     required: ['symbol']
 *   }
 * }
 * ```
 */
export interface ToolSchema {
    /** Unique tool identifier (e.g., 'displayStockChart') */
    name: string

    /** Human-readable description for AI agents and documentation */
    description: string

    /** Parameter schema (OpenAPI-style) */
    parameters: {
        type: 'object'
        properties: Record<string, ToolParameterDefinition>
        required?: string[]
    }
}

/**
 * Tool handler function signature
 *
 * Async function that executes tool logic when invoked via WebSocket.
 *
 * @template TParams - Tool parameter types
 * @template TResult - Tool return type (default: void)
 *
 * @example
 * ```typescript
 * const handler: ToolHandler<{ symbol: string; timeframe?: string }, void> =
 *   async (params) => {
 *     await chartWidget.setSymbol(params.symbol, params.timeframe || '1D')
 *   }
 * ```
 */
export type ToolHandler<TParams = Record<string, unknown>, TResult = void> =
    (params: TParams) => Promise<TResult>

/**
 * Tool command wrapper (WebSocket message from backend)
 *
 * @template TParams - Tool parameter types
 */
export interface ToolCommandWrapper<TParams = unknown> {
    /** Unique command ID for response correlation */
    commandId: string

    /** Tool invocation parameters */
    params: TParams
}

/**
 * Tool response wrapper (WebSocket message to backend)
 */
export interface ToolResponseWrapper {
    /** Command ID from request (for correlation) */
    commandId: string

    /** Tool name that was executed */
    tool: string

    /** Success flag */
    success: boolean

    /** Tool result (if successful) */
    result?: unknown

    /** Error message (if failed) */
    error?: string
}
