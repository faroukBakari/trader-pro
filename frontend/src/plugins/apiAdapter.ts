import { Configuration, V1Api } from '@clients/trader-client-generated/';
import type {
  Bar,
  DatafeedConfiguration,
  LibrarySymbolInfo,
  QuoteData,
  SearchSymbolResultItem
} from '@public/trading_terminal/charting_library';
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

export interface GetBarsResponse {
  bars: Array<Bar>
  no_data?: boolean
}

export interface GetQuotesRequest {
  symbols: string[]
}

export type ApiResponse<T> = { status: number; data: T }
type ApiPromise<T> = Promise<ApiResponse<T>>

export class ApiAdapter {
  rawApi: V1Api
  constructor() {
    this.rawApi = new V1Api(
      new Configuration({
        basePath: import.meta.env.TRADER_API_BASE_PATH || '',
      }),
    )
  }

  async getHealthStatus(): ApiPromise<HealthResponse> {
    const response = await this.rawApi.getHealthStatus()
    return response
  }

  async getAPIVersions(): ApiPromise<APIMetadata> {
    return this.rawApi.getAPIVersions()
  }

  async getConfig(): ApiPromise<DatafeedConfiguration> {
    const response = await this.rawApi.getConfig()
    return {
      status: response.status,
      data: {
        ...response.data,
        supported_resolutions: response.data.supported_resolutions as unknown as DatafeedConfiguration['supported_resolutions'],
      }
    }
  }
  async resolveSymbol(symbol: string): ApiPromise<LibrarySymbolInfo> {
    const response = await this.rawApi.resolveSymbol(symbol)
    return {
      status: response.status,
      data: {
        ...response.data,
        timezone: response.data.timezone as unknown as LibrarySymbolInfo['timezone'],
        format: response.data.format as unknown as LibrarySymbolInfo['format'],
        supported_resolutions: response.data.supported_resolutions as unknown as DatafeedConfiguration['supported_resolutions'],
      }
    }
  }
  searchSymbols(
    userInput: string,
    exchange?: string,
    symbolType?: string,
    maxResults?: number,
  ): ApiPromise<Array<SearchSymbolResultItem>> {
    return this.rawApi.searchSymbols(userInput, exchange, symbolType, maxResults)
  }
  getBars(
    symbol: string,
    resolution: string,
    fromTime: number,
    toTime: number,
    countBack?: number | null,
  ): ApiPromise<GetBarsResponse> {
    return this.rawApi.getBars(symbol, resolution, fromTime, toTime, countBack)
  }
  async getQuotes(getQuotesRequest: GetQuotesRequest): ApiPromise<Array<QuoteData>> {
    const response = await this.rawApi.getQuotes(getQuotesRequest)
    return {
      status: response.status,
      data: response.data.map(quote => (quote as unknown as QuoteData)),
    }
  }
}
