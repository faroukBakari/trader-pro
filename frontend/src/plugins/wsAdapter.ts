// no codegen for this file as developer need to configure mappers as needed

import type {
  Bar,
  Execution,
  PlacedOrder,
  Position,
  QuoteData,
} from '@public/trading_terminal/charting_library';
import {
  type Bar as Bar_Ws_Backend,
  type BarsSubscriptionRequest as BarsSubscriptionRequest_Ws_Backend,
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
  type QuoteData as QuoteData_Ws_Backend,
  type QuoteDataSubscriptionRequest as QuoteDataSubscriptionRequest_Ws_Backend,
} from '../clients/ws-types-generated/index.js';
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
    // Datafeed clients
    this.bars = new WebSocketClient<BarsSubscriptionRequest, Bar_Ws_Backend, Bar>('bars', data => data)
    this.quotes = new WebSocketClient<QuoteDataSubscriptionRequest, QuoteData_Ws_Backend, QuoteData>(
      'quotes', mapQuoteData
    )

    // Broker clients
    this.orders = new WebSocketClient<OrderSubscriptionRequest, PlacedOrder_Ws_Backend, PlacedOrder>(
      'orders', mapOrder
    )
    this.positions = new WebSocketClient<PositionSubscriptionRequest, Position_Ws_Backend, Position>(
      'positions', mapPosition
    )
    this.executions = new WebSocketClient<ExecutionSubscriptionRequest, Execution_Ws_Backend, Execution>(
      'executions', mapExecution
    )
    this.equity = new WebSocketClient<EquitySubscriptionRequest, EquityData_Ws_Backend, EquityData>(
      'equity', mapEquityData
    )
    this.brokerConnection = new WebSocketClient<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus_Ws_Backend, BrokerConnectionStatus>(
      'broker-connection', mapBrokerConnectionStatus
    )
  }
}

export class WsFallback implements Partial<WsAdapterType> {

  bars?: WebSocketInterface<BarsSubscriptionRequest, Bar>
  quotes?: WebSocketInterface<QuoteDataSubscriptionRequest, QuoteData>
  orders?: WebSocketInterface<OrderSubscriptionRequest, PlacedOrder>
  positions?: WebSocketInterface<PositionSubscriptionRequest, Position>
  executions?: WebSocketInterface<ExecutionSubscriptionRequest, Execution>
  equity?: WebSocketInterface<EquitySubscriptionRequest, EquityData>
  brokerConnection?: WebSocketInterface<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>

  constructor({
    barsMocker,
    quotesMocker,
    ordersMocker,
    positionsMocker,
    executionsMocker,
    equityMocker,
    brokerConnectionMocker,
  }: {
    barsMocker?: () => Bar,
    quotesMocker?: () => QuoteData,
    ordersMocker?: () => PlacedOrder,
    positionsMocker?: () => Position,
    executionsMocker?: () => Execution,
    equityMocker?: () => EquityData,
    brokerConnectionMocker?: () => BrokerConnectionStatus,
  } = {}) {
    if (barsMocker) this.bars = new WebSocketFallback<BarsSubscriptionRequest, Bar>(barsMocker)
    if (quotesMocker) this.quotes = new WebSocketFallback<QuoteDataSubscriptionRequest, QuoteData>(quotesMocker)
    if (ordersMocker) this.orders = new WebSocketFallback<OrderSubscriptionRequest, PlacedOrder>(ordersMocker)
    if (positionsMocker) this.positions = new WebSocketFallback<PositionSubscriptionRequest, Position>(positionsMocker)
    if (executionsMocker) this.executions = new WebSocketFallback<ExecutionSubscriptionRequest, Execution>(executionsMocker)
    if (equityMocker) this.equity = new WebSocketFallback<EquitySubscriptionRequest, EquityData>(equityMocker)
    if (brokerConnectionMocker) this.brokerConnection = new WebSocketFallback<BrokerConnectionSubscriptionRequest, BrokerConnectionStatus>(brokerConnectionMocker)
  }
}
