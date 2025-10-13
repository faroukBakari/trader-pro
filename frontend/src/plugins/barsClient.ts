import type { Bar } from './ws-types'
import { WebSocketClientBase } from './wsClientBase'

export interface BarsSubscriptionRequest {
  symbol: string
  resolution: string
}
export interface BarWebSocketInterface {
  subscribe(params: BarsSubscriptionRequest, onUpdate: (bar: Bar) => void): Promise<string>
  unsubscribe(listenerGuid: string): Promise<void>
}
export class BarsWebSocketClient implements BarWebSocketInterface {
  private instance: WebSocketClientBase

  constructor() {
    this.instance = WebSocketClientBase.getInstance()
  }

  async subscribe(payload: BarsSubscriptionRequest, onUpdate: (bar: Bar) => void): Promise<string> {
    const topic = `bars:${payload.symbol}:${payload.resolution}`

    // Use base class subscribe with server confirmation
    const subscriptionId = await this.instance.subscribe<BarsSubscriptionRequest, Bar>(
      'bars',
      payload,
      topic,
      onUpdate,
    )
    return subscriptionId
  }

  async unsubscribe(listenerGuid: string): Promise<void> {
    // Use base class unsubscribe
    await this.instance.unsubscribe(listenerGuid)
  }
}
