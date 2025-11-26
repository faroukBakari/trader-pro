"""Type stubs for ibapi.execution module."""

from decimal import Decimal
from enum import Enum

from ibapi.object_implem import Object

class Execution(Object):
    execId: str
    time: str
    acctNumber: str
    exchange: str
    side: str
    shares: Decimal
    price: float
    permId: int
    clientId: int
    orderId: int
    liquidation: int
    cumQty: Decimal
    avgPrice: float
    orderRef: str
    evRule: str
    evMultiplier: float
    modelCode: str
    lastLiquidity: int
    pendingPriceRevision: bool
    submitter: str
    optExerciseOrLapseType: OptionExerciseType
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class ExecutionFilter(Object):
    clientId: int
    acctCode: str
    time: str
    symbol: str
    secType: str
    exchange: str
    side: str
    lastNDays: int
    specificDates: list[str]
    def __init__(self) -> None: ...

class OptionExerciseType(Enum):
    NoneItem: tuple[int, str]
    Exercise: tuple[int, str]
    Lapse: tuple[int, str]
    DoNothing: tuple[int, str]
    Assigned: tuple[int, str]
    AutoexerciseClearing: tuple[int, str]
    Expired: tuple[int, str]
    Netting: tuple[int, str]
    AutoexerciseTrading: tuple[int, str]
