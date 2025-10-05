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
  SubscribeBarsCallback,
} from '@public/charting_library/charting_library'

// documentation:
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/required-methods
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/trading-platform-methods
// - https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/additional-methods

/**
 * TradingView Datafeed Service
 *
 * This class implements the IDatafeedChartApi interface required by TradingView.
 * All methods are left blank for custom implementation.
 *
 * @see https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IDatafeedChartApi
 */
export class DatafeedService implements IBasicDataFeed {
  /**
   * Hardcoded list of available symbols for search
   */
  private readonly availableSymbols: SearchSymbolResultItem[] = [
    {
      symbol: 'AAPL',
      description: 'Apple Inc.',
      exchange: 'NASDAQ',
      ticker: 'AAPL',
      type: 'stock',
    },
    {
      symbol: 'GOOGL',
      description: 'Alphabet Inc. Class A',
      exchange: 'NASDAQ',
      ticker: 'GOOGL',
      type: 'stock',
    },
    {
      symbol: 'MSFT',
      description: 'Microsoft Corporation',
      exchange: 'NASDAQ',
      ticker: 'MSFT',
      type: 'stock',
    },
    {
      symbol: 'TSLA',
      description: 'Tesla, Inc.',
      exchange: 'NASDAQ',
      ticker: 'TSLA',
      type: 'stock',
    },
    {
      symbol: 'AMZN',
      description: 'Amazon.com, Inc.',
      exchange: 'NASDAQ',
      ticker: 'AMZN',
      type: 'stock',
    },
    {
      symbol: 'NVDA',
      description: 'NVIDIA Corporation',
      exchange: 'NASDAQ',
      ticker: 'NVDA',
      type: 'stock',
    },
    {
      symbol: 'META',
      description: 'Meta Platforms, Inc.',
      exchange: 'NASDAQ',
      ticker: 'META',
      type: 'stock',
    },
  ]
  /**
   * Generated sample bars for the last 30 days
   * Each bar represents one day of OHLC data
   */
  private readonly sampleBars: Bar[] = this.generateLast30DaysBars()

  /**
   * Generate 30 bars for the last 30 days until today
   */
  private generateLast30DaysBars(): Bar[] {
    const bars: Bar[] = []
    const today = new Date()
    let currentPrice = 100 // Starting price

    // Generate bars for the last 30 days
    for (let i = 29; i >= 0; i--) {
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
        time: timestamp,
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

    // Use setTimeout to ensure asynchronous callback as required by TradingView
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

    // Filter by user input (search in symbol, description, or ticker)
    if (userInput && userInput.trim() !== '') {
      const searchTerm = userInput.toLowerCase().trim()
      filteredSymbols = filteredSymbols.filter(
        (symbol) =>
          symbol.symbol.toLowerCase().includes(searchTerm) ||
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
    const results = filteredSymbols.slice(0, maxResults)

    console.log(`[Datafeed] Found ${results.length} symbols matching search`)

    // Use setTimeout to ensure asynchronous callback as required by TradingView
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
    void symbolName
    void onResolve
    void onError
    // TODO: Implement symbol resolution
    // Example:
    // const symbolInfo: LibrarySymbolInfo = {
    //   name: symbolName,
    //   full_name: symbolName,
    //   description: `${symbolName} Description`,
    //   type: 'stock',
    //   session: '24x7',
    //   timezone: 'Etc/UTC',
    //   ticker: symbolName,
    //   exchange: 'Your Exchange',
    //   listed_exchange: 'Your Exchange',
    //   format: 'price',
    //   minmov: 1,
    //   pricescale: 100,
    //   has_intraday: false,
    //   has_daily: true,
    //   supported_resolutions: ['1D'],
    //   volume_precision: 0,
    //   data_status: 'streaming',
    // }
    // onResolve(symbolInfo)
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
    void symbolInfo
    void resolution
    void periodParams
    void onResult
    void onError
    // TODO: Implement historical data fetching
    // Example:
    // try {
    //   const bars = await fetchHistoricalData(
    //     symbolInfo.name,
    //     resolution,
    //     periodParams.from,
    //     periodParams.to
    //   )
    //   onResult(bars, { noData: bars.length === 0 })
    // } catch (error) {
    //   onError(error.message)
    // }
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
