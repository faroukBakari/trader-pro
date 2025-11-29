"""Type stubs for ibapi.commission_and_fees_report module."""

from ibapi.object_implem import Object

class CommissionAndFeesReport(Object):
    execId: str
    commissionAndFees: float
    currency: str
    realizedPNL: float
    yield_: float
    yieldRedemptionDate: int
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
