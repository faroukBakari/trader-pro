/**
 * WebSocket Client Test
 *
 * Manual test for the WebSocket client implementation.
 * Run this in browser console or as a separate script.
 */

import { BarsWebSocketClient } from './barsClient'
import type { Bar } from './ws-types'

/**
 * Test basic subscription and unsubscription
 */
export async function testBasicSubscription(): Promise<void> {
  console.log('=== Test: Basic Subscription ===')

  // Create client (automatically connects)
  const client = await BarsWebSocketClient.create({
    url: 'ws://localhost:8000/api/v1/ws',
    reconnect: true,
    debug: true,
  })

  console.log('✓ Client created and connected')
  console.log('  Connected:', client.isConnected())

  // Subscribe to bars
  const subscriptionId = await client.subscribeToBars('AAPL', '1', (bar: Bar) => {
    console.log('📊 New bar received:', {
      symbol: 'AAPL',
      resolution: '1',
      time: new Date(bar.time).toISOString(),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
    })
  })

  console.log('✓ Subscribed to AAPL:1')
  console.log('  Subscription ID:', subscriptionId)

  // Wait 10 seconds to receive some bars
  await new Promise((resolve) => setTimeout(resolve, 10000))

  // Unsubscribe
  await client.unsubscribe(subscriptionId)
  console.log('✓ Unsubscribed from AAPL:1')

  // Cleanup
  await client.dispose()
  console.log('✓ Client disposed')
  console.log('  Connected:', client.isConnected())
}

/**
 * Test multiple subscriptions
 */
export async function testMultipleSubscriptions(): Promise<void> {
  console.log('=== Test: Multiple Subscriptions ===')

  const client = await BarsWebSocketClient.create({
    url: 'ws://localhost:8000/api/v1/ws',
    debug: true,
  })

  console.log('✓ Client created')

  // Subscribe to multiple symbols
  const subscriptions = await Promise.all([
    client.subscribeToBars('AAPL', '1', (bar) => console.log('📊 AAPL:1 ->', bar.close)),
    client.subscribeToBars('GOOGL', '5', (bar) => console.log('📊 GOOGL:5 ->', bar.close)),
    client.subscribeToBars('MSFT', 'D', (bar) => console.log('📊 MSFT:D ->', bar.close)),
  ])

  console.log('✓ Created 3 subscriptions:', subscriptions)

  // Wait 10 seconds
  await new Promise((resolve) => setTimeout(resolve, 10000))

  // Unsubscribe from all
  for (const id of subscriptions) {
    await client.unsubscribe(id)
  }

  console.log('✓ Unsubscribed from all')

  await client.dispose()
  console.log('✓ Client disposed')
}

/**
 * Test singleton behavior
 */
export async function testSingleton(): Promise<void> {
  console.log('=== Test: Singleton Pattern ===')

  // Create two clients with same URL
  const client1 = await BarsWebSocketClient.create({
    url: 'ws://localhost:8000/api/v1/ws',
    debug: true,
  })

  const client2 = await BarsWebSocketClient.create({
    url: 'ws://localhost:8000/api/v1/ws',
    debug: true,
  })

  console.log('✓ Created two clients')
  console.log('  Client1 connected:', client1.isConnected())
  console.log('  Client2 connected:', client2.isConnected())

  // Both should be connected (sharing same WebSocket)
  if (!client1.isConnected() || !client2.isConnected()) {
    throw new Error('Clients should both be connected')
  }

  // Subscribe with both clients
  void (await client1.subscribeToBars('AAPL', '1', (bar) =>
    console.log('📊 Client1: AAPL ->', bar.close),
  ))

  void (await client2.subscribeToBars('GOOGL', '5', (bar) =>
    console.log('📊 Client2: GOOGL ->', bar.close),
  ))

  console.log('✓ Both clients subscribed')

  // Wait 5 seconds
  await new Promise((resolve) => setTimeout(resolve, 5000))

  // Dispose client1 (should NOT disconnect - client2 still using it)
  await client1.dispose()
  console.log('✓ Client1 disposed')
  console.log('  Client2 still connected:', client2.isConnected())

  // Client2 should still be connected
  if (!client2.isConnected()) {
    throw new Error('Client2 should still be connected (singleton pattern)')
  }

  // Wait 2 seconds
  await new Promise((resolve) => setTimeout(resolve, 2000))

  // Dispose client2 (NOW it should disconnect)
  await client2.dispose()
  console.log('✓ Client2 disposed')
  console.log('  Client2 connected:', client2.isConnected())

  console.log('✅ Singleton test passed!')
}

/**
 * Test error handling
 */
export async function testErrorHandling(): Promise<void> {
  console.log('=== Test: Error Handling ===')

  try {
    // Try to connect to non-existent server
    void (await BarsWebSocketClient.create({
      url: 'ws://localhost:9999/api/v1/ws', // Wrong port
      maxReconnectAttempts: 2,
      reconnectDelay: 500,
      debug: true,
    }))

    console.log('❌ Should have failed to connect')
  } catch (error) {
    console.log('✓ Connection failed as expected')
    console.log('  Error:', (error as Error).message)
  }
}

/**
 * Run all tests
 */
export async function runAllTests(): Promise<void> {
  console.log('🧪 WebSocket Client Tests\n')

  try {
    await testBasicSubscription()
    console.log('\n')

    await testMultipleSubscriptions()
    console.log('\n')

    await testSingleton()
    console.log('\n')

    await testErrorHandling()
    console.log('\n')

    console.log('✅ All tests completed!')
  } catch (error) {
    console.error('❌ Test failed:', error)
    throw error
  }
}

// For manual testing in browser console
if (typeof window !== 'undefined') {
  ;(window as unknown as { wsTests: Record<string, unknown> }).wsTests = {
    testBasicSubscription,
    testMultipleSubscriptions,
    testSingleton,
    testErrorHandling,
    runAllTests,
  }
  console.log('WebSocket tests available: window.wsTests')
}
