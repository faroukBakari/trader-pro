// API service for connecting to the FastAPI backend
// Using proxy configuration - requests to /api/* will be forwarded to backend
const API_BASE_URL = ''

export interface HealthResponse {
  status: string
  message: string
  timestamp: string
  api_version: string
  version_info: {
    version: string
    release_date: string
    status: string
    deprecation_notice: string | null
  }
}

export interface ApiVersion {
  version: string
  status: string
  deprecated?: boolean
  sunset_date?: string
}

export interface ApiVersionsResponse {
  versions: ApiVersion[]
  current_version: string
}

class ApiService {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error)
      throw error
    }
  }

  // Health check endpoint
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/v1/health')
  }

  // Get API versions
  async getVersions(): Promise<ApiVersionsResponse> {
    return this.request<ApiVersionsResponse>('/api/v1/versions')
  }

  // Get current API version
  async getCurrentVersion(): Promise<ApiVersion> {
    return this.request<ApiVersion>('/api/v1/versions/current')
  }
}

export const apiService = new ApiService()
export default ApiService
