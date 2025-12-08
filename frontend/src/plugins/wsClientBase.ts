// interface WebSocketClientBaseConfig {
//   wsUrl: string
//   reconnect?: boolean
//   maxReconnectAttempts?: number
//   reconnectDelay?: number
//   debug?: boolean
// }


function serialize_params(obj: unknown): string {
  if (obj === null || obj === undefined) {
    return ''
  }

  if (typeof obj !== 'object') {
    return JSON.stringify(obj)
  }

  if (Array.isArray(obj)) {
    return `[${obj.map(serialize_params).join(',')}]`
  }

  const objRecord = obj as Record<string, unknown>
  const sortedKeys = Object.keys(objRecord).sort()
  const pairs = sortedKeys.map(key => `${JSON.stringify(key)}:${serialize_params(objRecord[key])}`)
  return `{${pairs.join(',')}}`
}

interface SubscriptionRequest<TParams extends object = object> {
  sub_id: string
  sub_params: TParams
}
interface SubscriptionResponse {
  status: 'ok' | 'error'
  sub_id: string
  topic: string
  error?: string
}

interface SubscriptionUpdate<TBackendData extends object = object> {
  topic: string
  payload: TBackendData
}

interface WebSocketMessage<TBackendData extends object = object> {
  type: string
  payload: SubscriptionUpdate<TBackendData> | SubscriptionResponse
}

interface SubscriptionState<TParams extends object = object, TData extends object = object> {
  sub_id: string
  sub_type: string
  sub_params: TParams
  on_update: (data: TData) => void
}

export class WebSocketBase {
  // dont defaut to identity dataMapper to detect types missmatch (data => data as unknown as TData)
  private static instances = new Map<string, WebSocketBase>()

  private readonly config: {
    reconnect: boolean
    maxReconnectAttempts: number
    reconnectDelay: number
    debug: boolean
    wsUrl: string
  }
  protected logger: Console
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

  private constructor(wsUrl: string) {
    this.config = {
      reconnect: true,
      maxReconnectAttempts: 5,
      reconnectDelay: 1000,
      debug: false,
      wsUrl,
    }
    this.logger = this.config.debug
      ? console
      : ({ log: () => { }, warn: () => { }, error: () => { }, debug: () => { } } as Console)
  }

  static getInstance(wsUrl: string): WebSocketBase {
    if (!WebSocketBase.instances.has(wsUrl)) {
      WebSocketBase.instances.set(wsUrl, new WebSocketBase(wsUrl))
    }
    return WebSocketBase.instances.get(wsUrl)!
  }

  // Close all WebSocket connections on logout
  static logout(): void {
    WebSocketBase.instances.forEach((instance, wsUrl) => {
      try {
        instance.ws?.close()
      } finally {
        console.log(`WebSocket connection for ${wsUrl} ===> CLOSED`)
        instance.ws = null
      }
    })
  }

  private async __socketConnect(): Promise<void> {
    if (!this.wsCnxPromise) {
      this.wsCnxPromise = new Promise((resolve, reject) => {
        try {
          this.logger.log('Connecting to', this.config.wsUrl)
          this.ws = new WebSocket(this.config.wsUrl)

          this.ws.onerror = async (error) => {
            this.logger.log('Error:', error)
            setTimeout(() => {
              this.wsCnxPromise = null
              reject(error)
            }, 200)
          }

          this.ws.onclose = async (event) => {
            this.logger.log('WS Connection closed:', event)
            setTimeout(() => {
              this.wsCnxPromise = null
              reject(event)
            }, 200)
          }

          this.ws.onopen = () => {
            this.logger.log('WS Connected')
            this.ws!.binaryType = 'arraybuffer'

            this.ws!.onmessage = (event) => {
              this.handleMessage(event)
            }

            this.ws!.onerror = async (error) => {
              this.logger.log('WS Connection Error:', error)
              setTimeout(() => this.resubscribeAll(), 0)
            }

            this.ws!.onclose = async (event) => {
              this.logger.log('WS Connection closed:', event)
              setTimeout(() => this.resubscribeAll(), 0)
            }
            resolve()
            this.wsCnxPromise = null
          }
        } catch (error) {
          this.logger.log('WS creation Error:', error)
          setTimeout(() => {
            this.wsCnxPromise = null
            reject(error)
          }, 200)
        }
      })
    }

    return this.wsCnxPromise
  }

  private async connect(): Promise<void> {

    let attemps = 0
    while (!this.isConnected() && attemps++ < this.config.maxReconnectAttempts) {
      try {
        await this.__socketConnect()
      } catch (error) {
        this.logger.log('Connection error:', error)
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
    }
    if (this.config.maxReconnectAttempts <= attemps) {
      throw new Error('Max reconnect attempts reached')
    }
  }

  private isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  private async sendRequest(type: string, payload: SubscriptionRequest): Promise<void> {
    await this.connect()
    const message = JSON.stringify({ type, payload }, null, 2)
    this.ws!.send(message)
    this.logger.log('Sent:', type, message)
  }

  private handleMessage(event: MessageEvent): void {
    try {
      // Handle both text and binary (ArrayBuffer) messages
      const text = typeof event.data === 'string'
        ? event.data
        : new TextDecoder().decode(event.data as ArrayBuffer)
      const message: WebSocketMessage = JSON.parse(text)
      const { type, payload } = message

      if (type.endsWith('.update')) {
        const update = payload as SubscriptionUpdate
        this.routeUpdateMessage(update)
      } else {
        this.logger.log('Received:', type, payload)
        if (type.endsWith('.response')) {
          if (type.replace(/.response$/, '').endsWith('.subscribe')) {
            const subResponse = payload as SubscriptionResponse
            const pendingRequest = this.pendingRequests.get(subResponse.sub_id)
            if (pendingRequest) {
              this.pendingRequests.delete(subResponse.sub_id)
              pendingRequest.resolve(subResponse)
            } else {
              this.logger.error(`Cannot find sub_id ${subResponse.sub_id} for response :`, payload)
            }
          }
        } else {
          this.logger.error('Unknown message type:', type)
        }
      }
    } catch (error) {
      this.logger.error('Failed to parse message:', error)
    }
  }

  private routeUpdateMessage(data: SubscriptionUpdate): void {
    this.logger.debug(`${data.topic} message received:`, data)
    const subscription = this.subscriptions.get(data.topic)
    if (!subscription) {
      this.logger.warn(`No subscription found for topic: ${data.topic}`)
      return
    }
    try {
      subscription.on_update(data.payload)
    } catch (error) {
      this.logger.error(`Error in subscription onUpdate for sub_id ${subscription.sub_id} / topic ${data.topic}:`, error)
    }
  }

  async subscribe(
    sub_type: string,
    sub_params: object,
    on_update: (TbackendData: object) => void
  ): Promise<string> {

    // Generate unique sub_id hash
    const sub_id = `${sub_type}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`

    while (true)
      try {

        const response: SubscriptionResponse = await new Promise((resolve, reject) => {
          // Expected response type

          // Set up timeout
          const timeout = setTimeout(() => {
            this.pendingRequests.delete(sub_id)
            reject(new Error(`Request timeout: ${sub_id}`))
          }, 3000)

          // Register response handler
          this.pendingRequests.set(sub_id, {
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
          this.sendRequest(
            sub_type + '.subscribe',
            { sub_id, sub_params }
          ).catch((error) => {
            this.pendingRequests.delete(sub_id)
            clearTimeout(timeout)
            reject(error)
          })
        })

        if (response.status !== 'ok') {
          throw new Error(`Subscription ${sub_id} failed: ${response.error || 'unknown error'}`)
        }

        this.logger.log(`Subscription confirmed: `, response)

        this.subscriptions.set(response.topic, {
          sub_id,
          sub_type,
          sub_params,
          on_update,
        })

        return response.topic

      } catch (error) {

        this.logger.error('Subscription error:', error)
        await new Promise(resolve => setTimeout(resolve, 200))

      }
  }

  private async resubscribeAll(): Promise<void> {
    this.logger.log('Resubscribing to all active subscriptions...')

    await new Promise(resolve => setTimeout(resolve, 200))

    try {
      this.pendingRequests.forEach((pending) => {
        clearTimeout(pending.timeout)
      })
      this.pendingRequests.forEach((pending) => {
        pending.reject(new Error('WebSocket disconnected'))
      })
    } finally {
      this.pendingRequests.clear()
    }

    for (const [topic, subscription] of this.subscriptions.entries()) {

      try {
        const response: SubscriptionResponse = await new Promise((resolve, reject) => {
          // Expected response type
          // Set up timeout
          const timeout = setTimeout(() => {
            this.pendingRequests.delete(subscription.sub_id)
            reject(new Error(`Request timeout: ${subscription.sub_id}`))
          }, 3000)

          // Register response handler
          this.pendingRequests.set(subscription.sub_id, {
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
          this.sendRequest(
            subscription.sub_type + '.subscribe',
            { sub_id: subscription.sub_id, sub_params: subscription.sub_params }
          ).catch((error) => {
            this.pendingRequests.delete(subscription.sub_id)
            clearTimeout(timeout)
            reject(error)
          })
        })

        if (response.status === 'ok') {
          this.logger.log(`Resubscription confirmed sub_id ${subscription.sub_id} / topic: ${topic}`)
        } else {
          this.logger.log(`Resubscription failed sub_id ${subscription.sub_id} / topic: ${topic}`)
        }
      }
      catch (error) {
        this.logger.log(`Resubscription error sub_id ${subscription.sub_id} / topic: ${topic}:`, error)
        this.logger.error('Resubscription error:', error)
      }
    }
  }

  async unsubscribe(topic: string): Promise<void> {
    const subscription = this.subscriptions.get(topic)
    if (!subscription) {
      this.logger.warn(`No active subscription for topic: ${topic}`)
      return
    }
    try {
      const response = await this.sendRequest(
        subscription.sub_type + '.unsubscribe',
        { sub_id: subscription.sub_id, sub_params: subscription.sub_params }
      )
      this.logger.log(`Unsubscribed sub_id ${subscription.sub_id} / topic: ${topic}`, response)
    } finally {
      this.subscriptions.delete(topic)
      if (this.subscriptions.size === 0) {
        this.ws?.close()
        this.ws = null
      }
    }
  }
}

export interface WebSocketInterface<TParams extends object, TData extends object> {
  subscribe(
    subscriptionId: string,
    params: TParams,
    onUpdate: (data: TData) => void
  ): Promise<string>
  unsubscribe(subscriptionId: string): Promise<void>
  destroy?(): void
}

export class WebSocketClient<TParams extends object, TBackendData extends object, TData extends object> implements WebSocketInterface<TParams, TData> {
  protected baseSocket: WebSocketBase
  protected topics: Map<string, Promise<string>>
  protected listeners: Map<string, Map<string, (data: TData) => void>>
  protected debouncedUnsub: Map<string, NodeJS.Timeout>

  private wsRoute: string = ''
  private debounceMs?: number
  private dataMapper: ((data: TBackendData) => TData)

  // dont defaut to identity dataMapper to detect types missmatch (data => data as unknown as TData)
  constructor(wsUrl: string, wsRoute: string, dataMapper: ((data: TBackendData) => TData), debounceMs?: number) {
    this.wsRoute = wsRoute
    this.debounceMs = debounceMs
    this.dataMapper = dataMapper
    this.baseSocket = WebSocketBase.getInstance(wsUrl)
    this.topics = new Map()
    this.listeners = new Map()
    this.debouncedUnsub = new Map()
  }

  async subscribe(
    listenerId: string,
    subscriptionParams: TParams,
    onUpdate: (data: TData) => void,
  ): Promise<string> {

    const paramsKey = serialize_params(subscriptionParams)

    const unsubTimeout = this.debouncedUnsub.get(paramsKey)
    if (unsubTimeout) {
      console.log(`Clearing debounced unsubscribe for topic ${paramsKey}`)
      clearTimeout(unsubTimeout)
      this.debouncedUnsub.delete(paramsKey)
    }

    if (this.listeners.has(paramsKey)) {
      const topicListeners = this.listeners.get(paramsKey)!
      if (topicListeners?.has(listenerId)) {
        console.warn(`listener ${listenerId} spamming for the same subscription`, paramsKey)
      }
      topicListeners.set(listenerId, onUpdate)
    } else {
      console.log(`listener ${listenerId} subscribing to new params:`, paramsKey)
      this.listeners.set(paramsKey, new Map([[listenerId, onUpdate]]))
      const topicPromise = this.baseSocket.subscribe(
        this.wsRoute,
        subscriptionParams,
        (backendData: object) =>
          this.listeners.get(paramsKey)?.forEach(
            (onUpdate) => onUpdate(this.dataMapper(backendData as TBackendData))
          )
      )
      this.topics.set(paramsKey, topicPromise)
    }
    return await this.topics.get(paramsKey)!
  }

  // TODO: unsub and debounce not working as expected. need to fiabilize that!
  async unsubscribe(listenerId: string): Promise<void> {
    for (const [paramsKey, listenersMap] of this.listeners.entries()) {
      for (const id of listenersMap.keys())
        if (id.startsWith(listenerId)) {
          listenersMap.delete(id)
          const topic = await this.topics.get(paramsKey)
          console.log(`listener ${listenerId} unsubscribed from topic ${paramsKey}`)
          if (topic && !listenersMap.size) {
            console.log(`No more listeners for topic ${paramsKey}. Debouncing Unsub in ${this.debounceMs}ms...`)
            this.debouncedUnsub.set(
              paramsKey,
              setTimeout(async () => {
                if (this.debouncedUnsub.get(paramsKey)) {
                  console.log(`Unsubscribing from topic ${paramsKey}...`)
                  this.topics.delete(paramsKey)
                  this.listeners.delete(paramsKey)
                  this.debouncedUnsub.delete(paramsKey)
                  await this.baseSocket.unsubscribe(topic)
                }
              }, this.debounceMs || 0)
            )
          }
        }
    }
  }
}

export class WebSocketFallback<TParams extends object, TData extends object> implements WebSocketInterface<TParams, TData> {
  private subscriptions = new Map<
    string,
    { params: TParams; onUpdate: (data: TData) => void }
  >()
  private intervalId: NodeJS.Timeout

  constructor(mockData: () => TData | undefined) {
    // Mock data updates every 100ms for fast test execution
    this.intervalId = setInterval(() => {
      this.subscriptions.forEach(({ onUpdate }) => {
        const data = mockData()
        if (data) onUpdate(data)
      })
    }, 100)
  }

  async subscribe(
    subscriptionId: string,
    params: TParams,
    onUpdate: (data: TData) => void,
  ): Promise<string> {
    this.subscriptions.set(subscriptionId, { params, onUpdate })
    return subscriptionId
  }

  async unsubscribe(subscriptionId: string): Promise<void> {
    // Match prefix to support bulk unsubscribe (same as WebSocketClient)
    for (const id of this.subscriptions.keys()) {
      if (id.startsWith(subscriptionId)) {
        this.subscriptions.delete(id)
      }
    }
  }

  destroy(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId)
    }
    this.subscriptions.clear()
  }
}
