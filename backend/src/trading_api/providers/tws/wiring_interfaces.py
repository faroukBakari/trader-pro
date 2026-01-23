from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Callable

from ibapi.common import BarData
from ibapi.contract import Contract

from trading_api.models.exceptions import ProviderException

if TYPE_CHECKING:
    from ibapi.contract import ContractDescription, ContractDetails


class QuoteTrackerCBWiringInterface(ABC):
    @abstractmethod
    def update(self, req_id: int, updates: dict[str, int | float | str]) -> None: ...

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool: ...


class BarsTrackerCBWiringInterface(ABC):
    @abstractmethod
    def update(self, req_id: int, bar_data: BarData) -> None: ...

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool: ...

    @abstractmethod
    def flag_complete(self, req_id: int, start: str, end: str) -> None: ...


class ContractTrackerCBWiringInterface(ABC):
    @abstractmethod
    def update_descriptions(
        self, req_id: int, descriptions: list["ContractDescription"]
    ) -> None: ...

    @abstractmethod
    def update_details(self, req_id: int, details: "ContractDetails") -> None: ...

    @abstractmethod
    def flag_details_complete(self, req_id: int) -> None: ...

    @abstractmethod
    def raise_error(self, req_id: int, exception: ProviderException) -> bool: ...


class PositionTrackerCBWiringInterface(ABC):
    @abstractmethod
    def upsert_position(
        self,
        account: str,
        contract: Contract,
        position: Decimal,
        avgCost: float,
    ) -> None: ...

    @abstractmethod
    def mark_snapshot_complete(self) -> None: ...

    @abstractmethod
    def raise_error(self, exception: ProviderException) -> None: ...


class IbSocketWiringInterface(ABC):
    @property
    @abstractmethod
    def next_req_id(self) -> int: ...

    @abstractmethod
    def send_message(self, msgId: int, values: list[object]) -> None: ...

    @abstractmethod
    def wire_quote_tracker(
        self,
        tracker_interface: QuoteTrackerCBWiringInterface,
    ) -> None: ...

    @abstractmethod
    def wire_bars_tracker(
        self,
        tracker_interface: BarsTrackerCBWiringInterface,
    ) -> None: ...

    @abstractmethod
    def wire_contract_tracker(
        self,
        tracker_interface: ContractTrackerCBWiringInterface,
    ) -> None: ...

    @abstractmethod
    def wire_position_tracker(
        self,
        tracker_interface: PositionTrackerCBWiringInterface,
    ) -> None: ...
