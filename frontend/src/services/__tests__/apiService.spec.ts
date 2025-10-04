/**
 * API Service Tests
 *
 * Tests the API service wrapper functionality with mocking
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiService, ApiService, MOCK_CONFIG } from '../apiService'

describe('ApiService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset any cached state for each test
    vi.resetModules()
    // Disable logs during testing
    MOCK_CONFIG.enableLogs = false
  })

  describe('getHealth', () => {
    it('should return health data using fallback when generated client is not available', async () => {
      const result = await apiService.getHealth()

      expect(result).toMatchObject({
        status: 'ok',
        message: expect.stringContaining('Trading API is running'),
        api_version: 'v1',
        timestamp: expect.any(String),
        version_info: expect.any(Object),
      })

      // Verify timestamp is recent (within last minute)
      const timestamp = new Date(result.timestamp)
      const now = new Date()
      const timeDiff = now.getTime() - timestamp.getTime()
      expect(timeDiff).toBeLessThan(60000) // Less than 1 minute
    })

    it('should include realistic mock data', async () => {
      const result = await apiService.getHealth()

      expect(result.status).toBe('ok')
      expect(result.api_version).toBe('v1')
      expect(result.version_info).toHaveProperty('version', 'v1')
      expect(result.version_info).toHaveProperty('status', 'stable')
    })
  })

  describe('getVersions', () => {
    it('should return versions data using fallback when generated client is not available', async () => {
      const result = await apiService.getVersions()

      expect(result).toMatchObject({
        current_version: 'v1',
        available_versions: expect.arrayContaining([
          expect.objectContaining({
            version: 'v1',
            status: 'stable',
          }),
          expect.objectContaining({
            version: 'v2',
            status: 'planned',
          }),
        ]),
        documentation_url: expect.stringContaining('trading.com'),
        support_contact: expect.stringContaining('@trading.com'),
      })
    })

    it('should include realistic version information', async () => {
      const result = await apiService.getVersions()

      expect(result.available_versions).toHaveLength(2)

      const v1 = result.available_versions.find((v) => v.version === 'v1')
      const v2 = result.available_versions.find((v) => v.version === 'v2')

      expect(v1?.status).toBe('stable')
      expect(v2?.status).toBe('planned')
      expect(v2?.breaking_changes).toContain('Authentication required for all endpoints')
    })

    it('should simulate network delay', async () => {
      const startTime = Date.now()
      await apiService.getVersions()
      const endTime = Date.now()

      // Should take at least 100ms due to simulated delay
      expect(endTime - startTime).toBeGreaterThan(100)
    })
  })

  describe('Custom ApiService instance', () => {
    it('should allow creating custom instances for testing', () => {
      const customService = new ApiService()
      expect(customService).toBeInstanceOf(ApiService)
    })
  })

  describe('getClientType', () => {
    it('should return unknown before any API calls', () => {
      const customService = new ApiService()
      expect(customService.getClientType()).toBe('unknown')
    })

    it('should return mock after using fallback client', async () => {
      await apiService.getHealth()
      expect(apiService.getClientType()).toBe('mock')
    })
  })
})
