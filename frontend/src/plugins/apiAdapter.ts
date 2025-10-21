// this api adapter wraps the generated openapi client to provide type conversions and a cleaner interface
// do not import generated client models but import frontend ones. For api requests/responses, use the types defined here.
// we need to be able te detect breaking changes in the api, so we keep the types separate.
// for speed and simplicity, we allow typecasting. Not casting of complex objects.
// only simple enum/string/number conversions are done here.
// the best approach is to implement mappers that insure type safety, at runtime (but can be time consuming)
import type {
  PreOrder as PreOrder_Backend,
  QuoteData as QuoteData_Backend,
} from '@clients/trader-client-generated';
import { Configuration, V1Api } from '@clients/trader-client-generated/';
import type {
  AccountMetainfo,
  Bar,
  Brackets,
  CustomInputFieldsValues,
  DatafeedConfiguration,
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
} from '@public/trading_terminal/charting_library';
import { AxiosError } from 'axios';
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

// Type-safe mappers for API responses
// Mappers can import backend types for type safety (not exposed outside this file)
const apiMappers = {
  /**
   * Maps backend QuoteData to frontend discriminated union (QuoteOkData | QuoteErrorData)
   * Uses discriminant property 's' to determine the correct type
   */
  mapQuoteData: (quote: QuoteData_Backend): QuoteData => {
    // Type-safe mapping using backend types
    if (quote.s === 'error') {
      // Map to QuoteErrorData
      return {
        s: 'error' as const,
        n: quote.n,
        v: quote.v,
      }
    } else {
      // Map to QuoteOkData
      return {
        s: 'ok' as const,
        n: quote.n,
        v: {
          ch: quote.v.ch,
          chp: quote.v.chp,
          short_name: quote.v.short_name,
          exchange: quote.v.exchange,
          description: quote.v.description,
          lp: quote.v.lp,
          ask: quote.v.ask,
          bid: quote.v.bid,
          open_price: quote.v.open_price,
          high_price: quote.v.high_price,
          low_price: quote.v.low_price,
          prev_close_price: quote.v.prev_close_price,
          volume: quote.v.volume,
        },
      }
    }
  },

  /**
   * Maps frontend PreOrder to backend PreOrder_Backend
   * Handles enum type conversions for type, side, and stopType
   */
  mapPreOrder: (order: PreOrder): PreOrder_Backend => {
    return {
      symbol: order.symbol,
      type: order.type as unknown as PreOrder_Backend['type'],
      side: order.side as unknown as PreOrder_Backend['side'],
      qty: order.qty,
      limitPrice: order.limitPrice ?? null,
      stopPrice: order.stopPrice ?? null,
      takeProfit: order.takeProfit ?? null,
      stopLoss: order.stopLoss ?? null,
      guaranteedStop: order.guaranteedStop ?? null,
      trailingStopPips: order.trailingStopPips ?? null,
      stopType: order.stopType ? (order.stopType as unknown as PreOrder_Backend['stopType']) : null,
    }
  },
}

/**
 * Decorator for automatic API error handling
 * Wraps async methods with try-catch and delegates errors to handleError method
 *
 * @param endpoint - Static endpoint string or function that computes endpoint from method arguments
 *
 * @example
 * ```typescript
 * @HandleApiError('/health')
 * async getHealthStatus() { ... }
 *
 * @HandleApiError((args) => `/symbols/${args[0]}`)
 * async resolveSymbol(symbol: string) { ... }
 * ```
 */
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
  private rawApi: V1Api
  private apiConfig: Configuration
  constructor() {
    this.apiConfig = new Configuration({
      basePath: import.meta.env.TRADER_API_BASE_PATH || '',
    })
    this.rawApi = new V1Api(
      this.apiConfig
    )
  }

  @ApiErrorHandler('/health')
  async getHealthStatus(): ApiPromise<HealthResponse> {
    const response = await this.rawApi.getHealthStatus()
    return response
  }

  @ApiErrorHandler('/versions')
  async getAPIVersions(): ApiPromise<APIMetadata> {
    return await this.rawApi.getAPIVersions()
  }

  @ApiErrorHandler('/config')
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
  @ApiErrorHandler((...args) => `/symbols/${args[0]}`)
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
  @ApiErrorHandler('/search')
  async searchSymbols(
    userInput: string,
    exchange?: string,
    symbolType?: string,
    maxResults?: number,
  ): ApiPromise<Array<SearchSymbolResultItem>> {
    return await this.rawApi.searchSymbols(userInput, exchange, symbolType, maxResults)
  }
  @ApiErrorHandler((...args) => `/history?symbol=${args[0]}&resolution=${args[1]}`)
  async getBars(
    symbol: string,
    resolution: string,
    fromTime: number,
    toTime: number,
    countBack?: number | null,
  ): ApiPromise<GetBarsResponse> {
    return await this.rawApi.getBars(symbol, resolution, fromTime, toTime, countBack)
  }
  @ApiErrorHandler('/quotes')
  async getQuotes(getQuotesRequest: GetQuotesRequest): ApiPromise<Array<QuoteData>> {
    const response = await this.rawApi.getQuotes(getQuotesRequest)

    return {
      status: response.status,
      data: response.data.map(apiMappers.mapQuoteData),
    }
  }
  @ApiErrorHandler('/orders')
  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const response = await this.rawApi.placeOrder(apiMappers.mapPreOrder(order))

    return {
      status: response.status,
      data: response.data as PlaceOrderResult,
    }
  }
  @ApiErrorHandler('/orders/preview')
  async previewOrder(order: PreOrder): ApiPromise<OrderPreviewResult> {
    const response = await this.rawApi.previewOrder(apiMappers.mapPreOrder(order))

    return {
      status: response.status,
      data: response.data as OrderPreviewResult,
    }
  }

  @ApiErrorHandler((...args) => `/orders/${(args[1] as string | undefined) ?? (args[0] as Order).id}`)
  async modifyOrder(order: Order, confirmId?: string): ApiPromise<void> {
    const orderId = confirmId ?? order.id
    const response = await this.rawApi.modifyOrder(apiMappers.mapPreOrder(order), orderId)

    return {
      status: response.status,
      data: undefined as void,
    }
  }

  @ApiErrorHandler((...args) => `/orders/${args[0]}`)
  async cancelOrder(orderId: string): ApiPromise<void> {
    const response = await this.rawApi.cancelOrder(orderId)

    return {
      status: response.status,
      data: undefined as void,
    }
  }

  @ApiErrorHandler('/orders')
  async getOrders(): ApiPromise<Order[]> {
    const response = await this.rawApi.getOrders()

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
    const response = await this.rawApi.getPositions()

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
    const response = await this.rawApi.getExecutions(symbol)

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
    const response = await this.rawApi.getAccountInfo()

    return {
      status: response.status,
      data: response.data as AccountMetainfo,
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async closePosition(_positionId: string, _amount?: number): ApiPromise<void> {
    throw new ApiError('closePosition not implemented in backend API', 501, '/positions/close')
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async editPositionBrackets(_positionId: string, _brackets: Brackets, _customFields?: CustomInputFieldsValues): ApiPromise<void> {
    throw new ApiError('editPositionBrackets not implemented in backend API', 501, '/positions/brackets')
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async leverageInfo(_leverageInfoParams: LeverageInfoParams): ApiPromise<LeverageInfo> {
    throw new ApiError('leverageInfo not implemented in backend API', 501, '/leverage/info')
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async setLeverage(_leverageSetParams: LeverageSetParams): ApiPromise<LeverageSetResult> {
    throw new ApiError('setLeverage not implemented in backend API', 501, '/leverage/set')
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async previewLeverage(_leverageSetParams: LeverageSetParams): ApiPromise<LeveragePreviewResult> {
    throw new ApiError('previewLeverage not implemented in backend API', 501, '/leverage/preview')
  }
}
