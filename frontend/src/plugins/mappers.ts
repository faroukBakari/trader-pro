import type {
  PreOrder as PreOrder_Backend,
  QuoteData as QuoteData_Api_Backend
} from '@clients/trader-client-generated';
import type { QuoteData as QuoteData_Ws_Backend } from '@clients/ws-types-generated';
import type {
  PreOrder,
  QuoteData
} from '@public/trading_terminal/charting_library';


export function mapQuoteData(quote: QuoteData_Api_Backend | QuoteData_Ws_Backend): QuoteData {
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
}

/**
 * Maps frontend PreOrder to backend PreOrder_Backend
 * Handles enum type conversions for type, side, and stopType
 */
export function mapPreOrder(order: PreOrder): PreOrder_Backend {
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
}
