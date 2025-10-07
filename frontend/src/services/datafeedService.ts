import symbolsData from '@debug/symbols.json'
import type {
  Bar,
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
  Timezone,
} from '@public/trading_terminal/charting_library'

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
export class DatafeedService implements IBasicDataFeed, IDatafeedQuotesApi {
  /**
   * Available symbols loaded from JSON file
   */
  private readonly availableSymbols: LibrarySymbolInfo[]

  /**
   * Generated sample bars for the last 400 days
   * Each bar represents one day of OHLC data
   * Used as base data for getBars implementation
   */
  private readonly sampleBars: Bar[] = this.generateLast400DaysBars()

  /**
   * Active subscriptions map: listenerGuid -> subscription info
   */
  private readonly subscriptions = new Map<
    string,
    {
      symbolInfo: LibrarySymbolInfo
      resolution: string
      onTick: SubscribeBarsCallback
      onResetCacheNeeded?: () => void
      intervalId?: number
    }
  >()

  /**
   * Active quotes subscriptions map: listenerGuid -> subscription info
   */
  private readonly quotesSubscriptions = new Map<
    string,
    {
      symbols: string[]
      fastSymbols: string[]
      onRealtimeCallback: QuotesCallback
      intervalId?: number
    }
  >()

  /**
   * Configuration for real-time tick frequency
   */

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

  /**
   * Generate 400 bars for the last 400 days until today
   */
  private generateLast400DaysBars(): Bar[] {
    const bars: Bar[] = []
    const today = new Date()
    let currentPrice = 100 // Starting price

    // Generate bars for the last 400 days
    for (let i = 400; i >= 0; i--) {
      const date = new Date(today)
      date.setDate(today.getDate() - i)
      date.setUTCHours(0, 0, 0, 0) // Set to midnight UTC

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

  /**
   * Create a mock bar by duplicating the last bar and randomizing the close value
   * within the high-low range to simulate real-time data updates
   */
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

  /**
   * Called when the library is ready to work with the datafeed.
   * You should provide the configuration of your datafeed.
   *
   * @param callback - Function to call with datafeed configuration
   */
  onReady(callback: OnReadyCallback): void {
    console.log('[Datafeed] onReady called')

    const configuration = {
      // Supported time intervals/resolutions
      supported_resolutions: ['1D'] as unknown as ResolutionString[],

      // Feature support flags
      supports_marks: false,
      supports_timescale_marks: false,
      supports_time: false,
      supports_search: true,
      supports_group_request: false,

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

    // Use setTimeout to ensure asynchronous callback as required
    setTimeout(() => {
      console.log('[Datafeed] Sending configuration:', configuration)
      callback(configuration)
    }, 0)
  }

  /**
   * Called when the user types in the symbol search box.
   *
   * @param userInput - Text entered by user
   * @param exchange - Exchange name (if specified)
   * @param symbolType - Symbol type filter
   * @param onResult - Callback to return search results
   */
  searchSymbols(
    userInput: string,
    exchange: string,
    symbolType: string,
    onResult: SearchSymbolsCallback,
  ): void {
    console.log('[Datafeed] searchSymbols called:', {
      userInput,
      exchange,
      symbolType,
    })

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

    // Limit results to prevent overwhelming the UI
    const maxResults = 50
    const limitedSymbols = filteredSymbols.slice(0, maxResults)

    // Convert LibrarySymbolInfo to SearchSymbolResultItem for the callback
    const results: SearchSymbolResultItem[] = limitedSymbols.map((symbol) => ({
      symbol: symbol.name,
      description: symbol.description,
      exchange: symbol.exchange,
      ticker: symbol.ticker,
      type: symbol.type,
    }))

    console.log(`[Datafeed] Found ${results.length} symbols matching search`)

    // Use setTimeout to ensure asynchronous callback as required
    setTimeout(() => {
      onResult(results)
    }, 0)
  }

  /**
   * Called when the library needs to get symbol information.
   *
   * @param symbolName - Symbol name to resolve
   * @param onResolve - Success callback with symbol info
   * @param onError - Error callback
   */
  resolveSymbol(
    symbolName: string,
    onResolve: ResolveCallback,
    onError: DatafeedErrorCallback,
  ): void {
    console.log('[Datafeed] resolveSymbol called:', { symbolName })

    // Search for the symbol in our available symbols
    const symbolInfo = this.availableSymbols.find(
      (symbol) =>
        symbol.name === symbolName ||
        symbol.ticker === symbolName ||
        symbol.name.toLowerCase() === symbolName.toLowerCase() ||
        (symbol.ticker && symbol.ticker.toLowerCase() === symbolName.toLowerCase()),
    )

    // Use setTimeout to ensure asynchronous callback as required
    setTimeout(() => {
      if (symbolInfo) {
        console.log('[Datafeed] Symbol resolved:', symbolInfo)
        onResolve(symbolInfo)
      } else {
        console.log('[Datafeed] Symbol not found:', symbolName)
        // Use "unknown_symbol" to display the default ghost icon
        onError('unknown_symbol')
      }
    }, 0)
  }

  /**
   * Called when the library needs historical data for a symbol.
   *
   * @param symbolInfo - Symbol information
   * @param resolution - Time resolution
   * @param periodParams - Time range parameters
   * @param onResult - Success callback with historical data
   * @param onError - Error callback
   */
  getBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    periodParams: PeriodParams,
    onResult: HistoryCallback,
    onError: DatafeedErrorCallback,
  ): void {
    console.log('[Datafeed] getBars called:', {
      symbol: symbolInfo.name,
      resolution,
      from: new Date(periodParams.from * 1000).toISOString(),
      to: new Date(periodParams.to * 1000).toISOString(),
      countBack: periodParams.countBack,
    })

    // Use setTimeout to ensure asynchronous callback as required
    setTimeout(() => {
      try {
        // Only support 1D resolution for now
        if (resolution !== '1D') {
          console.log('[Datafeed] Unsupported resolution:', resolution)
          onResult([], { noData: true })
          return
        }

        // Check if symbol exists in our available symbols
        const symbolExists = this.availableSymbols.some(
          (symbol) =>
            symbol.name === symbolInfo.name ||
            symbol.ticker === symbolInfo.name ||
            symbol.name === symbolInfo.ticker ||
            (symbol.ticker && symbol.ticker === symbolInfo.ticker),
        )

        if (!symbolExists) {
          console.log('[Datafeed] Symbol not found in available symbols:', symbolInfo.name)
          onResult([], { noData: true })
          return
        }

        const from: number = periodParams.from * 1000,
          to: number = periodParams.to * 1000

        // Filter bars within the requested time range [from, to]
        const filteredBars = this.sampleBars.filter((bar) => bar.time >= from && bar.time <= to)

        console.log(
          `[Datafeed] Found ${filteredBars.length} bars in time range, need ${periodParams.countBack}`,
        )

        filteredBars.sort((a, b) => a.time - b.time)
        if (1 < filteredBars.length) {
          // prevent single bar which causes issues in charting library
          onResult(filteredBars)
        } else {
          onResult([], { noData: true })
        }
      } catch (error) {
        console.error('[Datafeed] Error in getBars:', error)
        onError(error instanceof Error ? error.message : 'Unknown error occurred')
      }
    }, 0)
  }

  /**
   * Called when the library wants to subscribe to real-time data updates.
   *
   * @param symbolInfo - Symbol information
   * @param resolution - Time resolution
   * @param onTick - Callback to call with new data
   * @param listenerGuid - Unique identifier for this subscription
   * @param onResetCacheNeededCallback - Callback to reset cache if needed
   */
  subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    onTick: SubscribeBarsCallback,
    listenerGuid: string,
    onResetCacheNeededCallback?: () => void,
  ): void {
    console.log('[Datafeed] subscribeBars called:', {
      symbol: symbolInfo.name,
      resolution,
      listenerGuid,
    })

    // Only support 1D resolution for now
    if (resolution !== '1D') {
      console.log('[Datafeed] Unsupported resolution for subscription:', resolution)
      return
    }

    // Check if symbol exists in our available symbols
    const symbolExists = this.availableSymbols.some(
      (symbol) =>
        symbol.name === symbolInfo.name ||
        symbol.ticker === symbolInfo.name ||
        symbol.name === symbolInfo.ticker ||
        (symbol.ticker && symbol.ticker === symbolInfo.ticker),
    )

    if (!symbolExists) {
      console.log('[Datafeed] Symbol not found for subscription:', symbolInfo.name)
      return
    }

    this.subscriptions.set(listenerGuid, {
      symbolInfo,
      resolution,
      onTick,
      onResetCacheNeeded: onResetCacheNeededCallback,
      intervalId: window.setInterval(() => {
        if (!this.subscriptions.has(listenerGuid)) {
          return
        }

        const lastBar = this.sampleBars[this.sampleBars.length - 1]
        if (!lastBar) {
          console.log('[Datafeed] No last bar available to mock')
          return
        }
        const mockedBar = this.mockLastBar(lastBar)

        console.debug('[Datafeed] Sending real-time update:', {
          symbol: symbolInfo.name,
          listenerGuid,
          bar: mockedBar,
          interval: 500,
        })

        onTick(mockedBar)
      }, 500),
    })

    console.log(`[Datafeed] Subscription started for ${symbolInfo.name} (${listenerGuid})`)
  }

  /**
   * Called when the library wants to unsubscribe from real-time data updates.
   *
   * @param listenerGuid - Unique identifier for the subscription to remove
   */
  unsubscribeBars(listenerGuid: string): void {
    console.log('[Datafeed] unsubscribeBars called:', { listenerGuid })
    const subscription = this.subscriptions.get(listenerGuid)
    if (subscription) {
      if (subscription.intervalId) {
        window.clearInterval(subscription.intervalId)
      }
      this.subscriptions.delete(listenerGuid)
      console.log(
        `[Datafeed] Subscription removed for ${subscription.symbolInfo.name} (${listenerGuid})`,
      )
    } else {
      console.log(`[Datafeed] No subscription found for listenerGuid: ${listenerGuid}`)
    }
  }

  /**
   * Called when the library needs quote data for trading platform features.
   * This method provides real-time market data for watchlist, order ticket, DOM, etc.
   *
   * @param symbols - Array of symbol names to get quotes for
   * @param onDataCallback - Callback to return the quote data
   * @param onErrorCallback - Callback for error handling
   */
  getQuotes(
    symbols: string[],
    onDataCallback: QuotesCallback,
    onErrorCallback: QuotesErrorCallback,
  ): void {
    console.debug('[Datafeed] getQuotes called:', { symbols })

    // Use setTimeout to ensure asynchronous callback as required
    setTimeout(() => {
      try {
        const quoteData: QuoteData[] = []

        symbols.forEach((symbol) => {
          // Check if symbol exists in our available symbols
          const symbolExists = this.availableSymbols.some(
            (availableSymbol) =>
              availableSymbol.name === symbol ||
              availableSymbol.ticker === symbol ||
              availableSymbol.name.toLowerCase() === symbol.toLowerCase() ||
              (availableSymbol.ticker &&
                availableSymbol.ticker.toLowerCase() === symbol.toLowerCase()),
          )

          if (!symbolExists) {
            console.log(`[Datafeed] Symbol not found for quotes: ${symbol}`)
            quoteData.push({
              s: 'error',
              n: symbol,
              v: { error: 'Symbol not found' },
            })
            return
          }

          // Generate realistic quote data based on the last bar
          const lastBar = this.sampleBars[this.sampleBars.length - 1]
          if (!lastBar) {
            console.log(`[Datafeed] No historical data available for quotes: ${symbol}`)
            quoteData.push({
              s: 'error',
              n: symbol,
              v: { error: 'No data available' },
            })
            return
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

          const responseData: QuoteData = {
            s: 'ok',
            n: symbol, // Ensure this exactly matches the requested symbol
            v: quoteValues,
          }

          quoteData.push(responseData)
        })

        console.debug(`[Datafeed] Generated quotes for ${quoteData.length} symbols`)
        onDataCallback(quoteData)
      } catch (error) {
        console.error('[Datafeed] Error in getQuotes:', error)
        onErrorCallback(error instanceof Error ? error.message : 'Unknown error occurred')
      }
    }, 0)
  }

  /**
   * Called when the library wants to subscribe to real-time quote updates.
   * This is used for trading platform features like watchlist, order ticket, etc.
   *
   * @param symbols - Array of symbols that should be updated rarely (once per minute)
   * @param fastSymbols - Array of symbols that should be updated frequently (every 10 seconds)
   * @param onRealtimeCallback - Callback to send real-time quote data updates
   * @param listenerGUID - Unique identifier for this subscription
   */
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

  /**
   * Called when the library wants to unsubscribe from real-time quote updates.
   *
   * @param listenerGUID - Unique identifier for the subscription to remove
   */
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
