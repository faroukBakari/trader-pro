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
  DatafeedConfiguration,
  Execution,
  LibrarySymbolInfo,
  Order,
  PlaceOrderResult,
  Position,
  PreOrder,
  QuoteData,
  SearchSymbolResultItem,
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
export type ApiPromise<T> = Promise<ApiResponse<T>>

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
      data: response.data.map(apiMappers.mapQuoteData),
    }
  }
  async placeOrder(order: PreOrder): ApiPromise<PlaceOrderResult> {
    const response = await this.rawApi.placeOrder(apiMappers.mapPreOrder(order))

    return {
      status: response.status,
      data: response.data as PlaceOrderResult,
    }
  }

  async modifyOrder(order: Order, confirmId?: string): ApiPromise<void> {
    const orderId = confirmId ?? order.id
    const response = await this.rawApi.modifyOrder(apiMappers.mapPreOrder(order), orderId)

    return {
      status: response.status,
      data: undefined as void,
    }
  }

  async cancelOrder(orderId: string): ApiPromise<void> {
    const response = await this.rawApi.cancelOrder(orderId)

    return {
      status: response.status,
      data: undefined as void,
    }
  }

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

  async getAccountInfo(): ApiPromise<AccountMetainfo> {
    const response = await this.rawApi.getAccountInfo()

    return {
      status: response.status,
      data: response.data as AccountMetainfo,
    }
  }
}
