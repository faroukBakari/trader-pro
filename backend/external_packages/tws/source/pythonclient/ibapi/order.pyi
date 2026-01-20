"""Type stubs for ibapi.order module."""

from decimal import Decimal
from typing import Any

from ibapi.contract import Contract
from ibapi.object_implem import Object
from ibapi.order_condition import OrderCondition
from ibapi.softdollartier import SoftDollarTier
from ibapi.tag_value import TagValue

# Enum Origin
CUSTOMER: int
FIRM: int
UNKNOWN: int

# Enum AuctionStrategy
AUCTION_UNSET: int
AUCTION_MATCH: int
AUCTION_IMPROVEMENT: int
AUCTION_TRANSPARENT: int

COMPETE_AGAINST_BEST_OFFSET_UP_TO_MID: float

class OrderComboLeg(Object):
    price: float
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class Order(Object):
    # Order identifier
    orderId: int
    clientId: int
    permId: int

    # Contract details
    contract: Contract

    # Main order fields
    action: str
    totalQuantity: Decimal
    orderType: str
    lmtPrice: float
    auxPrice: float

    # Extended order fields
    tif: str
    activeStartTime: str
    activeStopTime: str
    ocaGroup: str
    ocaType: int
    orderRef: str
    transmit: bool
    parentId: int
    blockOrder: bool
    sweepToFill: bool
    displaySize: int
    triggerMethod: int
    outsideRth: bool
    hidden: bool
    goodAfterTime: str
    goodTillDate: str
    rule80A: str
    allOrNone: bool
    minQty: int
    percentOffset: float
    overridePercentageConstraints: bool
    trailStopPrice: float
    trailingPercent: float

    # Financial advisors only
    faGroup: str
    faMethod: str
    faPercentage: str

    # Institutional only
    designatedLocation: str
    openClose: str
    origin: int
    shortSaleSlot: int
    exemptCode: int

    # SMART routing only
    discretionaryAmt: float
    optOutSmartRouting: bool

    # BOX exchange orders only
    auctionStrategy: int
    startingPrice: float
    stockRefPrice: float
    delta: float

    # Pegged to stock and VOL orders only
    stockRangeLower: float
    stockRangeUpper: float

    randomizePrice: bool
    randomizeSize: bool

    # VOLATILITY ORDERS ONLY
    volatility: float
    volatilityType: int
    deltaNeutralOrderType: str
    deltaNeutralAuxPrice: float
    deltaNeutralConId: int
    deltaNeutralSettlingFirm: str
    deltaNeutralClearingAccount: str
    deltaNeutralClearingIntent: str
    deltaNeutralOpenClose: str
    deltaNeutralShortSale: bool
    deltaNeutralShortSaleSlot: int
    deltaNeutralDesignatedLocation: str
    continuousUpdate: bool
    referencePriceType: int

    # COMBO ORDERS ONLY
    basisPoints: float
    basisPointsType: int

    # SCALE ORDERS ONLY
    scaleInitLevelSize: int
    scaleSubsLevelSize: int
    scalePriceIncrement: float
    scalePriceAdjustValue: float
    scalePriceAdjustInterval: int
    scaleProfitOffset: float
    scaleAutoReset: bool
    scaleInitPosition: int
    scaleInitFillQty: int
    scaleRandomPercent: bool
    scaleTable: str

    # HEDGE ORDERS
    hedgeType: str
    hedgeParam: str

    # Clearing info
    account: str
    settlingFirm: str
    clearingAccount: str
    clearingIntent: str

    # ALGO ORDERS ONLY
    algoStrategy: str
    algoParams: list[TagValue]
    smartComboRoutingParams: list[Any]
    algoId: str

    # What-if
    whatIf: bool

    # Not Held
    notHeld: bool
    solicited: bool

    # models
    modelCode: str

    # order combo legs
    orderComboLegs: list[OrderComboLeg]
    orderMiscOptions: list[Any]

    # VER PEG2BENCH fields
    referenceContractId: int
    peggedChangeAmount: float
    isPeggedChangeAmountDecrease: bool
    referenceChangeAmount: float
    referenceExchangeId: str
    adjustedOrderType: str

    triggerPrice: float
    adjustedStopPrice: float
    adjustedStopLimitPrice: float
    adjustedTrailingAmount: float
    adjustableTrailingUnit: int
    lmtPriceOffset: float

    conditions: list[OrderCondition]
    conditionsCancelOrder: bool
    conditionsIgnoreRth: bool

    # ext operator
    extOperator: str

    # native cash quantity
    cashQty: float

    mifid2DecisionMaker: str
    mifid2DecisionAlgo: str
    mifid2ExecutionTrader: str
    mifid2ExecutionAlgo: str

    dontUseAutoPriceForHedge: bool
    isOmsContainer: bool
    discretionaryUpToLimitPrice: bool
    autoCancelDate: str
    filledQuantity: Decimal
    refFuturesConId: int
    autoCancelParent: bool
    shareholder: str
    imbalanceOnly: bool
    routeMarketableToBbo: bool
    parentPermId: int

    usePriceMgmtAlgo: int | None
    duration: int
    postToAts: int
    advancedErrorOverride: str
    manualOrderTime: str
    minTradeQty: int
    minCompeteSize: int
    competeAgainstBestOffset: float
    midOffsetAtWhole: float
    midOffsetAtHalf: float
    customerAccount: str
    professionalCustomer: bool
    bondAccruedInterest: str
    includeOvernight: bool
    manualOrderIndicator: int
    submitter: str
    softDollarTier: SoftDollarTier

    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
