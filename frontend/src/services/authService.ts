import {
  AuthApi,
  Configuration,
  type GoogleLoginRequest,
  type LogoutRequest,
  type RefreshRequest,
} from '@/clients_generated/trader-client-auth_v1'
import { ApiAdapter } from '@/plugins/apiAdapter'
import { ref, type Ref } from 'vue'

const REFRESH_TOKEN_KEY = 'trader_refresh_token'

export interface AuthServiceState {
  isLoading: Ref<boolean>
  error: Ref<string | null>
}

export interface AuthServiceMethods {
  checkAuthStatus: () => Promise<boolean>
  loginWithGoogleToken: (googleToken: string) => Promise<void>
  logout: () => Promise<void>
}

export type AuthService = AuthServiceState & AuthServiceMethods

class AuthServiceImpl implements AuthService {
  private authApi: AuthApi
  private apiAdapter: ApiAdapter

  public isLoading: Ref<boolean>
  public error: Ref<string | null>

  constructor() {
    this.isLoading = ref(false)
    this.error = ref<string | null>(null)

    this.authApi = new AuthApi(
      new Configuration({
        basePath: '/api/v1/auth',
        // @ts-expect-error - withCredentials not in type definition but supported by axios
        withCredentials: true,
      }),
    )

    this.apiAdapter = ApiAdapter.getInstance()
  }

  public async checkAuthStatus(): Promise<boolean> {
    try {
      const result = await this.apiAdapter.introspectToken()

      if (result.data.status === 'valid') {
        return true
      } else {
        console.log('Access token expired, attempting refresh...')
        const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

        if (refreshToken) {
          const refreshed = await this.refreshAccessToken(refreshToken)
          return refreshed
        } else {
          return false
        }
      }

    } catch {
      return false
    }
  }

  private async refreshAccessToken(refreshToken: string): Promise<boolean> {
    try {
      console.log('Refreshing access token...')
      const refreshRequest: RefreshRequest = {
        refresh_token: refreshToken,
      }
      const result = await this.authApi.refreshToken(refreshRequest)

      console.log('Token refresh successful, storing new refresh token...')
      localStorage.setItem(REFRESH_TOKEN_KEY, result.data.refresh_token)

      console.log('Token refresh complete')
      return true
    } catch (err: unknown) {
      console.error('Token refresh failed:', err)
      await this.logout()
      return false
    }
  }

  public async loginWithGoogleToken(googleToken: string): Promise<void> {
    this.isLoading.value = true
    this.error.value = null
    try {
      console.log('Attempting login with Google token...')
      const loginRequest: GoogleLoginRequest = {
        google_token: googleToken,
      }
      const result = await this.authApi.login(loginRequest)

      console.log('Login successful, storing refresh token...')
      localStorage.setItem(REFRESH_TOKEN_KEY, result.data.refresh_token)

      console.log('Login complete')
    } catch (err: unknown) {
      console.error('Backend login failed:', err)

      let errorMessage = 'Login failed'
      if (err && typeof err === 'object') {
        const axiosError = err as {
          response?: { status?: number; data?: { detail?: string; message?: string } }
          message?: string
        }
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

      this.error.value = errorMessage
      throw new Error(errorMessage)
    } finally {
      this.isLoading.value = false
    }
  }

  public async logout(): Promise<void> {
    const currentRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

    if (currentRefreshToken) {
      try {
        const logoutRequest: LogoutRequest = {
          refresh_token: currentRefreshToken,
        }
        await this.authApi.logout(logoutRequest)
      } catch {
        console.error('Logout API call failed')
      }
    }

    this.error.value = null
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

let authServiceInstance: AuthService | null = null

export function createAuthService(): AuthService {
  if (!authServiceInstance) {
    authServiceInstance = new AuthServiceImpl()
  }
  return authServiceInstance
}

export function useAuthService(): AuthService {
  if (!authServiceInstance) {
    authServiceInstance = new AuthServiceImpl()
  }
  return authServiceInstance
}
