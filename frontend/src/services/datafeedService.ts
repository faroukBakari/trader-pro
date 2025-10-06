import symbolsData from '@debug/symbols.json'
import type {
  Bar,
  DatafeedErrorCallback,
  HistoryCallback,
  IBasicDataFeed,
  LibrarySymbolInfo,
  OnReadyCallback,
  PeriodParams,
  ResolutionString,
  ResolveCallback,
  SearchSymbolResultItem,
  SearchSymbolsCallback,
  SeriesFormat,
  SubscribeBarsCallback,
  Timezone,
} from '@public/charting_library/charting_library'

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
export class DatafeedService implements IBasicDataFeed {
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
    onResetCacheNeededCallback: () => void,
  ): void {
    void symbolInfo
    void resolution
    void onTick
    void listenerGuid
    void onResetCacheNeededCallback
    // TODO: Implement real-time data subscription
    // Example:
    // this.subscriptions.set(listenerGuid, {
    //   symbolInfo,
    //   resolution,
    //   onTick,
    //   onResetCacheNeededCallback
    // })
    // startRealTimeUpdates(symbolInfo.name, resolution, onTick)
  }

  /**
   * Called when the library wants to unsubscribe from real-time data updates.
   *
   * @param listenerGuid - Unique identifier for the subscription to remove
   */
  unsubscribeBars(listenerGuid: string): void {
    void listenerGuid
    // TODO: Implement unsubscription
    // Example:
    // const subscription = this.subscriptions.get(listenerGuid)
    // if (subscription) {
    //   stopRealTimeUpdates(listenerGuid)
    //   this.subscriptions.delete(listenerGuid)
    // }
  }
}
