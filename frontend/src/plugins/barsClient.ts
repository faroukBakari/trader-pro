import type { Bar, BarsSubscriptionRequest } from './ws-types'
import type { WebSocketInterface } from './wsClientBase'
import { WebSocketClientBase } from './wsClientBase'

export type BarsWebSocketInterface = WebSocketInterface<BarsSubscriptionRequest, Bar>

export function BarsWebSocketClientFactory(): BarsWebSocketInterface {
  return new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
}
