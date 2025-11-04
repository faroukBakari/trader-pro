import { fileURLToPath } from 'node:url'
import { configDefaults, defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test-setup.ts'],
      exclude: [
        ...configDefaults.exclude,
        'e2e/**',
        'public/charting_library/**',
        'public/datafeeds/**',
        'src/clients/*-generated/**',
      ],
      root: fileURLToPath(new URL('./', import.meta.url)),
      env: {
        VITE_TRADER_API_BASE_PATH: 'http://localhost:8000',
      },
    },
  }),
)
