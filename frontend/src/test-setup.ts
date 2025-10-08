import { existsSync, readdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeAll } from 'vitest'

// Get the directory of this setup file
const currentDir = dirname(fileURLToPath(import.meta.url))

/**
 * Clear generated client files before running tests
 * This ensures tests run with consistent state and don't depend on generated artifacts
 */
beforeAll(() => {
  const clientsDir = join(currentDir, 'clients')

  try {
    // Remove any directories or files matching *-generated pattern
    const generatedPattern = /-generated$/

    if (existsSync(clientsDir)) {
      const entries = readdirSync(clientsDir, { withFileTypes: true })

      for (const entry of entries) {
        if (generatedPattern.test(entry.name)) {
          const fullPath = join(clientsDir, entry.name)
          console.log(`🧹 Clearing generated files: ${fullPath}`)
          rmSync(fullPath, { recursive: true, force: true })
        }
      }
    }
  } catch (error) {
    console.warn('⚠️ Failed to clear generated client files:', error)
  }
})
