import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeAll } from 'vitest'

// Get the directory of this setup file
const currentDir = dirname(fileURLToPath(import.meta.url))

/**
 * Verify generated client files exist before running tests
 * This ensures tests have the required API client generated
 */
beforeAll(() => {
  const clientsDir = join(currentDir, 'clients')
  const traderClientDir = join(clientsDir, 'trader-client-generated')
  const wsClientDir = join(clientsDir, 'ws-types-generated')

  if (!existsSync(traderClientDir)) {
    throw new Error(
      '❌ API client not generated! Run client generation before running tests.',
    )
  }

  if (!existsSync(wsClientDir)) {
    throw new Error(
      '❌ WebSocket types not generated! Run client generation before running tests.',
    )
  }

  console.log('✓ Generated clients verified')
})
