import { ApiAdapter } from '@/plugins/apiAdapter'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AuthService } from '../authService'

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

describe('AuthService', () => {
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

    describe('Service Initialization', () => {
        it('should create service with initial state', () => {
            expect(authService.isLoading.value).toBe(false)
            expect(authService.error.value).toBeNull()
        })

        it('should create singleton instance with createAuthService', async () => {
            const { createAuthService } = await import('../authService')
            const instance1 = createAuthService()
            const instance2 = createAuthService()
            expect(instance1).toBe(instance2)
        })

        it('should create singleton instance with useAuthService', async () => {
            const { useAuthService } = await import('../authService')
            const instance1 = useAuthService()
            const instance2 = useAuthService()
            expect(instance1).toBe(instance2)
        })

        it('should have reactive refs for state management', () => {
            expect(authService.isLoading.value).toBeDefined()
            expect(authService.error.value).toBeDefined()

            // Verify refs are reactive
            authService.isLoading.value = true
            expect(authService.isLoading.value).toBe(true)

            authService.error.value = 'Test error'
            expect(authService.error.value).toBe('Test error')
        })
    })

    describe('checkAuthStatus', () => {
        it('should return true when token is valid', async () => {
            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'valid', exp: Date.now() + 300000, error: null },
            })

            const result = await authService.checkAuthStatus()

            expect(result).toBe(true)
            expect(mockApiAdapter.introspectToken).toHaveBeenCalledTimes(1)
        })

        it('should attempt refresh when token is expired and refresh token exists', async () => {
            const refreshToken = 'valid-refresh-token'
            localStorageMock.setItem('trader_refresh_token', refreshToken)
            vi.clearAllMocks()

            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

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
            expect(mockApiAdapter.introspectToken).toHaveBeenCalledTimes(1)
            expect(mockAuthApi.refreshToken).toHaveBeenCalledTimes(1)
            expect(mockAuthApi.refreshToken).toHaveBeenCalledExactlyOnceWith({
                refresh_token: refreshToken,
            })
            expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith(
                'trader_refresh_token',
                'new-refresh-token'
            )
        })

        it('should return false when token is expired and no refresh token exists', async () => {
            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

            const result = await authService.checkAuthStatus()

            expect(result).toBe(false)
            expect(mockAuthApi.refreshToken).not.toHaveBeenCalled()
        })

        it('should return false when token is revoked', async () => {
            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'revoked', exp: null, error: 'Token revoked' },
            })

            const result = await authService.checkAuthStatus()

            expect(result).toBe(false)
        })

        it('should return false and logout when refresh fails', async () => {
            localStorageMock.setItem('trader_refresh_token', 'invalid-token')

            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

            mockAuthApi.refreshToken.mockRejectedValue(new Error('Invalid refresh token'))
            mockAuthApi.logout.mockResolvedValue({})

            const result = await authService.checkAuthStatus()

            expect(result).toBe(false)
            expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
        })

        it('should handle introspection API errors gracefully', async () => {
            mockApiAdapter.introspectToken.mockRejectedValue(new Error('Network error'))

            const result = await authService.checkAuthStatus()

            expect(result).toBe(false)
        })

        it('should not throw errors on failure', async () => {
            mockApiAdapter.introspectToken.mockRejectedValue(new Error('API error'))

            await expect(authService.checkAuthStatus()).resolves.toBe(false)
        })
    })

    describe('loginWithGoogleToken', () => {
        const googleToken = 'valid-google-id-token'

        it('should successfully login with valid Google token', async () => {
            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'new-access-token',
                    refresh_token: 'new-refresh-token',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            await authService.loginWithGoogleToken(googleToken)

            expect(mockAuthApi.login).toHaveBeenCalledTimes(1)
            expect(mockAuthApi.login).toHaveBeenCalledExactlyOnceWith({
                google_token: googleToken,
            })
            expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith(
                'trader_refresh_token',
                'new-refresh-token'
            )
            expect(authService.error.value).toBeNull()
        })

        it('should set loading state during login', async () => {
            mockAuthApi.login.mockImplementation(
                () =>
                    new Promise((resolve) =>
                        setTimeout(
                            () =>
                                resolve({
                                    data: {
                                        access_token: 'token',
                                        refresh_token: 'refresh',
                                        token_type: 'bearer',
                                        expires_in: 300,
                                    },
                                }),
                            100
                        )
                    )
            )

            const loginPromise = authService.loginWithGoogleToken(googleToken)

            // Check loading state is true during operation
            expect(authService.isLoading.value).toBe(true)

            await loginPromise

            // Check loading state is false after completion
            expect(authService.isLoading.value).toBe(false)
        })

        it('should handle 401 unauthorized error', async () => {
            const axiosError = {
                response: {
                    status: 401,
                    data: { detail: 'Invalid Google token' },
                },
            }
            mockAuthApi.login.mockRejectedValue(axiosError)

            await expect(authService.loginWithGoogleToken(googleToken)).rejects.toThrow(
                'Invalid Google token'
            )

            expect(authService.error.value).toBe('Invalid Google token')
            expect(authService.isLoading.value).toBe(false)
        })

        it('should handle 500 server error', async () => {
            const axiosError = {
                response: {
                    status: 500,
                    data: { detail: 'Internal server error' },
                },
            }
            mockAuthApi.login.mockRejectedValue(axiosError)

            await expect(authService.loginWithGoogleToken(googleToken)).rejects.toThrow(
                'Server error. Please check backend logs.'
            )

            expect(authService.error.value).toBe('Server error. Please check backend logs.')
        })

        it('should handle network error without response', async () => {
            const networkError = { message: 'Network Error' }
            mockAuthApi.login.mockRejectedValue(networkError)

            await expect(authService.loginWithGoogleToken(googleToken)).rejects.toThrow('Network Error')

            expect(authService.error.value).toBe('Network Error')
        })

        it('should handle generic errors', async () => {
            mockAuthApi.login.mockRejectedValue(new Error('Unknown error'))

            await expect(authService.loginWithGoogleToken(googleToken)).rejects.toThrow('Unknown error')

            expect(authService.error.value).toBe('Unknown error')
        })

        it('should clear error state on successful login after previous error', async () => {
            // First login fails
            mockAuthApi.login.mockRejectedValueOnce(new Error('First error'))
            await expect(authService.loginWithGoogleToken(googleToken)).rejects.toThrow()
            expect(authService.error.value).toBe('First error')

            // Second login succeeds
            mockAuthApi.login.mockResolvedValueOnce({
                data: {
                    access_token: 'token',
                    refresh_token: 'refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })
            await authService.loginWithGoogleToken(googleToken)

            expect(authService.error.value).toBeNull()
        })

        it('should handle concurrent login attempts', async () => {
            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'token',
                    refresh_token: 'refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            const promises = [
                authService.loginWithGoogleToken('token1'),
                authService.loginWithGoogleToken('token2'),
            ]

            await Promise.all(promises)

            expect(mockAuthApi.login).toHaveBeenCalledTimes(2)
        })
    })

    describe('logout', () => {
        it('should call logout API with refresh token', async () => {
            const refreshToken = 'current-refresh-token'
            localStorageMock.setItem('trader_refresh_token', refreshToken)
            mockAuthApi.logout.mockResolvedValue({})

            await authService.logout()

            expect(mockAuthApi.logout).toHaveBeenCalledTimes(1)
            expect(mockAuthApi.logout).toHaveBeenCalledExactlyOnceWith({
                refresh_token: refreshToken,
            })
            expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
            expect(authService.error.value).toBeNull()
        })

        it('should remove refresh token even if API call fails', async () => {
            localStorageMock.setItem('trader_refresh_token', 'token')
            mockAuthApi.logout.mockRejectedValue(new Error('API error'))

            await authService.logout()

            expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
        })

        it('should handle logout when no refresh token exists', async () => {
            await authService.logout()

            expect(mockAuthApi.logout).not.toHaveBeenCalled()
            expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
        })

        it('should clear error state on logout', async () => {
            authService.error.value = 'Previous error'

            await authService.logout()

            expect(authService.error.value).toBeNull()
        })

        it('should not throw error on API failure', async () => {
            localStorageMock.setItem('trader_refresh_token', 'token')
            mockAuthApi.logout.mockRejectedValue(new Error('Network error'))

            await expect(authService.logout()).resolves.toBeUndefined()
        })
    })

    describe('Refresh Token Management', () => {
        it('should store refresh token in localStorage on login', async () => {
            const refreshToken = 'new-refresh-token'
            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'access',
                    refresh_token: refreshToken,
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            await authService.loginWithGoogleToken('google-token')

            expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token', refreshToken)
        })

        it('should update refresh token in localStorage on refresh', async () => {
            localStorageMock.setItem('trader_refresh_token', 'old-token')
            vi.clearAllMocks()

            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

            const newRefreshToken = 'new-refresh-token'
            mockAuthApi.refreshToken.mockResolvedValue({
                data: {
                    access_token: 'new-access',
                    refresh_token: newRefreshToken,
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            await authService.checkAuthStatus()

            expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token', newRefreshToken)
        })

        it('should remove refresh token on logout', async () => {
            localStorageMock.setItem('trader_refresh_token', 'token')
            mockAuthApi.logout.mockResolvedValue({})

            await authService.logout()

            expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
        })

        it('should retrieve refresh token from localStorage for operations', async () => {
            const refreshToken = 'stored-token'
            localStorageMock.setItem('trader_refresh_token', refreshToken)

            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

            mockAuthApi.refreshToken.mockResolvedValue({
                data: {
                    access_token: 'new',
                    refresh_token: 'new-refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            await authService.checkAuthStatus()

            expect(localStorageMock.getItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.getItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
            expect(mockAuthApi.refreshToken).toHaveBeenCalledTimes(1)
            expect(mockAuthApi.refreshToken).toHaveBeenCalledExactlyOnceWith({
                refresh_token: refreshToken,
            })
        })
    })

    describe('Error State Management', () => {
        it('should clear error on successful operation', async () => {
            authService.error.value = 'Previous error'

            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'token',
                    refresh_token: 'refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            await authService.loginWithGoogleToken('token')

            expect(authService.error.value).toBeNull()
        })

        it('should set error on failed operation', async () => {
            mockAuthApi.login.mockRejectedValue({
                response: {
                    status: 401,
                    data: { detail: 'Authentication failed' },
                },
            })

            await expect(authService.loginWithGoogleToken('token')).rejects.toThrow()

            expect(authService.error.value).toBe('Authentication failed')
        })

        it('should maintain error state across operations until cleared', async () => {
            mockAuthApi.login.mockRejectedValue({ message: 'Login error' })
            await expect(authService.loginWithGoogleToken('token')).rejects.toThrow()

            const errorAfterLogin = authService.error.value
            expect(errorAfterLogin).toBe('Login error')

            // Error persists
            expect(authService.error.value).toBe(errorAfterLogin)
        })
    })

    describe('Loading State Management', () => {
        it('should set loading to true during login', () => {
            mockAuthApi.login.mockImplementation(
                () =>
                    new Promise((resolve) =>
                        setTimeout(() => {
                            resolve({
                                data: {
                                    access_token: 'token',
                                    refresh_token: 'refresh',
                                    token_type: 'bearer',
                                    expires_in: 300,
                                },
                            })
                        }, 50)
                    )
            )

            authService.loginWithGoogleToken('token')

            expect(authService.isLoading.value).toBe(true)
        })

        it('should set loading to false after successful login', async () => {
            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'token',
                    refresh_token: 'refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            await authService.loginWithGoogleToken('token')

            expect(authService.isLoading.value).toBe(false)
        })

        it('should set loading to false after failed login', async () => {
            mockAuthApi.login.mockRejectedValue(new Error('Login failed'))

            await expect(authService.loginWithGoogleToken('token')).rejects.toThrow()

            expect(authService.isLoading.value).toBe(false)
        })

        it('should not affect loading state for checkAuthStatus', async () => {
            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'valid', exp: Date.now() + 300000, error: null },
            })

            const initialLoading = authService.isLoading.value
            await authService.checkAuthStatus()

            expect(authService.isLoading.value).toBe(initialLoading)
        })

        it('should not affect loading state for logout', async () => {
            mockAuthApi.logout.mockResolvedValue({})

            const initialLoading = authService.isLoading.value
            await authService.logout()

            expect(authService.isLoading.value).toBe(initialLoading)
        })
    })

    describe('Integration Scenarios', () => {
        it('should handle full authentication flow', async () => {
            // Login
            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'access',
                    refresh_token: 'refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })
            await authService.loginWithGoogleToken('google-token')

            // Check auth status (valid)
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
        })

        it('should handle token refresh flow', async () => {
            localStorageMock.setItem('trader_refresh_token', 'old-refresh')
            vi.clearAllMocks()

            // Check auth (expired)
            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

            // Refresh succeeds
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
            expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.setItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token', 'new-refresh')
        })

        it('should handle expired token with failed refresh', async () => {
            localStorageMock.setItem('trader_refresh_token', 'invalid-token')

            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'expired', exp: null, error: 'Token expired' },
            })

            mockAuthApi.refreshToken.mockRejectedValue(new Error('Invalid refresh token'))
            mockAuthApi.logout.mockResolvedValue({})

            const result = await authService.checkAuthStatus()

            expect(result).toBe(false)
            expect(localStorageMock.removeItem).toHaveBeenCalledTimes(1)
            expect(localStorageMock.removeItem).toHaveBeenCalledExactlyOnceWith('trader_refresh_token')
        })
    })

    describe('Service Resilience', () => {
        it('should handle rapid successive calls', async () => {
            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'valid', exp: Date.now() + 300000, error: null },
            })

            const calls = Array.from({ length: 10 }, () => authService.checkAuthStatus())

            const results = await Promise.all(calls)

            expect(results.every((r) => r === true)).toBe(true)
            expect(mockApiAdapter.introspectToken).toHaveBeenCalledTimes(10)
        })

        it('should maintain state consistency across concurrent operations', async () => {
            mockAuthApi.login.mockResolvedValue({
                data: {
                    access_token: 'token',
                    refresh_token: 'refresh',
                    token_type: 'bearer',
                    expires_in: 300,
                },
            })

            mockApiAdapter.introspectToken.mockResolvedValue({
                data: { status: 'valid', exp: Date.now() + 300000, error: null },
            })

            await Promise.all([
                authService.loginWithGoogleToken('token1'),
                authService.checkAuthStatus(),
                authService.loginWithGoogleToken('token2'),
            ])

            expect(authService.isLoading.value).toBe(false)
            expect(authService.error.value).toBeNull()
        })
    })
})
