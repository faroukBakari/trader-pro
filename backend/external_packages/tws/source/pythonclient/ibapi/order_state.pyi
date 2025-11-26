"""Type stubs for ibapi.order_state module."""

from decimal import Decimal

from ibapi.object_implem import Object

class OrderAllocation(Object):
    account: str
    position: Decimal
    positionDesired: Decimal
    positionAfter: Decimal
    desiredAllocQty: Decimal
    allowedAllocQty: Decimal
    isMonetary: bool
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...

class OrderState:
    status: str
    initMarginBefore: str
    maintMarginBefore: str
    equityWithLoanBefore: str
    initMarginChange: str
    maintMarginChange: str
    equityWithLoanChange: str
    initMarginAfter: str
    maintMarginAfter: str
    equityWithLoanAfter: str
    commissionAndFees: float
    minCommissionAndFees: float
    maxCommissionAndFees: float
    commissionAndFeesCurrency: str
    marginCurrency: str
    initMarginBeforeOutsideRTH: float
    maintMarginBeforeOutsideRTH: float
    equityWithLoanBeforeOutsideRTH: float
    initMarginChangeOutsideRTH: float
    maintMarginChangeOutsideRTH: float
    equityWithLoanChangeOutsideRTH: float
    initMarginAfterOutsideRTH: float
    maintMarginAfterOutsideRTH: float
    equityWithLoanAfterOutsideRTH: float
    suggestedSize: Decimal
    rejectReason: str
    orderAllocations: list[OrderAllocation]
    warningText: str
    completedTime: str
    completedStatus: str
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
