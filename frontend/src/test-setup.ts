import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeAll } from 'vitest'

// Get the directory of this setup file
const currentDir = dirname(fileURLToPath(import.meta.url))

/**
 * Verify generated client files exist before running tests
 * This ensures tests have the required API clients generated
 *
 * Note: We now use per-module clients (trader-client-broker_v1, trader-client-datafeed_v1)
 * instead of a monolithic trader-client-generated
 */
beforeAll(() => {
  const clientsDir = join(currentDir, 'clients_generated')

  // Required per-module OpenAPI clients
  const requiredOpenAPIClients = ['trader-client-broker_v1', 'trader-client-datafeed_v1']
  const missingOpenAPIClients = requiredOpenAPIClients.filter(
    (client) => !existsSync(join(clientsDir, client)),
  )

  if (missingOpenAPIClients.length > 0) {
    throw new Error(
      `❌ OpenAPI clients not generated! Missing: ${missingOpenAPIClients.join(', ')}\n` +
      'Run client generation before running tests: make generate-clients',
    )
  }

  // Required per-module AsyncAPI types
  const requiredAsyncAPIClients = ['ws-types-broker_v1', 'ws-types-datafeed_v1']
  const missingAsyncAPIClients = requiredAsyncAPIClients.filter(
    (client) => !existsSync(join(clientsDir, client)),
  )

  if (missingAsyncAPIClients.length > 0) {
    throw new Error(
      `❌ AsyncAPI types not generated! Missing: ${missingAsyncAPIClients.join(', ')}\n` +
      'Run client generation before running tests: make generate-clients',
    )
  }

  console.log('✓ Generated per-module clients verified (broker_v1, datafeed_v1)')
})
