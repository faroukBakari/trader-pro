#!/usr/bin/env node
/**
 * WebSocket Client Generator
 *
 * Generates TypeScript client interfaces and classes from AsyncAPI specification.
 * Phase 1: Generate IBarDataSource interface with type-safe operations.
 *
 * Usage:
 *   node generate-ws-client.mjs <asyncapi-spec.json> <output-dir>
 */

import fs from 'fs'
import path from 'path'

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  blue: '\x1b[34m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
}

function log(color, message) {
  console.log(`${colors[color]}${message}${colors.reset}`)
}

/**
 * Extract operations from AsyncAPI spec
 * Returns { send: [...], receive: [...] }
 */
function extractOperations(spec) {
  const operations = {
    send: [],
    receive: [],
  }

  const messages = spec.components?.messages || {}
  const channels = spec.channels || {}

  // Extract from channels
  for (const channelDef of Object.values(channels)) {
    // Publish operations (client -> server)
    if (channelDef.publish?.message?.oneOf) {
      channelDef.publish.message.oneOf.forEach((msgRef) => {
        const msgId = msgRef.$ref.split('/').pop()
        const message = messages[msgId]
        if (message && !msgId.includes('.response')) {
          operations.send.push({
            id: msgId,
            name: message.name || msgId,
            title: message.title || msgId,
            description: message.description || '',
          })
        }
      })
    }

    // Subscribe operations (server -> client)
    if (channelDef.subscribe?.message?.oneOf) {
      channelDef.subscribe.message.oneOf.forEach((msgRef) => {
        const msgId = msgRef.$ref.split('/').pop()
        const message = messages[msgId]
        if (message && msgId.includes('update')) {
          operations.receive.push({
            id: msgId,
            name: message.name || msgId,
            title: message.title || msgId,
            description: message.description || '',
          })
        }
      })
    }
  }

  return operations
}

/**
 * Generate IBarDataSource interface
 */
function generateDataSourceInterface(operations) {
  log(
    'blue',
    `🔧 Generating IBarDataSource interface for ${operations.send.length} send operations and ${operations.receive.length} receive operations...`,
  )
  return `/**
 * Bar data source interface
 *
 * Abstract interface for subscribing to real-time bar data.
 * Can be implemented by WebSocket client, mock data source, or any other provider.
 */
export interface IBarDataSource {
  /**
   * Subscribe to real-time bar updates for a symbol
   *
   * @param symbol - Trading symbol (e.g., 'AAPL', 'GOOGL')
   * @param resolution - Time resolution ('1', '5', '15', '30', '60', 'D', 'W', 'M')
   * @param onTick - Callback function called when new bar data arrives
   * @returns Subscription ID for unsubscribing
   */
  subscribe(
    symbol: string,
    resolution: string,
    onTick: (bar: Bar) => void,
  ): Promise<string>

  /**
   * Unsubscribe from bar updates
   *
   * @param listenerGuid - Subscription ID returned from subscribe()
   */
  unsubscribe(listenerGuid: string): Promise<void>

  /**
   * Check if data source is connected and ready
   */
  isConnected(): boolean

  /**
   * Connect to data source (if not already connected)
   */
  connect(): Promise<void>

  /**
   * Disconnect from data source
   */
  disconnect(): Promise<void>
}
`
}

/**
 * Generate basic WebSocket client stub
 */
function generateWebSocketClient(spec) {
  log('blue', `🔧 Generating WebSocketBarDataSource class for ${spec.info.title}...`)
  return `/**
 * WebSocket Bar Data Source
 *
 * Real-time bar data via WebSocket connection to trading API.
 * Implements IBarDataSource interface.
 */
export class WebSocketBarDataSource implements IBarDataSource {
  private ws: WebSocket | null = null
  private subscriptions = new Map<
    string,
    {
      symbol: string
      resolution: string
      callback: (bar: Bar) => void
    }
  >()
  private messageHandlers = new Map<string, ((data: any) => void)[]>()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isReconnecting = false

  constructor(private config: WebSocketClientConfig) {}

  async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.config.url)

        this.ws.onopen = () => {
          console.log('[WebSocket] Connected to', this.config.url)
          this.reconnectAttempts = 0
          this.isReconnecting = false
          resolve()
        }

        this.ws.onmessage = (event) => {
          this.handleMessage(event)
        }

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error)
          reject(error)
        }

        this.ws.onclose = (event) => {
          console.log('[WebSocket] Closed:', event.code, event.reason)
          this.handleReconnect()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  async disconnect(): Promise<void> {
    if (this.ws) {
      this.ws.close()
      this.ws = null
      this.subscriptions.clear()
      this.messageHandlers.clear()
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  async subscribe(
    symbol: string,
    resolution: string,
    onTick: (bar: Bar) => void,
  ): Promise<string> {
    // Ensure connected
    if (!this.isConnected()) {
      await this.connect()
    }

    // Generate unique subscription ID
    const listenerGuid = \`\${symbol}_\${resolution}_\${Date.now()}\`

    // Store subscription
    this.subscriptions.set(listenerGuid, {
      symbol,
      resolution,
      callback: onTick,
    })

    // Send subscribe message to server
    const request: BarsSubscriptionRequest = {
      symbol,
      resolution,
    }

    await this.send('bars.subscribe', request)

    // Register handler for updates
    this.onMessage('bars.update', (bar: Bar) => {
      // Call the callback for this subscription
      const sub = this.subscriptions.get(listenerGuid)
      if (sub && sub.symbol === symbol && sub.resolution === resolution) {
        sub.callback(bar)
      }
    })

    console.log(\`[WebSocket] Subscribed to \${symbol}:\${resolution}\`)
    return listenerGuid
  }

  async unsubscribe(listenerGuid: string): Promise<void> {
    const subscription = this.subscriptions.get(listenerGuid)
    if (!subscription) {
      return
    }

    // Send unsubscribe message to server
    const request: BarsSubscriptionRequest = {
      symbol: subscription.symbol,
      resolution: subscription.resolution,
    }

    await this.send('bars.unsubscribe', request)

    // Remove subscription
    this.subscriptions.delete(listenerGuid)
    console.log(
      \`[WebSocket] Unsubscribed from \${subscription.symbol}:\${subscription.resolution}\`,
    )
  }

  private async send<T>(type: string, payload: unknown): Promise<T> {
    if (!this.isConnected()) {
      throw new Error('WebSocket not connected')
    }

    return new Promise((resolve, reject) => {
      const message = JSON.stringify({ type, payload })

      // Set up response handler (for operations with responses)
      const responseType = \`\${type}.response\`
      const timeout = setTimeout(() => {
        reject(new Error(\`Timeout waiting for \${responseType}\`))
      }, 5000)

      this.onMessage(responseType, (data: any) => {
        clearTimeout(timeout)
        resolve(data as T)
      })

      this.ws!.send(message)
    })
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data)
      const { type, payload } = message

      // Trigger all handlers for this message type
      const handlers = this.messageHandlers.get(type) || []
      handlers.forEach((handler) => handler(payload))
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error)
    }
  }

  private onMessage(type: string, handler: (data: any) => void): void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, [])
    }
    this.messageHandlers.get(type)!.push(handler)
  }

  private handleReconnect(): void {
    if (this.isReconnecting) {
      return
    }

    if (!this.config.reconnect) {
      console.log('[WebSocket] Reconnection disabled')
      return
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached')
      return
    }

    this.isReconnecting = true
    this.reconnectAttempts++

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    console.log(
      \`[WebSocket] Reconnecting in \${delay}ms (attempt \${this.reconnectAttempts}/\${this.maxReconnectAttempts})\`,
    )

    setTimeout(async () => {
      try {
        await this.connect()

        // Re-subscribe to all active subscriptions
        for (const [listenerGuid, sub] of Array.from(this.subscriptions.entries())) {
          const request: BarsSubscriptionRequest = {
            symbol: sub.symbol,
            resolution: sub.resolution,
          }
          await this.send('bars.subscribe', request)
          console.log(\`[WebSocket] Re-subscribed to \${sub.symbol}:\${sub.resolution}\`)
        }
      } catch (error) {
        console.error('[WebSocket] Reconnection failed:', error)
        this.isReconnecting = false
        this.handleReconnect()
      }
    }, delay)
  }
}
`
}

/**
 * Generate configuration interface
 */
function generateConfigInterface() {
  return `/**
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
}
`
}

/**
 * Main generation function
 */
function generateClient(specPath, outputDir) {
  try {
    log('blue', '📖 Reading AsyncAPI specification...')
    const spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'))

    log('blue', '🔍 Extracting operations...')
    const operations = extractOperations(spec)

    log(
      'green',
      `✅ Found ${operations.send.length} send operations, ${operations.receive.length} receive operations`,
    )

    // Generate header
    let output = `/**
 * Auto-generated WebSocket Client from AsyncAPI specification
 *
 * DO NOT EDIT MANUALLY - This file is automatically generated
 *
 * Generated from: ${spec.info?.title || 'AsyncAPI Specification'}
 * Version: ${spec.info?.version || 'unknown'}
 * AsyncAPI: ${spec.asyncapi || 'unknown'}
 *
 * Generated on: ${new Date().toISOString()}
 */

import type { Bar, BarsSubscriptionRequest, SubscriptionResponse } from '../ws-types-generated'

`

    // Add configuration interface
    log('blue', '🔧 Generating WebSocketClientConfig interface...')
    output += generateConfigInterface()
    output += '\n'

    // Add data source interface
    log('blue', '🔧 Generating IBarDataSource interface...')
    output += generateDataSourceInterface(operations)
    output += '\n'

    // Add WebSocket client implementation
    log('blue', '🔧 Generating WebSocketBarDataSource class...')
    output += generateWebSocketClient(spec)

    // Create output directory
    fs.mkdirSync(outputDir, { recursive: true })

    // Write to file
    const outputPath = path.join(outputDir, 'client.ts')
    fs.writeFileSync(outputPath, output)

    log('green', `\n🎉 Success! Generated WebSocket client at: ${outputPath}`)
    log('blue', `📁 Output directory: ${outputDir}`)
    log('yellow', '\n📋 Generated:')
    log('yellow', '  - WebSocketClientConfig interface')
    log('yellow', '  - IBarDataSource interface')
    log('yellow', '  - WebSocketBarDataSource class')

    return true
  } catch (error) {
    log('red', `❌ Error generating client: ${error.message}`)
    console.error(error)
    return false
  }
}

// Main execution
const args = process.argv.slice(2)

if (args.length < 2) {
  console.log('Usage: node generate-ws-client.mjs <asyncapi-spec.json> <output-dir>')
  process.exit(1)
}

const [specPath, outputDir] = args

if (!fs.existsSync(specPath)) {
  log('red', `❌ AsyncAPI spec file not found: ${specPath}`)
  process.exit(1)
}

const success = generateClient(specPath, outputDir)
process.exit(success ? 0 : 1)
