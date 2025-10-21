// no codegen for this file as developer need to configure mappers as needed

import type {
  Bar,
  QuoteData,
} from '@public/trading_terminal/charting_library';
import {
  type Bar as Bar_backend,
  type BarsSubscriptionRequest as BarsSubscriptionRequest_backend,
  type QuoteData as QuoteData_backend,
  type QuoteDataSubscriptionRequest as QuoteDataSubscriptionRequest_backend
} from '../clients/ws-types-generated/index.js';
import { mapQuoteData } from './mappers.js';
import { WebSocketClient, WebSocketFallback, type WebSocketInterface } from './wsClientBase.js';

export type BarsSubscriptionRequest = BarsSubscriptionRequest_backend
export type QuoteDataSubscriptionRequest = QuoteDataSubscriptionRequest_backend

export type WsAdapterType = {
  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
}

export class WsAdapter implements WsAdapterType {

  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>

  constructor() {
    this.bars = new WebSocketClient<BarsSubscriptionRequest, Bar_backend, Bar>('bars', data => data)
    this.quotes = new WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_backend, QuoteData>(
      'quotes', mapQuoteData
    )
  }
}

export class WsFallback implements WsAdapterType {

  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>

  constructor({
    barsMocker,
    quotesMocker
  }: {
    barsMocker: () => Bar,
    quotesMocker: () => QuoteData
  }) {
    this.bars = new WebSocketFallback<BarsSubscriptionRequest, Bar>(barsMocker)
    this.quotes = new WebSocketFallback<QuoteDataSubscriptionRequest, QuoteData>(quotesMocker)
  }
}
