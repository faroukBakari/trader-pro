/**
 * WebSocket API Types
 *
 * Temporary type definitions for WebSocket communication.
 * TODO: Replace with generated types from AsyncAPI specification
 */

/**
 * OHLC bar data
 */
export interface Bar {
  /** Bar timestamp in milliseconds */
  time: number
  /** Opening price */
  open: number
  /** Highest price */
  high: number
  /** Lowest price */
  low: number
  /** Closing price */
  close: number
  /** Trading volume */
  volume: number
}

/**
 * Subscription request for bars
 */
export interface BarsSubscriptionRequest {
  /** Symbol to subscribe to */
  symbol: string
  /** Time resolution (e.g., "1", "5", "15", "60", "D") */
  resolution: string
}

/**
 * Subscription response
 */
export interface SubscriptionResponse {
  /** Status of subscription */
  status: 'ok' | 'error'
  /** Status message */
  message: string
  /** Subscription topic */
  topic: string
}

/**
 * Generic subscription update with typed payload
 */
export interface SubscriptionUpdate<T> {
  /** Update type */
  type: string
  /** Update payload */
  payload: T
}
