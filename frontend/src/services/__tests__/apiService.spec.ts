import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '../apiService'

describe('ApiService', () => {
  let apiService: ApiService

  beforeEach(() => {
    apiService = new ApiService(true)
    // Clear any cached client between tests
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Reset any module state if needed
    vi.restoreAllMocks()
  })

  describe('getHealthStatus', () => {
    it('should return health status with expected structure', async () => {
      const healthResponse = await apiService.getHealthStatus()

      expect(healthResponse).toBeDefined()
      expect(healthResponse).toHaveProperty('status')
      expect(healthResponse).toHaveProperty('timestamp')
      expect(healthResponse).toHaveProperty('api_version')
      expect(healthResponse).toHaveProperty('module_name')

      // Validate required fields
      expect(typeof healthResponse.status).toBe('string')
      expect(typeof healthResponse.timestamp).toBe('string')
      expect(typeof healthResponse.api_version).toBe('string')
      expect(typeof healthResponse.module_name).toBe('string')

      // Validate timestamp format (ISO string)
      expect(new Date(healthResponse.timestamp).toISOString()).toBe(healthResponse.timestamp)
    })

    it('should return consistent health status on multiple calls', async () => {
      const firstCall = await apiService.getHealthStatus()
      const secondCall = await apiService.getHealthStatus()

      // Basic structure should be consistent
      expect(firstCall.status).toBe(secondCall.status)
      expect(firstCall.api_version).toBe(secondCall.api_version)

      // Timestamps may differ but should be valid
      expect(new Date(firstCall.timestamp)).toBeInstanceOf(Date)
      expect(new Date(secondCall.timestamp)).toBeInstanceOf(Date)
    })

    it('should return health status within reasonable time', async () => {
      const start = Date.now()
      await apiService.getHealthStatus()
      const duration = Date.now() - start

      // Should complete within 5 seconds (accounting for mock delay + potential network)
      expect(duration).toBeLessThan(5000)
    })

    it('should handle concurrent health status requests', async () => {
      const promises = Array.from({ length: 3 }, () => apiService.getHealthStatus())

      const results = await Promise.all(promises)

      expect(results).toHaveLength(3)
      results.forEach((result) => {
        expect(result).toHaveProperty('status')
        expect(result).toHaveProperty('timestamp')
        expect(result).toHaveProperty('api_version')
      })
    })
  })

  describe('getAPIVersions', () => {
    it('should return API versions metadata with expected structure', async () => {
      const versionsResponse = await apiService.getAPIVersions()

      expect(versionsResponse).toBeDefined()
      expect(versionsResponse).toHaveProperty('current_version')
      expect(versionsResponse).toHaveProperty('available_versions')
      expect(versionsResponse).toHaveProperty('documentation_url')
      expect(versionsResponse).toHaveProperty('support_contact')

      // Validate types
      expect(typeof versionsResponse.current_version).toBe('string')
      expect(typeof versionsResponse.available_versions).toBe('object')
      expect(typeof versionsResponse.documentation_url).toBe('string')
      expect(typeof versionsResponse.support_contact).toBe('string')
    })

    it('should return valid version information structure', async () => {
      const versionsResponse = await apiService.getAPIVersions()

      const versionKeys = Object.keys(versionsResponse.available_versions)
      expect(versionKeys.length).toBeGreaterThan(0)

      Object.values(versionsResponse.available_versions).forEach((version) => {
        expect(version).toHaveProperty('version')
        expect(version).toHaveProperty('release_date')
        expect(version).toHaveProperty('status')

        expect(typeof version.version).toBe('string')
        expect(typeof version.release_date).toBe('string')
        expect(typeof version.status).toBe('string')

        // Optional properties should be the correct type if present
        if (version.breaking_changes !== undefined) {
          expect(Array.isArray(version.breaking_changes)).toBe(true)
        }
        if (version.deprecation_notice !== undefined) {
          expect(['string', 'object']).toContain(typeof version.deprecation_notice) // null or string
        }
        if (version.sunset_date !== undefined) {
          expect(['string', 'object']).toContain(typeof version.sunset_date) // null or string
        }
      })
    })

    it('should include current version in available versions', async () => {
      const versionsResponse = await apiService.getAPIVersions()

      const currentVersionExists = Object.values(versionsResponse.available_versions).some(
        (version) => version.version === versionsResponse.current_version,
      )

      expect(currentVersionExists).toBe(true)
    })

    it('should return consistent versions metadata on multiple calls', async () => {
      const firstCall = await apiService.getAPIVersions()
      const secondCall = await apiService.getAPIVersions()

      expect(firstCall.current_version).toBe(secondCall.current_version)
      expect(firstCall.documentation_url).toBe(secondCall.documentation_url)
      expect(firstCall.support_contact).toBe(secondCall.support_contact)
      expect(firstCall.available_versions).toEqual(secondCall.available_versions)
    })

    it('should return versions metadata within reasonable time', async () => {
      const start = Date.now()
      await apiService.getAPIVersions()
      const duration = Date.now() - start

      // Should complete within 5 seconds (accounting for mock delay + potential network)
      expect(duration).toBeLessThan(5000)
    })
  })

  describe('getClientType', () => {
    it('should return a valid client type', () => {
      const clientType = apiService.getClientType()

      expect(['server', 'mock', 'unknown']).toContain(clientType)
    })

    it('should return consistent client type across calls', () => {
      const firstCall = apiService.getClientType()
      const secondCall = apiService.getClientType()

      expect(firstCall).toBe(secondCall)
    })

    it('should be synchronous', () => {
      const result = apiService.getClientType()
      expect(typeof result).toBe('string')
      // Should not be a promise
      expect(result).not.toBeInstanceOf(Promise)
    })
  })

  describe('API Service Integration', () => {
    it('should work with both health and versions endpoints simultaneously', async () => {
      const [healthResponse, versionsResponse] = await Promise.all([
        apiService.getHealthStatus(),
        apiService.getAPIVersions(),
      ])

      expect(healthResponse).toBeDefined()
      expect(versionsResponse).toBeDefined()

      // Cross-validate version information
      expect(healthResponse.api_version).toBe(versionsResponse.current_version)
    })

    it('should maintain consistency between client type and API responses', async () => {
      const clientType = apiService.getClientType()
      const healthResponse = await apiService.getHealthStatus()

      // Both should work regardless of client type
      expect(clientType).toBeDefined()
      expect(healthResponse).toBeDefined()

      // If using mock, responses should be fast
      if (clientType === 'mock') {
        const start = Date.now()
        await apiService.getHealthStatus()
        const duration = Date.now() - start

        // Mock responses should be relatively fast (under 1 second including mock delay)
        expect(duration).toBeLessThan(1000)
      }
    })

    it('should handle multiple service instances independently', async () => {
      const service1 = new ApiService(true)
      const service2 = new ApiService(true)

      const [result1, result2] = await Promise.all([
        service1.getHealthStatus(),
        service2.getHealthStatus(),
      ])

      // Both should return valid responses
      expect(result1).toBeDefined()
      expect(result2).toBeDefined()
      expect(result1.status).toBe(result2.status)
    })
  })

  describe('Error Handling and Resilience', () => {
    it('should handle rapid successive calls gracefully', async () => {
      const rapidCalls = Array.from({ length: 10 }, () =>
        Promise.all([apiService.getHealthStatus(), apiService.getAPIVersions()]),
      )

      const results = await Promise.all(rapidCalls)

      expect(results).toHaveLength(10)
      results.forEach(([health, versions]) => {
        expect(health).toBeDefined()
        expect(versions).toBeDefined()
        expect(health.status).toBeDefined()
        expect(versions.current_version).toBeDefined()
      })
    })

    it('should maintain service integrity across different call patterns', async () => {
      // Sequential calls
      const health1 = await apiService.getHealthStatus()
      const versions1 = await apiService.getAPIVersions()

      // Parallel calls
      const [health2, versions2] = await Promise.all([
        apiService.getHealthStatus(),
        apiService.getAPIVersions(),
      ])

      // Validate all responses are consistent
      expect(health1.api_version).toBe(health2.api_version)
      expect(versions1.current_version).toBe(versions2.current_version)
      expect(health1.api_version).toBe(versions1.current_version)
    })

    it('should work correctly after multiple client type checks', async () => {
      // Check client type multiple times
      const type1 = apiService.getClientType()
      const type2 = apiService.getClientType()
      const type3 = apiService.getClientType()

      expect(type1).toBe(type2)
      expect(type2).toBe(type3)

      // API calls should still work
      const healthResponse = await apiService.getHealthStatus()
      expect(healthResponse).toBeDefined()
      expect(healthResponse.status).toBeDefined()
    })
  })

  describe('Response Validation', () => {
    it('should ensure health response follows HealthResponse interface', async () => {
      const health = await apiService.getHealthStatus()

      // Required fields according to HealthResponse interface
      expect(health).toMatchObject({
        status: expect.any(String),
        timestamp: expect.any(String),
        api_version: expect.any(String),
        module_name: expect.any(String),
      })

      // Optional field
      if ('message' in health) {
        expect(typeof health.message).toBe('string')
      }
    })

    it('should ensure versions response follows APIMetadata interface', async () => {
      const versions = await apiService.getAPIVersions()

      // Required fields according to APIMetadata interface
      expect(versions).toMatchObject({
        current_version: expect.any(String),
        available_versions: expect.any(Object),
        documentation_url: expect.any(String),
        support_contact: expect.any(String),
      })

      // Validate VersionInfo structure for each version
      Object.values(versions.available_versions).forEach((version) => {
        expect(version).toMatchObject({
          version: expect.any(String),
          release_date: expect.any(String),
          status: expect.any(String),
        })
      })
    })
  })

  // NEW: Multi-module method tests
  describe('getModuleHealth', () => {
    it('should return health status for broker module', async () => {
      const healthResponse = await apiService.getModuleHealth('broker')

      expect(healthResponse).toBeDefined()
      expect(healthResponse).toHaveProperty('status')
      expect(healthResponse).toHaveProperty('timestamp')
      expect(healthResponse).toHaveProperty('api_version')
      expect(healthResponse.module_name).toBe('broker')
    })

    it('should return health status for datafeed module', async () => {
      const healthResponse = await apiService.getModuleHealth('datafeed')

      expect(healthResponse).toBeDefined()
      expect(healthResponse).toHaveProperty('status')
      expect(healthResponse).toHaveProperty('timestamp')
      expect(healthResponse).toHaveProperty('api_version')
      expect(healthResponse.module_name).toBe('datafeed')
    })

    it('should return different timestamps for each call', async () => {
      const first = await apiService.getModuleHealth('broker')
      await new Promise((resolve) => setTimeout(resolve, 50))
      const second = await apiService.getModuleHealth('broker')

      expect(first.timestamp).not.toBe(second.timestamp)
    })

    it('should handle concurrent requests for different modules', async () => {
      const [brokerHealth, datafeedHealth] = await Promise.all([
        apiService.getModuleHealth('broker'),
        apiService.getModuleHealth('datafeed'),
      ])

      expect(brokerHealth.module_name).toBe('broker')
      expect(datafeedHealth.module_name).toBe('datafeed')
    })

    it('should validate health response structure', async () => {
      const health = await apiService.getModuleHealth('broker')

      expect(health).toMatchObject({
        status: expect.any(String),
        timestamp: expect.any(String),
        api_version: expect.any(String),
        module_name: expect.any(String),
      })

      // Validate timestamp is ISO format
      expect(new Date(health.timestamp).toISOString()).toBe(health.timestamp)
    })
  })

  describe('getModuleVersions', () => {
    it('should return versions for broker module', async () => {
      const versionsResponse = await apiService.getModuleVersions('broker')

      expect(versionsResponse).toBeDefined()
      expect(versionsResponse).toHaveProperty('current_version')
      expect(versionsResponse).toHaveProperty('available_versions')
      expect(versionsResponse.documentation_url).toContain('broker')
    })

    it('should return versions for datafeed module', async () => {
      const versionsResponse = await apiService.getModuleVersions('datafeed')

      expect(versionsResponse).toBeDefined()
      expect(versionsResponse).toHaveProperty('current_version')
      expect(versionsResponse).toHaveProperty('available_versions')
      expect(versionsResponse.documentation_url).toContain('datafeed')
    })

    it('should return valid version structure for each module', async () => {
      const brokerVersions = await apiService.getModuleVersions('broker')

      Object.values(brokerVersions.available_versions).forEach((version) => {
        expect(version).toHaveProperty('version')
        expect(version).toHaveProperty('release_date')
        expect(version).toHaveProperty('status')
        expect(typeof version.version).toBe('string')
      })
    })

    it('should handle concurrent version requests', async () => {
      const [brokerVersions, datafeedVersions] = await Promise.all([
        apiService.getModuleVersions('broker'),
        apiService.getModuleVersions('datafeed'),
      ])

      expect(brokerVersions.documentation_url).toContain('broker')
      expect(datafeedVersions.documentation_url).toContain('datafeed')
    })

    it('should include current version in available versions', async () => {
      const versions = await apiService.getModuleVersions('broker')

      const currentVersionExists = Object.values(versions.available_versions).some(
        (version) => version.version === versions.current_version,
      )

      expect(currentVersionExists).toBe(true)
    })
  })

  describe('getAllModulesHealth', () => {
    it('should return health for all modules', async () => {
      const allHealth = await apiService.getAllModulesHealth()

      expect(allHealth).toBeInstanceOf(Map)
      expect(allHealth.size).toBeGreaterThanOrEqual(2)
      expect(allHealth.has('broker')).toBe(true)
      expect(allHealth.has('datafeed')).toBe(true)
    })

    it('should return ModuleHealth objects for each module', async () => {
      const allHealth = await apiService.getAllModulesHealth()

      allHealth.forEach((moduleHealth, moduleName) => {
        expect(moduleHealth).toHaveProperty('moduleName')
        expect(moduleHealth).toHaveProperty('health')
        expect(moduleHealth).toHaveProperty('loading')
        expect(moduleHealth).toHaveProperty('error')
        expect(moduleHealth).toHaveProperty('responseTime')

        expect(moduleHealth.moduleName).toBe(moduleName)
        expect(moduleHealth.loading).toBe(false)
        expect(typeof moduleHealth.responseTime).toBe('number')
      })
    })

    it('should include health data when module is healthy', async () => {
      const allHealth = await apiService.getAllModulesHealth()
      const brokerHealth = allHealth.get('broker')

      expect(brokerHealth).toBeDefined()
      expect(brokerHealth!.health).not.toBeNull()
      expect(brokerHealth!.health).toHaveProperty('status')
      expect(brokerHealth!.health).toHaveProperty('timestamp')
      expect(brokerHealth!.error).toBeNull()
    })

    it('should track response times for each module', async () => {
      const allHealth = await apiService.getAllModulesHealth()

      allHealth.forEach((moduleHealth) => {
        expect(moduleHealth.responseTime).toBeGreaterThan(0)
        expect(moduleHealth.responseTime).toBeLessThan(5000)
      })
    })

    it('should handle concurrent getAllModulesHealth calls', async () => {
      const [first, second] = await Promise.all([
        apiService.getAllModulesHealth(),
        apiService.getAllModulesHealth(),
      ])

      expect(first.size).toBe(second.size)
      expect(first.has('broker')).toBe(true)
      expect(second.has('broker')).toBe(true)
    })

    it('should return consistent module names across calls', async () => {
      const first = await apiService.getAllModulesHealth()
      const second = await apiService.getAllModulesHealth()

      const firstModules = Array.from(first.keys()).sort()
      const secondModules = Array.from(second.keys()).sort()

      expect(firstModules).toEqual(secondModules)
    })

    it('should not set loading flag in completed response', async () => {
      const allHealth = await apiService.getAllModulesHealth()

      allHealth.forEach((moduleHealth) => {
        expect(moduleHealth.loading).toBe(false)
      })
    })

    it('should validate ModuleHealth structure', async () => {
      const allHealth = await apiService.getAllModulesHealth()
      const brokerHealth = allHealth.get('broker')

      expect(brokerHealth).toMatchObject({
        moduleName: 'broker',
        health: expect.any(Object),
        loading: false,
        error: null,
        responseTime: expect.any(Number),
      })
    })
  })

  describe('getAllModulesVersions', () => {
    it('should return versions for all modules', async () => {
      const allVersions = await apiService.getAllModulesVersions()

      expect(allVersions).toBeInstanceOf(Map)
      expect(allVersions.size).toBeGreaterThanOrEqual(2)
      expect(allVersions.has('broker')).toBe(true)
      expect(allVersions.has('datafeed')).toBe(true)
    })

    it('should return ModuleVersions objects for each module', async () => {
      const allVersions = await apiService.getAllModulesVersions()

      allVersions.forEach((moduleVersions, moduleName) => {
        expect(moduleVersions).toHaveProperty('moduleName')
        expect(moduleVersions).toHaveProperty('versions')
        expect(moduleVersions).toHaveProperty('loading')
        expect(moduleVersions).toHaveProperty('error')

        expect(moduleVersions.moduleName).toBe(moduleName)
        expect(moduleVersions.loading).toBe(false)
      })
    })

    it('should include versions data when module is accessible', async () => {
      const allVersions = await apiService.getAllModulesVersions()
      const brokerVersions = allVersions.get('broker')

      expect(brokerVersions).toBeDefined()
      expect(brokerVersions!.versions).not.toBeNull()
      expect(brokerVersions!.versions).toHaveProperty('current_version')
      expect(brokerVersions!.versions).toHaveProperty('available_versions')
      expect(brokerVersions!.error).toBeNull()
    })

    it('should validate versions structure for each module', async () => {
      const allVersions = await apiService.getAllModulesVersions()

      allVersions.forEach((moduleVersions) => {
        if (moduleVersions.versions) {
          expect(moduleVersions.versions).toHaveProperty('current_version')
          expect(moduleVersions.versions).toHaveProperty('available_versions')
          expect(typeof moduleVersions.versions.current_version).toBe('string')
          expect(typeof moduleVersions.versions.available_versions).toBe('object')
        }
      })
    })

    it('should handle concurrent getAllModulesVersions calls', async () => {
      const [first, second] = await Promise.all([
        apiService.getAllModulesVersions(),
        apiService.getAllModulesVersions(),
      ])

      expect(first.size).toBe(second.size)
      expect(first.has('broker')).toBe(true)
      expect(second.has('broker')).toBe(true)
    })

    it('should return consistent module names across calls', async () => {
      const first = await apiService.getAllModulesVersions()
      const second = await apiService.getAllModulesVersions()

      const firstModules = Array.from(first.keys()).sort()
      const secondModules = Array.from(second.keys()).sort()

      expect(firstModules).toEqual(secondModules)
    })

    it('should not set loading flag in completed response', async () => {
      const allVersions = await apiService.getAllModulesVersions()

      allVersions.forEach((moduleVersions) => {
        expect(moduleVersions.loading).toBe(false)
      })
    })

    it('should validate ModuleVersions structure', async () => {
      const allVersions = await apiService.getAllModulesVersions()
      const brokerVersions = allVersions.get('broker')

      expect(brokerVersions).toMatchObject({
        moduleName: 'broker',
        versions: expect.any(Object),
        loading: false,
        error: null,
      })
    })
  })

  describe('Multi-module Integration', () => {
    it('should cross-validate health and versions for same module', async () => {
      const health = await apiService.getModuleHealth('broker')
      const versions = await apiService.getModuleVersions('broker')

      expect(health.api_version).toBe(versions.current_version)
    })

    it('should work with parallel per-module and all-modules calls', async () => {
      const [brokerHealth, allHealth] = await Promise.all([
        apiService.getModuleHealth('broker'),
        apiService.getAllModulesHealth(),
      ])

      const brokerFromAll = allHealth.get('broker')
      expect(brokerFromAll).toBeDefined()
      expect(brokerFromAll!.health).not.toBeNull()
      expect(brokerHealth.module_name).toBe(brokerFromAll!.moduleName)
    })

    it('should handle rapid mixed calls gracefully', async () => {
      const promises = [
        apiService.getModuleHealth('broker'),
        apiService.getAllModulesHealth(),
        apiService.getModuleVersions('datafeed'),
        apiService.getAllModulesVersions(),
        apiService.getModuleHealth('datafeed'),
        apiService.getModuleVersions('broker'),
      ]

      const results = await Promise.all(promises)

      expect(results).toHaveLength(6)
      expect(results[0]).toHaveProperty('status') // broker health
      expect(results[1]).toBeInstanceOf(Map) // all health
      expect(results[2]).toHaveProperty('current_version') // datafeed versions
      expect(results[3]).toBeInstanceOf(Map) // all versions
      expect(results[4]).toHaveProperty('status') // datafeed health
      expect(results[5]).toHaveProperty('current_version') // broker versions
    })

    it('should maintain consistency between per-module and all-modules calls', async () => {
      const [brokerHealth, allHealth] = await Promise.all([
        apiService.getModuleHealth('broker'),
        apiService.getAllModulesHealth(),
      ])

      const brokerFromAll = allHealth.get('broker')!
      expect(brokerHealth.module_name).toBe(brokerFromAll.moduleName)
      expect(brokerHealth.status).toBe(brokerFromAll.health!.status)
    })
  })

  describe('Backward Compatibility', () => {
    it('should ensure getHealthStatus delegates to broker module', async () => {
      const oldHealth = await apiService.getHealthStatus()
      const brokerHealth = await apiService.getModuleHealth('broker')

      expect(oldHealth.api_version).toBe(brokerHealth.api_version)
      expect(oldHealth.status).toBe(brokerHealth.status)
    })

    it('should ensure getAPIVersions delegates to broker module', async () => {
      const oldVersions = await apiService.getAPIVersions()
      const brokerVersions = await apiService.getModuleVersions('broker')

      expect(oldVersions.current_version).toBe(brokerVersions.current_version)
      expect(oldVersions.documentation_url).toBe(brokerVersions.documentation_url)
    })

    it('should work with mixed old and new API calls', async () => {
      const [oldHealth, newHealth, oldVersions, newVersions] = await Promise.all([
        apiService.getHealthStatus(),
        apiService.getModuleHealth('broker'),
        apiService.getAPIVersions(),
        apiService.getModuleVersions('broker'),
      ])

      expect(oldHealth.api_version).toBe(newHealth.api_version)
      expect(oldVersions.current_version).toBe(newVersions.current_version)
    })
  })
})
