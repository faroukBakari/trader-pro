import { Configuration, V1Api } from '@clients/trader-client-generated/'

export interface HealthResponse {
  status: string
  message?: string
  timestamp: string
  api_version: string
  version_info: object
}

export interface VersionInfo {
  version: string
  release_date: string
  status: string
  breaking_changes?: string[]
  deprecation_notice?: string | null
  sunset_date?: string | null
}

export interface APIMetadata {
  current_version: string
  available_versions: VersionInfo[]
  documentation_url: string
  support_contact: string
}

export class ApiAdapter {
  rawApi: V1Api
  constructor() {
    this.rawApi = new V1Api(
      new Configuration({
        basePath: import.meta.env.TRADER_API_BASE_PATH || '',
      }),
    )
  }

  async getHealthStatus(): Promise<{ status: number; data: HealthResponse }> {
    return this.rawApi.getHealthStatus()
  }

  async getAPIVersions(): Promise<{ status: number; data: APIMetadata }> {
    return this.rawApi.getAPIVersions()
  }
}
