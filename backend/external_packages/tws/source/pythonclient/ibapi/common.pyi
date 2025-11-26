"""Type stubs for ibapi.common module."""

from decimal import Decimal
from typing import TypeAlias

from ibapi.object_implem import Object

# Type aliases
TickerId: TypeAlias = int
OrderId: TypeAlias = int
TagValueList: TypeAlias = list
FaDataType: TypeAlias = int
MarketDataType: TypeAlias = int
Liquidities: TypeAlias = int
SetOfString: TypeAlias = set[str]
SetOfFloat: TypeAlias = set[float]
ListOfOrder: TypeAlias = list
ListOfFamilyCode: TypeAlias = list
ListOfContractDescription: TypeAlias = list
ListOfDepthExchanges: TypeAlias = list
ListOfNewsProviders: TypeAlias = list
SmartComponentMap: TypeAlias = list
HistogramDataList: TypeAlias = list
ListOfPriceIncrements: TypeAlias = list
ListOfHistoricalTick: TypeAlias = list
ListOfHistoricalTickBidAsk: TypeAlias = list
ListOfHistoricalTickLast: TypeAlias = list
ListOfHistoricalSessions: TypeAlias = list

PROTOBUF_MSG_ID: int
PROTOBUF_MSG_IDS: dict[int, int]

# Enum-like instances
class _FaDataTypeEnum:
    GROUPS: int
    ALIASES: int
    def toStr(self, idx: int) -> str: ...

class _MarketDataTypeEnum:
    REALTIME: int
    FROZEN: int
    DELAYED: int
    DELAYED_FROZEN: int
    def toStr(self, idx: int) -> str: ...

class _LiquiditiesEnum:
    Added: int
    Remove: int
    RoudedOut: int
    def toStr(self, idx: int) -> str: ...

FaDataTypeEnum: _FaDataTypeEnum
MarketDataTypeEnum: _MarketDataTypeEnum
LiquiditiesEnum: _LiquiditiesEnum

class BarData(Object):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Decimal
    wap: Decimal
    barCount: int
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class RealTimeBar(Object):
    time: int
    endTime: int
    open_: float
    high: float
    low: float
    close: float
    volume: Decimal
    wap: Decimal
    count: int
    def __init__(
        self,
        time: int = 0,
        endTime: int = -1,
        open_: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
        close: float = 0.0,
        volume: Decimal = ...,
        wap: Decimal = ...,
        count: int = 0,
    ) -> None: ...
    def __str__(self) -> str: ...

class HistogramData(Object):
    price: float
    size: Decimal
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class NewsProvider(Object):
    code: str
    name: str
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class DepthMktDataDescription(Object):
    exchange: str
    secType: str
    listingExch: str
    serviceDataType: str
    aggGroup: int
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class SmartComponent(Object):
    bitNumber: int
    exchange: str
    exchangeLetter: str
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class TickAttrib(Object):
    canAutoExecute: bool
    pastLimit: bool
    preOpen: bool
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class TickAttribBidAsk(Object):
    bidPastLow: bool
    askPastHigh: bool
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class TickAttribLast(Object):
    pastLimit: bool
    unreported: bool
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class FamilyCode(Object):
    accountID: str
    familyCodeStr: str
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class PriceIncrement(Object):
    lowEdge: float
    increment: float
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class HistoricalTick(Object):
    time: int
    price: float
    size: Decimal
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class HistoricalTickBidAsk(Object):
    time: int
    tickAttribBidAsk: TickAttribBidAsk
    priceBid: float
    priceAsk: float
    sizeBid: Decimal
    sizeAsk: Decimal
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class HistoricalTickLast(Object):
    time: int
    tickAttribLast: TickAttribLast
    price: float
    size: Decimal
    exchange: str
    specialConditions: str
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class HistoricalSession(Object):
    startDateTime: str
    endDateTime: str
    refDate: str
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class WshEventData(Object):
    conId: int
    filter: str
    fillWatchlist: bool
    fillPortfolio: bool
    fillCompetitors: bool
    startDate: str
    endDate: str
    totalLimit: int
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
