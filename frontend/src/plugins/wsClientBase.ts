/**
 * Generic WebSocket Client Base
 *
 * Provides a reusable foundation for WebSocket clients with:
 * - Server-confirmed subscriptions
 * - Topic-based message filtering
 * - Automatic reconnection
 * - Type-safe message handling
 *
 * @module wsClientBase
 */

/**
 * Generic subscription response
 */
export interface SubscriptionResponse {
  /** Status */
  status: 'ok' | 'error'
  /** Status message */
  message: string
  /** Subscription topic */
  topic: string
}

/**
 * WebSocket message envelope
 * All messages follow this structure
 */
export interface WebSocketMessage<T = unknown> {
  /** Operation type (e.g., 'bars.subscribe', 'bars.update') */
  type: string
  /** Operation payload (optional) */
  payload?: T
}

/**
 * WebSocket client configuration
 */
export interface WebSocketClientConfig {
  /**
   * WebSocket server URL
   * @example 'ws://localhost:8000/api/v1/ws'
   */
  url: string

  /**
   * Enable automatic reconnection on disconnect
   * @default true
   */
  reconnect?: boolean

  /**
   * Maximum number of reconnection attempts
   * @default 5
   */
  maxReconnectAttempts?: number

  /**
   * Initial reconnection delay in milliseconds (uses exponential backoff)
   * @default 1000
   */
  reconnectDelay?: number

  /**
   * Enable debug logging
   * @default false
   */
  debug?: boolean
}

/**
 * Subscription state
 */
interface SubscriptionState<T> {
  /** Unique subscription ID */
  id: string
  /** Topic for filtering messages */
  topic: string
  /** Callback for data updates */
  callback: (data: T) => void
  /** Subscription confirmed by server */
  confirmed: boolean
  /** Original subscription payload for resubscription */
  subscriptionType: string
  subscriptionParams: unknown
  updateMessageType: string
}

/**
 * Generic WebSocket Client Base Class (Singleton)
 *
 * Handles WebSocket connection, subscriptions with server confirmation,
 * and topic-based message routing.
 *
 * Uses singleton pattern to ensure only one WebSocket connection per URL.
 * Multiple subscriptions share the same connection.
 *
 * @example
 * ```typescript
 * class BarsClient extends WebSocketClientBase {
 *   async subscribeToBars(symbol: string, resolution: string, callback: (bar: Bar) => void) {
 *     const topic = `bars:${symbol}:${resolution}`
 *     return this.subscribe(
 *       'bars.subscribe',
 *       { symbol, resolution },
 *       topic,
 *       'bars.update',
 *       callback
 *     )
 *   }
 * }
 * ```
 */
export class WebSocketClientBase {
  // Singleton instance per URL
  private static instances = new Map<string, WebSocketClientBase>()

  protected ws: WebSocket | null = null
  protected subscriptions = new Map<string, SubscriptionState<unknown>>()
  protected pendingRequests = new Map<
    string,
    {
      resolve: (value: unknown) => void
      reject: (error: Error) => void
      timeout: number
    }
  >()

  private reconnectAttempts = 0
  private isReconnecting = false
  private reconnectTimer: number | null = null
  private readonly config: Required<WebSocketClientConfig>
  private referenceCount = 0

  /**
   * Private constructor - use getInstance() instead
   */
  private constructor(config: WebSocketClientConfig) {
    this.config = {
      reconnect: config.reconnect ?? true,
      maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
      reconnectDelay: config.reconnectDelay ?? 1000,
      debug: config.debug ?? false,
      ...config,
    }
  }

  /**
   * Get singleton instance for a WebSocket URL
   * Automatically connects to the WebSocket server with retries
   *
   * @param config - WebSocket client configuration
   * @returns Promise that resolves to singleton instance for the URL
   */
  static async getInstance(config: WebSocketClientConfig): Promise<WebSocketClientBase> {
    const url = config.url
    let instance = WebSocketClientBase.instances.get(url)

    if (!instance) {
      instance = new WebSocketClientBase(config)
      WebSocketClientBase.instances.set(url, instance)
      instance.log('Created new WebSocket instance for', url)

      // Auto-connect with retries
      await instance.connectWithRetries()
    } else {
      // Update config if needed (merge with existing)
      instance.updateConfig(config)
      instance.log('Reusing existing WebSocket instance for', url)

      // Ensure connection is alive
      if (!instance.isConnected()) {
        await instance.connectWithRetries()
      }
    }

    instance.referenceCount++
    return instance
  }

  /**
   * Update configuration (merge with existing)
   */
  private updateConfig(newConfig: Partial<WebSocketClientConfig>): void {
    if (newConfig.reconnect !== undefined) {
      this.config.reconnect = newConfig.reconnect
    }
    if (newConfig.maxReconnectAttempts !== undefined) {
      this.config.maxReconnectAttempts = newConfig.maxReconnectAttempts
    }
    if (newConfig.reconnectDelay !== undefined) {
      this.config.reconnectDelay = newConfig.reconnectDelay
    }
    if (newConfig.debug !== undefined) {
      this.config.debug = newConfig.debug
    }
  }

  /**
   * Release reference to this instance
   * Automatically disconnects when reference count reaches 0
   */
  async releaseInstance(): Promise<void> {
    this.referenceCount--
    this.log(`Reference count: ${this.referenceCount}`)

    if (this.referenceCount <= 0) {
      this.log('No more references, cleaning up...')

      // Clear all subscriptions
      this.subscriptions.clear()

      // Force disconnect
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }

      if (this.ws) {
        this.ws.close()
        this.ws = null
      }

      this.pendingRequests.clear()

      // Remove from instances map
      WebSocketClientBase.instances.delete(this.config.url)
      this.log('Cleanup complete')
    }
  }

  /**
   * Connect with retries (used during initialization)
   */
  private async connectWithRetries(): Promise<void> {
    const maxAttempts = this.config.maxReconnectAttempts
    let attempt = 0

    while (attempt < maxAttempts) {
      try {
        await this.connect()
        return // Success
      } catch (error) {
        attempt++
        if (attempt >= maxAttempts) {
          throw new Error(`Failed to connect after ${maxAttempts} attempts: ${error}`)
        }

        const delay = this.config.reconnectDelay * Math.pow(2, attempt - 1)
        this.log(`Connection attempt ${attempt}/${maxAttempts} failed, retrying in ${delay}ms...`)
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }
  }

  /**
   * Connect to WebSocket server
   */
  private async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.log('Already connected')
      return
    }

    return new Promise((resolve, reject) => {
      try {
        this.log('Connecting to', this.config.url)
        this.ws = new WebSocket(this.config.url)

        this.ws.onopen = () => {
          this.log('Connected')
          this.reconnectAttempts = 0
          this.isReconnecting = false
          resolve()
        }

        this.ws.onmessage = (event) => {
          this.handleMessage(event)
        }

        this.ws.onerror = (error) => {
          this.log('Error:', error)
          reject(error)
        }

        this.ws.onclose = (event) => {
          this.log('Closed:', event.code, event.reason)
          this.handleDisconnect()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  /**
   * Disconnect from WebSocket server
   * Only closes connection if no more subscriptions exist
   */
  private async disconnect(): Promise<void> {
    // Don't disconnect if there are active subscriptions
    if (this.subscriptions.size > 0) {
      this.log('Cannot disconnect: active subscriptions exist')
      return
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this.pendingRequests.clear()
    this.log('Disconnected')
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Subscribe to a topic with server confirmation
   *
   * @param subscribeType - Subscription message type (e.g., 'bars.subscribe')
   * @param subscriptionParams - Subscription request payload
   * @param topic - Expected topic from server response
   * @param updateMessageType - Update message type to listen for (e.g., 'bars.update')
   * @param callback - Callback for data updates
   * @returns Subscription ID for unsubscribing
   *
   * @example
   * ```typescript
   * const subId = await client.subscribe(
   *   'bars.subscribe',
   *   { symbol: 'AAPL', resolution: '1' },
   *   'bars:AAPL:1',
   *   'bars.update',
   *   (bar) => console.log('New bar:', bar)
   * )
   * ```
   */
  async subscribe<TPayload, TData>(
    subscriptionType: string,
    subscriptionParams: TPayload,
    topic: string,
    callback: (data: TData) => void,
  ): Promise<string> {
    // Ensure connected
    if (!this.isConnected()) {
      await this.connect()
    }

    // Generate unique subscription ID
    const subscriptionId = `${topic}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Create subscription state (unconfirmed)
    const subscription: SubscriptionState<TData> = {
      id: subscriptionId,
      topic: topic,
      callback,
      confirmed: false,
      subscriptionType: `${subscriptionType}.subscribe`,
      subscriptionParams: subscriptionParams,
      updateMessageType: `${subscriptionType}.update`,
    }

    this.subscriptions.set(subscriptionId, subscription as SubscriptionState<unknown>)

    // Send subscription request and wait for confirmation
    try {
      const response = await this.sendRequest<SubscriptionResponse>(
        subscriptionType,
        subscriptionParams,
        5000, // 5 second timeout
      )

      // Verify topic matches
      if (response.topic !== topic) {
        throw new Error(`Topic mismatch: expected "${topic}", got "${response.topic}"`)
      }

      // Verify status is ok
      if (response.status !== 'ok') {
        throw new Error(`Subscription failed: ${response.message}`)
      }

      // Mark subscription as confirmed
      subscription.confirmed = true
      this.log(`Subscription confirmed: ${topic}`, response)

      return subscriptionId
    } catch (error) {
      // Remove failed subscription
      this.subscriptions.delete(subscriptionId)
      throw error
    }
  }

  /**
   * Unsubscribe from a topic
   *
   * @param subscriptionId - Subscription ID returned from subscribe()
   * @param unsubscribeType - Unsubscribe message type (e.g., 'bars.unsubscribe')
   * @param unsubscribePayload - Unsubscribe request payload
   */
  async unsubscribe<TPayload>(
    subscriptionId: string,
    unsubscribeType: string,
    unsubscribePayload: TPayload,
  ): Promise<void> {
    const subscription = this.subscriptions.get(subscriptionId)
    if (!subscription) {
      this.log('Subscription not found:', subscriptionId)
      return
    }

    try {
      // Send unsubscribe request
      const response = await this.sendRequest<SubscriptionResponse>(
        unsubscribeType,
        unsubscribePayload,
        5000,
      )

      // Verify status
      if (response.status !== 'ok') {
        this.log('Unsubscribe warning:', response.message)
      }

      this.log(`Unsubscribed from ${subscription.topic}`)
    } finally {
      // Always remove subscription from map
      this.subscriptions.delete(subscriptionId)
    }
  }

  /**
   * Send a request and wait for response
   *
   * @param type - Message type
   * @param payload - Message payload
   * @param timeout - Response timeout in milliseconds
   * @returns Response payload
   */
  async sendRequest<TResponse>(
    type: string,
    payload: unknown,
    timeout: number = 5000,
  ): Promise<TResponse> {
    if (!this.isConnected()) {
      throw new Error('WebSocket not connected')
    }

    return new Promise((resolve, reject) => {
      const message: WebSocketMessage = { type, payload }
      const messageStr = JSON.stringify(message)

      // Expected response type
      const responseType = `${type}.response`

      // Set up timeout
      const timeoutId = window.setTimeout(() => {
        this.pendingRequests.delete(responseType)
        reject(new Error(`Request timeout: ${type}`))
      }, timeout)

      // Register response handler
      this.pendingRequests.set(responseType, {
        resolve: (response: unknown) => {
          clearTimeout(timeoutId)
          resolve(response as TResponse)
        },
        reject: (error: Error) => {
          clearTimeout(timeoutId)
          reject(error)
        },
        timeout: timeoutId,
      })

      // Send message
      this.ws!.send(messageStr)
      this.log('Sent:', type, payload)
    })
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      const { type, payload } = message

      this.log('Received:', type, payload)

      // Check if this is a response to a pending request
      const pendingRequest = this.pendingRequests.get(type)
      if (pendingRequest) {
        this.pendingRequests.delete(type)
        pendingRequest.resolve(payload)
        return
      }

      // Check if this is an update message for any subscriptions
      if (type.endsWith('.update')) {
        this.routeUpdateMessage(type, payload)
        return
      }

      this.log('Unhandled message type:', type)
    } catch (error) {
      this.log('Failed to parse message:', error)
    }
  }

  /**
   * Route update message to appropriate subscription callbacks
   * Filters by topic - only confirmed subscriptions with matching updateType receive the data
   */
  private routeUpdateMessage(type: string, payload: unknown): void {
    // Iterate through all confirmed subscriptions with matching update message type
    for (const subscription of Array.from(this.subscriptions.values())) {
      if (subscription.confirmed && subscription.updateMessageType === type) {
        // Call the callback with the payload
        // Topic filtering is implicit - each subscription only receives its own updates
        try {
          subscription.callback(payload)
        } catch (error) {
          this.log('Error in subscription callback:', error)
        }
      }
    }
  }

  /**
   * Handle WebSocket disconnect
   */
  private handleDisconnect(): void {
    this.ws = null

    if (!this.config.reconnect || this.isReconnecting) {
      return
    }

    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.log('Max reconnection attempts reached')
      return
    }

    this.isReconnecting = true
    this.reconnectAttempts++

    const delay = this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    this.log(
      `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`,
    )

    this.reconnectTimer = window.setTimeout(async () => {
      try {
        await this.connect()
        await this.resubscribeAll()
      } catch (error) {
        this.log('Reconnection failed:', error)
        this.isReconnecting = false
        this.handleDisconnect()
      }
    }, delay)
  }

  /**
   * Resubscribe to all confirmed subscriptions after reconnect
   */
  private async resubscribeAll(): Promise<void> {
    this.log('Resubscribing to all active subscriptions...')

    const subscriptionsToRestore = Array.from(this.subscriptions.values()).filter(
      (sub) => sub.confirmed,
    )

    for (const subscription of subscriptionsToRestore) {
      try {
        // Mark as unconfirmed for resubscription
        subscription.confirmed = false

        // Resubscribe using stored parameters
        const response = await this.sendRequest<SubscriptionResponse>(
          subscription.subscriptionType,
          subscription.subscriptionParams,
          5000,
        )

        if (response.status === 'ok' && response.topic === subscription.topic) {
          subscription.confirmed = true
          this.log(`Resubscribed to ${subscription.topic}`)
        } else {
          throw new Error(`Resubscription failed: ${response.message}`)
        }
      } catch (error) {
        this.log(`Failed to resubscribe to ${subscription.topic}:`, error)
        this.subscriptions.delete(subscription.id)
      }
    }
  }

  /**
   * Log debug messages if debug mode enabled
   */
  protected log(...args: unknown[]): void {
    if (this.config.debug) {
      console.log('[WebSocketClient]', ...args)
    }
  }

  /**
   * Get all active subscriptions
   */
  getSubscriptions(): ReadonlyMap<string, Readonly<SubscriptionState<unknown>>> {
    return this.subscriptions
  }

  /**
   * Get subscription count
   */
  getSubscriptionCount(): number {
    return this.subscriptions.size
  }

  /**
   * Get confirmed subscription count
   */
  getConfirmedSubscriptionCount(): number {
    return Array.from(this.subscriptions.values()).filter((sub) => sub.confirmed).length
  }
}
