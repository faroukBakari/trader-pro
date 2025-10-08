/**
 * API Service Wrapper
 *
 * This wrapper provides a clean interface for API calls that can be easily mocked in tests.
 * It gracefully handles missing generated client for development/testing scenarios.
 */

// Type definitions (fallback when generated types are not available)

import { TraderPlugin } from '@clients/traderPlugin'
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

export interface ApiServiceInterface {
  getHealthStatus(): Promise<HealthResponse>
  getAPIVersions(): Promise<APIMetadata>
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
class FallbackApiService implements ApiServiceInterface {
  async getHealthStatus(): Promise<HealthResponse> {
    if (MOCK_CONFIG.enableLogs) {
      console.info('🎭 Using mock API response for health endpoint')
    }

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.health))

    return {
      status: 'ok',
      message: 'Trading API is running',
      timestamp: new Date().toISOString(),
      api_version: 'v1',
      version_info: {
        version: 'v1',
        release_date: new Date().toISOString().split('T')[0],
        status: 'stable',
        deprecation_notice: null,
      },
    }
  }
  async getAPIVersions(): Promise<APIMetadata> {
    if (MOCK_CONFIG.enableLogs) {
      console.info('🎭 Using mock API response for versions endpoint')
    }

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.versions))

    return {
      current_version: 'v1',
      available_versions: [
        {
          version: 'v1',
          release_date: '2024-01-01',
          status: 'stable',
          breaking_changes: [],
          deprecation_notice: null,
          sunset_date: null,
        },
        {
          version: 'v2',
          release_date: 'TBD',
          status: 'planned',
          breaking_changes: [
            'Authentication required for all endpoints',
            'New response format for error messages',
            'Renamed health endpoint to status',
          ],
          deprecation_notice: null,
          sunset_date: null,
        },
      ],
      documentation_url: '/api/v1/docs',
      support_contact: 'support@trading-pro.nodomainyet',
    }
  }
}

// Main API service implementation
class ApiService {
  private plugin: TraderPlugin<ApiServiceInterface>

  constructor() {
    this.plugin = new TraderPlugin<ApiServiceInterface>()
  }

  async getHealthStatus(): Promise<HealthResponse> {
    return this.plugin.getClient(FallbackApiService).then((client) => client.getHealthStatus())
  }

  async getAPIVersions(): Promise<APIMetadata> {
    return this.plugin.getClient(FallbackApiService).then((client) => client.getAPIVersions())
  }

  // Check if currently using mock client
  getClientType(): 'server' | 'mock' | 'unknown' {
    return TraderPlugin.getClientType()
  }
}

// Export singleton instance
export const apiService = new ApiService()

// Export classes for testing/mocking
export { ApiService, FallbackApiService }

// Export mock configuration for testing
export { MOCK_CONFIG }
