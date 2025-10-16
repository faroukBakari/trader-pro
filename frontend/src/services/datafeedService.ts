import symbolsData from '@debug/symbols.json';
import type {
  Bar,
  DatafeedConfiguration,
  DatafeedErrorCallback,
  DatafeedQuoteValues,
  HistoryCallback,
  IBasicDataFeed,
  IDatafeedQuotesApi,
  LibrarySymbolInfo,
  OnReadyCallback,
  PeriodParams,
  QuoteData,
  QuotesCallback,
  QuotesErrorCallback,
  ResolutionString,
  ResolveCallback,
  SearchSymbolResultItem,
  SearchSymbolsCallback,
  SeriesFormat,
  SubscribeBarsCallback,
  Timezone
} from '@public/trading_terminal/charting_library';

import type { GetBarsResponse, GetQuotesRequest, RequestPromise } from '@/plugins/apiAdapter';
import { ApiAdapter } from '@/plugins/apiAdapter';

import { WebSocketClientPlugin } from '@/plugins/traderPlugin';
import type { WebSocketInterface } from '@/plugins/wsClientBase';

interface BarsSubscriptionRequest {
  symbol: string
  resolution?: string
}

// documentation:
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/required-methods
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/trading-platform-methods
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/additional-methods

/**
 * Datafeed Service
 *
 * This class implements the IDatafeedChartApi interface required.
 * All methods are left blank for custom implementation.
 *
 * @see https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IDatafeedChartApi
 */

interface ApiInterface {
  getConfig(): RequestPromise<DatafeedConfiguration>
  resolveSymbol(symbol: string): RequestPromise<LibrarySymbolInfo>
  searchSymbols(
    userInput: string,
    exchange?: string,
    symbolType?: string,
    maxResults?: number,
  ): RequestPromise<Array<SearchSymbolResultItem>>
  getBars(
    symbol: string,
    resolution: string,
    fromTime: number,
    toTime: number,
    countBack?: number | null,
  ): RequestPromise<GetBarsResponse>
  getQuotes(getQuotesRequest: GetQuotesRequest): RequestPromise<Array<QuoteData>>
}

function generateLast400DaysBars(): Bar[] {
  const bars: Bar[] = []
  const today = new Date()
  today.setUTCHours(0, 0, 0, 0) // Set to midnight UTC
  let currentPrice = 100 // Starting price

  // Generate bars for the last 400 days
  for (let i = 400; i >= 0; i--) {
    const date = new Date(today)
    date.setTime(date.getTime() - i * 24 * 60 * 60 * 1000) // Subtract i days

    const timestamp = Math.floor(date.getTime() / 1000) // Convert to seconds

    // Use date as seed for deterministic random generation
    const seed = timestamp
    const seededRandom = (offset: number) => {
      const x = Math.sin(seed + offset) * 10000
      return x - Math.floor(x)
    }

    // Generate realistic OHLC data
    const volatility = 2
    const open = currentPrice
    const change = (seededRandom(1) - 0.5) * volatility
    const close = open + change
    const high = Math.max(open, close) + seededRandom(2) * volatility
    const low = Math.min(open, close) - seededRandom(3) * volatility
    const volume = Math.floor(seededRandom(4) * 1000000) + 500000

    const bar: Bar = {
      time: timestamp * 1000, // Convert to milliseconds
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
    }

    bars.push(bar)

    // Update price for next bar (trend simulation)
    currentPrice = close + (seededRandom(5) - 0.48) * 0.5
  }

  return bars
}
const sampleBars: Bar[] = generateLast400DaysBars()

class ApiFallback implements ApiInterface {
  /**
   * Available symbols loaded from JSON file
   */
  private readonly availableSymbols: LibrarySymbolInfo[]
  constructor() {
    // Load and parse symbols from JSON file
    this.availableSymbols = symbolsData.map((symbol) => ({
      ...symbol,
      supported_resolutions: symbol.supported_resolutions as ResolutionString[],
      timezone: symbol.timezone as Timezone,
      format: symbol.format as SeriesFormat,
      data_status: symbol.data_status as 'streaming' | 'endofday' | 'delayed_streaming',
    }))
  }
  async getConfig(): RequestPromise<DatafeedConfiguration> {
    const configuration: DatafeedConfiguration = {
      // Supported time intervals/resolutions
      supported_resolutions: ['1D'] as unknown as ResolutionString[],

      // Feature support flags
      supports_marks: false,
      supports_timescale_marks: false,
      supports_time: false,

      // Exchanges (for symbol search filtering)
      exchanges: [
        { value: '', name: 'All Exchanges', desc: '' },
        { value: 'NASDAQ', name: 'NASDAQ', desc: 'NASDAQ' },
        { value: 'NYSE', name: 'NYSE', desc: 'NYSE' },
      ],

      // Symbol types (for symbol search filtering)
      symbols_types: [
        { name: 'All types', value: '' },
        { name: 'Stock', value: 'stock' },
        { name: 'Crypto', value: 'crypto' },
        { name: 'Forex', value: 'forex' },
      ],
    }

    return Promise.resolve({
      data: configuration,
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {},
    }) as RequestPromise<DatafeedConfiguration>
  }
  async resolveSymbol(symbolName: string): RequestPromise<LibrarySymbolInfo> {
    console.log('[Datafeed] resolveSymbol called:', { symbolName })

    // Search for the symbol in our available symbols
    const symbolInfo = this.availableSymbols.find(
      (symbol) =>
        symbol.name === symbolName ||
        symbol.ticker === symbolName ||
        symbol.name.toLowerCase() === symbolName.toLowerCase() ||
        (symbol.ticker && symbol.ticker.toLowerCase() === symbolName.toLowerCase()),
    )
    return Promise.resolve({
      data: symbolInfo!,
      status: symbolInfo ? 200 : 404,
      statusText: symbolInfo ? 'OK' : 'Not Found',
    }) as RequestPromise<LibrarySymbolInfo>
  }
  async searchSymbols(
    userInput: string,
    exchange?: string,
    symbolType?: string,
    maxResults?: number,
  ): RequestPromise<Array<SearchSymbolResultItem>> {
    // Filter symbols based on user input and filters
    let filteredSymbols = this.availableSymbols

    // Filter by user input (search in name, description, or ticker)
    if (userInput && userInput.trim() !== '') {
      const searchTerm = userInput.toLowerCase().trim()
      filteredSymbols = filteredSymbols.filter(
        (symbol) =>
          symbol.name.toLowerCase().includes(searchTerm) ||
          symbol.description.toLowerCase().includes(searchTerm) ||
          (symbol.ticker && symbol.ticker.toLowerCase().includes(searchTerm)),
      )
    }

    // Filter by exchange
    if (exchange && exchange !== '') {
      filteredSymbols = filteredSymbols.filter(
        (symbol) => symbol.exchange.toLowerCase() === exchange.toLowerCase(),
      )
    }

    // Filter by symbol type
    if (symbolType && symbolType !== '') {
      filteredSymbols = filteredSymbols.filter(
        (symbol) => symbol.type.toLowerCase() === symbolType.toLowerCase(),
      )
    }

    // Convert LibrarySymbolInfo to SearchSymbolResultItem for the callback
    const results: SearchSymbolResultItem[] = filteredSymbols
      .slice(0, maxResults)
      .map((symbol) => ({
        symbol: symbol.name,
        description: symbol.description,
        exchange: symbol.exchange,
        ticker: symbol.ticker,
        type: symbol.type,
      }))

    console.log(`[Datafeed] Found ${results.length} symbols matching search`)
    return Promise.resolve({
      data: results,
      status: 200,
      statusText: 'OK',
    }) as RequestPromise<Array<SearchSymbolResultItem>>
  }
  async getBars(
    symbolName: string,
    resolution: string,
    from: number,
    to: number,
    countBack?: number | null,
  ): RequestPromise<GetBarsResponse> {
    if (resolution !== '1D') {
      throw new Error('Only 1D resolution is supported in fallback client')
    }

    // Check if symbol exists in our available symbols
    const symbolExists = this.availableSymbols.some(
      (symbol) => symbol.name === symbolName || symbol.ticker === symbolName,
    )

    if (!symbolExists) {
      throw new Error(`Symbol not found: ${symbolName}`)
    }

    // Filter bars within the requested time range [from, to]
    const filteredBars = sampleBars.filter((bar) => bar.time >= from && bar.time <= to)

    console.log(`[Datafeed] Found ${filteredBars.length} bars in time range, need ${countBack}`)

    filteredBars.sort((a, b) => a.time - b.time)
    return Promise.resolve({
      data: {
        bars: filteredBars,
        no_data: filteredBars.length === 0,
      },
      status: 200,
      statusText: 'OK',
    }) as RequestPromise<GetBarsResponse>
  }
  async getQuotes(
    getQuotesRequest: GetQuotesRequest,
  ): RequestPromise<Array<QuoteData>> {
    const quoteData: QuoteData[] = getQuotesRequest.symbols.map((symbol) => {
      // Check if symbol exists in our available symbols
      const symbolExists = this.availableSymbols.some(
        (availableSymbol) =>
          availableSymbol.name === symbol ||
          availableSymbol.ticker === symbol ||
          availableSymbol.name.toLowerCase() === symbol.toLowerCase() ||
          (availableSymbol.ticker && availableSymbol.ticker.toLowerCase() === symbol.toLowerCase()),
      )

      if (!symbolExists) {
        console.log(`[Datafeed] Symbol not found for quotes: ${symbol}`)
        return {
          s: 'error',
          n: symbol,
          v: { error: 'Symbol not found' },
        }
      }

      // Generate realistic quote data based on the last bar
      const lastBar = sampleBars[sampleBars.length - 1]
      if (!lastBar) {
        console.log(`[Datafeed] No historical data available for quotes: ${symbol}`)
        return {
          s: 'error',
          n: symbol,
          v: { error: 'No data available' },
        }
      }

      // Create realistic quote values based on the last bar
      const basePrice = Math.max(lastBar.close, 0.01) // Ensure positive price
      const spread = Math.max(basePrice * 0.001, 0.01) // 0.1% spread, minimum 0.01

      // Generate some variation for real-time feel
      const variation = (Math.random() - 0.5) * basePrice * 0.005 // 0.5% max variation
      const currentPrice = Math.max(basePrice + variation, 0.01) // Ensure positive

      const bid = Math.max(currentPrice - spread / 2, 0.01) // Ensure positive bid
      const ask = Math.max(currentPrice + spread / 2, bid + 0.01) // Ensure ask > bid

      const change = currentPrice - lastBar.open
      const changePercent = lastBar.open > 0 ? (change / lastBar.open) * 100 : 0

      const quoteValues: DatafeedQuoteValues = {
        // Price data - ensure all prices are positive numbers
        lp: Number(currentPrice.toFixed(2)), // Last price
        ask: Number(ask.toFixed(2)), // Ask price
        bid: Number(bid.toFixed(2)), // Bid price
        spread: Number((ask - bid).toFixed(2)), // Spread

        // Daily statistics
        open_price: Number(Math.max(lastBar.open, 0.01).toFixed(2)),
        high_price: Number(Math.max(lastBar.high, currentPrice, 0.01).toFixed(2)),
        low_price: Number(Math.max(Math.min(lastBar.low, currentPrice), 0.01).toFixed(2)),
        prev_close_price: Number(Math.max(lastBar.close * 0.995, 0.01).toFixed(2)),
        volume: Math.max(lastBar.volume || 0, 0),

        // Changes
        ch: Number(change.toFixed(2)),
        chp: Number(changePercent.toFixed(2)),

        // Symbol information
        short_name: symbol,
        exchange: 'DEMO',
        description: `Demo quotes for ${symbol}`,
        original_name: symbol,
      }

      return {
        s: 'ok',
        n: symbol,
        v: quoteValues,
      }
    })

    console.debug(`[Datafeed] Generated quotes for ${quoteData.length} symbols`)
    return Promise.resolve({
      data: quoteData,
      status: 200,
      statusText: 'OK',
    }) as RequestPromise<Array<QuoteData>>
  }
}

export type BarsWebSocketInterface = WebSocketInterface<BarsSubscriptionRequest, Bar>

class BarsWebSocketFallbackClient implements BarsWebSocketInterface {
  private subscriptions = new Map<
    string,
    { params: BarsSubscriptionRequest; onUpdate: (data: Bar) => void }
  >()
  private intervalId: number

  constructor() {
    // Mock data updates every 3 seconds
    this.intervalId = window.setInterval(() => {
      this.subscriptions.forEach(({ onUpdate }) => {
        onUpdate(this.mockLastBar(sampleBars[sampleBars.length - 1]))
      })
    }, 1000)
  }

  private mockLastBar(lastBar: Bar): Bar {
    const range = lastBar.high - lastBar.low
    const randomFactor = Math.random() // 0 to 1
    const newClose = lastBar.low + range * randomFactor

    // Ensure the new close doesn't exceed the original high/low bounds
    const adjustedClose = Math.max(lastBar.low, Math.min(lastBar.high, newClose))

    // Update high/low if the new close exceeds them
    const newHigh = Math.max(lastBar.high, adjustedClose)
    const newLow = Math.min(lastBar.low, adjustedClose)

    return {
      time: lastBar.time, // Same time to update existing bar
      open: lastBar.open, // Keep original open
      high: parseFloat(newHigh.toFixed(2)),
      low: parseFloat(newLow.toFixed(2)),
      close: parseFloat(adjustedClose.toFixed(2)),
      volume: (lastBar.volume || 0) + Math.floor(Math.random() * 10000), // Add some volume
    }
  }

  async subscribe(
    subscriptionId: string,
    params: BarsSubscriptionRequest,
    onUpdate: (data: Bar) => void,
  ): Promise<string> {
    this.subscriptions.set(subscriptionId, { params, onUpdate })
    return subscriptionId
  }

  async unsubscribe(subscriptionId: string): Promise<void> {
    this.subscriptions.delete(subscriptionId)
  }

  destroy(): void {
    if (this.intervalId) {
      window.clearInterval(this.intervalId)
    }
    this.subscriptions.clear()
  }
}

export class DatafeedService implements IBasicDataFeed, IDatafeedQuotesApi {
  private apiAdapter: ApiInterface
  private apiFallback: ApiInterface

  private wsPlugin: WebSocketClientPlugin<BarsWebSocketInterface>
  private wsFallbackClient: BarsWebSocketInterface = new BarsWebSocketFallbackClient()

  private mock: boolean

  private readonly subscriptions = new Map<
    string,
    {
      symbolInfo: LibrarySymbolInfo
      resolution: string
      onTick: SubscribeBarsCallback
      onResetCacheNeeded?: () => void
      intervalId?: number
      wsSubscriptionId?: string // WebSocket subscription ID
    }
  >()
  private readonly quotesSubscriptions = new Map<
    string,
    {
      symbols: string[]
      fastSymbols: string[]
      onRealtimeCallback: QuotesCallback
      intervalId?: number
    }
  >()

  constructor(mock: boolean = false) {
    this.apiAdapter = new ApiAdapter()
    this.apiFallback = new ApiFallback()
    this.wsPlugin = new WebSocketClientPlugin<BarsWebSocketInterface>()
    this.mock = mock
  }

  async _loadWsClient(mock: boolean = false): Promise<BarsWebSocketInterface> {
    return mock
      ? Promise.resolve(this.wsFallbackClient)
      : this.wsPlugin.getClientWithFallback(BarsWebSocketFallbackClient)
  }

  _getClient(mock: boolean = this.mock): ApiInterface {
    return mock ? this.apiFallback : this.apiAdapter
  }
  onReady(callback: OnReadyCallback): void {
    console.log('[Datafeed] onReady called')

    this._getClient().getConfig().then((response) => {
      // Handle both AxiosResponse (generated client) and direct data (fallback client)
      const config = 'data' in response ? response.data : response
      console.log('[Datafeed] Configuration loaded:', config)
      callback(config)
    })
  }
  searchSymbols(
    userInput: string,
    exchange: string,
    symbolType: string,
    onResult: SearchSymbolsCallback,
  ): void {
    this._getClient().searchSymbols(userInput, exchange, symbolType, 30).then((response) => {
      console.log(
        `[Datafeed] searchSymbols found ${response.data.length} symbols for input "${userInput}"`,
      )
      onResult(response.data)
    })
  }
  resolveSymbol(
    symbolName: string,
    onResolve: ResolveCallback,
    onError: DatafeedErrorCallback,
  ): void {
    this._getClient().resolveSymbol(symbolName).then((response) => {
      console.log(
        `[Datafeed] resolveSymbol found ${response.data ? 'a' : 'no'} symbol for input "${symbolName}"`,
      )
      if (response.data) {
        console.log('[Datafeed] Symbol resolved:', response.data)
        onResolve(response.data)
      } else {
        console.log('[Datafeed] Symbol not found:', symbolName)
        onError('unknown_symbol')
      }
    })
  }
  getBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    periodParams: PeriodParams,
    onResult: HistoryCallback,
    onError: DatafeedErrorCallback,
  ): void {
    this._getClient()
      .getBars(
        symbolInfo.name,
        resolution,
        periodParams.from * 1000,
        periodParams.to * 1000,
        periodParams.countBack,
      )
      .then((response) => {
        console.log(
          `[Datafeed] getBars returned ${response.data.bars.length} bars for ${symbolInfo.name} in range ${new Date(
            periodParams.from * 1000,
          ).toISOString()} - ${new Date(periodParams.to * 1000).toISOString()}`,
        )
        if (response.data.bars.length === 1)
          response.data.bars = [...response.data.bars, ...response.data.bars]
        onResult(response.data.bars, { noData: response.data.no_data || false })
      })
      .catch((error) => {
        console.error('[Datafeed] Error in getBars:', error)
        onError(error instanceof Error ? error.message : 'Unknown error occurred')
      })
  }
  subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    onTick: SubscribeBarsCallback,
    listenerGuid: string,
    // onResetCacheNeededCallback?: () => void,
  ): void {
    console.log('[Datafeed] subscribeBars called:', {
      symbol: symbolInfo.name,
      resolution,
      listenerGuid,
    })

    this._loadWsClient().then((wsClient) => {
      wsClient
        .subscribe(listenerGuid, { symbol: symbolInfo.name, resolution }, (bar) => {
          console.debug('[Datafeed] Bar received from WebSocket:', {
            symbol: symbolInfo.name,
            resolution,
            listenerGuid,
            bar,
          })
          onTick(bar)
        })
        .catch((error) => {
          console.error('[Datafeed] WebSocket subscription failed:', error)
        })
    })
  }
  unsubscribeBars(listenerGuid: string): void {
    console.log('[Datafeed] unsubscribeBars called:', { listenerGuid })
    this._loadWsClient().then((wsClient) => {
      wsClient.unsubscribe(listenerGuid).catch((error) => {
        console.error('[Datafeed] WebSocket unsubscription failed:', error)
      })
      console.log(`[Datafeed] Subscription removed for listenerGuid : (${listenerGuid})`)
    })
  }
  getQuotes(
    symbols: string[],
    onDataCallback: QuotesCallback,
    onErrorCallback: QuotesErrorCallback,
  ): void {
    console.debug('[Datafeed] getQuotes called:', { symbols })

    this._getClient()
      .getQuotes({ symbols })
      .then((response) => {
        console.debug(
          `[Datafeed] getQuotes returned ${response.data.length} quotes for ${symbols.length} requested symbols`,
        )
        onDataCallback(response.data)
      })
      .catch((error) => {
        console.error('[Datafeed] Error in getQuotes:', error)
        onErrorCallback(error instanceof Error ? error.message : 'Unknown error occurred')
      })
  }
  subscribeQuotes(
    symbols: string[],
    fastSymbols: string[],
    onRealtimeCallback: QuotesCallback,
    listenerGUID: string,
  ): void {
    console.log('[Datafeed] subscribeQuotes called:', {
      symbols,
      fastSymbols,
      listenerGUID,
    })

    // Combine all symbols for subscription
    const allSymbols = [...new Set([...symbols, ...fastSymbols])]

    if (allSymbols.length === 0) {
      console.log('[Datafeed] No symbols to subscribe to for quotes')
      return
    }

    // Store subscription info
    this.quotesSubscriptions.set(listenerGUID, {
      symbols,
      fastSymbols,
      onRealtimeCallback,
      // Use different intervals for regular vs fast symbols
      // Fast symbols update every 2 seconds, regular symbols every 10 seconds
      intervalId: window.setInterval(
        () => {
          if (!this.quotesSubscriptions.has(listenerGUID)) {
            return
          }

          // Get fresh quotes for all subscribed symbols
          this.getQuotes(
            allSymbols,
            (quoteData) => {
              console.debug('[Datafeed] Sending real-time quote updates:', {
                listenerGUID,
                symbolCount: quoteData.length,
              })
              onRealtimeCallback(quoteData)
            },
            (error) => {
              console.error('[Datafeed] Error getting quotes for real-time update:', error)
            },
          )
        },
        fastSymbols.length > 0 ? 2000 : 10000,
      ), // 2s for fast symbols, 10s for regular
    })

    console.log(
      `[Datafeed] Quote subscription started for ${allSymbols.length} symbols (${listenerGUID})`,
    )
  }
  unsubscribeQuotes(listenerGUID: string): void {
    console.log('[Datafeed] unsubscribeQuotes called:', { listenerGUID })

    const subscription = this.quotesSubscriptions.get(listenerGUID)
    if (subscription) {
      if (subscription.intervalId) {
        window.clearInterval(subscription.intervalId)
      }
      this.quotesSubscriptions.delete(listenerGUID)
      console.log(`[Datafeed] Quote subscription removed (${listenerGUID})`)
    } else {
      console.log(`[Datafeed] No quote subscription found for listenerGUID: ${listenerGUID}`)
    }
  }
}
