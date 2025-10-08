import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '../apiService'

describe('ApiService', () => {
  let apiService: ApiService

  beforeEach(() => {
    apiService = new ApiService()
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
      expect(healthResponse).toHaveProperty('version_info')

      // Validate required fields
      expect(typeof healthResponse.status).toBe('string')
      expect(typeof healthResponse.timestamp).toBe('string')
      expect(typeof healthResponse.api_version).toBe('string')
      expect(typeof healthResponse.version_info).toBe('object')

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
      expect(Array.isArray(versionsResponse.available_versions)).toBe(true)
      expect(typeof versionsResponse.documentation_url).toBe('string')
      expect(typeof versionsResponse.support_contact).toBe('string')
    })

    it('should return valid version information structure', async () => {
      const versionsResponse = await apiService.getAPIVersions()

      expect(versionsResponse.available_versions.length).toBeGreaterThan(0)

      versionsResponse.available_versions.forEach((version) => {
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

      const currentVersionExists = versionsResponse.available_versions.some(
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
      const service1 = new ApiService()
      const service2 = new ApiService()

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
        version_info: expect.any(Object),
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
        available_versions: expect.any(Array),
        documentation_url: expect.any(String),
        support_contact: expect.any(String),
      })

      // Validate VersionInfo structure for each version
      versions.available_versions.forEach((version) => {
        expect(version).toMatchObject({
          version: expect.any(String),
          release_date: expect.any(String),
          status: expect.any(String),
        })
      })
    })
  })
})
