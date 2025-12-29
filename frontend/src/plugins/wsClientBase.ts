import { WebSocketError } from '@/errors'

function serializeParams(obj: unknown): string {
  if (obj === null || obj === undefined) {
    return ''
  }

  if (typeof obj !== 'object') {
    return JSON.stringify(obj)
  }

  if (Array.isArray(obj)) {
    return `[${obj.map(serializeParams).join(',')}]`
  }

  const objRecord = obj as Record<string, unknown>
  const sortedKeys = Object.keys(objRecord).sort()
  const pairs = sortedKeys.map(key => `${JSON.stringify(key)}:${serializeParams(objRecord[key])}`)
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

/**
 * Error notification for an active subscription.
 * Sent when a subscription encounters an error but connection remains open.
 */
export interface SubscriptionError {
  /** Affected subscription topic */
  topic: string
  /** Serialized exception details */
  error: {
    code: string
    message: string
    timestamp: number
    details?: Record<string, unknown> | null
  }
  /** If true, client should expect automatic recovery */
  recoverable?: boolean
  /** Suggested retry delay in milliseconds */
  retry_after_ms?: number | null
}

interface WebSocketMessage<TBackendData extends object = object> {
  type: string
  payload: SubscriptionUpdate<TBackendData> | SubscriptionResponse
}

interface SubscriptionState<TParams extends object = object, TData extends object = object> {
  sub_id: string
  subType: string
  sub_params: TParams
  onUpdate: (data: TData) => void
  onError: (error: SubscriptionError) => void
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
      debug: true,
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
        console.log(`[wsClientBase] WebSocket connection for ${wsUrl} ===> CLOSED`)
        instance.ws = null
      }
    })
  }

  private async __socketConnect(): Promise<void> {
    if (!this.wsCnxPromise) {
      this.wsCnxPromise = new Promise((resolve, reject) => {
        try {
          this.logger.log('[wsBase] Connecting to', this.config.wsUrl)
          this.ws = new WebSocket(this.config.wsUrl)

          this.ws.onerror = async (error) => {
            this.logger.log('[wsBase] Error:', error)
            setTimeout(() => {
              this.wsCnxPromise = null
              reject(error)
            }, 200)
          }

          this.ws.onclose = async (event) => {
            this.logger.log('[wsBase] WS Connection closed:', event)
            setTimeout(() => {
              this.wsCnxPromise = null
              reject(event)
            }, 200)
          }

          this.ws.onopen = () => {
            this.logger.log('[wsBase] WS Connected')
            this.ws!.binaryType = 'arraybuffer'

            this.ws!.onmessage = (event) => {
              this.handleMessage(event)
            }

            this.ws!.onerror = async (error) => {
              this.logger.log('[wsBase] WS Connection Error:', error)
              setTimeout(() => this.resubscribeAll(), 0)
            }

            this.ws!.onclose = async (event) => {
              this.logger.log('[wsBase] WS Connection closed:', event)
              setTimeout(() => this.resubscribeAll(), 0)
            }
            resolve()
            this.wsCnxPromise = null
          }
        } finally {
          setTimeout(() => {
            this.wsCnxPromise = null
          }, 200)
        }
      })
    }

    return this.wsCnxPromise
  }

  private async connect(): Promise<void> {

    let attemps = 0
    let connectionError: unknown;
    while (attemps < this.config.maxReconnectAttempts && !this.isConnected()) {
      try {
        return this.__socketConnect()
      } catch (error) {
        connectionError = error
        await new Promise(resolve => setTimeout(resolve, 1000))
      } finally {
        attemps++
      }
    }
    if (this.config.maxReconnectAttempts <= attemps) {
      throw (connectionError ?? new Error('Max reconnect attempts reached'))
    }
  }

  private isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  private async sendRequest(type: string, payload: SubscriptionRequest): Promise<void> {
    await this.connect()
    const message = JSON.stringify({ type, payload }, null, 2)
    this.ws!.send(message)
    this.logger.log('[wsBase] Sent:', type, message)
  }

  private handleMessage(event: MessageEvent): void {

    // Handle both text and binary (ArrayBuffer) messages
    const text = typeof event.data === 'string'
      ? event.data
      : new TextDecoder().decode(event.data as ArrayBuffer)
    const message: WebSocketMessage = JSON.parse(text)
    const { type, payload } = message

    if (type.endsWith('.update')) {
      const update = payload as SubscriptionUpdate
      this.routeUpdateMessage(update)
    } else if (type.endsWith('.error')) {
      const error = payload as unknown as SubscriptionError
      this.routeErrorMessage(error)
    } else {
      this.logger.log('[wsBase] Received:', type, payload)
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

  }

  private routeUpdateMessage(data: SubscriptionUpdate): void {
    this.logger.debug(`${data.topic} message received:`, data)
    const subscription = this.subscriptions.get(data.topic)
    if (!subscription) {
      this.logger.warn(`No subscription found for topic: ${data.topic}`)
      return
    }
    subscription.onUpdate(data.payload)
  }

  /**
   * Global error handler for subscription errors without specific onError callback.
   * Throws WebSocketError to bubble up to global error handler.
   */
  globalErrorHandler(error: SubscriptionError): void {
    throw WebSocketError.fromSubscription(error)
  }

  /**
   * Route error messages to the appropriate subscription handler or global handler.
   */
  private routeErrorMessage(error: SubscriptionError): void {
    const subscription = this.subscriptions.get(error.topic)
    if (subscription) {
      subscription.onError(error)
    } else {
      this.globalErrorHandler(error)
    }
  }

  async subscribe(
    subType: string,
    sub_params: object,
    onUpdate: (TbackendData: object) => void,
    onError: (error: SubscriptionError) => void
  ): Promise<string> {

    // Generate unique sub_id hash
    const sub_id = `${subType}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`


    let maxSubscriptionAttempts = 5;


    let subscriptionError: unknown;
    while (maxSubscriptionAttempts-- > 0)
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
            subType + '.subscribe',
            { sub_id: sub_id, sub_params: sub_params }
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
          subType,
          sub_params,
          onUpdate,
          onError,
        })

        return response.topic

      } catch (error) {
        subscriptionError = error
        this.logger.error('Subscription error:', subscriptionError)
        await new Promise(resolve => setTimeout(resolve, 200))

      }

    throw (subscriptionError ??
      new Error(
        `Subscription failed after multiple attempts: ${subType} with params ${JSON.stringify(sub_params)}`
      ))
  }

  private async resubscribeAll(): Promise<void> {
    this.logger.log('[wsBase] Resubscribing to all active subscriptions...')

    await new Promise(resolve => setTimeout(resolve, 200))

    this.pendingRequests.forEach((pending) => {
      clearTimeout(pending.timeout)
    })
    this.pendingRequests.forEach((pending) => {
      pending.reject(new Error('WebSocket disconnected'))
    })

    this.pendingRequests.clear()

    for (const [topic, subscription] of this.subscriptions.entries()) {

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
          subscription.subType + '.subscribe',
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
        throw new Error(`Resubscription failed for sub_id ${subscription.sub_id} / topic: ${topic} : ${response.error || 'unknown error'}`)
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
        subscription.subType + '.unsubscribe',
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
    onUpdate: (data: TData) => void,
    onError?: (error: SubscriptionError) => void
  ): Promise<string>
  unsubscribe(subscriptionId: string): Promise<void>
  destroy?(): void
}

/** Listener callbacks stored per-listener for fanout */
interface Listener<TData extends object> {
  paramsKey: string
  onUpdate: (data: TData) => void
  onError: (error: SubscriptionError) => void
}

export class WebSocketClient<TParams extends object, TBackendData extends object, TData extends object> implements WebSocketInterface<TParams, TData> {
  protected baseSocket: WebSocketBase
  protected topicPromises: Map<string, Promise<string>>
  protected listeners: Map<string, Listener<TData>>
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
    this.topicPromises = new Map()
    this.listeners = new Map()
    this.debouncedUnsub = new Map()
  }

  async subscribe(
    listenerId: string,
    subscriptionParams: TParams,
    onUpdate: (data: TData) => void,
    onError?: (error: SubscriptionError) => void,
  ): Promise<string> {

    const paramsKey = serializeParams(subscriptionParams)

    const unsubTimeout = this.debouncedUnsub.get(paramsKey)
    if (unsubTimeout) {
      console.log(`[wsClientBase] Clearing debounced unsubscribe for topic ${paramsKey}`)
      clearTimeout(unsubTimeout)
      this.debouncedUnsub.delete(paramsKey)
    }

    if (this.listeners.has(listenerId)) {

      const topicListener = this.listeners.get(listenerId)!

      if (topicListener.paramsKey !== paramsKey) {

        console.log(`[wsClientBase] listener ${listenerId} switching from ${topicListener.paramsKey} to ${paramsKey}`)

        if ([...this.listeners.values()].every(lis => (lis.paramsKey !== paramsKey))) {

          console.log(`[wsClientBase] No more listeners for topic ${paramsKey}. Debouncing Unsub in ${this.debounceMs}ms...`)

          this.debouncedUnsub.set(
            paramsKey,
            setTimeout(async () => {
              if (this.debouncedUnsub.has(paramsKey) && this.topicPromises.has(paramsKey)) {
                const topic = await this.topicPromises.get(paramsKey)!
                console.log(`[wsClientBase] Unsubscribing from topic ${paramsKey}...`)
                this.topicPromises.delete(paramsKey)
                this.debouncedUnsub.delete(paramsKey)
                await this.baseSocket.unsubscribe(topic)
              }
            }, this.debounceMs || 0)
          )
        }

      } else {
        console.warn(`[wsClientBase] listener ${listenerId} spamming for the same subscription`, paramsKey)
      }

    } else {
      console.log(`[wsClientBase] New listener ${listenerId} subscribing to params:`, paramsKey)
    }

    this.listeners.set(listenerId, {
      paramsKey,
      onUpdate,
      onError: onError || ((error) => this.baseSocket.globalErrorHandler(error))
    })

    if (!this.topicPromises.has(paramsKey)) {
      console.log(`[wsClientBase] Creating new subscription for params ${paramsKey}`)
      this.topicPromises.set(paramsKey, this.baseSocket.subscribe(
        this.wsRoute,
        subscriptionParams,
        (backendData: object) => {
          // capture this.listeners by reference so only mutations are allower
          for (const listener of this.listeners.values()) {
            if (listener.paramsKey === paramsKey) {
              listener.onUpdate(this.dataMapper(backendData as TBackendData))
            }
          }
        },
        (error: SubscriptionError) => {
          // capture this.listeners by reference so only mutations are allower
          for (const listener of this.listeners.values()) {
            if (listener.paramsKey === paramsKey) {
              listener.onError(error)
            }
          }
        }
      ))
    }

    const topic = await this.topicPromises.get(paramsKey)!
    return topic
  }

  async unsubscribe(listenerId: string): Promise<void> {
    if (!this.listeners.has(listenerId)) {
      console.warn(`[wsClientBase] listener ${listenerId} trying to unsubscribe but not found`)
      return
    }
    const listener = this.listeners.get(listenerId)!
    const paramsKey = listener.paramsKey
    const topic = await this.topicPromises.get(paramsKey)!
    this.listeners.delete(listenerId)
    console.log(`[wsClientBase] listener ${listenerId} unsubscribed from topic ${topic}`)
    if ([...this.listeners.values()].every(lis => (lis.paramsKey !== paramsKey))) {
      console.log(`[wsClientBase] No more listeners for topic ${paramsKey}. Debouncing Unsub in ${this.debounceMs}ms...`)
      this.debouncedUnsub.set(
        paramsKey,
        setTimeout(async () => {
          if (this.debouncedUnsub.has(paramsKey)) {
            console.log(`[wsClientBase] Unsubscribing from topic ${paramsKey}...`)
            this.topicPromises.delete(paramsKey)
            this.debouncedUnsub.delete(paramsKey)
            await this.baseSocket.unsubscribe(topic)
          }
        }, this.debounceMs || 0)
      )
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
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    onError?: (error: SubscriptionError) => void,
  ): Promise<string> {
    // Note: onError is ignored in fallback - errors don't occur in mock mode
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
