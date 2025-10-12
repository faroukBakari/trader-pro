/**
 * Bars WebSocket Client Example
 *
 * Demonstrates how to use WebSocketClientBase for bars data subscriptions.
 * This is a concrete implementation that handles bar-specific operations.
 */

import type { Bar, BarsSubscriptionRequest } from './ws-types'
import { WebSocketClientBase, type WebSocketClientConfig } from './wsClientBase'

/**
 * Bar Data Source Interface
 *
 * Abstract interface for subscribing to real-time bar data.
 */
export interface BarsWebSocketInterface {
  /**
   * Subscribe to real-time bar updates
   */
  subscribeToBars(symbol: string, resolution: string, onTick: (bar: Bar) => void): Promise<string>

  /**
   * Unsubscribe from bar updates
   */
  unsubscribe(listenerGuid: string): Promise<void>

  /**
   * Check if connected
   */
  isConnected(): boolean

  /**
   * Dispose and cleanup resources
   */
  dispose(): Promise<void>
}

/**
 * Bars WebSocket Client
 *
 * Extends WebSocketClientBase to provide bars-specific functionality.
 * Implements IBarDataSource interface for compatibility.
 *
 * Uses singleton pattern - multiple instances share the same WebSocket connection.
 * Connection is established automatically on creation with retries.
 *
 * @example
 * ```typescript
 * // Create client (automatically connects)
 * const client = await BarsWebSocketClient.create({
 *   url: 'ws://localhost:8000/api/v1/ws',
 *   debug: true
 * })
 *
 * const subId = await client.subscribeToBars('AAPL', '1', (bar) => {
 *   console.log('New bar:', bar)
 * })
 *
 * // Later: cleanup
 * await client.unsubscribe(subId)
 * await client.dispose() // Clean up when done
 * ```
 */
export class BarsWebSocketClient implements BarsWebSocketInterface {
  private instance: WebSocketClientBase

  /**
   * Map subscription IDs to their parameters for unsubscribe operations
   */
  private subscriptionParams = new Map<
    string,
    {
      symbol: string
      resolution: string
    }
  >()

  /**
   * Private constructor - use create() instead
   */
  private constructor(instance: WebSocketClientBase) {
    this.instance = instance
  }

  /**
   * Create a new BarsWebSocketClient instance
   * Automatically connects to the WebSocket server with retries
   *
   * @param config - WebSocket client configuration
   * @returns Promise that resolves to a connected client instance
   */
  static async create(config: WebSocketClientConfig): Promise<BarsWebSocketClient> {
    const instance = await WebSocketClientBase.getInstance(config)
    return new BarsWebSocketClient(instance)
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.instance.isConnected()
  }

  /**
   * Dispose this client instance
   * Releases the reference to the singleton and disconnects if no more references exist
   */
  async dispose(): Promise<void> {
    // Unsubscribe from all subscriptions
    const subscriptionIds = Array.from(this.subscriptionParams.keys())
    for (const id of subscriptionIds) {
      await this.unsubscribe(id)
    }

    // Release reference to singleton
    await this.instance.releaseInstance()
  }

  /**
   * Subscribe to bar updates for a symbol
   *
   * @param symbol - Trading symbol (e.g., 'AAPL', 'GOOGL')
   * @param resolution - Time resolution ('1', '5', '15', '30', '60', 'D', 'W', 'M')
   * @param onTick - Callback function called when new bar data arrives
   * @returns Subscription ID for unsubscribing
   */
  async subscribeToBars(
    symbol: string,
    resolution: string,
    onTick: (bar: Bar) => void,
  ): Promise<string> {
    // Build expected topic (matches backend topic format)
    const topic = `bars:${symbol}:${resolution}`

    // Prepare subscription payload
    const payload: BarsSubscriptionRequest = {
      symbol,
      resolution,
    }

    // Use base class subscribe with server confirmation
    const subscriptionId = await this.instance.subscribe<BarsSubscriptionRequest, Bar>(
      'bars', // subscription type
      payload, // subscription request
      topic, // expected topic from response
      onTick, // callback for bar updates
    )

    // Store params for unsubscribe
    this.subscriptionParams.set(subscriptionId, { symbol, resolution })
    return subscriptionId
  }

  /**
   * Unsubscribe from bar updates
   *
   * @param listenerGuid - Subscription ID returned from subscribe()
   */
  async unsubscribe(listenerGuid: string): Promise<void> {
    const params = this.subscriptionParams.get(listenerGuid)
    if (!params) {
      return
    }

    // Prepare unsubscribe payload
    const payload: BarsSubscriptionRequest = {
      symbol: params.symbol,
      resolution: params.resolution,
    }

    // Use base class unsubscribe
    await this.instance.unsubscribe(listenerGuid, 'bars.unsubscribe', payload)

    // Clean up params
    this.subscriptionParams.delete(listenerGuid)
  }
}
