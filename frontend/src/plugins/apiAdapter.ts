// this api adapter wraps the generated openapi client to provide type conversions and a cleaner interface
// do not import generated client models but import frontend ones. For api requests/responses, use the types defined here.
// we need to be able te detect breaking changes in the api, so we keep the types separate.
// for speed and simplicity, we allow typecasting. Not casting of complex objects.
// only simple enum/string/number conversions are done here.
// the best approach is to implement mappers that insure type safety, at runtime (but can be time consuming)

// Per-module-version API clients (versionned-microservice-ready architecture)
import {
  AuthApi,
  Configuration as AuthConfigurationV1
} from '@clients/trader-client-auth_v1';
import {
  BrokerApi,
  Configuration as BrokerConfigurationV1
} from '@clients/trader-client-broker_v1';
import {
  DatafeedApi,
  Configuration as DatafeedConfigurationV1
} from '@clients/trader-client-datafeed_v1';

import type { ModuleInfo } from '@/types/apiStatus';
import type {
  AccountMetainfo,
  Bar,
  Brackets,
  CustomInputFieldsValues,
  Execution,
  LeverageInfo,
  LeverageInfoParams,
  LeveragePreviewResult,
  LeverageSetParams,
  LeverageSetResult,
  LibrarySymbolInfo,
  Order,
  OrderPreviewResult,
  PlaceOrderResult,
  Position,
  PreOrder,
  QuoteData,
  SearchSymbolResultItem,
  DatafeedConfiguration as TradingViewDatafeedConfiguration,
} from '@public/trading_terminal/charting_library';
import { AxiosError } from 'axios';
import {
  mapPreOrder,
  mapQuoteData,
} from './mappers';
import { WsAdapter } from './wsAdapter';

// Import backend types for health and versioning

// Frontend interface types (can differ from backend)
export interface HealthResponse {
  status: string
  message?: string
  timestamp: string
  module_name: string
  api_version: string
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
  available_versions: { [key: string]: VersionInfo }
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

export interface TokenIntrospectResponse {
  status: 'valid' | 'expired' | 'revoked' | 'error'
  exp: number | null
  error: string | null
}

export type ApiResponse<T> = { status: number; data: T }
export type ApiPromise<T> = Promise<ApiResponse<T>>

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number,
    public readonly endpoint?: string,
    public readonly originalError?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function ApiErrorHandler(endpoint: string | ((...args: unknown[]) => string)) {
  return function (
    _target: unknown,
    _propertyKey: string,
    descriptor: PropertyDescriptor
  ): PropertyDescriptor {
    const originalMethod = descriptor.value as (...args: unknown[]) => Promise<unknown>

    descriptor.value = async function (this: { handleError: (error: unknown, endpoint: string) => never }, ...args: unknown[]) {
      try {
        return await originalMethod.apply(this, args)
      } catch (error) {
        const endpointStr = typeof endpoint === 'function' ? endpoint(...args) : endpoint
        if (error instanceof AxiosError) {
          if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
            throw new ApiError(
              `Network error: Unable to connect to the API server. Please ensure the backend is running and accessible.`,
              undefined,
              endpointStr,
              error,
            )
          }

          if (error.response) {
            const status = error.response.status
            const data = error.response.data as { detail?: string; message?: string }
            const message = data?.detail || data?.message || error.message

            throw new ApiError(
              `API error (${status}): ${message}`,
              status,
              endpointStr,
              error,
            )
          }

          if (error.request) {
            throw new ApiError(
              `No response received from API server at ${endpointStr}: ${error.message}`,
              undefined,
              endpointStr,
              error,
            )
          }
        }

        throw new ApiError(
          `Unexpected error during API call to ${endpointStr}: ${error instanceof Error ? error.message : String(error)}`,
          undefined,
          endpointStr,
          error,
        )
      }
    }

    return descriptor
  }
}

export class ApiAdapter {
  private static instance: ApiAdapter | null = null

  private brokerApi!: BrokerApi
  private datafeedApi!: DatafeedApi
  private authApi!: AuthApi
  private brokerConfig!: BrokerConfigurationV1
  private datafeedConfig!: DatafeedConfigurationV1
  private authConfig!: AuthConfigurationV1

  constructor() {
    if (ApiAdapter.instance) {
      return ApiAdapter.instance
    }

    const ApiV1BasePath = (import.meta.env.VITE_TRADER_API_BASE_PATH || '') + "/v1"

    // Initialize per-module configurations
    // In multi-process mode, these could point to different services:
    // broker: http://broker-service:8001
    // datafeed: http://datafeed-service:8002
    // withCredentials: true enables cookies to be sent with cross-origin requests
    this.brokerConfig = new BrokerConfigurationV1({
      basePath: ApiV1BasePath + '/broker',
      // @ts-expect-error - withCredentials not in type definition but supported by axios
      withCredentials: true,
    })
    this.datafeedConfig = new DatafeedConfigurationV1({
      basePath: ApiV1BasePath + '/datafeed',
      // @ts-expect-error - withCredentials not in type definition but supported by axios
      withCredentials: true,
    })
    this.authConfig = new AuthConfigurationV1({
      basePath: ApiV1BasePath + '/auth',
      // @ts-expect-error - withCredentials not in type definition but supported by axios
      withCredentials: true,
    })

    // Initialize per-module API clients
    this.brokerApi = new BrokerApi(this.brokerConfig)
    this.datafeedApi = new DatafeedApi(this.datafeedConfig)
    this.authApi = new AuthApi(this.authConfig)

    ApiAdapter.instance = this
  }

  static getInstance(): ApiAdapter {
    if (!ApiAdapter.instance) {
      ApiAdapter.instance = new ApiAdapter()
    }
    return ApiAdapter.instance
  }

  /**
   * Get list of integrated modules with their configuration.
   *
   * IMPORTANT: When adding a new module, update:
   * 1. This method's return array
   * 2. WsAdapter.getModules() if module has WebSocket support
   * 3. Switch cases in getModuleHealth() and getModuleVersions()
   *
   * @private
   * @returns Array of module information including docs URLs and WebSocket support
   */
  private getIntegratedModules(): ModuleInfo[] {
    const wsModules = WsAdapter.getModules()

    return [
      {
        name: 'broker',
        displayName: 'Broker',
        docsUrl: '/api/v1/broker/docs',
        hasWebSocket: wsModules.includes('broker'),
      },
      {
        name: 'datafeed',
        displayName: 'Datafeed',
        docsUrl: '/api/v1/datafeed/docs',
        hasWebSocket: wsModules.includes('datafeed'),
      },
    ]
  }

  /**
   * Get API client for specific module
   * @private
   * @param moduleName - Name of the module ('broker' or 'datafeed')
   * @returns API client instance for the module
   */
  private getModuleApi(moduleName: string): {
    getHealthStatus: () => ApiPromise<HealthResponse>,
    getAPIVersions: () => ApiPromise<APIMetadata>
  } {
    switch (moduleName) {
      case 'broker':
        return this.brokerApi
      case 'datafeed':
        return this.datafeedApi
      default:
        throw new Error(`Unknown module: ${moduleName}`)
    }
  }

  @ApiErrorHandler('/health')
  async getHealthStatus(): ApiPromise<HealthResponse> {
    // Health check from broker module (per-module health via APIRouterInterface)
    const response = await this.brokerApi.getHealthStatus()
    // Map backend HealthResponse to frontend HealthResponse
    return {
      status: response.status,
      data: {
        status: response.data.status,
        timestamp: response.data.timestamp,
        module_name: response.data.module_name,
        api_version: response.data.api_version,
        message: response.data.message,
      }
    }
  }

  @ApiErrorHandler('/versions')
  async getAPIVersions(): ApiPromise<APIMetadata> {
    // Version info from broker module (per-module versioning via APIRouterInterface)
    const response = await this.brokerApi.getAPIVersions()
    // Backend returns { [key: string]: VersionInfo }, frontend expects same
    return response
  }

  // NEW: Multi-module methods

  @ApiErrorHandler((...args: unknown[]) => `/${args[0]}/health`)
  async getModuleHealth(moduleName: string): ApiPromise<HealthResponse> {
    const api = this.getModuleApi(moduleName)
    const response = await api.getHealthStatus()
    return {
      status: response.status,
      data: {
        status: response.data.status,
        timestamp: response.data.timestamp,
        module_name: response.data.module_name,
        api_version: response.data.api_version,
        message: response.data.message,
      }
    }
  }

  @ApiErrorHandler('/health/all')
  async getAllModulesHealth(): ApiPromise<Map<string, import('@/types/apiStatus').ModuleHealth>> {
    const modules = this.getIntegratedModules()

    const healthChecks = await Promise.all(
      modules.map(async (module) => {
        const start = Date.now()
        try {
          const response = await this.getModuleHealth(module.name)
          const moduleHealth: import('@/types/apiStatus').ModuleHealth = {
            moduleName: module.name,
            health: response.data,
            loading: false,
            error: null,
            responseTime: Date.now() - start,
          }
          return [module.name, moduleHealth] as [string, import('@/types/apiStatus').ModuleHealth]
        } catch (error) {
          const moduleHealth: import('@/types/apiStatus').ModuleHealth = {
            moduleName: module.name,
            health: null,
            loading: false,
            error: error instanceof Error ? error.message : String(error),
            responseTime: Date.now() - start,
          }
          return [module.name, moduleHealth] as [string, import('@/types/apiStatus').ModuleHealth]
        }
      })
    )

    return {
      status: 200,
      data: new Map(healthChecks),
    }
  }

  @ApiErrorHandler((...args: unknown[]) => `/${args[0]}/versions`)
  async getModuleVersions(moduleName: string): ApiPromise<APIMetadata> {
    const api = this.getModuleApi(moduleName)
    return await api.getAPIVersions()
  }

  @ApiErrorHandler('/versions/all')
  async getAllModulesVersions(): ApiPromise<Map<string, import('@/types/apiStatus').ModuleVersions>> {
    const modules = this.getIntegratedModules()

    const versionChecks = await Promise.all(
      modules.map(async (module) => {
        try {
          const response = await this.getModuleVersions(module.name)
          const moduleVersions: import('@/types/apiStatus').ModuleVersions = {
            moduleName: module.name,
            versions: response.data,
            loading: false,
            error: null,
          }
          return [module.name, moduleVersions] as [string, import('@/types/apiStatus').ModuleVersions]
        } catch (error) {
          const moduleVersions: import('@/types/apiStatus').ModuleVersions = {
            moduleName: module.name,
            versions: null,
            loading: false,
            error: error instanceof Error ? error.message : String(error),
          }
          return [module.name, moduleVersions] as [string, import('@/types/apiStatus').ModuleVersions]
        }
      })
    )

    return {
      status: 200,
      data: new Map(versionChecks),
    }
  }

  // Auth module endpoints
  @ApiErrorHandler('/introspect')
  async introspectToken(): ApiPromise<TokenIntrospectResponse> {
    const response = await this.authApi.introspectToken()
    return {
      status: response.status,
      data: {
        status: response.data.status as TokenIntrospectResponse['status'],
        exp: response.data.exp ?? null,
        error: response.data.error ?? null,
      }
    }
  }

  @ApiErrorHandler('/config')
  async getConfig(): ApiPromise<TradingViewDatafeedConfiguration> {
    const response = await this.datafeedApi.getConfig()
    return {
      status: response.status,
      data: {
        ...response.data,
        supported_resolutions: response.data.supported_resolutions as unknown as TradingViewDatafeedConfiguration['supported_resolutions'],
      }
    }
  }
  // Datafeed module endpoints
  @ApiErrorHandler((...args) => `/symbols/${args[0]}`)
  async resolveSymbol(symbol: string): ApiPromise<LibrarySymbolInfo> {
    const response = await this.datafeedApi.resolveSymbol(symbol)
    return {
      status: response.status,
      data: {
        ...response.data,
        timezone: response.data.timezone as unknown as LibrarySymbolInfo['timezone'],
        format: response.data.format as unknown as LibrarySymbolInfo['format'],
        supported_resolutions: response.data.supported_resolutions as unknown as TradingViewDatafeedConfiguration['supported_resolutions'],
      }
    }
  }
  @ApiErrorHandler('/search')
  async searchSymbols(
    userInput: string,
    exchange?: string,
    symbolType?: string,
    maxResults?: number,
  ): ApiPromise<Array<SearchSymbolResultItem>> {
    return await this.datafeedApi.searchSymbols(userInput, exchange, symbolType, maxResults)
  }
  @ApiErrorHandler((...args) => `/history?symbol=${args[0]}&resolution=${args[1]}`)
  async getBars(
    symbol: string,
    resolution: string,
    fromTime: number,
    toTime: number,
    countBack?: number | null,
  ): ApiPromise<GetBarsResponse> {
    return await this.datafeedApi.getBars(symbol, resolution, fromTime, toTime, countBack)
  }
  @ApiErrorHandler('/quotes')
  async getQuotes(getQuotesRequest: GetQuotesRequest): ApiPromise<Array<QuoteData>> {
    const response = await this.datafeedApi.getQuotes(getQuotesRequest)

    return {
      status: response.status,
      data: response.data.map(mapQuoteData),
    }
  }

  // Broker module endpoints
  @ApiErrorHandler('/orders')
  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const response = await this.brokerApi.placeOrder(mapPreOrder(order))

    return {
      status: response.status,
      data: response.data as PlaceOrderResult,
    }
  }
  @ApiErrorHandler('/orders/preview')
  async previewOrder(order: PreOrder): ApiPromise<OrderPreviewResult> {
    const response = await this.brokerApi.previewOrder(mapPreOrder(order))

    return {
      status: response.status,
      data: response.data as OrderPreviewResult,
    }
  }

  @ApiErrorHandler((...args) => `/orders/${(args[1] as string | undefined) ?? (args[0] as Order).id}`)
  async modifyOrder(order: Order, confirmId?: string): ApiPromise<void> {
    const orderId = confirmId ?? order.id
    const response = await this.brokerApi.modifyOrder(mapPreOrder(order), orderId)

    return {
      status: response.status,
      data: undefined as void,
    }
  }

  @ApiErrorHandler((...args) => `/orders/${args[0]}`)
  async cancelOrder(orderId: string): ApiPromise<void> {
    const response = await this.brokerApi.cancelOrder(orderId)

    return {
      status: response.status,
      data: undefined as void,
    }
  }

  @ApiErrorHandler('/orders')
  async getOrders(): ApiPromise<Order[]> {
    const response = await this.brokerApi.getOrders()

    // Note: Backend returns PlacedOrder[], frontend expects Order[] (union type)
    // Order is a union including BracketOrder which requires parentId/parentType
    // PlacedOrder doesn't have these fields - this is a structural mismatch
    // Cannot map individual fields due to missing required properties in union type
    return {
      status: response.status,
      data: response.data as unknown as Order[],
    }
  }

  @ApiErrorHandler('/positions')
  async getPositions(): ApiPromise<Position[]> {
    const response = await this.brokerApi.getPositions()

    return {
      status: response.status,
      data: response.data.map(position => ({
        ...position,
        side: position.side as unknown as Position['side'],
      })),
    }
  }

  @ApiErrorHandler((...args) => `/executions?symbol=${args[0]}`)
  async getExecutions(symbol: string): ApiPromise<Execution[]> {
    const response = await this.brokerApi.getExecutions(symbol)

    return {
      status: response.status,
      data: response.data.map(execution => ({
        ...execution,
        side: execution.side as unknown as Execution['side'],
      })),
    }
  }

  @ApiErrorHandler('/accounts')
  async getAccountInfo(): ApiPromise<AccountMetainfo> {
    const response = await this.brokerApi.getAccountInfo()

    return {
      status: response.status,
      data: response.data as AccountMetainfo,
    }
  }

  @ApiErrorHandler((...args) => `/positions/${args[0]}`)
  async closePosition(positionId: string, amount?: number): ApiPromise<void> {
    const response = await this.brokerApi.closePosition(positionId, amount)
    return {
      status: response.status,
      data: undefined as void,
    }
  }

  @ApiErrorHandler((...args) => `/positions/${args[0]}/brackets`)
  async editPositionBrackets(positionId: string, brackets: Brackets, customFields?: CustomInputFieldsValues): ApiPromise<void> {
    const response = await this.brokerApi.editPositionBrackets(
      {
        brackets: {
          stopLoss: brackets.stopLoss ?? null,
          takeProfit: brackets.takeProfit ?? null,
          guaranteedStop: brackets.guaranteedStop ?? null,
          trailingStopPips: brackets.trailingStopPips ?? null,
        },
        customFields: customFields ?? null,
      },
      positionId
    )
    return {
      status: response.status,
      data: undefined as void,
    }
  }

  @ApiErrorHandler("/leverage/info")
  async leverageInfo(leverageInfoParams: LeverageInfoParams): ApiPromise<LeverageInfo> {
    const response = await this.brokerApi.leverageInfo(
      leverageInfoParams.symbol,
      leverageInfoParams.orderType as unknown as number,
      leverageInfoParams.side as unknown as number
    )
    return {
      status: response.status,
      data: response.data as LeverageInfo,
    }
  }

  @ApiErrorHandler("/leverage/set")
  async setLeverage(leverageSetParams: LeverageSetParams): ApiPromise<LeverageSetResult> {
    const response = await this.brokerApi.setLeverage({
      symbol: leverageSetParams.symbol,
      orderType: leverageSetParams.orderType as unknown as number,
      side: leverageSetParams.side as unknown as number,
      leverage: leverageSetParams.leverage,
      customFields: leverageSetParams.customFields ?? null,
    })
    return {
      status: response.status,
      data: response.data as LeverageSetResult,
    }
  }

  @ApiErrorHandler("/leverage/preview")
  async previewLeverage(leverageSetParams: LeverageSetParams): ApiPromise<LeveragePreviewResult> {
    const response = await this.brokerApi.previewLeverage({
      symbol: leverageSetParams.symbol,
      orderType: leverageSetParams.orderType as unknown as number,
      side: leverageSetParams.side as unknown as number,
      leverage: leverageSetParams.leverage,
      customFields: leverageSetParams.customFields ?? null,
    })
    return {
      status: response.status,
      data: response.data as LeveragePreviewResult,
    }
  }
}
