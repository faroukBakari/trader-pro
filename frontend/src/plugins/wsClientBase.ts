export interface WebSocketClientConfig {
  wsUrl: string
  reconnect?: boolean
  maxReconnectAttempts?: number
  reconnectDelay?: number
  debug?: boolean
}

interface WebSocketMessage<TParams extends object = object> {
  type: string
  payload: TParams
}

interface SubscriptionResponse {
  status: 'ok' | 'error'
  message: string
  topic: string
}

interface SubscriptionState<TParams extends object = object, TData extends object = object> {
  id: string
  topic: string
  onUpdate: (data: TData) => void
  confirmed: boolean
  subscriptionType: string
  subscriptionParams: TParams
  updateMessageType: string
}

export interface WebSocketInterface {
  subscribe<TParams, TData>(params: TParams, onUpdate: (data: TData) => void): Promise<string>
  unsubscribe(listenerGuid: string): Promise<void>
}

export class WebSocketClientBase {
  // Singleton instance per URL
  private static instances = new Map<string, WebSocketClientBase>()
  private readonly config: Required<WebSocketClientConfig>
  protected ws: WebSocket | null = null
  protected subscriptions = new Map<string, SubscriptionState>()
  protected pendingRequests = new Map<
    string,
    {
      resolve: (value: unknown) => void
      reject: (error: Error) => void
      timeout: number
    }
  >()

  private constructor(config: WebSocketClientConfig) {
    this.config = {
      reconnect: config.reconnect ?? true,
      maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
      reconnectDelay: config.reconnectDelay ?? 1000,
      debug: config.debug ?? false,
      wsUrl: config.wsUrl,
    }
  }

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
            setTimeout(async () => await this.resubscribeAll(), 0)
          }

          this.ws.onclose = async (event) => {
            this.log('Connection closed:', event)
            this.ws = null
            setTimeout(async () => await this.resubscribeAll(), 0)
          }
        } catch (error) {
          reject(error)
        }
      })
    } catch (error) {
      this.log('Connection error:', error)
      this.ws = null
      setTimeout(async () => await this.resubscribeAll(), 0)
    }
  }

  private isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  private async sendRequest<TResponse>(
    type: string,
    payload: object,
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

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      const { type, payload } = message

      this.log('Received:', type, payload)

      const pendingRequest = this.pendingRequests.get(type)
      if (pendingRequest) {
        this.pendingRequests.delete(type)
        pendingRequest.resolve(payload)
        return
      }

      if (type.endsWith('.update')) {
        this.routeUpdateMessage(type, payload as WebSocketMessage)
        return
      }

      this.log('Unhandled message type:', type)
    } catch (error) {
      this.log('Failed to parse message:', error)
    }
  }

  private routeUpdateMessage(type: string, data: WebSocketMessage): void {
    for (const subscription of Array.from(this.subscriptions.values())) {
      if (subscription.confirmed && subscription.updateMessageType === type) {
        try {
          subscription.onUpdate(data.payload)
        } catch (error) {
          this.log('Error in subscription onUpdate:', error)
        }
      }
    }
  }

  private async resubscribeAll(): Promise<void> {
    this.log('Resubscribing to all active subscriptions...')

    this.pendingRequests.forEach((pending) => {
      clearTimeout(pending.timeout)
    })

    this.pendingRequests.clear()

    for (const subscription of this.subscriptions.values()) {
      try {
        subscription.confirmed = false

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

  protected log(...args: unknown[]): void {
    if (this.config.debug) {
      console.log('[WebSocketClient]', ...args)
    }
  }

  async subscribe<TParams extends object, TData extends object>(
    subscriptionType: string,
    subscriptionParams: TParams,
    onUpdate: (data: TData) => void,
  ): Promise<string> {
    const topic = `bars:${Object.keys(subscriptionParams)
      .sort()
      .map((key) => subscriptionParams[key as keyof TParams])
      .join(':')}`
    const subscriptionId = `${topic}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Create subscription state (unconfirmed)
    const subscription: SubscriptionState<TParams, TData> = {
      id: subscriptionId,
      topic: topic,
      onUpdate,
      confirmed: false,
      subscriptionType: `${subscriptionType}.subscribe`,
      subscriptionParams: subscriptionParams,
      updateMessageType: `${subscriptionType}.update`,
    }

    this.subscriptions.set(subscriptionId, subscription as unknown as SubscriptionState)

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
}
