// interface WebSocketClientBaseConfig {
//   wsUrl: string
//   reconnect?: boolean
//   maxReconnectAttempts?: number
//   reconnectDelay?: number
//   debug?: boolean
// }


interface DataFeed<TBackendData extends object = object> {
  topic: string
  payload: TBackendData
}

interface SubscriptionResponse {
  status: 'ok' | 'error'
  message: string
  topic: string
}

interface WebSocketMessage<TBackendData extends object = object> {
  type: string
  payload: DataFeed<TBackendData> | SubscriptionResponse
}

interface SubscriptionState<TParams extends object = object, TData extends object = object> {
  topic: string
  subscriptionParams: TParams
  confirmed: boolean
  subscriptionType: string
  listeners: Map<string, (data: TData) => void>
}

function buildTopicParams(obj: unknown): string {
  if (obj === null || obj === undefined) {
    return ''
  }

  if (typeof obj !== 'object') {
    return JSON.stringify(obj)
  }

  if (Array.isArray(obj)) {
    return `[${obj.map(buildTopicParams).join(',')}]`
  }

  const objRecord = obj as Record<string, unknown>
  const sortedKeys = Object.keys(objRecord).sort()
  const pairs = sortedKeys.map(key => `${JSON.stringify(key)}:${buildTopicParams(objRecord[key])}`)
  return `{${pairs.join(',')}}`
}

export class WebSocketBase {
  private readonly config = {
    reconnect: true,
    maxReconnectAttempts: 5,
    reconnectDelay: 1000,
    debug: true,
    wsUrl: '/api/v1/ws', // TODO: make configurable
  }
  protected ws: WebSocket | null = null
  protected wsCnxPromise: Promise<void> | null = null
  protected pendingRequests = new Map<
    string,
    {
      resolve: (value: SubscriptionResponse) => void
      reject: (error: Error) => void
      timeout: NodeJS.Timeout
    }
  >()
  protected subscriptions = new Map<string, SubscriptionState>()

  // dont defaut to identity dataMapper to detect types missmatch (data => data as unknown as TData)
  private static instance: WebSocketBase | null = null

  private constructor() { }

  static getInstance(): WebSocketBase {
    if (!WebSocketBase.instance) {
      WebSocketBase.instance = new WebSocketBase()
    }
    return WebSocketBase.instance
  }

  private async __socketConnect(): Promise<void> {
    if (!this.wsCnxPromise) {
      this.wsCnxPromise = new Promise((resolve, reject) => {
        try {
          console.log('Connecting to', this.config.wsUrl)
          this.ws = new WebSocket(this.config.wsUrl)

          this.ws.onerror = async (error) => {
            console.log('Error:', error)
            reject(error)
          }

          this.ws.onclose = async (event) => {
            console.log('Connection closed:', event)
            reject(new Error('WebSocket closed'))
          }

          this.ws.onopen = () => {
            console.log('Connected')

            this.ws!.onmessage = (event) => {
              this.handleMessage(event)
            }

            this.ws!.onerror = async (error) => {
              console.log('Error:', error)
              setTimeout(() => this.resubscribeAll(), 0)
            }

            this.ws!.onclose = async (event) => {
              console.log('Connection closed:', event)
              setTimeout(() => this.resubscribeAll(), 0)
            }
            setTimeout(() => (this.wsCnxPromise = null), 0)
            resolve()
          }
        } catch (error) {
          setTimeout(() => (this.wsCnxPromise = null), 0)
          reject(error)
        }
      })
    }

    return this.wsCnxPromise
  }

  private async connect(): Promise<void> {
    while (!this.isConnected()) {
      try {
        await this.__socketConnect()
      } catch (error) {
        console.log('Connection error:', error)
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
    }
  }

  private isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  private async sendRequest(type: string, payload: object): Promise<void> {
    await this.connect()
    const message = JSON.stringify({ type, payload })
    this.ws!.send(message)
    console.log('Sent:', type, payload)
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      const { type, payload } = message

      if (type.endsWith('.update')) {
        const update = payload as DataFeed
        this.routeUpdateMessage(update)
      } else {
        console.log('Received:', type, payload)
        if (type.endsWith('.response')) {
          if (type.replace(/.response$/, '').endsWith('.subscribe')) {
            const subResponse = payload as SubscriptionResponse
            const requestId = `${type.replace(/.response$/, '')}-${subResponse.topic}`
            const pendingRequest = this.pendingRequests.get(requestId)
            if (pendingRequest) {
              this.pendingRequests.delete(requestId)
              pendingRequest.resolve(subResponse)
            } else {
              console.error('Cannot find request Id:', requestId)
            }
          }
        } else {
          console.error('Unknown message type:', type)
        }
      }
    } catch (error) {
      console.error('Failed to parse message:', error)
    }
  }

  private routeUpdateMessage(data: DataFeed): void {
    for (const subscription of Array.from(this.subscriptions.values())) {
      if (subscription.confirmed && subscription.topic === data.topic) {
        try {
          for (const onUpdate of subscription.listeners.values()) {
            onUpdate(data.payload)
          }
        } catch (error) {
          console.error('Error in subscription onUpdate:', error)
        }
      }
    }
  }

  async subscribe(
    topic: string,
    subscriptionType: string,
    subscriptionParams: object,
    listenerId: string,
    onUpdate: (TbackendData: object) => void
  ): Promise<SubscriptionState> {

    let subscription = this.subscriptions.get(topic)
    if (subscription) {
      subscription?.listeners.set(listenerId, onUpdate)
      return subscription;
    }

    subscription = {
      topic,
      subscriptionParams,
      subscriptionType,
      confirmed: false,
      listeners: new Map<string, (data: object) => void>([[listenerId, onUpdate]]),
    }

    this.subscriptions.set(topic, subscription)

    while (true)
      try {
        subscription.confirmed = false

        const response: SubscriptionResponse = await new Promise((resolve, reject) => {
          // Expected response type
          const requestId = `${subscription.subscriptionType}-${subscription.topic}`

          // Set up timeout
          const timeout = setTimeout(() => {
            this.pendingRequests.delete(requestId)
            reject(new Error(`Request timeout: ${requestId}`))
          }, 15000)

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

          // Send request after registering the handler
          this.sendRequest(subscription.subscriptionType, subscription.subscriptionParams)
            .catch((error) => {
              this.pendingRequests.delete(requestId)
              clearTimeout(timeout)
              reject(error)
            })
        })

        if (response.status !== 'ok') {
          throw new Error(response.message)
        }

        subscription.confirmed = true
        console.log(`Subscription confirmed: ${subscription.topic}`, response)
        return subscription
      } catch (error) {
        console.error('Subscription error:', error)
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
  }

  private async resubscribeAll(): Promise<void> {
    console.log('Resubscribing to all active subscriptions...')

    await new Promise(resolve => setTimeout(resolve, 2000))

    this.pendingRequests.forEach((pending) => {
      clearTimeout(pending.timeout)
    })

    this.pendingRequests.clear()

    for (const subscription of this.subscriptions.values()) {
      subscription.confirmed = false

      const response: SubscriptionResponse = await new Promise((resolve, reject) => {
        const requestId = `${subscription.subscriptionType}-${subscription.topic}`

        const timeout = setTimeout(() => {
          this.pendingRequests.delete(requestId)
          reject(new Error(`Request timeout: ${requestId}`))
        }, 15000)

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

        this.sendRequest(subscription.subscriptionType, subscription.subscriptionParams)
          .catch((error) => {
            this.pendingRequests.delete(requestId)
            clearTimeout(timeout)
            reject(error)
          })
      })

      if (response.status === 'ok') {
        subscription.confirmed = true
        console.log(`Resubscription confirmed: ${subscription.topic}`, response)
      } else {
        console.error(`Resubscription failed: ${subscription.topic}`, response)
      }
    }
  }

  async unsubscribe(listenerId: string, topic?: string | undefined): Promise<void> {
    for (const subscription of this.subscriptions.values()) {
      if (subscription.topic === topic && subscription.listeners.has(listenerId)) {
        subscription.listeners.delete(listenerId)
        if (subscription.listeners.size === 0) {
          try {
            const unsubscribeType = subscription.subscriptionType.replace('subscribe', 'unsubscribe')
            const unsubscribePayload = subscription.subscriptionParams
            await this.sendRequest(unsubscribeType, unsubscribePayload)
          } finally {
            this.subscriptions.delete(topic)
          }
        }
      }
    }
  }
}

export class WebSocketClient<TParams extends object, TBackendData extends object, TData extends object> {
  protected ws: WebSocketBase
  protected listeners: Map<string, Set<string>>

  private wsRoute: string = ''
  private dataMapper: ((data: TBackendData) => TData)

  // dont defaut to identity dataMapper to detect types missmatch (data => data as unknown as TData)
  constructor(wsRoute: string, dataMapper: ((data: TBackendData) => TData)) {
    this.wsRoute = wsRoute
    this.dataMapper = dataMapper
    this.ws = WebSocketBase.getInstance()
    this.listeners = new Map<string, Set<string>>()
  }

  async subscribe(
    listenerId: string,
    subscriptionParams: TParams,
    onUpdate: (data: TData) => void,
  ): Promise<string> {
    const topic = `${this.wsRoute}:${buildTopicParams(subscriptionParams)}`

    if (this.listeners.has(listenerId)) {
      this.listeners.get(listenerId)!.add(topic)
    } else {
      this.listeners.set(listenerId, new Set([topic]))
    }


    await this.ws.subscribe(
      topic,
      this.wsRoute + '.subscribe',
      subscriptionParams,
      listenerId,
      (backendData: object) => {
        onUpdate(this.dataMapper(backendData as TBackendData))
      }
    )

    return topic
  }

  async unsubscribe(listenerId: string, topic?: string | undefined): Promise<void> {
    if (!this.listeners.has(listenerId)) {
      return
    }
    this.listeners.delete(listenerId)
    await this.ws.unsubscribe(listenerId, topic)

  }
}
