"""CachedContract - Combined contract description and details for caching.

This module provides a unified contract cache that can be populated from either
ContractDescription (partial, from symbol search) or ContractDetails (full).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.models.market.instruments import SearchSymbolResultItem
from trading_api.providers.tws.tws_mappers import (
    clone_contract,
    normalize_timezone,
    ticker_name,
)

# TWS secType → TradingView-style symbol type
SEC_TYPE_MAP: dict[str, str] = {
    "STK": "stock",
    "OPT": "option",
    "FUT": "futures",
    "FOP": "option",
    "CASH": "forex",
    "BOND": "bond",
    "FUND": "fund",
    "IND": "index",
    "CMDTY": "commodity",
    "WAR": "warrant",
    "CRYPTO": "crypto",
    "NEWS": "news",
    "BAG": "combo",
}


@dataclass
class CachedContract(ContractDetails):
    """Combined contract description and details for caching.

    Can be created from either ContractDescription (partial) or ContractDetails (full).
    The `has_full_details` flag indicates whether full contract details are available.

    Attributes:
        derivativeSecTypes: List of derivative security types (from ContractDescription)
        has_full_details: True if populated from ContractDetails, False if from ContractDescription
    """

    derivativeSecTypes: list[str] = field(default_factory=list)
    has_full_details: bool = False
    _ticker: str = ""
    overnight_hours: str | None = None

    # === Factory Methods ===

    @staticmethod
    def from_contract_details(
        details: ContractDetails, overnight_hours: str | None = None
    ) -> "CachedContract":
        """Create a CachedContract from a ContractDetails instance.

        Copies all attributes from the source ContractDetails and marks
        has_full_details=True.

        Args:
            details: The ContractDetails to convert
            overnight_hours: Optional overnight trading hours string (from OVERNIGHT exchange)

        Returns:
            A new CachedContract with full details
        """
        instance = CachedContract()
        instance.__dict__.update(details.__dict__)
        instance.secIdList = details.secIdList[:]
        instance.ineligibilityReasonList = details.ineligibilityReasonList[:]

        # Deep copy contract to avoid shared references
        instance.contract = clone_contract(details.contract)

        instance.has_full_details = True
        instance._ticker = ticker_name(instance.contract)
        instance.overnight_hours = overnight_hours
        return instance

    @staticmethod
    def from_contract_description(desc: ContractDescription) -> "CachedContract":
        """Create a CachedContract from a ContractDescription instance.

        Only copies contract and derivativeSecTypes fields. Other ContractDetails
        fields remain at defaults. Marks has_full_details=False.

        Args:
            desc: The ContractDescription to convert

        Returns:
            A new CachedContract with partial details
        """
        # Copy fields from ContractDescription
        instance = CachedContract()
        instance.__dict__.update(desc.__dict__)
        instance.derivativeSecTypes = desc.derivativeSecTypes[:]

        # Deep copy contract to avoid shared references
        instance.contract = clone_contract(desc.contract)

        # Mark as partial details
        instance.has_full_details = False
        instance._ticker = ticker_name(instance.contract)
        return instance

    # === Conversion Methods ===

    def to_contract_details(self) -> ContractDetails:
        """Export as a ContractDetails instance.

        Creates a new ContractDetails with all inherited attributes copied,
        excluding derivativeSecTypes and has_full_details.

        Returns:
            A new ContractDetails instance
        """
        details = ContractDetails()
        for key, value in self.__dict__.items():
            if key not in ("derivativeSecTypes", "has_full_details") and hasattr(
                details, key
            ):
                value_copy = (
                    value[:]
                    if isinstance(value, list)
                    else (
                        clone_contract(value) if isinstance(value, Contract) else value
                    )
                )
                setattr(details, key, value_copy)
        return details

    def to_contract_description(self) -> ContractDescription:
        """Export as a ContractDescription instance.

        Creates a new ContractDescription with contract and derivativeSecTypes.

        Returns:
            A new ContractDescription instance
        """
        desc = ContractDescription()
        desc.contract = clone_contract(self.contract)
        desc.derivativeSecTypes = self.derivativeSecTypes[:]
        return desc

    # === Serialization Methods (for SQLite persistence) ===

    def to_dict(self) -> dict[str, Any]:
        """Serialize ContractDescription fields for SQLite storage.

        Only serializes immutable instrument identity fields (from ContractDescription).
        ContractDetails fields (tradingHours, etc.) are NOT persisted as they are
        session-dependent and mutable.

        Returns:
            Dictionary suitable for SQLite INSERT/UPDATE
        """
        return {
            "con_id": self.contract.conId,
            "symbol": self.contract.symbol,
            "sec_type": self.contract.secType,
            "primary_exchange": self.contract.primaryExchange,
            "currency": self.contract.currency,
            "derivative_sec_types": self.derivativeSecTypes,
            "description": self.contract.description or "",
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CachedContract":
        """Deserialize from SQLite row to CachedContract (partial).

        Creates a CachedContract with ContractDescription-level data only.
        has_full_details=False since ContractDetails fields are not persisted.

        Args:
            data: Dictionary from SQLite row (con_id, symbol, sec_type, etc.)

        Returns:
            CachedContract with partial details (from ContractDescription)
        """
        contract = Contract()
        contract.conId = data["con_id"]
        contract.symbol = data["symbol"]
        contract.secType = data["sec_type"]
        contract.primaryExchange = data["primary_exchange"]
        contract.currency = data["currency"]
        contract.description = data.get("description", "")

        instance = CachedContract()
        instance.contract = contract
        instance.derivativeSecTypes = data.get("derivative_sec_types") or []
        instance.has_full_details = False
        instance._ticker = ticker_name(contract)
        return instance

    def to_search_result(self) -> SearchSymbolResultItem:
        """Map CachedContract → domain SearchSymbolResultItem.

        Args:
            desc: CachedContract from symbolSamples callback

        Returns:
            Domain SearchSymbolResultItem for frontend consumption
        """
        contract = self.contract
        description = contract.description or f"{contract.symbol} ({contract.secType})"
        type = SEC_TYPE_MAP.get(contract.secType, "stock")
        ticker = ticker_name(contract)
        return SearchSymbolResultItem(
            symbol=contract.symbol,
            description=description,
            exchange=contract.primaryExchange,
            ticker=ticker,
            type=type,
        )

    def update_from_details(self, details: ContractDetails) -> None:
        """Update this CachedContract with full details.

        Used to upgrade a partial cache entry (from ContractDescription)
        to full details (from ContractDetails).

        Args:
            details: The ContractDetails to merge
        """
        # Preserve derivativeSecTypes before update
        self.__dict__.update(details.__dict__)
        self.secIdList = details.secIdList[:]
        self.ineligibilityReasonList = details.ineligibilityReasonList[:]
        self.contract = clone_contract(details.contract)
        self.has_full_details = True

    @property
    def con_id(self) -> int:
        """Get the contract ID (conId) for cache key purposes."""
        return self.contract.conId

    @property
    def ticker(self) -> str:
        """Get the ticker name for logging purposes."""
        try:
            if not self._ticker:
                self._ticker = ticker_name(self.contract)
        finally:
            return self._ticker

    def matches(self, ticker: str) -> bool:
        """Check if this cached contract matches the given contract.

        Args:
            contract: The Contract to compare against
        Returns:
            True if matches, False otherwise
        """
        return ticker.startswith(self.ticker)

    def _is_trading_closed(
        self,
        trading_hours: str,
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        """Check if trading session is currently closed.

        Parses TWS tradingHours string and compares against current time
        in the instrument's timezone to determine if market is closed.

        Args:
            trading_hours: TWS tradingHours or liquidHours string
                Format: "YYYYMMDD:HHMM-YYYYMMDDHHMM;YYYYMMDD:CLOSED;..."
            timezone_id: TWS timeZoneId (e.g., "US/Eastern")
            reference_time: Override current time (for testing)

        Returns:
            True if market is closed, False if open

        Examples:
            >>> is_trading_closed("20260109:0930-20260109:1600", "US/Eastern")
            False  # During market hours
            >>> is_trading_closed("20260109:CLOSED", "US/Eastern")
            True   # Holiday
        """
        timezone_id = self.timeZoneId
        if not trading_hours:
            return True  # No hours = assume closed

        # Get current time in instrument's timezone
        tz = ZoneInfo(normalize_timezone(timezone_id))
        now = reference_time or datetime.now(tz)
        today_str = now.strftime("%Y%m%d")

        # Find today's segment in tradingHours
        for segment in trading_hours.split(";"):
            segment = segment.strip()
            if not segment:
                continue

            # Check if this segment is for today
            if not segment.startswith(today_str):
                continue

            # Today is explicitly CLOSED
            if "CLOSED" in segment:
                return True

            # Parse "YYYYMMDD:HHMM-YYYYMMDDHHMM" or "YYYYMMDD:HHMM-HHMM"
            if "-" not in segment:
                continue

            try:
                start_part, end_part = segment.split("-", 1)
                # Extract time: "YYYYMMDD:HHMM" → "HHMM"
                start_time_str = (
                    start_part.split(":", 1)[1] if ":" in start_part else start_part
                )
                end_time_str = (
                    end_part.split(":", 1)[1] if ":" in end_part else end_part
                )

                # Parse to time objects
                start_time = datetime.strptime(start_time_str, "%H%M").time()
                end_time = datetime.strptime(end_time_str, "%H%M").time()
                current_time = now.time()

                # Handle overnight session (end < start means crosses midnight)
                if end_time < start_time:
                    # Open if: current >= start OR current < end
                    return not (current_time >= start_time or current_time < end_time)
                else:
                    # Normal session: open if start <= current < end
                    return not (start_time <= current_time < end_time)

            except (ValueError, IndexError):
                continue

        # No matching segment for today = closed
        return True

    def is_session_closed(
        self,
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        return self._is_trading_closed(self.tradingHours, reference_time=reference_time)

    def is_darkpool_closed(
        self,
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        if not self.overnight_hours:
            return True
        return self._is_trading_closed(
            self.overnight_hours, reference_time=reference_time
        )

    def build_best_contract(self) -> Contract:
        contract = clone_contract(self.contract)
        if (
            "OVERNIGHT" in self.validExchanges
            and self.is_session_closed()
            and not self.is_darkpool_closed()
        ):
            contract.exchange = "OVERNIGHT"
        elif "SMART" in self.validExchanges:
            contract.exchange = "SMART"
        else:
            contract.exchange = contract.exchange or contract.primaryExchange
        return contract

    def build_smart_contract(self) -> Contract | None:
        contract = None
        if "SMART" in self.validExchanges:
            contract = clone_contract(self.contract)
            contract.exchange = "SMART"
        return contract

    def build_darkpool_contract(self: ContractDetails) -> Contract | None:
        contract = None
        if "OVERNIGHT" in self.validExchanges:
            contract = clone_contract(self.contract)
            contract.exchange = "OVERNIGHT"
        return contract
