// no codegen for this file as developer need to configure mappers as needed

import type {
  Bar,
  Execution,
  PlacedOrder,
  Position,
  QuoteData,
} from '@public/trading_terminal/charting_library';

// Per-module WebSocket types (microservice-ready architecture)
// Datafeed module types
import {
  type Bar as Bar_Ws_Backend,
  type BarsSubscriptionRequest as BarsSubscriptionRequest_Ws_Backend,
  type QuoteData as QuoteData_Ws_Backend,
  type QuoteDataSubscriptionRequest as QuoteDataSubscriptionRequest_Ws_Backend,
} from '../clients/ws-types-datafeed/index.js';

// Broker module types
import {
  type BrokerConnectionStatus as BrokerConnectionStatus_Ws_Backend,
  type BrokerConnectionSubscriptionRequest as BrokerConnectionSubscriptionRequest_Ws_Backend,
  type EquityData as EquityData_Ws_Backend,
  type EquitySubscriptionRequest as EquitySubscriptionRequest_Ws_Backend,
  type Execution as Execution_Ws_Backend,
  type ExecutionSubscriptionRequest as ExecutionSubscriptionRequest_Ws_Backend,
  type OrderSubscriptionRequest as OrderSubscriptionRequest_Ws_Backend,
  type PlacedOrder as PlacedOrder_Ws_Backend,
  type Position as Position_Ws_Backend,
  type PositionSubscriptionRequest as PositionSubscriptionRequest_Ws_Backend,
} from '../clients/ws-types-broker/index.js';

import {
  mapBrokerConnectionStatus,
  mapEquityData,
  mapExecution,
  mapOrder,
  mapPosition,
  mapQuoteData
} from './mappers.js';
import { WebSocketClient, WebSocketFallback, type WebSocketInterface } from './wsClientBase.js';

export type BarsSubscriptionRequest = BarsSubscriptionRequest_Ws_Backend
export type QuoteDataSubscriptionRequest = QuoteDataSubscriptionRequest_Ws_Backend
export type OrderSubscriptionRequest = OrderSubscriptionRequest_Ws_Backend
export type PositionSubscriptionRequest = PositionSubscriptionRequest_Ws_Backend
export type ExecutionSubscriptionRequest = ExecutionSubscriptionRequest_Ws_Backend
export type EquitySubscriptionRequest = EquitySubscriptionRequest_Ws_Backend
export type BrokerConnectionSubscriptionRequest = BrokerConnectionSubscriptionRequest_Ws_Backend
export type EquityData = EquityData_Ws_Backend
export type BrokerConnectionStatus = BrokerConnectionStatus_Ws_Backend

export type WsAdapterType = {
  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  orders: WebSocketInterface<OrderSubscriptionRequest, PlacedOrder>
  positions: WebSocketInterface<PositionSubscriptionRequest, Position>
  executions: WebSocketInterface<ExecutionSubscriptionRequest, Execution>
  equity: WebSocketInterface<EquitySubscriptionRequest, EquityData>
  brokerConnection: WebSocketInterface<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>
}

export class WsAdapter implements WsAdapterType {

  bars: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  orders: WebSocketInterface<OrderSubscriptionRequest, PlacedOrder>
  positions: WebSocketInterface<PositionSubscriptionRequest, Position>
  executions: WebSocketInterface<ExecutionSubscriptionRequest, Execution>
  equity: WebSocketInterface<EquitySubscriptionRequest, EquityData>
  brokerConnection: WebSocketInterface<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>

  constructor() {
    // TODO: make ws urls auto configurable
    const datafeedWsUrl = '/api/v1/datafeed/ws'
    this.bars = new WebSocketClient<BarsSubscriptionRequest, Bar_Ws_Backend, Bar>(datafeedWsUrl, 'bars', data => data)
    this.quotes = new WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_Ws_Backend, QuoteData>(
      datafeedWsUrl, 'quotes', mapQuoteData
    )

    // Broker clients - connect to /api/v1/broker/ws
    const brokerWsUrl = '/api/v1/broker/ws'
    this.orders = new WebSocketClient<OrderSubscriptionRequest, PlacedOrder_Ws_Backend, PlacedOrder>(
      brokerWsUrl, 'orders', mapOrder
    )
    this.positions = new WebSocketClient<PositionSubscriptionRequest, Position_Ws_Backend, Position>(
      brokerWsUrl, 'positions', mapPosition
    )
    this.executions = new WebSocketClient<ExecutionSubscriptionRequest, Execution_Ws_Backend, Execution>(
      brokerWsUrl, 'executions', mapExecution
    )
    this.equity = new WebSocketClient<EquitySubscriptionRequest, EquityData_Ws_Backend, EquityData>(
      brokerWsUrl, 'equity', mapEquityData
    )
    this.brokerConnection = new WebSocketClient<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus_Ws_Backend, BrokerConnectionStatus>(
      brokerWsUrl, 'broker-connection', mapBrokerConnectionStatus
    )
  }
}

export interface wsMocker {
  barsMocker?: () => Bar | undefined,
  quotesMocker?: () => QuoteData | undefined,
  ordersMocker?: () => PlacedOrder | undefined,
  positionsMocker?: () => Position | undefined,
  executionsMocker?: () => Execution | undefined,
  equityMocker?: () => EquityData | undefined,
  brokerConnectionMocker?: () => BrokerConnectionStatus | undefined,
}

export class WsFallback implements Partial<WsAdapterType> {

  bars?: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes?: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  orders?: WebSocketInterface<OrderSubscriptionRequest, PlacedOrder>
  positions?: WebSocketInterface<PositionSubscriptionRequest, Position>
  executions?: WebSocketInterface<ExecutionSubscriptionRequest, Execution>
  equity?: WebSocketInterface<EquitySubscriptionRequest, EquityData>
  brokerConnection?: WebSocketInterface<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>

  constructor(wsMocker: wsMocker) {
    if (wsMocker.barsMocker) this.bars = new WebSocketFallback<BarsSubscriptionRequest, Bar>(wsMocker.barsMocker.bind(wsMocker))
    if (wsMocker.quotesMocker) this.quotes = new WebSocketFallback<QuoteDataSubscriptionRequest, QuoteData>(wsMocker.quotesMocker.bind(wsMocker))
    if (wsMocker.ordersMocker) this.orders = new WebSocketFallback<OrderSubscriptionRequest, PlacedOrder>(wsMocker.ordersMocker.bind(wsMocker))
    if (wsMocker.positionsMocker) this.positions = new WebSocketFallback<PositionSubscriptionRequest, Position>(wsMocker.positionsMocker.bind(wsMocker))
    if (wsMocker.executionsMocker) this.executions = new WebSocketFallback<ExecutionSubscriptionRequest, Execution>(wsMocker.executionsMocker.bind(wsMocker))
    if (wsMocker.equityMocker) this.equity = new WebSocketFallback<EquitySubscriptionRequest, EquityData>(wsMocker.equityMocker.bind(wsMocker))
    if (wsMocker.brokerConnectionMocker) this.brokerConnection = new WebSocketFallback<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>(wsMocker.brokerConnectionMocker.bind(wsMocker))
  }
}
