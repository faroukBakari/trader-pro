import {
  AuthApi,
  Configuration,
  type GoogleLoginRequest,
  type LogoutRequest,
  type RefreshRequest,
  type User,
} from '@/clients_generated/trader-client-auth_v1'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useTokenClient, type CredentialResponse } from 'vue3-google-signin'

const REFRESH_TOKEN_KEY = 'trader_refresh_token'
const TOKEN_REFRESH_INTERVAL = 4 * 60 * 1000

export const useAuthStore = defineStore('auth', () => {
  const refreshToken = ref<string | null>(null)
  const user = ref<User | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isGoogleReady = ref(false)

  const authApi = new AuthApi(new Configuration({
    basePath: '/api/v1/auth',
    // @ts-expect-error - withCredentials not in type definition but supported by axios
    withCredentials: true,
  }))
  let refreshTimeoutId: ReturnType<typeof setTimeout> | null = null
  let googleLogin: (() => void) | null = null

  // Lazy initialization of Google client (called from LoginView component)
  function initializeGoogleClient() {
    if (googleLogin) return // Already initialized

    const { isReady, login } = useTokenClient({
      onSuccess: async (response: CredentialResponse) => {
        isLoading.value = true
        error.value = null
        try {
          const loginRequest: GoogleLoginRequest = {
            google_token: response.credential!,
          }
          const result = await authApi.login(loginRequest)

          refreshToken.value = result.data.refresh_token
          localStorage.setItem(REFRESH_TOKEN_KEY, result.data.refresh_token)

          // Cookie-based auth: no need to pass accessToken, cookies sent automatically
          const userResult = await authApi.getCurrentUser()
          user.value = userResult.data

          scheduleTokenRefresh()
        } catch (err: unknown) {
          const errorMessage = err instanceof Error ? err.message : 'Login failed'
          error.value = errorMessage
          console.error('Backend login failed:', err)
        } finally {
          isLoading.value = false
        }
      },
      onError: () => {
        error.value = 'Google sign-in failed'
        console.error('Google sign-in failed')
        isLoading.value = false
      },
      scope: 'openid email profile',
    })

    googleLogin = login
    isGoogleReady.value = isReady.value

    // Watch for isReady changes
    watch(isReady, (ready: boolean) => {
      isGoogleReady.value = ready
    })
  }

  const isAuthenticated = computed(() => !!user.value)

  function scheduleTokenRefresh() {
    if (refreshTimeoutId) {
      clearTimeout(refreshTimeoutId)
    }

    refreshTimeoutId = setTimeout(async () => {
      await refreshAccessToken()
    }, TOKEN_REFRESH_INTERVAL)
  }

  async function refreshAccessToken(): Promise<boolean> {
    const currentRefreshToken = refreshToken.value || localStorage.getItem(REFRESH_TOKEN_KEY)

    if (!currentRefreshToken) {
      return false
    }

    try {
      const refreshRequest: RefreshRequest = {
        refresh_token: currentRefreshToken,
      }
      const result = await authApi.refreshToken(refreshRequest)

      refreshToken.value = result.data.refresh_token
      localStorage.setItem(REFRESH_TOKEN_KEY, result.data.refresh_token)

      // Cookie-based auth: no need to pass accessToken, cookies sent automatically
      const userResult = await authApi.getCurrentUser()
      user.value = userResult.data

      scheduleTokenRefresh()

      return true
    } catch (err: unknown) {
      console.error('Token refresh failed:', err)
      await logout()
      return false
    }
  }

  async function handleGoogleSignIn() {
    initializeGoogleClient() // Ensure Google client is initialized
    error.value = null
    isLoading.value = true
    try {
      if (googleLogin) {
        googleLogin()
      } else {
        throw new Error('Google client not initialized')
      }
    } catch {
      error.value = 'Failed to initiate Google sign-in'
      isLoading.value = false
    }
  }

  async function loginWithGoogleToken(googleToken: string) {
    isLoading.value = true
    error.value = null
    try {
      console.log('Attempting login with Google token...')
      const loginRequest: GoogleLoginRequest = {
        google_token: googleToken,
      }
      const result = await authApi.login(loginRequest)

      console.log('Login successful, setting tokens...')
      refreshToken.value = result.data.refresh_token
      localStorage.setItem(REFRESH_TOKEN_KEY, result.data.refresh_token)

      console.log('Fetching user data...')
      // Cookie-based auth: no need to pass accessToken, cookies sent automatically
      const userResult = await authApi.getCurrentUser()
      user.value = userResult.data

      console.log('Login complete, user:', user.value?.email)
      scheduleTokenRefresh()
    } catch (err: unknown) {
      console.error('Backend login failed:', err)

      // Enhanced error handling
      let errorMessage = 'Login failed'
      if (err && typeof err === 'object') {
        const axiosError = err as { response?: { status?: number; data?: { detail?: string; message?: string } }; message?: string }
        if (axiosError.response) {
          const status = axiosError.response.status
          const detail = axiosError.response.data?.detail || axiosError.response.data?.message

          if (status === 401) {
            errorMessage = detail || 'Invalid Google token. Please try again.'
          } else if (status === 500) {
            errorMessage = 'Server error. Please check backend logs.'
            console.error('Backend 500 error:', axiosError.response.data)
          } else {
            errorMessage = detail || `Request failed with status ${status}`
          }
        } else if (axiosError.message) {
          errorMessage = axiosError.message
        }
      } else if (err instanceof Error) {
        errorMessage = err.message
      }

      error.value = errorMessage
      throw new Error(errorMessage)
    } finally {
      isLoading.value = false
    }
  }

  async function logout() {
    const currentRefreshToken = refreshToken.value || localStorage.getItem(REFRESH_TOKEN_KEY)

    if (currentRefreshToken) {
      try {
        const logoutRequest: LogoutRequest = {
          refresh_token: currentRefreshToken,
        }
        await authApi.logout(logoutRequest)
      } catch {
        console.error('Logout API call failed')
      }
    }

    refreshToken.value = null
    user.value = null
    error.value = null

    localStorage.removeItem(REFRESH_TOKEN_KEY)

    if (refreshTimeoutId) {
      clearTimeout(refreshTimeoutId)
      refreshTimeoutId = null
    }
  }

  async function initAuth(): Promise<boolean> {
    const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

    if (!storedRefreshToken) {
      return false
    }

    refreshToken.value = storedRefreshToken
    return await refreshAccessToken()
  }

  function handleStorageChange(event: StorageEvent) {
    if (event.key === REFRESH_TOKEN_KEY) {
      if (!event.newValue && refreshToken.value) {
        logout()
      }
    }
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('storage', handleStorageChange)
  }

  return {
    refreshToken,
    user,
    isLoading,
    error,
    isAuthenticated,
    isGoogleReady,
    handleGoogleSignIn,
    loginWithGoogleToken,
    refreshAccessToken,
    logout,
    initAuth,
    initializeGoogleClient,
  }
})
