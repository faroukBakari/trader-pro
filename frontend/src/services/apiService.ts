/**
 * API Service Wrapper
 *
 * This wrapper provides a clean interface for API calls that can be easily mocked in tests.
 * It gracefully handles missing generated client for development/testing scenarios.
 */

// Type definitions (fallback when generated types are not available)

import type { APIMetadata, ApiResponse, HealthResponse } from '@/plugins/apiAdapter';
import { ApiAdapter } from '@/plugins/apiAdapter';

export interface ApiInterface {
  getHealthStatus(): Promise<ApiResponse<HealthResponse>>
  getAPIVersions(): Promise<ApiResponse<APIMetadata>>
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
class ApiFallback implements ApiInterface {
  async getHealthStatus(): Promise<ApiResponse<HealthResponse>> {
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

  async getAPIVersions(): Promise<ApiResponse<APIMetadata>> {
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
  private adapter: ApiInterface
  private fallback: ApiInterface
  private mock: boolean
  constructor(mock: boolean = false) {
    this.adapter = new ApiAdapter()
    this.fallback = new ApiFallback()
    this.mock = mock
  }

  _getClient(mock: boolean = this.mock): ApiInterface {
    return mock ? this.fallback : this.adapter
  }

  async getHealthStatus(): Promise<HealthResponse> {
    const { status, data } = await this._getClient().getHealthStatus()
    if (status !== 200) {
      return Promise.reject(new Error(`Health check failed with status ${status}`))
    }
    return data
  }

  async getAPIVersions(): Promise<APIMetadata> {
    const { status, data } = await this._getClient().getAPIVersions()
    if (status !== 200) {
      return Promise.reject(new Error(`Versions check failed with status ${status}`))
    }
    return data
  }

  getClientType(): 'mock' | 'server' {
    return this.mock ? 'mock' : 'server'
  }
}

export type { APIMetadata, HealthResponse } from '@/plugins/apiAdapter';

