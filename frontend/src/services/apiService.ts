/**
 * API Service Wrapper
 *
 * This wrapper provides a clean interface for API calls that can be easily mocked in tests.
 * It gracefully handles missing generated client for development/testing scenarios.
 */

// Type definitions (fallback when generated types are not available)

import type { APIMetadata, ApiResponse, HealthResponse } from '@/plugins/apiAdapter';
import { ApiAdapter } from '@/plugins/apiAdapter';
import { WsAdapter } from '@/plugins/wsAdapter';
import type { ModuleHealth, ModuleInfo, ModuleVersions } from '@/types/apiStatus';

export interface ApiInterface {
  // OLD - Keep for backward compatibility
  getHealthStatus(): Promise<ApiResponse<HealthResponse>>
  getAPIVersions(): Promise<ApiResponse<APIMetadata>>

  // NEW - Multi-module methods
  getModuleHealth(moduleName: string): Promise<ApiResponse<HealthResponse>>
  getModuleVersions(moduleName: string): Promise<ApiResponse<APIMetadata>>
  getAllModulesHealth(): Promise<ApiResponse<Map<string, ModuleHealth>>>
  getAllModulesVersions(): Promise<ApiResponse<Map<string, ModuleVersions>>>
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
  // NEW: Per-module health
  async getModuleHealth(moduleName: string): Promise<ApiResponse<HealthResponse>> {
    if (MOCK_CONFIG.enableLogs) {
      console.info(`🎭 Using mock API response for ${moduleName} health endpoint`)
    }

    await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.health))

    return {
      status: 200,
      data: {
        status: 'ok',
        timestamp: new Date().toISOString(),
        module_name: moduleName,
        api_version: 'v1',
        message: `${moduleName} module is running (mock)`,
      }
    }
  }

  // NEW: Per-module versions
  async getModuleVersions(moduleName: string): Promise<ApiResponse<APIMetadata>> {
    if (MOCK_CONFIG.enableLogs) {
      console.info(`🎭 Using mock API response for ${moduleName} versions endpoint`)
    }

    await new Promise((resolve) => setTimeout(resolve, MOCK_CONFIG.networkDelay.versions))

    return {
      status: 200,
      data: {
        current_version: 'v1',
        available_versions: {
          v1: {
            version: 'v1',
            release_date: '2024-01-01',
            status: 'stable',
            breaking_changes: [],
            deprecation_notice: null,
            sunset_date: null,
          },
        },
        documentation_url: `/api/v1/${moduleName}/docs`,
        support_contact: 'support@example.com',
      }
    }
  }

  // NEW: All modules health
  async getAllModulesHealth(): Promise<ApiResponse<Map<string, ModuleHealth>>> {
    if (MOCK_CONFIG.enableLogs) {
      console.info('🎭 Using mock API response for all modules health')
    }

    const modules = ['broker', 'datafeed']
    const healthChecks = await Promise.all(
      modules.map(async (name) => {
        const start = Date.now()
        const health = await this.getModuleHealth(name)
        const moduleHealth: ModuleHealth = {
          moduleName: name,
          health: health.data,
          loading: false,
          error: null,
          responseTime: Date.now() - start,
        }
        return [name, moduleHealth] as [string, ModuleHealth]
      })
    )

    return {
      status: 200,
      data: new Map(healthChecks),
    }
  }

  // NEW: All modules versions
  async getAllModulesVersions(): Promise<ApiResponse<Map<string, ModuleVersions>>> {
    if (MOCK_CONFIG.enableLogs) {
      console.info('🎭 Using mock API response for all modules versions')
    }

    const modules = ['broker', 'datafeed']
    const versionChecks = await Promise.all(
      modules.map(async (name) => {
        const versions = await this.getModuleVersions(name)
        const moduleVersions: ModuleVersions = {
          moduleName: name,
          versions: versions.data,
          loading: false,
          error: null,
        }
        return [name, moduleVersions] as [string, ModuleVersions]
      })
    )

    return {
      status: 200,
      data: new Map(versionChecks),
    }
  }

  // OLD: Keep for backward compatibility - delegate to broker
  async getHealthStatus(): Promise<ApiResponse<HealthResponse>> {
    return this.getModuleHealth('broker')
  }

  async getAPIVersions(): Promise<ApiResponse<APIMetadata>> {
    return this.getModuleVersions('broker')
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

  // NEW: Multi-module methods
  async getModuleHealth(moduleName: string): Promise<HealthResponse> {
    const { status, data } = await this._getClient().getModuleHealth(moduleName)
    if (status !== 200) {
      return Promise.reject(new Error(`Health check for ${moduleName} failed with status ${status}`))
    }
    return data
  }

  async getModuleVersions(moduleName: string): Promise<APIMetadata> {
    const { status, data } = await this._getClient().getModuleVersions(moduleName)
    if (status !== 200) {
      return Promise.reject(new Error(`Version check for ${moduleName} failed with status ${status}`))
    }
    return data
  }

  async getAllModulesHealth(): Promise<Map<string, ModuleHealth>> {
    const { status, data } = await this._getClient().getAllModulesHealth()
    if (status !== 200) {
      return Promise.reject(new Error(`All modules health check failed with status ${status}`))
    }
    return data
  }

  async getAllModulesVersions(): Promise<Map<string, ModuleVersions>> {
    const { status, data } = await this._getClient().getAllModulesVersions()
    if (status !== 200) {
      return Promise.reject(new Error(`All modules versions check failed with status ${status}`))
    }
    return data
  }

  /**
   * Get list of integrated modules with their metadata.
   * This is a static method that returns the hardcoded list of modules
   * that are wired into the ApiAdapter.
   */
  static getIntegratedModules(): ModuleInfo[] {
    // Hardcoded list matching ApiAdapter.getIntegratedModules()
    // When adding a new module, update both this method and ApiAdapter
    const wsModules = WsAdapter.getModules()

    return [
      {
        name: 'broker',
        displayName: 'Broker',
        docsUrl: '/api/v1/broker/docs',
        hasWebSocket: wsModules.includes('broker'),
      },
      {
        name: 'datafeed',
        displayName: 'Datafeed',
        docsUrl: '/api/v1/datafeed/docs',
        hasWebSocket: wsModules.includes('datafeed'),
      },
    ]
  }

  getClientType(): 'mock' | 'server' {
    return this.mock ? 'mock' : 'server'
  }
}

export type { APIMetadata, HealthResponse } from '@/plugins/apiAdapter';

