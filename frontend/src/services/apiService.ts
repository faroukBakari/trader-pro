/**
 * API Service Wrapper
 *
 * This wrapper provides a clean interface for API calls that can be easily mocked in tests.
 * It gracefully handles missing generated client for development/testing scenarios.
 */

// Type definitions (fallback when generated types are not available)
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
  healthApi: { getHealthStatus(): Promise<{ data: HealthResponse }> }
  versioningApi: { getAPIVersions(): Promise<{ data: APIMetadata }> }
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
  healthApi = {
    async getHealthStatus(): Promise<{ data: HealthResponse }> {
      if (MOCK_CONFIG.enableLogs) {
        console.info('🎭 Using mock API response for health endpoint')
      }

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.health))

      return {
        data: {
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
        },
      }
    },
  }
  versioningApi = {
    async getAPIVersions(): Promise<{ data: APIMetadata }> {
      if (MOCK_CONFIG.enableLogs) {
        console.info('🎭 Using mock API response for versions endpoint')
      }

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.versions))

      return {
        data: {
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
        },
      }
    },
  }
}

// Dynamic import helper for generated client
const fallback = new FallbackApiService()

// Main API service implementation
class ApiService {
  private clientType: 'server' | 'mock' | 'unknown' = 'unknown'
  private clientPromise: Promise<ApiServiceInterface> | null = null

  private async getGeneratedClient(): Promise<ApiServiceInterface> {
    if (!this.clientPromise) {
      // Use dynamic path construction to avoid Vite's static analysis
      const baseUrl = '../clients/trader-api-generated/'
      const fileName = 'client-config'
      const modulePath = baseUrl + fileName

      this.clientPromise = import(/* @vite-ignore */ modulePath)
        .then((mod) => mod as unknown as ApiServiceInterface)
        .catch((importError) => {
          // If import fails (file doesn't exist), throw error to trigger fallback
          throw new Error(`Generated client not available: ${importError.message}`)
        })
    }

    try {
      const client = await this.clientPromise
      this.clientType = 'server'
      if (import.meta.env.DEV) {
        console.info('✅ Generated API client loaded successfully')
      }
      return client
    } catch {
      if (import.meta.env.DEV) {
        console.warn('⚠️ Using fallback API client (generated client not available)')
      }
      this.clientType = 'mock'
      return fallback
    }
  }

  async getHealthStatus(): Promise<HealthResponse> {
    return this.getGeneratedClient().then((client) => {
      return client.healthApi.getHealthStatus().then((response) => response.data)
    })
  }

  async getAPIVersions(): Promise<APIMetadata> {
    return this.getGeneratedClient().then((client) => {
      return client.versioningApi.getAPIVersions().then((response) => response.data)
    })
  }

  // Check if currently using mock client
  getClientType(): 'server' | 'mock' | 'unknown' {
    return this.clientType
  }
}

// Export singleton instance
export const apiService = new ApiService()

// Export classes for testing/mocking
export { ApiService, FallbackApiService }

// Export mock configuration for testing
export { MOCK_CONFIG }
