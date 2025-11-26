"""Type stubs for ibapi.wrapper module."""

from abc import ABC, abstractmethod
from decimal import Decimal

from ibapi.commission_and_fees_report import CommissionAndFeesReport
from ibapi.common import (
    BarData,
    FaDataType,
    HistogramData,
    ListOfContractDescription,
    ListOfDepthExchanges,
    ListOfFamilyCode,
    ListOfHistoricalSessions,
    ListOfHistoricalTick,
    ListOfHistoricalTickBidAsk,
    ListOfHistoricalTickLast,
    ListOfNewsProviders,
    ListOfPriceIncrements,
    OrderId,
    SetOfFloat,
    SetOfString,
    SmartComponentMap,
    TickAttrib,
    TickAttribBidAsk,
    TickAttribLast,
    TickerId,
)
from ibapi.contract import Contract, ContractDetails, DeltaNeutralContract
from ibapi.execution import Execution
from ibapi.order import Order
from ibapi.order_state import OrderState
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.protobuf.ExecutionDetails_pb2 import (
    ExecutionDetails as ExecutionDetailsProto,
)
from ibapi.protobuf.ExecutionDetailsEnd_pb2 import (
    ExecutionDetailsEnd as ExecutionDetailsEndProto,
)
from ibapi.protobuf.OpenOrder_pb2 import OpenOrder as OpenOrderProto
from ibapi.protobuf.OpenOrdersEnd_pb2 import OpenOrdersEnd as OpenOrdersEndProto
from ibapi.protobuf.OrderStatus_pb2 import OrderStatus as OrderStatusProto
from ibapi.ticktype import TickType

def default_dispatcher(fnName: str, fnParams: dict) -> None: ...
def current_fn_name(parent_idx: int = 0) -> str: ...

class EWrapper(ABC):
    def dispatchMessage(self, fnName: str, fnParams: dict) -> None: ...
    def error(
        self,
        reqId: TickerId,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None: ...
    def winError(self, text: str, lastError: int) -> None: ...
    def connectAck(self) -> None: ...
    def marketDataType(self, reqId: TickerId, marketDataType: int) -> None: ...
    def tickPrice(
        self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib
    ) -> None: ...
    def tickSize(self, reqId: TickerId, tickType: TickType, size: Decimal) -> None: ...
    def tickSnapshotEnd(self, reqId: int) -> None: ...
    def tickGeneric(
        self, reqId: TickerId, tickType: TickType, value: float
    ) -> None: ...
    def tickString(self, reqId: TickerId, tickType: TickType, value: str) -> None: ...
    def tickEFP(
        self,
        reqId: TickerId,
        tickType: TickType,
        basisPoints: float,
        formattedBasisPoints: str,
        totalDividends: float,
        holdDays: int,
        futureLastTradeDate: str,
        dividendImpact: float,
        dividendsToLastTradeDate: float,
    ) -> None: ...
    def orderStatus(
        self,
        orderId: OrderId,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ) -> None: ...
    def openOrder(
        self, orderId: OrderId, contract: Contract, order: Order, orderState: OrderState
    ) -> None: ...
    def openOrderEnd(self) -> None: ...
    def connectionClosed(self) -> None: ...
    def updateAccountValue(
        self, key: str, val: str, currency: str, accountName: str
    ) -> None: ...
    def updatePortfolio(
        self,
        contract: Contract,
        position: Decimal,
        marketPrice: float,
        marketValue: float,
        averageCost: float,
        unrealizedPNL: float,
        realizedPNL: float,
        accountName: str,
    ) -> None: ...
    def updateAccountTime(self, timeStamp: str) -> None: ...
    def accountDownloadEnd(self, accountName: str) -> None: ...
    def nextValidId(self, orderId: int) -> None: ...
    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None: ...
    def bondContractDetails(
        self, reqId: int, contractDetails: ContractDetails
    ) -> None: ...
    def contractDetailsEnd(self, reqId: int) -> None: ...
    def execDetails(
        self, reqId: int, contract: Contract, execution: Execution
    ) -> None: ...
    def execDetailsEnd(self, reqId: int) -> None: ...
    def updateMktDepth(
        self,
        reqId: TickerId,
        position: int,
        operation: int,
        side: int,
        price: float,
        size: Decimal,
    ) -> None: ...
    def updateMktDepthL2(
        self,
        reqId: TickerId,
        position: int,
        marketMaker: str,
        operation: int,
        side: int,
        price: float,
        size: Decimal,
        isSmartDepth: bool,
    ) -> None: ...
    def updateNewsBulletin(
        self, msgId: int, msgType: int, newsMessage: str, originExch: str
    ) -> None: ...
    def managedAccounts(self, accountsList: str) -> None: ...
    def receiveFA(self, faData: FaDataType, cxml: str) -> None: ...
    def historicalData(self, reqId: int, bar: BarData) -> None: ...
    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None: ...
    def scannerParameters(self, xml: str) -> None: ...
    def scannerData(
        self,
        reqId: int,
        rank: int,
        contractDetails: ContractDetails,
        distance: str,
        benchmark: str,
        projection: str,
        legsStr: str,
    ) -> None: ...
    def scannerDataEnd(self, reqId: int) -> None: ...
    def realtimeBar(
        self,
        reqId: TickerId,
        time: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: Decimal,
        wap: Decimal,
        count: int,
    ) -> None: ...
    def currentTime(self, time: int) -> None: ...
    def fundamentalData(self, reqId: TickerId, data: str) -> None: ...
    def deltaNeutralValidation(
        self, reqId: int, deltaNeutralContract: DeltaNeutralContract
    ) -> None: ...
    def commissionAndFeesReport(
        self, commissionAndFeesReport: CommissionAndFeesReport
    ) -> None: ...
    def position(
        self, account: str, contract: Contract, position: Decimal, avgCost: float
    ) -> None: ...
    def positionEnd(self) -> None: ...
    def accountSummary(
        self, reqId: int, account: str, tag: str, value: str, currency: str
    ) -> None: ...
    def accountSummaryEnd(self, reqId: int) -> None: ...
    def verifyMessageAPI(self, apiData: str) -> None: ...
    def verifyCompleted(self, isSuccessful: bool, errorText: str) -> None: ...
    def verifyAndAuthMessageAPI(self, apiData: str, xyzChallange: str) -> None: ...
    def verifyAndAuthCompleted(self, isSuccessful: bool, errorText: str) -> None: ...
    def displayGroupList(self, reqId: int, groups: str) -> None: ...
    def displayGroupUpdated(self, reqId: int, contractInfo: str) -> None: ...
    def positionMulti(
        self,
        reqId: int,
        account: str,
        modelCode: str,
        contract: Contract,
        pos: Decimal,
        avgCost: float,
    ) -> None: ...
    def positionMultiEnd(self, reqId: int) -> None: ...
    def accountUpdateMulti(
        self,
        reqId: int,
        account: str,
        modelCode: str,
        key: str,
        value: str,
        currency: str,
    ) -> None: ...
    def accountUpdateMultiEnd(self, reqId: int) -> None: ...
    def tickOptionComputation(
        self,
        reqId: TickerId,
        tickType: TickType,
        tickAttrib: int,
        impliedVol: float,
        delta: float,
        optPrice: float,
        pvDividend: float,
        gamma: float,
        vega: float,
        theta: float,
        undPrice: float,
    ) -> None: ...
    def securityDefinitionOptionParameter(
        self,
        reqId: int,
        exchange: str,
        underlyingConId: int,
        tradingClass: str,
        multiplier: str,
        expirations: SetOfString,
        strikes: SetOfFloat,
    ) -> None: ...
    def securityDefinitionOptionParameterEnd(self, reqId: int) -> None: ...
    def softDollarTiers(self, reqId: int, tiers: list) -> None: ...
    def familyCodes(self, familyCodes: ListOfFamilyCode) -> None: ...
    def symbolSamples(
        self, reqId: int, contractDescriptions: ListOfContractDescription
    ) -> None: ...
    def mktDepthExchanges(
        self, depthMktDataDescriptions: ListOfDepthExchanges
    ) -> None: ...
    def tickNews(
        self,
        tickerId: int,
        timeStamp: int,
        providerCode: str,
        articleId: str,
        headline: str,
        extraData: str,
    ) -> None: ...
    def smartComponents(
        self, reqId: int, smartComponentMap: SmartComponentMap
    ) -> None: ...
    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None: ...
    def newsProviders(self, newsProviders: ListOfNewsProviders) -> None: ...
    def newsArticle(
        self, requestId: int, articleType: int, articleText: str
    ) -> None: ...
    def historicalNews(
        self,
        requestId: int,
        time: str,
        providerCode: str,
        articleId: str,
        headline: str,
    ) -> None: ...
    def historicalNewsEnd(self, requestId: int, hasMore: bool) -> None: ...
    def headTimestamp(self, reqId: int, headTimestamp: str) -> None: ...
    def histogramData(self, reqId: int, items: list[HistogramData]) -> None: ...
    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None: ...
    def rerouteMktDataReq(self, reqId: int, conId: int, exchange: str) -> None: ...
    def rerouteMktDepthReq(self, reqId: int, conId: int, exchange: str) -> None: ...
    def marketRule(
        self, marketRuleId: int, priceIncrements: ListOfPriceIncrements
    ) -> None: ...
    def pnl(
        self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float
    ) -> None: ...
    def pnlSingle(
        self,
        reqId: int,
        pos: Decimal,
        dailyPnL: float,
        unrealizedPnL: float,
        realizedPnL: float,
        value: float,
    ) -> None: ...
    def historicalTicks(
        self, reqId: int, ticks: ListOfHistoricalTick, done: bool
    ) -> None: ...
    def historicalTicksBidAsk(
        self, reqId: int, ticks: ListOfHistoricalTickBidAsk, done: bool
    ) -> None: ...
    def historicalTicksLast(
        self, reqId: int, ticks: ListOfHistoricalTickLast, done: bool
    ) -> None: ...
    def tickByTickAllLast(
        self,
        reqId: int,
        tickType: int,
        time: int,
        price: float,
        size: Decimal,
        tickAttribLast: TickAttribLast,
        exchange: str,
        specialConditions: str,
    ) -> None: ...
    def tickByTickBidAsk(
        self,
        reqId: int,
        time: int,
        bidPrice: float,
        askPrice: float,
        bidSize: Decimal,
        askSize: Decimal,
        tickAttribBidAsk: TickAttribBidAsk,
    ) -> None: ...
    def tickByTickMidPoint(self, reqId: int, time: int, midPoint: float) -> None: ...
    def orderBound(self, permId: int, clientId: int, orderId: int) -> None: ...
    def completedOrder(
        self, contract: Contract, order: Order, orderState: OrderState
    ) -> None: ...
    def completedOrdersEnd(self) -> None: ...
    def replaceFAEnd(self, reqId: int, text: str) -> None: ...
    def wshMetaData(self, reqId: int, dataJson: str) -> None: ...
    def wshEventData(self, reqId: int, dataJson: str) -> None: ...
    def historicalSchedule(
        self,
        reqId: int,
        startDateTime: str,
        endDateTime: str,
        timeZone: str,
        sessions: ListOfHistoricalSessions,
    ) -> None: ...
    def userInfo(self, reqId: int, whiteBrandingId: str) -> None: ...
    def currentTimeInMillis(self, timeInMillis: int) -> None: ...

    # Protobuf methods
    def orderStatusProtoBuf(self, orderStatusProto: OrderStatusProto) -> None: ...
    def openOrderProtoBuf(self, openOrderProto: OpenOrderProto) -> None: ...
    def openOrdersEndProtoBuf(self, openOrdersEndProto: OpenOrdersEndProto) -> None: ...
    def errorProtoBuf(self, errorMessageProto: ErrorMessageProto) -> None: ...
    def executionDetailsProtoBuf(
        self, executionDetailsProto: ExecutionDetailsProto
    ) -> None: ...
    def executionDetailsEndProtoBuf(
        self, executionDetailsProto: ExecutionDetailsEndProto
    ) -> None: ...
