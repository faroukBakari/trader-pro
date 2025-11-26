"""Type stubs for ibapi.contract module."""

from decimal import Decimal
from enum import Enum

from ibapi.object_implem import Object

SAME_POS: int
OPEN_POS: int
CLOSE_POS: int
UNKNOWN_POS: int

class ComboLeg(Object):
    conId: int
    ratio: int
    action: str
    exchange: str
    openClose: int
    shortSaleSlot: int
    designatedLocation: str
    exemptCode: int
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class DeltaNeutralContract(Object):
    conId: int
    delta: float
    price: float
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class Contract(Object):
    conId: int
    symbol: str
    secType: str
    lastTradeDateOrContractMonth: str
    lastTradeDate: str
    strike: float
    right: str
    multiplier: str
    exchange: str
    primaryExchange: str
    currency: str
    localSymbol: str
    tradingClass: str
    includeExpired: bool
    secIdType: str
    secId: str
    description: str
    issuerId: str
    comboLegsDescrip: str
    comboLegs: list[ComboLeg]
    deltaNeutralContract: DeltaNeutralContract | None
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class ContractDetails(Object):
    contract: Contract
    marketName: str
    minTick: float
    orderTypes: str
    validExchanges: str
    priceMagnifier: int
    underConId: int
    longName: str
    contractMonth: str
    industry: str
    category: str
    subcategory: str
    timeZoneId: str
    tradingHours: str
    liquidHours: str
    evRule: str
    evMultiplier: int
    aggGroup: int
    underSymbol: str
    underSecType: str
    marketRuleIds: str
    secIdList: list
    realExpirationDate: str
    lastTradeTime: str
    stockType: str
    minSize: Decimal
    sizeIncrement: Decimal
    suggestedSizeIncrement: Decimal
    # BOND values
    cusip: str
    ratings: str
    descAppend: str
    bondType: str
    couponType: str
    callable: bool
    putable: bool
    coupon: int
    convertible: bool
    maturity: str
    issueDate: str
    nextOptionDate: str
    nextOptionType: str
    nextOptionPartial: bool
    notes: str
    # FUND values
    fundName: str
    fundFamily: str
    fundType: str
    fundFrontLoad: str
    fundBackLoad: str
    fundBackLoadTimeInterval: str
    fundManagementFee: str
    fundClosed: bool
    fundClosedForNewInvestors: bool
    fundClosedForNewMoney: bool
    fundNotifyAmount: str
    fundMinimumInitialPurchase: str
    fundSubsequentMinimumPurchase: str
    fundBlueSkyStates: str
    fundBlueSkyTerritories: str
    fundDistributionPolicyIndicator: FundDistributionPolicyIndicator
    fundAssetType: FundAssetType
    ineligibilityReasonList: list
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class ContractDescription(Object):
    contract: Contract
    derivativeSecTypes: list[str]
    def __init__(self) -> None: ...

class FundAssetType(Enum):
    NoneItem: tuple[str, str]
    Others: tuple[str, str]
    MoneyMarket: tuple[str, str]
    FixedIncome: tuple[str, str]
    MultiAsset: tuple[str, str]
    Equity: tuple[str, str]
    Sector: tuple[str, str]
    Guaranteed: tuple[str, str]
    Alternative: tuple[str, str]

class FundDistributionPolicyIndicator(Enum):
    NoneItem: tuple[str, str]
    AccumulationFund: tuple[str, str]
    IncomeFund: tuple[str, str]
