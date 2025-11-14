import { ApiAdapter } from '@/plugins/apiAdapter'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AuthService } from '../authService'

/**
 * Integration tests for AuthService
 *
 * These tests verify the integration between authService and:
 * - AuthApi (generated client)
 * - ApiAdapter (token introspection)
 * - localStorage (refresh token storage)
 * - Router guards (401 error handling)
 */

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock the ApiAdapter
vi.mock('@/plugins/apiAdapter', () => ({
  ApiAdapter: {
    getInstance: vi.fn(),
  },
}))

// Mock the generated auth client
vi.mock('@/clients_generated/trader-client-auth_v1', () => {
  const AuthApi = vi.fn()
  const Configuration = vi.fn()
  return {
    AuthApi,
    Configuration,
  }
})

describe('AuthService Integration Tests', () => {
  let authService: AuthService
  let mockAuthApi: {
    login: ReturnType<typeof vi.fn>
    refreshToken: ReturnType<typeof vi.fn>
    logout: ReturnType<typeof vi.fn>
  }
  let mockApiAdapter: {
    introspectToken: ReturnType<typeof vi.fn>
  }

  beforeEach(async () => {
    // Reset localStorage
    localStorageMock.clear()
    vi.clearAllMocks()

    // Reset modules to clear singleton
    vi.resetModules()

    // Setup mock AuthApi
    mockAuthApi = {
      login: vi.fn(),
      refreshToken: vi.fn(),
      logout: vi.fn(),
    }

    // Setup mock ApiAdapter
    mockApiAdapter = {
      introspectToken: vi.fn(),
    }

    // Configure mocks
    vi.mocked(ApiAdapter.getInstance).mockReturnValue(mockApiAdapter as unknown as ApiAdapter)

    // Mock the AuthApi constructor to return our mock
    const { AuthApi: AuthApiConstructor } = await import('@/clients_generated/trader-client-auth_v1')
    vi.mocked(AuthApiConstructor).mockImplementation(
      () => mockAuthApi as unknown as InstanceType<typeof AuthApiConstructor>
    )

    // Import and create service after mocks are configured
    const { createAuthService } = await import('../authService')
    authService = createAuthService()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Full Login Flow', () => {
    it('should handle complete login flow with Google OAuth', async () => {
      // Mock successful Google token exchange
      mockAuthApi.login.mockResolvedValue({
        data: {
          access_token: 'mock-access-token',
          refresh_token: 'mock-refresh-token',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      await authService.loginWithGoogleToken('valid-google-token')

      // Verify refresh token stored
      expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith(
        'trader_refresh_token',
        'mock-refresh-token'
      )

      // Verify no error
      expect(authService.error.value).toBeNull()
    })

    it('should handle login with backend returning 401', async () => {
      // Mock 401 unauthorized response
      mockAuthApi.login.mockRejectedValue({
        response: {
          status: 401,
          data: { detail: 'Invalid Google token' },
        },
      })

      await expect(authService.loginWithGoogleToken('invalid-token')).rejects.toThrow(
        'Invalid Google token'
      )

      // Verify error state set
      expect(authService.error.value).toBe('Invalid Google token')

      // Verify no refresh token stored
      expect(localStorageMock.setItem).not.toHaveBeenCalled()
    })

    it('should handle login with network failure', async () => {
      // Mock network error
      mockAuthApi.login.mockRejectedValue(new Error('Network error'))

      await expect(authService.loginWithGoogleToken('token')).rejects.toThrow()

      // Verify error state set
      expect(authService.error.value).toBeTruthy()
    })
  })

  describe('Token Introspection Integration', () => {
    it('should integrate with ApiAdapter for token validation', async () => {
      // Mock successful introspection
      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'valid',
          exp: Date.now() + 300000,
          error: null,
        },
      })

      const result = await authService.checkAuthStatus()

      expect(result).toBe(true)
      expect(mockApiAdapter.introspectToken).toHaveBeenCalled()
    })

    it('should handle expired token with refresh flow', async () => {
      localStorageMock.setItem('trader_refresh_token', 'old-refresh-token')
      vi.clearAllMocks()

      // Mock expired token introspection
      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'expired',
          exp: null,
          error: 'Token expired',
        },
      })

      // Mock successful refresh
      mockAuthApi.refreshToken.mockResolvedValue({
        data: {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      const result = await authService.checkAuthStatus()

      expect(result).toBe(true)
      expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith(
        'trader_refresh_token',
        'new-refresh-token'
      )
    })
  })

  describe('Logout Integration', () => {
    it('should handle logout with backend coordination', async () => {
      localStorageMock.setItem('trader_refresh_token', 'current-token')

      // Mock successful logout
      mockAuthApi.logout.mockResolvedValue({})

      await authService.logout()

      // Verify refresh token removed
      expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')

      // Verify error cleared
      expect(authService.error.value).toBeNull()
    })

    it('should handle logout even if backend fails', async () => {
      localStorageMock.setItem('trader_refresh_token', 'current-token')

      // Mock failed logout
      mockAuthApi.logout.mockRejectedValue(new Error('Network error'))

      await authService.logout()

      // Verify refresh token still removed
      expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
    })
  })

  describe('Cross-Tab Synchronization', () => {
    it('should read refresh token from localStorage (cross-tab compatible)', async () => {
      // Simulate another tab storing a refresh token
      localStorageMock.setItem('trader_refresh_token', 'token-from-another-tab')
      vi.clearAllMocks()

      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'expired',
          exp: null,
          error: 'Token expired',
        },
      })

      mockAuthApi.refreshToken.mockResolvedValue({
        data: {
          access_token: 'new-access',
          refresh_token: 'new-refresh',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      const result = await authService.checkAuthStatus()

      expect(result).toBe(true)
      expect(localStorageMock.getItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.getItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
    })

    it('should handle logout clearing token for all tabs', async () => {
      localStorageMock.setItem('trader_refresh_token', 'shared-token')

      mockAuthApi.logout.mockResolvedValue({})

      await authService.logout()

      // Token removed from localStorage (affects all tabs)
      expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
    })
  })

  describe('Error Recovery', () => {
    it('should recover from failed login on retry', async () => {
      // First login fails
      mockAuthApi.login.mockRejectedValueOnce(new Error('Network error'))

      await expect(authService.loginWithGoogleToken('token')).rejects.toThrow()
      expect(authService.error.value).toBeTruthy()

      // Second login succeeds
      mockAuthApi.login.mockResolvedValueOnce({
        data: {
          access_token: 'token',
          refresh_token: 'refresh',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      await authService.loginWithGoogleToken('token')

      expect(authService.error.value).toBeNull()
      expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token', 'refresh')
    })

    it('should handle failed refresh by logging out', async () => {
      localStorageMock.setItem('trader_refresh_token', 'invalid-token')

      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'expired',
          exp: null,
          error: 'Token expired',
        },
      })

      // Mock failed refresh
      mockAuthApi.refreshToken.mockRejectedValue(new Error('Invalid refresh token'))
      mockAuthApi.logout.mockResolvedValue({})

      const result = await authService.checkAuthStatus()

      expect(result).toBe(false)
      expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
    })
  })

  describe('Cookie-Based Authentication', () => {
    it('should work with cookie-based access token (no manual token management)', async () => {
      // Login sets cookie (backend-managed)
      mockAuthApi.login.mockResolvedValue({
        data: {
          access_token: 'mock-access-token',
          refresh_token: 'mock-refresh-token',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      await authService.loginWithGoogleToken('google-token')

      // Service doesn't manage access token (cookie-based)
      // Only refresh token in localStorage
      expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith(
        'trader_refresh_token',
        'mock-refresh-token'
      )
    })

    it('should verify token introspection works with cookies', async () => {
      // Introspection reads token from cookie (automatic via browser)
      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'valid',
          exp: Date.now() + 300000,
          error: null,
        },
      })

      const result = await authService.checkAuthStatus()

      expect(result).toBe(true)
      // No manual token passing needed - browser sends cookie automatically
      expect(mockApiAdapter.introspectToken).toHaveBeenCalled()
    })
  })

  describe('State Consistency', () => {
    it('should maintain consistent state across login -> check -> logout flow', async () => {
      // Login
      mockAuthApi.login.mockResolvedValue({
        data: {
          access_token: 'access',
          refresh_token: 'refresh',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      await authService.loginWithGoogleToken('token')

      expect(authService.error.value).toBeNull()
      expect(authService.isLoading.value).toBe(false)

      // Check status
      mockApiAdapter.introspectToken.mockResolvedValue({
        data: { status: 'valid', exp: Date.now() + 300000, error: null },
      })

      const isValid = await authService.checkAuthStatus()
      expect(isValid).toBe(true)

      // Logout
      mockAuthApi.logout.mockResolvedValue({})

      await authService.logout()

      expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
      expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
      expect(authService.error.value).toBeNull()
    })

    it('should handle concurrent operations gracefully', async () => {
      mockAuthApi.login.mockResolvedValue({
        data: {
          access_token: 'token',
          refresh_token: 'refresh',
          token_type: 'bearer',
          expires_in: 300,
        },
      })

      // Concurrent logins
      await Promise.all([
        authService.loginWithGoogleToken('token1'),
        authService.loginWithGoogleToken('token2'),
      ])

      expect(authService.isLoading.value).toBe(false)
      expect(localStorageMock.setItem).toHaveBeenCalled()
    })
  })

  describe('Router Guard Integration', () => {
    it('should work with router guard token checks', async () => {
      // Simulate router guard calling checkAuthStatus
      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'valid',
          exp: Date.now() + 300000,
          error: null,
        },
      })

      const isAuthenticated = await authService.checkAuthStatus()

      expect(isAuthenticated).toBe(true)
      // Router guard can proceed to protected route
    })

    it('should handle 401 redirect scenario', async () => {
      // Simulate expired token detected by router guard
      mockApiAdapter.introspectToken.mockResolvedValue({
        data: {
          status: 'expired',
          exp: null,
          error: 'Token expired',
        },
      })

      // No refresh token available
      const isAuthenticated = await authService.checkAuthStatus()

      expect(isAuthenticated).toBe(false)
      // Router guard should redirect to login
    })
  })
})
