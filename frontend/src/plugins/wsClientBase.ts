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
  wsUrl: string

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
  /** onUpdate for data updates */
  onUpdate: (data: T) => void
  /** Subscription confirmed by server */
  confirmed: boolean
  /** Original subscription payload for resubscription */
  subscriptionType: string
  subscriptionParams: unknown
  updateMessageType: string
}

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

  private readonly config: Required<WebSocketClientConfig>

  /**
   * Private constructor - use getInstance() instead
   */
  private constructor(config: WebSocketClientConfig) {
    this.config = {
      reconnect: config.reconnect ?? true,
      maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
      reconnectDelay: config.reconnectDelay ?? 1000,
      debug: config.debug ?? false,
      wsUrl: config.wsUrl,
    }
  }

  /**
   * Get singleton instance for a WebSocket URL
   * Automatically connects to the WebSocket server with retries
   *
   * @param config - WebSocket client configuration
   * @returns Promise that resolves to singleton instance for the URL
   */
  static getInstance(): WebSocketClientBase {
    const wsUrl = '/api/v1/ws' // TODO: Make configurable
    const config: WebSocketClientConfig = { wsUrl }
    console.log('[Datafeed] Initializing WebSocket client:', config)
    let instance = WebSocketClientBase.instances.get(wsUrl)

    if (!instance) {
      instance = new WebSocketClientBase(config)
      WebSocketClientBase.instances.set(wsUrl, instance)
      instance.log('Created new WebSocket instance for', wsUrl)
    } else {
      instance.log('Reusing existing WebSocket instance for', wsUrl)
    }

    return instance
  }

  private async connect(): Promise<void> {
    try {
      if (this.isConnected()) {
        this.log('Already connected')
        return
      }

      return new Promise((resolve, reject) => {
        try {
          this.log('Connecting to', this.config.wsUrl)
          this.ws = new WebSocket(this.config.wsUrl)

          this.ws.onopen = () => {
            this.log('Connected')
            resolve()
          }

          this.ws.onmessage = (event) => {
            this.handleMessage(event)
          }

          this.ws.onerror = async (error) => {
            this.log('Error:', error)
            this.ws = null
            await this.resubscribeAll()
          }

          this.ws.onclose = async (event) => {
            this.log('Connection closed:', event)
            this.ws = null
            await this.resubscribeAll()
          }
        } catch (error) {
          reject(error)
        }
      })
    } catch (error) {
      this.log('Connection error:', error)
      this.ws = null
      await this.resubscribeAll()
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  async subscribe<TPayload, TData>(
    subscriptionType: string,
    subscriptionParams: TPayload,
    topic: string,
    onUpdate: (data: TData) => void,
  ): Promise<string> {
    // Ensure connected

    // Generate unique subscription ID
    const subscriptionId = `${topic}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Create subscription state (unconfirmed)
    const subscription: SubscriptionState<TData> = {
      id: subscriptionId,
      topic: topic,
      onUpdate,
      confirmed: false,
      subscriptionType: `${subscriptionType}.subscribe`,
      subscriptionParams: subscriptionParams,
      updateMessageType: `${subscriptionType}.update`,
    }

    this.subscriptions.set(subscriptionId, subscription as SubscriptionState<unknown>)

    // Send subscription request and wait for confirmation
    while (true)
      try {
        const response = await this.sendRequest<SubscriptionResponse>(
          subscription.subscriptionType,
          subscription.subscriptionParams,
          5000, // 5 second timeout
        )

        if (response.status !== 'ok') {
          throw new Error(response.message)
        }

        subscription.confirmed = true
        this.log(`Subscription confirmed: ${topic}`, response)
        return subscriptionId
      } catch (error) {
        this.log('Subscription error:', error)
      }
  }

  async unsubscribe(subscriptionId: string): Promise<void> {
    const subscription = this.subscriptions.get(subscriptionId)
    if (subscription) {
      const unsubscribeType = subscription.subscriptionType.replace('subscribe', 'unsubscribe')
      const unsubscribePayload = subscription.subscriptionParams

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
    await this.connect()

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
      // Wierd stuff about fastws implementation that encapsulates WebSocketMessage in another layer of WebSocketMessage
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
        this.routeUpdateMessage(type, payload as WebSocketMessage)
        return
      }

      this.log('Unhandled message type:', type)
    } catch (error) {
      this.log('Failed to parse message:', error)
    }
  }

  /**
   * Route update message to appropriate subscription onUpdates
   * Filters by topic - only confirmed subscriptions with matching updateType receive the data
   */
  private routeUpdateMessage(type: string, data: WebSocketMessage): void {
    // Iterate through all confirmed subscriptions with matching update message type
    for (const subscription of Array.from(this.subscriptions.values())) {
      if (subscription.confirmed && subscription.updateMessageType === type) {
        // Call the onUpdate with the payload
        // Topic filtering is implicit - each subscription only receives its own updates
        try {
          subscription.onUpdate(data.payload)
        } catch (error) {
          this.log('Error in subscription onUpdate:', error)
        }
      }
    }
  }

  /**
   * Resubscribe to all confirmed subscriptions after reconnect
   */
  private async resubscribeAll(): Promise<void> {
    this.log('Resubscribing to all active subscriptions...')

    this.pendingRequests.clear()

    for (const subscription of this.subscriptions.values()) {
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
