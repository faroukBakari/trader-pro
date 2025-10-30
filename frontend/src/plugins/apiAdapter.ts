// this api adapter wraps the generated openapi client to provide type conversions and a cleaner interface
// do not import generated client models but import frontend ones. For api requests/responses, use the types defined here.
// we need to be able te detect breaking changes in the api, so we keep the types separate.
// for speed and simplicity, we allow typecasting. Not casting of complex objects.
// only simple enum/string/number conversions are done here.
// the best approach is to implement mappers that insure type safety, at runtime (but can be time consuming)

// Per-module API clients (microservice-ready architecture)
import {
  Configuration as BrokerConfiguration,
  V1Api as BrokerV1Api
} from '@clients/trader-client-broker';
import {
  Configuration as DatafeedConfiguration,
  V1Api as DatafeedV1Api
} from '@clients/trader-client-datafeed';

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
  private brokerApi: BrokerV1Api
  private datafeedApi: DatafeedV1Api
  private brokerConfig: BrokerConfiguration
  private datafeedConfig: DatafeedConfiguration

  constructor() {
    const basePath = import.meta.env.TRADER_API_BASE_PATH || ''

    // Initialize per-module configurations
    // In multi-process mode, these could point to different services:
    // broker: http://broker-service:8001
    // datafeed: http://datafeed-service:8002
    this.brokerConfig = new BrokerConfiguration({ basePath })
    this.datafeedConfig = new DatafeedConfiguration({ basePath })

    // Initialize per-module API clients
    this.brokerApi = new BrokerV1Api(this.brokerConfig)
    this.datafeedApi = new DatafeedV1Api(this.datafeedConfig)
  }

  @ApiErrorHandler('/health')
  async getHealthStatus(): ApiPromise<HealthResponse> {
    // TODO: In future, aggregate health from both broker and datafeed modules
    const response = await this.brokerApi.getHealthStatus()
    return response
  }

  @ApiErrorHandler('/versions')
  async getAPIVersions(): ApiPromise<APIMetadata> {
    // TODO: In future, aggregate versions from both broker and datafeed modules
    return await this.brokerApi.getAPIVersions()
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
