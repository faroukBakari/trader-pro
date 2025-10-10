/**
 * API Service Wrapper
 *
 * This wrapper provides a clean interface for API calls that can be easily mocked in tests.
 * It gracefully handles missing generated client for development/testing scenarios.
 */

// Type definitions (fallback when generated types are not available)

import { TraderPlugin } from '@/plugins/traderPlugin'
export interface HealthResponse {
  status: string
  message?: string
  timestamp: string
  api_version: string
  version_info: object
}

export interface VersionInfo {
  version: string
  release_date: string
  status: string
  breaking_changes?: string[]
  deprecation_notice?: string | null
  sunset_date?: string | null
}

export interface APIMetadata {
  current_version: string
  available_versions: VersionInfo[]
  documentation_url: string
  support_contact: string
}

export interface ClientInterface {
  getHealthStatus(): Promise<{ status: number; data: HealthResponse }>
  getAPIVersions(): Promise<{ status: number; data: APIMetadata }>
}

// Configuration for mock behavior
const MOCK_CONFIG = {
  networkDelay: {
    health: 100,
    versions: 150,
  },
  enableLogs: false, // Disabled by default for cleaner UX
}

// Fallback implementation with mock data for development/testing
class FallbackClient implements ClientInterface {
  async getHealthStatus(): Promise<{ status: number; data: HealthResponse }> {
    if (MOCK_CONFIG.enableLogs) {
      console.info('🎭 Using mock API response for health endpoint')
    }

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.health))

    return {
      status: 200,
      data: {
        status: 'ok',
        message: 'Trading API down',
        timestamp: new Date().toISOString(),
        api_version: 'v0',
        version_info: {
          version: 'v0',
          release_date: new Date().toISOString().split('T')[0],
          status: 'none',
          deprecation_notice: null,
        },
      },
    }
  }

  async getAPIVersions(): Promise<{ status: number; data: APIMetadata }> {
    if (MOCK_CONFIG.enableLogs) {
      console.info('🎭 Using mock API response for versions endpoint')
    }

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.versions))

    return {
      status: 200,
      data: {
        current_version: 'v0',
        available_versions: [
          {
            version: 'v0',
            release_date: '2024-01-01',
            status: 'none',
            breaking_changes: [],
            deprecation_notice: null,
            sunset_date: null,
          },
          {
            version: 'v1',
            release_date: 'none',
            status: 'next',
            breaking_changes: ['none'],
            deprecation_notice: null,
            sunset_date: null,
          },
        ],
        documentation_url: '/',
        support_contact: 'none',
      },
    }
  }
}

// Main API service implementation
export class ApiService {
  private plugin: TraderPlugin<ClientInterface>

  constructor() {
    this.plugin = new TraderPlugin<ClientInterface>()
  }

  async _loadClient(): Promise<ClientInterface> {
    return this.plugin.getClientWithFallback(FallbackClient)
  }

  async getHealthStatus(): Promise<HealthResponse> {
    return this._loadClient().then(async (client) => {
      const { status, data } = await client.getHealthStatus()
      if (status !== 200) {
        return Promise.reject(new Error(`Health check failed with status ${status}`))
      }
      return data
    })
  }

  async getAPIVersions(): Promise<APIMetadata> {
    return this._loadClient().then(async (client) => {
      const { status, data } = await client.getAPIVersions()
      if (status !== 200) {
        return Promise.reject(new Error(`Versions check failed with status ${status}`))
      }
      return data
    })
  }

  // Check if currently using mock client
  getClientType(): 'server' | 'mock' | 'unknown' {
    return TraderPlugin.getClientType()
  }
}
