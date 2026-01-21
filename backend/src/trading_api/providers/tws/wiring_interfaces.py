from abc import ABC, abstractmethod

from ibapi.common import BarData

from trading_api.models.exceptions import ProviderException


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
