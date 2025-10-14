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

export interface WebSocketInterface<TParams extends object, TData extends object> {
  subscribe(params: TParams, onUpdate: (data: TData) => void): Promise<string>
  unsubscribe(listenerGuid: string): Promise<void>
}

export class WebSocketClientBase<TParams extends object, TData extends object> {
  private static readonly config = {
    reconnect: true,
    maxReconnectAttempts: 5,
    reconnectDelay: 1000,
    debug: false,
    wsUrl: '/api/v1/ws', // TODO: make configurable
  }
  protected static ws: WebSocket | null = null
  protected subscriptions = new Map<string, SubscriptionState>()
  protected pendingRequests = new Map<
    string,
    {
      resolve: (value: SubscriptionResponse) => void
      reject: (error: Error) => void
      timeout: NodeJS.Timeout
    }
  >()

  private topicType: string = ''

  constructor(topicType: string) {
    this.topicType = topicType
  }

  private async __socketConnect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        console.log('Connecting to', WebSocketClientBase.config.wsUrl)
        WebSocketClientBase.ws = new WebSocket(WebSocketClientBase.config.wsUrl)

        WebSocketClientBase.ws.onerror = async (error) => {
          console.log('Error:', error)
          reject(error)
        }

        WebSocketClientBase.ws.onclose = async (event) => {
          console.log('Connection closed:', event)
          reject(new Error('WebSocket closed'))
        }

        WebSocketClientBase.ws.onopen = () => {
          console.log('Connected')

          WebSocketClientBase.ws!.onmessage = (event) => {
            this.handleMessage(event)
          }

          WebSocketClientBase.ws!.onerror = async (error) => {
            console.log('Error:', error)
            this.resubscribeAll()
          }

          WebSocketClientBase.ws!.onclose = async (event) => {
            console.log('Connection closed:', event)
            this.resubscribeAll()
          }
          resolve()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  private async connect(): Promise<void> {
    while (!this.isConnected()) {
      try {
        await this.__socketConnect()
      } catch (error) {
        this.log('Connection error:', error)
      }
    }
  }

  private isConnected(): boolean {
    return WebSocketClientBase.ws?.readyState === WebSocket.OPEN
  }

  private async sendRequest(type: string, payload: object): Promise<void> {
    await this.connect()
    const message = JSON.stringify({ type, payload })
    WebSocketClientBase.ws!.send(message)
    this.log('Sent:', type, payload)
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      const { type, payload } = message

      this.log('Received:', type, payload)

      if (type.endsWith('.update')) {
        const update = payload as WebSocketMessage
        this.routeUpdateMessage(type, update)
      } else {
        const subResponse = payload as SubscriptionResponse
        const requestId = `${type}-${subResponse.topic}`
        const pendingRequest = this.pendingRequests.get(requestId)
        if (pendingRequest) {
          this.pendingRequests.delete(requestId)
          pendingRequest.resolve(subResponse)
          return
        } else {
          console.log('Unhandled message type:', type)
        }
      }
    } catch (error) {
      console.log('Failed to parse message:', error)
    }
  }

  private routeUpdateMessage(type: string, data: WebSocketMessage): void {
    for (const subscription of Array.from(this.subscriptions.values())) {
      if (subscription.confirmed && subscription.updateMessageType === type) {
        try {
          subscription.onUpdate(data.payload)
        } catch (error) {
          console.log('Error in subscription onUpdate:', error)
        }
      }
    }
  }

  private async __subscribe(subscription: SubscriptionState): Promise<SubscriptionResponse> {
    while (true)
      try {
        subscription.confirmed = false

        await this.sendRequest(subscription.subscriptionType, subscription.subscriptionParams)

        const response: SubscriptionResponse = await new Promise((resolve, reject) => {
          // Expected response type
          const responseType = `${subscription.subscriptionType}.response`
          const requestId = `${responseType}-${subscription.topic}`

          // Set up timeout
          const timeout = setTimeout(() => {
            this.pendingRequests.delete(requestId)
            reject(new Error(`Request timeout: ${subscription.subscriptionType}`))
          }, 5000)

          // Register response handler
          this.pendingRequests.set(requestId, {
            resolve: (response: SubscriptionResponse) => {
              clearTimeout(timeout)
              resolve(response)
            },
            reject: (error: Error) => {
              clearTimeout(timeout)
              reject(error)
            },
            timeout,
          })
        })

        if (response.status !== 'ok') {
          throw new Error(response.message)
        }

        subscription.confirmed = true
        console.log(`Subscription confirmed: ${subscription.topic}`, response)
        return response
      } catch (error) {
        console.log('Subscription error:', error)
      }
  }

  private async resubscribeAll(): Promise<void> {
    console.log('Resubscribing to all active subscriptions...')

    this.pendingRequests.forEach((pending) => {
      clearTimeout(pending.timeout)
    })

    this.pendingRequests.clear()

    for (const subscription of this.subscriptions.values()) {
      await this.__subscribe(subscription)
    }
  }

  protected log(...args: unknown[]): void {
    if (WebSocketClientBase.config.debug) {
      console.log('[WebSocketClient]', ...args)
    }
  }

  async subscribe(subscriptionParams: TParams, onUpdate: (data: TData) => void): Promise<string> {
    const topic = `${this.topicType}:${Object.keys(subscriptionParams)
      .sort()
      .map((key) => subscriptionParams[key as keyof TParams])
      .join(':')}`
    const subscriptionId = `${topic}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Create subscription state (unconfirmed)
    const subscription: SubscriptionState<TParams, TData> = {
      id: subscriptionId,
      topic,
      onUpdate,
      confirmed: false,
      subscriptionType: `${this.topicType}.subscribe`,
      subscriptionParams: subscriptionParams,
      updateMessageType: `${this.topicType}.update`,
    }

    this.subscriptions.set(subscriptionId, subscription as unknown as SubscriptionState)

    // Send subscription request and wait for confirmation
    await this.__subscribe(subscription as unknown as SubscriptionState)
    return subscriptionId
  }

  async unsubscribe(subscriptionId: string): Promise<void> {
    const subscription = this.subscriptions.get(subscriptionId)
    if (subscription) {
      const unsubscribeType = subscription.subscriptionType.replace('subscribe', 'unsubscribe')
      const unsubscribePayload = subscription.subscriptionParams

      try {
        await this.sendRequest(unsubscribeType, unsubscribePayload)
      } finally {
        this.subscriptions.delete(subscriptionId)
      }
    }
  }
}
