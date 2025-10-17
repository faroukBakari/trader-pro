// TODO: add dict with routes as keys and builder as vaues in the fashion of 'bar' => new  WebSocketInterface<BarsSubscriptionRequest, Bar>(bar)
// TODO: offline mode for asyncapi generator for ci

import type {
  Bar,
  QuoteData,
  QuoteDataResponse,
} from '@public/trading_terminal/charting_library';
import {
  type Bar as Bar_backend,
  type BarsSubscriptionRequest as BarsSubscriptionRequest_backend,
  type QuoteData as QuoteData_backend,
  type QuoteDataSubscriptionRequest as QuoteDataSubscriptionRequest_backend
} from '../clients/ws-types-generated/index.js';
import { WebSocketClient } from './wsClientBase.js';

export interface WebSocketInterface<TParams extends object, TData extends object> {
  subscribe(
    subscriptionId: string,
    params: TParams,
    onUpdate: (data: TData) => void
  ): Promise<string>
  unsubscribe(subscriptionId: string): Promise<void>
}


export type BarsSubscriptionRequest = BarsSubscriptionRequest_backend
export type QuoteDataSubscriptionRequest = QuoteDataSubscriptionRequest_backend

export class WsAdapter {

  bars: WebSocketClient<BarsSubscriptionRequest, Bar_backend, Bar>
  quotes: WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_backend, QuoteData>

  constructor() {
    this.bars = new WebSocketClient<BarsSubscriptionRequest, Bar_backend, Bar>('bars', data => data)
    this.quotes = new WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_backend, QuoteData>(
      'quotes', data => data as QuoteDataResponse as QuoteData
    )
  }
}
