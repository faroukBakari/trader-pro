from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

from ibapi.common import BarData
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.order_state import OrderState

from trading_api.models.exceptions import ProviderException

if TYPE_CHECKING:
    from ibapi.contract import ContractDescription, ContractDetails
    from ibapi.execution import Execution as TWSExecution


class QuoteTrackerCBWiringInterface(ABC):
    @abstractmethod
    def update(self, req_id: int, updates: dict[str, int | float | str]) -> None:
        ...

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        ...


class BarsTrackerCBWiringInterface(ABC):
    @abstractmethod
    def update(self, req_id: int, bar_data: BarData) -> None:
        ...

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        ...

    @abstractmethod
    def flag_complete(self, req_id: int, start: str, end: str) -> None:
        ...


class ContractTrackerCBWiringInterface(ABC):
    @abstractmethod
    def update_descriptions(
        self, req_id: int, descriptions: list["ContractDescription"]
    ) -> None:
        ...

    @abstractmethod
    def update_details(self, req_id: int, details: "ContractDetails") -> None:
        ...

    @abstractmethod
    def flag_details_complete(self, req_id: int) -> None:
        ...

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        ...


class PositionTrackerCBWiringInterface(ABC):
    @abstractmethod
    def upsert_position(
        self,
        account: str,
        contract: Contract,
        position: Decimal,
        avgCost: float,
    ) -> None:
        ...

    @abstractmethod
    def mark_snapshot_complete(self) -> None:
        ...

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None:
        ...


class ExecutionTrackerCBWiringInterface(ABC):
    @abstractmethod
    def upsert_execution(
        self,
        contract: Contract,
        execution: "TWSExecution",
    ) -> None:
        ...

    @abstractmethod
    def update_commission(self, exec_id: str, commission: float) -> None:
        ...

    @abstractmethod
    def mark_snapshot_complete(self) -> None:
        ...

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None:
        ...


class OrderTrackerCBWiringInterface(ABC):
    @abstractmethod
    def upsert_order(
        self,
        orderId: int,
        contract: Contract,
        order: Order,
        orderState: OrderState,
    ) -> None:
        ...

    @abstractmethod
    def update_status(
        self,
        orderId: int,
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
    ) -> None:
        ...

    @abstractmethod
    def mark_snapshot_complete(self) -> None:
        ...

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None:
        ...


class IbSocketWiringInterface(ABC):
    @property
    @abstractmethod
    def next_req_id(self) -> int:
        ...

    @abstractmethod
    def send_message(self, msgId: int, values: list[object]) -> None:
        ...

    @abstractmethod
    def send_protobuf(self, msgId: int, protobuf_data: bytes) -> None:
        ...

    @abstractmethod
    def wire_quote_tracker(
        self,
        tracker_interface: QuoteTrackerCBWiringInterface,
    ) -> None:
        ...

    @abstractmethod
    def wire_bars_tracker(
        self,
        tracker_interface: BarsTrackerCBWiringInterface,
    ) -> None:
        ...

    @abstractmethod
    def wire_contract_tracker(
        self,
        tracker_interface: ContractTrackerCBWiringInterface,
    ) -> None:
        ...

    @abstractmethod
    def wire_position_tracker(
        self,
        tracker_interface: PositionTrackerCBWiringInterface,
    ) -> None:
        ...

    @abstractmethod
    def wire_execution_tracker(
        self,
        tracker_interface: ExecutionTrackerCBWiringInterface,
    ) -> None:
        ...

    @abstractmethod
    def wire_order_tracker(
        self,
        tracker_interface: OrderTrackerCBWiringInterface,
    ) -> int | None:
        ...
