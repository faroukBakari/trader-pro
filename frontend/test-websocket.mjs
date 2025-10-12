#!/usr/bin/env node
/**
 * WebSocket Client Test Script
 *
 * Tests the WebSocket implementation with the backend server.
 * Run with: node test-websocket.mjs
 */

import WebSocket from 'ws'

const WS_URL = 'ws://localhost:8000/api/v1/ws'

console.log('🧪 WebSocket Client Test\n')

/**
 * Test basic connection and subscription
 */
async function testBasicConnection() {
  return new Promise((resolve, reject) => {
    console.log('=== Test: Basic Connection ===')
    console.log('Connecting to:', WS_URL)

    const ws = new WebSocket(WS_URL)
    const timeout = setTimeout(() => {
      ws.close()
      reject(new Error('Connection timeout'))
    }, 5000)

    ws.on('open', () => {
      clearTimeout(timeout)
      console.log('✓ Connected to WebSocket server')

      // Send subscription request
      const subscribeMsg = {
        type: 'bars.subscribe',
        payload: {
          symbol: 'AAPL',
          resolution: '1',
        },
      }

      console.log('Sending subscription:', subscribeMsg)
      ws.send(JSON.stringify(subscribeMsg))
    })

    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString())
        console.log('📨 Received message:', {
          type: message.type,
          payload: message.payload,
        })

        // Check for subscription confirmation
        if (message.type === 'bars.subscribe.response') {
          if (message.payload.status === 'ok') {
            console.log('✓ Subscription confirmed!')
            console.log('  Topic:', message.payload.topic)
            console.log('  Message:', message.payload.message)

            // Wait a bit for any updates, then close
            setTimeout(() => {
              ws.close()
              resolve()
            }, 2000)
          } else {
            ws.close()
            reject(new Error('Subscription failed: ' + message.payload.message))
          }
        }

        // Log any bar updates
        if (message.type === 'bars.update') {
          console.log('📊 Bar update received:', message.payload)
        }
      } catch (error) {
        console.error('Error parsing message:', error)
      }
    })

    ws.on('error', (error) => {
      clearTimeout(timeout)
      console.error('❌ WebSocket error:', error.message)
      reject(error)
    })

    ws.on('close', (code, reason) => {
      clearTimeout(timeout)
      console.log('Connection closed:', code, reason.toString())
    })
  })
}

/**
 * Test subscription and unsubscription
 */
async function testSubscribeUnsubscribe() {
  return new Promise((resolve, reject) => {
    console.log('\n=== Test: Subscribe and Unsubscribe ===')

    const ws = new WebSocket(WS_URL)

    ws.on('open', () => {
      console.log('✓ Connected')

      // Subscribe
      const subscribeMsg = {
        type: 'bars.subscribe',
        payload: {
          symbol: 'GOOGL',
          resolution: '5',
        },
      }

      console.log('Subscribing to GOOGL:5')
      ws.send(JSON.stringify(subscribeMsg))
    })

    ws.on('message', (data) => {
      const message = JSON.parse(data.toString())

      if (message.type === 'bars.subscribe.response') {
        console.log('✓ Subscription confirmed')

        // Wait a bit, then unsubscribe
        setTimeout(() => {
          const unsubscribeMsg = {
            type: 'bars.unsubscribe',
            payload: {
              symbol: 'GOOGL',
              resolution: '5',
            },
          }

          console.log('Unsubscribing from GOOGL:5')
          ws.send(JSON.stringify(unsubscribeMsg))
        }, 2000)
      }

      if (message.type === 'bars.unsubscribe.response') {
        console.log('✓ Unsubscription confirmed')
        console.log('  Topic:', message.payload.topic)

        ws.close()
        resolve()
      }
    })

    ws.on('error', (error) => {
      console.error('❌ Error:', error.message)
      reject(error)
    })
  })
}

/**
 * Test message format validation
 */
async function testMessageFormat() {
  return new Promise((resolve, reject) => {
    console.log('\n=== Test: Message Format ===')

    const ws = new WebSocket(WS_URL)

    ws.on('open', () => {
      console.log('✓ Connected')

      // Send subscription with valid format
      const msg = {
        type: 'bars.subscribe',
        payload: {
          symbol: 'AAPL',
          resolution: '1',
        },
      }

      console.log('Testing message format:', msg)
      ws.send(JSON.stringify(msg))
    })

    ws.on('message', (data) => {
      const message = JSON.parse(data.toString())
      console.log('✓ Message received with correct format')
      console.log('  Type:', message.type)
      console.log('  Payload keys:', Object.keys(message.payload || {}))

      // Validate response format
      if (message.type === 'bars.subscribe.response') {
        const payload = message.payload
        if (payload.status && payload.message && payload.topic) {
          console.log('✓ Response format is correct')
        } else {
          console.error('❌ Response format is incorrect')
          reject(new Error('Invalid response format'))
        }

        ws.close()
        resolve()
      }
    })

    ws.on('error', (error) => {
      console.error('❌ Error:', error.message)
      reject(error)
    })
  })
}

/**
 * Run all tests
 */
async function runAllTests() {
  try {
    await testBasicConnection()
    await testSubscribeUnsubscribe()
    await testMessageFormat()

    console.log('\n✅ All WebSocket tests passed!\n')
  } catch (error) {
    console.error('\n❌ Test failed:', error.message, '\n')
    process.exit(1)
  }
}

// Check if ws package is installed
try {
  await import('ws')
} catch {
  console.error('❌ Error: "ws" package not found')
  console.error('Install it with: npm install ws')
  process.exit(1)
}

// Run tests
runAllTests()
