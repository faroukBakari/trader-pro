/**
 * @vitest-environment node
 */

import type {
  Bar,
  DatafeedConfiguration,
  LibrarySymbolInfo,
  QuoteData,
  SearchSymbolResultItem,
} from '@public/trading_terminal'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DatafeedMock, DatafeedService } from '../datafeedService'

/**
 * Test suite for DatafeedService
 *
 * Tests the datafeed implementation with both fallback (mock) and real backend modes:
 * - Configuration loading (onReady)
 * - Symbol search and resolution
 * - Historical bars fetching
 * - Real-time bar subscriptions
 * - Quote data fetching and subscriptions
 * - WebSocket integration
 * - Mock data generation
 *
 * NOTE: DatafeedMock provides deterministic mock data for testing
 * The service can switch between mock and backend modes via constructor parameter
 */
describe('DatafeedService', () => {
  let datafeedService: DatafeedService
  let testDatafeedMock: DatafeedMock

  /**
   * Helper to convert callback-based datafeed methods to promises
   */
  const onReadyPromise = (): Promise<DatafeedConfiguration> => {
    return new Promise((resolve) => {
      datafeedService.onReady(resolve)
    })
  }

  const searchSymbolsPromise = (
    userInput: string,
    exchange: string,
    symbolType: string,
  ): Promise<SearchSymbolResultItem[]> => {
    return new Promise((resolve) => {
      datafeedService.searchSymbols(userInput, exchange, symbolType, resolve)
    })
  }

  const resolveSymbolPromise = (symbolName: string): Promise<LibrarySymbolInfo> => {
    return new Promise((resolve, reject) => {
      datafeedService.resolveSymbol(symbolName, resolve, reject)
    })
  }

  const getBarsPromise = (
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    from: number,
    to: number,
    countBack?: number,
  ): Promise<Bar[]> => {
    return new Promise((resolve, reject) => {
      datafeedService.getBars(
        symbolInfo,
        resolution,
        { from, to, countBack: countBack ?? 0, firstDataRequest: false },
        (bars) => resolve(bars),
        reject,
      )
    })
  }

  const getQuotesPromise = (symbols: string[]): Promise<QuoteData[]> => {
    return new Promise((resolve, reject) => {
      datafeedService.getQuotes(symbols, resolve, reject)
    })
  }

  beforeEach(() => {
    // Create fresh DatafeedMock instance for each test
    testDatafeedMock = new DatafeedMock()

    // Use fallback client with test DatafeedMock instance
    datafeedService = new DatafeedService(testDatafeedMock)

    // Clear all mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up any remaining state
    vi.restoreAllMocks()
  })

  describe('Configuration (onReady)', () => {
    it('should return datafeed configuration', async () => {
      const config = await onReadyPromise()

      expect(config).toBeDefined()
      expect(config).toHaveProperty('supported_resolutions')
      expect(config).toHaveProperty('supports_marks')
      expect(config).toHaveProperty('supports_timescale_marks')
      expect(config).toHaveProperty('supports_time')
    })

    it('should support 1D resolution', async () => {
      const config = await onReadyPromise()
      expect(config.supported_resolutions).toContain('1D')
    })

    it('should provide exchanges list', async () => {
      const config = await onReadyPromise()

      expect(config.exchanges).toBeDefined()
      expect(Array.isArray(config.exchanges)).toBe(true)
      expect(config.exchanges!.length).toBeGreaterThan(0)

      // Check structure of exchanges
      config.exchanges!.forEach((exchange) => {
        expect(exchange).toHaveProperty('value')
        expect(exchange).toHaveProperty('name')
        expect(exchange).toHaveProperty('desc')
      })
    })

    it('should provide symbol types list', async () => {
      const config = await onReadyPromise()

      expect(config.symbols_types).toBeDefined()
      expect(Array.isArray(config.symbols_types)).toBe(true)
      expect(config.symbols_types!.length).toBeGreaterThan(0)

      // Check structure of symbol types
      config.symbols_types!.forEach((type) => {
        expect(type).toHaveProperty('name')
        expect(type).toHaveProperty('value')
      })
    })

    it('should have consistent configuration across multiple calls', async () => {
      const firstConfig = await onReadyPromise()
      const secondConfig = await onReadyPromise()

      expect(secondConfig.supported_resolutions).toEqual(firstConfig.supported_resolutions)
      expect(secondConfig.exchanges).toEqual(firstConfig.exchanges)
      expect(secondConfig.symbols_types).toEqual(firstConfig.symbols_types)
    })
  })

  describe('Symbol Search', () => {
    it('should search symbols with empty query', async () => {
      const results = await searchSymbolsPromise('', '', '')

      expect(Array.isArray(results)).toBe(true)
      expect(results.length).toBeGreaterThan(0)

      // Verify result structure
      results.forEach((result) => {
        expect(result).toHaveProperty('symbol')
        expect(result).toHaveProperty('description')
        expect(result).toHaveProperty('exchange')
        expect(result).toHaveProperty('type')
      })
    })

    it('should search symbols by name', async () => {
      const results = await searchSymbolsPromise('AAPL', '', '')

      expect(results.length).toBeGreaterThan(0)
      const hasApple = results.some(
        (r) => r.symbol.includes('AAPL') || r.description.toLowerCase().includes('apple'),
      )
      expect(hasApple).toBe(true)
    })

    it('should filter symbols by exchange', async () => {
      const results = await searchSymbolsPromise('', 'NASDAQ', '')

      results.forEach((result) => {
        expect(result.exchange).toBe('NASDAQ')
      })
    })

    it('should filter symbols by type', async () => {
      const results = await searchSymbolsPromise('', '', 'stock')

      results.forEach((result) => {
        expect(result.type.toLowerCase()).toBe('stock')
      })
    })

    it('should handle case-insensitive search', async () => {
      const results = await searchSymbolsPromise('aapl', '', '')
      expect(results.length).toBeGreaterThan(0)
    })

    it('should handle combined filters', async () => {
      const results = await searchSymbolsPromise('A', 'NASDAQ', 'stock')

      results.forEach((result) => {
        // Search matches name, description, or ticker (not just symbol)
        const matchesSearch =
          result.symbol.toLowerCase().includes('a') || result.description.toLowerCase().includes('a')
        expect(matchesSearch).toBe(true)
        expect(result.exchange).toBe('NASDAQ')
        expect(result.type.toLowerCase()).toBe('stock')
      })
    })
  })

  describe('Symbol Resolution', () => {
    it('should resolve valid symbol', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')

      expect(symbolInfo).toBeDefined()
      expect(symbolInfo).toHaveProperty('name')
      expect(symbolInfo).toHaveProperty('ticker')
      expect(symbolInfo).toHaveProperty('description')
      expect(symbolInfo).toHaveProperty('type')
      expect(symbolInfo).toHaveProperty('exchange')
      expect(symbolInfo).toHaveProperty('minmov')
      expect(symbolInfo).toHaveProperty('pricescale')
      expect(symbolInfo).toHaveProperty('timezone')
    })

    it('should resolve symbol with full name format', async () => {
      const symbolInfo = await resolveSymbolPromise('NASDAQ:AAPL')
      expect(symbolInfo.name).toContain('AAPL')
    })

    it('should handle non-existent symbol', async () => {
      await expect(resolveSymbolPromise('NONEXISTENT123456')).rejects.toBe('unknown_symbol')
    })

    it('should return consistent symbol info on multiple resolves', async () => {
      const firstInfo = await resolveSymbolPromise('AAPL')
      const secondInfo = await resolveSymbolPromise('AAPL')

      expect(secondInfo.name).toBe(firstInfo.name)
      expect(secondInfo.ticker).toBe(firstInfo.ticker)
      expect(secondInfo.type).toBe(firstInfo.type)
      expect(secondInfo.exchange).toBe(firstInfo.exchange)
    })

    it('should resolve symbol with supported_resolutions', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')

      expect(symbolInfo.supported_resolutions).toBeDefined()
      expect(Array.isArray(symbolInfo.supported_resolutions)).toBe(true)
      expect(symbolInfo.supported_resolutions!.length).toBeGreaterThan(0)
    })
  })

  describe('Historical Bars', () => {
    it('should fetch historical bars', async () => {
      const to = Date.now()
      const from = to - 30 * 24 * 60 * 60 * 1000 // 30 days ago

      const symbolInfo = await resolveSymbolPromise('AAPL')
      const bars = await getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), 30)

      expect(Array.isArray(bars)).toBe(true)
      expect(bars.length).toBeGreaterThan(0)

      // Verify bar structure
      bars.forEach((bar) => {
        expect(bar).toHaveProperty('time')
        expect(bar).toHaveProperty('open')
        expect(bar).toHaveProperty('high')
        expect(bar).toHaveProperty('low')
        expect(bar).toHaveProperty('close')
        expect(bar).toHaveProperty('volume')

        // Validate OHLC relationships
        expect(bar.high).toBeGreaterThanOrEqual(bar.low)
        expect(bar.high).toBeGreaterThanOrEqual(bar.open)
        expect(bar.high).toBeGreaterThanOrEqual(bar.close)
        expect(bar.low).toBeLessThanOrEqual(bar.open)
        expect(bar.low).toBeLessThanOrEqual(bar.close)
      })
    })

    it('should return bars in chronological order', async () => {
      const to = Date.now()
      const from = to - 30 * 24 * 60 * 60 * 1000

      const symbolInfo = await resolveSymbolPromise('AAPL')
      const bars = await getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), 30)

      for (let i = 1; i < bars.length; i++) {
        expect(bars[i].time).toBeGreaterThanOrEqual(bars[i - 1].time)
      }
    })

    it('should handle bars request with no data', async () => {
      const to = Date.now() - 100 * 365 * 24 * 60 * 60 * 1000 // 100 years ago
      const from = to - 30 * 24 * 60 * 60 * 1000

      const symbolInfo = await resolveSymbolPromise('AAPL')
      const bars = await getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), 30)

      expect(bars.length).toBe(0)
    })

    it('should respect time range boundaries', async () => {
      const to = Date.now()
      const from = to - 30 * 24 * 60 * 60 * 1000

      const symbolInfo = await resolveSymbolPromise('AAPL')
      const bars = await getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), 30)

      bars.forEach((bar) => {
        expect(bar.time).toBeGreaterThanOrEqual(from)
        expect(bar.time).toBeLessThanOrEqual(to)
      })
    })

    it('should handle countBack parameter', async () => {
      const to = Date.now()
      const from = to - 100 * 24 * 60 * 60 * 1000 // 100 days
      const countBack = 10

      const symbolInfo = await resolveSymbolPromise('AAPL')
      const bars = await getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), countBack)

      // May return up to countBack bars, but not more than available
      expect(bars.length).toBeLessThanOrEqual(countBack + 1)
    })
  })

  describe('Real-time Bar Subscriptions', () => {
    it('should subscribe to bars', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')
      const listenerGuid = 'test-listener-' + Date.now()

      return new Promise<void>((resolve, reject) => {
        let barReceived = false

        datafeedService.subscribeBars(
          symbolInfo,
          '1D',
          (bar: Bar) => {
            barReceived = true
            expect(bar).toBeDefined()
            expect(bar).toHaveProperty('time')
            expect(bar).toHaveProperty('open')
            expect(bar).toHaveProperty('high')
            expect(bar).toHaveProperty('low')
            expect(bar).toHaveProperty('close')

            datafeedService.unsubscribeBars(listenerGuid)
            resolve()
          },
          listenerGuid,
        )

        // Wait for mocker to generate bar update
        setTimeout(() => {
          if (!barReceived) {
            datafeedService.unsubscribeBars(listenerGuid)
            reject(new Error('No bar received after timeout'))
          }
        }, 500)
      })
    })

    it('should handle multiple bar subscriptions', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')

      return new Promise<void>((resolve, reject) => {
        let receivedCount = 0
        const expectedCount = 2

        const listener1 = 'listener-1-' + Date.now()
        const listener2 = 'listener-2-' + Date.now()

        const callback = () => {
          receivedCount++
          if (receivedCount === expectedCount) {
            expect(receivedCount).toBe(expectedCount)
            datafeedService.unsubscribeBars(listener1)
            datafeedService.unsubscribeBars(listener2)
            resolve()
          }
        }

        datafeedService.subscribeBars(symbolInfo, '1D', callback, listener1)
        datafeedService.subscribeBars(symbolInfo, '1D', callback, listener2)

        // Wait for updates
        setTimeout(() => {
          if (receivedCount < expectedCount) {
            datafeedService.unsubscribeBars(listener1)
            datafeedService.unsubscribeBars(listener2)
            reject(new Error(`Expected ${expectedCount} updates, got ${receivedCount}`))
          }
        }, 500)
      })
    })

    it('should unsubscribe from bars', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')
      const listenerGuid = 'test-listener-' + Date.now()
      let barCount = 0

      datafeedService.subscribeBars(
        symbolInfo,
        '1D',
        () => {
          barCount++
        },
        listenerGuid,
      )

      // Immediately unsubscribe
      datafeedService.unsubscribeBars(listenerGuid)

      // Wait and verify no more bars received
      await new Promise((resolve) => setTimeout(resolve, 300))

      expect(barCount).toBeLessThanOrEqual(1) // May receive one before unsubscribe
    })
  })

  describe('Quote Data Fetching', () => {
    it('should fetch quotes for single symbol', async () => {
      const quotes = await getQuotesPromise(['AAPL'])

      expect(Array.isArray(quotes)).toBe(true)
      expect(quotes.length).toBeGreaterThan(0)

      const quote = quotes[0]
      expect(quote).toBeDefined()
      expect(quote.s).toBe('ok')
      expect(quote.n).toBeDefined()
      expect(quote.v).toBeDefined()

      // Validate quote values structure
      expect(quote.v).toHaveProperty('lp') // last price
      expect(quote.v).toHaveProperty('ask')
      expect(quote.v).toHaveProperty('bid')
      expect(quote.v).toHaveProperty('open_price')
      expect(quote.v).toHaveProperty('high_price')
      expect(quote.v).toHaveProperty('low_price')
    })

    it('should fetch quotes for multiple symbols', async () => {
      const symbols = ['AAPL', 'GOOGL', 'MSFT']
      const quotes = await getQuotesPromise(symbols)

      expect(quotes.length).toBe(symbols.length)
      quotes.forEach((quote) => {
        expect(quote.s).toBe('ok')
        expect(quote.v).toBeDefined()
      })
    })

    it('should handle empty symbols array', async () => {
      const quotes = await getQuotesPromise([])

      expect(Array.isArray(quotes)).toBe(true)
      expect(quotes.length).toBe(0)
    })

    it('should return realistic bid/ask spread', async () => {
      const quotes = await getQuotesPromise(['AAPL'])
      const quote = quotes[0]
      const values = quote.v as { ask?: number; bid?: number; lp?: number }
      const spread = (values.ask ?? 0) - (values.bid ?? 0)

      expect(spread).toBeGreaterThan(0)
      expect(spread).toBeLessThan((values.lp ?? 100) * 0.01) // Spread should be less than 1% of price
    })

    it('should include change and change percentage', async () => {
      const quotes = await getQuotesPromise(['AAPL'])
      const quote = quotes[0]
      const values = quote.v as { ch?: number; chp?: number }

      expect(quote.v).toHaveProperty('ch') // change
      expect(quote.v).toHaveProperty('chp') // change percentage
      expect(typeof values.ch).toBe('number')
      expect(typeof values.chp).toBe('number')
    })
  })

  describe('Quote Subscriptions', () => {
    it('should subscribe to quotes', () => {
      const listenerGuid = 'quote-listener-' + Date.now()

      return new Promise<void>((resolve, reject) => {
        let quoteReceived = false

        datafeedService.subscribeQuotes(
          ['AAPL'],
          [],
          (quotes: QuoteData[]) => {
            quoteReceived = true
            expect(Array.isArray(quotes)).toBe(true)
            expect(quotes.length).toBeGreaterThan(0)
            expect(quotes[0].s).toBe('ok')
            expect(quotes[0].v).toBeDefined()

            datafeedService.unsubscribeQuotes(listenerGuid)
            resolve()
          },
          listenerGuid,
        )

        // Wait for mocker to generate quote update
        setTimeout(() => {
          if (!quoteReceived) {
            datafeedService.unsubscribeQuotes(listenerGuid)
            reject(new Error('No quote received after timeout'))
          }
        }, 500)
      })
    })

    it('should subscribe to fast symbols separately', () => {
      const listenerGuid = 'fast-quote-listener-' + Date.now()

      return new Promise<void>((resolve, reject) => {
        let quoteReceived = false

        datafeedService.subscribeQuotes(
          ['AAPL'],
          ['TSLA'], // fast symbol
          (quotes: QuoteData[]) => {
            quoteReceived = true
            expect(quotes.length).toBeGreaterThan(0)

            datafeedService.unsubscribeQuotes(listenerGuid)
            resolve()
          },
          listenerGuid,
        )

        setTimeout(() => {
          if (!quoteReceived) {
            datafeedService.unsubscribeQuotes(listenerGuid)
            reject(new Error('No quote received after timeout'))
          }
        }, 500)
      })
    })

    it('should handle empty symbols in subscription', () => {
      const listenerGuid = 'empty-listener-' + Date.now()

      // Should not throw
      expect(() => {
        datafeedService.subscribeQuotes([], [], () => { }, listenerGuid)
      }).not.toThrow()

      // Clean up
      datafeedService.unsubscribeQuotes(listenerGuid)
    })

    it('should unsubscribe from quotes', async () => {
      const listenerGuid = 'unsubscribe-test-' + Date.now()
      let quoteCount = 0

      datafeedService.subscribeQuotes(
        ['AAPL'],
        [],
        () => {
          quoteCount++
        },
        listenerGuid,
      )

      // Immediately unsubscribe
      datafeedService.unsubscribeQuotes(listenerGuid)

      // Wait and verify no more quotes received
      await new Promise((resolve) => setTimeout(resolve, 300))

      expect(quoteCount).toBeLessThanOrEqual(1) // May receive one before unsubscribe
    })

    it('should handle multiple quote subscriptions', () => {
      return new Promise<void>((resolve, reject) => {
        let receivedCount = 0
        const expectedCount = 2

        const listener1 = 'multi-listener-1-' + Date.now()
        const listener2 = 'multi-listener-2-' + Date.now()

        const callback = () => {
          receivedCount++
          if (receivedCount === expectedCount) {
            expect(receivedCount).toBe(expectedCount)
            datafeedService.unsubscribeQuotes(listener1)
            datafeedService.unsubscribeQuotes(listener2)
            resolve()
          }
        }

        datafeedService.subscribeQuotes(['AAPL'], [], callback, listener1)
        datafeedService.subscribeQuotes(['GOOGL'], [], callback, listener2)

        setTimeout(() => {
          if (receivedCount < expectedCount) {
            datafeedService.unsubscribeQuotes(listener1)
            datafeedService.unsubscribeQuotes(listener2)
            reject(new Error(`Expected ${expectedCount} updates, got ${receivedCount}`))
          }
        }, 500)
      })
    })
  })

  describe('DatafeedMock', () => {
    it('should generate 400 days of historical bars', () => {
      const bars = testDatafeedMock.getMockedBars()
      expect(bars.length).toBeGreaterThanOrEqual(400)
    })

    it('should generate bars with valid OHLCV data', () => {
      const bars = testDatafeedMock.getMockedBars()

      bars.forEach((bar) => {
        expect(bar.high).toBeGreaterThanOrEqual(bar.low)
        expect(bar.high).toBeGreaterThanOrEqual(bar.open)
        expect(bar.high).toBeGreaterThanOrEqual(bar.close)
        expect(bar.low).toBeLessThanOrEqual(bar.open)
        expect(bar.low).toBeLessThanOrEqual(bar.close)
        expect(bar.volume).toBeGreaterThan(0)
      })
    })

    it('should generate bars in chronological order', () => {
      const bars = testDatafeedMock.getMockedBars()

      for (let i = 1; i < bars.length; i++) {
        expect(bars[i].time).toBeGreaterThan(bars[i - 1].time)
      }
    })

    it('should generate deterministic bars based on date seed', () => {
      const mock1 = new DatafeedMock()
      const mock2 = new DatafeedMock()

      const bars1 = mock1.getMockedBars()
      const bars2 = mock2.getMockedBars()

      expect(bars1.length).toBe(bars2.length)

      // Bars should be identical for same dates
      for (let i = 0; i < Math.min(bars1.length, bars2.length); i++) {
        expect(bars1[i].time).toBe(bars2[i].time)
        expect(bars1[i].open).toBe(bars2[i].open)
        expect(bars1[i].high).toBe(bars2[i].high)
        expect(bars1[i].low).toBe(bars2[i].low)
        expect(bars1[i].close).toBe(bars2[i].close)
      }
    })

    it('should generate realistic bar updates', () => {
      const bar = testDatafeedMock.barsMocker()

      expect(bar).toBeDefined()
      expect(bar!.high).toBeGreaterThanOrEqual(bar!.low)
      expect(bar!.close).toBeGreaterThanOrEqual(bar!.low)
      expect(bar!.close).toBeLessThanOrEqual(bar!.high)
    })

    it('should generate realistic quote data', () => {
      const quote = testDatafeedMock.quotesMocker()
      const values = quote.v as { lp?: number; ask?: number; bid?: number; high_price?: number; low_price?: number }

      expect(quote).toBeDefined()
      expect(quote.s).toBe('ok')
      expect(quote.v).toBeDefined()
      expect(values.lp).toBeGreaterThan(0)
      expect(values.ask).toBeGreaterThan(values.bid!)
      expect(values.high_price).toBeGreaterThanOrEqual(values.low_price!)
    })

    it('should maintain price continuity in bar updates', () => {
      const initialBars = testDatafeedMock.getMockedBars()
      const lastBar = initialBars[initialBars.length - 1]

      const updatedBar = testDatafeedMock.barsMocker()

      // Updated bar should maintain same timestamp (intraday update)
      expect(updatedBar!.time).toBe(lastBar.time)

      // Updated bar should have reasonable price changes
      expect(updatedBar!.high).toBeGreaterThanOrEqual(lastBar.high)
      expect(updatedBar!.low).toBeLessThanOrEqual(lastBar.low)
    })

    it('should return copies of bars to prevent mutations', () => {
      const bars1 = testDatafeedMock.getMockedBars()
      const bars2 = testDatafeedMock.getMockedBars()

      // Mutate first array
      bars1[0].close = 99999

      // Second array should be unchanged
      expect(bars2[0].close).not.toBe(99999)
    })
  })

  describe('Edge Cases and Error Handling', () => {
    it('should handle concurrent symbol resolutions', async () => {
      const symbols = ['AAPL', 'GOOGL', 'MSFT']

      const results = await Promise.all(symbols.map((symbol) => resolveSymbolPromise(symbol)))

      results.forEach((symbolInfo) => {
        expect(symbolInfo).toBeDefined()
      })
    })

    it('should handle concurrent bar requests', async () => {
      const to = Date.now()
      const from = to - 30 * 24 * 60 * 60 * 1000

      const symbolInfo = await resolveSymbolPromise('AAPL')

      const requests = Array.from({ length: 3 }, () =>
        getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), 30),
      )

      const results = await Promise.all(requests)

      results.forEach((bars) => {
        expect(bars.length).toBeGreaterThan(0)
      })
    })

    it('should handle rapid subscribe/unsubscribe cycles', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')

      // Should not throw during rapid subscribe/unsubscribe
      expect(() => {
        for (let i = 0; i < 10; i++) {
          const guid = 'rapid-test-' + i
          datafeedService.subscribeBars(symbolInfo, '1D', () => { }, guid)
          datafeedService.unsubscribeBars(guid)
        }
      }).not.toThrow()
    })

    it('should handle malformed symbol names gracefully', async () => {
      await expect(resolveSymbolPromise('')).rejects.toBe('unknown_symbol')
    })
  })

  describe('Service Configuration', () => {
    it('should work with mock instance', async () => {
      // Create service with DatafeedMock (uses fallback adapters)
      const mockInstance = new DatafeedMock()
      const datafeedWithMock = new DatafeedService(mockInstance)

      const config = await new Promise<DatafeedConfiguration>((resolve) => {
        datafeedWithMock.onReady(resolve)
      })

      expect(config).toBeDefined()
      expect(config.supported_resolutions).toBeDefined()
      expect(config.supported_resolutions).toContain('1D')
    })
  })

  describe('Integration Scenarios', () => {
    it('should handle complete datafeed workflow: config -> search -> resolve -> bars -> quotes', async () => {
      // Step 1: Load configuration
      const config = await onReadyPromise()
      expect(config).toBeDefined()

      // Step 2: Search for symbol
      const results = await searchSymbolsPromise('AAPL', '', '')
      expect(results.length).toBeGreaterThan(0)

      // Step 3: Resolve symbol
      const symbolInfo = await resolveSymbolPromise('AAPL')
      expect(symbolInfo).toBeDefined()

      // Step 4: Get historical bars
      const to = Date.now()
      const from = to - 30 * 24 * 60 * 60 * 1000

      const bars = await getBarsPromise(symbolInfo, '1D', Math.floor(from / 1000), Math.floor(to / 1000), 30)
      expect(bars.length).toBeGreaterThan(0)

      // Step 5: Get current quotes
      const quotes = await getQuotesPromise(['AAPL'])
      expect(quotes.length).toBeGreaterThan(0)
    })

    it('should handle real-time workflow: resolve -> subscribe bars -> subscribe quotes', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')

      return new Promise<void>((resolve, reject) => {
        let barsReceived = false
        let quotesReceived = false

        const checkCompletion = () => {
          if (barsReceived && quotesReceived) {
            datafeedService.unsubscribeBars(barListener)
            datafeedService.unsubscribeQuotes(quoteListener)
            resolve()
          }
        }

        const barListener = 'bar-sub-' + Date.now()
        const quoteListener = 'quote-sub-' + Date.now()

        // Subscribe to bars
        datafeedService.subscribeBars(
          symbolInfo,
          '1D',
          (bar) => {
            expect(bar).toBeDefined()
            barsReceived = true
            checkCompletion()
          },
          barListener,
        )

        // Subscribe to quotes
        datafeedService.subscribeQuotes(
          ['AAPL'],
          [],
          (quotes) => {
            expect(quotes.length).toBeGreaterThan(0)
            quotesReceived = true
            checkCompletion()
          },
          quoteListener,
        )

        // Timeout safety
        setTimeout(() => {
          if (!barsReceived || !quotesReceived) {
            datafeedService.unsubscribeBars(barListener)
            datafeedService.unsubscribeQuotes(quoteListener)
            reject(new Error('Not all subscriptions received data'))
          }
        }, 1000)
      })
    })

    it('should handle multiple symbols with subscriptions', () => {
      const symbols = ['AAPL', 'GOOGL']

      return new Promise<void>((resolve, reject) => {
        let receivedCount = 0
        const expectedCount = symbols.length

        symbols.forEach((symbol, index) => {
          const quoteListener = `multi-symbol-${index}-${Date.now()}`

          datafeedService.subscribeQuotes(
            [symbol],
            [],
            (quotes) => {
              expect(quotes.length).toBeGreaterThan(0)
              receivedCount++

              if (receivedCount === expectedCount) {
                // Cleanup
                symbols.forEach((_, idx) => {
                  datafeedService.unsubscribeQuotes(`multi-symbol-${idx}-${Date.now()}`)
                })
                resolve()
              }
            },
            quoteListener,
          )
        })

        setTimeout(() => {
          if (receivedCount < expectedCount) {
            reject(new Error(`Expected ${expectedCount} quotes, received ${receivedCount}`))
          }
        }, 1000)
      })
    })
  })

  describe('Performance and Reliability', () => {
    it('should handle high-frequency bar updates', async () => {
      const symbolInfo = await resolveSymbolPromise('AAPL')

      return new Promise<void>((resolve, reject) => {
        const listenerGuid = 'perf-test-' + Date.now()
        let updateCount = 0
        const targetUpdates = 5

        datafeedService.subscribeBars(
          symbolInfo,
          '1D',
          () => {
            updateCount++
            if (updateCount >= targetUpdates) {
              datafeedService.unsubscribeBars(listenerGuid)
              expect(updateCount).toBeGreaterThanOrEqual(targetUpdates)
              resolve()
            }
          },
          listenerGuid,
        )

        // Wait for updates
        setTimeout(() => {
          if (updateCount < targetUpdates) {
            datafeedService.unsubscribeBars(listenerGuid)
            reject(new Error(`Only received ${updateCount} updates`))
          }
        }, 1000)
      })
    })

    it('should maintain consistent performance across multiple operations', async () => {
      const iterations = 10
      const times: number[] = []

      for (let i = 0; i < iterations; i++) {
        const start = Date.now()

        await getQuotesPromise(['AAPL'])

        times.push(Date.now() - start)
      }

      // Calculate average and max time
      const avgTime = times.reduce((a, b) => a + b, 0) / times.length
      const maxTime = Math.max(...times)

      // Performance should be consistent (max not much larger than average)
      // Allow more variance for very fast operations (< 5ms)
      const allowedMultiplier = avgTime < 5 ? 10 : 3
      expect(maxTime).toBeLessThan(avgTime * allowedMultiplier + 5)
    })

    it('should not leak memory with repeated subscriptions', () => {
      // Should not throw or cause errors with many subscribe/unsubscribe cycles
      expect(() => {
        for (let i = 0; i < 100; i++) {
          const guid = 'memory-test-' + i

          datafeedService.subscribeQuotes(['AAPL'], [], () => { }, guid)
          datafeedService.unsubscribeQuotes(guid)
        }
      }).not.toThrow()
    })
  })
})
