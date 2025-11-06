/**
 * Type Mappers
 *
 * Centralized type-safe data transformations between backend and frontend types.
 *
 * ⚠️ STRICT NAMING CONVENTIONS - MUST BE FOLLOWED ⚠️
 *
 * When importing types in this file, ALWAYS use these naming patterns:
 *
 * 1. API Backend types (from OpenAPI - per module):
 *    import type { TypeName as TypeName_Api_Backend } from '@clients/trader-client-{module}'
 *    Example: PreOrder as PreOrder_Api_Backend from trader-client-broker
 *
 * 2. WebSocket Backend types (from AsyncAPI - per module):
 *    import type { TypeName as TypeName_Ws_Backend } from '@clients/ws-types-{module}'
 *    Example: PlacedOrder as PlacedOrder_Ws_Backend from ws-types-broker
 *
 * 3. Frontend types (TradingView):
 *    import type { TypeName } from '@public/trading_terminal/charting_library'
 *    Example: PreOrder, PlacedOrder
 *
 * WHY STRICT NAMING?
 * - Instant recognition of type source at a glance
 * - Easy maintenance and debugging
 * - Clear distinction between API and WebSocket variants
 * - Consistent pattern across entire codebase
 *
 * ❌ WRONG: import type { PreOrder as PreOrder_Backend }
 * ❌ WRONG: import type { PlacedOrder as Order_Backend }
 * ✅ CORRECT: import type { PreOrder as PreOrder_Api_Backend }
 * ✅ CORRECT: import type { PlacedOrder as PlacedOrder_Ws_Backend }
 */

// Per-module API Backend types (OpenAPI)
import type {
  PreOrder as PreOrder_Api_Backend
} from '@clients/trader-client-broker_v1';
import type {
  QuoteData as QuoteData_Api_Backend
} from '@clients/trader-client-datafeed_v1';

// Per-module WebSocket Backend types (AsyncAPI)
import type {
  BrokerConnectionStatus as BrokerConnectionStatus_Ws_Backend,
  EquityData as EquityData_Ws_Backend,
  Execution as Execution_Ws_Backend,
  PlacedOrder as PlacedOrder_Ws_Backend,
  Position as Position_Ws_Backend
} from '@clients/ws-types-broker_v1';
import type {
  QuoteData as QuoteData_Ws_Backend
} from '@clients/ws-types-datafeed_v1';

// Frontend types (TradingView)
import type {
  Execution,
  PlacedOrder,
  Position,
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
 * Maps frontend PreOrder to backend PreOrder_Api_Backend
 * Handles enum type conversions for type, side, and stopType
 *
 * Note: seenPrice is sent by TradingView but not in official type definitions,
 * so we use type assertion to access it
 */
export function mapPreOrder(order: PreOrder): PreOrder_Api_Backend {
  // TradingView sends seenPrice but it's not in the official type definitions
  const orderWithSeenPrice = order as PreOrder & { seenPrice?: number | null }

  return {
    symbol: order.symbol,
    type: order.type as unknown as PreOrder_Api_Backend['type'],
    side: order.side as unknown as PreOrder_Api_Backend['side'],
    qty: order.qty,
    limitPrice: order.limitPrice ?? null,
    stopPrice: order.stopPrice ?? null,
    takeProfit: order.takeProfit ?? null,
    stopLoss: order.stopLoss ?? null,
    guaranteedStop: order.guaranteedStop ?? null,
    trailingStopPips: order.trailingStopPips ?? null,
    stopType: order.stopType ? (order.stopType as unknown as PreOrder_Api_Backend['stopType']) : null,
    seenPrice: orderWithSeenPrice.seenPrice ?? null,
    currentQuotes: order.currentQuotes
      ? {
        ask: order.currentQuotes.ask,
        bid: order.currentQuotes.bid,
      }
      : null,
  }
}/**
 * Maps backend PlacedOrder_Ws_Backend to TradingView PlacedOrder
 * Converts null values to undefined and handles enum types
 */
export function mapOrder(order: PlacedOrder_Ws_Backend): PlacedOrder {
  return {
    id: order.id,
    symbol: order.symbol,
    type: order.type as unknown as PlacedOrder['type'],
    side: order.side as unknown as PlacedOrder['side'],
    qty: order.qty,
    status: order.status as unknown as PlacedOrder['status'],
    limitPrice: order.limitPrice ?? undefined,
    stopPrice: order.stopPrice ?? undefined,
    filledQty: order.filledQty ?? undefined,
    avgPrice: order.avgPrice ?? undefined,
    updateTime: order.updateTime ?? undefined,
    takeProfit: order.takeProfit ?? undefined,
    stopLoss: order.stopLoss ?? undefined,
    guaranteedStop: order.guaranteedStop ?? undefined,
    trailingStopPips: order.trailingStopPips ?? undefined,
    stopType: order.stopType ? (order.stopType as unknown as PlacedOrder['stopType']) : undefined,
  }
}

/**
 * Maps backend Position_Ws_Backend to TradingView Position
 * Converts null values to undefined and handles enum types
 */
export function mapPosition(position: Position_Ws_Backend): Position {
  return {
    id: position.id,
    symbol: position.symbol,
    qty: position.qty,
    side: position.side as unknown as Position['side'],
    avgPrice: position.avgPrice,
  }
}

/**
 * Maps backend Execution_Ws_Backend to TradingView Execution
 * Handles enum type conversions for side
 */
export function mapExecution(execution: Execution_Ws_Backend): Execution {
  return {
    symbol: execution.symbol,
    price: execution.price,
    qty: execution.qty,
    side: execution.side as unknown as Execution['side'],
    time: execution.time,
  }
}

/**
 * Identity mapper for EquityData_Ws_Backend (no conversion needed)
 */
export function mapEquityData(data: EquityData_Ws_Backend): EquityData_Ws_Backend {
  return data
}

/**
 * Identity mapper for BrokerConnectionStatus_Ws_Backend (no conversion needed)
 */
export function mapBrokerConnectionStatus(status: BrokerConnectionStatus_Ws_Backend): BrokerConnectionStatus_Ws_Backend {
  return status
}
